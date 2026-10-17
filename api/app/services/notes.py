"""把一条助手回答存成笔记。同一条回答重复保存时返回原来的笔记。"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError
from app.models.notebook import ChatMessage, ChatThread, Note, Notebook


def note_dict(note: Note) -> dict:
    created = note.created_at
    return {
        "id": note.id,
        "notebook_id": note.notebook_id,
        "message_id": note.message_id,
        "title": note.title,
        "content_text": note.content_text,
        "citations": note.citations_json or [],
        "created_at": created.isoformat() if created else None,
    }


async def list_notes(session: AsyncSession, *, owner_id: int, notebook_id: int) -> list[dict]:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None or notebook.owner_id != owner_id or notebook.deleted_at is not None:
        raise NotFoundError(f"notebook {notebook_id} 不存在")
    rows = (
        await session.execute(
            select(Note)
            .where(Note.notebook_id == notebook_id, Note.deleted_at.is_(None))
            .order_by(Note.id.desc())
        )
    ).scalars().all()
    return [note_dict(row) for row in rows]


async def note_ids_for_messages(session: AsyncSession, message_ids: list[int]) -> dict[int, int]:
    if not message_ids:
        return {}
    rows = (
        await session.execute(
            select(Note.message_id, Note.id).where(
                Note.message_id.in_(message_ids),
                Note.deleted_at.is_(None),
            )
        )
    ).all()
    return {message_id: note_id for message_id, note_id in rows if message_id is not None}


async def save_message_as_note(
    session: AsyncSession, *, owner_id: int, message_id: int
) -> dict:
    row = (
        await session.execute(
            select(ChatMessage, ChatThread, Notebook)
            .join(ChatThread, ChatThread.id == ChatMessage.thread_id)
            .join(Notebook, Notebook.id == ChatThread.notebook_id)
            .where(ChatMessage.id == message_id)
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("消息不存在")
    message, _thread, notebook = row
    if notebook.owner_id != owner_id or notebook.deleted_at is not None:
        raise NotFoundError("消息不存在")
    if message.role != "assistant":
        raise BadRequestError("只能保存助手的回答")
    existing = (
        await session.execute(
            select(Note).where(Note.message_id == message.id, Note.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if existing is not None:
        return note_dict(existing)
    note = Note(
        notebook_id=notebook.id,
        author_id=owner_id,
        message_id=message.id,
        title=_title(message.content_text),
        content_text=message.content_text,
        citations_json=message.citations_json or [],
    )
    session.add(note)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        again = (
            await session.execute(select(Note).where(Note.message_id == message.id))
        ).scalar_one()
        return note_dict(again)
    await session.refresh(note)
    return note_dict(note)


async def rename_note(
    session: AsyncSession, *, owner_id: int, note_id: int, title: str
) -> dict:
    note = await _owned_note(session, owner_id=owner_id, note_id=note_id)
    note.title = title.strip()[:255]
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note_dict(note)


async def delete_note(session: AsyncSession, *, owner_id: int, note_id: int) -> None:
    note = await _owned_note(session, owner_id=owner_id, note_id=note_id)
    note.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    note.message_id = None
    session.add(note)
    await session.commit()


async def _owned_note(session: AsyncSession, *, owner_id: int, note_id: int) -> Note:
    note = await session.get(Note, note_id)
    if note is None or note.deleted_at is not None:
        raise NotFoundError("笔记不存在")
    notebook = await session.get(Notebook, note.notebook_id)
    if notebook is None or notebook.owner_id != owner_id or notebook.deleted_at is not None:
        raise NotFoundError("笔记不存在")
    return note


def _title(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip().lstrip("#").replace("**", "").replace("*", "").strip()
        if cleaned:
            return cleaned[:80]
    return "笔记"
