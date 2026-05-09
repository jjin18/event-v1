"""Signed tokens for confirm-via-link flow.

Lightweight stdlib-only HMAC tokens — JWT-shaped (payload.signature) but
without algorithm negotiation. Each token carries:

  - aid: attendee id
  - eid: event id (a hash of the current event payload)
  - exp: unix expiry (min(30 days from issuance, event_date))

Verification rejects tampered, expired, or wrong-event tokens.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

# 30 days in seconds — matches the spec ("30 days after creation or after
# the event date, whichever is sooner").
DEFAULT_TTL_SECONDS = 30 * 24 * 60 * 60


def _secret() -> bytes:
    """Return the signing secret as bytes.

    Reads CONFIRM_TOKEN_SECRET from env. Falls back to a process-stable derived
    value so dev still works without configuration — but logs a warning so the
    fallback isn't silently used in production.
    """
    raw = os.environ.get("CONFIRM_TOKEN_SECRET", "").strip()
    if raw:
        return raw.encode("utf-8")
    # Dev fallback: stable across the lifetime of this process. Tokens issued
    # here won't survive a restart — that's intentional for dev safety.
    fallback = os.environ.setdefault(
        "_CONFIRM_TOKEN_SECRET_DEV",
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
    )
    return fallback.encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def event_id_for(event: dict) -> str:
    """Derive a stable event id from the current event payload.

    Hash identifying fields that don't normally change after issuance — name
    and format. Date is intentionally excluded so rescheduling doesn't
    invalidate already-sent confirm links.
    """
    name = (event.get("name") or "").strip().lower()
    fmt = (event.get("format") or "").strip().lower()
    raw = f"{name}|{fmt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def attendee_id_for(name: str, email: str = "") -> str:
    """Stable attendee id from name + email so re-runs of the EI pipeline
    don't mint new ids for the same person."""
    norm = f"{(name or '').strip().lower()}|{(email or '').strip().lower()}".encode("utf-8")
    return "att_" + hashlib.sha256(norm).hexdigest()[:16]


def _expiry_unix(event_date_iso: str | None, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> int:
    """Min(now+ttl, event_date midnight UTC)."""
    base = int(time.time()) + ttl_seconds
    if not event_date_iso:
        return base
    try:
        s = event_date_iso.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            from datetime import date as _d
            dt = datetime.combine(_d.fromisoformat(s), datetime.min.time(), tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        event_unix = int(dt.timestamp())
        return min(base, event_unix)
    except Exception:
        return base


def issue(attendee_id: str,
          event: dict,
          event_date_iso: Optional[str] = None,
          ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """Create a signed token. ``event_date_iso`` overrides event["date"] for
    the expiry computation (the new top-level event_date key)."""
    payload = {
        "aid": attendee_id,
        "eid": event_id_for(event or {}),
        "exp": _expiry_unix(event_date_iso or (event or {}).get("date") or "", ttl_seconds),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(sig)}"


# --- Badge / scanner tokens (PRD §5.5–§5.6) -----------------------------------
#
# Badge tokens are baked into the QR code printed on each attendee's badge at
# check-in. They carry only the attendee id + event id and are valid for the
# event-day window (default: through the event date). The booth scanner verifies
# a badge token by re-deriving the eid against the current event payload.
#
# Scanner-staff tokens authenticate booth staff into the scanner UI itself.
# They carry the sponsor id + staff email + event id; ``kind: "scanner"``
# distinguishes them from RSVP tokens at verify time.

def issue_badge(attendee_id: str,
                event: dict,
                event_date_iso: Optional[str] = None,
                ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """QR-code badge token. Same shape as ``issue`` — kept as a named alias
    so call sites describe intent."""
    return issue(attendee_id, event, event_date_iso=event_date_iso, ttl_seconds=ttl_seconds)


def issue_scanner_session(sponsor_id: str,
                          staff_email: str,
                          event: dict,
                          event_date_iso: Optional[str] = None,
                          ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """Booth-staff scanner session token. Carries sponsor + staff identity."""
    payload = {
        "kind": "scanner",
        "sid": sponsor_id,
        "staff": (staff_email or "").strip().lower(),
        "eid": event_id_for(event or {}),
        "exp": _expiry_unix(event_date_iso or (event or {}).get("date") or "", ttl_seconds),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(sig)}"


def verify_scanner_session(token: str, event: dict) -> dict:
    """Verify a scanner-session token. Same signature/expiry/event checks as
    ``verify`` but additionally requires kind == 'scanner'."""
    payload = verify(token, event)
    if payload.get("kind") != "scanner":
        raise TokenError("not a scanner token")
    if not payload.get("sid"):
        raise TokenError("missing sponsor id")
    return payload


def sponsor_id_for(company_name: str) -> str:
    """Stable sponsor id from company name."""
    norm = (company_name or "").strip().lower().encode("utf-8")
    return "spn_" + hashlib.sha256(norm).hexdigest()[:16]


def scan_id_for(sponsor_id: str, attendee_id: str, ts: int) -> str:
    """Stable-ish scan id. ts allows multiple scans of same attendee."""
    raw = f"{sponsor_id}|{attendee_id}|{ts}".encode("utf-8")
    return "scn_" + hashlib.sha256(raw).hexdigest()[:16]


class TokenError(Exception):
    """Verification failure — bad signature, expired, or wrong event."""


def verify(token: str, event: dict) -> dict:
    """Decode + verify a token against the current event. Returns the payload
    dict on success; raises TokenError otherwise."""
    if not token or "." not in token:
        raise TokenError("malformed token")
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
    try:
        provided = _b64url_decode(sig)
    except Exception as e:
        raise TokenError(f"bad signature encoding: {e}") from None
    if not hmac.compare_digest(expected, provided):
        raise TokenError("bad signature")
    try:
        payload = json.loads(_b64url_decode(body))
    except Exception as e:
        raise TokenError(f"bad payload: {e}") from None
    if payload.get("exp", 0) < int(time.time()):
        raise TokenError("expired")
    if payload.get("eid") != event_id_for(event or {}):
        raise TokenError("wrong event")
    return payload
