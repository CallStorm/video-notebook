"""Admin 封面生成设置。"""
from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.cover_settings.defaults import (
    DEFAULT_COVER_MODE,
    DEFAULT_COVER_SYSTEM_PROMPT,
    DEFAULT_COVER_USER_PROMPT,
    DEFAULT_COVER_TEMPERATURE,
    DEFAULT_FORCE_KEYWORD_MOTIF,
    DEFAULT_FALLBACK_ON_ERROR,
    DEFAULT_IMAGE_COVER_SYSTEM_PROMPT,
    DEFAULT_IMAGE_COVER_USER_PROMPT,
    DEFAULT_IMAGE_COVER_SIZE,
)
from app.models.cover_settings import CoverSettingsConfig
from app.schemas.cover_settings import CoverSettingsRead, CoverSettingsUpdate

_ROW_ID = 1
_SIZE_RE = re.compile(r"^\d{2,4}x\d{2,4}$")
_RATIO_RE = re.compile(r"^(1:1|16:9|4:3|3:2|2:3|3:4|9:16|21:9)$")


async def _ensure_row(session: AsyncSession) -> CoverSettingsConfig:
    row = await session.get(CoverSettingsConfig, _ROW_ID)
    if row is None:
        row = CoverSettingsConfig(
            id=_ROW_ID,
            mode=DEFAULT_COVER_MODE,
            prompt_system=None,
            prompt_user=None,
            temperature=DEFAULT_COVER_TEMPERATURE,
            force_keyword_motif=DEFAULT_FORCE_KEYWORD_MOTIF,
            fallback_on_error=DEFAULT_FALLBACK_ON_ERROR,
            image_prompt_system=None,
            image_prompt_user=None,
            image_size=DEFAULT_IMAGE_COVER_SIZE,
        )
        session.add(row)
        await session.flush()
    return row


def resolve_mode(row: CoverSettingsConfig | None) -> str:
    mode = ((row.mode if row else None) or DEFAULT_COVER_MODE).strip().lower()
    return mode if mode in ("image", "svg") else DEFAULT_COVER_MODE


def resolve_system_prompt(row: CoverSettingsConfig | None) -> str:
    if row is None:
        return DEFAULT_COVER_SYSTEM_PROMPT
    text = (row.prompt_system or "").strip()
    return text or DEFAULT_COVER_SYSTEM_PROMPT


def resolve_user_prompt(row: CoverSettingsConfig | None) -> str:
    if row is None:
        return DEFAULT_COVER_USER_PROMPT
    text = (row.prompt_user or "").strip()
    return text or DEFAULT_COVER_USER_PROMPT


def resolve_temperature(row: CoverSettingsConfig | None) -> float:
    if row is None:
        return DEFAULT_COVER_TEMPERATURE
    try:
        t = float(row.temperature)
    except (TypeError, ValueError):
        return DEFAULT_COVER_TEMPERATURE
    return max(0.0, min(2.0, t))


def resolve_force_keyword_motif(row: CoverSettingsConfig | None) -> bool:
    if row is None:
        return DEFAULT_FORCE_KEYWORD_MOTIF
    return bool(row.force_keyword_motif)


def resolve_fallback_on_error(row: CoverSettingsConfig | None) -> bool:
    if row is None:
        return DEFAULT_FALLBACK_ON_ERROR
    return bool(row.fallback_on_error)


def resolve_image_system_prompt(row: CoverSettingsConfig | None) -> str:
    if row is None:
        return DEFAULT_IMAGE_COVER_SYSTEM_PROMPT
    text = (row.image_prompt_system or "").strip()
    return text or DEFAULT_IMAGE_COVER_SYSTEM_PROMPT


def resolve_image_user_prompt(row: CoverSettingsConfig | None) -> str:
    if row is None:
        return DEFAULT_IMAGE_COVER_USER_PROMPT
    text = (row.image_prompt_user or "").strip()
    return text or DEFAULT_IMAGE_COVER_USER_PROMPT


