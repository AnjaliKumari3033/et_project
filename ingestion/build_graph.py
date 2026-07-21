"""Build the expanded multi-entity knowledge graph (NetworkX DiGraph).

This phase reads from the SQLite DB built by build_sql.py and constructs:
  - Equipment nodes (15)  + feeds/powers/etc. edges (13)  + attributes from
    equipment_master + plant_layout + pm_schedule
  - Event nodes (75)  + occurred_on edges  + has_chain edges  +
    caused_by_failure edges  + reported_by / assigned_to edges
  - Document nodes (675) from document_index  + documents edges (Document->Event)
  - Employee nodes (50)  + belongs_to (Employee->Department) edges
  - Department nodes (8)  from department_document_matrix / distinct employee.dept
  - SparePart nodes (10)  + needs_part (Equipment->Part) edges (CSV-split)
      + recommended_for (SparePart|Equipment <- FailureTaxonomy) edges
  - FailureCategory nodes (11 hierarchical Level1/2/3)  + leaf taxonomy siblings
  - Chain nodes from plant_events.Chain_ID  + Event->Chain edges
  - EquipmentClass nodes (Pump/Motor/etc. derived from equipment name suffix)
      + of_class (Equipment->EquipmentClass) edges

PDF nodes (~85) and PDF-derived edges ("references_equipment", "references_class",
"describes_chemical", "governs") are not added here — those are added in
ingest_pdfs.py once the public_document corpus has been parsed.

The doc-doc "cites" edges (from the "Linked Documents" section inside each
generated .docx) are also added in ingest_docx.py, not here, because they require
reading the actual .docx content (and require the .txt->.docx email extension fix).

All counts per the dataset report:
    ~870 nodes / ~900 edges (without PDF + doc-doc edges; with them it lands at
    the announced ~870 nodes / ~900 edges).
"""
from __future__ import annotations

import pickle
import re
import sqlite3
from pathlib import Path
from typing import Any

import networkx as nx

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "sqlite" / "novachem.db"
G_PATH = ROOT / "data" / "graph" / "equipment_graph.pkl"

# Heuristics for EquipmentClass derivation from "Equipment Name" suffix.
# (Suffix used because typical names are "Feed Pump", "Air Compressor", "Steam
# Boiler", "Cooling Tower Fan", "Raw Material Storage Tank", etc. The LAST word
# is the noun; we map common industrial nouns to canonical classes.)
CLASS_KEYWORDS = {
    "pump": "Pump",
    "compressor": "Compressor",
    "boiler": "Boiler",
    "tank": "Tank",
    "heat exchanger": "HeatExchanger",
    "motor": "Motor",
    "fan": "Fan",
    "tower": "CoolingTower",
    "reactor": "Reactor",
    "valve": "Valve",
    "separator": "Separator",
    "filter": "Filter",
    "conveyor": "Conveyor",
    "blower": "Blower",
    "generator": "Generator",
}


def _derive_class(name: str) -> str | None:
    if not name:
        return None
    n = str(name).lower()
    for kw, cls in CLASS_KEYWORDS.items():
        if kw in n:
            return cls
    return None


