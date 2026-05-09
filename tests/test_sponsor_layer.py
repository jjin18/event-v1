"""Smoke tests for the sponsor measurement layer (PRD §5–§6).

Covers the lifecycle: create sponsor → issue scanner session → log scan →
execute contract → fetch packet → log outcome. Uses an isolated event_state
file per test (monkeypatch on the module-level EVENT_STATE_PATH), so tests
don't read or write the dev data directory.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from packages.scoring.sponsor_match import match_attendee_to_sponsor
from packages.shared import tokens as token_mod
from packages.shared.event_state import (
    empty_event_state,
    empty_sponsor,
    save_event_state,
)


@pytest.fixture
def isolated_state(tmp_path: Path, monkeypatch):
    """Redirect the API's event_state path to a clean file per test."""
    state_path = tmp_path / "event_state.json"
    save_event_state(state_path, empty_event_state())
    # Routes import EVENT_STATE_PATH from _state at module load; patch the
    # symbol on the routes module after they imported it too.
    from apps.api.routes import _state as state_mod
    monkeypatch.setattr(state_mod, "EVENT_STATE_PATH", state_path)
    # Force CONFIRM_TOKEN_SECRET so tokens are deterministic across the test.
    monkeypatch.setenv("CONFIRM_TOKEN_SECRET", "test-secret-please-ignore")
    return state_path


@pytest.fixture
def client(isolated_state: Path):
    from apps.api.main import app
    return TestClient(app)


# ---------- pure matcher ----------

def test_sponsor_match_full_signal():
    sponsor = empty_sponsor()
    sponsor["icp"] = {
        "role_categories": ["engineer"],
        "seniority_bands": ["senior_year"],
        "skill_signals": ["pytorch"],
        "institution_signals": ["MIT"],
        "behavioral_signals": [],
        "free_text": "",
    }
    person = {
        "name": "Avery K", "company": "MIT", "role": "senior_year CS engineer",
        "why_relevant": "ships pytorch projects",
    }
    res = match_attendee_to_sponsor(person, sponsor)
    assert res["match_status"] == "match"
    assert "MIT" in res["match_explanation"]
    assert res["score"] > 0


def test_sponsor_match_partial():
    sponsor = empty_sponsor()
    sponsor["icp"]["role_categories"] = ["engineer"]
    sponsor["icp"]["skill_signals"] = ["rust"]
    person = {"role": "junior engineer at small startup", "why_relevant": "python only"}
    res = match_attendee_to_sponsor(person, sponsor)
    assert res["match_status"] == "partial"


def test_sponsor_match_needs_review_when_icp_empty():
    sponsor = empty_sponsor()
    person = {"name": "anyone"}
    res = match_attendee_to_sponsor(person, sponsor)
    assert res["match_status"] == "needs_review"


# ---------- end-to-end HTTP ----------

def test_create_sponsor_and_match_preview(client):
    body = {
        "company_name": "AI Taco",
        "icp": {
            "role_categories": ["engineer"],
            "skill_signals": ["pytorch"],
            "institution_signals": ["MIT"],
        },
        "contract": {"base_fee": 5000, "per_match_fee": 1500, "cap": 20000},
    }
    r = client.post("/sponsors", json=body)
    assert r.status_code == 200, r.text
    sid = r.json()["sponsor"]["id"]

    # Listing reflects what we created
    r = client.get("/sponsors")
    assert r.status_code == 200
    assert any(s["id"] == sid for s in r.json()["sponsors"])

    # Match preview tolerates an empty ranked-prospects list
    r = client.get(f"/sponsors/{sid}/match-preview")
    assert r.status_code == 200
    assert r.json()["matches"] == []


def test_scanner_session_and_scan_log(client, isolated_state):
    # 1. Create sponsor with a clear ICP.
    sponsor_body = {
        "company_name": "AI Taco",
        "icp": {"role_categories": ["engineer"], "skill_signals": ["pytorch"]},
        "contract": {"base_fee": 5000, "per_match_fee": 1500, "cap": 10000},
    }
    sid = client.post("/sponsors", json=sponsor_body).json()["sponsor"]["id"]

    # 2. Add an attendee + seed a matching ranked prospect so the scanner can
    #    resolve the badge.
    name = "Avery K"
    email = "avery@example.edu"
    aid = token_mod.attendee_id_for(name, email)
    add = client.post("/attendees", json={"name": name, "email": email, "company": "MIT"})
    assert add.status_code == 200, add.text
    # Seed ranked_prospects so match resolution finds skill signals.
    from apps.api.routes._state import mutate_state
    def _seed(state):
        state.setdefault("people", {})["ranked_prospects"] = [{
            "name": name, "email": email, "company": "MIT",
            "role": "engineer", "why_relevant": "ships pytorch projects",
        }]
        return None
    mutate_state(_seed)

    # 3. Issue a scanner session for booth staff.
    r = client.post(f"/sponsors/{sid}/staff/issue", json={"name": "Booth Lead", "email": "lead@aitaco.com"})
    assert r.status_code == 200, r.text
    scanner_token = r.json()["scanner_token"]

    # 4. Issue a badge token for the attendee.
    r = client.get(f"/attendees/{aid}/badge")
    assert r.status_code == 200, r.text
    badge_token = r.json()["badge_token"]

    # 5. Log a scan.
    r = client.post("/scans", json={
        "scanner_token": scanner_token,
        "badge_token": badge_token,
        "rating": "strong_fit",
        "memo_text": "Built a PyTorch eval suite over the weekend.",
    })
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["match"]["status"] == "match"
    assert payload["summary"]["total_scans"] == 1
    assert payload["summary"]["matches"] == 1


