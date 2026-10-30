"""/api/admin/studio — read-only plugin/capability introspection (no toggles)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.studio import CapabilityRead, FormatRead
from app.services import capabilities as svc
from app.studio.formats import list_formats
from app.studio.plugins.registry import list_plugins

router = APIRouter(prefix="/admin/studio", tags=["admin-studio"])


@router.get("/formats", response_model=list[FormatRead])
async def list_studio_formats(_: User = Depends(require_admin)):
    # Prefer plugin labels; include legacy file for compatibility.
    return [{"key": fmt.key, "label": fmt.label} for fmt in list_formats()]


@router.get("/plugins")
async def list_studio_plugins(_: User = Depends(require_admin)):
    """Disk plugins (source of truth for installed formats)."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "icon": p.icon,
            "version": p.version,
            "skill": p.skill_name,
            "timeout_seconds": p.timeout_seconds,
        }
        for p in list_plugins()
    ]


@router.get("/capabilities", response_model=list[CapabilityRead])
async def list_capabilities(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.list_capabilities(session)


@router.get("/capabilities/{capability_id}", response_model=CapabilityRead)
async def get_capability(
    capability_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_capability(session, capability_id)
