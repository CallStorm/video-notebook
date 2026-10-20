"""/api/collections — author-owned notebook collections."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.collection import (
    CollectionCreate,
    CollectionDetail,
    CollectionNotebooksPut,
    CollectionRead,
    CollectionUpdate,
)
from app.services import collections as svc

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=list[CollectionRead])
async def list_collections(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.list_collections(session, user.id)


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
async def create_collection(
    body: CollectionCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.create_collection(session, user.id, name=body.name, icon=body.icon, cover_url=body.cover_url)


@router.get("/{collection_id}", response_model=CollectionDetail)
async def get_collection(
    collection_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.get_collection(session, user.id, collection_id)


@router.patch("/{collection_id}", response_model=CollectionRead)
async def update_collection(
    collection_id: int,
    body: CollectionUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    raw = await request.json()
    return await svc.update_collection(
        session,
        user.id,
        collection_id,
        name=body.name,
        icon_provided="icon" in raw,
        icon=body.icon,
        cover_url_provided="cover_url" in raw,
        cover_url=body.cover_url,
    )


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    await svc.delete_collection(session, user.id, collection_id)


@router.put("/{collection_id}/notebooks", response_model=CollectionDetail)
async def put_collection_notebooks(
    collection_id: int,
    body: CollectionNotebooksPut,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.set_collection_notebooks(
        session, user.id, collection_id, body.notebook_ids
    )
