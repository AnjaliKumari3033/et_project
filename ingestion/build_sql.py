"""Build SQLite database from all .xlsx files in the dataset.

20 tables total:
  16 root xlsx  (Dataset/*.xlsx)
   4 operational (Dataset/generated_documents/operational_data/*.xlsx)

Design rules enforced per the architecture plan:
  - `Equipment ID` is stored as TEXT (e.g. "P-101" is not a number).
  - Headers are normalized: lowercase, spaces -> underscores, stripped.
  - Tables are dropped-recreated on each run (idempotent ingestion).
  - Empty cells become NULL (not the string "nan").
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "Dataset"
DB_PATH = ROOT / "data" / "sqlite" / "novachem.db"

ROOT_TABLES = [
    "equipment_master",
    "equipment_relationships",
    "plant_events",
    "equipment_health_history",
    "failure_taxonomy",
    "plant_layout",
    "preventive_maintenance_schedule",
    "spare_parts_inventory",
    "novachem_employees",
    "department_document_matrix",
    "document_lifecycle",
]

GENERATED_ROOT_TABLES = [
    "document_index",
]

OPERATIONAL_TABLES = [
    "daily_production_reports",
    "operator_logs",
    "shift_logs",
    "spare_parts_requests",
]


def _norm_header(name: str) -> str:
    s = str(name).strip().lower()
    s = s.replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
    s = "_".join(seg for seg in s.split("_") if seg)  # collapse double underscores
    return s


def _load_xlsx(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [_norm_header(c) for c in df.columns]
    df = df.where(pd.notnull(df), None)
    if "equipment_id" in df.columns:
        df["equipment_id"] = df["equipment_id"].astype(str).str.strip()
        df.loc[df["equipment_id"].isin(["", "None", "nan"]), "equipment_id"] = None
    return df


def _to_sql(df: pd.DataFrame, table: str, conn: sqlite3.Connection) -> None:
    df.to_sql(table, conn, if_exists="replace", index=False, dtype={"equipment_id": "TEXT"})


def build() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        n_rows_total = 0
        table_counts: list[tuple[str, int]] = []

        def _ingest(path: Path, table: str) -> None:
            nonlocal n_rows_total
            df = _load_xlsx(path)
            _to_sql(df, table, conn)
            table_counts.append((table, len(df)))
            n_rows_total += len(df)
            print(f"  - {table:36s} {len(df):>5d} rows  ({path.relative_to(ROOT)})")

        print("Root tables:")
        for t in ROOT_TABLES:
            _ingest(DATASET / f"{t}.xlsx", t)

        print("Generated root table:")
        for t in GENERATED_ROOT_TABLES:
            _ingest(DATASET / "generated_documents" / f"{t}.xlsx", t)

        print("Operational tables:")
        for t in OPERATIONAL_TABLES:
            _ingest(DATASET / "generated_documents" / "operational_data" / f"{t}.xlsx", t)

        conn.commit()

        print("\n--- SQLite build summary ---")
        print(f"Tables written : {len(table_counts)}")
        print(f"Total rows     : {n_rows_total}")
        print(f"DB file        : {DB_PATH.relative_to(ROOT)}  ({DB_PATH.stat().st_size/1024:.1f} KB)")

        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        names = [r[0] for r in cur.fetchall()]
        expected = len(ROOT_TABLES) + len(GENERATED_ROOT_TABLES) + len(OPERATIONAL_TABLES)
        assert len(names) == expected, f"expected {expected} tables, got {len(names)}: {names}"
        print(f"Verified all {expected} tables present.")
    finally:
        conn.close()


if __name__ == "__main__":
    build()
