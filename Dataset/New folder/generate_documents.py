"""
=========================================================
NovaChem Industrial Knowledge Intelligence
Master Document Generator
=========================================================
Runs every per-document-type generator script in order,
then rebuilds the master document index.

Usage:
    python generate_documents.py

Each generator script below is a standalone module (they
already work fine run individually with `python work_orders.py`
etc.) — this just runs them all back-to-back as subprocesses
so the whole dataset can be rebuilt with one command.
"""

import subprocess
import sys
import os

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Order only matters in that the index generator must run last —
# the nine document-type scripts are independent of each other.
DOCUMENT_SCRIPTS = [
    "work_orders.py",
    "maintenance.py",
    "inspection.py",
    "incidents.py",
    "emails.py",
    "rca.py",
    "quality.py",
    "safety.py",
    "calibration.py",
]

INDEX_SCRIPT = "generate_document_index.py"


def run_script(script_name):
    path = os.path.join(SCRIPTS_DIR, script_name)

    print(f"\n{'=' * 60}")
    print(f"Running {script_name}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, path],
        cwd=SCRIPTS_DIR
    )

    if result.returncode != 0:
        print(f"\n[FAILED] {script_name} exited with code {result.returncode}")
        sys.exit(result.returncode)


def main():
    print("Regenerating full NovaChem document set...")

    for script in DOCUMENT_SCRIPTS:
        run_script(script)

    run_script(INDEX_SCRIPT)

    print("\n" + "=" * 60)
    print("All document types generated and document_index.xlsx rebuilt.")
    print("=" * 60)


if __name__ == "__main__":
    main()
