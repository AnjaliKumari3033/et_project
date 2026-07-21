"""Quick test: load the knowledge graph and print summaries for P-101."""
import sys
from pathlib import Path

# Ensure project root is on sys.path so `knowledge_graph` package is importable
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge_graph import KnowledgeGraph

kg = KnowledgeGraph()  # defaults to data/graph/knowledge_graph.gpickle

print("=== Equipment Summary: P-101 ===")
print(kg.equipment_summary("P-101"))
print()
print("=== Context: P-101 ===")
print(kg.get_context("P-101"))
print()
print("=== Graph Statistics ===")
print(kg.graph_statistics())
