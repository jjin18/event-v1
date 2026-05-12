"""FastAPI app — upload CSV → run pipeline → SSE progress → serve match results.

Routes:
  GET  /                          → index.html
  POST /api/match                 → upload CSV + event metadata, returns event_id
  GET  /api/events/{id}/stream    → SSE stream of progress events
  GET  /api/events/{id}/matrix    → final matrix JSON
  GET  /api/events/{id}/people/{pid}  → single-person detail

Run: uvicorn apps.api:app --reload --port 8001
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Ensure packages load .env
import packages  # noqa: F401
from packages.run import run_pipeline
from packages.schema import EnrichedPerson
from packages.explain import explain_matches, _pair_key


app = FastAPI(title="event-match")

# CORS — permissive for the demo. When deployed behind a subdomain proxy
# this lets the proxy + browser handshake work regardless of origin.
# Tighten allow_origins to specific domains once we know the production URLs.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

UI_DIR = Path(__file__).parent / "ui"
INPUT_DIR = Path("data/input")
INPUT_DIR.mkdir(parents=True, exist_ok=True)


# --- In-memory state ---
# Per-run state: queue of progress events + final matrix.
# A run_id is a uuid generated at upload time. The actual event_id (hash of
# event name+desc) comes back from rubric synthesis.
class RunState:
    def __init__(self) -> None:
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.matrix: dict[str, Any] | None = None
        self.by_id: dict[str, EnrichedPerson] = {}   # enriched people for lazy explain
        self.rubric: dict[str, Any] | None = None
        self.event_id: str | None = None
        self.done: bool = False
        self.error: str | None = None
        self.started_at: float = time.time()


RUNS: dict[str, RunState] = {}


# --- Routes ---

@app.get("/")
async def root() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.post("/api/match")
async def start_match(
    csv: UploadFile = File(...),
    event_name: str = Form(...),
    event_description: str = Form(...),
    top_k: int = Form(5),
    enrich_limit: int = Form(0),
    enrich_concurrency: int = Form(50),
    explain_mode: str = Form("lazy"),  # "lazy" = on-click; "upfront" = generate all
    enrich_model: str = Form("claude-haiku-4-5-20251001"),  # haiku=cheap, sonnet=high-quality
) -> JSONResponse:
    """Upload a CSV and start the pipeline. Returns a run_id immediately.

    Client should then EventSource /api/events/{run_id}/stream for progress.
    """
    # Persist CSV to disk so the pipeline can re-read it
    run_id = uuid.uuid4().hex[:12]
    csv_path = INPUT_DIR / f"upload_{run_id}_{csv.filename or 'event.csv'}"
    csv_path.write_bytes(await csv.read())

    state = RunState()
    RUNS[run_id] = state

    async def on_progress(event: str, payload: dict[str, Any]) -> None:
        await state.queue.put({"event": event, "data": payload})

    async def run_in_background() -> None:
        try:
            matrix, by_id, rubric = await run_pipeline(
                csv_path,
                event_name=event_name,
                event_description=event_description,
                top_k=top_k,
                enrich_limit=enrich_limit if enrich_limit > 0 else None,
                enrich_concurrency=enrich_concurrency,
                explain_mode=explain_mode,
                enrich_model=enrich_model,
                on_progress=on_progress,
            )
            state.matrix = matrix
            state.by_id = by_id
            state.rubric = rubric
            state.event_id = matrix.get("event_id")
        except Exception as e:
            state.error = repr(e)
            await state.queue.put({"event": "error", "data": {"error": repr(e)}})
        finally:
            state.done = True
            await state.queue.put({"event": "__close__", "data": {}})

    asyncio.create_task(run_in_background())

    return JSONResponse({"run_id": run_id, "status": "started"})


@app.get("/api/events/{run_id}/stream")
async def stream(run_id: str) -> StreamingResponse:
    state = RUNS.get(run_id)
    if not state:
        raise HTTPException(404, f"unknown run_id: {run_id}")

    async def gen():
        # Heartbeat so the client knows the connection is live
        yield f"event: hello\ndata: {json.dumps({'run_id': run_id})}\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(state.queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if msg.get("event") == "__close__":
                yield f"event: __close__\ndata: {{}}\n\n"
                break
            payload = json.dumps(msg["data"], default=str)
            yield f"event: {msg['event']}\ndata: {payload}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/events/{run_id}/matrix")
async def get_matrix(run_id: str) -> JSONResponse:
    state = RUNS.get(run_id)
    if not state:
        raise HTTPException(404, f"unknown run_id: {run_id}")
    if not state.done:
        raise HTTPException(202, "still running")
    if state.error:
        raise HTTPException(500, state.error)
    return JSONResponse(state.matrix)


@app.get("/api/events/{run_id}/people/{person_id}")
async def get_person_detail(run_id: str, person_id: str) -> JSONResponse:
    """Get a person's top-K. Returns immediately without generating rationales —
    the UI fetches rationales async per card so cards appear instantly."""
    state = RUNS.get(run_id)
    if not state or not state.matrix:
        raise HTTPException(404, "run or matrix not found")
    matrix = state.matrix
    person = next((p for p in matrix.get("people", []) if p["id"] == person_id), None)
    if not person:
        raise HTTPException(404, "person not found")
    top_k = matrix.get("top_k_per_person", {}).get(person_id, [])

    by_id_denorm = {p["id"]: p for p in matrix.get("people", [])}
    enriched_matches = []
    for m in top_k:
        other = by_id_denorm.get(m["other_id"])
        if other:
            enriched_matches.append({**m, "other": other})
    return JSONResponse({"person": person, "matches": enriched_matches})


@app.post("/api/events/{run_id}/rationale")
async def get_single_rationale(run_id: str, payload: dict) -> JSONResponse:
    """Generate one pair's rationale. UI calls this in parallel per-card so
    rationales stream in as they finish (rather than waiting for all 5)."""
    state = RUNS.get(run_id)
    if not state or not state.matrix:
        raise HTTPException(404, "run or matrix not found")
    if not (state.by_id and state.rubric):
        raise HTTPException(503, "enrichment state unavailable")
    a_id = payload.get("a_id")
    b_id = payload.get("b_id")
    if not (a_id and b_id):
        raise HTTPException(400, "a_id and b_id required")
    key = _pair_key(a_id, b_id)
    # Look up the existing pair record (or compute on the fly)
    pair_record = None
    for p in state.matrix.get("pairs", []):
        if _pair_key(p["a_id"], p["b_id"]) == key:
            pair_record = p
            break
    if not pair_record:
        raise HTTPException(404, "pair not found")
    # If already cached on the record, return immediately
    if pair_record.get("rationale"):
        return JSONResponse({
            "rationale": pair_record["rationale"],
            "intro_message": pair_record.get("intro_message", ""),
        })
    # Generate just this one rationale
    from packages.explain import _explain_one
    from anthropic import AsyncAnthropic
    a = state.by_id.get(a_id)
    b = state.by_id.get(b_id)
    if not (a and b):
        raise HTTPException(404, "enriched person not found")
    client = AsyncAnthropic()
    out = await _explain_one(a, b, pair_record, state.rubric, client)
    pair_record["rationale"] = out.get("rationale", "")
    pair_record["intro_message"] = out.get("intro_message", "")
    # Also mirror into top_k entries for both people
    for pid in (a_id, b_id):
        for m in state.matrix.get("top_k_per_person", {}).get(pid, []):
            if m["other_id"] == (b_id if pid == a_id else a_id):
                m["rationale"] = out.get("rationale", "")
                m["intro_message"] = out.get("intro_message", "")
    return JSONResponse(out)


@app.get("/api/healthz")
async def healthz() -> dict[str, Any]:
    return {"ok": True, "active_runs": len(RUNS)}


# Static assets (for any CSS/JS we want to add later)
if (UI_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=UI_DIR / "static"), name="static")
