"""笔记本 Studio：已启用能力、创建与列出任务。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.studio import CapabilityRead, TaskCreate, TaskRead
from app.services import studio_tasks as svc

router = APIRouter(tags=["studio"])


@router.get("/notebooks/{notebook_id}/studio/capabilities", response_model=list[CapabilityRead])
async def list_studio_capabilities(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.list_enabled_capabilities(
        session, owner_id=user.id, notebook_id=notebook_id
    )


@router.get("/notebooks/{notebook_id}/studio/tasks", response_model=list[TaskRead])
async def list_studio_tasks(
    notebook_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.list_tasks(session, owner_id=user.id, notebook_id=notebook_id)


@router.post(
    "/notebooks/{notebook_id}/studio/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_studio_task(
    notebook_id: int,
    body: TaskCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.create_task(
        session, owner_id=user.id, notebook_id=notebook_id, body=body
    )
