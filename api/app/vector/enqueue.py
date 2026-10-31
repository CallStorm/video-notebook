"""API side: enqueue notebook index tasks; refresh indexes after media pipeline."""
from __future__ import annotations

import logging
import time
from datetime import datetime

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def enqueue_index_notebook(notebook_id: int, *, force: bool = False) -> None:
    if get_settings().app_env == "test":
        return
    from app.media.worker import celery_app

    celery_app.send_task(
        "vector.index_notebook",
        args=[int(notebook_id), bool(force)],
        queue="media",
    )
    logger.info(
        "enqueued vector.index_notebook notebook_id=%s force=%s",
        notebook_id,
        force,
    )


async def refresh_indexes_for_video(video_id: int) -> None:
    """After media/overview success: refresh vector indexes for notebooks that contain this video.

    Emits vector stage events on the current pipeline run. Index failures are logged only
    and do not fail the media run (media artifacts are already usable).
    """
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models.notebook import NotebookSource
    from app.observability.pipeline_log import current_run_id, log_event

    async with get_sessionmaker()() as session:
        nb_ids = list(
            (
                await session.execute(
                    select(NotebookSource.notebook_id)
                    .where(NotebookSource.video_id == int(video_id))
                    .order_by(NotebookSource.sort.asc())
                )
            )
            .scalars()
            .all()
        )

    if not nb_ids:
        if current_run_id():
            log_event(
                "vector",
                "skipped",
                summary="video not linked to any notebook",
                detail={"video_id": int(video_id)},
            )
        return

    for nid in nb_ids:
        await index_notebook_logged(int(nid), force=False)


async def index_notebook_logged(notebook_id: int, *, force: bool) -> str:
    """Run index_notebook and emit vector started/ok/skipped/failed on the current run.

    Returns final status string (ready|skipped|failed|...).
    """
    from app.db.session import get_sessionmaker
    from app.observability.pipeline_log import current_run_id, log_event
    from app.vector.indexer import index_notebook

    started = datetime.utcnow()
    t0 = time.perf_counter()
    rid = current_run_id()
    if rid:
        log_event(
            "vector",
            "started",
            summary=f"notebook_id={notebook_id}",
            detail={"notebook_id": notebook_id, "force": force},
            started_at=started,
        )
    try:
        async with get_sessionmaker()() as session:
            state = await index_notebook(session, notebook_id, force=force)
        ms = int((time.perf_counter() - t0) * 1000)
        st = (state.status or "failed") if state is not None else "failed"
        noop = bool(getattr(state, "_index_noop", False)) if state is not None else False
        if noop:
            st = "skipped"
        summary = (
            f"notebook_id={notebook_id} index unchanged, already ready"
            if noop
            else f"notebook_id={notebook_id} status={st}"
        )
        err = (state.index_error if state is not None else None) or None
        if st == "failed":
            if rid:
                log_event(
                    "vector",
                    "failed",
                    summary=summary,
                    error_text=(err or "")[:2000] or None,
                    started_at=started,
                    finished_at=datetime.utcnow(),
                    duration_ms=ms,
                )
        elif st == "skipped":
            if rid:
                log_event(
                    "vector",
                    "skipped",
                    summary=err or summary,
                    detail={"notebook_id": notebook_id},
                    started_at=started,
                    finished_at=datetime.utcnow(),
                    duration_ms=ms,
                )
        else:
            if rid:
                log_event(
                    "vector",
                    "ok",
                    summary=summary,
                    detail={
                        "notebook_id": notebook_id,
                        "vector_dim": getattr(state, "vector_dim", None),
                        "model_name": getattr(state, "model_name", None),
                    },
                    started_at=started,
                    finished_at=datetime.utcnow(),
                    duration_ms=ms,
                )
        return st
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        logger.exception(
            "vector refresh failed notebook_id=%s", notebook_id
        )
        if rid:
            log_event(
                "vector",
                "failed",
                summary=f"notebook_id={notebook_id}",
                error_text=str(exc)[:2000],
                started_at=started,
                finished_at=datetime.utcnow(),
                duration_ms=ms,
            )
        return "failed"
