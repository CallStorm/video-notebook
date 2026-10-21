"""Admin 语音切片设置服务。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subtitle_slice_settings import SubtitleSliceSettingsConfig
from app.schemas.subtitle_slice_settings import (
    SubtitleSliceSettingsRead,
    SubtitleSliceSettingsUpdate,
)
from app.subtitle_slice_settings.runtime import set_runtime_snapshot

_ROW_ID = 1


async def _ensure_row(session: AsyncSession) -> SubtitleSliceSettingsConfig:
    row = await session.get(SubtitleSliceSettingsConfig, _ROW_ID)
    if row is None:
        row = SubtitleSliceSettingsConfig(
            id=_ROW_ID,
            max_slice_seconds=30,
            min_slice_ms=600,
            silence_noise_db=-32.0,
            silence_min_duration_s=0.3,
            min_silence_for_cut_ms=200,
        )
        session.add(row)
        await session.flush()
    return row


def _publish(row: SubtitleSliceSettingsConfig) -> None:
    set_runtime_snapshot(
        max_slice_seconds=int(row.max_slice_seconds),
        min_slice_ms=int(row.min_slice_ms),
        silence_noise_db=float(row.silence_noise_db),
        silence_min_duration_s=float(row.silence_min_duration_s),
        min_silence_for_cut_ms=int(row.min_silence_for_cut_ms),
    )


def _to_read(row: SubtitleSliceSettingsConfig) -> SubtitleSliceSettingsRead:
    return SubtitleSliceSettingsRead(
        max_slice_seconds=int(row.max_slice_seconds),
        min_slice_ms=int(row.min_slice_ms),
        silence_noise_db=float(row.silence_noise_db),
        silence_min_duration_s=float(row.silence_min_duration_s),
        min_silence_for_cut_ms=int(row.min_silence_for_cut_ms),
    )


async def get_subtitle_slice_settings(session: AsyncSession) -> SubtitleSliceSettingsRead:
    row = await _ensure_row(session)
    _publish(row)
    return _to_read(row)


async def update_subtitle_slice_settings(
    session: AsyncSession, body: SubtitleSliceSettingsUpdate
) -> SubtitleSliceSettingsRead:
    row = await _ensure_row(session)
    row.max_slice_seconds = body.max_slice_seconds
    row.min_slice_ms = body.min_slice_ms
    row.silence_noise_db = body.silence_noise_db
    row.silence_min_duration_s = body.silence_min_duration_s
    row.min_silence_for_cut_ms = body.min_silence_for_cut_ms
    session.add(row)
    await session.commit()
    await session.refresh(row)
    _publish(row)
    return _to_read(row)
