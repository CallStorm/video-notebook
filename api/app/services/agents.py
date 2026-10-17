"""智能体 CRUD 与停用连动。"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.studio import Agent, Skill, StudioCapability
from app.schemas.studio import AgentWrite

_PROVIDER = "claude_code"
_MIN_TIMEOUT = 30
_MAX_TIMEOUT = 3600


def _validate_timeout(timeout_seconds: int) -> None:
    if not _MIN_TIMEOUT <= timeout_seconds <= _MAX_TIMEOUT:
        raise BadRequestError("超时必须在 30 到 3600 秒之间")


async def _ensure_live_skill(session: AsyncSession, skill_id: int | None) -> None:
    if skill_id is None:
        return
    skill = await session.get(Skill, skill_id)
    if skill is None or skill.deleted_at is not None:
        raise BadRequestError("技能不存在")


async def _get_live_agent(session: AsyncSession, agent_id: int) -> Agent:
    agent = await session.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        raise NotFoundError("智能体不存在")
    return agent


async def create_agent(session: AsyncSession, *, updated_by: int, payload: AgentWrite) -> Agent:
    _validate_timeout(payload.timeout_seconds)
    await _ensure_live_skill(session, payload.skill_id)
    agent = Agent(
        name=payload.name,
        provider=_PROVIDER,
        skill_id=payload.skill_id,
        model_name=payload.model_name,
        system_prompt=payload.system_prompt,
        timeout_seconds=payload.timeout_seconds,
        is_active=True,
        updated_by=updated_by,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


async def list_agents(session: AsyncSession) -> list[Agent]:
    rows = (
        await session.execute(
            select(Agent).where(Agent.deleted_at.is_(None)).order_by(Agent.id.desc())
        )
    ).scalars().all()
    return list(rows)


async def get_agent(session: AsyncSession, agent_id: int) -> Agent:
    return await _get_live_agent(session, agent_id)


async def update_agent(
    session: AsyncSession, agent_id: int, *, updated_by: int, payload: AgentWrite
) -> Agent:
    _validate_timeout(payload.timeout_seconds)
    await _ensure_live_skill(session, payload.skill_id)
    agent = await _get_live_agent(session, agent_id)
    agent.name = payload.name
    agent.skill_id = payload.skill_id
    agent.model_name = payload.model_name
    agent.system_prompt = payload.system_prompt
    agent.timeout_seconds = payload.timeout_seconds
    agent.updated_by = updated_by
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


async def disable_agent(session: AsyncSession, agent_id: int) -> Agent:
    agent = await _get_live_agent(session, agent_id)
    agent.is_active = False
    caps = (
        await session.execute(
            select(StudioCapability).where(
                StudioCapability.agent_id == agent_id,
                StudioCapability.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for cap in caps:
        cap.enabled = False
        session.add(cap)
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


async def enable_agent(session: AsyncSession, agent_id: int) -> Agent:
    agent = await _get_live_agent(session, agent_id)
    agent.is_active = True
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


async def delete_agent(session: AsyncSession, agent_id: int) -> None:
    agent = await _get_live_agent(session, agent_id)
    referenced = await session.scalar(
        select(StudioCapability.id)
        .where(
            StudioCapability.agent_id == agent_id,
            StudioCapability.deleted_at.is_(None),
        )
        .limit(1)
    )
    if referenced is not None:
        raise ConflictError("智能体仍被能力选用")
    agent.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(agent)
    await session.commit()
