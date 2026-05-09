"""Pre-event composition reveal (PRD §5.4).

Three days before the event, confirmed attendees see "who else is coming"
as anonymized aggregate counts plus the sponsor list with stated ICPs.

This module exposes both the aggregate JSON (consumable by an emailer or
downstream UI) and a public HTML page suitable for direct sharing.

GET /composition/{event_id}.json  — anonymized aggregate JSON.
GET /composition/{event_id}       — public HTML page.

For v1 there's only one event in the system, so ``event_id`` is the eid
derived in tokens.event_id_for(state['event']).
"""
from __future__ import annotations

import html
from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from apps.api.routes._state import read_state
from packages.shared import tokens as token_mod


router = APIRouter(tags=["composition"])


def _bucket_persona(p: dict[str, Any]) -> str:
    persona = (p.get("persona") or "").strip()
    if persona:
        return persona
    role = (p.get("role") or "").lower()
    if any(w in role for w in ("founder", "ceo", "cto", "head of", "lead")):
        return "founders/leads"
    if any(w in role for w in ("research", "phd", "postdoc")):
        return "researchers"
    if any(w in role for w in ("student", "intern", "ms ", "phd")):
        return "students"
    if "engineer" in role or "developer" in role:
        return "engineers"
    return "other"


def _aggregate(state: dict) -> dict[str, Any]:
    attendees = state.get("attendees") or []
    confirmed = [a for a in attendees if a.get("status") in ("Confirmed", "Attended")]

    # Counts by persona — derived from ranked_prospects when an attendee row
    # doesn't carry persona of its own.
    by_id = {token_mod.attendee_id_for(p.get("name", ""), p.get("email", "")): p
             for p in (state.get("people") or {}).get("ranked_prospects", [])}

    persona_counts: Counter[str] = Counter()
    affiliation_counts: Counter[str] = Counter()
    for a in confirmed:
        person_payload = by_id.get(a.get("id"), {})
        merged = {**person_payload, **a}
        persona_counts[_bucket_persona(merged)] += 1
        company = (merged.get("company") or "").strip()
        if company:
            affiliation_counts[company] += 1

    sponsors = (state.get("sponsors") or {}).get("roster", [])
    sponsor_view = [{
        "company_name": s.get("company_name"),
        "icp_summary": _summarize_icp(s.get("icp", {})),
    } for s in sponsors if s.get("status") != "draft"]

    return {
        "event_name": (state.get("event") or {}).get("name", ""),
        "event_date": state.get("event_date") or "",
        "city": (state.get("event") or {}).get("city", ""),
        "confirmed_count": len(confirmed),
        "persona_breakdown": dict(persona_counts),
        "top_affiliations": [n for n, _ in affiliation_counts.most_common(10)],
        "sponsors": sponsor_view,
    }


def _summarize_icp(icp: dict) -> str:
    if not icp:
        return ""
    parts: list[str] = []
    if icp.get("role_categories"):
        parts.append(", ".join(icp["role_categories"]))
    if icp.get("seniority_bands"):
        parts.append("(" + ", ".join(icp["seniority_bands"]) + ")")
    if icp.get("skill_signals"):
        parts.append("with " + ", ".join(icp["skill_signals"][:3]))
    if icp.get("free_text"):
        parts.append("— " + icp["free_text"])
    return " ".join(parts).strip()


def _resolve_event_id(state: dict, requested: str) -> str:
    eid = token_mod.event_id_for(state.get("event") or {})
    if requested != eid:
        raise HTTPException(404, f"event {requested} not found (current: {eid})")
    return eid


@router.get("/composition/{event_id}.json")
async def composition_json(event_id: str) -> dict:
    state = read_state()
    _resolve_event_id(state, event_id)
    agg = _aggregate(state)
    return {"ok": True, "event_id": event_id, "composition": agg}


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__EVENT__ — who's coming</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#FFFFFF;--bg-alt:#FAFAFA;--text:#0A0A0A;--text-2:#525252;--text-3:#A3A3A3;--border:#EAEAEA;--font:'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif}
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{font:400 15px/1.55 var(--font);color:var(--text);background:var(--bg)}
.wrap{max-width:680px;margin:0 auto;padding:60px 24px}
h1{font-size:32px;letter-spacing:-0.02em;margin:0 0 6px;font-weight:600}
.meta{color:var(--text-2);font-size:14px}
section{margin-top:34px}
section h2{font-size:13px;letter-spacing:0.06em;text-transform:uppercase;color:var(--text-2);margin:0 0 14px;font-weight:600}
.row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)}
.row:last-child{border-bottom:0}
.row b{font-weight:500}
.row span{color:var(--text-2);font-variant-numeric:tabular-nums}
.tag{display:inline-block;padding:3px 10px;background:var(--bg-alt);border:1px solid var(--border);border-radius:999px;font-size:12px;color:var(--text-2);margin:0 6px 6px 0}
.sponsor{padding:12px 0;border-bottom:1px solid var(--border)}
.sponsor:last-child{border-bottom:0}
.sponsor b{font-weight:600}
.sponsor div{color:var(--text-2);font-size:14px;margin-top:3px}
.muted{color:var(--text-3);font-size:13px;margin-top:30px;font-style:italic}
</style></head><body>
<div class="wrap">
<h1>__EVENT__</h1>
<div class="meta">__WHEN____CITY__ • __COUNT__ confirmed</div>
<section>
<h2>Who's coming</h2>
__PERSONAS__
</section>
<section>
<h2>Notable affiliations</h2>
<div>__AFFILIATIONS__</div>
</section>
<section>
<h2>Sponsors and what they're looking for</h2>
__SPONSORS__
</section>
<p class="muted">Counts above include only confirmed attendees. Anonymized — no individual identities.</p>
</div></body></html>"""


@router.get("/composition/{event_id}", response_class=HTMLResponse)
async def composition_page(event_id: str) -> HTMLResponse:
    state = read_state()
    _resolve_event_id(state, event_id)
    agg = _aggregate(state)

    personas = "".join(
        f'<div class="row"><b>{html.escape(p)}</b><span>{n}</span></div>'
        for p, n in sorted(agg["persona_breakdown"].items(), key=lambda kv: -kv[1])
    ) or '<div class="row"><b>No confirmed attendees yet</b><span>—</span></div>'

    affiliations = "".join(f'<span class="tag">{html.escape(a)}</span>'
                           for a in agg["top_affiliations"]) or '<span class="muted">None yet</span>'

    sponsors = "".join(
        f'<div class="sponsor"><b>{html.escape(s["company_name"] or "")}</b>'
        f'<div>{html.escape(s["icp_summary"] or "(no ICP listed)")}</div></div>'
        for s in agg["sponsors"]
    ) or '<div class="sponsor"><b>No sponsors yet</b></div>'

    when = html.escape(agg["event_date"]) + " " if agg["event_date"] else ""
    city = html.escape(agg["city"]) + " " if agg["city"] else ""

    page = (
        _PAGE
        .replace("__EVENT__", html.escape(agg["event_name"] or "Event"))
        .replace("__WHEN__", when)
        .replace("__CITY__", city)
        .replace("__COUNT__", str(agg["confirmed_count"]))
        .replace("__PERSONAS__", personas)
        .replace("__AFFILIATIONS__", affiliations)
        .replace("__SPONSORS__", sponsors)
    )
    return HTMLResponse(page)
