"""/api/notebooks/{id}/knowledge-draft — 本内知识底稿。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.knowledge_draft import (
    DraftStrategyOption,
    KnowledgeDraftGenerateRequest,
    KnowledgeDraftPointAskRequest,
    KnowledgeDraftPointAskResponse,
    KnowledgeDraftRead,
    KnowledgeDraftUpdateRequest,
)
from app.services import knowledge_draft as svc

router = APIRouter(tags=["knowledge-draft"])


@router.get(
    "/notebooks/{notebook_id}/draft-strategies",
    response_model=list[DraftStrategyOption],
)
async def list_draft_strategies(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    # notebook_id 仅用于鉴权路径一致性；策略为全站启用列表
    from app.services import notebooks as notebooks_svc

    await notebooks_svc.get_notebook(
        session, owner_id=user.id, notebook_id=notebook_id
    )
    return await svc.list_enabled_strategies(session)


@router.get(
    "/notebooks/{notebook_id}/knowledge-draft",
    response_model=KnowledgeDraftRead | None,
)
async def get_knowledge_draft(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.get_draft(session, owner_id=user.id, notebook_id=notebook_id)


@router.post(
    "/notebooks/{notebook_id}/knowledge-draft",
    response_model=KnowledgeDraftRead,
)
async def generate_knowledge_draft(
    notebook_id: int,
    body: KnowledgeDraftGenerateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.generate_draft(
        session, owner_id=user.id, notebook_id=notebook_id, body=body
    )


@router.patch(
    "/notebooks/{notebook_id}/knowledge-draft",
    response_model=KnowledgeDraftRead,
)
async def patch_knowledge_draft(
    notebook_id: int,
    body: KnowledgeDraftUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.update_draft(
        session, owner_id=user.id, notebook_id=notebook_id, body=body
    )


@router.delete(
    "/notebooks/{notebook_id}/knowledge-draft",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_knowledge_draft(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    await svc.delete_draft(session, owner_id=user.id, notebook_id=notebook_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/notebooks/{notebook_id}/knowledge-draft/point-ask",
    response_model=KnowledgeDraftPointAskResponse,
)
async def ask_knowledge_draft_point(
    notebook_id: int,
    body: KnowledgeDraftPointAskRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.ask_about_point(
        session, owner_id=user.id, notebook_id=notebook_id, body=body
    )

