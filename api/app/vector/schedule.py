"""内容变更后排队索引。失败只记日志，不回滚已经保存的内容。"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def touch_notebook_index(notebook_id: int, *, force: bool = False) -> None:
    try:
        from app.vector.enqueue import enqueue_index_notebook

        enqueue_index_notebook(int(notebook_id), force=force)
    except Exception:
        logger.exception("auto index enqueue failed notebook_id=%s", notebook_id)
