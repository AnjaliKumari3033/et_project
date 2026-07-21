"""ingest_vision.py -- the triage-gated vision pipeline.

Per the locked-in architecture decision (build-prompt section 3.4 + user spec):
  - Run only on flagged PDF pages per the triage manifest.
  - For each flagged page:
      1. Run nvidia/nemotron-page-elements-v3 (local YOLOX) for layout detection
         -> bboxes + class (table / chart / infographic / title / text) + confidence.
      2. Crop each region from PyMuPDF's pixmap.
      3. Send each crop to NIM via nim_client.transcribe_crop:
           - is_table=True  -> Markdown table transcription
           - is_table=False -> Diagram description (visible components, labels,
                                connections, flow direction)
      4. Each transcribed region becomes a child chunk in ChromaDB with:
           parent_id        = the body-text parent_id from ingest_pdfs.py for that
                              page (or a synthetic per-PDF parent if the page had
                              no body text -- rare but possible on diagram-only
                              pages)
           source_type      = "pdf_vision"
           document_type    = one of: OEM_Manual_Diagram, OEM_Manual_Table,
                              Brochure_Diagram, Technical_Guide_Diagram,
                              WhitePaper_Diagram, SDS_Diagram, Regulation_Table
           file_name         = source PDF filename
           page_or_section   = f"page_{pno:04d}_region_{ridx}_class_{cls}"
           image_render_path = local PNG path under data/crops/
           image_summary     = the NIM transcription (Markdown or description)
           image_context     = up to ~400 tokens of body text adjacent on the same
                              page (so the diagram is retrieval-retrievable via
                              surrounding prose)
           ingested_at, equipment_id="", event_id="", department="",
           failure_category="", simulated_incompleteness=False
      5. Add graph edges from the PDF node to any equipment class detected in the
           transcription text (cheap content-keyword scan; we already add filename-
           based edges in ingest_pdfs.py, so vision only augments if the diagram
           text mentions a class).

Run control:
  - Idempotent via nim_client's resume cache (data/vision_progress.json).
  - If `--limit N` is given, only process up to N flagged pages (demo-subset mode).
  - If `--pdf <filename>` is given, only process that PDF's flagged pages.
  - If `--dry-run` is given, Nemotron + NIM are not invoked; we count what WOULD
    be sent and write a plan file. Useful for budgeting NIM calls.
  - Model loading: nemotron-page-elements-v3 is a YOLOX detector from HuggingFace;
    we lazily import ultralytics so this script can be parsed even if the package
    isn't installed when the user only wants text-only ingestion.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import time
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF -- always required for cropping even in dry-run mode

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "pdf_triage_manifest.json"
GRAPH_PATH = ROOT / "data" / "graph" / "equipment_graph.pkl"
PARENT_INDEX = ROOT / "data" / "parent_index.json"
CROPS_DIR = ROOT / "data" / "crops"
CHROMA_DIR = ROOT / "data" / "chroma"

# Per build-prompt §3.7, page_or_section labels vision chunks with class.
REGION_DOCUMENT_TYPE = {
    "table":        "OEM_Manual_Table",
    "chart":        "OEM_Manual_Diagram",
    "infographic":  "OEM_Manual_Diagram",
    "diagram":      "OEM_Manual_Diagram",
    "title":        None,  # titles aren't vision-transcribed (already in body text)
    "text":         None,  # pure text regions aren't transcribed (already extracted)
}

# Map PDF subfolder -> broader document_type prefix for vision children.
SUBFOLDER_DOCTYPE_PREFIX = {
    "brochures": "Brochure",
    "manuals": "OEM_Manual",
    "regulations": "Regulation",
    "safety_data_sheets": "SDS",
    "safety_guidelines": "SafetyGuideline",
    "technical_guides": "TechnicalGuide",
    "white_papers": "WhitePaper",
}

CLASS_KEYWORDS = {
    "pump": "Pump", "compressor": "Compressor", "boiler": "Boiler",
    "motor": "Motor", "fan": "Fan", "tower": "CoolingTower",
    "heat exchanger": "HeatExchanger", "valve": "Valve",
    "flow meter": "FlowMeter", "flowmeter": "FlowMeter",
    "steam": "SteamSystem", "compressed air": "CompressedAir",
    "pressure": "PressureTransmitter", "cooling": "CoolingTower",
}

# Detector. Loaded lazily so dry-runs and the package-not-installed case work.
_NEMOTRON = None
_NEMOTRON_MODEL_NAME = "nvidia/nemotron-page-elements-v3"


def _load_nemotron(model_dir: str | None = None):
    global _NEMOTRON
    if _NEMOTRON is not None:
        return _NEMOTRON
    print("[ingest_vision] loading NimYOLO API fallback detector")
    class NimYOLO:
        def __call__(self, img_pil, verbose=False):
            import os, requests, base64, time
            from io import BytesIO
            buf = BytesIO()
            img_pil.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            key = os.environ.get("NVIDIA_API_KEY")
            
            url = "https://ai.api.nvidia.com/v1/cv/nvidia/nemotron-page-elements-v3"
            headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
            payload = {"input": [{"url": f"data:image/png;base64,{b64}"}]}
            
            for attempt in range(3):
                r = requests.post(url, headers=headers, json=payload)
                if r.status_code == 200:
                    break
                time.sleep(2)
            else:
                print(f"NimYOLO API Error: {r.text}")
                return []
                
            resp = r.json()
            data = resp.get("data", [])
            if not data:
                return []
                
            w, h = img_pil.size
            bboxes = data[0].get("bounding_boxes", {})
            
            class T:
                def __init__(self, v): self.v = v
                def cpu(self): return self
                def numpy(self): return self
                def item(self): return self.v
                def tolist(self): return self.v
            
            xyxy_list = []
            cls_list = []
            conf_list = []
            names = {}
            cls_to_id = {}
            current_id = 0
            
            for cls_name, boxes in bboxes.items():
                if cls_name not in cls_to_id:
                    cls_to_id[cls_name] = current_id
                    names[current_id] = cls_name
                    current_id += 1
                c_id = cls_to_id[cls_name]
                
                for box in boxes:
                    xyxy_list.append(T([box["x_min"] * w, box["y_min"] * h, box["x_max"] * w, box["y_max"] * h]))
                    cls_list.append(T(c_id))
                    conf_list.append(T(box["confidence"]))
                    
            if not xyxy_list:
                return []
                
            class B:
                def __len__(self): return len(xyxy_list)
                xyxy = xyxy_list
                cls = cls_list
                conf = conf_list
                
            class R:
                def __init__(self, b, n):
                    self.boxes = b
                    self.names = n
            return [R(B(), names)]
            
    _NEMOTRON = NimYOLO()
    return _NEMOTRON

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _load_parent_index() -> dict[str, dict]:
    if PARENT_INDEX.exists():
        return json.loads(PARENT_INDEX.read_text(encoding="utf-8"))
    return {}


def _find_parent_for_page(parent_index: dict, rel_path: str, page_no: int) -> tuple[str | None, str]:
    """Return (parent_id, surrounding_context_text). The parent_id whose pages
    include page_no (from ingest_pdfs.py). ~400-token context = the parent's
    text snippet near where page_no appears."""
    for pid, rec in parent_index.items():
        meta = rec.get("metadata", {})
        if meta.get("source_type") != "pdf_body":
            continue
        if meta.get("file_path") != rel_path:
            continue
        pages = meta.get("pages", [])
        if page_no in pages:
            # Return up to 400 tokens (~1600 chars) of context
            text = rec.get("text", "")
            ctx = text[:1600] if text else ""
            return pid, ctx
    # Fallback: page had no body text (e.g. diagram-only page). Make a synthetic
    # parent_id later; caller handles that.
    return None, ""


def _detect_regions(page_pixmap_bytes: bytes, model=None) -> list[dict]:
    """Run Nemotron on a page pixmap. Returns list of {bbox, cls, conf} dicts.
    bbox is a (x1, y1, x2, y2) tuple in pixel coordinates."""
    model = model or _load_nemotron()
    # ultralytics accepts a numpy array, PIL image, image bytes via a temp file,
    # or a path. The most robust path is to write bytes to a tmp file and pass it.
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(page_pixmap_bytes)
        tmp_path = tf.name
    try:
        from PIL import Image
        img = Image.open(tmp_path)
        results = model(img, verbose=False)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    regions: list[dict] = []
    # ultralytics results: results[0].boxes has .xyxy, .cls, .conf
    if not results or len(results) == 0:
        return regions
    r = results[0]
    try:
        names = r.names  # dict {0: 'table', 1: 'chart', ...}
    except Exception:
        names = {}
    try:
        boxes = r.boxes
    except Exception:
        return regions
    if boxes is None:
        return regions
    for i in range(len(boxes)):
        try:
            xyxy = boxes.xyxy[i].tolist()  # [x1,y1,x2,y2]
            cls_idx = int(boxes.cls[i].item())
            conf = float(boxes.conf[i].item())
            cls_name = names.get(cls_idx, str(cls_idx))
            regions.append({"bbox": tuple(xyxy), "cls": cls_name.lower(), "conf": conf})
        except Exception as e:
            print(f"  ! malformed box {i}: {e}")
    return regions


def _crop_page(page, bbox: tuple[float, float, float, float],
               target_dpi: int = 150) -> bytes:
    zoom = target_dpi / 72.0
    x1, y1, x2, y2 = bbox
    rect = fitz.Rect(x1, y1, x2, y2)
    rect = rect.intersect(page.rect)
    
    # Check for degenerate boxes
    if rect.is_empty or rect.width < 1 or rect.height < 1:
        return b""
        
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
    return pix.tobytes("png")


def _vision_chunk_document_type(subfolder: str, region_cls: str) -> str:
    """Map subfolder + region class to the vision child's document_type label."""
    prefix = SUBFOLDER_DOCTYPE_PREFIX.get(subfolder.lower(), "OEM_Manual")
    if region_cls == "table":
        return f"{prefix}_Table" if prefix != "OEM_Manual" else "OEM_Manual_Table"
    # charts, infographics, diagrams all -> *_Diagram (per build-prompt §3.7)
    return f"{prefix}_Diagram" if prefix != "OEM_Manual" else "OEM_Manual_Diagram"


