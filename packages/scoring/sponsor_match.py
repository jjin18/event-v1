"""Per-sponsor ICP matching for attendees. PRD §6.2.

Given a sponsor's structured ICP and an attendee profile, produce one of:

    match     — every required ICP dimension hits at least one signal
    partial   — at least one but not all dimensions hit
    none      — no dimensions hit
    needs_review — required structured data is missing on the attendee side

Every result includes a human-readable explanation that cites which signals
matched on which fields. There is no LLM here on purpose: matching must be
auditable and reproducible (PRD §6.2 "Must not: hallucinate matches").

Sponsor ICP shape (matches ``empty_sponsor()['icp']``):

    {
      "role_categories":     [str, ...],
      "seniority_bands":     [str, ...],
      "skill_signals":       [str, ...],
      "institution_signals": [str, ...],
      "behavioral_signals":  [str, ...],
      "free_text":           str,
    }

Attendee profile is the existing person dict (packages/shared/event_state).
Any of name / company / role / persona / why_relevant / notes / tags can
contribute matched signals.
"""
from __future__ import annotations

from typing import Any


# Each ICP dimension carries a weight toward the overall match decision and a
# label used in the explanation. Keep the order stable — explanations read
# top-to-bottom.
_ICP_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("role_categories", "role"),
    ("seniority_bands", "seniority"),
    ("skill_signals", "skills"),
    ("institution_signals", "institution"),
    ("behavioral_signals", "behavior"),
)


def _profile_text(person: dict[str, Any]) -> str:
    """Concatenate every profile field the matcher reads from."""
    parts: list[str] = []
    for key in ("name", "company", "role", "persona", "why_relevant", "notes", "outreach_angle"):
        v = person.get(key)
        if v:
            parts.append(str(v))
    tags = person.get("tags") or []
    if isinstance(tags, str):
        parts.append(tags)
    elif isinstance(tags, list):
        parts.extend(str(t) for t in tags)
    return " | ".join(parts).lower()


def _hits(signals: list[str], haystack: str) -> list[str]:
    """Return signals that appear (case-insensitive substring) in haystack.

    Single-word signals also match as whole-word — that's the stricter case;
    multi-word signals match as substring so "pytorch core" matches "pytorch
    core engineer".
    """
    if not signals:
        return []
    out: list[str] = []
    for raw in signals:
        s = (raw or "").strip().lower()
        if not s:
            continue
        if s in haystack:
            out.append(raw)
    return out


def _normalize_icp(icp: dict[str, Any] | None) -> dict[str, list[str]]:
    """Coerce missing/None lists to []. Dropping unknown keys silently."""
    icp = icp or {}
    out: dict[str, list[str]] = {}
    for dim, _label in _ICP_DIMENSIONS:
        v = icp.get(dim) or []
        if isinstance(v, str):
            v = [v]
        out[dim] = [str(x) for x in v if x]
    return out


def match_attendee_to_sponsor(person: dict[str, Any],
                              sponsor: dict[str, Any]) -> dict[str, Any]:
    """Match one attendee to one sponsor's ICP.

    Returns:
        {
          "match_status": "match" | "partial" | "none" | "needs_review",
          "match_explanation": str,
          "dimensions": {
            "role":        {"defined": bool, "hits": [signal, ...]},
            ...
          },
          "score": int,   # 0-100, sum of hits across dimensions, capped
        }
    """
    icp = _normalize_icp((sponsor or {}).get("icp"))
    haystack = _profile_text(person or {})

    if not haystack.strip():
        return {
            "match_status": "needs_review",
            "match_explanation": "Attendee profile is empty; cannot evaluate ICP.",
            "dimensions": {label: {"defined": bool(icp[dim]), "hits": []}
                           for dim, label in _ICP_DIMENSIONS},
            "score": 0,
        }

    dim_results: dict[str, dict[str, Any]] = {}
    defined_dims = 0
    matched_dims = 0
    for dim, label in _ICP_DIMENSIONS:
        signals = icp[dim]
        defined = bool(signals)
        hits = _hits(signals, haystack) if defined else []
        dim_results[label] = {"defined": defined, "hits": hits}
        if defined:
            defined_dims += 1
            if hits:
                matched_dims += 1

    if defined_dims == 0:
        # No structured criteria. Surface for manual review rather than
        # auto-passing — protects the sponsor from low-signal contracts.
        return {
            "match_status": "needs_review",
            "match_explanation": "Sponsor ICP has no structured criteria; needs operator review.",
            "dimensions": dim_results,
            "score": 0,
        }

    if matched_dims == defined_dims:
        status = "match"
    elif matched_dims > 0:
        status = "partial"
    else:
        status = "none"

    score = min(100, sum(20 * len(d["hits"]) for d in dim_results.values()))

    explanation = _explain(dim_results, status)

    return {
        "match_status": status,
        "match_explanation": explanation,
        "dimensions": dim_results,
        "score": score,
    }


def _explain(dim_results: dict[str, dict[str, Any]], status: str) -> str:
    parts: list[str] = []
    if status == "match":
        parts.append("Full ICP match.")
    elif status == "partial":
        parts.append("Partial ICP match.")
    elif status == "none":
        parts.append("No ICP signals hit.")
    for label, r in dim_results.items():
        if not r["defined"]:
            continue
        if r["hits"]:
            parts.append(f"{label}: hit {', '.join(r['hits'])}")
        else:
            parts.append(f"{label}: no hit")
    return " ".join(parts)


def match_all_attendees(people: list[dict[str, Any]],
                        sponsors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cross-product matching: every attendee against every sponsor.

    Returns a flat list of match-row dicts (one per non-empty result), suitable
    for storing in ``state['sponsors']['matches']`` for pre-event view. Each
    row is shaped like ``empty_sponsor_match()`` with the engine's status and
    explanation.
    """
    from packages.shared.event_state import empty_sponsor_match

    rows: list[dict[str, Any]] = []
    for person in people or []:
        aid = person.get("id") or person.get("attendee_id") or person.get("name", "")
        if not aid:
            continue
        for sponsor in sponsors or []:
            sid = sponsor.get("id")
            if not sid:
                continue
            result = match_attendee_to_sponsor(person, sponsor)
            if result["match_status"] in ("none", "needs_review"):
                continue
            row = empty_sponsor_match()
            row["sponsor_id"] = sid
            row["attendee_id"] = aid
            row["match_status"] = result["match_status"]
            row["match_explanation"] = result["match_explanation"]
            rows.append(row)
    return rows
