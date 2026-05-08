"""Auth helpers — JWT (HS256) with stdlib only, PIN hashing with hashlib."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
TOKEN_EXPIRE_DAYS = 30
ADMIN_TOKEN_EXPIRE_HOURS = 24

# ── Minimal HS256 JWT ────────────────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * pad)


def _sign(header_b64: str, payload_b64: str) -> str:
    msg = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).digest()
    return _b64url_encode(sig)


def _encode(payload: dict) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(payload).encode())
    sig = _sign(header, body)
    return f"{header}.{body}.{sig}"


def _decode(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Bad token format")
        header_b64, payload_b64, sig_b64 = parts
        expected_sig = _sign(header_b64, payload_b64)
        if not hmac.compare_digest(expected_sig, sig_b64):
            raise ValueError("Invalid signature")
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            raise ValueError("Token expired")
        return payload
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise ValueError(str(e))


# ── Public API ───────────────────────────────────────────────────────────────

def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
    return f"pbkdf2:sha256:{salt}:{digest.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        _, _, salt, digest_hex = hashed.split(":")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def create_judge_token(judge_id: int, event_id: int) -> str:
    return _encode({
        "sub": str(judge_id),
        "event_id": event_id,
        "type": "judge",
        "exp": int(time.time()) + TOKEN_EXPIRE_DAYS * 86400,
    })


def verify_judge_token(token: str) -> dict:
    payload = _decode(token)
    if payload.get("type") != "judge":
        raise ValueError("Not a judge token")
    return payload


def create_admin_token(event_id: int) -> str:
    return _encode({
        "event_id": event_id,
        "type": "admin",
        "exp": int(time.time()) + ADMIN_TOKEN_EXPIRE_HOURS * 3600,
    })


def verify_admin_token(token: str) -> dict:
    payload = _decode(token)
    if payload.get("type") != "admin":
        raise ValueError("Not an admin token")
    return payload
