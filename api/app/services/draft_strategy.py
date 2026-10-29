"""底稿策略：CRUD、全局设置、内置种子、试跑。"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError
from app.draft_strategy.defaults import (
    BUILTIN_STRATEGIES,
    DEFAULT_PREFIX,
    KIND_LABELS,
    OUTPUT_SCHEMA,
    OUTPUT_SCHEMA_INSTRUCTION,
)
from app.llm.config_service import get_active_llm
from app.llm.providers import make_provider
from app.models.draft_strategy import (
    GLOBAL_MODEL_REF_VALUES,
    KIND_VALUES,
    MODEL_REF_VALUES,
    DraftStrategy,
    DraftStrategySettings,
)
from app.models.notebook import Subtitle, SubtitleLine, Video
from app.schemas.draft_strategy import (
    DraftStrategyCreate,
    DraftStrategyPlaygroundRequest,
    DraftStrategyPlaygroundResponse,
    DraftStrategyRead,
    DraftStrategySettingsRead,
    DraftStrategySettingsUpdate,
    DraftStrategyUpdate,
)

_SETTINGS_ID = 1
_MAX_TRANSCRIPT_CHARS = 14_000
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _to_read(row: DraftStrategy) -> DraftStrategyRead:
    return DraftStrategyRead(
        id=int(row.id),
        name=row.name,
        title=row.title,
        description=row.description or "",
        kind=row.kind,  # type: ignore[arg-type]
        prompt=row.prompt or "",
        apply_default=bool(row.apply_default),
        enabled=bool(row.enabled),
        suggested_model=row.suggested_model,  # type: ignore[arg-type]
        min_sources=int(row.min_sources),
        is_builtin=bool(row.is_builtin),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _ensure_settings(session: AsyncSession) -> DraftStrategySettings:
    row = await session.get(DraftStrategySettings, _SETTINGS_ID)
    if row is None:
        row = DraftStrategySettings(
            id=_SETTINGS_ID,
            default_prefix=DEFAULT_PREFIX,
            default_model_ref="claude_code",
        )
        session.add(row)
        await session.flush()
    return row


async def seed_builtin_strategies(session: AsyncSession) -> None:
    """插入缺失的内置策略与全局设置行；不覆盖已有 prompt。"""
    await _ensure_settings(session)
    existing = {
        r.name: r
        for r in (
            await session.execute(select(DraftStrategy).where(DraftStrategy.is_builtin.is_(True)))
        ).scalars().all()
    }
    for spec in BUILTIN_STRATEGIES:
        if spec["name"] in existing:
            continue
        session.add(
            DraftStrategy(
                name=spec["name"],
                title=spec["title"],
                description=spec["description"],
                kind=spec["kind"],
                prompt=spec["prompt"],
                apply_default=bool(spec["apply_default"]),
                enabled=bool(spec["enabled"]),
                suggested_model=spec["suggested_model"],
                min_sources=int(spec["min_sources"]),
                is_builtin=True,
            )
        )
    await session.flush()
    # 保证至多一条 apply_default
    defaults = (
        await session.execute(
            select(DraftStrategy).where(DraftStrategy.apply_default.is_(True)).order_by(DraftStrategy.id)
        )
    ).scalars().all()
    if len(defaults) > 1:
        keep = defaults[0].id
        await session.execute(
            update(DraftStrategy)
            .where(DraftStrategy.id != keep, DraftStrategy.apply_default.is_(True))
            .values(apply_default=False)
        )
    elif len(defaults) == 0:
        deep = (
            await session.execute(
                select(DraftStrategy).where(DraftStrategy.name == "deep_read")
            )
        ).scalar_one_or_none()
        if deep is not None:
            deep.apply_default = True
            session.add(deep)
    await session.commit()


async def get_settings(session: AsyncSession) -> DraftStrategySettingsRead:
    await seed_builtin_strategies(session)
    row = await _ensure_settings(session)
    return DraftStrategySettingsRead(
        default_prefix=row.default_prefix or "",
        default_model_ref=row.default_model_ref,  # type: ignore[arg-type]
        output_schema=OUTPUT_SCHEMA,
        kind_labels=KIND_LABELS,
    )


async def update_settings(
    session: AsyncSession, body: DraftStrategySettingsUpdate
) -> DraftStrategySettingsRead:
    if body.default_model_ref not in GLOBAL_MODEL_REF_VALUES:
        raise BadRequestError("default_model_ref 无效")
    row = await _ensure_settings(session)
    row.default_prefix = body.default_prefix or ""
    row.default_model_ref = body.default_model_ref
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return DraftStrategySettingsRead(
        default_prefix=row.default_prefix or "",
        default_model_ref=row.default_model_ref,  # type: ignore[arg-type]
        output_schema=OUTPUT_SCHEMA,
        kind_labels=KIND_LABELS,
    )


async def list_strategies(session: AsyncSession) -> list[DraftStrategyRead]:
    await seed_builtin_strategies(session)
    rows = (
        await session.execute(
            select(DraftStrategy).order_by(
                DraftStrategy.is_builtin.desc(),
                DraftStrategy.id.asc(),
            )
        )
    ).scalars().all()
    return [_to_read(r) for r in rows]


async def get_strategy(session: AsyncSession, strategy_id: int) -> DraftStrategyRead:
    row = await session.get(DraftStrategy, strategy_id)
    if row is None:
        raise NotFoundError(f"策略 {strategy_id} 不存在")
    return _to_read(row)


async def _clear_other_defaults(session: AsyncSession, keep_id: int) -> None:
    await session.execute(
        update(DraftStrategy)
        .where(DraftStrategy.id != keep_id, DraftStrategy.apply_default.is_(True))
        .values(apply_default=False)
    )


async def create_strategy(
    session: AsyncSession, body: DraftStrategyCreate
) -> DraftStrategyRead:
    name = body.name.strip()
    if not _NAME_RE.fullmatch(name):
        raise BadRequestError("name 须为小写字母开头的 snake_case（最多 64）")
    if body.kind not in KIND_VALUES:
        raise BadRequestError("kind 无效")
    if body.suggested_model not in MODEL_REF_VALUES:
        raise BadRequestError("suggested_model 无效")
    # 自定义策略 kind 允许选内置类型标签；name 不可与现有冲突
    clash = (
        await session.execute(select(DraftStrategy).where(DraftStrategy.name == name))
    ).scalar_one_or_none()
    if clash is not None:
        raise BadRequestError(f"name={name} 已存在")
    row = DraftStrategy(
        name=name,
        title=body.title.strip(),
        description=(body.description or "").strip(),
        kind=body.kind,
        prompt=body.prompt or "",
        apply_default=bool(body.apply_default),
        enabled=bool(body.enabled),
        suggested_model=body.suggested_model,
        min_sources=int(body.min_sources),
        is_builtin=False,
    )
    session.add(row)
    await session.flush()
    if row.apply_default:
        await _clear_other_defaults(session, int(row.id))
    await session.commit()
    await session.refresh(row)
    return _to_read(row)


async def update_strategy(
    session: AsyncSession, strategy_id: int, body: DraftStrategyUpdate
) -> DraftStrategyRead:
    row = await session.get(DraftStrategy, strategy_id)
    if row is None:
        raise NotFoundError(f"策略 {strategy_id} 不存在")

    data = body.model_dump(exclude_unset=True)
    if row.is_builtin:
        # 内置：不可改 name / kind
        data.pop("name", None)
        data.pop("kind", None)

    if "name" in data and data["name"] is not None:
        name = str(data["name"]).strip()
        if not _NAME_RE.fullmatch(name):
            raise BadRequestError("name 须为小写字母开头的 snake_case")
        clash = (
            await session.execute(
                select(DraftStrategy).where(
                    DraftStrategy.name == name, DraftStrategy.id != strategy_id
                )
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise BadRequestError(f"name={name} 已存在")
        row.name = name

    if "kind" in data and data["kind"] is not None:
        if data["kind"] not in KIND_VALUES:
            raise BadRequestError("kind 无效")
        row.kind = data["kind"]

    if "title" in data and data["title"] is not None:
        row.title = str(data["title"]).strip()
    if "description" in data and data["description"] is not None:
        row.description = str(data["description"]).strip()
    if "prompt" in data and data["prompt"] is not None:
        row.prompt = data["prompt"]
    if "suggested_model" in data and data["suggested_model"] is not None:
        if data["suggested_model"] not in MODEL_REF_VALUES:
            raise BadRequestError("suggested_model 无效")
        row.suggested_model = data["suggested_model"]
    if "min_sources" in data and data["min_sources"] is not None:
        row.min_sources = int(data["min_sources"])
    if "enabled" in data and data["enabled"] is not None:
        row.enabled = bool(data["enabled"])

    make_default = data.get("apply_default")
    if make_default is True:
        row.apply_default = True
    elif make_default is False:
        row.apply_default = False

    session.add(row)
    await session.flush()
    if row.apply_default:
        await _clear_other_defaults(session, int(row.id))
    await session.commit()
    await session.refresh(row)
    return _to_read(row)


async def delete_strategy(session: AsyncSession, strategy_id: int) -> None:
    row = await session.get(DraftStrategy, strategy_id)
    if row is None:
        raise NotFoundError(f"策略 {strategy_id} 不存在")
    if row.is_builtin:
        raise BadRequestError("内置策略不可删除，可停用")
    was_default = bool(row.apply_default)
    await session.delete(row)
    await session.flush()
    if was_default:
        deep = (
            await session.execute(
                select(DraftStrategy).where(DraftStrategy.name == "deep_read")
            )
        ).scalar_one_or_none()
        if deep is not None:
            deep.apply_default = True
            session.add(deep)
    await session.commit()


def _transcript_from_lines(lines: list[SubtitleLine]) -> str:
    parts: list[str] = []
    total = 0
    for line in lines:
        text = (line.text or "").strip()
        if not text:
            continue
        start = getattr(line, "start_ms", None)
        if start is not None:
            try:
                sec = int(start) // 1000
                mm, ss = divmod(sec, 60)
                stamp = f"{mm:02d}:{ss:02d}"
                piece = f"[{stamp}] {text}"
            except Exception:
                piece = text
        else:
            piece = text
        parts.append(piece)
        total += len(piece)
        if total >= _MAX_TRANSCRIPT_CHARS:
            break
    return "\n".join(parts)


async def _load_video_transcript(session: AsyncSession, video_id: int) -> str:
    video = await session.get(Video, video_id)
    if video is None:
        raise NotFoundError(f"video {video_id} 不存在")
    sub = (
        await session.execute(
            select(Subtitle)
            .where(Subtitle.video_id == video_id)
            .order_by(Subtitle.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if sub is None:
        raise BadRequestError(f"video {video_id} 尚无字幕")
    lines = (
        await session.execute(
            select(SubtitleLine)
            .where(SubtitleLine.subtitle_id == sub.id)
            .order_by(SubtitleLine.line_no)
        )
    ).scalars().all()
    transcript = _transcript_from_lines(list(lines))
    if not transcript.strip():
        raise BadRequestError(f"video {video_id} 字幕为空")
    title = (video.title or "").strip()
    if title:
        return f"视频标题：{title}\n\n字幕：\n{transcript}"
    return transcript


def _extract_json(text: str) -> tuple[dict[str, Any] | None, str | None]:
    raw = (text or "").strip()
    if not raw:
        return None, "模型返回为空"
    # 剥掉 ```json ... ```
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data, None
        return None, "JSON 根节点不是对象"
    except json.JSONDecodeError:
        # 尝试截取第一个 { ... 最后一个 }
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
                if isinstance(data, dict):
                    return data, None
            except json.JSONDecodeError as exc:
                return None, f"JSON 解析失败: {exc}"
        return None, "无法从回复中解析 JSON"


async def run_playground(
    session: AsyncSession, body: DraftStrategyPlaygroundRequest
) -> DraftStrategyPlaygroundResponse:
    row = await session.get(DraftStrategy, body.strategy_id)
    if row is None:
        raise NotFoundError(f"策略 {body.strategy_id} 不存在")

    source_text = (body.source_text or "").strip()
    if body.video_id is not None:
        source_text = await _load_video_transcript(session, int(body.video_id))
    if not source_text:
        raise BadRequestError("请提供 source_text 或有效的 video_id")

    settings = await _ensure_settings(session)
    prefix = (settings.default_prefix or DEFAULT_PREFIX).strip()
    strategy_prompt = (row.prompt or "").strip()

    resolved_ref = body.model_override or row.suggested_model or "inherit"
    if resolved_ref == "inherit":
        resolved_ref = settings.default_model_ref or "chat"

    model_note = None
    # 试跑统一走默认聊天模型（Claude Code 面向 Studio 工作区，不适合短试跑）
    if resolved_ref == "claude_code":
        model_note = "试跑使用默认聊天模型（Claude Code 仅用于 Studio 正式任务）"
        resolved_ref = "chat"

    llm = await get_active_llm(session)
    provider = make_provider(
        provider_name=llm.provider,
        api_key=llm.api_key,
        base_url=llm.base_url,
        model_name=llm.model_name,
        params_json=llm.params_json,
    )

    system = "\n\n".join(
        p for p in [prefix, OUTPUT_SCHEMA_INSTRUCTION] if p
    )
    user_prompt = f"{strategy_prompt}\n\n---\n来源材料：\n{source_text}"

    raw_text = await provider.complete(
        user_prompt,
        system=system,
        max_tokens=3500,
    )
    preview, parse_error = _extract_json(raw_text)
    return DraftStrategyPlaygroundResponse(
        strategy_id=int(row.id),
        model_used=f"{llm.provider}:{llm.model_name}",
        model_note=model_note,
        raw_text=raw_text or "",
        preview=preview,
        parse_ok=preview is not None,
        parse_error=parse_error,
    )
