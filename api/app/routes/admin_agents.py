"""/api/admin/agents — 智能体 CRUD、启用、停用。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.studio import AgentRead, AgentWrite
from app.services import agents as svc

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])


@router.get("", response_model=list[AgentRead])
async def list_agents(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.list_agents(session)


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentWrite,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await svc.create_agent(session, updated_by=user.id, payload=body)


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(
    agent_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_agent(session, agent_id)


@router.patch("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: int,
    body: AgentWrite,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await svc.update_agent(session, agent_id, updated_by=user.id, payload=body)


@router.post("/{agent_id}/disable", response_model=AgentRead)
async def disable_agent(
    agent_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.disable_agent(session, agent_id)


@router.post("/{agent_id}/enable", response_model=AgentRead)
async def enable_agent(
    agent_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.enable_agent(session, agent_id)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    await svc.delete_agent(session, agent_id)
    return None