def resolve_image_size(row: CoverSettingsConfig | None) -> str:
    raw = ((row.image_size if row else None) or DEFAULT_IMAGE_COVER_SIZE).strip()
    if _SIZE_RE.match(raw) or _RATIO_RE.match(raw):
        return raw
    return DEFAULT_IMAGE_COVER_SIZE


def render_user_prompt(template: str, *, title: str, description: str) -> str:
    """渲染用户提示词模板；未知占位符保持原样。"""
    desc = (description or "").strip() or "（无）"
    return (
        (template or DEFAULT_COVER_USER_PROMPT)
        .replace("{title}", title)
        .replace("{description}", desc)
    )


def render_image_prompt(
    system_template: str,
    user_template: str,
    *,
    title: str,
    description: str,
) -> str:
    """合并 system + user 为单条文生图 prompt（多数网关只吃一个 prompt）。"""
    user = render_user_prompt(user_template, title=title, description=description)
    system = (system_template or "").strip()
    if not system:
        return user
    return f"{system}\n\n{user}"


def _to_read(row: CoverSettingsConfig) -> CoverSettingsRead:
    return CoverSettingsRead(
        mode=resolve_mode(row),  # type: ignore[arg-type]
        prompt_system=resolve_system_prompt(row),
        prompt_user=resolve_user_prompt(row),
        temperature=resolve_temperature(row),
        force_keyword_motif=resolve_force_keyword_motif(row),
        fallback_on_error=resolve_fallback_on_error(row),
        image_prompt_system=resolve_image_system_prompt(row),
        image_prompt_user=resolve_image_user_prompt(row),
        image_size=resolve_image_size(row),
        is_custom_system=bool((row.prompt_system or "").strip()),
        is_custom_user=bool((row.prompt_user or "").strip()),
        is_custom_image_system=bool((row.image_prompt_system or "").strip()),
        is_custom_image_user=bool((row.image_prompt_user or "").strip()),
        default_prompt_system=DEFAULT_COVER_SYSTEM_PROMPT,
        default_prompt_user=DEFAULT_COVER_USER_PROMPT,
        default_temperature=DEFAULT_COVER_TEMPERATURE,
        default_image_prompt_system=DEFAULT_IMAGE_COVER_SYSTEM_PROMPT,
        default_image_prompt_user=DEFAULT_IMAGE_COVER_USER_PROMPT,
        default_image_size=DEFAULT_IMAGE_COVER_SIZE,
        default_mode=DEFAULT_COVER_MODE,
    )


async def get_cover_settings(session: AsyncSession) -> CoverSettingsRead:
    row = await _ensure_row(session)
    return _to_read(row)


async def get_cover_settings_row(session: AsyncSession) -> CoverSettingsConfig:
    return await _ensure_row(session)


async def update_cover_settings(
    session: AsyncSession, body: CoverSettingsUpdate
) -> CoverSettingsRead:
    row = await _ensure_row(session)
    row.mode = body.mode if body.mode in ("image", "svg") else DEFAULT_COVER_MODE
    row.prompt_system = (body.prompt_system or "").strip() or None
    row.prompt_user = (body.prompt_user or "").strip() or None
    row.temperature = float(body.temperature)
    row.force_keyword_motif = bool(body.force_keyword_motif)
    row.fallback_on_error = bool(body.fallback_on_error)
    row.image_prompt_system = (body.image_prompt_system or "").strip() or None
    row.image_prompt_user = (body.image_prompt_user or "").strip() or None
    size = (body.image_size or "").strip() or DEFAULT_IMAGE_COVER_SIZE
    row.image_size = (
        size
        if (_SIZE_RE.match(size) or _RATIO_RE.match(size))
        else DEFAULT_IMAGE_COVER_SIZE
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _to_read(row)
