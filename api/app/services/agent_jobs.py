"""Agent 门面的异步任务：复用封面与知识底稿服务，不在结果里放媒体字节。"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, BadRequestError
from app.db.session import get_sessionmaker
from app.models.agent_token import AgentJob
from app.services.agent_tokens import iso
from app.services.cover_url import expand_cover_url

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _error_text(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return (exc.message or "任务失败")[:2000]
    return "任务失败"


def present_job(job: AgentJob, *, origin: str) -> dict:
    from app.agent.urls import absolute_url

    result = None
    if isinstance(job.result_json, dict):
        result = dict(job.result_json)
        cover_storage = result.pop("cover_storage", None)
        if cover_storage:
            result["cover_url"] = absolute_url(origin, expand_cover_url(str(cover_storage)))
        elif result.get("cover_url"):
            result["cover_url"] = absolute_url(origin, result.get("cover_url"))
    next_step = None
    if job.kind == "generate_draft" and job.status == "succeeded":
        next_step = "调用 get_draft(notebook_id) 读取知识底稿全文；产物页也会有对应底稿任务。"
    elif job.kind == "generate_draft" and job.status == "failed":
        next_step = "可再次 generate_draft；成功后用 get_draft 读正文（底稿不在 list_artifacts）。"
    return {
        "job_id": int(job.id),
        "kind": job.kind,
        "status": job.status,
        "notebook_id": job.notebook_id,
        "result": result,
        "error": job.error_message,
        "next_step": next_step,
        "created_at": iso(job.created_at),
        "finished_at": iso(job.finished_at),
    }


async def enqueue_job(
    session: AsyncSession,
    *,
    owner_id: int,
    kind: str,
    notebook_id: int | None,
    payload: dict,
) -> AgentJob:
    job = AgentJob(
        owner_id=owner_id,
        notebook_id=notebook_id,
        kind=kind,
        status="queued",
        payload_json=payload,
        result_json=None,
        error_message=None,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    kick_agent_job(int(job.id))
    return job


def kick_agent_job(job_id: int) -> None:
    """测试环境不自动跑，避免打到真实模型。本地与线上在当前事件循环里执行。"""
    if get_settings().app_env == "test":
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("no running loop for agent job %s", job_id)
        return

    async def _go() -> None:
        try:
            await run_agent_job(job_id)
        except Exception:
            logger.exception("agent job %s crashed", job_id)

    loop.create_task(_go())


async def run_agent_job(job_id: int) -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        job = await session.get(AgentJob, job_id)
        if job is None or job.status in {"succeeded", "failed"}:
            return
        job.status = "running"
        job.error_message = None
        session.add(job)
        await session.commit()
        try:
            result = await _execute(session, job)
            encoded = json.loads(json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            await session.rollback()
            failed = await session.get(AgentJob, job_id)
            if failed is None:
                return
            failed.status = "failed"
            failed.error_message = _error_text(exc)
            failed.finished_at = _now()
            session.add(failed)
            await session.commit()
            if not isinstance(exc, AppError):
                logger.exception("agent job %s failed", job_id)
            return
        done = await session.get(AgentJob, job_id)
        if done is None:
            return
        done.status = "succeeded"
        done.result_json = encoded
        done.error_message = None
        done.finished_at = _now()
        session.add(done)
        await session.commit()


async def _execute(session: AsyncSession, job: AgentJob) -> dict:
    payload = job.payload_json if isinstance(job.payload_json, dict) else {}
    if job.kind == "generate_cover":
        return await _run_cover(session, owner_id=int(job.owner_id), payload=payload)
    if job.kind == "generate_draft":
        return await _run_draft(session, owner_id=int(job.owner_id), payload=payload)
    raise BadRequestError(f"未知任务 {job.kind}")


async def _run_cover(session: AsyncSession, *, owner_id: int, payload: dict) -> dict:
    from app.services import cover_generate
    from app.services import notebooks as notebooks_svc

    notebook_id = int(payload["notebook_id"])
    notebook = await notebooks_svc.get_notebook(
        session, owner_id=owner_id, notebook_id=notebook_id
    )
    title = (payload.get("title") or notebook.title or "").strip()
    description = payload.get("description")
    if description is None:
        description = notebook.description
    result = await cover_generate.generate_cover(
        session, title=title, description=description
    )
    cover_ref = result.get("storage_key") or result.get("cover_url")
    await notebooks_svc.update_notebook(
        session,
        owner_id=owner_id,
        notebook_id=notebook_id,
        cover_url=cover_ref,
        cover_url_set=True,
    )
    stored = await notebooks_svc.get_notebook(
        session, owner_id=owner_id, notebook_id=notebook_id
    )
    return {"notebook_id": notebook_id, "cover_storage": stored.cover_url}


async def _run_draft(session: AsyncSession, *, owner_id: int, payload: dict) -> dict:
    from sqlalchemy import select

    from app.models.draft_strategy import DraftStrategy
    from app.schemas.knowledge_draft import KnowledgeDraftGenerateRequest
    from app.services import knowledge_draft as draft_svc
    from app.services import notebooks as notebooks_svc
    from app.services.draft_strategy import seed_builtin_strategies

    notebook_id = int(payload["notebook_id"])
    await notebooks_svc.get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)

    video_ids = payload.get("video_ids")
    note_ids = payload.get("note_ids")
    if video_ids is None and note_ids is None:
        sources = await notebooks_svc.list_sources(
            session, owner_id=owner_id, notebook_id=notebook_id
        )
        ready = [item.video_id for item in sources if item.video.subtitle_status == "ready"]
        video_ids = ready or [item.video_id for item in sources]
        note_ids = []
    else:
        video_ids = list(video_ids or [])
        note_ids = list(note_ids or [])

    await seed_builtin_strategies(session)
    strategy_id = payload.get("strategy_id")
    if strategy_id is None:
        row = await session.scalar(
            select(DraftStrategy)
            .where(DraftStrategy.enabled.is_(True), DraftStrategy.apply_default.is_(True))
            .order_by(DraftStrategy.id.asc())
            .limit(1)
        )
        if row is None:
            row = await session.scalar(
                select(DraftStrategy)
                .where(DraftStrategy.enabled.is_(True))
                .order_by(DraftStrategy.id.asc())
                .limit(1)
            )
        if row is None:
            raise BadRequestError("没有可用的底稿策略")
        strategy_id = int(row.id)

    try:
        body = KnowledgeDraftGenerateRequest(
            strategy_id=int(strategy_id),
            language=payload.get("language") or "中文",
            video_ids=[int(item) for item in video_ids],
            note_ids=[int(item) for item in note_ids],
            focus=payload.get("focus") or None,
            extra_constraints=payload.get("extra_constraints") or None,
        )
    except ValidationError as exc:
        raise BadRequestError("底稿参数不正确") from exc

    result = await draft_svc.generate_draft(
        session, owner_id=owner_id, notebook_id=notebook_id, body=body
    )
    if hasattr(result, "model_dump"):
        data = result.model_dump(mode="json")
    else:
        data = dict(result)
    return {"notebook_id": notebook_id, "draft": data}
