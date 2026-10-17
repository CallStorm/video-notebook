"""笔记本对话与来源勾选。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import service as chat_svc
from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.chat import ChatRequest, SourceSelection
from app.schemas.notebook import NoteRename
from app.services.notes import delete_note, rename_note, save_message_as_note

router = APIRouter(tags=["chat"])


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/notebooks/{notebook_id}/chat")
async def get_chat(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    messages = await chat_svc.list_messages(
        session, owner_id=user.id, notebook_id=notebook_id
    )
    return {"messages": messages}


@router.post("/notebooks/{notebook_id}/chat")
async def post_chat(
    notebook_id: int,
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    prepared = await chat_svc.prepare_chat(
        session,
        owner_id=user.id,
        notebook_id=notebook_id,
        message=body.message,
        source_ids=body.source_ids,
        note_ids=body.note_ids,
    )

    async def events():
        async for event in chat_svc.stream_answer(prepared):
            yield _sse(event)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/messages/{message_id}/save_as_note")
async def post_save_as_note(
    message_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await save_message_as_note(session, owner_id=user.id, message_id=message_id)


@router.patch("/notes/{note_id}")
async def patch_note(
    note_id: int,
    body: NoteRename,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await rename_note(session, owner_id=user.id, note_id=note_id, title=body.title)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_note(
    note_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    await delete_note(session, owner_id=user.id, note_id=note_id)
    return None


@router.patch("/notebooks/{notebook_id}/sources/selection")
async def patch_all_selection(
    notebook_id: int,
    body: SourceSelection,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    await chat_svc.set_selected(
        session,
        owner_id=user.id,
        notebook_id=notebook_id,
        selected=body.selected_for_chat,
    )
    return {"ok": True}


@router.patch("/notebooks/{notebook_id}/sources/{video_id}")
async def patch_source_selection(
    notebook_id: int,
    video_id: int,
    body: SourceSelection,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    await chat_svc.set_selected(
        session,
        owner_id=user.id,
        notebook_id=notebook_id,
        selected=body.selected_for_chat,
        video_id=video_id,
    )
    return {"ok": True}
