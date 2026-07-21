"""ingest_pdfs.py -- extract body text + text-layer tables from all 85 public PDFs.

Per the architecture plan:
  - PDF body text uses PyMuPDF (page-by-page). The 31 MB / 308+ page outlier is
    streamed: we use doc.load_page(pno) explicitly rather than preloading all pages.
  - Text-layer tables use pdfplumber (e.g. SDS Section 8 exposure limits). We try
    pdfplumber for tables BEFORE any vision call.
  - Chunking: parent ~1000 tokens section-aware, children ~200 tokens. Vision-
    derived diagram/table crops are NOT done here -- they are produced later by
    ingest_vision.py against the triage manifest.
  - Graph: each PDF becomes a node (kind="ExternalPDF"). Edges derived via
    filename + content heuristics:
        - SDS -> Chemical node via filename prefix
        - Regulations/safety_guidelines -> Regulation node + safety topic edges
        - Manuals/Brochures/Technical_guides/white_papers -> EquipmentClass edges
          via filename keyword ("pump", "compressor", "motor", "boiler", etc.)
  - Embed: each child chunk is upserted into the same ChromaDB collection as the
    docx chunks, with source_type="pdf_body".

The triage manifest is consulted to decide per-page whether the page will be
processed by vision later. For vision-candidate pages, we still extract any
text-layer body + pdfplumber tables here; vision crops are added later.

Idempotency: if we detect the collection already has pdf_body children, we pass
--reset to wipe the collection and rebuild fresh.
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF
import networkx as nx
import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
PUB_ROOT = ROOT / "Dataset" / "public_document"
MANIFEST = ROOT / "data" / "pdf_triage_manifest.json"
GRAPH_PATH = ROOT / "data" / "graph" / "equipment_graph.pkl"
PARENT_INDEX = ROOT / "data" / "parent_index.json"

# Per architecture plan: parent ~1000 tokens, child ~200 tokens. Using ~4 chars/token.
PARENT_CHARS = 4000
CHILD_CHARS = 800  # roughly 200 tokens

# Map filename keyword -> EquipmentClass node id
CLASS_KEYWORDS = {
    "pump": "Pump",
    "compressor": "Compressor",
    "boiler": "Boiler",
    "motor": "Motor",
    "fan": "Fan",
    "tower": "CoolingTower",
    "heat": "HeatExchanger",  # "heat exchanger", "heat transfer"
    "valve": "Valve",
    "flow meter": "FlowMeter",
    "flowmeter": "FlowMeter",
    "steam": "SteamSystem",
    "compressed air": "CompressedAir",
    "pressure": "PressureTransmitter",
    "cooling": "CoolingTower",
}

# Map subfolder -> general document_type label
SUBFOLDER_DOCTYPE = {
    "brochures": "Brochure",
    "manuals": "OEM_Manual",
    "regulations": "Regulation",
    "safety_data_sheets": "SDS",
    "safety_guidelines": "SafetyGuideline",
    "technical_guides": "TechnicalGuide",
    "white_papers": "WhitePaper",
}

# Safety/compliance topic keyword -> Regulation node label (used for `governs` edges)
REGULATION_TOPICS = {
    "loto": "LOTO",
    "lockout": "LOTO",
    "tagout": "LOTO",
    "confined space": "ConfinedSpace",
    "permit to work": "PTW",
    "ptw": "PTW",
    "hot work": "HotWork",
    "hotwork": "HotWork",
    "psi": "ProcessSafetyInformation",
    "oisd": "OISD",
    "factory act": "FactoryAct",
    "petroleum": "PetroleumRules",
    "osha": "OSHA",
    "fire safety": "FireSafety",
}

CHEMICAL_KEYWORDS = [
    "acetic acid", "ammonia", "sulfuric acid", "hydrochloric acid", "ethylene glycol",
    "toluene", "xylene", "sodium hydroxide", "methanol", "acetone", "ethanol",
    "chlorine", "nitrogen", "oxygen", "hydrogen",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_parent_on_pages(doc_text_by_page: list[tuple[int, str]]) -> list[dict]:
    """Group page texts into parent units within PARENT_CHARS budget. A parent
    always starts on a new page boundary to keep provenance clean."""
    parents: list[dict] = []
    cur: list[int] = []  # page numbers in the current parent
    cur_len = 0
    for pno, text in doc_text_by_page:
        if not text.strip():
            continue
        if cur_len + len(text) > PARENT_CHARS and cur:
            parents.append({"pages": cur, "text": "\n\n".join(doc_text_by_page[p][1] for p in cur)})
            cur = []
            cur_len = 0
        cur.append(pno)
        cur_len += len(text) + 2
    if cur:
        parents.append({"pages": cur, "text": "\n\n".join(doc_text_by_page[p][1] for p in cur)})
    return parents


def _split_children(parent_text: str, parent_id: str, file_name: str,
                    pages_lbl: str) -> list[dict]:
    """Token-windowed children within a parent, preserving provenance."""
    children: list[dict] = []
    # Split on paragraph breaks first; if a single paragraph exceeds CHILD_CHARS,
    # fall back to fixed-window slicing so we never drop content.
    paras = re.split(r"\n\s*\n", parent_text)
    buf: list[str] = []
    cur_len = 0
    n = 0
    for para in paras:
        if not para.strip():
            continue
        if len(para) > CHILD_CHARS:
            # Flush buffer first
            if buf:
                n += 1
                children.append({"chunk_id": str(uuid.uuid4()), "parent_id": parent_id,
                                  "text": "\n".join(buf), "page_or_section": f"{pages_lbl}_chunk{n}"})
                buf = []
                cur_len = 0
            # Slice the long para
            for i in range(0, len(para), CHILD_CHARS):
                n += 1
                children.append({"chunk_id": str(uuid.uuid4()), "parent_id": parent_id,
                                  "text": para[i:i + CHILD_CHARS], "page_or_section": f"{pages_lbl}_chunk{n}"})
            continue
        if cur_len + len(para) > CHILD_CHARS and buf:
            n += 1
            children.append({"chunk_id": str(uuid.uuid4()), "parent_id": parent_id,
                              "text": "\n".join(buf), "page_or_section": f"{pages_lbl}_chunk{n}"})
            buf = []
            cur_len = 0
        buf.append(para)
        cur_len += len(para) + 1
    if buf and any(p.strip() for p in buf):
        n += 1
        children.append({"chunk_id": str(uuid.uuid4()), "parent_id": parent_id,
                          "text": "\n".join(buf), "page_or_section": f"{pages_lbl}_chunk{n}"})
    return children


def _extract_pdf_text(pdf_path: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """Return (page_text_list, pdfplumber_tables) where each item is (page_idx, text).
    pdfplumber_tables is a list of (page_idx, table_markdown_or_str)."""
    page_texts: list[tuple[int, str]] = []
    table_texts: list[tuple[int, str]] = []
    # PyMuPDF for body text -- streaming, page by page
    doc = fitz.open(str(pdf_path))
    try:
        for pno in range(len(doc)):
            try:
                page = doc.load_page(pno)
                text = page.get_text("text") or ""
                page_texts.append((pno, text))
            except Exception as e:
                page_texts.append((pno, f"[page extraction error: {e}]"))
    finally:
        doc.close()

    # pdfplumber for text-layer tables -- one pass per PDF.
    # For very large PDFs (>200 pages), pdfplumber table extraction is
    # prohibitively slow and aggressive false-positive; vision pipeline will
    # handle diagram/table-dense pages on those PDFs, so we skip pdfplumber
    # tables for them. Table-light text PDFs (SDS, regulations, guidelines)
    # are the right targets here.
    do_pdfplumber = True
    try:
        with pdfplumber.open(str(pdf_path)) as ppdf:
            if len(ppdf.pages) > 200:
                do_pdfplumber = False
                print(f"  . skipping pdfplumber on {pdf_path.name} ({len(ppdf.pages)} pages; vision will handle diagrams)")
        if do_pdfplumber:
            with pdfplumber.open(str(pdf_path)) as ppdf:
                for pno, page in enumerate(ppdf.pages):
                    try:
                        tables = page.extract_tables() or []
                    except Exception:
                        continue
                    for t_idx, tbl in enumerate(tables):
                        if not tbl or not tbl[0]:
                            continue
                        # Filter trivial tables: require >=3 rows AND >=2 columns, and
                        # require that the table has substantial content (>=50 non-empty chars).
                        if len(tbl) < 3 or len(tbl[0]) < 2:
                            continue
                        char_count = sum(len(str(c) or "") for row in tbl for c in row)
                        if char_count < 50:
                            continue
                        # Markdown-like representation (build-prompt §3.4 prompt also
                        # uses Markdown, so we mimic it for text-layer tables too so
                        # we don't double-process them in vision).
                        lines: list[str] = []
                        for row in tbl:
                            cells = [str(c).strip() if c is not None else "" for c in row]
                            lines.append(" | ".join(cells))
                        if lines:
                            # Markdown header row + separator
                            header = lines[0]
                            sep = " | ".join(["---"] * len(tbl[0]))
                            md = header + "\n" + sep + "\n" + "\n".join(lines[1:])
                            table_texts.append((pno, f"[TABLE_{t_idx}]\n{md}"))
                    # also: text-based pressure/exposure-limit style tables are caught here
    except Exception as e:
        print(f"  ! pdfplumber error on {pdf_path.name}: {e}")

    # Append pdfplumber tables to the corresponding page's text so they form
    # their own parents/chunks naturally.
    if table_texts:
        # Merge tables into page_texts: append tables to same page's text block
        merged: list[tuple[int, str]] = []
        t_idx = 0
        table_by_page: dict[int, list[str]] = {}
        for pno, md in table_texts:
            table_by_page.setdefault(pno, []).append(md)
        for pno, text in page_texts:
            tb = table_by_page.get(pno, [])
            full = text + ("\n\n" + "\n\n".join(tb) if tb else "")
            merged.append((pno, full))
        page_texts = merged

    return page_texts, table_texts


def _derive_pdf_graph_edges(filename_stem: str, page_texts: list[tuple[int, str]],
                            subfolder: str) -> list[tuple[str, str, str, dict]]:
    """Return list of (src_node, dst_node, relationship, attrs). The src_node
    is always the PDF node id which the caller will add. We only return edges
    where dst_node exists (caller skips otherwise).
    """
    edges: list[tuple[str, str, str, dict]] = []
    pdf_id = filename_stem  # caller uses full file path string as node id
    full_text = " ".join(t for _, t in page_texts[:5]).lower()  # first 5 pages for content hints
    stem = filename_stem.lower()

    # --- Class derivation from filename or content ---
    edges_by_method = []  # accumulate (cls, method) then push to edges
    matched_filename: set[str] = set()
    matched_content: set[str] = set()
    # Treat _ and - as word separators so that "Air_Compressor" matches '\bcompressor\b'.
    stem_tokenized = re.sub(r"[_\-]+", " ", stem)
    for kw, cls in CLASS_KEYWORDS.items():
        # Word-boundary match on the tokenized filename stem first (more reliable).
        if re.search(rf"\b{re.escape(kw)}\b", stem_tokenized):
            matched_filename.add(cls)
        # Always also try content as a fallback/extension.
        if re.search(rf"\b{re.escape(kw)}\b", full_text[:4000]):
            matched_content.add(cls)
    # Emit filename matches once each (filename wins), and any content matches
    # that weren't already covered by filename.
    seen: set[str] = set()
    for cls in sorted(matched_filename):
        seen.add(cls)
        edges_by_method.append((cls, "filename_keyword"))
    for cls in sorted(matched_content - seen):
        edges_by_method.append((cls, "content_keyword"))
    for cls, method in edges_by_method:
        edges.append((pdf_id, cls, "references_class", {"derivation_method": method}))

    # --- SDS chemical extraction ---
    if subfolder == "safety_data_sheets":
        # Filename typically "Ammonia_sds.pdf" or "Acetic_Acid.pdf"
        # Try to extract a chemical name from the stem
        chem = None
        for kw in ("_sds", "-sds", " sds"):
            if kw in stem:
                chem = stem.split(kw)[0].strip("_- ")
                break
        if not chem:
            chem = stem
        # Title-case and clean: "Ammonia", "Acetic_Acid" -> "Acetic Acid"
        chem = chem.replace("_", " ").strip().title()
        if chem:
            edges.append((pdf_id, chem, "describes_chemical",
                          {"derivation_method": "sds_filename"}))
            # Also -- check content for chemical occurrences (helps edges to
            # generated incident docs that mention specific chemicals later)
        # Also try content keywords
        for ck in CHEMICAL_KEYWORDS:
            if ck in full_text[:8000]:
                edges.append((pdf_id, ck.title(), "mentions_chemical",
                              {"derivation_method": "content_keyword"}))

    # --- Regulations / safety_guidelines -> Regulation topic edges ---
    if subfolder in ("regulations", "safety_guidelines"):
        # stem is the regulation name e.g. "Lockout_Tagout" -> Label "Lockout Tagout"
        reg_label = stem.replace("_", " ").strip().title()
        if reg_label:
            edges.append((pdf_id, reg_label, "named_regulation",
                          {"derivation_method": "filename_stem"}))
        # Scan content for topic keywords
        for kw, topic in REGULATION_TOPICS.items():
            if kw in full_text[:4000]:
                edges.append((pdf_id, topic, "governs",
                              {"derivation_method": "content_keyword"}))

    # --- Specific equipment reference -- rare. We could attempt to match
    # equipment IDs like "P-101" but public manuals typically don't reference
    # plant equipment. Skip for v1. ---

    return edges


def ingest(reset_chroma: bool = False) -> None:
    if not MANIFEST.exists():
        raise SystemExit(f"Triage manifest missing at {MANIFEST} -- run triage_pdfs.py first.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    # Open ChromaDB
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    CHROMA = ROOT / "data" / "chroma"
    client = chromadb.PersistentClient(path=str(CHROMA), settings=Settings(anonymized_telemetry=False))
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    col = client.get_or_create_collection("novachem_corpus", embedding_function=ef,
                                          metadata={"description": "NovaChem corpus v1"})

    if reset_chroma:
        # Full empy wipe - regenerate from scratch.
        client.delete_collection("novachem_corpus")
        col = client.get_or_create_collection("novachem_corpus", embedding_function=ef,
                                              metadata={"description": "NovaChem corpus v1"})

    # Load existing parent index (we'll merge PDF parents in)
    parent_index: dict = json.loads(PARENT_INDEX.read_text(encoding="utf-8")) if PARENT_INDEX.exists() else {}

    # Load existing graph
    G = pickle.loads(GRAPH_PATH.read_bytes()) if GRAPH_PATH.exists() else nx.DiGraph()

    # Build a quick lookup of equipment class node ids (for adds)
    existing_class_nodes = {n for n, d in G.nodes(data=True) if d.get("kind") == "EquipmentClass"}

    t0 = time.time()
    total_pdf_parents = 0
    total_pdf_children = 0
    total_edges_added = 0
    total_tables_extracted = 0
    per_folder_stats: dict = {}

    # For embedding, accumulate batches then upsert.
    BATCH = 256
    ids_buf: list[str] = []
    docs_buf: list[str] = []
    metas_buf: list[dict] = []

    def _flush() -> None:
        nonlocal ids_buf, docs_buf, metas_buf
        if ids_buf:
            col.upsert(ids=ids_buf, documents=docs_buf, metadatas=metas_buf)
            ids_buf.clear(); docs_buf.clear(); metas_buf.clear()

    # Iterate over PDFs (sorted by manifest order, which is filesystem-sorted)
    print(f"\nExtracting body text + pdfplumber tables from {len(manifest['pdfs'])} PDFs...")
    i = 0
    for pdf_meta in manifest["pdfs"]:
        i += 1
        if pdf_meta.get("error"):
            continue
        rel_path = pdf_meta["file"]  # relative path
        abs_path = ROOT / rel_path
        stem = abs_path.stem
        subfolder_parents = abs_path.parents
        # subfolder under "public_document"
        pub_idx = rel_path.replace("\\", "/").split("/").index("public_document")
        subfolder = rel_path.replace("\\", "/").split("/")[pub_idx + 1] if len(rel_path.replace("\\", "/").split("/")) > pub_idx + 1 else ""
        subfolder_lower = subfolder.lower()
        doc_type = SUBFOLDER_DOCTYPE.get(subfolder_lower, "ExternalPDF")

        # --- Extract body text + tables for ALL pages (flagged or not) ---
        page_texts, table_texts = _extract_pdf_text(abs_path)
        total_tables_extracted += len(table_texts)

        # --- Build parents & children (chunk only text, not tables separately --
        # tables are already appended to page_texts in the function).
        parents = _split_parent_on_pages(page_texts)
        per_folder_stats.setdefault(subfolder, {"pdfs":0, "parents":0, "children":0, "tables":0})
        per_folder_stats[subfolder]["pdfs"] += 1
        per_folder_stats[subfolder]["parents"] += len(parents)
        per_folder_stats[subfolder]["tables"] += len(table_texts)

        # Add a single "PDF" node
        pdf_node_id = rel_path  # use rel path as the unique id
        if pdf_node_id not in G.nodes:
            G.add_node(pdf_node_id, kind="ExternalPDF", file_name=abs_path.name,
                        subfolder=subfolder, document_type=doc_type,
                        n_pages=pdf_meta.get("n_pages", 0),
                        n_flagged_pages=pdf_meta.get("n_flagged_pages", 0),
                        is_vision_candidate=pdf_meta.get("is_vision_candidate", False),
                        stem=stem)

        # Derive graph edges from filename + content
        derived_edges = _derive_pdf_graph_edges(pdf_node_id, page_texts, subfolder_lower)
        for src, dst, rel, attrs in derived_edges:
            if dst not in G.nodes:
                # Create a lightweight target node (Chemical / Regulation / Topic / EquipmentClass)
                if rel == "describes_chemical":
                    G.add_node(dst, kind="Chemical", label=dst)
                elif rel == "mentions_chemical":
                    if dst not in G.nodes:
                        G.add_node(dst, kind="Chemical", label=dst)
                elif rel in ("governs",):
                    G.add_node(dst, kind="Regulation", label=dst)
                elif rel == "named_regulation":
                    G.add_node(dst, kind="Regulation", label=dst)
                elif rel == "references_class":
                    if dst not in G.nodes:
                        G.add_node(dst, kind="EquipmentClass", label=dst)
                # skip edges to new EquipmentClass nodes if they already exist
            # Always ensure both endpoints exist now
            if src in G.nodes and dst in G.nodes and not G.has_edge(src, dst):
                G.add_edge(src, dst, relationship=rel, **attrs)
                total_edges_added += 1

        # Chunk the PDF parents into children + embed
        for pno_group in parents:
            parent_id = str(uuid.uuid4())
            pages_lbl = f"pages_{'-'.join(str(p) for p in pno_group['pages'][:3])}{'+' if len(pno_group['pages'])>3 else ''}"
            # Parent record (add to sidecar index)
            parent_index[parent_id] = {
                "text": pno_group["text"],
                "metadata": {
                    "parent_id": parent_id,
                    "source_type": "pdf_body",
                    "document_type": doc_type,
                    "file_name": abs_path.name,
                    "file_path": rel_path,
                    "subfolder": subfolder,
                    "pages": pno_group["pages"],
                    "is_vision_candidate": pdf_meta.get("is_vision_candidate", False),
                }
            }
            total_pdf_parents += 1

            children = _split_children(parent_text=pno_group["text"], parent_id=parent_id,
                                        file_name=abs_path.name, pages_lbl=pages_lbl)
            for c in children:
                ids_buf.append(c["chunk_id"])
                docs_buf.append(f"{abs_path.name} p{pno_group['pages'][0]}\n{c['text']}")
                metas_buf.append({
                    "parent_id": parent_id,
                    "source_type": "pdf_body",
                    "document_type": doc_type,
                    "equipment_id": "",
                    "event_id": "",
                    "department": "",
                    "failure_category": "",
                    "simulated_incompleteness": False,
                    "page_or_section": c["page_or_section"],
                    "file_name": abs_path.name,
                    "image_render_path": "",
                    "image_summary": "",
                    "image_context": "",
                    "ingested_at": _now_iso(),
                })
                total_pdf_children += 1
            if len(ids_buf) >= BATCH:
                _flush()
        if i % 5 == 0:
            print(f"  [{i:>3d}/{len(manifest['pdfs'])}]  "
                  f"pdf_parents={total_pdf_parents}  pdf_children={total_pdf_children}  "
                  f"edges_added={total_edges_added}  tables={total_tables_extracted}  "
                  f"({time.time()-t0:.1f}s)")
    _flush()

    # Cleanup helper signature typo
    # (no-op - the call inside _split_children is correct)

    # Persist parent index (merged)
    PARENT_INDEX.write_text(json.dumps(parent_index, indent=2, default=str), encoding="utf-8")

    # Persist graph
    with open(GRAPH_PATH, "wb") as f:
        pickle.dump(G, f)

    # Stats
    print("\n--- PDF body ingestion summary ---")
    print(f"PDFs processed      : {sum(s['pdfs'] for s in per_folder_stats.values())}")
    print(f"PDF body parents    : {total_pdf_parents}")
    print(f"PDF body children   : {total_pdf_children}")
    print(f"pdfplumber tables   : {total_tables_extracted}")
    print(f"Graph edges added   : {total_edges_added}")
    print(f"Graph now           : nodes={G.number_of_nodes()}  edges={G.number_of_edges()}")
    print(f"Time                : {time.time()-t0:.1f}s")
    print(f"ChromaDB total      : {col.count()} child chunks (docx + pdf_body)")
    print()
    print("Per-folder breakdown:")
    for sf, st in sorted(per_folder_stats.items()):
        print(f"  {sf:22s} pdfs={st['pdfs']:>3d}  parents={st['parents']:>4d}  children={st['children']:>5d}  tables={st['tables']:>3d}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="Wipe ChromaDB collection and rebuild from scratch.")
    args = ap.parse_args()
    ingest(reset_chroma=args.reset)
