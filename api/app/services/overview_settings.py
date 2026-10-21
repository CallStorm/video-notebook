"""Admin 概览生成设置。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.overview_settings import OverviewSettingsConfig
from app.overview_settings.defaults import (
    DEFAULT_AUTO_GENERATE_AFTER_SUBTITLE,
    DEFAULT_OVERVIEW_PROMPT,
)
from app.schemas.overview_settings import OverviewSettingsRead, OverviewSettingsUpdate

_ROW_ID = 1


async def _ensure_row(session: AsyncSession) -> OverviewSettingsConfig:
    row = await session.get(OverviewSettingsConfig, _ROW_ID)
    if row is None:
        row = OverviewSettingsConfig(
            id=_ROW_ID,
            auto_generate_after_subtitle=DEFAULT_AUTO_GENERATE_AFTER_SUBTITLE,
            prompt_text=None,
        )
        session.add(row)
        await session.flush()
    return row


def resolve_prompt(row: OverviewSettingsConfig | None) -> str:
    if row is None:
        return DEFAULT_OVERVIEW_PROMPT
    text = (row.prompt_text or "").strip()
    return text or DEFAULT_OVERVIEW_PROMPT


def _to_read(row: OverviewSettingsConfig) -> OverviewSettingsRead:
    custom = bool((row.prompt_text or "").strip())
    return OverviewSettingsRead(
        auto_generate_after_subtitle=bool(row.auto_generate_after_subtitle),
        prompt_text=resolve_prompt(row),
        is_custom_prompt=custom,
        default_prompt=DEFAULT_OVERVIEW_PROMPT,
    )


async def get_overview_settings(session: AsyncSession) -> OverviewSettingsRead:
    row = await _ensure_row(session)
    return _to_read(row)


async def get_overview_settings_row(session: AsyncSession) -> OverviewSettingsConfig:
    """供 pipeline / overview 读取。"""
    return await _ensure_row(session)


async def update_overview_settings(
    session: AsyncSession, body: OverviewSettingsUpdate
) -> OverviewSettingsRead:
    row = await _ensure_row(session)
    row.auto_generate_after_subtitle = bool(body.auto_generate_after_subtitle)
    cleaned = (body.prompt_text or "").strip()
    row.prompt_text = cleaned or None
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _to_read(row)
