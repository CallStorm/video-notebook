"""/api/admin/skills — 技能上传、元数据、下载、软删。"""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.core.errors import BadRequestError
from app.db.session import get_session
from app.models.user import User
from app.schemas.studio import SkillRead, SkillUpdate
from app.services import skills as svc

router = APIRouter(prefix="/admin/skills", tags=["admin-skills"])


@router.get("", response_model=list[SkillRead])
async def list_skills(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.list_skills(session)


@router.post("", response_model=SkillRead, status_code=status.HTTP_201_CREATED)
async def create_skill(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    data = await file.read()
    if not data:
        raise BadRequestError("空文件")
    return await svc.create_skill_from_zip(session, uploaded_by=user.id, data=data)


@router.get("/{skill_id}", response_model=SkillRead)
async def get_skill(
    skill_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_skill(session, skill_id)


@router.patch("/{skill_id}", response_model=SkillRead)
async def update_skill(
    skill_id: int,
    body: SkillUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_skill(
        session,
        skill_id,
        name=body.name,
        description=body.description,
        version=body.version,
    )


@router.get("/{skill_id}/download")
async def download_skill(
    skill_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    skill = await svc.get_skill(session, skill_id)
    data = svc.skill_zip_bytes(skill)
    filename = f"skill-{skill.id}.zip"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    await svc.delete_skill(session, skill_id)
    return None
