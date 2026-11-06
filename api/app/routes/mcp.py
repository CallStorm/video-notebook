"""最小 MCP HTTP：initialize / tools/list / tools/call。工具名与 REST 一致。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.facade import TOOLS, dispatch
from app.core.errors import AppError
from app.db.session import get_session
from app.routes.agent_v1 import get_agent_context

router = APIRouter(tags=["mcp"])


def _rpc_result(req_id: object, result: object) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_error(req_id: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


@router.get("/mcp")
async def mcp_discover() -> dict:
    return {
        "service": "video-notebook",
        "protocol": "mcp",
        "transport": "json-rpc-http",
        "auth": "Authorization: Bearer vn_agent_…",
        "note": "POST JSON-RPC（initialize、tools/list、tools/call）。不要使用登录 JWT。",
    }


@router.post("/mcp")
async def mcp_post(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    raw = await request.body()
    try:
        payload = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return JSONResponse(_rpc_error(None, -32700, "Parse error"), status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse(_rpc_error(None, -32600, "Invalid Request"), status_code=400)

    req_id = payload.get("id", None)
    method = payload.get("method")
    if "id" not in payload:
        return Response(status_code=202)
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        return JSONResponse(_rpc_error(req_id, -32602, "Invalid params"))

    if method == "initialize":
        version = params.get("protocolVersion") or "2024-11-05"
        return JSONResponse(
            _rpc_result(
                req_id,
                {
                    "protocolVersion": version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "video-notebook", "version": "0.1.0"},
                    "instructions": "使用 vn_agent_ Token。按 Skill 的顺序调用工具。不要使用登录 JWT。",
                },
            )
        )
    if method == "ping":
        return JSONResponse(_rpc_result(req_id, {}))

    try:
        ctx = await get_agent_context(request, session)
    except AppError as exc:
        return JSONResponse(
            {"code": exc.code, "message": exc.message},
            status_code=exc.status_code,
        )

    if method == "tools/list":
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.model.model_json_schema(),
            }
            for tool in TOOLS
        ]
        return JSONResponse(_rpc_result(req_id, {"tools": tools}))

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return JSONResponse(_rpc_error(req_id, -32602, "Invalid params"))
        try:
            data = await dispatch(session, ctx, name, arguments)
        except AppError as exc:
            return JSONResponse(
                _rpc_result(
                    req_id,
                    {
                        "content": [{"type": "text", "text": exc.message}],
                        "isError": True,
                    },
                )
            )
        text = json.dumps(data, ensure_ascii=False)
        return JSONResponse(
            _rpc_result(
                req_id,
                {"content": [{"type": "text", "text": text}], "isError": False},
            )
        )

    return JSONResponse(_rpc_error(req_id, -32601, f"Method not found: {method}"))
