"""Booth scanner: scan logging + mobile web UI (PRD §5.6, §6.3).

The scanner is a mobile web app. Auth is a signed scanner-session token
embedded in the URL — the booth-staff link issued from /sponsors/{id}/staff/issue.
No login screen; the token is the credential.

GET    /scanner/{token}              — mobile scanner UI (server-rendered HTML).
POST   /scans                        — log a scan (token + badge_token + rating + memo).
GET    /scans/by-sponsor/{sponsor_id} — list scans for a sponsor (real-time dashboard).
"""
from __future__ import annotations

import html
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from apps.api.routes._state import mutate_state, read_state
from packages.shared import tokens as token_mod
from packages.shared.event_state import empty_scan
from packages.scoring.sponsor_match import match_attendee_to_sponsor


router = APIRouter(tags=["scans"])


_VALID_RATINGS = {"strong_fit", "some_interest", "not_a_match"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_sponsor(state: dict, sid: str) -> Optional[dict]:
    return next((s for s in (state.get("sponsors") or {}).get("roster", []) if s.get("id") == sid), None)


def _find_attendee(state: dict, aid: str) -> Optional[dict]:
    """Resolve the attendee profile for matching.

    Merges the attendees row (status / notes) with the matching
    ranked_prospects row (role / persona / why_relevant / tags) so the ICP
    matcher sees the richer signal columns. The attendees row wins on
    overlapping keys — it's the operator-edited surface.
    """
    attendees_row: Optional[dict] = next((a for a in (state.get("attendees") or []) if a.get("id") == aid), None)
    prospect_row: Optional[dict] = None
    for p in (state.get("people") or {}).get("ranked_prospects", []) or []:
        if token_mod.attendee_id_for(p.get("name", ""), p.get("email", "")) == aid:
            prospect_row = p
            break
    if attendees_row is None and prospect_row is None:
        return None
    base = {
        "id": aid,
        "name": (prospect_row or {}).get("name", "") or (attendees_row or {}).get("name", ""),
        "company": (prospect_row or {}).get("company", "") or (attendees_row or {}).get("company", ""),
        "role": (prospect_row or {}).get("role", ""),
        "email": (prospect_row or {}).get("email", "") or (attendees_row or {}).get("email", ""),
        "fit_score": (prospect_row or {}).get("fit_score"),
        "persona": (prospect_row or {}).get("persona", ""),
        "why_relevant": (prospect_row or {}).get("why_relevant", ""),
        "tags": (prospect_row or {}).get("tags", []),
        "notes": (prospect_row or {}).get("notes", ""),
    }
    if attendees_row:
        for k, v in attendees_row.items():
            if v not in (None, "", []):
                base[k] = v
    return base


# ---------- POST /scans ----------

class ScanBody(BaseModel):
    scanner_token: str = Field(..., min_length=8)
    badge_token: str = Field(..., min_length=8)
    rating: str = Field(..., description="strong_fit | some_interest | not_a_match")
    memo_text: Optional[str] = ""


@router.post("/scans")
async def log_scan(body: ScanBody) -> dict:
    if body.rating not in _VALID_RATINGS:
        raise HTTPException(400, f"rating must be one of {sorted(_VALID_RATINGS)}")
    state = read_state()
    event = state.get("event") or {}

    try:
        scanner_payload = token_mod.verify_scanner_session(body.scanner_token, event)
    except token_mod.TokenError as e:
        raise HTTPException(401, f"scanner token invalid: {e}")
    try:
        badge_payload = token_mod.verify(body.badge_token, event)
    except token_mod.TokenError as e:
        raise HTTPException(400, f"badge token invalid: {e}")

    sponsor_id = scanner_payload["sid"]
    attendee_id = badge_payload["aid"]
    staff_email = scanner_payload.get("staff", "")

    sponsor = _find_sponsor(state, sponsor_id)
    if not sponsor:
        raise HTTPException(404, f"sponsor {sponsor_id} not found")
    attendee = _find_attendee(state, attendee_id)

    # Compute match status. If we can't resolve the attendee profile (badge
    # for someone outside our roster), surface as needs_review.
    if attendee is None:
        match_status = "needs_review"
        match_explanation = "Attendee not found in roster; needs operator review."
    else:
        result = match_attendee_to_sponsor(attendee, sponsor)
        match_status = result["match_status"]
        match_explanation = result["match_explanation"]

    ts_unix = int(time.time())
    scan = empty_scan()
    scan.update({
        "id": token_mod.scan_id_for(sponsor_id, attendee_id, ts_unix),
        "sponsor_id": sponsor_id,
        "attendee_id": attendee_id,
        "booth_staff_email": staff_email,
        "scanned_at": _now_iso(),
        "rating": body.rating,
        "match_status": match_status,
        "match_explanation": match_explanation,
        "memo_text": (body.memo_text or "")[:200],
        "status_reviewed": "pending",
    })

    def _apply(s: dict) -> dict:
        scans = s.setdefault("sponsors", {}).setdefault("scans", [])
        scans.append(scan)
        return {"scan": scan, "scans": scans}

    res = mutate_state(_apply)
    counts = _summarize_for_sponsor(res["scans"], sponsor_id)
    return {
        "ok": True,
        "scan": res["scan"],
        "attendee": attendee,
        "match": {"status": match_status, "explanation": match_explanation},
        "summary": counts,
    }


def _summarize_for_sponsor(scans: list[dict], sponsor_id: str) -> dict:
    rows = [s for s in scans if s.get("sponsor_id") == sponsor_id]
    return {
        "total_scans": len(rows),
        "matches": sum(1 for s in rows if s.get("match_status") == "match"),
        "partial": sum(1 for s in rows if s.get("match_status") == "partial"),
        "needs_review": sum(1 for s in rows if s.get("match_status") == "needs_review"),
        "strong_fit": sum(1 for s in rows if s.get("rating") == "strong_fit"),
    }


# ---------- GET /scans/by-sponsor/{sponsor_id} ----------

@router.get("/scans/by-sponsor/{sponsor_id}")
async def scans_by_sponsor(sponsor_id: str) -> dict:
    state = read_state()
    sponsor = _find_sponsor(state, sponsor_id)
    if not sponsor:
        raise HTTPException(404, f"sponsor {sponsor_id} not found")
    all_scans = (state.get("sponsors") or {}).get("scans", []) or []
    rows = [s for s in all_scans if s.get("sponsor_id") == sponsor_id]
    rows.sort(key=lambda s: s.get("scanned_at", ""), reverse=True)
    return {
        "ok": True,
        "sponsor_id": sponsor_id,
        "scans": rows,
        "summary": _summarize_for_sponsor(all_scans, sponsor_id),
    }


# ---------- GET /scanner/{token} (mobile UI) ----------

_SCANNER_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Booth scanner</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#0A0A0A;--panel:#171717;--text:#FAFAFA;--text-2:#A3A3A3;--accent:#22C55E;--warn:#F59E0B;--err:#EF4444;--border:#262626;--font:'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif}
*{box-sizing:border-box}html,body{margin:0;padding:0;background:var(--bg);color:var(--text);font:400 15px/1.5 var(--font);min-height:100dvh}
header{padding:18px 20px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
header h1{margin:0;font-size:16px;font-weight:600;letter-spacing:-0.01em}
header .meta{color:var(--text-2);font-size:12px}
main{padding:20px;display:flex;flex-direction:column;gap:16px;max-width:520px;margin:0 auto}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:16px}
.panel h2{margin:0 0 8px;font-size:14px;font-weight:600;color:var(--text-2);letter-spacing:0.02em;text-transform:uppercase}
input,textarea{width:100%;background:#0F0F0F;color:var(--text);border:1px solid var(--border);border-radius:6px;padding:12px;font:inherit}
input:focus,textarea:focus{outline:0;border-color:#525252}
.btn-row{display:flex;gap:8px;margin-top:10px}
.btn{flex:1;padding:14px;border:1px solid var(--border);border-radius:6px;font:600 14px var(--font);cursor:pointer;background:transparent;color:var(--text)}
.btn-strong{background:var(--accent);color:#0A0A0A;border-color:var(--accent)}
.btn-some{background:#262626;color:var(--text);border-color:var(--border)}
.btn-none{background:transparent;color:var(--text-2);border-color:var(--border)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.match-pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600}
.pill-match{background:rgba(34,197,94,0.18);color:var(--accent)}
.pill-partial{background:rgba(245,158,11,0.18);color:var(--warn)}
.pill-needs-review{background:rgba(239,68,68,0.18);color:var(--err)}
.pill-none{background:#262626;color:var(--text-2)}
.attendee-name{font-size:18px;font-weight:600;margin:6px 0 2px}
.attendee-meta{color:var(--text-2);font-size:13px}
.explain{margin-top:8px;color:var(--text-2);font-size:12px;line-height:1.5}
.history{display:flex;flex-direction:column;gap:8px}
.row{padding:10px 0;border-bottom:1px solid var(--border)}
.row:last-child{border-bottom:0}
.row-name{font-weight:500}
.row-meta{color:var(--text-2);font-size:12px;margin-top:2px}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--accent);color:#0A0A0A;padding:10px 18px;border-radius:8px;font-weight:600;font-size:13px;display:none}
.toast.err{background:var(--err);color:#fff}
.kpi{display:flex;gap:12px;margin-top:8px}
.kpi div{flex:1;background:#0F0F0F;border:1px solid var(--border);border-radius:6px;padding:10px;text-align:center}
.kpi b{display:block;font-size:18px;font-weight:600}
.kpi span{font-size:11px;color:var(--text-2);text-transform:uppercase;letter-spacing:0.04em}
</style></head><body>
<header>
  <h1>__SPONSOR__</h1>
  <span class="meta">__STAFF__</span>
</header>
<main>
<section class="panel">
  <h2>Scan badge</h2>
  <input id="badge" placeholder="Paste badge token (camera support TBD)" autocomplete="off"/>
  <div id="profile" style="margin-top:12px;display:none">
    <div><span id="status-pill" class="match-pill"></span></div>
    <div class="attendee-name" id="att-name"></div>
    <div class="attendee-meta" id="att-meta"></div>
    <div class="explain" id="att-explain"></div>
    <textarea id="memo" rows="2" placeholder="Optional memo (60 chars)" maxlength="200" style="margin-top:10px"></textarea>
    <div class="btn-row">
      <button class="btn btn-strong" data-rating="strong_fit">Strong fit</button>
      <button class="btn btn-some" data-rating="some_interest">Some interest</button>
      <button class="btn btn-none" data-rating="not_a_match">Not a match</button>
    </div>
  </div>
</section>
<section class="panel">
  <h2>Today</h2>
  <div class="kpi">
    <div><b id="k-total">0</b><span>Scans</span></div>
    <div><b id="k-match">0</b><span>Matches</span></div>
    <div><b id="k-partial">0</b><span>Partial</span></div>
    <div><b id="k-strong">0</b><span>Strong</span></div>
  </div>
</section>
<section class="panel">
  <h2>Recent scans</h2>
  <div class="history" id="history"></div>
</section>
</main>
<div id="toast" class="toast"></div>
<script>
const SCANNER_TOKEN = "__TOKEN__";
const SPONSOR_ID = "__SID__";
let pendingAttendee = null;

const $ = s => document.querySelector(s);
const badge = $('#badge'), profile = $('#profile');

function showToast(msg, err){
  const t = $('#toast'); t.textContent = msg; t.className = 'toast' + (err?' err':''); t.style.display='block';
  setTimeout(()=> t.style.display='none', 2200);
}

async function lookup(token){
  if(!token) return;
  // Pre-validation happens server-side in /scans; here we just stash the
  // token and reveal the profile panel after a probe.
  pendingAttendee = token;
  profile.style.display='block';
  $('#att-name').textContent = 'Ready to scan';
  $('#att-meta').textContent = 'Token captured — choose a rating to record.';
  $('#att-explain').textContent = '';
  $('#status-pill').className = 'match-pill pill-needs-review';
  $('#status-pill').textContent = 'pending';
}
badge.addEventListener('change', e => lookup(e.target.value.trim()));
badge.addEventListener('input', e => { if(!e.target.value) profile.style.display='none'; });

async function submit(rating){
  const token = pendingAttendee || badge.value.trim();
  if(!token){ showToast('Scan a badge first', true); return; }
  const memo = $('#memo').value.trim();
  document.querySelectorAll('.btn').forEach(b=>b.disabled=true);
  try{
    const r = await fetch('/scans', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({scanner_token: SCANNER_TOKEN, badge_token: token, rating, memo_text: memo})
    });
    const data = await r.json();
    if(!r.ok){ throw new Error(data.detail || 'failed'); }
    const m = data.match || {};
    const cls = m.status === 'match' ? 'pill-match'
              : m.status === 'partial' ? 'pill-partial'
              : m.status === 'needs_review' ? 'pill-needs-review' : 'pill-none';
    $('#status-pill').className = 'match-pill ' + cls;
    $('#status-pill').textContent = m.status || 'unknown';
    const a = data.attendee || {};
    $('#att-name').textContent = a.name || '(no name in roster)';
    $('#att-meta').textContent = [a.company, a.role].filter(Boolean).join(' — ');
    $('#att-explain').textContent = m.explanation || '';
    showToast('Logged');
    // Refresh stats + history after a successful scan.
    refresh();
    // Reset for next scan.
    setTimeout(()=>{ badge.value=''; $('#memo').value=''; profile.style.display='none'; pendingAttendee=null; }, 1200);
  }catch(e){ showToast(e.message, true); }
  finally{ document.querySelectorAll('.btn').forEach(b=>b.disabled=false); }
}
document.querySelectorAll('.btn').forEach(b => b.addEventListener('click', () => submit(b.dataset.rating)));

async function refresh(){
  try{
    const r = await fetch('/scans/by-sponsor/' + SPONSOR_ID);
    if(!r.ok) return;
    const data = await r.json();
    const s = data.summary || {};
    $('#k-total').textContent = s.total_scans || 0;
    $('#k-match').textContent = s.matches || 0;
    $('#k-partial').textContent = s.partial || 0;
    $('#k-strong').textContent = s.strong_fit || 0;
    const hist = $('#history');
    hist.innerHTML = '';
    (data.scans || []).slice(0, 8).forEach(s => {
      const div = document.createElement('div'); div.className='row';
      const cls = s.match_status === 'match' ? 'pill-match'
                : s.match_status === 'partial' ? 'pill-partial'
                : s.match_status === 'needs_review' ? 'pill-needs-review' : 'pill-none';
      div.innerHTML = '<div class="row-name">' + (s.attendee_id || '') + ' <span class="match-pill ' + cls + '">' + (s.match_status || '') + '</span></div>'
                    + '<div class="row-meta">' + (s.rating || '') + ' • ' + (s.scanned_at || '') + '</div>';
      hist.appendChild(div);
    });
  }catch{ /* swallow */ }
}
refresh(); setInterval(refresh, 5000);
</script></body></html>"""


@router.get("/scanner/{token}", response_class=HTMLResponse)
async def scanner_page(token: str) -> HTMLResponse:
    state = read_state()
    event = state.get("event") or {}
    try:
        payload = token_mod.verify_scanner_session(token, event)
    except token_mod.TokenError as e:
        return HTMLResponse(
            f"<h1>Scanner link unavailable</h1><p>{html.escape(str(e))}</p>"
            "<p>Ask the organizer to re-issue your booth-staff link.</p>",
            status_code=410,
        )
    sponsor = _find_sponsor(state, payload["sid"])
    sponsor_name = (sponsor or {}).get("company_name", "Sponsor")
    page = (
        _SCANNER_PAGE
        .replace("__SPONSOR__", html.escape(sponsor_name))
        .replace("__STAFF__", html.escape(payload.get("staff", "")))
        .replace("__TOKEN__", html.escape(token, quote=True))
        .replace("__SID__", html.escape(payload["sid"], quote=True))
    )
    return HTMLResponse(page)