def build() -> nx.DiGraph:
    if not DB_PATH.exists():
        raise SystemExit(f"SQLite DB missing at {DB_PATH} -- run build_sql.py first.")
    G_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    G = nx.DiGraph()

    def add_node(node_id: str, kind: str, **attrs: Any) -> None:
        if node_id is None or str(node_id).strip() == "":
            return
        if node_id in G.nodes:
            G.nodes[node_id].update(attrs, kind=kind)
        else:
            G.add_node(node_id, kind=kind, **attrs)

    def add_edge(src: str | None, dst: str | None, rel: str, **attrs: Any) -> None:
        if not src or not dst:
            return
        if src not in G.nodes:
            return
        if dst not in G.nodes:
            return
        if G.has_edge(src, dst):
            G[src][dst].setdefault("relationships", []).append(rel)
            G[src][dst].update(attrs)
        else:
            G.add_edge(src, dst, relationship=rel, **attrs)

    # ---------- Equipment + attributes from plant_layout + pm_schedule ----------
    equip_rows = conn.execute("SELECT * FROM equipment_master").fetchall()
    layout_by_id = {r["equipment_id"]: r for r in conn.execute("SELECT * FROM plant_layout").fetchall()}
    pm_by_id = {r["equipment_id"]: r for r in conn.execute("SELECT * FROM preventive_maintenance_schedule").fetchall()}

    for r in equip_rows:
        eid = r["equipment_id"]
        attrs = {
            "name": r["equipment_name"],
            "area": r["area"],
            "manufacturer": r["manufacturer"],
            "install_year": r["install_year"],
            "status": r["status"],
        }
        if eid in layout_by_id:
            lo = layout_by_id[eid]
            attrs.update({
                "building": lo["building"],
                "floor": lo["floor"],
                "nearby_equipment": lo["nearby_equipment"],
                "criticality_layout": lo["criticality"],
            })
        if eid in pm_by_id:
            pm = pm_by_id[eid]
            attrs.update({
                "pm_frequency": pm["maintenance_frequency"],
                "next_pm_due": pm["next_pm_due"],
                "assigned_technician": pm["assigned_technician"],
            })
        add_node(eid, "Equipment", **attrs)

        cls = _derive_class(attrs.get("name") or "")
        if cls:
            add_node(cls, "EquipmentClass")
            add_edge(eid, cls, "of_class", derivation_method="name_suffix")

    # ---------- Equipment --feeds/powers--> Equipment (13 edges) ----------
    for r in conn.execute("SELECT * FROM equipment_relationships").fetchall():
        add_node(r["source_equipment"], "Equipment")
        add_node(r["target_equipment"], "Equipment")
        add_edge(r["source_equipment"], r["target_equipment"], r["relationship"].strip(), reason=r["reason"])

    # ---------- Events ----------
    event_rows = conn.execute("SELECT * FROM plant_events").fetchall()
    # Build Hmm sets for expert_in
    # Failure category edges
    fc_root_seen: set[str] = set()
    for r in event_rows:
        eid = r["event_id"]
        add_node(eid, "Event",
                 date=r["date"],
                 equipment_id=r["equipment_id"],
                 event_type=r["event_type"],
                 department=r["department"],
                 severity=r["severity"],
                 priority=r["priority"],
                 status=r["status"],
                 downtime_hrs=r["downtime_hrs"],
                 description=r["description"],
                 root_cause=r["root_cause"],
                 corrective_action=r["corrective_action"])
        # Event -> Equipment
        add_edge(eid, r["equipment_id"], "occurred_on")
        # Event -> Chain
        chain_id = r["chain_id"]
        if chain_id:
            add_node(chain_id, "Chain")
            add_edge(eid, chain_id, "has_chain")
        # Event -> FailureCategory (L1 only here)
        fc = (r["failure_category"] or "").strip()
        if fc:
            add_node(fc, "FailureCategory", level=1)
            fc_root_seen.add(fc)
            add_edge(eid, fc, "caused_by_failure")

    # ---------- FailureTaxonomy (11 rows) -> hierarchical nodes ----------
    # Build composite IDs like "FC:Mechanical" , "FC:Mechanical>Bearing Failure", etc.
    def _fc_id(levels: list[str]) -> str:
        return "FC:" + ">".join(levels)

    for r in conn.execute("SELECT * FROM failure_taxonomy").fetchall():
        levels = [str(r["level_1"] or "").strip(), str(r["level_2"] or "").strip(), str(r["level_3"] or "").strip()]
        levels = [lv for lv in levels if lv]
        if not levels:
            continue
        parent_id: str | None = None
        for i in range(1, len(levels) + 1):
            nid = _fc_id(levels[:i])
            attrs = {}
            if i == len(levels):
                attrs.update({
                    "possible_cause": r["possible_cause"],
                    "affected_equipment": r["affected_equipment"],
                    "recommended_action": r["recommended_action"],
                })
            add_node(nid, "FailureCategory", level=i, label=levels[i-1], **attrs)
            if parent_id:
                add_edge(parent_id, nid, "subsumes")
            else:
                # connect L1 root to the L1 plain-named node created from plant_events
                # (e.g. "Mechanical" node created above with level=1)
                root_label = levels[0]
                if root_label in fc_root_seen and root_label != nid:
                    # merge: add same attributes to the plain node & add a "same_as" edge
                    add_edge(nid, root_label, "same_as")
            parent_id = nid

    # ---------- SpareParts + needs_part ----------
    parts = conn.execute("SELECT * FROM spare_parts_inventory").fetchall()
    for r in parts:
        pid = r["part_id"]
        add_node(pid, "SparePart",
                 name=r["part_name"],
                 category=r["category"],
                 used_for=r["used_for"],
                 quantity_available=r["quantity_available"],
                 min_stock=r["minimum_stock_level"],
                 storage=r["storage_location"],
                 criticality=r["criticality"],
                 stock_status=r["stock_status"])
        compat = (r["compatible_equipment"] or "")
        for eq in re.split(r"[,;/]", compat):
            eq = eq.strip()
            if eq:
                add_edge(eq, pid, "needs_part")

    # ---------- Employees + Departments ----------
    depts_seen: set[str] = set()
    for r in conn.execute("SELECT * FROM novachem_employees").fetchall():
        emp_id = r["employee_id"]
        dept = (r["department"] or "").strip()
        add_node(emp_id, "Employee",
                 name=r["name"],
                 department=dept,
                 role=r["role"],
                 experience=r["experience"],
                 email=r["email"])
        if dept:
            add_node(dept, "Department")
            depts_seen.add(dept)
            add_edge(emp_id, dept, "belongs_to")
        # expert_in heuristic: role keyword -> FailureCategory or EquipmentClass
        role_lower = (r["role"] or "").lower()
        if "mechanical" in role_lower:
            add_node("Mechanical", "FailureCategory", level=1)
            add_edge(emp_id, "Mechanical", "expert_in", derivation_method="role_keyword")
        if "electrical" in role_lower:
            add_node("Electrical", "FailureCategory", level=1)
            add_edge(emp_id, "Electrical", "expert_in", derivation_method="role_keyword")
        if "instrument" in role_lower or "calibration" in role_lower:
            add_node("Instrument", "FailureCategory", level=1)
            add_edge(emp_id, "Instrument", "expert_in", derivation_method="role_keyword")
        if "safety" in role_lower:
            add_node("Safety", "FailureCategory", level=1)
            add_edge(emp_id, "Safety", "expert_in", derivation_method="role_keyword")
        # operator role -> EquipmentClass expert via department inference (best effort)
        if "operator" in role_lower:
            # Operators in Tank Farm / Production typically expert in Pump/Reactor etc.
            pass

    # Department nodes from department_document_matrix (add any missing)
    for r in conn.execute("SELECT * FROM department_document_matrix").fetchall():
        d = r["department"]
        if d:
            add_node(d, "Department", creates_documents=r["creates_documents"])

    # ---------- Documents (generated) from document_index ----------
    # File Name is the canonical node id (e.g. "MNT_EVT-001.docx").
    doc_rows = conn.execute("SELECT * FROM document_index").fetchall()
    for r in doc_rows:
        fname = r["file_name"]
        add_node(fname, "Document",
                 document_id=r["document_id"],
                 document_type=r["document_type"],
                 source="generated_docx",
                 file_name=fname,
                 event_id=r["event_id"],
                 equipment_id=r["equipment_id"],
                 equipment_name=r["equipment_name"],
                 department=r["department"],
                 date=r["date"],
                 failure_category=r["failure_category"],
                 root_cause=r["root_cause"],
                 status=r["status"])
        add_edge(fname, r["event_id"], "documents")
        # If document references an equipment (most do), add Document->Equipment edge
        if r["equipment_id"]:
            add_edge(fname, r["equipment_id"], "pertains_to")

    # ---------- Event <-> Employee (reported_by / assigned_to) ----------
    # employee lookup by Name -> Employee ID
    emp_by_name: dict[str, str] = {}
    for r in conn.execute("SELECT employee_id, name FROM novachem_employees").fetchall():
        emp_by_name[(r["name"] or "").strip().lower()] = r["employee_id"]
    for r in event_rows:
        for col, rel in (("reported_by", "reported_by"), ("assigned_to", "assigned_to")):
            raw = r[col] if col in r.keys() else None
            if not raw:
                continue
            emp_id = emp_by_name.get(raw.strip().lower())
            if emp_id:
                add_edge(r["event_id"], emp_id, rel)

    # ---------- Doc-doc `cites` edges (from Linked Documents sections in .docx) ----------
    # Per the architecture plan: every generated .docx contains a "Linked Documents"
    # section listing sibling doc filenames. Email references erroneously have a
    # .txt extension due to a known bug in Scripts/utils.py:266 -- ingest_docx.py
    # normalizes those to .docx before storing in the citations list.
    cites_pkl = ROOT / "data" / "docx_chunks.pkl"
    n_cites_added = 0
    if cites_pkl.exists():
        import pickle as _pk
        with open(cites_pkl, "rb") as _f:
            _chunks_data = _pk.load(_f)
        for src_doc, tgt_doc in _chunks_data.get("citations", []):
            # Only add edge if both endpoints exist (tgt may not have been
            # generated if e.g. the doc generation script skipped an event).
            if src_doc in G.nodes and tgt_doc in G.nodes:
                add_edge(src_doc, tgt_doc, "cites", derivation_method="linked_documents_section",
                         nag_extension_normalized=True)
                n_cites_added += 1

    conn.close()

    # Serialize
    with open(G_PATH, "wb") as f:
        pickle.dump(G, f)

    # Report
    by_kind: dict[str, int] = {}
    for _, d in G.nodes(data=True):
        by_kind[d.get("kind", "?")] = by_kind.get(d.get("kind", "?"), 0) + 1
    print("\n--- Knowledge graph build summary ---")
    print(f"Nodes: {G.number_of_nodes()}")
    for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1]):
        print(f"   {k:18s} {v:>4d}")
    print(f"Edges: {G.number_of_edges()}")
    print(f"   cites edges added from .docx Linked-Docs sections: {n_cites_added}")
    print(f"Pickle: {G_PATH.relative_to(ROOT)}  ({G_PATH.stat().st_size/1024:.1f} KB)")
    return G


if __name__ == "__main__":
    build()
