"""/api/tags — author-owned notebook tags."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.tag import (
    AutoOrganizeApplyRequest,
    AutoOrganizeApplyResponse,
    AutoOrganizePreviewResponse,
    TagCreate,
    TagRead,
    TagUpdate,
)
from app.services import tags as svc

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagRead])
async def list_tags(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.list_tags(session, user.id)


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def create_tag(
    body: TagCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.create_tag(session, user.id, name=body.name, color=body.color)


@router.post("/auto-organize/preview", response_model=AutoOrganizePreviewResponse)
async def auto_organize_preview(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """Analyze notebooks and suggest tags + multi-tag assignments."""
    return await svc.preview_auto_organize(session, user.id)


@router.post("/auto-organize/apply", response_model=AutoOrganizeApplyResponse)
async def auto_organize_apply(
    body: AutoOrganizeApplyRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """Cover notebook tag associations with the confirmed plan; create missing tags."""
    tags = await svc.apply_auto_organize(
        session,
        user.id,
        [t.model_dump() for t in body.tags],
        [a.model_dump() for a in body.assignments],
    )
    return {"tags": tags}


@router.patch("/{tag_id}", response_model=TagRead)
async def update_tag(
    tag_id: int,
    body: TagUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    raw = await request.json()
    return await svc.update_tag(
        session,
        user.id,
        tag_id,
        name=body.name,
        color_provided="color" in raw,
        color=body.color,
    )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    await svc.delete_tag(session, user.id, tag_id)
