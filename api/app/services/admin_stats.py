"""Admin 运营总览：一次聚合返回大屏指标。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.notebook import Note, Notebook, NotebookSource, Video
from app.models.notebook_index import NotebookIndexState
from app.models.observability import (
    LlmTrace,
    PipelineRunEvent,
)
from app.models.studio import StudioTask
from app.schemas.admin_stats import (
    AdminStatsResponse,
    CallCount,
    ContentStats,
    DailyCount,
    FailureStats,
    FailureTopItem,
    ModelCallsStats,
    ObservabilityFlags,
    QueueStats,
    ReadinessRate,
    ReadinessStats,
    TokenStats,
)
from app.services import observability as obs_svc

logger = logging.getLogger(__name__)

_STAGE_LABEL = {
    "enqueue": "入队",
    "fetch": "抓取",
    "subtitle": "字幕",
    "asr": "语音转文字",
    "overview": "概览",
    "vector": "向量",
}


def _rate(ready: int, total: int) -> ReadinessRate:
    if total <= 0:
        return ReadinessRate(ready=ready, total=total, rate=None)
    return ReadinessRate(ready=ready, total=total, rate=round(ready / total, 4))


def _utc_day_start(days_ago: int = 0) -> datetime:
    now = datetime.utcnow()
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=days_ago)


def _day_keys(n: int = 7) -> list[str]:
    """近 n 个 UTC 日历日，旧→新。"""
    start = _utc_day_start(n - 1)
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


def _celery_queue_depths() -> tuple[int | None, int | None, bool, str | None]:
    """LLEN Celery Redis 队列 media / studio（broker db）。"""
    try:
        import redis

        url = get_settings().celery_broker_url
        r = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=1.5)
        media = int(r.llen("media"))
        studio = int(r.llen("studio"))
        return media, studio, True, None
    except Exception as exc:  # noqa: BLE001
        logger.warning("admin_stats redis LLEN failed: %s", exc)
        return None, None, False, str(exc)[:200]


async def _content(session: AsyncSession) -> ContentStats:
    nb = await session.scalar(
        select(func.count()).select_from(Notebook).where(Notebook.deleted_at.is_(None))
    )
    share = await session.scalar(
        select(func.count())
        .select_from(Notebook)
        .where(Notebook.deleted_at.is_(None), Notebook.share_all.is_(True))
    )
    # Only videos still linked to an alive notebook (orphan after nb soft-delete excluded)
    videos = await session.scalar(
        select(func.count(func.distinct(NotebookSource.video_id)))
        .select_from(NotebookSource)
        .join(Notebook, Notebook.id == NotebookSource.notebook_id)
        .where(Notebook.deleted_at.is_(None))
    )
    # Soft-deleted notes OR notes on soft-deleted notebooks do not count
    notes = await session.scalar(
        select(func.count())
        .select_from(Note)
        .join(Notebook, Notebook.id == Note.notebook_id)
        .where(Note.deleted_at.is_(None), Notebook.deleted_at.is_(None))
    )
    return ContentStats(
        notebooks=int(nb or 0),
        videos=int(videos or 0),
        notes=int(notes or 0),
        share_all_notebooks=int(share or 0),
    )


async def _model_calls_and_tokens(
    session: AsyncSession, *, llm_enabled: bool, pipeline_enabled: bool
) -> tuple[ModelCallsStats, TokenStats]:
    days = _day_keys(7)
    since = _utc_day_start(6)

    # LLM totals + daily
    llm_total: int | None
    llm_by_day: dict[str, int] = {d: 0 for d in days}
    if not llm_enabled:
        llm_call = CallCount(
            count=None,
            unavailable=True,
            reason="LLM 追踪未开启，开启后计入 llm_traces",
        )
        llm_total = None
    else:
        llm_total_v = await session.scalar(select(func.count()).select_from(LlmTrace))
        llm_total = int(llm_total_v or 0)
        llm_call = CallCount(count=llm_total, unavailable=False)
        # MySQL/SQLite 兼容：用 DATE(started_at) / strftime
        bind = session.get_bind()
        dialect = bind.dialect.name if bind is not None else "sqlite"
        if dialect == "sqlite":
            day_expr = func.strftime("%Y-%m-%d", LlmTrace.started_at)
        else:
            day_expr = func.date(LlmTrace.started_at)
        rows = (
            await session.execute(
                select(day_expr.label("d"), func.count().label("c"))
                .where(LlmTrace.started_at >= since)
                .group_by(day_expr)
            )
        ).all()
        for d, c in rows:
            key = str(d)[:10] if d is not None else None
            if key in llm_by_day:
                llm_by_day[key] = int(c)

    # ASR from pipeline events (ok|started)，依赖流水线日志
    asr_by_day: dict[str, int] = {d: 0 for d in days}
    if not pipeline_enabled:
        asr_call = CallCount(
            count=None,
            unavailable=True,
            reason="流水线日志未开启；ASR 次数依赖 pipeline_run_events",
        )
    else:
        bind = session.get_bind()
        dialect = bind.dialect.name if bind is not None else "sqlite"
        if dialect == "sqlite":
            day_expr = func.strftime("%Y-%m-%d", PipelineRunEvent.started_at)
        else:
            day_expr = func.date(PipelineRunEvent.started_at)
        # 优先计 ok；若无 ok 则 started 也算一次尝试（避免只记 started 翻倍：用 ok+skipped 以外的终态）
        # 口径：stage=asr 且 status in ('ok','started') 去重按 run 太贵，这里简单 COUNT status='ok'，
        # 若 ok=0 再回退 COUNT status='started'。
        asr_ok = await session.scalar(
            select(func.count())
            .select_from(PipelineRunEvent)
            .where(
                PipelineRunEvent.stage == "asr",
                PipelineRunEvent.status == "ok",
            )
        )
        if int(asr_ok or 0) > 0:
            asr_status = "ok"
            asr_total = int(asr_ok)
        else:
            asr_started = await session.scalar(
                select(func.count())
                .select_from(PipelineRunEvent)
                .where(
                    PipelineRunEvent.stage == "asr",
                    PipelineRunEvent.status == "started",
                )
            )
            asr_status = "started"
            asr_total = int(asr_started or 0)
        asr_call = CallCount(
            count=asr_total,
            unavailable=False,
            reason=f"估自 pipeline_run_events stage=asr status={asr_status}（依赖流水线日志）",
        )
        rows = (
            await session.execute(
                select(day_expr.label("d"), func.count().label("c"))
                .where(
                    PipelineRunEvent.stage == "asr",
                    PipelineRunEvent.status == asr_status,
                    PipelineRunEvent.started_at >= since,
                )
                .group_by(day_expr)
            )
        ).all()
        for d, c in rows:
            key = str(d)[:10] if d is not None else None
            if key in asr_by_day:
                asr_by_day[key] = int(c)

    embed_call = CallCount(
        count=None, unavailable=True, reason="Embed 暂无埋点，待接入后统计"
    )
    tts_call = CallCount(
        count=None, unavailable=True, reason="文字转语音尚未接入调用链"
    )

    # Token：字段已有，但写入侧尚未落 usage → 检查是否有任何非空
    token_sum = await session.scalar(
        select(
            func.coalesce(func.sum(LlmTrace.prompt_tokens), 0)
            + func.coalesce(func.sum(LlmTrace.completion_tokens), 0)
        ).select_from(LlmTrace)
    )
    any_usage = await session.scalar(
        select(func.count())
        .select_from(LlmTrace)
        .where(
            (LlmTrace.prompt_tokens.is_not(None))
            | (LlmTrace.completion_tokens.is_not(None))
        )
    )
    tokens_by_day: dict[str, int | None] = {d: None for d in days}
    if not llm_enabled:
        token_stats = TokenStats(
            total=None,
            unavailable=True,
            reason="LLM 追踪未开启",
            trend_7d=[],
        )
    elif int(any_usage or 0) == 0:
        token_stats = TokenStats(
            total=None,
            unavailable=True,
            reason="调用尚未写入 token usage，接口字段已预留",
            trend_7d=[],
        )
    else:
        bind = session.get_bind()
        dialect = bind.dialect.name if bind is not None else "sqlite"
        if dialect == "sqlite":
            day_expr = func.strftime("%Y-%m-%d", LlmTrace.started_at)
        else:
            day_expr = func.date(LlmTrace.started_at)
        tok_expr = func.coalesce(LlmTrace.prompt_tokens, 0) + func.coalesce(
            LlmTrace.completion_tokens, 0
        )
        rows = (
            await session.execute(
                select(day_expr.label("d"), func.sum(tok_expr).label("t"))
                .where(LlmTrace.started_at >= since)
                .group_by(day_expr)
            )
        ).all()
        for d in days:
            tokens_by_day[d] = 0
        for d, t in rows:
            key = str(d)[:10] if d is not None else None
            if key in tokens_by_day:
                tokens_by_day[key] = int(t or 0)
        token_stats = TokenStats(
            total=int(token_sum or 0),
            unavailable=False,
            reason=None,
            trend_7d=[],
        )

    trend: list[DailyCount] = []
    for d in days:
        trend.append(
            DailyCount(
                date=d,
                llm=None if llm_call.unavailable else llm_by_day.get(d, 0),
                embed=None,
                asr=None if asr_call.unavailable else asr_by_day.get(d, 0),
                tts=None,
                tokens=tokens_by_day.get(d),
            )
        )

    if token_stats.unavailable:
        token_stats.trend_7d = [
            DailyCount(date=d, tokens=None) for d in days
        ]
    else:
        token_stats.trend_7d = [
            DailyCount(date=d, tokens=tokens_by_day.get(d)) for d in days
        ]

    model = ModelCallsStats(
        llm=llm_call,
        embed=embed_call,
        asr=asr_call,
        tts=tts_call,
        trend_7d=trend,
    )
    return model, token_stats


async def _queues(session: AsyncSession) -> QueueStats:
    media_d, studio_d, ok, err = _celery_queue_depths()
    backlog = await session.scalar(
        select(func.count())
        .select_from(NotebookIndexState)
        .join(Notebook, Notebook.id == NotebookIndexState.notebook_id)
        .where(
            Notebook.deleted_at.is_(None),
            NotebookIndexState.status.in_(("pending", "indexing")),
        )
    )
    studio_queued = await session.scalar(
        select(func.count())
        .select_from(StudioTask)
        .where(
            StudioTask.deleted_at.is_(None),
            StudioTask.status.in_(("queued", "pending")),
        )
    )
    # 兼容可能的 status 命名
    if int(studio_queued or 0) == 0:
        studio_queued = await session.scalar(
            select(func.count())
            .select_from(StudioTask)
            .where(StudioTask.deleted_at.is_(None), StudioTask.status == "queued")
        )
    return QueueStats(
        media_depth=media_d,
        studio_depth=studio_d,
        index_backlog=int(backlog or 0),
        studio_queued=int(studio_queued or 0),
        redis_ok=ok,
        redis_error=err,
    )


async def _readiness(session: AsyncSession) -> ReadinessStats:
    # Scope videos to those still attached to undeleted notebooks
    active_video = (
        select(NotebookSource.video_id)
        .join(Notebook, Notebook.id == NotebookSource.notebook_id)
        .where(Notebook.deleted_at.is_(None))
        .distinct()
        .scalar_subquery()
    )
    video_total = int(
        await session.scalar(
            select(func.count()).select_from(Video).where(Video.id.in_(active_video))
        )
        or 0
    )
    sub_ready = int(
        await session.scalar(
            select(func.count())
            .select_from(Video)
            .where(Video.id.in_(active_video), Video.subtitle_status == "ready")
        )
        or 0
    )
    ov_ready = int(
        await session.scalar(
            select(func.count())
            .select_from(Video)
            .where(Video.id.in_(active_video), Video.overview_status == "ready")
        )
        or 0
    )

    nb_total = int(
        await session.scalar(
            select(func.count()).select_from(Notebook).where(Notebook.deleted_at.is_(None))
        )
        or 0
    )
    vec_ready = int(
        await session.scalar(
            select(func.count())
            .select_from(NotebookIndexState)
            .join(Notebook, Notebook.id == NotebookIndexState.notebook_id)
            .where(
                Notebook.deleted_at.is_(None),
                NotebookIndexState.status == "ready",
            )
        )
        or 0
    )

    # 完整就绪：至少 1 个来源；所有来源字幕+概览 ready；索引 ready
    # 用聚合：对每个 notebook 统计来源数、未就绪来源数
    src_stats = (
        await session.execute(
            select(
                NotebookSource.notebook_id,
                func.count().label("src_n"),
                func.sum(
                    case(
                        (
                            and_(
                                Video.subtitle_status == "ready",
                                Video.overview_status == "ready",
                            ),
                            0,
                        ),
                        else_=1,
                    )
                ).label("bad_n"),
            )
            .join(Video, Video.id == NotebookSource.video_id)
            .join(Notebook, Notebook.id == NotebookSource.notebook_id)
            .where(Notebook.deleted_at.is_(None))
            .group_by(NotebookSource.notebook_id)
        )
    ).all()
    ready_ids = {
        int(r.notebook_id)
        for r in (
            await session.execute(
                select(NotebookIndexState.notebook_id).where(
                    NotebookIndexState.status == "ready"
                )
            )
        ).all()
    }
    alive = {
        int(r)
        for r in (
            await session.execute(
                select(Notebook.id).where(Notebook.deleted_at.is_(None))
            )
        ).scalars()
    }
    complete = 0
    eligible = 0
    for row in src_stats:
        nid = int(row.notebook_id)
        if nid not in alive:
            continue
        src_n = int(row.src_n or 0)
        if src_n <= 0:
            continue
        eligible += 1
        bad = int(row.bad_n or 0)
        if bad == 0 and nid in ready_ids:
            complete += 1

    return ReadinessStats(
        subtitle=_rate(sub_ready, video_total),
        overview=_rate(ov_ready, video_total),
        vector=_rate(vec_ready, nb_total),
        complete_notebooks=_rate(complete, eligible),
    )


async def _failures(
    session: AsyncSession, *, pipeline_enabled: bool
) -> FailureStats:
    since = datetime.utcnow() - timedelta(hours=24)
    note = None
    if not pipeline_enabled:
        note = "流水线日志未开启，失败 TOP 可能为空或不完整"
    rows = (
        await session.execute(
            select(PipelineRunEvent.stage, func.count().label("c"))
            .where(
                PipelineRunEvent.status == "failed",
                PipelineRunEvent.started_at >= since,
            )
            .group_by(PipelineRunEvent.stage)
            .order_by(func.count().desc())
            .limit(8)
        )
    ).all()
    top = [
        FailureTopItem(
            stage=str(stage),
            count=int(c),
            label=_STAGE_LABEL.get(str(stage), str(stage)),
        )
        for stage, c in rows
    ]
    # 业务表补充：若事件为空，用视频/索引 failed 作辅
    if not top:
        extras: list[FailureTopItem] = []
        active_video = (
            select(NotebookSource.video_id)
            .join(Notebook, Notebook.id == NotebookSource.notebook_id)
            .where(Notebook.deleted_at.is_(None))
            .distinct()
            .scalar_subquery()
        )
        sub_f = int(
            await session.scalar(
                select(func.count())
                .select_from(Video)
                .where(Video.id.in_(active_video), Video.subtitle_status == "failed")
            )
            or 0
        )
        ov_f = int(
            await session.scalar(
                select(func.count())
                .select_from(Video)
                .where(Video.id.in_(active_video), Video.overview_status == "failed")
            )
            or 0
        )
        idx_f = int(
            await session.scalar(
                select(func.count())
                .select_from(NotebookIndexState)
                .join(Notebook, Notebook.id == NotebookIndexState.notebook_id)
                .where(
                    Notebook.deleted_at.is_(None),
                    NotebookIndexState.status == "failed",
                )
            )
            or 0
        )
        stu_f = int(
            await session.scalar(
                select(func.count())
                .select_from(StudioTask)
                .where(
                    StudioTask.deleted_at.is_(None),
                    StudioTask.status == "failed",
                )
            )
            or 0
        )
        if sub_f:
            extras.append(
                FailureTopItem(stage="subtitle_biz", count=sub_f, label="字幕失败(业务)")
            )
        if ov_f:
            extras.append(
                FailureTopItem(stage="overview_biz", count=ov_f, label="概览失败(业务)")
            )
        if idx_f:
            extras.append(
                FailureTopItem(stage="vector_biz", count=idx_f, label="向量失败(业务)")
            )
        if stu_f:
            extras.append(
                FailureTopItem(stage="studio_biz", count=stu_f, label="产物失败")
            )
        extras.sort(key=lambda x: x.count, reverse=True)
        top = extras[:8]
        if extras and note is None:
            note = "近 24h 无流水线失败事件，以下为业务表当前失败存量"
    return FailureStats(top=top, window_hours=24, note=note)


async def get_admin_stats(session: AsyncSession) -> AdminStatsResponse:
    settings = await obs_svc.get_settings(session)
    flags = ObservabilityFlags(
        pipeline_logs_enabled=bool(settings.pipeline_logs_enabled),
        llm_traces_enabled=bool(settings.llm_traces_enabled),
    )
    content = await _content(session)
    model_calls, tokens = await _model_calls_and_tokens(
        session,
        llm_enabled=flags.llm_traces_enabled,
        pipeline_enabled=flags.pipeline_logs_enabled,
    )
    queues = await _queues(session)
    readiness = await _readiness(session)
    failures = await _failures(
        session, pipeline_enabled=flags.pipeline_logs_enabled
    )
    return AdminStatsResponse(
        observability=flags,
        content=content,
        model_calls=model_calls,
        tokens=tokens,
        queues=queues,
        readiness=readiness,
        failures=failures,
    )
