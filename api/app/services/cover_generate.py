"""按名称 + 可选描述生成笔记本封面（文生图）。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, BadRequestError, NotFoundError, ServiceUnavailableError
from app.llm.config_service import get_active_cover_image_llm
from app.llm.image_generate import generate_image_bytes
from app.services import cover_settings as cover_cfg
from app.services.cover_url import expand_cover_url, put_cover_image


async def generate_cover(
    session: AsyncSession,
    *,
    title: str,
    description: str | None = None,
) -> dict:
    trimmed = (title or "").strip()
    if not trimmed:
        raise BadRequestError("名称不能为空")
    if len(trimmed) > 255:
        raise BadRequestError("名称过长")
    desc = (description or "").strip()
    if len(desc) > 2000:
        raise BadRequestError("描述过长")

    settings_row = await cover_cfg.get_cover_settings_row(session)
    return await _generate_cover_image(
        session,
        settings_row=settings_row,
        title=trimmed,
        description=desc,
    )


async def _generate_cover_image(
    session: AsyncSession,
    *,
    settings_row,
    title: str,
    description: str,
) -> dict:
    system_prompt = cover_cfg.resolve_image_system_prompt(settings_row)
    user_template = cover_cfg.resolve_image_user_prompt(settings_row)
    size = cover_cfg.resolve_image_size(settings_row)
    prompt = cover_cfg.render_image_prompt(
        system_prompt, user_template, title=title, description=description
    )
    try:
        llm = await get_active_cover_image_llm(session)
    except NotFoundError as exc:
        raise BadRequestError(
            "未配置「封面文生图」模型：请到管理后台 → 模型配置，为「封面文生图」绑定出图模型。"
            "MiniMax 请新增模型名 image-01（同一凭证即可）；"
            "OpenAI 兼容网关可用 FLUX / Kolors / dall-e。不要绑聊天模型当出图模型。"
        ) from exc
    try:
        raw, content_type = await generate_image_bytes(
            api_key=llm.api_key,
            base_url=llm.base_url,
            model_name=llm.model_name,
            prompt=prompt,
            size=size,
            provider=getattr(llm, "provider", None),
        )
    except (BadRequestError, ServiceUnavailableError, AppError):
        raise
    except Exception as exc:
        msg = str(exc).strip() or exc.__class__.__name__
        raise ServiceUnavailableError(f"封面文生图失败：{msg}") from exc

    if not raw:
        raise ServiceUnavailableError("封面文生图返回空内容")

    stored = put_cover_image(data=raw, content_type=content_type)
    return {
        "cover_url": expand_cover_url(stored) or stored,
        "layout": "image",
        "motif": "image",
        "pattern": "image",
        "a": "#000000",
        "b": "#000000",
        "c": "#000000",
        "ink": "#FFFFFF",
        "mist": "#888888",
        "label": "",
        "storage_key": stored,
    }
