"""Admin 可观测：设置 + 查询（限流）。"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.notebook import ChatThread, Notebook, NotebookSource, Video
from app.models.observability import (
    LlmSpan,
    LlmTrace,
    ObservabilitySettingsConfig,
    PipelineRun,
    PipelineRunEvent,
)
from app.observability.purge import request_purge
from app.observability.settings_cache import invalidate
from app.schemas.observability import (
    LlmSpanItem,
    LlmTraceDetail,
    LlmTraceListItem,
    LlmTraceListResponse,
    ObservabilitySettingsRead,
    ObservabilitySettingsUpdate,
    PipelineRunDetail,
    PipelineRunEventItem,
    PipelineRunListItem,
    PipelineRunListResponse,
)

_ROW_ID = 1
_MAX_LIST = 100


async def _ensure_row(session: AsyncSession) -> ObservabilitySettingsConfig:
    row = await session.get(ObservabilitySettingsConfig, _ROW_ID)
    if row is None:
        row = ObservabilitySettingsConfig(
            id=_ROW_ID,
            pipeline_logs_enabled=False,
            llm_traces_enabled=False,
            retention_days=7,
            success_sample_rate=1.0,
            llm_record_full=False,
            llm_truncate_chars=4096,
            max_pipeline_run_rows=50000,
            max_llm_trace_rows=20000,
            langfuse_enabled=False,
        )
        session.add(row)
        await session.flush()
    return row


def _to_settings(row: ObservabilitySettingsConfig) -> ObservabilitySettingsRead:
    return ObservabilitySettingsRead(
        pipeline_logs_enabled=bool(row.pipeline_logs_enabled),
        llm_traces_enabled=bool(row.llm_traces_enabled),
        retention_days=int(row.retention_days),
        success_sample_rate=float(row.success_sample_rate),
        llm_record_full=bool(row.llm_record_full),
        llm_truncate_chars=int(row.llm_truncate_chars),
        max_pipeline_run_rows=int(row.max_pipeline_run_rows),
        max_llm_trace_rows=int(row.max_llm_trace_rows),
        langfuse_enabled=bool(row.langfuse_enabled),
    )


async def get_settings(session: AsyncSession) -> ObservabilitySettingsRead:
    return _to_settings(await _ensure_row(session))


async def update_settings(
    session: AsyncSession, body: ObservabilitySettingsUpdate
) -> ObservabilitySettingsRead:
    row = await _ensure_row(session)
    row.pipeline_logs_enabled = bool(body.pipeline_logs_enabled)
    row.llm_traces_enabled = bool(body.llm_traces_enabled)
    row.retention_days = int(body.retention_days)
    row.success_sample_rate = float(body.success_sample_rate)
    row.llm_record_full = bool(body.llm_record_full)
    row.llm_truncate_chars = int(body.llm_truncate_chars)
    row.max_pipeline_run_rows = int(body.max_pipeline_run_rows)
    row.max_llm_trace_rows = int(body.max_llm_trace_rows)
    row.langfuse_enabled = bool(body.langfuse_enabled)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    invalidate()
    return _to_settings(row)


async def list_pipeline_runs(
    session: AsyncSession,
    *,
    video_id: int | None = None,
    notebook_id: int | None = None,
    status: str | None = None,
    include_events: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> PipelineRunListResponse:
    limit = max(1, min(_MAX_LIST, limit))
    offset = max(0, offset)
    filters = [PipelineRun.status != "dropped"]
    if video_id is not None:
        filters.append(PipelineRun.video_id == video_id)
    if notebook_id is not None:
        # 兼容旧 run：notebook_id 为空时，经 notebook_sources 反查所属笔记本
        video_ids_subq = select(NotebookSource.video_id).where(
            NotebookSource.notebook_id == notebook_id
        )
        filters.append(
            or_(
                PipelineRun.notebook_id == notebook_id,
                PipelineRun.video_id.in_(video_ids_subq),
            )
        )
    if status:
        filters.append(PipelineRun.status == status)
    total = (
        await session.execute(select(func.count()).select_from(PipelineRun).where(*filters))
    ).scalar() or 0
    rows = (
        await session.execute(
            select(PipelineRun)
            .where(*filters)
            .order_by(PipelineRun.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    titles: dict[int, str | None] = {}
    vid_ids = {int(r.video_id) for r in rows if r.video_id is not None}
    if vid_ids:
        for vid, title in (
            await session.execute(select(Video.id, Video.title).where(Video.id.in_(vid_ids)))
        ).all():
            titles[int(vid)] = title

    events_by_run: dict[str, list[PipelineRunEvent]] = {r.run_id: [] for r in rows}
    if include_events and rows:
        ev_rows = (
            await session.execute(
                select(PipelineRunEvent)
                .where(PipelineRunEvent.run_id.in_([r.run_id for r in rows]))
                .order_by(PipelineRunEvent.run_id.asc(), PipelineRunEvent.seq.asc())
                .limit(5000)
            )
        ).scalars().all()
        for e in ev_rows:
            bucket = events_by_run.get(e.run_id)
            if bucket is not None and len(bucket) < 200:
                bucket.append(e)

    items: list[PipelineRunListItem] = []
    for row in rows:
        evs = events_by_run.get(row.run_id, [])
        if include_events:
            cnt = len(evs)
        else:
            cnt = (
                await session.execute(
                    select(func.count())
                    .select_from(PipelineRunEvent)
                    .where(PipelineRunEvent.run_id == row.run_id)
                )
            ).scalar() or 0
        items.append(
            _run_item(
                row,
                event_count=int(cnt),
                video_title=titles.get(int(row.video_id)) if row.video_id else None,
                events=[_event_item(e) for e in evs] if include_events else [],
            )
        )
    return PipelineRunListResponse(items=items, total=int(total))


async def get_pipeline_run(session: AsyncSession, run_id: str) -> PipelineRunDetail:
    row = (
        await session.execute(select(PipelineRun).where(PipelineRun.run_id == run_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("运行记录不存在")
    events = (
        await session.execute(
            select(PipelineRunEvent)
            .where(PipelineRunEvent.run_id == run_id)
            .order_by(PipelineRunEvent.seq.asc())
            .limit(500)
        )
    ).scalars().all()
    title = None
    if row.video_id is not None:
        title = (
            await session.execute(select(Video.title).where(Video.id == row.video_id))
        ).scalar_one_or_none()
    base = _run_item(
        row,
        event_count=len(events),
        video_title=title,
        events=[_event_item(e) for e in events],
    )
    return PipelineRunDetail(
        **base.model_dump(),
        celery_task_id=row.celery_task_id,
    )


def _event_item(e: PipelineRunEvent) -> PipelineRunEventItem:
    return PipelineRunEventItem(
        seq=e.seq,
        stage=e.stage,
        status=e.status,
        summary=e.summary,
        detail_json=e.detail_json,
        error_text=e.error_text,
        started_at=e.started_at,
        finished_at=e.finished_at,
        duration_ms=e.duration_ms,
    )


def _run_item(
    row: PipelineRun,
    *,
    event_count: int,
    video_title: str | None = None,
    events: list[PipelineRunEventItem] | None = None,
) -> PipelineRunListItem:
    return PipelineRunListItem(
        run_id=row.run_id,
        video_id=row.video_id,
        notebook_id=row.notebook_id,
        video_title=video_title,
        stage=row.stage,
        status=row.status,
        force=bool(row.force),
        error_summary=row.error_summary,
        started_at=row.started_at,
        finished_at=row.finished_at,
        duration_ms=row.duration_ms,
        event_count=event_count,
        events=events or [],
    )


async def list_llm_traces(
    session: AsyncSession,
    *,
    kind: str | None = None,
    status: str | None = None,
    notebook_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> LlmTraceListResponse:
    limit = max(1, min(_MAX_LIST, limit))
    offset = max(0, offset)
    filters = []
    if kind:
        filters.append(LlmTrace.kind == kind)
    if status:
        filters.append(LlmTrace.status == status)
    if notebook_id is not None:
        # Include legacy chat rows that only stored thread_id (pre-P0).
        thread_ids = select(ChatThread.id).where(ChatThread.notebook_id == notebook_id)
        filters.append(
            or_(
                LlmTrace.notebook_id == notebook_id,
                and_(
                    LlmTrace.notebook_id.is_(None),
                    LlmTrace.thread_id.in_(thread_ids),
                ),
            )
        )
    stmt_count = select(func.count()).select_from(LlmTrace)
    stmt = select(LlmTrace)
    if filters:
        stmt_count = stmt_count.where(*filters)
        stmt = stmt.where(*filters)
    total = (await session.execute(stmt_count)).scalar() or 0
    rows = list(
        (
            await session.execute(
                stmt.order_by(LlmTrace.started_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
    )
    nb_by_row = await _effective_notebook_ids(session, rows)
    titles = await _notebook_titles(session, list(nb_by_row.values()))
    return LlmTraceListResponse(
        items=[
            _trace_item(
                r,
                notebook_id=nb_by_row.get(id(r), r.notebook_id),
                notebook_title=titles.get(nb_by_row.get(id(r), r.notebook_id)),
            )
            for r in rows
        ],
        total=int(total),
    )


async def _effective_notebook_ids(
    session: AsyncSession, rows: list[LlmTrace]
) -> dict[int, int | None]:
    """Display fallback: chat traces missing notebook_id resolve via thread."""
    out: dict[int, int | None] = {id(r): r.notebook_id for r in rows}
    need_thread_ids = sorted(
        {
            int(r.thread_id)
            for r in rows
            if r.notebook_id is None and r.thread_id is not None
        }
    )
    if not need_thread_ids:
        return out
    mapping = dict(
        (
            await session.execute(
                select(ChatThread.id, ChatThread.notebook_id).where(
                    ChatThread.id.in_(need_thread_ids)
                )
            )
        ).all()
    )
    for r in rows:
        if r.notebook_id is None and r.thread_id is not None:
            nb = mapping.get(int(r.thread_id))
            if nb is not None:
                out[id(r)] = int(nb)
    return out


async def _notebook_titles(
    session: AsyncSession, notebook_ids: list[int | None]
) -> dict[int, str]:
    """含已软删笔记本标题，便于筛选后仍能显示名称。"""
    ids = sorted({i for i in notebook_ids if i is not None})
    if not ids:
        return {}
    rows = (
        await session.execute(select(Notebook.id, Notebook.title).where(Notebook.id.in_(ids)))
    ).all()
    return {int(r[0]): (r[1] or f"笔记本 #{r[0]}") for r in rows}


async def get_llm_trace(session: AsyncSession, trace_id: str) -> LlmTraceDetail:
    row = (
        await session.execute(select(LlmTrace).where(LlmTrace.trace_id == trace_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("追踪记录不存在")
    spans = (
        await session.execute(
            select(LlmSpan)
            .where(LlmSpan.trace_id == trace_id)
            .order_by(LlmSpan.seq.asc())
            .limit(200)
        )
    ).scalars().all()
    nb_map = await _effective_notebook_ids(session, [row])
    effective_nb = nb_map.get(id(row), row.notebook_id)
    titles = await _notebook_titles(session, [effective_nb])
    base = _trace_item(
        row, notebook_id=effective_nb, notebook_title=titles.get(effective_nb)
    )
    return LlmTraceDetail(
        **base.model_dump(),
        spans=[
            LlmSpanItem(
                seq=s.seq,
                name=s.name,
                role=s.role,
                content_text=s.content_text,
                content_chars=s.content_chars,
                truncated=bool(s.truncated),
                created_at=s.created_at,
            )
            for s in spans
        ],
    )


def _trace_item(
    row: LlmTrace,
    *,
    notebook_id: int | None = None,
    notebook_title: str | None = None,
) -> LlmTraceListItem:
    return LlmTraceListItem(
        trace_id=row.trace_id,
        kind=row.kind,
        status=row.status,
        notebook_id=row.notebook_id if notebook_id is None else notebook_id,
        notebook_title=notebook_title,
        video_id=row.video_id,
        thread_id=row.thread_id,
        message_id=row.message_id,
        provider=row.provider,
        model_name=row.model_name,
        latency_ms=row.latency_ms,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        error_text=row.error_text,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


async def trigger_purge(session: AsyncSession) -> dict[str, str]:
    await _ensure_row(session)
    request_purge()
    return {"status": "queued"}
