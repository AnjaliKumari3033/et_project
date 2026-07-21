from pydantic import BaseModel
from typing import List, Optional

class QueryRequest(BaseModel):
    query: str
    stream: bool = False
    temperature: float = 0.0

class SourceDocument(BaseModel):
    content: str
    metadata: dict

class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceDocument]
