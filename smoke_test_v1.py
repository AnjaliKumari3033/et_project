"""End-to-end smoke test of the v1 text-only store (post-docx ingestion)."""
import json, pickle, sqlite3
from pathlib import Path
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parent

print("=" * 70)
print("V1 SMOKE TEST — text-only store (SQLite + ChromaDB + NetworkX graph)")
print("=" * 70)

# 1. SQLite
DB = ROOT / "data" / "sqlite" / "novachem.db"
c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print(f"\n[SQLite] file={DB.relative_to(ROOT)}  size={DB.stat().st_size/1024:.1f} KB  tables={len(tables)}")
expected = {"plant_events":75, "equipment_master":15, "equipment_relationships":13,
            "equipment_health_history":75, "failure_taxonomy":11, "plant_layout":15,
            "preventive_maintenance_schedule":15, "spare_parts_inventory":10,
            "novachem_employees":50, "department_document_matrix":8, "document_lifecycle":8,
            "document_index":675, "daily_production_reports":75, "operator_logs":75,
            "shift_logs":75, "spare_parts_requests":75}
errs = 0
for t, nrows in expected.items():
    got = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    if got != nrows: print(f"  MISMATCH {t}: expected {nrows}, got {got}"); errs += 1
print(f"  Row counts verified for {len(expected)} tables.  errors={errs}")
# Confirm Equipment ID kept as TEXT
ctype = c.execute("PRAGMA table_info(equipment_master)").fetchall()[0]
print(f"  equipment_master.equipment_id storage class: {ctype[2]} (expected TEXT)")
# Confirm plant_events schema has all 25 columns
pe_cols = [d[1] for d in c.execute("PRAGMA table_info(plant_events)")]
print(f"  plant_events cols: {len(pe_cols)}  (expected 25)")
c.close()

# 2. Graph
g_path = ROOT / "data" / "graph" / "equipment_graph.pkl"
G = pickle.loads(g_path.read_bytes())
print(f"\n[Graph] file={g_path.relative_to(ROOT)}  size={g_path.stat().st_size/1024:.1f} KB")
print(f"  nodes={G.number_of_nodes()}  edges={G.number_of_edges()}")

# Edge relationship breakdown
from collections import Counter
rel_counts = Counter(d.get("relationship","?") for _,_,d in G.edges(data=True))
print(f"  Edge relationships ({len(rel_counts)} types):")
for r, cnt in rel_counts.most_common():
    print(f"    {r:25s} {cnt}")

# Traversal sanity: full multi-hop from EVT-001 (depth 3)
print("\n  Multi-hop traversal from EVT-001 (depth=3):")
import networkx as nx
seen_kinds = Counter()
for u,v in nx.bfs_edges(G, "EVT-001", depth_limit=3):
    seen_kinds[(G.nodes[u].get('kind'), G.nodes[v].get('kind'))] += 1
print(f"    Reached {len(seen_kinds)} kind-to-kind edge types in 3 hops.")
for (sk, dk), n in seen_kinds.most_common():
    print(f"      {str(sk):>15s} -> {str(dk):<15s}  x {n}")

# 3. ChromaDB + parent index
PI_PATH = ROOT / "data" / "parent_index.json"
parent_index = json.loads(PI_PATH.read_text(encoding="utf-8"))
print(f"\n[ChromaDB] parent index: {PI_PATH.relative_to(ROOT)}  size={PI_PATH.stat().st_size/1024:.1f} KB  entries={len(parent_index)}")

client = chromadb.PersistentClient(path=str(ROOT / "data" / "chroma"), settings=Settings(anonymized_telemetry=False))
col = client.get_collection("novachem_corpus")
print(f"  Collection '{col.name}'  count={col.count()}")

# Incomplete-marker chunk count  (col.count() API doesn't support `where` filter; use col.get)
incomplete_res = col.get(where={"simulated_incompleteness": True}, limit=20000)
print(f"  Chunks w/ simulated_incompleteness=True: {len(incomplete_res['ids'])}")

# Sample retrieval test
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
res = col.query(query_texts=["bearing wear vibration in feed pump"], n_results=5,
                where={"equipment_id": "P-101"})
print("\n  Sample vector search: query='bearing wear vibration in feed pump', filter equipment_id=P-101")
for i in range(len(res["ids"][0])):
    cid = res["ids"][0][i]
    dist = res["distances"][0][i]
    m = res["metadatas"][0][i]
    print(f"    [{i+1}] dist={dist:.3f}  doc={m.get('file_name')}  section={m.get('page_or_section')}")
    print(f"        parent_id={m.get('parent_id')[:8]}... event={m.get('event_id')} incomplete={m.get('simulated_incompleteness')}")

# Auto-merge test: retrieve the parent text for the top hit
top_parent_id = res["metadatas"][0][0]["parent_id"]
parent_record = parent_index.get(top_parent_id)
print(f"\n  Auto-merge test: top hit parent_id={top_parent_id[:8]}...")
print(f"    parent file_name: {parent_record['metadata']['file_name']}")
print(f"    parent document_type: {parent_record['metadata']['document_type']}")
print(f"    parent text length: {len(parent_record['text'])} chars")
print(f"    parent first 200 chars: {parent_record['text'][:200]!r}")

print("\nSMOKE TEST COMPLETE")
