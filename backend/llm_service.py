import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

SYSTEM_PROMPT = """You are an elite industrial knowledge-intelligence AI for NovaChem Industries.
Your sole purpose is to provide factual, accurate, and structured answers based ONLY on the provided context.

CRITICAL RULES:
1. NO IMAGINATION: Never hallucinate, guess, or imagine data. If the answer is not in the context, explicitly say: "I do not have sufficient information in the provided context to answer this."
2. ALWAYS CITE SOURCES: When making claims, cite the exact source document name or Knowledge Graph equipment ID.
3. STRUCTURED OUTPUT: Use Markdown bullet points for diagnostic steps. If providing technical specifications, you MUST format them in a clean Markdown table.
4. CONFIDENCE WARNINGS: If context is partial or conflicting, add a "> [!WARNING]" block stating the limitations.
"""

def generate_answer(query: str, context: str, temperature: float = 0.0) -> str:
    """Generate an answer using local Ollama Qwen model."""
    
    prompt = f"Context:\n{context}\n\nUser Query:\n{query}\n\nAnswer:"
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "temperature": temperature
    }
    
    try:
        response = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result["message"]["content"]
    except Exception as e:
        return f"Error communicating with local LLM ({OLLAMA_MODEL}): {e}"

def generate_answer_stream(query: str, context: str, temperature: float = 0.0):
    """Yield chunks of an answer using local Ollama Qwen model."""
    
    prompt = f"Context:\n{context}\n\nUser Query:\n{query}\n\nAnswer:"
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "stream": True,
        "temperature": temperature
    }
    
    try:
        with requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, stream=True, timeout=120) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    yield chunk["message"]["content"]
    except Exception as e:
        yield f"\n\n[Error communicating with local LLM ({OLLAMA_MODEL}): {e}]"
