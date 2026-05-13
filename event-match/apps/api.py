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
        self.event_name: str = ""        # for outreach draft personalization
        self.event_description: str = ""  # for outreach draft personalization
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
    state.event_name = event_name
    state.event_description = event_description
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


# Featured demo run (used by the landing page's "Open live demo" CTA).
# This is a pre-computed, full-event run that loads instantly with no LLM cost.
FEATURED_RUN_ID = "7b354ce31526"


def _hydrate_saved_run(run_id: str) -> RunState | None:
    """Load a saved run from data/matches/{run_id}/ into RUNS so the existing
    matrix/people/rationale endpoints can serve it without re-running the pipeline.

    Also rebuilds by_id (the EnrichedPerson dict) from .cache/enrich/*.json so
    lazy rationale generation works on clicked match cards.
    """
    run_dir = Path("data/matches") / run_id
    matrix_path = run_dir / "matrix.json"
    rubric_path = run_dir / "rubric.json"
    if not matrix_path.exists():
        return None
    state = RunState()
    state.matrix = json.loads(matrix_path.read_text())
    if rubric_path.exists():
        state.rubric = json.loads(rubric_path.read_text())

    # Rebuild by_id from the per-person enrichment cache so rationale generation
    # has access to full EnrichedPerson objects (bio, conviction, asks, etc.).
    enrich_dir = Path(".cache/enrich")
    if enrich_dir.exists():
        from dataclasses import fields as _dc_fields
        valid_fields = {f.name for f in _dc_fields(EnrichedPerson)}
        people_ids = {p["id"] for p in state.matrix.get("people", [])}
        for jf in enrich_dir.glob("*.json"):
            try:
                raw = json.loads(jf.read_text())
            except Exception:
                continue
            pid = raw.get("id")
            if pid in people_ids:
                # Filter to only dataclass fields; drop embeddings + extras
                clean = {k: v for k, v in raw.items() if k in valid_fields}
                # Coerce list-typed fields that may have been serialized as strings
                for lf in ("domains", "tech_stack", "conviction_themes",
                          "previous_experiences", "github_languages",
                          "github_top_repos", "x_recent_post_themes",
                          "explicit_asks", "mentor_signals", "roles_history",
                          "enrichment_sources", "enrichment_errors"):
                    v = clean.get(lf)
                    if isinstance(v, str):
                        try:
                            clean[lf] = json.loads(v.replace("'", '"'))
                        except Exception:
                            clean[lf] = []
                try:
                    state.by_id[pid] = EnrichedPerson(**clean)
                except Exception:
                    pass

    state.event_id = run_id
    state.event_name = state.matrix.get("event_name") or ""
    state.event_description = (state.rubric or {}).get("event_brief") or state.matrix.get("event_description") or ""
    state.done = True
    RUNS[run_id] = state
    return state


@app.on_event("startup")
async def _hydrate_featured() -> None:
    if FEATURED_RUN_ID and FEATURED_RUN_ID not in RUNS:
        _hydrate_saved_run(FEATURED_RUN_ID)


@app.get("/api/featured")
async def get_featured() -> JSONResponse:
    """Returns the featured demo run_id so the landing page can deep-link into it."""
    state = RUNS.get(FEATURED_RUN_ID) or _hydrate_saved_run(FEATURED_RUN_ID)
    if not state or not state.matrix:
        raise HTTPException(404, "featured run not available")
    m = state.matrix
    stats = m.get("stats", {})
    return JSONResponse({
        "run_id": FEATURED_RUN_ID,
        "event_name": m.get("event_name") or "Physical AI Hack SF",
        "n_people": stats.get("n_people", len(m.get("people", []))),
        "n_pairs_scored": stats.get("n_pairs_scored", 0),
        "n_mutual": stats.get("n_mutual_pairs", 0),
    })


INVITE_MODEL = "claude-haiku-4-5-20251001"
INVITE_CACHE_NS = "invite"
INVITE_CACHE_VERSION = "v1"


def _room_signature(room: dict) -> str:
    """Stable key for the room composition — same room → same cache hits."""
    parts = [
        room.get("name", ""),
        room.get("city", ""),
        room.get("description", "")[:240],
        ",".join(room.get("top_domains", [])[:4]),
        ",".join(f"{n.get('name','')}:{n.get('company','')}" for n in room.get("notable", [])[:5]),
    ]
    return "|".join(parts)


