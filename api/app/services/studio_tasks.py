"""创建、列表、入队 Studio 任务。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError
from app.models.notebook import Note, NotebookSource
from app.models.studio import Agent, StudioCapability, StudioTask
from app.schemas.studio import TaskCreate
from app.services.notebooks import get_notebook

_ALLOWED_LANGUAGES = frozenset({"中文", "English"})


def enqueue_studio_task(task_id: int) -> None:
    from app.studio.worker import studio_run

    studio_run.delay(task_id)


async def list_enabled_capabilities(
    session: AsyncSession, *, owner_id: int, notebook_id: int
) -> list[StudioCapability]:
    await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    rows = (
        await session.execute(
            select(StudioCapability)
            .where(
                StudioCapability.enabled.is_(True),
                StudioCapability.deleted_at.is_(None),
            )
            .order_by(StudioCapability.id.asc())
        )
    ).scalars().all()
    return list(rows)


async def list_tasks(
    session: AsyncSession, *, owner_id: int, notebook_id: int
) -> list[StudioTask]:
    await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    rows = (
        await session.execute(
            select(StudioTask)
            .where(
                StudioTask.notebook_id == notebook_id,
                StudioTask.deleted_at.is_(None),
            )
            .order_by(StudioTask.id.desc())
        )
    ).scalars().all()
    return list(rows)


async def create_task(
    session: AsyncSession, *, owner_id: int, notebook_id: int, body: TaskCreate
) -> StudioTask:
    await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    cap = await session.get(StudioCapability, body.capability_id)
    if cap is None or cap.deleted_at is not None or not cap.enabled:
        raise BadRequestError("能力未启用")
    if cap.agent_id is None:
        raise BadRequestError("智能体未启用")
    agent = await session.get(Agent, cap.agent_id)
    if agent is None or agent.deleted_at is not None or not agent.is_active:
        raise BadRequestError("智能体未启用")

    form = cap.form_json or []
    has_sources = any(field.get("type") == "sources" for field in form)
    has_language = any(field.get("type") == "language" for field in form)
    text_fields = [field for field in form if field.get("type") == "text"]

    if has_language:
        if body.language not in _ALLOWED_LANGUAGES:
            raise BadRequestError("语言无效")
    elif body.language is not None:
        raise BadRequestError("表单没有语言字段")

    if has_sources:
        if not body.video_ids and not body.note_ids:
            raise BadRequestError("请选择来源")
        await _require_notebook_videos(session, notebook_id, body.video_ids)
        await _require_notebook_notes(session, notebook_id, body.note_ids)
    elif body.video_ids or body.note_ids:
        raise BadRequestError("表单没有来源字段")

    allowed_keys = {field["key"] for field in text_fields if "key" in field}
    extra = set(body.fields) - allowed_keys
    if extra:
        raise BadRequestError("未知字段")
    snapshot_fields: list[dict] = []
    for field in text_fields:
        key = field["key"]
        value = body.fields.get(key, "")
        if field.get("required") and not str(value).strip():
            raise BadRequestError("必填文本不能为空")
        snapshot_fields.append(
            {"key": key, "label": field.get("label") or "", "value": value}
        )

    task = StudioTask(
        notebook_id=notebook_id,
        owner_id=owner_id,
        capability_id=cap.id,
        agent_id=agent.id,
        format_key=cap.format_key,
        title=cap.name,
        status="queued",
        params_json={
            "language": body.language,
            "video_ids": list(body.video_ids),
            "note_ids": list(body.note_ids),
            "fields": snapshot_fields,
        },
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    try:
        enqueue_studio_task(task.id)
    except Exception:
        task.status = "failed"
        task.error_code = "process_failed"
        session.add(task)
        await session.commit()
        await session.refresh(task)
    return task


async def _require_notebook_videos(
    session: AsyncSession, notebook_id: int, video_ids: list[int]
) -> None:
    if not video_ids:
        return
    found = set(
        (
            await session.execute(
                select(NotebookSource.video_id).where(
                    NotebookSource.notebook_id == notebook_id,
                    NotebookSource.video_id.in_(video_ids),
                )
            )
        ).scalars().all()
    )
    if found != set(video_ids):
        raise BadRequestError("来源不属于该笔记本")


async def _require_notebook_notes(
    session: AsyncSession, notebook_id: int, note_ids: list[int]
) -> None:
    if not note_ids:
        return
    found = set(
        (
            await session.execute(
                select(Note.id).where(
                    Note.notebook_id == notebook_id,
                    Note.deleted_at.is_(None),
                    Note.id.in_(note_ids),
                )
            )
        ).scalars().all()
    )
    if found != set(note_ids):
        raise BadRequestError("来源不属于该笔记本")
