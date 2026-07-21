"""triage_pdfs.py -- build a per-page manifest of all 85 public PDFs.

For each page of each PDF:
  - text_len   = len(page.get_text().strip())
  - image_count = len(page.get_images())
  - drawing_paths = len(page.get_drawings())

A page is flagged as a vision candidate if:
  image_count > 0 OR drawing_paths > 50

Output: data/pdf_triage_manifest.json with structure:
  {
    "generated_at": "ISO...",
    "summary": {total_pages, flagged_pages, total_pdfs, vision_pdfs},
    "pdfs": [
      {
        "file": "Brochures\\Flow_meters\\Differential pressure flow meters.pdf",
        "n_pages": 126,
        "n_flagged_pages": 122,
        "is_vision_candidate": true,
        "pages": [
            {"page": 0, "text_len": 45, "image_count": 2, "drawing_paths": 137, "flagged": true},
            ...
        ]
      },
      ...
    ]
  }
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
PUB_ROOT = ROOT / "Dataset" / "public_document"
MANIFEST_PATH = ROOT / "data" / "pdf_triage_manifest.json"

DRAW_PATH_THRESHOLD = 50  # from build-prompt section 3.4 heuristic


def triage() -> dict:
    if not PUB_ROOT.exists():
        raise SystemExit(f"public_document root not found: {PUB_ROOT}")
    pdfs = sorted(PUB_ROOT.rglob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs under {PUB_ROOT.relative_to(ROOT)}/")

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": {"drawing_paths_min": DRAW_PATH_THRESHOLD, "image_count_min": 1},
        "summary": {"total_pdfs": len(pdfs), "total_pages": 0, "flagged_pages": 0, "vision_pdfs": 0},
        "pdfs": [],
    }
    t0 = time.time()
    for i, pdf_path in enumerate(pdfs, 1):
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            print(f"  ! cannot open {pdf_path}: {e}")
            out["pdfs"].append({
                "file": str(pdf_path.relative_to(ROOT)),
                "error": str(e),
                "n_pages": 0, "n_flagged_pages": 0,
                "is_vision_candidate": False, "pages": [],
            })
            continue

        pages_info = []
        n_flagged_in_doc = 0
        for pno in range(len(doc)):
            try:
                page = doc.load_page(pno)
                text = page.get_text().strip()
                img_count = len(page.get_images())
                # get_drawings() can be slow on very dense pages but is bounded.
                try:
                    dwg_count = len(page.get_drawings())
                except Exception:
                    dwg_count = 0
                flagged = (img_count > 0) or (dwg_count > DRAW_PATH_THRESHOLD)
                if flagged:
                    n_flagged_in_doc += 1
                pages_info.append({
                    "page": pno,
                    "text_len": len(text),
                    "image_count": img_count,
                    "drawing_paths": dwg_count,
                    "flagged": flagged,
                })
            except Exception as e:
                pages_info.append({"page": pno, "error": str(e), "flagged": False})

        doc.close()
        out["summary"]["total_pages"] += len(pages_info)
        out["summary"]["flagged_pages"] += n_flagged_in_doc
        is_vision = n_flagged_in_doc > 0
        if is_vision:
            out["summary"]["vision_pdfs"] += 1

        out["pdfs"].append({
            "file": str(pdf_path.relative_to(ROOT)),
            "n_pages": len(pages_info),
            "n_flagged_pages": n_flagged_in_doc,
            "is_vision_candidate": is_vision,
            "pages": pages_info,
        })

        # Progress every 10 PDFs
        if i % 10 == 0 or i == len(pdfs):
            elapsed = time.time() - t0
            print(f"  [{i:>3d}/{len(pdfs)}] pages={out['summary']['total_pages']:>5d}  "
                  f"flagged={out['summary']['flagged_pages']:>5d}  vision_pdfs={out['summary']['vision_pdfs']}  "
                  f"({elapsed:.1f}s)")

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Per-folder breakdown
    from collections import defaultdict
    per_folder = defaultdict(lambda: {"pdfs": 0, "pages": 0, "flagged": 0, "vision": 0})
    for pdf in out["pdfs"]:
        # subfolder = the first segment under "Dataset/public_document/", e.g. "Manuals"
        parts = Path(pdf["file"]).parts  # ('Dataset','public_document','Manuals','Air_Compressor.pdf')
        # find "public_document" then take the next segment if any
        folder = "(root)"
        for idx, seg in enumerate(parts):
            if seg == "public_document" and idx + 1 < len(parts):
                folder = parts[idx + 1]
                break
        per_folder[folder]["pdfs"] += 1
        per_folder[folder]["pages"] += pdf["n_pages"]
        per_folder[folder]["flagged"] += pdf["n_flagged_pages"]
        if pdf["is_vision_candidate"]:
            per_folder[folder]["vision"] += 1

    print("\n--- PDF triage summary ---")
    print(f"Total PDFs       : {len(pdfs)}")
    print(f"Total pages      : {out['summary']['total_pages']}")
    print(f"Flagged pages    : {out['summary']['flagged_pages']}  ({100*out['summary']['flagged_pages']/max(1,out['summary']['total_pages']):.1f}%)")
    print(f"Vision candidates: {out['summary']['vision_pdfs']} PDFs")
    print(f"Manifest         : {MANIFEST_PATH.relative_to(ROOT)}  ({MANIFEST_PATH.stat().st_size/1024:.1f} KB)")
    print()
    print(f"Per-folder breakdown:")
    for folder, stats in sorted(per_folder.items()):
        print(f"  {folder:25s} pdfs={stats['pdfs']:>3d}  pages={stats['pages']:>5d}  flagged={stats['flagged']:>5d}  "
              f"vision_pdfs={stats['vision']:>3d}")

    return out


if __name__ == "__main__":
    triage()
