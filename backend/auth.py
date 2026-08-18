import base64
import hashlib
import hmac
import json
import os
import time
from typing import Dict, Optional

from fastapi import Header, HTTPException, status


TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "28800"))
_APP_SECRET = os.getenv("APP_SECRET")
if not _APP_SECRET:
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise RuntimeError("APP_SECRET must be configured in production")
    _APP_SECRET = "re-active-local-development-secret-change-me"
    print("WARNING: APP_SECRET is not set; using the local-development secret")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_APP_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64encode(signature)}"


def decode_access_token(token: str) -> Optional[Dict[str, object]]:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(
            _APP_SECRET.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(supplied_signature)):
            return None

        payload = json.loads(_b64decode(encoded).decode("utf-8"))
        if int(payload.get("exp", 0)) <= int(time.time()):
            return None
        if payload.get("role") not in {"patient", "doctor"} or not payload.get("sub"):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, object]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(authorization[7:].strip())
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def require_role(user: Dict[str, object], role: str) -> None:
    if user.get("role") != role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{role.title()} access required")
