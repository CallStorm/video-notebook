"""/api/covers — AI 生成笔记本封面样式。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.services import cover_generate as svc

router = APIRouter(prefix="/covers", tags=["covers"])


class CoverGenerateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class CoverGenerateResponse(BaseModel):
    cover_url: str
    pattern: str
    a: str
    b: str
    c: str
    ink: str
    mist: str


@router.post("/generate", response_model=CoverGenerateResponse)
async def generate_cover(
    body: CoverGenerateRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_active_user),
):
    result = await svc.generate_cover(
        session,
        title=body.title,
        description=body.description,
    )
    return CoverGenerateResponse(**result)
