"""Ingest all .docx files (677 = 2 static + 675 generated) into structured chunks.

Each generated .docx is chunked section-aware: every Word Heading-1 paragraph
starts a new child chunk; following body paragraphs AND table rows are appended
into that section's child chunk (tables are flattened to "Label: value" lines).

Pipeline:
  1. Load document_index.xlsx into a dict keyed by File Name for metadata lookup.
  2. Walk the body of each .docx in document order, splitting at Heading 1.
  3. Flatten each table to "Label: value" lines, belonging to the most recent H1
     section (later we'll attach them to whatever section was most recently started),
     OR detect when a table is the first thing under a section header (the typical
     case for "Document Information", "Equipment Details", "Maintenance Summary",
     "Spare Parts Used", "Previous Equipment History", "Approval").
  4. For each child chunk:
     - Attach metadata: parent_id (uuid4 str), source_type (docx_event|docx_static),
       document_type, equipment_id, event_id, department, failure_category,
       page_or_section = section header, file_name, simulated_incompleteness
       (true if "Under Investigation" or "X -- Pending" found in section body).
  5. Extract all "Linked Documents" bullet items (normalized .txt -> .docx for
     EMAIL files, per the known bug in utils.py:266 of the source scripts).
     Returns them as a list per document so the graph builder can add `cites`
     edges between sibling documents.

Output:
  - parent_store: dict mapping parent_id -> {file_name, full_text, metadata}
  - child_chunks: list of dicts with text + metadata (ready for embedding)
  - citations:   list of (source_doc, target_doc) pairs for graph `cites` edges

No embedding happens here -- that's the job of embed_all.py.
"""
from __future__ import annotations

import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

from docx import Document
from docx.document import Document as DocxDocument  # type: ignore
from docx.table import Table
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "Dataset"
DB_PATH = ROOT / "data" / "sqlite" / "novachem.db"

# Static docx files (no Document Information / Equipment Details / sections
# metadata like the generated ones).
STATIC_DOCX = [
    ("company_profile.docx", "company_profile", "Company Profile"),
    ("production_process.docx", "production_process", "Production Process"),
]

# Map subfolder name -> document_type label used in metadata
SUBFOLDER_DOC_TYPE = {
    "calibration":   "Calibration Report",
    "emails":        "Email",
    "incidents":     "Incident Report",
    "inspection":    "Inspection Report",
    "maintenance":   "Maintenance Report",
    "quality":       "Quality Report",
    "rca":           "RCA Report",
    "safety":        "Safety Report",
    "work_orders":   "Work Order",
}

# Heuristics for "Linked Documents" parsing: which file prefixes & doc-type
# strings map to which filenames (with .docx extension normalization).
EMAIL_EXT_BUG = ".txt"


