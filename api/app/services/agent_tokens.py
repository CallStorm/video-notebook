"""签发、列出、撤销 Agent Token。明文只返回一次。"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ForbiddenError, NotFoundError, UnauthorizedError
from app.models.agent_token import AgentToken
from app.models.user import User

TOKEN_PREFIX = "vn_agent_"
ALLOWED_SCOPES = ("read", "write_notebook", "write_generate")


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _as_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def iso(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    return str(value)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mint_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def scope_set(row: AgentToken) -> set[str]:
    raw = row.scopes or []
    if isinstance(raw, str):
        raw = json.loads(raw)
    return {str(item) for item in raw}


def normalize_scopes(scopes: list[str]) -> list[str]:
    if not scopes:
        raise BadRequestError("至少选择一项权限")
    unknown = [item for item in scopes if item not in ALLOWED_SCOPES]
    if unknown:
        raise BadRequestError("未知权限")
    chosen = set(scopes)
    return [item for item in ALLOWED_SCOPES if item in chosen]


def token_status(row: AgentToken, *, now: datetime | None = None) -> str:
    if row.revoked_at is not None:
        return "revoked"
    current = now or _now()
    expires = _as_naive(row.expires_at) if isinstance(row.expires_at, datetime) else row.expires_at
    if isinstance(expires, datetime) and expires <= current:
        return "expired"
    return "active"


def present_token(row: AgentToken) -> dict:
    scopes = row.scopes or []
    if isinstance(scopes, str):
        scopes = json.loads(scopes)
    return {
        "id": int(row.id),
        "name": row.name,
        "scopes": list(scopes),
        "created_at": iso(row.created_at),
        "expires_at": iso(row.expires_at),
        "revoked_at": iso(row.revoked_at),
        "last_used_at": iso(row.last_used_at),
        "status": token_status(row),
        "hint": row.token_hint,
    }


async def create_token(
    session: AsyncSession,
    *,
    user_id: int,
    name: str | None,
    scopes: list[str],
    expires_in_days: int | None,
) -> tuple[AgentToken, str]:
    if expires_in_days not in (None, 30, 90):
        raise BadRequestError("过期时间只支持不过期、30 天或 90 天")
    cleaned = (name or "").strip() or "Default"
    if len(cleaned) > 64:
        raise BadRequestError("名称过长")
    plaintext = mint_token()
    row = AgentToken(
        user_id=user_id,
        name=cleaned,
        token_hash=hash_token(plaintext),
        token_hint=plaintext[-4:],
        scopes=normalize_scopes(scopes),
        expires_at=None if not expires_in_days else _now() + timedelta(days=expires_in_days),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row, plaintext


async def list_tokens(session: AsyncSession, *, user_id: int) -> list[AgentToken]:
    rows = (
        await session.execute(
            select(AgentToken)
            .where(AgentToken.user_id == user_id)
            .order_by(AgentToken.id.desc())
        )
    ).scalars().all()
    return list(rows)


async def revoke_token(
    session: AsyncSession, *, user_id: int, token_id: int
) -> AgentToken:
    row = await session.get(AgentToken, token_id)
    if row is None or row.user_id != user_id:
        raise NotFoundError("Token 不存在")
    if row.revoked_at is None:
        row.revoked_at = _now()
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def authenticate_agent_token(
    session: AsyncSession, raw: str
) -> tuple[User, AgentToken]:
    if not raw.startswith(TOKEN_PREFIX):
        raise UnauthorizedError("Agent 门面只接受 vn_agent_ Token，不要使用登录 JWT")
    row = await session.scalar(
        select(AgentToken).where(AgentToken.token_hash == hash_token(raw))
    )
    if row is None:
        raise UnauthorizedError("Agent Token 无效")
    now = _now()
    if row.revoked_at is not None:
        raise UnauthorizedError("Agent Token 已撤销")
    expires = row.expires_at if isinstance(row.expires_at, datetime) else None
    if isinstance(expires, datetime) and (_as_naive(expires) or expires) <= now:
        raise UnauthorizedError("Agent Token 已过期")
    user = await session.get(User, int(row.user_id))
    if user is None:
        raise UnauthorizedError("Agent Token 无效")
    if user.status != "active":
        raise ForbiddenError("用户已停用")
    row.last_used_at = now
    session.add(row)
    await session.commit()
    return user, row
