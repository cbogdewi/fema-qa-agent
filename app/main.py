"""FastAPI service: Ask FEMA. Runs locally with uvicorn and on AWS Lambda via Mangum."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from mangum import Mangum
from pydantic import BaseModel, Field

from .agent import Agent
from .config import get_settings
from .data import Database
from .llm import LLMError, RateLimitedError, build_llm

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("fema-qa")

settings = get_settings()
STATIC = Path(__file__).parent / "static"

app = FastAPI(
    title="Ask FEMA — LLM Q&A over OpenFEMA data",
    version="1.0.0",
    description="Natural-language questions over FEMA disaster declarations, answered with grounded SQL.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    max_age=3600,
)


@lru_cache
def get_db() -> Database:
    return Database(settings.db_path)


@lru_cache
def get_agent() -> Agent:
    return Agent(build_llm(settings), get_db(), settings.max_result_rows)


class RateLimiter:
    """Sliding-window limits per client IP. In-memory, so it resets on cold start;
    it blunts abuse of the free LLM quota rather than acting as a billing control."""

    def __init__(self, per_minute: int, per_day: int):
        self.per_minute, self.per_day = per_minute, per_day
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.time()
        q = self.hits[key]
        while q and now - q[0] > 86400:
            q.popleft()
        recent = sum(1 for t in q if now - t < 60)
        if recent >= self.per_minute or len(q) >= self.per_day:
            return False
        q.append(now)
        return True


limiter = RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_per_day)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=settings.max_question_chars)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict:
    db = get_db()
    ok = db.path.exists()
    return {
        "status": "ok" if ok else "degraded",
        "database": ok,
        "provider": settings.llm_provider,
        "data": db.metadata() if ok else {},
    }


@app.post("/api/ask")
def ask(body: AskRequest, request: Request) -> JSONResponse:
    # Mangum fills request.client from the Lambda request context (not spoofable by the caller).
    client = request.client.host if request.client else "unknown"
    if not limiter.check(client):
        raise HTTPException(429, "Rate limit reached for this demo. Please wait a minute and try again.")
    try:
        result = get_agent().ask(body.question)
    except RateLimitedError as e:
        raise HTTPException(503, str(e)) from e
    except LLMError as e:
        log.error(json.dumps({"event": "llm_error", "error": str(e)}))
        raise HTTPException(502, "The language model is unavailable right now.") from e
    log.info(
        json.dumps(
            {
                "event": "ask",
                "refused": result.refused,
                "latency_ms": result.latency_ms,
                "rows": len(result.rows),
                "error": result.error,
            }
        )
    )
    out = result.to_dict()
    out["data_as_of"] = get_db().metadata().get("loaded_at")
    return JSONResponse(out)


@lru_cache
def _stats() -> dict:
    db = get_db()

    def q(sql: str):
        return db.query(sql)[1]

    kpi = q("""
        SELECT COUNT(DISTINCT disaster_number),
               COUNT(DISTINCT disaster_number)
                   FILTER (WHERE EXTRACT(year FROM declaration_date) = EXTRACT(year FROM current_date)),
               COUNT(DISTINCT state),
               MIN(declaration_date), MAX(declaration_date)
        FROM declarations""")[0]
    top_type = q("""SELECT incident_type FROM declarations
                    WHERE declaration_date >= current_date - INTERVAL 10 YEAR
                    GROUP BY 1 ORDER BY COUNT(DISTINCT disaster_number) DESC LIMIT 1""")
    per_year = q("""SELECT CAST(EXTRACT(year FROM declaration_date) AS INTEGER) AS y, COUNT(DISTINCT disaster_number)
                    FROM declarations WHERE declaration_date >= DATE '2000-01-01' GROUP BY 1 ORDER BY 1""")
    by_type = q("""SELECT incident_type, COUNT(DISTINCT disaster_number) FROM declarations
                   WHERE declaration_date >= current_date - INTERVAL 10 YEAR GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")
    by_state = q("""SELECT state, COUNT(DISTINCT disaster_number) FROM declarations
                    WHERE declaration_date >= current_date - INTERVAL 10 YEAR GROUP BY 1 ORDER BY 2 DESC LIMIT 10""")
    recent = q("""SELECT fema_declaration_string, MIN(declaration_date), ANY_VALUE(state), ANY_VALUE(incident_type),
                         ANY_VALUE(declaration_title)
                  FROM declarations GROUP BY 1 ORDER BY 2 DESC LIMIT 8""")
    return {
        "kpis": {
            "total_disasters": kpi[0],
            "disasters_this_year": kpi[1],
            "states_and_territories": kpi[2],
            "first_declaration": kpi[3],
            "latest_declaration": kpi[4],
            "top_incident_type_10y": top_type[0][0] if top_type else None,
        },
        "per_year": [{"year": r[0], "disasters": r[1]} for r in per_year],
        "by_incident_type_10y": [{"incident_type": r[0], "disasters": r[1]} for r in by_type],
        "by_state_10y": [{"state": r[0], "disasters": r[1]} for r in by_state],
        "recent": [{"id": r[0], "date": r[1], "state": r[2], "incident_type": r[3], "title": r[4]} for r in recent],
        "meta": db.metadata(),
    }


@app.get("/api/stats")
def stats() -> dict:
    try:
        return _stats()
    except FileNotFoundError as e:
        raise HTTPException(503, "Data not loaded yet.") from e


@app.get("/api/evals")
def evals() -> dict:
    path = settings.eval_results_path
    if not path.exists():
        return {"available": False}
    return {"available": True, **json.loads(path.read_text())}


handler = Mangum(app, lifespan="off")
