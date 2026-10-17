"""JWT 签发与校验。"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.errors import UnauthorizedError

TokenType = Literal["access", "refresh"]


def _now() -> datetime:
    return datetime.now(UTC)


def _create_token(
    *,
    subject: str,
    claims: dict[str, Any],
    token_type: TokenType,
    ttl_seconds: int,
) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        "jti": uuid.uuid4().hex,
        **claims,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(
    user_id: int, *, role: str, extra: dict[str, Any] | None = None
) -> tuple[str, int]:
    """返回 (token, ttl_seconds)。"""
    settings = get_settings()
    claims = {"role": role, **(extra or {})}
    return (
        _create_token(
            subject=str(user_id),
            claims=claims,
            token_type="access",
            ttl_seconds=settings.jwt_access_ttl_seconds,
        ),
        settings.jwt_access_ttl_seconds,
    )


def create_refresh_token(user_id: int) -> str:
    settings = get_settings()
    return _create_token(
        subject=str(user_id),
        claims={},
        token_type="refresh",
        ttl_seconds=settings.jwt_refresh_ttl_seconds,
    )


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError(f"Invalid token: {exc}") from exc
    if payload.get("type") != expected_type:
        raise UnauthorizedError(f"Expected {expected_type} token, got {payload.get('type')}")
    return payload
