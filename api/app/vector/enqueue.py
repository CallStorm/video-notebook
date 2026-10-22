"""API 侧：把笔记本索引任务丢进 media Celery 队列。"""
from __future__ import annotations

import logging

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
