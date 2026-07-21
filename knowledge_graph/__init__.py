"""
NovaChem Knowledge Graph Pipeline
==================================
LLM-extracted knowledge graph built from documents via Qwen/Ollama.

Modules:
    read_documents   - Reads .docx/.pdf into documents.jsonl
    extract_entities - Qwen entity/relationship extraction
    build_graph      - Builds NetworkX MultiDiGraph from all sources
    graph_queries    - Production query interface (KnowledgeGraph class)
"""

from knowledge_graph.graph_queries import KnowledgeGraph

__all__ = ["KnowledgeGraph"]