async def _personalize_invite(
    person: dict,
    room: dict,
    client,
) -> str | None:
    """LLM-personalized "come join us" message. Returns None if LLM fails."""
    from packages.shared import cache as _cache

    cache_key_parts = [
        INVITE_CACHE_VERSION,
        INVITE_MODEL,
        person.get("id", "") or person.get("name", ""),
        _room_signature(room),
    ]
    cached = _cache.get(INVITE_CACHE_NS, *cache_key_parts)
    if cached and cached.get("message"):
        return cached["message"]

    bio = (person.get("bio_text") or "")[:600]
    conviction = person.get("conviction_themes") or []
    if isinstance(conviction, str):
        try:
            conviction = json.loads(conviction.replace("'", '"'))
        except Exception:
            conviction = []
    conviction_str = "; ".join(conviction[:3]) if conviction else ""
    domains = person.get("domains") or []
    if isinstance(domains, str):
        try:
            domains = json.loads(domains.replace("'", '"'))
        except Exception:
            domains = []

    notable_lines_list = [
        f"- {n['name']} ({n['company']})"
        for n in (room.get("notable") or [])[:5]
        if n.get("name") and n.get("company") and n["name"] != person.get("name")
    ]
    notable_block = "\n".join(notable_lines_list) if notable_lines_list else "- a small group"
    domains_str = ", ".join(domains[:3]) if domains else "(unknown)"
    top_domains_str = ", ".join(room.get("top_domains", [])[:3]) or "this person's area of work"
    name = person.get("name", "")
    title = person.get("title") or person.get("role") or ""
    company = person.get("company", "")
    description = (room.get("description") or "a small gathering of operators in the space")[:240]

    prompt = f"""You're drafting a recruitment DM inviting someone to a small event. The goal is to get them to RSVP. Tone: casual, direct, founder-to-founder. 3-4 sentences max. No emojis. No "I hope this finds you well." No "Best,". Just the message body.

EVENT: {room.get('name','a small event')}
LOCATION: {room.get('city','SF')}
ABOUT: {description}
ALREADY CONFIRMED: {len(room.get('notable',[]))} notable folks including:
{notable_block}
ROOM SKEWS TOWARD: {top_domains_str}

WRITING TO:
Name: {name}
Title/role: {title}
Company: {company}
Domains they work in: {domains_str}
Bio: {bio or '(none)'}
Conviction themes: {conviction_str or '(none)'}

WRITE the message body only. Open with their first name. Reference one specific thing about their work or conviction (something only they would have written). Name 2 of the confirmed attendees by name. End with a direct ask like "Want in?" or "Worth a slot?"."""

    try:
        resp = await client.messages.create(
            model=INVITE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        if text:
            _cache.put(INVITE_CACHE_NS, {"message": text}, *cache_key_parts)
            return text
    except Exception as e:
        # Log and fall back to template; don't block the demo
        print(f"[invite-personalize] error for {person.get('name','?')}: {e}")
    return None


@app.get("/api/events/{run_id}/outreach")
async def get_outreach(run_id: str, personalize: int = 0, personalize_top: int = 0) -> JSONResponse:
    """Generate "come to this event" recruitment drafts.

    Each draft pitches the room: who's coming so far, what they work on, and
    why this specific recipient would fit. The frame is recruitment (get them
    to RSVP), not introductions — that comes later, after they're confirmed.
    """
    state = RUNS.get(run_id)
    if not state or not state.matrix:
        raise HTTPException(404, "run not found")

    # Reuse outreach_agent's _channel_for / _priority categorization for honesty
    # (same categorization shows up in event-v1's existing CRM). The message
    # body itself we generate fresh, room-aware.
    try:
        import sys
        from pathlib import Path as _P
        candidate = _P(__file__).resolve().parent.parent.parent
        if (candidate / "packages" / "ops" / "outreach_agent.py").exists():
            sys.path.insert(0, str(candidate))
        from packages.ops import outreach_agent as _oa
    except Exception:
        _oa = None

    matrix = state.matrix
    people = matrix.get("people", [])
    top_k = matrix.get("top_k_per_person", {})
    city = _infer_city(people)
    event_name = state.event_name or matrix.get("event_name") or "a small builder's dinner"
    event_desc = (state.event_description or "").strip()

    # Compute room composition for the pitch ─────────────────
    # Most notable attendees: highest fit_score (i.e. their best match composite)
    # and those with strong companies / bios.
    def _person_score(p: dict) -> float:
        return ((top_k.get(p["id"]) or [{}])[0] or {}).get("composite", 0)

    ranked = sorted(people, key=_person_score, reverse=True)
    notable = [p for p in ranked if p.get("name") and p.get("company")][:8]

    # Top domains across the whole room
    domain_counts: dict[str, int] = {}
    for p in people:
        for d in (p.get("domains") or []):
            if isinstance(d, str) and d:
                domain_counts[d] = domain_counts.get(d, 0) + 1
    top_domains = [d for d, _ in sorted(domain_counts.items(), key=lambda x: -x[1])[:4]]

    room = {
        "name": event_name,
        "description": event_desc[:240],
        "city": city,
        "n_people": len(people),
        "top_domains": top_domains,
        "notable": [
            {"name": p.get("name", ""), "company": p.get("company", ""), "title": p.get("title") or p.get("role") or ""}
            for p in notable
        ],
    }

    # Per-recipient draft: room pitch + their angle ─────────────────
    invites: list[dict[str, Any]] = []
    for p in people:
        person_dict = {
            "name": p.get("name", ""),
            "email": p.get("email", ""),
            "linkedin_url": p.get("linkedin_url", ""),
            "role": p.get("title") or p.get("role") or "",
            "company": p.get("company", ""),
            "fit_score": _person_score(p),
        }
        channel = _oa._channel_for(person_dict) if _oa else (
            "email" if person_dict["email"] else ("linkedin" if person_dict["linkedin_url"] else "poke")
        )
        priority = _oa._priority(person_dict) if _oa else (
            "high" if person_dict["fit_score"] >= 0.5 else "medium"
        )

        # Build the room-aware "come join us" message. Excludes the recipient
        # themselves from the "who's coming" list.
        first = (person_dict["name"] or "there").split()[0] or "there"
        others = [n for n in room["notable"] if n["name"] != p.get("name")][:3]
        whos_coming = ", ".join(
            f"{n['name']} ({n['company']})" for n in others if n["name"] and n["company"]
        ) or "a small group of operators in the space"
        domains_phrase = (
            ", ".join(top_domains[:3]) if top_domains else "your kind of work"
        )
        their_angle = (
            f"your work on {person_dict['role']}".strip()
            if person_dict["role"]
            else f"what you're building at {person_dict['company']}"
        ) if person_dict["company"] else "what you're building"

        message = (
            f"Hey {first} — putting together {event_name} in {city}. "
            f"Got {room['n_people']} folks confirmed so far including {whos_coming}. "
            f"Crowd skews toward {domains_phrase}. "
            f"Saw {their_angle} — you'd be one of the strongest in the room. "
            f"Want in?"
        )
        subject = f"{event_name} — {city}, you'd fit"
        follow_up = (
            f"Hey {first}, bumping this — list is starting to fill. "
            f"Happy to send the full lineup if you're potentially around."
        )

        invites.append({
            "name": p.get("name", ""),
            "company": p.get("company", ""),
            "role": person_dict["role"],
            "channel": channel,
            "priority": priority,
            "subject": subject,
            "message": message,
            "follow_up": follow_up,
            "person_id": p.get("id"),
            "email": p.get("email", ""),
            "linkedin_url": p.get("linkedin_url", ""),
            "x_handle": p.get("x_handle", ""),
        })

    # LLM personalization. personalize=0 → templates only. personalize=1 → LLM + cache.
    # personalize_top=0 means everyone; otherwise cap at that count (highest fit_score first).
    n_personalized = 0
    if personalize:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic()
        ranked_invites = sorted(invites, key=lambda x: -((top_k.get(x["person_id"]) or [{}])[0] or {}).get("composite", 0))
        targets = ranked_invites if personalize_top <= 0 else ranked_invites[:personalize_top]

        from dataclasses import asdict as _asdict
        # Cap parallel LLM calls so we don't trip Anthropic rate limits
        sem = asyncio.Semaphore(40)

        async def _do_one(inv):
            async with sem:
                pid = inv["person_id"]
                if pid in state.by_id:
                    p_full = _asdict(state.by_id[pid])
                else:
                    p_full = next((p for p in people if p.get("id") == pid), {})
                text = await _personalize_invite(p_full, room, client)
                if text:
                    inv["message"] = text
                    inv["personalized"] = True

        await asyncio.gather(*(_do_one(inv) for inv in targets))
        n_personalized = sum(1 for inv in invites if inv.get("personalized"))

    return JSONResponse({
        "event": {"name": event_name, "city": city, "description": event_desc[:240]},
        "room": {"n_people": room["n_people"], "top_domains": top_domains, "notable": room["notable"][:5]},
        "invites": invites,
        "invite_total": len(people),
        "personalized_count": n_personalized,
    })


def _infer_city(people: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for p in people:
        c = (p.get("city") or "").strip()
        if c:
            counts[c] = counts.get(c, 0) + 1
    if not counts:
        return "SF"
    return max(counts.items(), key=lambda x: x[1])[0]


@app.get("/api/healthz")
async def healthz() -> dict[str, Any]:
    return {"ok": True, "active_runs": len(RUNS)}


# Static assets (for any CSS/JS we want to add later)
if (UI_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=UI_DIR / "static"), name="static")
