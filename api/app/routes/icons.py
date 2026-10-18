"""/api/icons — AI 生成 emoji 图标。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.services import icon_generate as svc

router = APIRouter(prefix="/icons", tags=["icons"])


class IconGenerateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class IconGenerateResponse(BaseModel):
    icon: str


@router.post("/generate", response_model=IconGenerateResponse)
async def generate_icon(
    body: IconGenerateRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_active_user),
):
    icon = await svc.generate_icon(session, body.name)
    return IconGenerateResponse(icon=icon)
