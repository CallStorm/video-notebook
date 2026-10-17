"""能力 CRUD、表单校验、预置种子。"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.studio import Agent, StudioCapability, StudioTask
from app.studio.formats import get_format

_TEXT_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_FIELD_TYPES = frozenset({"sources", "language", "text"})

_MIND_MAP_FORM = [
    {"type": "language"},
    {"type": "sources"},
    {"type": "text", "key": "topic", "label": "主题", "required": True, "multiline": False},
]
_SLIDES_FORM = [
    {"type": "language"},
    {"type": "sources"},
    {
        "type": "text",
        "key": "brief",
        "label": "描述",
        "placeholder": "写明受众、结构和期望页数",
        "required": True,
        "multiline": True,
    },
]
_BUILTINS = (
    {
        "name": "思维导图",
        "icon": "🧠",
        "format_key": "mind_map",
        "form_json": _MIND_MAP_FORM,
    },
    {
        "name": "PPT",
        "icon": "📊",
        "format_key": "slides",
        "form_json": _SLIDES_FORM,
    },
)


def validate_form(fields: list[dict]) -> list[dict]:
    if not isinstance(fields, list):
        raise BadRequestError("表单必须是数组")
    seen_singleton: set[str] = set()
    seen_keys: set[str] = set()
    normalized: list[dict] = []
    for field in fields:
        if not isinstance(field, dict):
            raise BadRequestError("表单字段无效")
        ftype = field.get("type")
        if ftype not in _FIELD_TYPES:
            raise BadRequestError("表单字段类型无效")
        if ftype in {"sources", "language"}:
            if ftype in seen_singleton:
                raise BadRequestError("来源和语言各自最多一个")
            seen_singleton.add(ftype)
            normalized.append({"type": ftype})
            continue
        key = field.get("key")
        if not isinstance(key, str) or not _TEXT_KEY_RE.fullmatch(key):
            raise BadRequestError("文本字段 key 无效")
        if key in seen_keys:
            raise BadRequestError("文本字段 key 必须唯一")
        seen_keys.add(key)
        item: dict = {
            "type": "text",
            "key": key,
            "label": field.get("label") or "",
            "required": bool(field.get("required", False)),
            "multiline": bool(field.get("multiline", False)),
        }
        placeholder = field.get("placeholder")
        if isinstance(placeholder, str) and placeholder:
            item["placeholder"] = placeholder
        normalized.append(item)
    return normalized


async def seed_builtin_capabilities(session: AsyncSession) -> None:
    for spec in _BUILTINS:
        existing = await session.scalar(
            select(StudioCapability.id).where(
                StudioCapability.is_builtin.is_(True),
                StudioCapability.format_key == spec["format_key"],
            )
        )
        if existing is not None:
            continue
        session.add(
            StudioCapability(
                name=spec["name"],
                icon=spec["icon"],
                format_key=spec["format_key"],
                agent_id=None,
                enabled=False,
                is_builtin=True,
                form_json=spec["form_json"],
            )
        )
    await session.commit()


async def _get_live(session: AsyncSession, capability_id: int) -> StudioCapability:
    cap = await session.get(StudioCapability, capability_id)
    if cap is None or cap.deleted_at is not None:
        raise NotFoundError("能力不存在")
    return cap


def _ensure_format(format_key: str) -> None:
    try:
        get_format(format_key)
    except KeyError as exc:
        raise BadRequestError("产物格式不存在") from exc


async def _require_existing_agent(session: AsyncSession, agent_id: int | None) -> Agent | None:
    if agent_id is None:
        return None
    agent = await session.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        raise BadRequestError("智能体不存在")
    return agent


def _require_usable_agent_if_enabled(*, enabled: bool, agent: Agent | None) -> None:
    if not enabled:
        return
    if agent is None or not agent.is_active:
        raise ConflictError("能力还没有可用的智能体")


async def list_capabilities(session: AsyncSession) -> list[StudioCapability]:
    rows = (
        await session.execute(
            select(StudioCapability)
            .where(StudioCapability.deleted_at.is_(None))
            .order_by(StudioCapability.id.asc())
        )
    ).scalars().all()
    return list(rows)


async def get_capability(session: AsyncSession, capability_id: int) -> StudioCapability:
    return await _get_live(session, capability_id)


async def create_capability(
    session: AsyncSession,
    *,
    name: str,
    icon: str | None,
    format_key: str,
    agent_id: int | None,
    form: list[dict],
) -> StudioCapability:
    _ensure_format(format_key)
    agent = await _require_existing_agent(session, agent_id)
    _require_usable_agent_if_enabled(enabled=False, agent=agent)
    cap = StudioCapability(
        name=name,
        icon=icon,
        format_key=format_key,
        agent_id=agent_id,
        enabled=False,
        is_builtin=False,
        form_json=validate_form(form),
    )
    session.add(cap)
    await session.commit()
    await session.refresh(cap)
    return cap


async def update_capability(
    session: AsyncSession,
    capability_id: int,
    *,
    name: str | None,
    icon: str | None,
    agent_id: int | None,
    form: list[dict] | None,
    fields_set: set[str],
) -> StudioCapability:
    if "format_key" in fields_set:
        raise BadRequestError("产物格式创建后不能改")
    cap = await _get_live(session, capability_id)
    next_agent_id = agent_id if "agent_id" in fields_set else cap.agent_id
    agent = await _require_existing_agent(session, next_agent_id)
    _require_usable_agent_if_enabled(enabled=cap.enabled, agent=agent)
    if name is not None:
        cap.name = name
    if "icon" in fields_set:
        cap.icon = icon
    if "agent_id" in fields_set:
        cap.agent_id = agent_id
    if form is not None:
        cap.form_json = validate_form(form)
    session.add(cap)
    await session.commit()
    await session.refresh(cap)
    return cap


async def enable_capability(session: AsyncSession, capability_id: int) -> StudioCapability:
    cap = await _get_live(session, capability_id)
    agent_ok = False
    if cap.agent_id is not None:
        agent = await session.get(Agent, cap.agent_id)
        if agent is not None and agent.deleted_at is None and agent.is_active:
            agent_ok = True
    if not agent_ok:
        raise ConflictError("能力还没有可用的智能体")
    cap.enabled = True
    session.add(cap)
    await session.commit()
    await session.refresh(cap)
    return cap


async def disable_capability(session: AsyncSession, capability_id: int) -> StudioCapability:
    cap = await _get_live(session, capability_id)
    cap.enabled = False
    session.add(cap)
    await session.commit()
    await session.refresh(cap)
    return cap


async def delete_capability(session: AsyncSession, capability_id: int) -> None:
    cap = await _get_live(session, capability_id)
    if cap.is_builtin:
        raise ConflictError("预置能力不能删除")
    has_task = await session.scalar(
        select(StudioTask.id).where(StudioTask.capability_id == capability_id).limit(1)
    )
    if has_task is not None:
        raise ConflictError("能力仍有任务")
    cap.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(cap)
    await session.commit()
