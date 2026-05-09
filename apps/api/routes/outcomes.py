"""Sponsor outcome tracking (PRD §5.9, §6.7).

Captures the post-event funnel per (sponsor, attendee):

    no_follow_up → contacted → interviewing → offered → hired
                                         ↘    declined

Email cadence (T+14/+30/+60/+90) is not scheduled here — there is no
scheduler in the repo yet. This module is the data capture layer; a worker
that owns scheduling can read sponsor.contract.signed_at + an offset and
POST reminders, then read /outcomes to surface the funnel.

GET    /outcomes/{sponsor_id}              — list outcomes with funnel summary.
POST   /outcomes/{sponsor_id}/log          — log/update a single outcome row.
GET    /outcomes/{sponsor_id}/export.csv   — flat CSV for sponsor download.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from apps.api.routes._state import mutate_state, read_state
from packages.shared.event_state import empty_outcome


router = APIRouter(tags=["outcomes"])


_VALID_STATUSES = ("no_follow_up", "contacted", "interviewing", "offered", "hired", "declined")
_VALID_SOURCES = ("sponsor_report", "attendee_report", "signal_inference")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_sponsor(state: dict, sid: str) -> Optional[dict]:
    return next((s for s in (state.get("sponsors") or {}).get("roster", []) if s.get("id") == sid), None)


def _outcomes_for(state: dict, sid: str) -> list[dict]:
    return [o for o in (state.get("sponsors") or {}).get("outcomes", []) if o.get("sponsor_id") == sid]


def _funnel(rows: list[dict]) -> dict:
    counts: dict[str, int] = {s: 0 for s in _VALID_STATUSES}
    for r in rows:
        s = r.get("status") or "no_follow_up"
        counts[s] = counts.get(s, 0) + 1
    return counts


# ---------- GET ----------

@router.get("/outcomes/{sponsor_id}")
async def list_outcomes(sponsor_id: str) -> dict:
    state = read_state()
    sponsor = _find_sponsor(state, sponsor_id)
    if not sponsor:
        raise HTTPException(404, f"sponsor {sponsor_id} not found")
    rows = _outcomes_for(state, sponsor_id)
    return {
        "ok": True,
        "sponsor_id": sponsor_id,
        "outcomes": rows,
        "funnel": _funnel(rows),
        "total": len(rows),
    }


# ---------- POST log ----------

class OutcomeLog(BaseModel):
    attendee_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    role: Optional[str] = ""
    salary_range: Optional[str] = ""
    notes: Optional[str] = ""
    captured_via: Optional[str] = "sponsor_report"


@router.post("/outcomes/{sponsor_id}/log")
async def log_outcome(sponsor_id: str, body: OutcomeLog) -> dict:
    if body.status not in _VALID_STATUSES:
        raise HTTPException(400, f"status must be one of {list(_VALID_STATUSES)}")
    if body.captured_via and body.captured_via not in _VALID_SOURCES:
        raise HTTPException(400, f"captured_via must be one of {list(_VALID_SOURCES)}")

    def _apply(state: dict) -> dict:
        sponsor = _find_sponsor(state, sponsor_id)
        if not sponsor:
            raise HTTPException(404, f"sponsor {sponsor_id} not found")
        outcomes = state.setdefault("sponsors", {}).setdefault("outcomes", [])
        oid = f"out_{sponsor_id}_{body.attendee_id}"
        existing = next((o for o in outcomes if o.get("id") == oid), None)
        if existing is None:
            row = empty_outcome()
            row.update({
                "id": oid,
                "sponsor_id": sponsor_id,
                "attendee_id": body.attendee_id,
            })
            outcomes.append(row)
            existing = row

        previous = existing.get("status")
        existing["status"] = body.status
        if body.role is not None and body.role:
            existing["role"] = body.role
        if body.salary_range is not None and body.salary_range:
            existing["salary_range"] = body.salary_range
        if body.notes is not None and body.notes:
            existing["notes"] = body.notes
        existing["captured_via"] = body.captured_via or "sponsor_report"
        existing["captured_at"] = _now_iso()
        existing.setdefault("history", []).append({
            "ts": _now_iso(),
            "status": body.status,
            "previous_status": previous,
            "captured_via": existing["captured_via"],
            "notes": body.notes or "",
        })
        return {"outcome": existing, "outcomes": outcomes}

    res = mutate_state(_apply)
    return {
        "ok": True,
        "outcome": res["outcome"],
        "funnel": _funnel([o for o in res["outcomes"] if o.get("sponsor_id") == sponsor_id]),
    }


# ---------- CSV export ----------

@router.get("/outcomes/{sponsor_id}/export.csv", response_class=PlainTextResponse)
async def outcomes_csv(sponsor_id: str) -> PlainTextResponse:
    state = read_state()
    sponsor = _find_sponsor(state, sponsor_id)
    if not sponsor:
        raise HTTPException(404, f"sponsor {sponsor_id} not found")
    rows = _outcomes_for(state, sponsor_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["attendee_id", "status", "role", "salary_range", "captured_via", "captured_at", "notes"])
    for r in rows:
        w.writerow([
            r.get("attendee_id", ""), r.get("status", ""), r.get("role", ""),
            r.get("salary_range", ""), r.get("captured_via", ""), r.get("captured_at", ""),
            r.get("notes", ""),
        ])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")
