"""run_all.py -- top-level orchestrator for the v1 ingestion + storage layer.

Run order (per the architecture plan):
  1. build_sql           -- 16 tables -> data/sqlite/novachem.db
  2. ingest_docx         -- 677 .docx section-aware chunks -> data/docx_chunks.pkl
  3. build_graph         -- 898-node multi-entity DiGraph (+ cites edges from .docx)
  4. embed_all           -- docx chunks -> ChromaDB + parent index sidecar
  5. triage_pdfs         -- 85 PDFs -> data/pdf_triage_manifest.json (~30s)
  6. ingest_pdfs         -- PDF body text + pdfplumber tables + graph PDF edges
                            + embed PDF children into the same ChromaDB
                            -- this step is SLOW; budget ~30-60 minutes on CPU.
  7. ingest_vision       -- triage-gated; runs Nemotron + NIM vision only on
                            flagged pages. Requires NVIDIA_API_KEY + ultralytics.
                            Skipped if --skip-vision.
Steps are individually idempotent (most use IF EXISTS / replace / resume cache),
so you can re-run this script after any failure.

Usage:
  python run_all.py                 # full v1 pipeline (skip vision by default;
                                    # requires NVIDIA_API_KEY + ultralytics to
                                    # enable vision; add --vision to enable)
  python run_all.py --from triage   # start from step 5 (skip 1-4)
  python run_all.py --vision        # also run step 7 (needs API key)
  python run_all.py --vision --vision-limit 30
                                    # vision only on first 30 flagged pages
                                    # (demo-subset mode)
  python run_all.py --reset-chroma  # wipe & rebuild ChromaDB from scratch
  python run_all.py --skip-graph    # don't rebuild the graph (useful if you
                                    # already have the latest pickled graph)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "ingestion"))

STAGES = [
    "build_sql",
    "ingest_docx",
    "build_graph",
    "embed_all",
    "triage_pdfs",
    "ingest_pdfs",
    "ingest_vision",
]


def _stage_idx(name: str) -> int:
    return STAGES.index(name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_stage", choices=STAGES, default="build_sql",
                    help="Skip all stages before this one (default: build_sql).")
    ap.add_argument("--skip", nargs="+", default=[], choices=STAGES[1:],
                    help="Skip these named stages.")
    ap.add_argument("--vision", action="store_true",
                    help="Enable the final vision ingestion stage (requires NVIDIA_API_KEY).")
    ap.add_argument("--vision-limit", type=int, default=None,
                    help="Stop vision after N flagged pages (demo-subset).")
    ap.add_argument("--vision-only-pdf", type=str, default=None,
                    help="Only run vision on this one PDF file name.")
    ap.add_argument("--reset-chroma", action="store_true",
                    help="Wipe and recreate the ChromaDB collection from scratch.")
    ap.add_argument("--skip-vision-by-default", action="store_true", default=True,
                    help="Default behaviour; ignored. Kept for compatibility.")
    args = ap.parse_args()

    start_idx = _stage_idx(args.from_stage)
    skip_set = set(args.skip)
    if not args.vision:
        skip_set.add("ingest_vision")

    print("=" * 72)
    print("NovaChem Industrial Knowledge Intelligence -- v1 ingestion orchestrator")
    print("=" * 72)
    print(f"Starting stage : {args.from_stage}")
    print(f"Skipping       : {sorted(skip_set) or '(none)'}")
    print(f"Vision         : {'ENABLED' if args.vision else 'SKIPPED'}"
          + (f"  limit={args.vision_limit}" if args.vision_limit else "")
          + (f"  only_pdf={args.vision_only_pdf}" if args.vision_only_pdf else ""))
    print(f"Reset Chroma   : {args.reset_chroma}")
    print()

    overall_t0 = time.time()
    failures = []
    for i, stage in enumerate(STAGES[start_idx:], start=start_idx):
        if stage in skip_set:
            print(f"[{i+1}/{len(STAGES)}] SKIPPED: {stage}")
            continue
        if stage == "ingest_pdfs":
            # The PDF stage takes its own arg via argparse inside the module;
            # we import and call its `ingest()` function directly with
            # reset_chroma = False UNLESS the user requested a clean Chroma rebuild.
            from ingestion.ingest_pdfs import ingest as ingest_pdfs
            t0 = time.time()
            try:
                ingest_pdfs(reset_chroma=args.reset_chroma)
                # If --reset-chroma was set, we only wanted it to apply to this
                # step's beginning; reset the flag for subsequent runs of
                # embed_all (already done) and ingest_vision (next).
                args.reset_chroma = False
                print(f"[{i+1}/{len(STAGES)}] DONE {stage} ({time.time()-t0:.1f}s)\n")
            except Exception as e:
                failures.append((stage, str(e)))
                print(f"[{i+1}/{len(STAGES)}] FAILED {stage}: {e}\n")
                continue
            continue
        if stage == "ingest_vision":
            from ingestion.ingest_vision import ingest_vision
            t0 = time.time()
            try:
                ingest_vision(dry_run=False, limit_pages=args.vision_limit,
                              only_pdf=args.vision_only_pdf)
                print(f"[{i+1}/{len(STAGES)}] DONE {stage} ({time.time()-t0:.1f}s)\n")
            except Exception as e:
                failures.append((stage, str(e)))
                print(f"[{i+1}/{len(STAGES)}] FAILED {stage}: {e}\n")
            continue
        if stage == "embed_all":
            from ingestion.embed_all import embed_docx_children
            t0 = time.time()
            try:
                embed_docx_children()
                # If --reset-chroma was set on the orchestrator, the embed_all
                # step already wipes the collection for fresh docx chunks; pdf
                # ingestion will then upsert into the freshly-wiped collection.
                if args.reset_chroma:
                    args.reset_chroma = False  # consumed
                print(f"[{i+1}/{len(STAGES)}] DONE {stage} ({time.time()-t0:.1f}s)\n")
            except Exception as e:
                failures.append((stage, str(e)))
                print(f"[{i+1}/{len(STAGES)}] FAILED {stage}: {e}\n")
            continue
        # Generic dispatch for the rest of the stages.
        if stage == "build_sql":
            from ingestion.build_sql import build as run_stage
        elif stage == "ingest_docx":
            from ingestion.ingest_docx import ingest as run_stage
        elif stage == "build_graph":
            from ingestion.build_graph import build as run_stage
        elif stage == "triage_pdfs":
            from ingestion.triage_pdfs import triage as run_stage
        else:
            print(f"[{i+1}/{len(STAGES)}] UNKNOWN {stage} -- skipping")
            continue
        t0 = time.time()
        try:
            run_stage()
            print(f"[{i+1}/{len(STAGES)}] DONE {stage} ({time.time()-t0:.1f}s)\n")
        except Exception as e:
            failures.append((stage, str(e)))
            print(f"[{i+1}/{len(STAGES)}] FAILED {stage}: {e}\n")

    print("=" * 72)
    print(f"Orchestration complete in {time.time()-overall_t0:.1f}s")
    print(f"Failures: {len(failures)}")
    for stage, msg in failures:
        print(f"  - {stage}: {msg}")
    if not failures:
        print("All requested stages completed successfully.")
        print("Artifacts are under data/:")
        print("  data/sqlite/novachem.db       -- SQLite, 16 tables")
        print("  data/graph/equipment_graph.pkl -- NetworkX DiGraph (~898 nodes)")
        print("  data/docx_chunks.pkl          -- intermediate .docx chunk records")
        print("  data/parent_index.json        -- parent text + metadata sidecar")
        print("  data/chroma/                  -- ChromaDB persistent store")
        print("  data/pdf_triage_manifest.json -- per-page triage manifest of 85 PDFs")
        print("  data/vision_progress.json     -- NIM vision batch resume cache")
        print("  data/vision_crop_sidecar.json -- per-crop metadata for embedding")
        print("  data/crops/                   -- Snapdragon PNG crops for vision children")
    print("=" * 72)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
