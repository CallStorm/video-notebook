"""登录用户管理自己的 Agent Token。明文只在创建响应里出现。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.urls import connect_info, public_origin
from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.services import agent_tokens as svc

router = APIRouter(prefix="/users/me", tags=["agent-tokens"])


class AgentTokenCreate(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    scopes: list[str] = Field(
        default_factory=lambda: ["read", "write_notebook", "write_generate"]
    )
    expires_in_days: int | None = None


@router.get("/agent-connect")
async def agent_connect(
    request: Request,
    _: User = Depends(get_current_active_user),
) -> dict:
    return connect_info(public_origin(request))


@router.get("/agent-tokens")
async def list_agent_tokens(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
) -> dict:
    rows = await svc.list_tokens(session, user_id=user.id)
    return {"items": [svc.present_token(row) for row in rows]}


@router.post("/agent-tokens", status_code=status.HTTP_201_CREATED)
async def create_agent_token(
    body: AgentTokenCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
) -> dict:
    row, plaintext = await svc.create_token(
        session,
        user_id=user.id,
        name=body.name,
        scopes=body.scopes,
        expires_in_days=body.expires_in_days,
    )
    origin = public_origin(request)
    return {
        "token": svc.present_token(row),
        "plaintext": plaintext,
        **connect_info(origin, plaintext),
    }


@router.post("/agent-tokens/{token_id}/revoke")
async def revoke_agent_token(
    token_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
) -> dict:
    row = await svc.revoke_token(session, user_id=user.id, token_id=token_id)
    return svc.present_token(row)
