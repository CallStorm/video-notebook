"""公开文档：llms.txt、Skill、安装脚本、OpenAPI。不接受登录 JWT，也不内嵌 Token。"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.agent.docs import install_script, llms_text, openapi_document, skill_markdown
from app.agent.urls import public_origin

router = APIRouter(tags=["agent-public"])


@router.get("/llms.txt", include_in_schema=False)
async def get_llms(request: Request) -> PlainTextResponse:
    return PlainTextResponse(llms_text(public_origin(request)), media_type="text/plain; charset=utf-8")


@router.get("/agent/skill.md", include_in_schema=False)
async def get_skill() -> PlainTextResponse:
    return PlainTextResponse(skill_markdown(), media_type="text/markdown; charset=utf-8")


@router.get("/agent/install.sh", include_in_schema=False)
async def get_install(request: Request) -> PlainTextResponse:
    return PlainTextResponse(
        install_script(public_origin(request)),
        media_type="text/x-shellscript; charset=utf-8",
    )


@router.get("/agent/openapi.json", include_in_schema=False)
async def get_agent_openapi(request: Request) -> JSONResponse:
    return JSONResponse(openapi_document(public_origin(request)))
