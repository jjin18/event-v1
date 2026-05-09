"""Canonical shared event state schema for OneLoop.

This module defines the contract between the Eventful branch and the
Agentic Ops branch. Both branches read/write `data/event_state.json` using this
shape. Keep additions backward-compatible: prefer adding new optional keys over
renaming existing ones.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import json
from pathlib import Path


# ---------- Person / prospect ----------

PERSON_CSV_COLUMNS: list[str] = [
    "name",
    "company",
    "role",
    "linkedin_url",
    "email",
    "source",
    "persona",
    "why_relevant",
    "fit_score",
    "priority",
    "outreach_angle",
    "status",
    "tags",
    "notes",
]


def empty_person() -> dict[str, Any]:
    return {
        "name": "",
        "company": "",
        "role": "",
        "linkedin_url": "",
        "email": "",
        "source": "",
        "persona": "",
        "why_relevant": "",
        "fit_score": None,
        "priority": "",
        "outreach_angle": "",
        "status": "not_contacted",
        "tags": [],
        "notes": "",
    }


# ---------- Sub-section dataclasses ----------

@dataclass
class EventInfo:
    # goal = overall success intent; format = event kind; desired_attendees = who belongs in the room
    name: str = ""
    goal: str = ""
    desired_attendees: str = ""
    city: str = ""
    date: str = ""
    target_size: int = 100
    format: str = ""
    success_metrics: list[str] = field(default_factory=list)


@dataclass
class Intelligence:
    audience_icp: list[dict] = field(default_factory=list)
    avoid_personas: list[dict] = field(default_factory=list)
    sourcing_strategy: list[dict] = field(default_factory=list)
    scoring_rubric: dict = field(default_factory=dict)
    room_balance: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class People:
    prospects: list[dict] = field(default_factory=list)
    ranked_prospects: list[dict] = field(default_factory=list)
    approved: list[dict] = field(default_factory=list)
    waitlist: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


@dataclass
class Ops:
    workstreams: list[dict] = field(default_factory=list)
    outreach_queue: list[dict] = field(default_factory=list)
    rsvp_tracker: list[dict] = field(default_factory=list)
    retention_plan: list[dict] = field(default_factory=list)
    basic_ops_checklist: list[dict] = field(default_factory=list)


@dataclass
class Venues:
    requirements: dict = field(default_factory=dict)
    pipeline: list[dict] = field(default_factory=list)


@dataclass
class Sponsors:
    partner_icp: list[dict] = field(default_factory=list)
    pipeline: list[dict] = field(default_factory=list)
    # PRD §5.2 — sponsor records with structured ICP + contract terms.
    # Each entry is a Sponsor dict (see ``empty_sponsor``); flat list keyed by id.
    roster: list[dict] = field(default_factory=list)
    # PRD §5.6 — booth scans logged at the event. One row per scan attempt.
    scans: list[dict] = field(default_factory=list)
    # PRD §5.6/§5.8 — verified sponsor↔attendee matches (computed from scans
    # plus pre-event ICP matching). Persisted so contract execution and the
    # post-event packet can read a stable snapshot.
    matches: list[dict] = field(default_factory=list)
    # PRD §5.8 — contract execution state per (sponsor, event). One row per
    # sponsor; updated as base fee accrues and per-match accruals are locked.
    contracts: list[dict] = field(default_factory=list)
    # PRD §5.9 — outcome tracking entries logged at +14/+30/+60/+90 days.
    outcomes: list[dict] = field(default_factory=list)


# ---------- Sponsor / Scan / Match / Contract / Outcome shapes ----------
#
# These mirror the PRD data model (§7.2) but live as plain dicts so they fit
# the existing JSON-on-disk storage pattern. Helper factories give every
# consumer a known-good shape to work from.

# Allowed values for a sponsor ICP definition (PRD §6.2).
ICP_ROLE_CATEGORIES: tuple[str, ...] = (
    "engineer", "designer", "founder", "researcher", "student", "other",
)
ICP_SENIORITY_BANDS: tuple[str, ...] = (
    "intern", "junior", "mid", "senior", "lead",
    "freshman", "sophomore", "junior_year", "senior_year", "grad",
)


def empty_sponsor() -> dict[str, Any]:
    """Sponsor record. PRD §5.2.

    The ICP block is the structured criterion the matching engine reads
    (packages/scoring/sponsor_match). Contract terms are the contingent
    structure (PRD §9.2): base fee + per-match fee × verified-match count,
    capped at ``cap``.
    """
    return {
        "id": "",
        "company_name": "",
        "contact_name": "",
        "contact_email": "",
        "status": "draft",   # draft | active | closed
        # Structured ICP (PRD §6.2). All fields optional; matcher uses what's there.
        "icp": {
            "role_categories": [],         # subset of ICP_ROLE_CATEGORIES
            "seniority_bands": [],         # subset of ICP_SENIORITY_BANDS
            "skill_signals": [],           # free-text signals (e.g. "pytorch", "rust")
            "institution_signals": [],     # e.g. ["MIT", "CMU", "top-30"]
            "behavioral_signals": [],      # e.g. ["shipped open source", "hackathon winner"]
            "free_text": "",               # operator's note, surfaced to sponsors
        },
        # Contract terms (PRD §9.2). Currency = USD.
        "contract": {
            "base_fee": 0.0,
            "per_match_fee": 0.0,
            "cap": 0.0,
            "match_dispute_window_days": 7,
            "signed_at": None,
        },
        # Booth staff allowed to use the scanner. Each entry: {name, email, token_issued_at}.
        "booth_staff": [],
        "created_at": "",
    }


def empty_scan() -> dict[str, Any]:
    """Booth scan event. PRD §5.6.

    ``match_status`` is auto-computed at scan time from sponsor.icp; the
    sponsor lead can flip ``status_reviewed`` post-event during the dispute
    window. ``rating`` is the booth-staff one-tap label.
    """
    return {
        "id": "",
        "sponsor_id": "",
        "attendee_id": "",
        "booth_staff_email": "",
        "scanned_at": "",
        "rating": "",                   # strong_fit | some_interest | not_a_match
        "match_status": "",             # match | partial | none | needs_review
        "match_explanation": "",        # human-readable cite of profile facts
        "memo_text": "",
        "memo_audio_url": "",           # populated post-event if voice memos enabled
        "status_reviewed": "",          # pending | confirmed | disputed | rejected
    }


def empty_sponsor_match() -> dict[str, Any]:
    """Verified match snapshot. PRD §5.8.

    Created when contract is executed: aggregates scan(s) + ICP match into a
    single billable row per (sponsor, attendee).
    """
    return {
        "id": "",
        "sponsor_id": "",
        "attendee_id": "",
        "match_status": "",             # match | partial
        "match_explanation": "",
        "scan_ids": [],
        "rating": "",
        "memo_text": "",
        "verified_at": "",
        "billable": True,
    }


def empty_contract_execution() -> dict[str, Any]:
    """Contract execution state. PRD §5.8 / §9.2.

    Created at sponsor signup with base_fee charged; finalised at close-out
    after the dispute window with the final invoice amount.
    """
    return {
        "id": "",
        "sponsor_id": "",
        "base_fee": 0.0,
        "per_match_fee": 0.0,
        "cap": 0.0,
        "verified_match_count": 0,
        "final_invoice_amount": 0.0,
        "payment_status": "pending",    # pending | base_paid | finalized | disputed
        "executed_at": "",
        "audit_log": [],                # list of {ts, actor, action} entries
    }


def empty_outcome() -> dict[str, Any]:
    """Sponsor outcome row. PRD §5.9.

    One row per (sponsor, attendee). status moves through the funnel; history
    keeps the trail so the +30/+60/+90 cadence can be reconstructed.
    """
    return {
        "id": "",
        "sponsor_id": "",
        "attendee_id": "",
        "status": "no_follow_up",       # no_follow_up | contacted | interviewing | offered | hired | declined
        "role": "",
        "salary_range": "",
        "notes": "",
        "captured_via": "sponsor_report",  # sponsor_report | attendee_report | signal_inference
        "captured_at": "",
        "history": [],                  # list of {ts, status, notes, captured_via}
    }


@dataclass
class LastAgentRun:
    agent_name: str = ""
    timestamp: str = ""
    summary: str = ""
    run_id: str = ""


@dataclass
class StateMeta:
    open_questions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    approval_queue: list[dict] = field(default_factory=list)
    activity_log: list[dict] = field(default_factory=list)
    last_agent_run: LastAgentRun = field(default_factory=LastAgentRun)


@dataclass
class Visibility:
    latest_summary_files: list[str] = field(default_factory=list)
    latest_trace_file: str = "logs/agent_runs.jsonl"
    latest_activity_log: str = "docs/agent_activity_log.md"


# Pre-populated category names for the Budget tab. Five fixed categories per spec.
BUDGET_CATEGORIES: list[str] = ["Venue", "Food", "A/V", "Marketing", "Other"]


@dataclass
class Budget:
    total_budget: float = 0.0
    sponsor_income: float = 0.0
    # Flat list keyed by id; each item has category, name, cost (number), cost_text
    # (raw quote string when sourced from Org), status, source ("manual"|"org_shortlist"),
    # source_ref (vendor name when auto-filled).
    line_items: list[dict] = field(default_factory=list)


# Header fields tracked for provenance ("manual" vs "extracted").
# Keys are flat names; values live in their existing locations
# (event.name / event.city / event.format / event.target_size /
# event_date / event_end_time) so agents continue reading the same
# paths they always have.
TRACKED_HEADER_FIELDS: tuple[str, ...] = (
    "name", "city", "format", "target_size", "event_date", "event_end_time",
    "total_budget",
)


@dataclass
class EventState:
    event: EventInfo = field(default_factory=EventInfo)
    intelligence: Intelligence = field(default_factory=Intelligence)
    people: People = field(default_factory=People)
    ops: Ops = field(default_factory=Ops)
    venues: Venues = field(default_factory=Venues)
    sponsors: Sponsors = field(default_factory=Sponsors)
    state: StateMeta = field(default_factory=StateMeta)
    visibility: Visibility = field(default_factory=Visibility)
    # Eventful platform extensions (date anchor, budget tab, attendees tab).
    # New top-level keys per spec — existing keys above are untouched.
    event_date: str = ""              # ISO 8601 date or datetime
    event_end_time: Optional[str] = None  # ISO 8601 datetime, nullable
    budget: Budget = field(default_factory=Budget)
    attendees: list[dict] = field(default_factory=list)
    # Provenance of each header field: "manual" | "extracted" | absent.
    # Manual values are sticky — re-running the pipeline leaves them alone.
    event_field_sources: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------- IO helpers ----------

def empty_event_state() -> dict[str, Any]:
    return EventState().to_dict()


def load_event_state(path: str | Path) -> dict[str, Any]:
    """Load event_state.json, or return an empty state if it doesn't exist."""
    p = Path(path)
    if not p.exists():
        return empty_event_state()
    with p.open("r") as f:
        data = json.load(f)
    # merge with empty defaults so missing keys don't break consumers
    return _deep_merge(empty_event_state(), data)


def save_event_state(path: str | Path, state: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        json.dump(state, f, indent=2, default=str)


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
