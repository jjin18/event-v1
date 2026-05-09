"""Sponsor roster + contract terms (PRD §5.2, §6.5, §9.2).

Sponsors are managed by the internal team in v1 — every contract is
hand-priced — so this is intentionally CRUD with no self-serve flows.

GET    /sponsors                 — list sponsors (with execution state).
POST   /sponsors                 — create a sponsor record (ICP + contract).
GET    /sponsors/{sponsor_id}    — fetch one sponsor.
PATCH  /sponsors/{sponsor_id}    — update ICP / contract / status / booth_staff.
DELETE /sponsors/{sponsor_id}    — remove (only allowed in 'draft' status).
POST   /sponsors/{sponsor_id}/staff/issue
                                 — issue a scanner-session token for a staff member.
GET    /sponsors/{sponsor_id}/match-preview
                                 — pre-event preview: ranked attendees vs ICP.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.api.routes._state import mutate_state, read_state
from packages.shared import tokens as token_mod
from packages.shared.event_state import (
    empty_contract_execution,
    empty_sponsor,
    ICP_ROLE_CATEGORIES,
    ICP_SENIORITY_BANDS,
)
from packages.scoring.sponsor_match import match_attendee_to_sponsor


router = APIRouter(tags=["sponsors"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sponsors(state: dict) -> list[dict]:
    sp = state.setdefault("sponsors", {})
    return sp.setdefault("roster", [])


def _contracts(state: dict) -> list[dict]:
    sp = state.setdefault("sponsors", {})
    return sp.setdefault("contracts", [])


def _find_sponsor(state: dict, sid: str) -> Optional[dict]:
    return next((s for s in _sponsors(state) if s.get("id") == sid), None)


def _find_contract(state: dict, sid: str) -> Optional[dict]:
    return next((c for c in _contracts(state) if c.get("sponsor_id") == sid), None)


# ---------- Request shapes ----------

class IcpBody(BaseModel):
    role_categories: Optional[list[str]] = None
    seniority_bands: Optional[list[str]] = None
    skill_signals: Optional[list[str]] = None
    institution_signals: Optional[list[str]] = None
    behavioral_signals: Optional[list[str]] = None
    free_text: Optional[str] = None


class ContractBody(BaseModel):
    base_fee: Optional[float] = Field(None, ge=0)
    per_match_fee: Optional[float] = Field(None, ge=0)
    cap: Optional[float] = Field(None, ge=0)
    match_dispute_window_days: Optional[int] = Field(None, ge=0, le=30)


class SponsorCreate(BaseModel):
    company_name: str = Field(..., min_length=1)
    contact_name: Optional[str] = ""
    contact_email: Optional[str] = ""
    icp: Optional[IcpBody] = None
    contract: Optional[ContractBody] = None


class SponsorPatch(BaseModel):
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    status: Optional[str] = None
    icp: Optional[IcpBody] = None
    contract: Optional[ContractBody] = None
    booth_staff: Optional[list[dict]] = None


def _validate_icp(icp: IcpBody) -> None:
    if icp.role_categories:
        bad = [r for r in icp.role_categories if r not in ICP_ROLE_CATEGORIES]
        if bad:
            raise HTTPException(400, f"unknown role_categories: {bad}")
    if icp.seniority_bands:
        bad = [r for r in icp.seniority_bands if r not in ICP_SENIORITY_BANDS]
        if bad:
            raise HTTPException(400, f"unknown seniority_bands: {bad}")


def _apply_icp(target: dict, src: IcpBody) -> None:
    for k in ("role_categories", "seniority_bands", "skill_signals",
              "institution_signals", "behavioral_signals"):
        v = getattr(src, k)
        if v is not None:
            target[k] = list(v)
    if src.free_text is not None:
        target["free_text"] = src.free_text


def _apply_contract(target: dict, src: ContractBody) -> None:
    for k in ("base_fee", "per_match_fee", "cap", "match_dispute_window_days"):
        v = getattr(src, k)
        if v is not None:
            target[k] = v


# ---------- list / create ----------

@router.get("/sponsors")
async def list_sponsors() -> dict:
    state = read_state()
    roster = _sponsors(state)
    contracts = _contracts(state)
    by_sid = {c.get("sponsor_id"): c for c in contracts}
    out = []
    for s in roster:
        out.append({**s, "execution": by_sid.get(s.get("id"))})
    return {"ok": True, "sponsors": out, "total": len(out)}


@router.post("/sponsors")
async def create_sponsor(body: SponsorCreate) -> dict:
    if body.icp:
        _validate_icp(body.icp)
    sid = token_mod.sponsor_id_for(body.company_name)

    def _apply(state: dict) -> dict:
        roster = _sponsors(state)
        if any(s.get("id") == sid for s in roster):
            raise HTTPException(409, f"sponsor {sid} already exists")
        sponsor = empty_sponsor()
        sponsor.update({
            "id": sid,
            "company_name": body.company_name.strip(),
            "contact_name": (body.contact_name or "").strip(),
            "contact_email": (body.contact_email or "").strip().lower(),
            "created_at": _now_iso(),
        })
        if body.icp:
            _apply_icp(sponsor["icp"], body.icp)
        if body.contract:
            _apply_contract(sponsor["contract"], body.contract)
        roster.append(sponsor)

        # Open the execution row immediately. Base fee is recorded but not
        # marked paid — payment integration is intentionally out of scope.
        execution = empty_contract_execution()
        execution.update({
            "id": f"con_{sid}",
            "sponsor_id": sid,
            "base_fee": sponsor["contract"]["base_fee"],
            "per_match_fee": sponsor["contract"]["per_match_fee"],
            "cap": sponsor["contract"]["cap"],
        })
        execution["audit_log"].append({
            "ts": _now_iso(), "actor": "system", "action": "contract_opened",
        })
        _contracts(state).append(execution)
        return {"sponsor": sponsor, "execution": execution}

    res = mutate_state(_apply)
    return {"ok": True, "sponsor": res["sponsor"], "execution": res["execution"]}


# ---------- get / patch / delete ----------

@router.get("/sponsors/{sponsor_id}")
async def get_sponsor(sponsor_id: str) -> dict:
    state = read_state()
    sponsor = _find_sponsor(state, sponsor_id)
    if not sponsor:
        raise HTTPException(404, f"sponsor {sponsor_id} not found")
    execution = _find_contract(state, sponsor_id)
    return {"ok": True, "sponsor": sponsor, "execution": execution}


@router.patch("/sponsors/{sponsor_id}")
async def patch_sponsor(sponsor_id: str, body: SponsorPatch) -> dict:
    if body.icp:
        _validate_icp(body.icp)
    if body.status and body.status not in ("draft", "active", "closed"):
        raise HTTPException(400, "status must be draft|active|closed")

    def _apply(state: dict) -> dict:
        sponsor = _find_sponsor(state, sponsor_id)
        if not sponsor:
            raise HTTPException(404, f"sponsor {sponsor_id} not found")
        if body.contact_name is not None:
            sponsor["contact_name"] = body.contact_name
        if body.contact_email is not None:
            sponsor["contact_email"] = body.contact_email.strip().lower()
        if body.status is not None:
            sponsor["status"] = body.status
        if body.icp:
            _apply_icp(sponsor["icp"], body.icp)
        if body.contract:
            _apply_contract(sponsor["contract"], body.contract)
            # Mirror contract changes into the execution row so the dashboard
            # always shows live terms.
            ex = _find_contract(state, sponsor_id)
            if ex:
                for k in ("base_fee", "per_match_fee", "cap"):
                    ex[k] = sponsor["contract"][k]
                ex["audit_log"].append({
                    "ts": _now_iso(), "actor": "system", "action": "contract_terms_updated",
                })
        if body.booth_staff is not None:
            sponsor["booth_staff"] = body.booth_staff
        return {"sponsor": sponsor}

    res = mutate_state(_apply)
    return {"ok": True, "sponsor": res["sponsor"]}


@router.delete("/sponsors/{sponsor_id}")
async def delete_sponsor(sponsor_id: str) -> dict:
    def _apply(state: dict) -> dict:
        roster = _sponsors(state)
        sponsor = next((s for s in roster if s.get("id") == sponsor_id), None)
        if not sponsor:
            raise HTTPException(404, f"sponsor {sponsor_id} not found")
        if sponsor.get("status") != "draft":
            raise HTTPException(409, "only draft sponsors can be deleted")
        roster.remove(sponsor)
        contracts = _contracts(state)
        for c in list(contracts):
            if c.get("sponsor_id") == sponsor_id:
                contracts.remove(c)
        return {"deleted": sponsor_id}

    res = mutate_state(_apply)
    return {"ok": True, "deleted": res["deleted"]}


# ---------- staff token issue ----------

class StaffIssue(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)


@router.post("/sponsors/{sponsor_id}/staff/issue")
async def issue_staff_token(sponsor_id: str, body: StaffIssue) -> dict:
    state = read_state()
    sponsor = _find_sponsor(state, sponsor_id)
    if not sponsor:
        raise HTTPException(404, f"sponsor {sponsor_id} not found")
    event = state.get("event") or {}
    event_date = state.get("event_date") or event.get("date")
    token = token_mod.issue_scanner_session(sponsor_id, body.email, event,
                                            event_date_iso=event_date)

    def _apply(s: dict) -> dict:
        sp = _find_sponsor(s, sponsor_id)
        if not sp:
            raise HTTPException(404, f"sponsor {sponsor_id} not found")
        staff = sp.setdefault("booth_staff", [])
        existing = next((x for x in staff if x.get("email", "").lower() == body.email.lower()), None)
        rec = {
            "name": body.name.strip(),
            "email": body.email.strip().lower(),
            "token_issued_at": _now_iso(),
        }
        if existing:
            existing.update(rec)
        else:
            staff.append(rec)
        return {"booth_staff": staff}

    res = mutate_state(_apply)
    return {
        "ok": True,
        "sponsor_id": sponsor_id,
        "scanner_url": f"/scanner/{token}",
        "scanner_token": token,
        "booth_staff": res["booth_staff"],
    }


# ---------- match preview ----------

@router.get("/sponsors/{sponsor_id}/match-preview")
async def match_preview(sponsor_id: str, limit: int = 50) -> dict:
    state = read_state()
    sponsor = _find_sponsor(state, sponsor_id)
    if not sponsor:
        raise HTTPException(404, f"sponsor {sponsor_id} not found")
    ranked = (state.get("people") or {}).get("ranked_prospects", []) or []
    rows = []
    for person in ranked:
        result = match_attendee_to_sponsor(person, sponsor)
        if result["match_status"] in ("none", "needs_review"):
            continue
        rows.append({
            "attendee_id": token_mod.attendee_id_for(person.get("name", ""), person.get("email", "")),
            "name": person.get("name"),
            "company": person.get("company"),
            "role": person.get("role"),
            "match_status": result["match_status"],
            "match_explanation": result["match_explanation"],
            "score": result["score"],
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    rows = rows[:limit]
    full = sum(1 for r in rows if r["match_status"] == "match")
    partial = sum(1 for r in rows if r["match_status"] == "partial")
    return {
        "ok": True,
        "sponsor_id": sponsor_id,
        "total": len(rows),
        "full_matches": full,
        "partial_matches": partial,
        "matches": rows,
    }
