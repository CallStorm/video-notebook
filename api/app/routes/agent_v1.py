"""POST /agent/v1/tools/<name> — 与 MCP 同名的工具门面。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.facade import AgentContext, dispatch, tool_catalog
from app.agent.urls import public_origin
from app.core.errors import BadRequestError, UnauthorizedError
from app.db.session import get_session
from app.services.agent_tokens import authenticate_agent_token, scope_set

router = APIRouter(prefix="/agent/v1", tags=["agent"])


async def get_agent_context(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AgentContext:
    header = request.headers.get("authorization") or ""
    scheme, _, raw = header.partition(" ")
    token = raw.strip()
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("缺少 Bearer Token")
    if not token.startswith("vn_agent_"):
        raise UnauthorizedError("Agent 门面只接受 vn_agent_ Token，不要使用登录 JWT")
    user, row = await authenticate_agent_token(session, token)
    return AgentContext(user=user, token=row, scopes=scope_set(row), origin=public_origin(request))


async def _read_object(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BadRequestError("请求体不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise BadRequestError("请求体必须是 JSON 对象")
    return data


@router.get("/tools")
async def list_tools(ctx: AgentContext = Depends(get_agent_context)) -> dict:
    return {"tools": tool_catalog(ctx.scopes)}


@router.post("/tools/{name}")
async def call_tool(
    name: str,
    request: Request,
    ctx: AgentContext = Depends(get_agent_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await dispatch(session, ctx, name, await _read_object(request))
