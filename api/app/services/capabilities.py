"""Studio capability sync from disk plugins + enable/disable."""
from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models.studio import StudioCapability, StudioTask
from app.studio.plugins.registry import get_plugin, list_plugins

_TEXT_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_FIELD_TYPES = frozenset({"sources", "language", "text", "select"})


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
        if ftype == "select":
            options_raw = field.get("options")
            if not isinstance(options_raw, list) or not options_raw:
                raise BadRequestError("下拉选项无效")
            options: list[dict] = []
            values: set[str] = set()
            for opt in options_raw:
                if not isinstance(opt, dict):
                    raise BadRequestError("下拉选项无效")
                value = opt.get("value")
                if not isinstance(value, str) or not value.strip():
                    raise BadRequestError("下拉选项无效")
                value = value.strip()
                if value in values:
                    raise BadRequestError("下拉选项不能重复")
                values.add(value)
                label = opt.get("label")
                options.append(
                    {
                        "value": value,
                        "label": label.strip() if isinstance(label, str) and label.strip() else value,
                    }
                )
            item = {
                "type": "select",
                "key": key,
                "label": field.get("label") or "",
                "required": bool(field.get("required", False)),
                "options": options,
            }
            default = field.get("default")
            if isinstance(default, str) and default.strip():
                default = default.strip()
                if default not in values:
                    raise BadRequestError("下拉默认值不在选项中")
                item["default"] = default
            normalized.append(item)
            continue
        item = {
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
    """Sync disk plugins into studio_capabilities (create / refresh form+name+icon)."""
    plugin_ids = {p.id for p in list_plugins()}
    for plugin in list_plugins():
        form = validate_form(plugin.form)
        cap = await session.scalar(
            select(StudioCapability).where(
                StudioCapability.is_builtin.is_(True),
                StudioCapability.format_key == plugin.id,
                StudioCapability.deleted_at.is_(None),
            )
        )
        if cap is None:
            session.add(
                StudioCapability(
                    name=plugin.name,
                    icon=plugin.icon,
                    format_key=plugin.id,
                    agent_id=None,
                    enabled=bool(plugin.enabled_by_default),
                    is_builtin=True,
                    form_json=form,
                )
            )
            continue
        # Plugin metadata owned by disk; enabled / agent_id kept as admin set them.
        cap.name = plugin.name
        cap.icon = plugin.icon
        cap.form_json = form
        # Plugins no longer need bound agents.
        cap.agent_id = None
        session.add(cap)

    # Soft-delete builtins whose plugin folder disappeared.
    builtins = (
        await session.execute(
            select(StudioCapability).where(
                StudioCapability.is_builtin.is_(True),
                StudioCapability.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    now = datetime.now(UTC).replace(tzinfo=None)
    for cap in builtins:
        if cap.format_key not in plugin_ids:
            cap.enabled = False
            cap.deleted_at = now
            session.add(cap)
        # structured_notes retired from Studio product — keep row, force off.
        elif cap.format_key == "structured_notes" and cap.enabled:
            cap.enabled = False
            session.add(cap)
    await session.commit()


async def _get_live(session: AsyncSession, capability_id: int) -> StudioCapability:
    cap = await session.get(StudioCapability, capability_id)
    if cap is None or cap.deleted_at is not None:
        raise NotFoundError("能力不存在")
    return cap


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


async def enable_capability(session: AsyncSession, capability_id: int) -> StudioCapability:
    cap = await _get_live(session, capability_id)
    if cap.format_key == "structured_notes":
        raise ConflictError("结构化笔记已下线，无法启用")
    # Must correspond to a disk plugin (or legacy non-plugin for tests with is_builtin=False).
    if cap.is_builtin:
        try:
            get_plugin(cap.format_key)
        except KeyError as exc:
            raise ConflictError("插件目录不存在，无法启用") from exc
    cap.enabled = True
    # Clear legacy agent binding — plugins are self-contained.
    cap.agent_id = None
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


# --- Legacy CRUD kept for tests / API compatibility but admin UI no longer exposes them ---


async def create_capability(
    session: AsyncSession,
    *,
    name: str,
    icon: str | None,
    format_key: str,
    agent_id: int | None,
    form: list[dict],
) -> StudioCapability:
    raise BadRequestError("Studio 能力改为磁盘插件，请在 api/app/studio/plugins/ 新增，不在页面创建")


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
    raise BadRequestError("Studio 能力由插件目录管理，页面仅支持启用/停用")


async def delete_capability(session: AsyncSession, capability_id: int) -> None:
    cap = await _get_live(session, capability_id)
    if cap.is_builtin:
        raise ConflictError("预置能力不能删除；请停用或移除插件目录")
    has_task = await session.scalar(
        select(StudioTask.id).where(StudioTask.capability_id == capability_id).limit(1)
    )
    if has_task is not None:
        raise ConflictError("能力仍有任务")
    cap.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(cap)
    await session.commit()
