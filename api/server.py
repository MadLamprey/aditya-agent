"""
FastAPI server exposing the AMA pipeline over HTTP.

Start with:
    uvicorn api.server:app --reload --port 8000

Or directly:
    python api/server.py
"""

import sys
import os

# Allow imports from project root when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from src.chain import ask

app = FastAPI(title="AMA Bot API", version="1.0.0")

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str
    audience: str = ""
    history: list[list[str]] = []  # list of [user_msg, assistant_msg] pairs


class QueryResponse(BaseModel):
    answer: str
    sources_used: list[str]
    audience: str
    routing_reasoning: str
    is_off_topic: bool
    is_low_confidence: bool
    latency_ms: float


@app.post("/ask", response_model=QueryResponse)
async def ask_endpoint(req: QueryRequest):
    try:
        history_tuples = [(h[0], h[1]) for h in req.history if len(h) == 2]
        response = ask(req.query, audience_hint=req.audience, history=history_tuples)
        return QueryResponse(
            answer=response.answer,
            sources_used=response.sources_used,
            audience=response.audience,
            routing_reasoning=response.routing_reasoning,
            is_off_topic=response.is_off_topic,
            is_low_confidence=response.is_low_confidence,
            latency_ms=response.latency_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
