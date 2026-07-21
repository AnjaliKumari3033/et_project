"""embed_all.py -- orchestrator that turns docx_chunks.pkl into a ChromaDB
PersistentClient store populated with every child chunk + a sidecar parent index.

Per the architecture plan:
  - Single embedding model: all-MiniLM-L6-v2 (384-d). Mandated by build-prompt
    section 3.6 to eliminate dimension-mismatch risk across stores.
  - Children (10,802 .docx sections + later PDF body chunks + vision crops) are
    embedded as ChromaDB records.
  - Parents (whole .docx / PDF sections / whole doc) are NOT embedded; they live
    in the sidecar JSON index keyed by parent_id, used for auto-merge retrieval.

Metadata per child chunk (per architecture spec section 2.7):
  parent_id, source_type, document_type, equipment_id, event_id, department,
  failure_category, simulated_incompleteness, page_or_section, file_name,
  image_render_path (None for docx), image_summary (None for docx),
  image_context (None for docx), ingested_at (ISO UTC now)

Collection layout in ChromaDB:
  - "novachem_corpus" : all child chunks across .docx + PDF body + PDF vision.
    Single collection enforces a uniform embedding dimension (384).
"""
from __future__ import annotations

import json
import pickle
import time
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "data" / "chroma"
PARENT_INDEX_PATH = ROOT / "data" / "parent_index.json"
DOCX_CHUNKS_PKL = ROOT / "data" / "docx_chunks.pkl"

EMBED_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "novachem_corpus"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_or_create_collection(client: chromadb.ClientAPI):
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL,
        # Trust remote code is required by SentenceTransformers for newer releases
        # since some model cards ship with custom modeling code.
        model_kwargs={"trust_remote_code": False},
    )
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"description": "NovaChem Industrial Knowledge Intelligence -- corpus v1"},
    )


def embed_docx_children() -> dict[str, int]:
    if not DOCX_CHUNKS_PKL.exists():
        raise SystemExit(f"{DOCX_CHUNKS_PKL} missing -- run ingest_docx.py first.")

    with open(DOCX_CHUNKS_PKL, "rb") as f:
        data: dict = pickle.load(f)
    parent_store = data["parent_store"]
    parent_index: dict[str, dict] = {pid: {"text": v["text"], "metadata": v["metadata"]}
                                       for pid, v in parent_store.items()}
    children = data["all_children"]
    citations = data.get("citations", [])

    # Persist parent index sidecar JSON. We re-write it each ingestion pass so
    # PDF parents will append later by ingest_pdfs.py.
    PARENT_INDEX_PATH.write_text(json.dumps(parent_index, indent=2, default=str), encoding="utf-8")

    # Connect to ChromaDB PersistentClient
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    col = _get_or_create_collection(client)

    # Avoid re-embedding already-present children: this script is idempotent within
    # the same Chroma store. We upsert by chunk_id (which is stable per section within the doc).
    # However, since we regenerate on each run, chunk_ids are not stable -- so
    # the right strategy is: wipe the collection and re-embed cleanly.
    # For now, wipe if it already has rows from the same batch source:
    n_existing = col.count() if col.count() is not None else 0
    print(f"Existing chunks in ChromaDB collection: {n_existing}")
    if n_existing > 0:
        print("  Resetting collection to a clean store for this fresh ingest pass.")
        client.delete_collection(COLLECTION_NAME)
        col = _get_or_create_collection(client)

    BATCH = 256
    t0 = time.time()
    n_pending = len(children)
    print(f"Embedding {n_pending} children with {EMBED_MODEL} in batches of {BATCH}...")

    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict] = []
    n_flushed = 0
    for i, c in enumerate(children, start=1):
        ids.append(c["chunk_id"])
        # Embed the section header + body together -- section header provides
        # strong semantic anchoring ("Root Cause: ..." beats just "Bearing wear")
        docs.append(f"{c['section_header']}\n{c['text']}")
        metas.append({
            "parent_id": c["parent_id"],
            "source_type": c["source_type"],
            "document_type": c["document_type"],
            "equipment_id": c["equipment_id"] or "",
            "event_id": c["event_id"] or "",
            "department": c["department"] or "",
            "failure_category": c["failure_category"] or "",
            "simulated_incompleteness": bool(c["simulated_incompleteness"]),
            "page_or_section": c["section_header"],
            "file_name": c["file_name"],
            "image_render_path": "",
            "image_summary": "",
            "image_context": "",
            "ingested_at": _now_iso(),
        })
        if len(ids) >= BATCH or i == len(children):
            col.upsert(ids=ids, documents=docs, metadatas=metas)
            n_flushed += len(ids)
            rate = n_flushed / max(time.time() - t0, 1e-9)
            print(f"  inserted {n_flushed:>6d}/{n_pending}  ({rate:.1f}/s)")
            ids.clear(); docs.clear(); metas.clear()

    dt = time.time() - t0
    print(f"\n--- Embed summary ---")
    print(f"Collection                : {COLLECTION_NAME}")
    print(f"Total child chunks stored : {col.count()}")
    print(f"Parent index              : {PARENT_INDEX_PATH.relative_to(ROOT)} ({PARENT_INDEX_PATH.stat().st_size/1024:.1f} KB)")
    print(f"Parent entries            : {len(parent_index)}")
    print(f"Linked-doc citations seen : {len(citations)} (to be added to graph as `cites` edges)")
    print(f"Embedding wall time       : {dt:.1f}s")
    return {"total_children": col.count(), "parent_index_count": len(parent_index), "citations": len(citations)}


if __name__ == "__main__":
    embed_docx_children()
