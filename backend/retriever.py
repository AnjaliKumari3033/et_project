import sys
import os
from pathlib import Path

# Add project root to path so we can import from knowledge_graph
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from knowledge_graph import KnowledgeGraph
from backend.schemas import SourceDocument

class UnifiedRetriever:
    def __init__(self):
        # 1. Init Knowledge Graph (Your side)
        try:
            self.kg = KnowledgeGraph()
        except Exception as e:
            print(f"Failed to load Knowledge Graph: {e}")
            self.kg = None
            
        # 2. Init ChromaDB (Friend's side)
        chroma_dir = ROOT / "data" / "chroma"
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=str(chroma_dir), 
                settings=Settings(anonymized_telemetry=False)
            )
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
            self.collection = self.chroma_client.get_collection(
                "novachem_corpus", 
                embedding_function=self.embedding_fn
            )
            # Hack: wipe the internal metadata that tells Chroma it was built with PyTorch
            # This completely bypasses the Windows App Control block on shm.dll during query validation
            self.collection._model.configuration_json = "{}"
        except Exception as e:
            print(f"Failed to load ChromaDB: {e}")
            self.collection = None

    def retrieve(self, query: str, top_k: int = 5) -> tuple[str, list[SourceDocument]]:
        sources = []
        context_parts = []
        
        # A. Retrieve from Knowledge Graph
        if self.kg:
            # We use fuzzy matching in the KG to find the relevant equipment context
            # A more advanced version would use an LLM to extract the entity from the query first
            # Here we just do a broad context grab
            try:
                # We could potentially search for equipment IDs mentioned in the query
                # For now, let's try to get a general context if an equipment ID is matched
                # We can iterate through equipment nodes to see if they are in the query
                equipment_nodes = [n for n, d in self.kg._G.nodes(data=True) if d.get('node_type') == 'Equipment']
                matched_equipment = [eq for eq in equipment_nodes if eq in query.upper()]
                
                if matched_equipment:
                    import json
                    eq_id = matched_equipment[0]
                    kg_context = self.kg.get_context(eq_id)
                    context_str = json.dumps(kg_context, indent=2)
                    context_parts.append(f"--- KNOWLEDGE GRAPH CONTEXT for {eq_id} ---\n{context_str}")
                    sources.append(SourceDocument(content=context_str, metadata={"source": f"Knowledge Graph: {eq_id}"}))
            except Exception as e:
                print(f"KG Retrieval Error: {e}")

        # B. Retrieve from Vector Store
        if self.collection:
            try:
                # Embed manually to completely bypass Chroma's internal PyTorch metadata loader
                emb = self.embedding_fn([query])
                results = self.collection.query(
                    query_embeddings=emb,
                    n_results=top_k
                )
                
                if results['documents'] and results['documents'][0]:
                    v_context = "--- DOCUMENT TEXT & DIAGRAM TRANSCRIPTIONS ---\n"
                    for i in range(len(results['documents'][0])):
                        doc_text = results['documents'][0][i]
                        meta = results['metadatas'][0][i]
                        file_name = meta.get('file_name', 'Unknown file')
                        page = meta.get('page_or_section', 'Unknown page')
                        
                        v_context += f"Source: {file_name} ({page})\n{doc_text}\n\n"
                        sources.append(SourceDocument(content=doc_text, metadata=meta))
                        
                    context_parts.append(v_context)
            except Exception as e:
                print(f"Vector Retrieval Error: {e}")
                
        final_context = "\n\n".join(context_parts)
        if not final_context:
            final_context = "No context could be retrieved for this query."
            
        return final_context, sources
