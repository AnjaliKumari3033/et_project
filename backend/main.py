from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from backend.schemas import QueryRequest, QueryResponse
from backend.retriever import UnifiedRetriever
from backend.llm_service import generate_answer, generate_answer_stream
import sqlite3
import json
import os
from pathlib import Path

app = FastAPI(title="NovaChem Knowledge Intelligence API")

# Setup CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize retriever on startup
retriever = None

@app.on_event("startup")
async def startup_event():
    global retriever
    print("Initializing Unified Retriever...")
    retriever = UnifiedRetriever()
    print("Retriever initialized.")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "components": {"retriever": retriever is not None}}

@app.post("/api/chat", response_model=QueryResponse)
async def chat_endpoint(request: QueryRequest):
    if not retriever:
        raise HTTPException(status_code=500, detail="Retriever not initialized")
        
    try:
        # 1. Retrieve context
        context, sources = retriever.retrieve(request.query, top_k=5)
        
        # 2. Generate answer
        answer = generate_answer(request.query, context, request.temperature)
        
        # 3. Return response
        return QueryResponse(answer=answer, sources=sources)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat_stream")
async def chat_stream_endpoint(request: QueryRequest):
    if not retriever:
        raise HTTPException(status_code=500, detail="Retriever not initialized")
        
    try:
        context, sources = retriever.retrieve(request.query, top_k=5)
        
        def event_generator():
            yield json.dumps({"type": "sources", "data": [s.model_dump() for s in sources]}) + "\n"
            try:
                for chunk in generate_answer_stream(request.query, context, request.temperature):
                    yield json.dumps({"type": "chunk", "data": chunk}) + "\n"
            except Exception as e:
                yield json.dumps({"type": "error", "data": str(e)}) + "\n"
                
        return StreamingResponse(event_generator(), media_type="application/x-ndjson")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_db_path():
    return str(Path(__file__).resolve().parent.parent / "data" / "sqlite" / "novachem.db")

@app.get("/api/analytics")
async def get_analytics():
    try:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT status, COUNT(*) as count FROM equipment_master GROUP BY status")
        status_data = [{"status": row["status"], "count": row["count"]} for row in cursor.fetchall()]
        
        cursor.execute("SELECT equipment_id, SUM(downtime_hrs) as total_downtime FROM equipment_health_history GROUP BY equipment_id")
        downtime_data = [{"equipment_id": row["equipment_id"], "total_downtime": row["total_downtime"] or 0} for row in cursor.fetchall()]
        
        cursor.execute("SELECT event_type, COUNT(*) as count FROM equipment_health_history GROUP BY event_type")
        event_data = [{"event_type": row["event_type"], "count": row["count"]} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "status_distribution": status_data,
            "downtime_per_equipment": downtime_data,
            "event_types": event_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/equipment")
async def get_equipment_list():
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("SELECT equipment_id FROM equipment_master ORDER BY equipment_id")
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"equipment_ids": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/equipment/{eq_id}")
async def get_equipment_details(eq_id: str):
    try:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Fetch specs
        cursor.execute("SELECT * FROM equipment_master WHERE equipment_id = ?", (eq_id,))
        spec_row = cursor.fetchone()
        if not spec_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Equipment not found")
        
        specs = dict(spec_row)
        
        # Fetch recent events
        cursor.execute("SELECT * FROM equipment_health_history WHERE equipment_id = ? ORDER BY date DESC LIMIT 5", (eq_id,))
        events = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return {"specs": specs, "recent_events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