def test_contract_execution_caps_invoice(client):
    sid = client.post("/sponsors", json={
        "company_name": "AI Taco",
        "icp": {"role_categories": ["engineer"], "skill_signals": ["pytorch"]},
        "contract": {"base_fee": 5000, "per_match_fee": 5000, "cap": 12000},
    }).json()["sponsor"]["id"]

    # Manually inject 5 verified matches via direct state mutation. Each
    # billable adds $5k → gross $30k, capped at $12k.
    from apps.api.routes._state import mutate_state
    from packages.shared.event_state import empty_scan
    def _seed(state):
        scans = state.setdefault("sponsors", {}).setdefault("scans", [])
        for i in range(5):
            s = empty_scan()
            s.update({
                "id": f"scn_test_{i}",
                "sponsor_id": sid,
                "attendee_id": f"att_test_{i}",
                "match_status": "match",
                "rating": "strong_fit",
                "scanned_at": f"2026-05-09T10:0{i}:00+00:00",
            })
            scans.append(s)
        return None
    mutate_state(_seed)

    r = client.post(f"/contracts/{sid}/execute", json={"actor": "tests"})
    assert r.status_code == 200, r.text
    ex = r.json()["execution"]
    assert ex["verified_match_count"] == 5
    assert ex["final_invoice_amount"] == 12000  # cap applied
    assert ex["payment_status"] == "finalized"

    # Idempotency: re-execute is rejected.
    r = client.post(f"/contracts/{sid}/execute", json={"actor": "tests"})
    assert r.status_code == 409


def test_packet_renders_after_execute(client):
    sid = client.post("/sponsors", json={
        "company_name": "AI Taco",
        "icp": {"role_categories": ["engineer"]},
        "contract": {"base_fee": 1000, "per_match_fee": 1000, "cap": 5000},
    }).json()["sponsor"]["id"]

    from apps.api.routes._state import mutate_state
    from packages.shared.event_state import empty_scan
    def _seed(state):
        scans = state.setdefault("sponsors", {}).setdefault("scans", [])
        s = empty_scan()
        s.update({
            "id": "scn_test_pack", "sponsor_id": sid, "attendee_id": "att_X",
            "match_status": "match", "rating": "strong_fit",
            "memo_text": "Great chat.", "scanned_at": "2026-05-09T10:00:00+00:00",
        })
        scans.append(s)
        state.setdefault("attendees", []).append({
            "id": "att_X", "name": "Avery K", "company": "MIT",
            "role": "engineer", "status": "Attended",
        })
        return None
    mutate_state(_seed)

    client.post(f"/contracts/{sid}/execute", json={"actor": "tests"})

    r = client.get(f"/packets/{sid}.json")
    assert r.status_code == 200, r.text
    pkt = r.json()["packet"]
    assert pkt["summary"]["billable"] == 1
    assert pkt["matches"][0]["person"]["name"] == "Avery K"
    assert "follow_up_draft" in pkt["matches"][0]

    r = client.get(f"/packets/{sid}")
    assert r.status_code == 200
    assert "AI Taco" in r.text


def test_outcomes_funnel(client):
    sid = client.post("/sponsors", json={
        "company_name": "AI Taco",
        "contract": {"base_fee": 1000, "per_match_fee": 1000, "cap": 5000},
    }).json()["sponsor"]["id"]

    aid = "att_test_outcomes"
    r = client.post(f"/outcomes/{sid}/log", json={"attendee_id": aid, "status": "contacted"})
    assert r.status_code == 200
    r = client.post(f"/outcomes/{sid}/log", json={"attendee_id": aid, "status": "interviewing"})
    assert r.status_code == 200
    r = client.post(f"/outcomes/{sid}/log", json={"attendee_id": aid, "status": "hired",
                                                  "role": "ML Engineer", "salary_range": "$140-160k"})
    assert r.status_code == 200
    payload = r.json()
    assert payload["outcome"]["status"] == "hired"
    assert payload["funnel"]["hired"] == 1

    # CSV export round-trips.
    r = client.get(f"/outcomes/{sid}/export.csv")
    assert r.status_code == 200
    assert "hired" in r.text
    assert "ML Engineer" in r.text


def test_composition_page_reflects_confirmed(client, isolated_state):
    # Add three attendees, two confirmed.
    for nm, em, status in [
        ("A K", "a@x.edu", "Confirmed"),
        ("B L", "b@x.edu", "Confirmed"),
        ("C M", "c@x.edu", "Invited"),
    ]:
        client.post("/attendees", json={"name": nm, "email": em})
        aid = token_mod.attendee_id_for(nm, em)
        client.patch(f"/attendees/{aid}", json={"status": status})

    # Resolve the event_id (eid) from the current state — it's a hash of
    # event.name + event.format, both empty here.
    from apps.api.routes._state import read_state
    state = read_state()
    eid = token_mod.event_id_for(state.get("event") or {})

    r = client.get(f"/composition/{eid}.json")
    assert r.status_code == 200, r.text
    comp = r.json()["composition"]
    assert comp["confirmed_count"] == 2