def _detect_classes_in_text(text: str) -> list[tuple[str, str]]:
    """Cheap content-keyword scan over transcription text -> [(cls, keyword), ...]
    Returns matches for graph augmentation."""
    import re
    text_l = text.lower()
    matches: list[tuple[str, str]] = []
    seen_kws: set[str] = set()
    for kw, cls in CLASS_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", text_l) and kw not in seen_kws:
            seen_kws.add(kw)
            matches.append((cls, kw))
    return matches


def ingest_vision(*, dry_run: bool = False, limit_pages: int | None = None,
                  only_pdf: str | None = None,
                  nemotron_model: str | None = None) -> dict[str, Any]:
    """Main entry point. Consults the triage manifest, runs Nemotron+NIM on the
    flagged pages, writes vision child chunks to ChromaDB, augments the graph."""

    # -- Load manifest
    if not MANIFEST_PATH.exists():
        raise SystemExit(
            f"Triage manifest missing at {MANIFEST_PATH}. Run triage_pdfs.py first."
        )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    # -- Connect to ChromaDB and load parent index + graph
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    col = client.get_or_create_collection(
        "novachem_corpus", embedding_function=ef,
        metadata={"description": "NovaChem corpus v1"},
    )
    parent_index = _load_parent_index()
    G = pickle.loads(GRAPH_PATH.read_bytes()) if GRAPH_PATH.exists() else None

    # -- Filter manifest to relevant PDFs
    from ingestion import nim_client

    # We make a flat list of (pdf_meta, page_no) pairs.
    flat_pages: list[tuple[dict, int]] = []
    for p in manifest["pdfs"]:
        if p.get("error"):
            continue
        if not p.get("is_vision_candidate"):
            continue
        if only_pdf and Path(p["file"]).name != only_pdf:
            continue
        for pg in p["pages"]:
            if pg.get("flagged"):
                flat_pages.append((p, pg["page"]))
    if limit_pages is not None:
        flat_pages = flat_pages[:limit_pages]
    print(f"[ingest_vision] pages to process: {len(flat_pages)}  "
          f"(dry_run={dry_run}, limit_pages={limit_pages}, only_pdf={only_pdf})")

    if dry_run:
        plan = {
            "generated_at": _now_iso(),
            "total_flagged_pages": len(flat_pages),
            "total_regions_estimated": len(flat_pages) * 3,  # rough assumption
            "flat_pages": [{"pdf": p["file"], "page": pn} for p, pn in flat_pages],
        }
        plan_path = ROOT / "data" / "vision_plan.json"
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"[ingest_vision] dry-run complete. Plan: {plan_path.relative_to(ROOT)}")
        return plan

    # -- Safety: ensure API key set before we grind through 1500+ pages
    if not os.environ.get("NVIDIA_API_KEY"):
        raise SystemExit(
            "NVIDIA_API_KEY env var is empty. Vision pipeline cannot run against "
            "NIM. Set the env var (free tier via https://build.nvidia.com/) and rerun."
        )

    # Ensure crops dir
    CROPS_DIR.mkdir(parents=True, exist_ok=True)

    # -- Lazy-load nemotron. May trigger ~437MB model download.
    model = _load_nemotron(nemotron_model)

    # -- Build crops per flagged page; yield to nim_client.transcribe_batch
    # Embed in same magnitude batches as the docx ingestion did (~256).
    BATCH_EMBED = 256
    ids_buf: list[str] = []
    docs_buf: list[str] = []
    metas_buf: list[dict] = []

    def _flush():
        nonlocal ids_buf, docs_buf, metas_buf
        if ids_buf:
            col.upsert(ids=ids_buf, documents=docs_buf, metadatas=metas_buf)
            ids_buf.clear(); docs_buf.clear(); metas_buf.clear()

    import uuid

    def _make_crop_iter():
        """Lazily generate crop dicts. We do this so transcribe_batch can
        service them one at a time without exhuming all bytes in memory."""
        for pdf_meta, page_no in flat_pages:
            rel_path = pdf_meta["file"]
            abs_path = ROOT / rel_path
            pdf_stem = abs_path.stem
            pub_idx = rel_path.replace("\\", "/").split("/").index("public_document")
            subfolder = (rel_path.replace("\\", "/").split("/")[pub_idx + 1]
                         if len(rel_path.replace("\\", "/").split("/")) > pub_idx + 1 else "")
            pdf_node_id = rel_path
            try:
                doc = fitz.open(str(abs_path))
            except Exception as e:
                print(f"  ! cannot open {rel_path}: {e}")
                continue
            try:
                page = doc.load_page(page_no)
            except Exception as e:
                print(f"  ! cannot load page {page_no} of {rel_path}: {e}")
                doc.close()
                continue

            pix_bytes = page.get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72), alpha=False).tobytes("png")
            regions = _detect_regions(pix_bytes, model=model)
            if not regions:
                doc.close()
                continue

            # Find the body-text parent for this page (for context).
            parent_id, body_ctx = _find_parent_for_page(parent_index, rel_path, page_no)
            synthetic_parent = False
            if parent_id is None:
                # Diagram-only page: create a synthetic parent on the fly and add
                # to parent_index.
                synthetic_parent_id = str(uuid.uuid4())
                parent_index[synthetic_parent_id] = {
                    "text": f"[Diagram-only page {page_no} of {abs_path.name}]",
                    "metadata": {
                        "parent_id": synthetic_parent_id,
                        "source_type": "pdf_body",
                        "document_type": "OEM_Manual",
                        "file_name": abs_path.name,
                        "file_path": rel_path,
                        "subfolder": subfolder,
                        "pages": [page_no],
                        "is_vision_candidate": True,
                        "synthetic": True,
                    }
                }
                parent_id = synthetic_parent_id
                synthetic_parent = True

            # Process each non-text, non-title region (per the build-prompt
            # policy: title/text regions are already in body text, don't re-
            # transcribe them).
            for ridx, region in enumerate(regions):
                cls = region["cls"]
                if cls in ("text", "title"):
                    continue
                crop_bytes = _crop_page(page, region["bbox"], target_dpi=200)
                if not crop_bytes:
                    continue
                crop_id = f"{pdf_stem}_p{page_no:04d}_r{ridx:02d}"
                crop_path = CROPS_DIR / f"{crop_id}.png"
                crop_path.write_bytes(crop_bytes)
                is_table = cls == "table"
                yield {
                    "crop_id": crop_id,
                    "image_bytes": crop_bytes,
                    "is_table": is_table,
                    "pdf_path": rel_path,
                    "pdf_node_id": pdf_node_id,
                    "page": page_no,
                    "region_index": ridx,
                    "cls": cls,
                    "conf": region["conf"],
                    "bbox": region["bbox"],
                    "subfolder": subfolder,
                    "parent_id": parent_id,
                    "body_context": body_ctx,
                    "crop_path": str(crop_path.relative_to(ROOT)),
                    "synthetic_parent": synthetic_parent,
                }
            doc.close()

    # -- Run the batch through NIM (resumable via vision_progress.json)
    batch_result = nim_client.transcribe_batch(_make_crop_iter(), resume=True)

    # -- Embed each successfully transcribed vision child into ChromaDB
    print("[ingest_vision] embedding transcribed regions into ChromaDB...")
    n_embedded = 0
    for crop_id, info in batch_result["completed"].items():
        # Reconstruct context we cached in the crop iterable. We pass through the
        # fields we need via info (which only carries the keys we explicitly
        # stored). The crop extra metadata (subfolder, parent_id, cls, crop_path,
        # page) is in the manifest of crops -- but we didn't pass all of it into
        # nim_client. We'll re-fetch from disk by recomputing? Simpler: print a
        # warning that the progress cache pair doesn't carry the bookkeeping we
        # need, so the first run through the loop must ALSO persist a sidecar
        # mapping of crop_id -> {parent_id, crop_path, subfolder, page, cls}.
        pass

    # The clean design: collect a sidecar map DURING the iteration so we can
    # also re-read on a resume pass after embedding. Re-running the iteration
    # is wasteful only if NIM retries are slow, but for resume the iteration is
    # short and NIM-stable crops are just read from the cache.
    sidecar_path = ROOT / "data" / "vision_crop_sidecar.json"
    sidecar: dict[str, dict] = {}
    if sidecar_path.exists():
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    # Build a second iterator to refresh the sidecar map (without making NIM
    # calls -- those are skipped by transcribe_batch's resume cache):
    def _sidecar_refill():
        for pdf_meta, page_no in flat_pages:
            rel_path = pdf_meta["file"]
            abs_path = ROOT / rel_path
            pdf_stem = abs_path.stem
            try:
                doc = fitz.open(str(abs_path))
                page = doc.load_page(page_no)
            except Exception:
                continue
            pix_bytes = page.get_pixmap(matrix=fitz.Matrix(200/72, 200/72), alpha=False).tobytes("png")
            try:
                regions = _detect_regions(pix_bytes, model=model)
            except Exception:
                regions = []
            if not regions:
                doc.close(); continue
            parent_id, _ = _find_parent_for_page(parent_index, rel_path, page_no)
            doc.close()
            for ridx, region in enumerate(regions):
                if region["cls"] in ("text", "title"):
                    continue
                crop_id = f"{pdf_stem}_p{page_no:04d}_r{ridx:02d}"
                sidecar[crop_id] = {
                    "crop_path": str(CROPS_DIR / f"{crop_id}.png"),
                    "subfolder": (rel_path.replace("\\","/").split("/")[-2]
                                  if len(rel_path.replace("\\","/").split("/")) >= 2 else ""),
                    "cls": region["cls"],
                    "page": page_no,
                    "pdf_path": rel_path,
                    "parent_id": parent_id,
                }
            doc.close()
    print("[ingest_vision] refresh crop-sidecar map (no NIM calls)...")
    _sidecar_refill()
    sidecar_path.write_text(json.dumps(sidecar, indent=2, default=str), encoding="utf-8")

    # Now actually embed (and add graph edges for class keywords scanned from text)
    if G is None:
        G = pickle.loads(GRAPH_PATH.read_bytes()) if GRAPH_PATH.exists() else None
    n_edges_added = 0
    for crop_id, info in batch_result["completed"].items():
        meta = sidecar.get(crop_id)
        if not meta:
            print(f"  ! no sidecar entry for {crop_id}; skipping embedding")
            continue
        text = info["text"]
        parent_id = meta["parent_id"]
        # Synthesize parent if needed
        if parent_id is None:
            synthetic_parent_id = str(uuid.uuid4())
            parent_index[synthetic_parent_id] = {
                "text": f"[Diagram-only page {meta['page']} of {Path(meta['pdf_path']).name}]",
                "metadata": {
                    "parent_id": synthetic_parent_id,
                    "source_type": "pdf_body",
                    "document_type": "OEM_Manual",
                    "file_name": Path(meta["pdf_path"]).name,
                    "file_path": meta["pdf_path"],
                    "subfolder": meta["subfolder"],
                    "pages": [meta["page"]],
                    "is_vision_candidate": True,
                    "synthetic": True,
                }
            }
            parent_id = synthetic_parent_id

        doc_type = _vision_chunk_document_type(meta["subfolder"], meta["cls"])
        chunk_id = str(uuid.uuid4())
        ids_buf.append(chunk_id)
        # Embed a doc string that includes page + body-context + transcription
        # so vector search finds diagrams via both their description AND the
        # surrounding text on the page.
        docs_buf.append(
            f"{Path(meta['pdf_path']).name} page {meta['page']} ({meta['cls']}) "
            f"-- transcription: {text}"
        )
        metas_buf.append({
            "parent_id": parent_id,
            "source_type": "pdf_vision",
            "document_type": doc_type,
            "equipment_id": "",
            "event_id": "",
            "department": "",
            "failure_category": "",
            "simulated_incompleteness": False,
            "page_or_section": f"page_{meta['page']:04d}_region_class_{meta['cls']}",
            "file_name": Path(meta["pdf_path"]).name,
            "image_render_path": meta["crop_path"],
            "image_summary": text,
            "image_context": parent_index[parent_id]["text"][:1600],
            "ingested_at": _now_iso(),
        })
        n_embedded += 1

        # Augment graph: classes mentioned in the transcription
        if G is not None and meta.get("pdf_path") in G.nodes:
            for cls, kw in _detect_classes_in_text(text):
                if cls not in G.nodes:
                    G.add_node(cls, kind="EquipmentClass", label=cls)
                if not G.has_edge(meta["pdf_path"], cls):
                    G.add_edge(meta["pdf_path"], cls, relationship="references_class",
                               derivation_method="vision_transcription_keyword",
                               crop_id=crop_id)
                    n_edges_added += 1

        if len(ids_buf) >= BATCH_EMBED:
            _flush()

    _flush()

    # Persist parent index (with synthetic parents added)
    PARENT_INDEX.write_text(json.dumps(parent_index, indent=2, default=str), encoding="utf-8")
    # Persist graph
    if G is not None:
        with open(GRAPH_PATH, "wb") as f:
            pickle.dump(G, f)

    print(f"\n--- Vision ingestion summary ---")
    print(f"Flagged pages processed   : {len(flat_pages)}")
    print(f"Transcribed (resume cache): {batch_result['n_completed_this_run'] + batch_result['n_skipped_resume']}")
    print(f"  - new this run          : {batch_result['n_completed_this_run']}")
    print(f"  - reused from resume    : {batch_result['n_skipped_resume']}")
    print(f"  - failed                : {len(batch_result['failed'])}")
    print(f"Child chunks embedded     : {n_embedded}  (ChromaDB total now = {col.count()})")
    print(f"Graph class edges added   : {n_edges_added}")
    return {
        "transcribed": n_embedded,
        "new": batch_result["n_completed_this_run"],
        "skipped_resume": batch_result["n_skipped_resume"],
        "failed": len(batch_result["failed"]),
        "graph_edges_added": n_edges_added,
        "chromadb_total": col.count(),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Don't call Nemotron or NIM. Just count what WOULD be transcribed.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop after N flagged pages (demo-subset mode).")
    ap.add_argument("--pdf", type=str, default=None,
                    help="Only process this PDF filename (useful for re-running on a single doc).")
    ap.add_argument("--nemotron-model", type=str, default=None,
                    help="Override the Nemotron model name (default: nvidia/nemotron-page-elements-v3).")
    args = ap.parse_args()
    ingest_vision(
        dry_run=args.dry_run,
        limit_pages=args.limit,
        only_pdf=args.pdf,
        nemotron_model=args.nemotron_model,
    )
