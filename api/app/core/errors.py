"""统一错误响应形状 + 异常类。

设计 §6.7 中所有 admin 等接口返回 `{ code, message }` 风格的错误。
不在 Phase 1 覆盖完整 RBAC / 业务异常，先把通用 shape + 几个占位异常立起来。
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """所有应用层异常的基类。子类应定义 status_code 与 code。"""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "", **details: Any) -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details or None,
        },
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": exc.errors(),
            }
        ),
    )