def _load_document_index_index(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """doc_index keyed by File Name -> metadata dict."""
    out: dict[str, dict[str, Any]] = {}
    for r in conn.execute("SELECT * FROM document_index"):
        out[r["file_name"]] = dict(r)
    return out


# ----- Section heading detection -------------------------------------------------

# Strict: any paragraph whose Word style name starts with "Heading 1".
# We also accept a fallback: paragraphs whose text matches the exact set of
# known section-header literals (in case a doc has unstyled headers).
KNOWN_SECTION_HEADERS = {
    "Document Information", "Document Control",
    "Equipment Details", "Problem Description", "Inspection Findings",
    "Corrective Action", "Root Cause", "Engineer Remarks", "Safety",
    "Tools Used", "Maintenance Summary", "Previous Equipment History",
    "Spare Parts Used", "Maintenance Checklist", "Recommendations",
    "Linked Documents", "Approval",
    "Inspection Objective", "Observed Defects", "Risk Assessment",
    "Inspector Remarks", "Safety Observation", "Inspection Tools",
    "Inspection Summary", "Inspection Checklist",
    "Work Order Information", "Work Scope", "Required Resources",
    "Estimated Duration", "Safety Requirements", "Special Instructions",
    "Incident Information", "Incident Description", "Impact Assessment",
    "Root Cause Analysis", "Immediate Action Taken", "Safety Classification",
    "RCA Information", "Problem Statement", "Preventive Action",
    "Quality Information", "Quality Issue Description", "Quality Findings",
    "Non Conformance Details", "Quality Assessment", "Verification Status",
    "Final Quality Status", "Quality Engineer Remarks", "Safety Observation",
    "Inspection Tools Used", "Quality Inspection Checklist",
    "Safety Information", "Safety Event Description", "Hazard Identification",
    "Immediate Action Taken", "Preventive Action", "Safety Officer Remarks",
    "Safety Compliance Checklist",
    "Calibration Information", "Calibration Objective",
    "Calibration Findings", "Deviation Analysis", "Adjustment Performed",
    "Calibration Verification", "Calibration Checklist",
    "Email Information", "Email Subject", "Email Body", "Action Required",
}


def _is_h1(paragraph: Paragraph) -> bool:
    style = paragraph.style.name if paragraph.style else ""
    if style and style.startswith("Heading 1"):
        return True
    txt = paragraph.text.strip()
    if txt in KNOWN_SECTION_HEADERS:
        return True
    return False


# ----- Incompleteness markers ---------------------------------------------------

# Marker 1: literal "Under Investigation" replaces whole section body.
INVESTIGATION_RE = re.compile(r"\bUnder Investigation\b", re.IGNORECASE)
# Marker 2: checklist line "☐ <item> — Pending" (em-dash U+2014) OR
#           "☐ <item> - Pending" with regular hyphen, OR "☐ <item> Pending" -- be permissive.
PENDING_CHECKLIST_RE = re.compile(r"[☐]\s*[^—\-\n]{1,80}\s*[—\-]?\s*Pending", re.UNICODE)


def _has_incompleteness_marker(text: str) -> bool:
    return bool(INVESTIGATION_RE.search(text) or PENDING_CHECKLIST_RE.search(text))


# ----- Linked-documents parsing -------------------------------------------------

# Pattern of any "Linked Documents" bullet we expect -- any of the 9 known
# prefixes followed by an EVT-NNN ID and either .docx or .txt.
LINKED_RE = re.compile(
    r"^\s*(MNT|INS|WO|INC|RCA|QA|SAF|CAL|EMAIL)_EVT-\d+\.docx\s*$",
    re.IGNORECASE,
)
LINKED_RE_TXT_BUG = re.compile(
    r"^\s*(EMAIL)_EVT-\d+\.txt\s*$",
    re.IGNORECASE,
)


def _normalize_linked_filename(line: str) -> str | None:
    """Email references stored in Linked Documents sections say .txt due to a
    known bug in Scripts/utils.py:266. Normalise to .docx."""
    line = line.strip()
    if not line:
        return None
    line_lc = line.lower()
    if line_lc.endswith(EMAIL_EXT_BUG) and line_lc.startswith("email_evt-"):
        # Strip .txt and add .docx
        return line[:-len(EMAIL_EXT_BUG)] + ".docx"
    if LINKED_RE.match(line):
        return line
    # Also accept any ".docx" item to be permissive
    if re.match(r"^\s*[A-Z]+[-_]?EVT-?\d+\.docx\s*$", line, re.IGNORECASE):
        return line
    return None


# ----- Walking docx in document order with table interleaving -------------------

def _iter_block_items(parent: DocxDocument | Any) -> Iterable[Any]:
    """Yield paragraphs and tables in the order they appear in the document body."""
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = parent.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _flatten_table(table: Table) -> list[str]:
    """Flatten to list of "Label: value" lines, where Label is cell[0] of each row.
    If it's a multi-column table (e.g. Spare Parts Used, Previous Equipment
    History), flatten as 'val1 | val2 | val3' rows preceded by a header row."""
    rows_text: list[str] = []
    nrows = len(table.rows)
    ncols = len(table.rows[0].cells) if nrows else 0
    if ncols == 2:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if cells and cells[0]:
                rows_text.append(f"{cells[0]}: {cells[1] if len(cells) > 1 else ''}".rstrip())
    else:
        # Multi-column table: emit a header line + each row as pipe-joined values
        for i, row in enumerate(table.rows):
            cells = [c.text.strip() for c in row.cells]
            line = " | ".join(cells)
            rows_text.append(line)
    return rows_text


# ----- Main parser ---------------------------------------------------------------

def parse_docx(path: Path, source_type: str, document_type: str,
               doc_index_meta: dict[str, Any] | None) -> dict[str, Any]:
    """Parse a single .docx into a parent + children. Returns:
       {
         "parent_id": "...",
         "parent_text": "<full document text>",
         "parent_metadata": {...},
         "children": [ {id, text, parent_id, page_or_section, simulated_incompleteness}, ... ],
         "linked_documents": [normalized .docx filenames]
       }
    """
    doc = Document(str(path))

    # Walk blocks in document order
    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None  # the active section dict
    # We accumulate per-section body lines (paragraphs + flattened table rows).
    # When we hit a new H1 paragraph, we close current section and start a new one.
    linked_documents: list[str] = []

    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            style = block.style.name if block.style else ""

            if _is_h1(block):
                # Close previous section (already in `sections`); start new one
                current_section = {
                    "section_header": text,
                    "lines": [],
                }
                sections.append(current_section)
                continue

            # Plain paragraph -> append to current section (or an implicit
            # "preface" section if we hit body before any H1 -- the company
            # header block at the very top of every doc)
            if current_section is None:
                current_section = {"section_header": "_preface", "lines": []}
                sections.append(current_section)

            # Skip empty paragraphs (don't pollute chunks)
            if text:
                current_section["lines"].append(text)

                # If this is a bullet under "Linked Documents", capture it
                if style == "List Bullet" and current_section["section_header"] == "Linked Documents":
                    norm = _normalize_linked_filename(text)
                    if norm:
                        linked_documents.append(norm)

        elif isinstance(block, Table):
            # Append flattened rows to current section (or create implicit preface)
            if current_section is None:
                current_section = {"section_header": "_preface", "lines": []}
                sections.append(current_section)
            current_section["lines"].extend(_flatten_table(block))

    # Build parent text = concatenation of all sections
    parent_lines: list[str] = []
    for s in sections:
        parent_lines.append(s["section_header"])
        parent_lines.extend(s["lines"])
        parent_lines.append("")  # blank line between sections
    parent_text = "\n".join(parent_lines).strip()

    # Build children (one per section). Skip empty preface or empty sections.
    parent_id = str(uuid.uuid4())
    children: list[dict[str, Any]] = []
    for s in sections:
        body = "\n".join(s["lines"]).strip()
        if not body:
            continue
        children.append({
            "id": str(uuid.uuid4()),
            "parent_id": parent_id,
            "text": body,
            "section_header": s["section_header"],
            "simulated_incompleteness": _has_incompleteness_marker(body),
        })

    # Build parent metadata: prefer document_index; fallback to minimal
    meta = doc_index_meta or {}
    parent_metadata = {
        "parent_id": parent_id,
        "source_type": source_type,
        "document_type": document_type,
        "equipment_id": meta.get("equipment_id"),
        "event_id": meta.get("event_id"),
        "department": meta.get("department"),
        "failure_category": meta.get("failure_category"),
        "file_name": path.name,
    }
    # For static docs (no doc_index entry), the parent metadata above is mostly
    # None -- which is correct.

    return {
        "parent_id": parent_id,
        "parent_text": parent_text,
        "parent_metadata": parent_metadata,
        "children": children,
        "linked_documents": linked_documents,
    }


def ingest() -> dict[str, Any]:
    """Parse every .docx in the corpus. Returns aggregate stats + chunk records
    persisted via pickle to data/docx_chunks.pkl, plus the citation list for
    graph building (cites edges)."""
    import pickle

    if not DB_PATH.exists():
        raise SystemExit(f"SQLite DB missing at {DB_PATH} -- run build_sql.py first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    doc_index = _load_document_index_index(conn)
    conn.close()

    # Collect chunks
    parent_store: dict[str, dict[str, Any]] = {}  # parent_id -> {text, metadata}
    all_children: list[dict[str, Any]] = []        # ready for embed_all.py
    citations: list[tuple[str, str]] = []         # (source_doc_file_name, target_doc_file_name)

    n_docs = 0
    n_static = 0
    n_generated = 0
    n_incomplete = 0
    per_type_counts: dict[str, int] = {}
    per_type_incomplete: dict[str, int] = {}

    def _handle_parsed(path: Path, parsed: dict[str, Any]) -> None:
        nonlocal n_docs, n_static, n_generated, n_incomplete
        n_docs += 1
        parent_store[parsed["parent_id"]] = {
            "text": parsed["parent_text"],
            "metadata": parsed["parent_metadata"],
        }
        for child in parsed["children"]:
            child_chunk = {
                "chunk_id": child["id"],
                "parent_id": child["parent_id"],
                "text": child["text"],
                "section_header": child["section_header"],
                "simulated_incompleteness": child["simulated_incompleteness"],
                "source_type": parsed["parent_metadata"]["source_type"],
                "document_type": parsed["parent_metadata"]["document_type"],
                "equipment_id": parsed["parent_metadata"]["equipment_id"],
                "event_id": parsed["parent_metadata"]["event_id"],
                "department": parsed["parent_metadata"]["department"],
                "failure_category": parsed["parent_metadata"]["failure_category"],
                "file_name": parsed["parent_metadata"]["file_name"],
            }
            all_children.append(child_chunk)
            doc_type = parsed["parent_metadata"]["document_type"]
            per_type_counts[doc_type] = per_type_counts.get(doc_type, 0) + 1
            if child["simulated_incompleteness"]:
                per_type_incomplete[doc_type] = per_type_incomplete.get(doc_type, 0) + 1
        # Citations
        src_fname = path.name
        for tgt_fname in parsed["linked_documents"]:
            citations.append((src_fname, tgt_fname))

    # Static docs
    for fname, src_type, doc_type in STATIC_DOCX:
        path = DATASET / fname
        if not path.exists():
            print(f"  ! missing static doc: {path}")
            continue
        meta = doc_index.get(fname)  # None for static docs (they aren't in doc_index)
        parsed = parse_docx(path, "docx_static", doc_type, meta)
        _handle_parsed(path, parsed)
        n_static += 1

    # Generated docs -- walk each subfolder
    generated_dir = DATASET / "generated_documents"
    for subfolder in sorted(generated_dir.iterdir()):
        if not subfolder.is_dir():
            continue
        if subfolder.name in {"operational_data"}:
            continue
        doc_type = SUBFOLDER_DOC_TYPE.get(subfolder.name)
        if not doc_type:
            print(f"  ! unknown subfolder {subfolder.name} -- skipping")
            continue
        for path in sorted(subfolder.glob("*.docx")):
            meta = doc_index.get(path.name)
            if not meta:
                # DOC_TYPE_MAP in scripts sometimes mismatches; do regex fallback
                m = re.search(r"EVT-\d+", path.name)
                if m:
                    evtid = m.group(0)
                    # find any doc_index row with that event_id (cheap: linear scan via SQL)
                    import sqlite3 as _sq
                    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row
                    row = c.execute("SELECT * FROM document_index WHERE event_id = ? AND file_name = ?",
                                    (evtid, path.name)).fetchone()
                    c.close()
                    if row:
                        meta = dict(row)
            parsed = parse_docx(path, "docx_event", doc_type, meta)
            _handle_parsed(path, parsed)
            n_generated += 1

    # Persist
    out_path = ROOT / "data" / "docx_chunks.pkl"
    with open(out_path, "wb") as f:
        pickle.dump({
            "parent_store": parent_store,
            "all_children": all_children,
            "citations": citations,
        }, f)

    # Stats
    n_incomplete = sum(1 for c in all_children if c["simulated_incompleteness"])
    print("\n--- .docx ingestion summary ---")
    print(f"Total docs parsed       : {n_docs}  (static={n_static}, generated={n_generated})")
    print(f"Parent chunks           : {len(parent_store)}")
    print(f"Child chunks (sections) : {len(all_children)}")
    print(f"Chunks w/ incomplete mrk: {n_incomplete}  ({100*n_incomplete/len(all_children):.1f}%)")
    print(f"Linked-doc citations    : {len(citations)}")
    print()
    print(f"Chunk counts per document type:")
    for dt, cnt in sorted(per_type_counts.items(), key=lambda kv: -kv[1]):
        inc = per_type_incomplete.get(dt, 0)
        print(f"   {dt:22s} chunks={cnt:>5d}  incomplete={inc:>3d}  ({100*inc/cnt:.1f}%)")
    print()
    print(f"Saved: {out_path.relative_to(ROOT)}  ({out_path.stat().st_size/1024:.1f} KB)")
    return {
        "parent_store": parent_store,
        "all_children": all_children,
        "citations": citations,
    }


if __name__ == "__main__":
    ingest()
