"""Generate human-readable rationales for top-K matches.

LAZY by design — only runs on matches that will actually be shown. For 1,100
people × top-5 each = 5,500 displayed matches, but symmetric pairs share a
rationale so ~2,750 unique Claude calls. At Haiku rates that's ~$5 per event.

Cached by canonicalized pair id so re-runs are free.

Usage:
    from packages.explain import explain_matches
    explanations = await explain_matches(matrix, enriched_people, rubric, top_k=5)
    # → {pair_key: {"rationale": "...", "intro_message": "..."}}
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from anthropic import AsyncAnthropic

from packages.schema import EnrichedPerson
from packages.shared import cache as _cache


MODEL = os.environ.get("EXPLAIN_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = 600
PROMPT_PATH = Path("prompts/explain_match.md")
CACHE_NAMESPACE = "rationale"
CACHE_VERSION = "v1"


# ---- Pair key (canonical, order-independent) ----

def _pair_key(a_id: str, b_id: str) -> str:
    a, b = sorted([a_id, b_id])
    return f"{a}__{b}"


# ---- Cache ----

def _read_cache(key: str) -> Optional[dict[str, Any]]:
    return _cache.get(CACHE_NAMESPACE, CACHE_VERSION, MODEL, key)


def _write_cache(key: str, data: dict[str, Any]) -> None:
    _cache.put(CACHE_NAMESPACE, data, CACHE_VERSION, MODEL, key)


# ---- Prompt building ----

def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text()


def _short_list(items: Optional[list[Any]], limit: int = 6) -> str:
    if not items:
        return "(none)"
    out = [str(x) for x in items[:limit]]
    return ", ".join(out)


def _short_roles(roles: list[dict] | None) -> str:
    if not roles:
        return "(none)"
    parts = []
    for r in roles[:4]:
        title = (r or {}).get("title", "")
        company = (r or {}).get("company", "")
        years = (r or {}).get("years", "")
        if title or company:
            parts.append(f"{title} @ {company}".strip(" @") + (f" ({years})" if years else ""))
    return "; ".join(parts) or "(none)"


def _top_drivers(components: dict[str, float], n: int = 3) -> str:
    items = sorted(components.items(), key=lambda kv: kv[1], reverse=True)
    return ", ".join(f"{k}={v}" for k, v in items[:n] if v > 0) or "(all low)"


def _build_prompt(
    a: EnrichedPerson,
    b: EnrichedPerson,
    pair: dict[str, Any],
    rubric: dict[str, Any],
) -> str:
    template = _load_prompt_template()
    subs = {
        "{event_name}": rubric.get("_event_name", "(event)"),
        "{event_type}": rubric.get("event_type", "event"),
        "{match_intent}": rubric.get("match_intent", "mixed"),

        "{a_name}": a.name,
        "{a_role}": (a.role or a.title or "(unknown)"),
        "{a_ticket_type}": a.ticket_type,
        "{a_company}": a.company or "(unknown)",
        "{a_city}": a.city or "(unknown)",
        "{a_bio}": a.bio_text[:600] or "(empty)",
        "{a_domains}": _short_list(a.domains),
        "{a_tech}": _short_list(a.tech_stack),
        "{a_conviction}": _short_list(a.conviction_themes, 4),
        "{a_mentor}": _short_list(a.mentor_signals, 4),
        "{a_asks}": _short_list(a.explicit_asks, 4),
        "{a_past}": _short_roles(a.roles_history),

        "{b_name}": b.name,
        "{b_role}": (b.role or b.title or "(unknown)"),
        "{b_ticket_type}": b.ticket_type,
        "{b_company}": b.company or "(unknown)",
        "{b_city}": b.city or "(unknown)",
        "{b_bio}": b.bio_text[:600] or "(empty)",
        "{b_domains}": _short_list(b.domains),
        "{b_tech}": _short_list(b.tech_stack),
        "{b_conviction}": _short_list(b.conviction_themes, 4),
        "{b_mentor}": _short_list(b.mentor_signals, 4),
        "{b_asks}": _short_list(b.explicit_asks, 4),
        "{b_past}": _short_roles(b.roles_history),

        "{composite}": str(pair["composite"]),
        "{similar}": str(pair["similar_score"]),
        "{complementary}": str(pair["complementary_score"]),
        "{top_similar}": _top_drivers(pair["components"]["similar"]),
        "{top_complement}": _top_drivers(pair["components"]["complementary"]),
        "{mutual}": "true" if pair.get("mutual") else "false",
    }
    # Replace personB schema-block placeholders (template uses {b_*})
    out = template
    for k, v in subs.items():
        out = out.replace(k, str(v))
    # Inject the PERSON B block details (template just says "same fields as A")
    person_b_block = (
        f"Name:           {b.name}\n"
        f"Role:           {b.role or b.title or '(unknown)'}  ({b.ticket_type})\n"
        f"Company:        {b.company or '(unknown)'}\n"
        f"City:           {b.city or '(unknown)'}\n"
        f"Bio:            {(b.bio_text or '(empty)')[:600]}\n"
        f"Domains:        {_short_list(b.domains)}\n"
        f"Tech stack:     {_short_list(b.tech_stack)}\n"
        f"Conviction:     {_short_list(b.conviction_themes, 4)}\n"
        f"Mentor signals: {_short_list(b.mentor_signals, 4)}\n"
        f"Explicit asks:  {_short_list(b.explicit_asks, 4)}\n"
        f"Past:           {_short_roles(b.roles_history)}"
    )
    out = out.replace("(same fields as A)", person_b_block)
    return out


# ---- JSON extraction ----

def _extract_json(text: str) -> Optional[dict[str, Any]]:
    text = text.strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


# ---- LLM call ----

async def _explain_one(
    a: EnrichedPerson,
    b: EnrichedPerson,
    pair: dict[str, Any],
    rubric: dict[str, Any],
    client: AsyncAnthropic,
) -> dict[str, Any]:
    prompt = _build_prompt(a, b, pair, rubric)
    try:
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return {"rationale": "", "intro_message": "", "error": repr(e)}

    text = "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    parsed = _extract_json(text)
    if not parsed:
        return {"rationale": text.strip()[:400], "intro_message": "", "parse_failed": True}
    return {
        "rationale": parsed.get("rationale", "").strip(),
        "intro_message": parsed.get("intro_message", "").strip(),
    }


# ---- Batch orchestration ----

ProgressCallback = Callable[[str, str, dict[str, Any]], Awaitable[None]]


async def explain_matches(
    matrix: dict[str, Any],
    people_by_id: dict[str, EnrichedPerson],
    rubric: dict[str, Any],
    *,
    top_k: int = 5,
    concurrency: int = 20,
    use_cache: bool = True,
    on_progress: Optional[ProgressCallback] = None,
) -> dict[str, dict[str, Any]]:
    """Generate rationales for every unique pair appearing in top_k_per_person.

    Returns {pair_key: {rationale, intro_message}}.

    Symmetric: pair_key is sorted(a_id, b_id) so each pair only generated once.
    Mutates the matrix in-place to attach `rationale` + `intro_message` per
    pair record AND per top_k entry.
    """
    # Collect unique pairs we actually need to explain
    needed: dict[str, dict[str, Any]] = {}
    for pid, matches in matrix.get("top_k_per_person", {}).items():
        for m in matches[:top_k]:
            key = _pair_key(pid, m["other_id"])
            if key in needed:
                continue
            # Find the corresponding pair record
            pair_record = None
            for p in matrix.get("pairs", []):
                if _pair_key(p["a_id"], p["b_id"]) == key:
                    pair_record = p
                    break
            if not pair_record:
                continue
            needed[key] = pair_record

    if not needed:
        return {}

    sem = asyncio.Semaphore(concurrency)
    client = AsyncAnthropic()
    results: dict[str, dict[str, Any]] = {}

    async def one(key: str, pair: dict[str, Any]) -> None:
        async with sem:
            if use_cache:
                cached = _read_cache(key)
                if cached:
                    results[key] = cached
                    if on_progress:
                        await on_progress("cache_hit", key, {})
                    return
            a = people_by_id.get(pair["a_id"])
            b = people_by_id.get(pair["b_id"])
            if not (a and b):
                return
            if on_progress:
                await on_progress("start", key, {"a": a.name, "b": b.name})
            out = await _explain_one(a, b, pair, rubric, client)
            if use_cache and not out.get("error") and not out.get("parse_failed"):
                _write_cache(key, out)
            results[key] = out
            if on_progress:
                await on_progress("ok", key, {"rationale_len": len(out.get("rationale", ""))})

    await asyncio.gather(*(one(k, p) for k, p in needed.items()))

    # Attach rationales onto the matrix
    for pair_record in matrix.get("pairs", []):
        key = _pair_key(pair_record["a_id"], pair_record["b_id"])
        if key in results:
            pair_record["rationale"] = results[key].get("rationale", "")
            pair_record["intro_message"] = results[key].get("intro_message", "")
    for pid, matches in matrix.get("top_k_per_person", {}).items():
        for m in matches:
            key = _pair_key(pid, m["other_id"])
            if key in results:
                m["rationale"] = results[key].get("rationale", "")
                m["intro_message"] = results[key].get("intro_message", "")

    return results
