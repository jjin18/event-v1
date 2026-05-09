"""Contract execution (PRD §5.8, §6.5).

Closes out a sponsor's contract after the event:

  1. Aggregates booth scans by attendee, building one verified-match row per
     (sponsor, attendee) where status ∈ {match, partial}.
  2. Skips scans flagged ``status_reviewed == 'rejected'`` (dispute path).
  3. Computes the invoice: base_fee + per_match_fee × verified_count, capped
     at the sponsor's contract cap.
  4. Writes the result back to the contract execution row and returns it.

Payment integration (Stripe) is intentionally not wired here — the PRD calls
it out as needed but it's a separate concern requiring real account setup.
What we do is produce the final invoice number, lock the verified-match list,
and stamp the audit log. A downstream payments worker can pick up rows where
``payment_status == 'finalized'`` to actually charge.

GET    /contracts/{sponsor_id}            — current contract execution state.
POST   /contracts/{sponsor_id}/execute    — close out + compute invoice.
POST   /contracts/{sponsor_id}/dispute    — flag a scan as disputed pre-execute.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.api.routes._state import mutate_state, read_state
from packages.shared.event_state import (
    empty_contract_execution,
    empty_sponsor_match,
)


router = APIRouter(tags=["contracts"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_sponsor(state: dict, sid: str) -> Optional[dict]:
    return next((s for s in (state.get("sponsors") or {}).get("roster", []) if s.get("id") == sid), None)


def _find_contract(state: dict, sid: str) -> dict:
    contracts = state.setdefault("sponsors", {}).setdefault("contracts", [])
    ex = next((c for c in contracts if c.get("sponsor_id") == sid), None)
    if ex is None:
        ex = empty_contract_execution()
        ex["id"] = f"con_{sid}"
        ex["sponsor_id"] = sid
        contracts.append(ex)
    return ex


def _scans_for(state: dict, sid: str) -> list[dict]:
    return [s for s in (state.get("sponsors") or {}).get("scans", []) if s.get("sponsor_id") == sid]


# ---------- GET ----------

@router.get("/contracts/{sponsor_id}")
async def get_contract(sponsor_id: str) -> dict:
    state = read_state()
    sponsor = _find_sponsor(state, sponsor_id)
    if not sponsor:
        raise HTTPException(404, f"sponsor {sponsor_id} not found")
    ex = _find_contract(state, sponsor_id)
    return {"ok": True, "sponsor_id": sponsor_id, "execution": ex}


# ---------- POST execute ----------

class ExecuteBody(BaseModel):
    actor: Optional[str] = Field("operator", description="Who is closing out this contract.")


@router.post("/contracts/{sponsor_id}/execute")
async def execute_contract(sponsor_id: str, body: ExecuteBody) -> dict:
    def _apply(state: dict) -> dict:
        sponsor = _find_sponsor(state, sponsor_id)
        if not sponsor:
            raise HTTPException(404, f"sponsor {sponsor_id} not found")
        contract_terms = sponsor.get("contract", {}) or {}
        ex = _find_contract(state, sponsor_id)

        if ex.get("payment_status") == "finalized":
            raise HTTPException(409, "contract already finalized")

        scans = _scans_for(state, sponsor_id)

        # Group scans by attendee. The attendee's "best" scan wins:
        # match > partial > anything else; ties broken by latest scan.
        rank_order = {"match": 3, "partial": 2, "needs_review": 1}
        by_attendee: dict[str, dict] = {}
        scan_ids_by_attendee: dict[str, list[str]] = {}
        for s in scans:
            if s.get("status_reviewed") == "rejected":
                continue
            aid = s.get("attendee_id")
            if not aid:
                continue
            scan_ids_by_attendee.setdefault(aid, []).append(s.get("id", ""))
            best = by_attendee.get(aid)
            if best is None:
                by_attendee[aid] = s
                continue
            cur_rank = rank_order.get(s.get("match_status", ""), 0)
            best_rank = rank_order.get(best.get("match_status", ""), 0)
            if cur_rank > best_rank or (cur_rank == best_rank and s.get("scanned_at", "") > best.get("scanned_at", "")):
                by_attendee[aid] = s

        verified: list[dict] = []
        for aid, s in by_attendee.items():
            if s.get("match_status") not in ("match", "partial"):
                continue
            row = empty_sponsor_match()
            row.update({
                "id": f"match_{sponsor_id}_{aid}",
                "sponsor_id": sponsor_id,
                "attendee_id": aid,
                "match_status": s.get("match_status"),
                "match_explanation": s.get("match_explanation", ""),
                "scan_ids": scan_ids_by_attendee.get(aid, []),
                "rating": s.get("rating", ""),
                "memo_text": s.get("memo_text", ""),
                "verified_at": _now_iso(),
                "billable": s.get("match_status") == "match",  # partials surfaced but not billed
            })
            verified.append(row)

        # Persist verified matches (replace any prior snapshot for this sponsor).
        all_matches = state.setdefault("sponsors", {}).setdefault("matches", [])
        state["sponsors"]["matches"] = [m for m in all_matches if m.get("sponsor_id") != sponsor_id] + verified

        billable_count = sum(1 for m in verified if m["billable"])
        base_fee = float(contract_terms.get("base_fee", 0) or 0)
        per_match_fee = float(contract_terms.get("per_match_fee", 0) or 0)
        cap = float(contract_terms.get("cap", 0) or 0)
        gross = base_fee + (billable_count * per_match_fee)
        invoice = min(gross, cap) if cap > 0 else gross

        ex["base_fee"] = base_fee
        ex["per_match_fee"] = per_match_fee
        ex["cap"] = cap
        ex["verified_match_count"] = billable_count
        ex["final_invoice_amount"] = invoice
        ex["payment_status"] = "finalized"
        ex["executed_at"] = _now_iso()
        ex.setdefault("audit_log", []).append({
            "ts": _now_iso(),
            "actor": body.actor or "operator",
            "action": "contract_executed",
            "verified_match_count": billable_count,
            "invoice": invoice,
            "scans_considered": len(scans),
        })
        return {"execution": ex, "verified": verified}

    res = mutate_state(_apply)
    return {
        "ok": True,
        "sponsor_id": sponsor_id,
        "execution": res["execution"],
        "verified_matches": res["verified"],
    }


# ---------- POST dispute ----------

class DisputeBody(BaseModel):
    scan_id: str = Field(..., min_length=1)
    decision: str = Field(..., description="confirmed | rejected")
    reason: Optional[str] = ""


@router.post("/contracts/{sponsor_id}/dispute")
async def dispute_scan(sponsor_id: str, body: DisputeBody) -> dict:
    if body.decision not in ("confirmed", "rejected"):
        raise HTTPException(400, "decision must be 'confirmed' or 'rejected'")

    def _apply(state: dict) -> dict:
        sponsor = _find_sponsor(state, sponsor_id)
        if not sponsor:
            raise HTTPException(404, f"sponsor {sponsor_id} not found")
        scans = (state.get("sponsors") or {}).get("scans", [])
        scan = next((s for s in scans if s.get("id") == body.scan_id and s.get("sponsor_id") == sponsor_id), None)
        if not scan:
            raise HTTPException(404, f"scan {body.scan_id} not found for sponsor {sponsor_id}")
        scan["status_reviewed"] = body.decision
        ex = _find_contract(state, sponsor_id)
        ex.setdefault("audit_log", []).append({
            "ts": _now_iso(),
            "actor": "operator",
            "action": f"scan_{body.decision}",
            "scan_id": body.scan_id,
            "reason": body.reason or "",
        })
        return {"scan": scan, "execution": ex}

    res = mutate_state(_apply)
    return {"ok": True, "scan": res["scan"], "execution": res["execution"]}
