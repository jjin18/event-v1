"""Post-event sponsor packet (PRD §5.8, §6.6).

Within 48 hours of event close, each sponsor gets a packet of every verified
ICP match: full profile, scan rating, memo, and a suggested follow-up draft.

In v1 the packet is HTML (browser-printable). PDF export and AI-generated
follow-up email drafts are scaffolded by the simple template here — a
downstream worker can swap in an LLM-generated draft.

GET /packets/{sponsor_id}.json — packet payload as JSON.
GET /packets/{sponsor_id}      — packet HTML view.

The packet is generated lazily — it always reflects the current contract
execution state. For a stable export, run /contracts/{sponsor_id}/execute first.
"""
from __future__ import annotations

import html
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from apps.api.routes._state import read_state
from packages.shared import tokens as token_mod


router = APIRouter(tags=["packets"])


def _find_sponsor(state: dict, sid: str) -> Optional[dict]:
    return next((s for s in (state.get("sponsors") or {}).get("roster", []) if s.get("id") == sid), None)


def _find_contract(state: dict, sid: str) -> Optional[dict]:
    return next((c for c in (state.get("sponsors") or {}).get("contracts", []) if c.get("sponsor_id") == sid), None)


def _verified_matches(state: dict, sid: str) -> list[dict]:
    return [m for m in (state.get("sponsors") or {}).get("matches", []) if m.get("sponsor_id") == sid]


def _attendee_index(state: dict) -> dict[str, dict]:
    """Map attendee_id → best available profile (attendees row + ranked prospect merge)."""
    out: dict[str, dict] = {}
    for p in (state.get("people") or {}).get("ranked_prospects", []) or []:
        pid = token_mod.attendee_id_for(p.get("name", ""), p.get("email", ""))
        out[pid] = {
            "id": pid,
            "name": p.get("name", ""),
            "company": p.get("company", ""),
            "role": p.get("role", ""),
            "email": p.get("email", ""),
            "linkedin_url": p.get("linkedin_url", ""),
            "persona": p.get("persona", ""),
            "fit_score": p.get("fit_score"),
            "why_relevant": p.get("why_relevant", ""),
        }
    for a in state.get("attendees") or []:
        aid = a.get("id")
        if not aid:
            continue
        merged = {**out.get(aid, {}), **{k: v for k, v in a.items() if v}}
        out[aid] = merged
    return out


def _follow_up_template(person: dict[str, Any], sponsor: dict[str, Any], memo: str) -> str:
    name = (person.get("name") or "there").split()[0]
    company = sponsor.get("company_name", "")
    role_hint = sponsor.get("icp", {}).get("free_text") or "the role we discussed"
    memo_line = f' I jotted down: "{memo.strip()}".' if memo else ""
    return (
        f"Hey {name} — great talking at the event.{memo_line}\n\n"
        f"At {company} we're hiring for {role_hint}, and from your background I think there's a real fit. "
        "Want to grab 20 minutes next week to compare notes?\n\nBest, [your name]"
    )


def _build_packet(state: dict, sid: str) -> dict[str, Any]:
    sponsor = _find_sponsor(state, sid)
    if not sponsor:
        raise HTTPException(404, f"sponsor {sid} not found")
    execution = _find_contract(state, sid)
    matches = _verified_matches(state, sid)
    scans_by_id = {s.get("id"): s for s in (state.get("sponsors") or {}).get("scans", [])}
    attendees = _attendee_index(state)

    rows: list[dict[str, Any]] = []
    for m in matches:
        person = attendees.get(m.get("attendee_id"), {"id": m.get("attendee_id")})
        scan = next((scans_by_id[i] for i in m.get("scan_ids", []) if i in scans_by_id), {})
        rows.append({
            "match_id": m.get("id"),
            "match_status": m.get("match_status"),
            "match_explanation": m.get("match_explanation"),
            "rating": m.get("rating"),
            "memo_text": m.get("memo_text"),
            "billable": m.get("billable"),
            "person": person,
            "scan": scan,
            "follow_up_draft": _follow_up_template(person, sponsor, m.get("memo_text") or ""),
        })

    return {
        "sponsor": sponsor,
        "execution": execution,
        "matches": rows,
        "summary": {
            "total_matches": len(rows),
            "billable": sum(1 for r in rows if r["billable"]),
            "partial": sum(1 for r in rows if r["match_status"] == "partial"),
        },
    }


@router.get("/packets/{sponsor_id}.json")
async def packet_json(sponsor_id: str) -> dict:
    state = read_state()
    return {"ok": True, "packet": _build_packet(state, sponsor_id)}


