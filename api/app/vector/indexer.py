"""笔记本索引：拼文档 → embedding → upsert Qdrant → 更新状态表。"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.llm.config_service import get_active_embedding
from app.models.notebook import Notebook
from app.models.notebook_index import NotebookIndexState
from app.services.vector_settings import get_vector_settings_row
from app.vector.document import build_notebook_document
from app.vector.embeddings import EmbeddingError, embed_texts
from app.vector.store import VectorPoint, VectorStoreError, make_vector_store

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _get_or_create_state(
    session: AsyncSession, notebook_id: int
) -> NotebookIndexState:
    row = await session.get(NotebookIndexState, notebook_id)
    if row is None:
        row = NotebookIndexState(notebook_id=notebook_id, status="pending")
        session.add(row)
        await session.flush()
    return row


async def index_notebook(
    session: AsyncSession,
    notebook_id: int,
    *,
    force: bool = False,
) -> NotebookIndexState:
    nb = await session.get(Notebook, notebook_id)
    if nb is None or nb.deleted_at is not None:
        raise NotFoundError(f"notebook {notebook_id} 不存在")

    settings = await get_vector_settings_row(session)
    state = await _get_or_create_state(session, notebook_id)
    prev_hash = state.content_hash
    prev_status = state.status

    state.status = "indexing"
    state.index_error = None
    session.add(state)
    await session.commit()

    try:
        doc = await build_notebook_document(session, nb, settings)
        from sqlalchemy import func, select
        from app.models.notebook import NotebookSource

        source_count = int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(NotebookSource)
                    .where(NotebookSource.notebook_id == notebook_id)
                )
            )
            or 0
        )
        # 空壳：无来源且无笔记正文 → 不进向量库（标题/描述 alone 易假阳性）
        has_notes = "notes" in doc.parts_used
        is_empty_shell = (not doc.text.strip()) or (source_count == 0 and not has_notes)
        if is_empty_shell:
            # 删掉旧点，避免空壳继续污染检索
            try:
                store = make_vector_store(
                    backend=settings.vector_backend,
                    qdrant_url=settings.qdrant_url,
                    qdrant_collection=settings.qdrant_collection,
                    qdrant_api_key=settings.qdrant_api_key,
                )
                await store.delete(notebook_id)
            except VectorStoreError as exc:
                logger.warning(
                    "delete skipped-point failed notebook_id=%s err=%s",
                    notebook_id,
                    exc,
                )
            state = await _get_or_create_state(session, notebook_id)
            state.status = "skipped"
            state.content_hash = doc.content_hash
            if not doc.text.strip():
                state.index_error = "没有可索引的文本（检查索引字段开关与笔记本内容）"
            else:
                state.index_error = "空壳笔记本（无来源且无笔记），已跳过索引"
            state.indexed_at = _now()
            state.model_name = None
            state.vector_dim = None
            session.add(state)
            await session.commit()
            await session.refresh(state)
            return state

        if (
            not force
            and prev_status == "ready"
            and prev_hash
            and prev_hash == doc.content_hash
        ):
            state = await _get_or_create_state(session, notebook_id)
            state.status = "ready"
            state.index_error = None
            session.add(state)
            await session.commit()
            await session.refresh(state)
            return state

        try:
            emb = await get_active_embedding(session)
        except NotFoundError as exc:
            raise EmbeddingError(str(exc)) from exc

        vectors = await embed_texts(emb, [doc.text[:30000]])
        vector = vectors[0]
        dim = len(vector)

        store = make_vector_store(
            backend=settings.vector_backend,
            qdrant_url=settings.qdrant_url,
            qdrant_collection=settings.qdrant_collection,
            qdrant_api_key=settings.qdrant_api_key,
        )
        await store.ensure_collection(dim)
        await store.upsert(
            VectorPoint(
                notebook_id=notebook_id,
                vector=vector,
                payload={
                    "title": nb.title,
                    "owner_id": nb.owner_id,
                    "share_all": bool(nb.share_all),
                    "parts": doc.parts_used,
                    "content_hash": doc.content_hash,
                    "model_name": emb.model_name,
                },
            )
        )

        state = await _get_or_create_state(session, notebook_id)
        state.status = "ready"
        state.content_hash = doc.content_hash
        state.model_name = emb.model_name
        state.vector_dim = dim
        state.indexed_at = _now()
        state.index_error = None
        session.add(state)
        await session.commit()
        await session.refresh(state)
        logger.info(
            "indexed notebook_id=%s dim=%s parts=%s",
            notebook_id,
            dim,
            ",".join(doc.parts_used),
        )
        return state
    except (EmbeddingError, VectorStoreError, NotFoundError) as exc:
        state = await _get_or_create_state(session, notebook_id)
        state.status = "failed"
        state.index_error = str(exc)[:2000]
        session.add(state)
        await session.commit()
        await session.refresh(state)
        logger.warning("index failed notebook_id=%s err=%s", notebook_id, exc)
        return state
    except Exception as exc:  # noqa: BLE001
        state = await _get_or_create_state(session, notebook_id)
        state.status = "failed"
        state.index_error = f"{exc.__class__.__name__}: {exc}"[:2000]
        session.add(state)
        await session.commit()
        await session.refresh(state)
        logger.exception("index unexpected failure notebook_id=%s", notebook_id)
        return state


def state_to_dict(state: NotebookIndexState | None, notebook_id: int) -> dict:
    if state is None:
        return {
            "notebook_id": notebook_id,
            "status": "pending",
            "content_hash": None,
            "model_name": None,
            "vector_dim": None,
            "indexed_at": None,
            "index_error": None,
        }
    return {
        "notebook_id": state.notebook_id,
        "status": state.status,
        "content_hash": state.content_hash,
        "model_name": state.model_name,
        "vector_dim": state.vector_dim,
        "indexed_at": state.indexed_at.isoformat() if state.indexed_at else None,
        "index_error": state.index_error,
    }
