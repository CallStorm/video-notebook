"""/api/admin/observability — 流水线日志与 LLM 追踪。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.observability import (
    LlmTraceDetail,
    LlmTraceListResponse,
    ObservabilitySettingsRead,
    ObservabilitySettingsUpdate,
    PipelineRunDetail,
    PipelineRunListResponse,
)
from app.services import observability as svc

router = APIRouter(prefix="/admin/observability", tags=["admin-observability"])


@router.get("/settings", response_model=ObservabilitySettingsRead)
async def get_settings(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_settings(session)


@router.put("/settings", response_model=ObservabilitySettingsRead)
async def put_settings(
    body: ObservabilitySettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_settings(session, body)


@router.get("/pipeline-runs", response_model=PipelineRunListResponse)
async def list_pipeline_runs(
    video_id: int | None = None,
    notebook_id: int | None = None,
    status: str | None = None,
    include_events: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.list_pipeline_runs(
        session,
        video_id=video_id,
        notebook_id=notebook_id,
        status=status,
        include_events=include_events,
        limit=limit,
        offset=offset,
    )


@router.get("/pipeline-runs/{run_id}", response_model=PipelineRunDetail)
async def get_pipeline_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_pipeline_run(session, run_id)


@router.get("/llm-traces", response_model=LlmTraceListResponse)
async def list_llm_traces(
    kind: str | None = None,
    status: str | None = None,
    notebook_id: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.list_llm_traces(
        session,
        kind=kind,
        status=status,
        notebook_id=notebook_id,
        limit=limit,
        offset=offset,
    )


@router.get("/llm-traces/{trace_id}", response_model=LlmTraceDetail)
async def get_llm_trace(
    trace_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_llm_trace(session, trace_id)


@router.post("/purge")
async def purge(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.trigger_purge(session)