_PACKET_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__SPONSOR__ — post-event packet</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#FFFFFF;--bg-alt:#FAFAFA;--text:#0A0A0A;--text-2:#525252;--text-3:#A3A3A3;--border:#EAEAEA;--font:'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif}
*{box-sizing:border-box}html,body{margin:0;padding:0;color:var(--text);background:var(--bg);font:400 14px/1.55 var(--font)}
.wrap{max-width:820px;margin:0 auto;padding:48px 24px 80px}
header{border-bottom:1px solid var(--border);padding-bottom:24px;margin-bottom:32px}
header h1{margin:0 0 4px;font-size:28px;letter-spacing:-0.02em}
header .meta{color:var(--text-2);font-size:14px}
.kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}
.kpi div{background:var(--bg-alt);border:1px solid var(--border);border-radius:8px;padding:12px}
.kpi b{display:block;font-size:22px;font-weight:600}
.kpi span{font-size:11px;text-transform:uppercase;color:var(--text-2);letter-spacing:0.05em}
.match{border:1px solid var(--border);border-radius:8px;padding:18px;margin-bottom:14px}
.match h3{margin:0 0 4px;font-size:18px;font-weight:600}
.match .who{color:var(--text-2);font-size:13px}
.pill{display:inline-block;padding:2px 8px;font-size:11px;border-radius:999px;font-weight:600;letter-spacing:0.04em;text-transform:uppercase}
.pill-match{background:#DCFCE7;color:#166534}
.pill-partial{background:#FEF3C7;color:#92400E}
.pill-strong{background:#0A0A0A;color:#fff}
.pill-some{background:#E5E5E5;color:#171717}
.match .why{color:var(--text-2);font-size:13px;margin-top:8px}
.match .memo{margin-top:10px;padding:10px 12px;background:var(--bg-alt);border-radius:6px;font-size:13px}
.draft{margin-top:12px;border-top:1px dashed var(--border);padding-top:12px}
.draft b{display:block;font-size:11px;text-transform:uppercase;color:var(--text-2);letter-spacing:0.05em;margin-bottom:6px}
.draft pre{background:var(--bg-alt);padding:12px;border-radius:6px;white-space:pre-wrap;margin:0;font-family:inherit;font-size:13px;line-height:1.55}
@media print{header,.kpi{break-inside:avoid}.match{break-inside:avoid;page-break-inside:avoid}}
</style></head><body>
<div class="wrap">
<header>
<h1>__SPONSOR__ — post-event packet</h1>
<div class="meta">__EVENT__ • Final invoice: $__INVOICE__ • __MATCH_COUNT__ verified matches</div>
<div class="kpi">
<div><b>__TOTAL__</b><span>Total matches</span></div>
<div><b>__BILLABLE__</b><span>Billable</span></div>
<div><b>__PARTIAL__</b><span>Partial</span></div>
<div><b>$__INVOICE__</b><span>Invoice</span></div>
</div>
</header>
__MATCHES__
</div></body></html>"""


def _pill(status: str) -> str:
    cls = "pill-match" if status == "match" else ("pill-partial" if status == "partial" else "pill-some")
    return f'<span class="pill {cls}">{html.escape(status or "")}</span>'


def _rating_pill(rating: str) -> str:
    cls = "pill-strong" if rating == "strong_fit" else ("pill-some" if rating == "some_interest" else "pill-some")
    return f'<span class="pill {cls}">{html.escape(rating or "")}</span>'


@router.get("/packets/{sponsor_id}", response_class=HTMLResponse)
async def packet_page(sponsor_id: str) -> HTMLResponse:
    state = read_state()
    packet = _build_packet(state, sponsor_id)
    sponsor = packet["sponsor"]
    execution = packet["execution"] or {}
    summary = packet["summary"]

    matches_html: list[str] = []
    for r in packet["matches"]:
        p = r["person"]
        memo = (r["memo_text"] or "").strip()
        memo_html = (
            f'<div class="memo">"{html.escape(memo)}"</div>' if memo else ""
        )
        matches_html.append(
            f'<div class="match">'
            f'<div>{_pill(r["match_status"])} {_rating_pill(r["rating"])}</div>'
            f'<h3>{html.escape(p.get("name") or "(unknown)")} </h3>'
            f'<div class="who">{html.escape(p.get("company") or "")} — {html.escape(p.get("role") or "")}</div>'
            f'<div class="why">{html.escape(r["match_explanation"] or "")}</div>'
            f'{memo_html}'
            f'<div class="draft"><b>Suggested follow-up</b><pre>{html.escape(r["follow_up_draft"])}</pre></div>'
            f'</div>'
        )

    if not matches_html:
        matches_html.append('<p style="color:var(--text-3)">No verified matches yet. Run /contracts/{sponsor_id}/execute after the event.</p>')

    page = (
        _PACKET_PAGE
        .replace("__SPONSOR__", html.escape(sponsor.get("company_name") or ""))
        .replace("__EVENT__", html.escape((state.get("event") or {}).get("name") or "Event"))
        .replace("__INVOICE__", f"{execution.get('final_invoice_amount', 0):.0f}")
        .replace("__MATCH_COUNT__", str(execution.get("verified_match_count", summary["billable"])))
        .replace("__TOTAL__", str(summary["total_matches"]))
        .replace("__BILLABLE__", str(summary["billable"]))
        .replace("__PARTIAL__", str(summary["partial"]))
        .replace("__MATCHES__", "\n".join(matches_html))
    )
    return HTMLResponse(page)
