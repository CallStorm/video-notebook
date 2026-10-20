"""/api/notebooks/* — Notebook CRUD + share_all 切换。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.collection import NotebookCollectionsPut, NotebookCollectionsRead
from app.schemas.notebook import (
    NotebookCreate,
    NotebookListResponse,
    NotebookRead,
    NotebookSourceRead,
    NotebookUpdate,
)
from app.services import collections as collections_svc
from app.services import notebooks as svc

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


@router.get("", response_model=NotebookListResponse)
async def list_notebooks(
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    items, total = await svc.list_notebooks(
        session,
        owner_id=user.id,
        search=search,
        page=page,
        size=size,
    )
    return NotebookListResponse(
        items=[NotebookRead(**svc._to_read_dict(nb)) for nb in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=NotebookRead, status_code=status.HTTP_201_CREATED)
async def create_notebook(
    body: NotebookCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.create_notebook(
        session,
        owner_id=user.id,
        title=body.title,
        description=body.description,
        icon=body.icon,
        cover_url=body.cover_url,
    )


@router.get("/{notebook_id}", response_model=NotebookSourceRead)
async def get_notebook_detail(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    nb = await svc.get_notebook(session, owner_id=user.id, notebook_id=notebook_id)
    sources = await svc.list_sources(session, owner_id=user.id, notebook_id=notebook_id)
    from app.subtitles.pipeline import kick_subtitle_job

    for source in sources:
        video = source.video
        if video.subtitle_status == "pending" and video.storage_key:
            kick_subtitle_job(video.id)
    from app.services.notes import list_notes

    notes = await list_notes(session, owner_id=user.id, notebook_id=notebook_id)
    detail = svc._to_read_dict(nb, source_count=len(sources), note_count=len(notes))
    detail["sources"] = sources
    detail["notes"] = notes
    return detail


@router.patch("/{notebook_id}", response_model=NotebookRead)
async def update_notebook(
    notebook_id: int,
    body: NotebookUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    fields = body.model_dump(exclude_unset=True)
    return await svc.update_notebook(
        session,
        owner_id=user.id,
        notebook_id=notebook_id,
        title=fields.get("title"),
        description=fields.get("description"),
        icon=fields.get("icon"),
        cover_url=fields.get("cover_url"),
        cover_url_set="cover_url" in fields,
        is_pinned=fields.get("is_pinned"),
    )


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    await svc.delete_notebook(session, owner_id=user.id, notebook_id=notebook_id)
    return None


@router.post("/{notebook_id}/share_all", response_model=NotebookRead)
async def post_share_all(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.set_share_all(
        session, owner_id=user.id, notebook_id=notebook_id, value=True
    )


@router.delete("/{notebook_id}/share_all", response_model=NotebookRead)
async def delete_share_all(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.set_share_all(
        session, owner_id=user.id, notebook_id=notebook_id, value=False
    )


@router.get("/{notebook_id}/collections", response_model=NotebookCollectionsRead)
async def get_notebook_collections(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    ids = await collections_svc.get_notebook_collection_ids(session, user.id, notebook_id)
    return NotebookCollectionsRead(collection_ids=ids)


@router.put("/{notebook_id}/collections", response_model=NotebookCollectionsRead)
async def put_notebook_collections(
    notebook_id: int,
    body: NotebookCollectionsPut,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    ids = await collections_svc.set_notebook_collections(
        session, user.id, notebook_id, body.collection_ids
    )
    return NotebookCollectionsRead(collection_ids=ids)
