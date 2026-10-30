"""ConfigService：根据 default_models 取当前 role → model → credential → 完整 LLM / ASR / Embedding 配置。

缓存：默认 30s 内存 TTL。admin 改完配置后调用 `invalidate(role)` 失效。
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt
from app.core.errors import NotFoundError
from app.llm.provider_registry import get_provider
from app.models.credential import Credential
from app.models.default_model import DefaultModel
from app.models.model import Model

_TTL_SECONDS = 30


@dataclass
class LlmResolved:
    provider: str
    base_url: str | None
    api_key: str
    model_name: str
    params_json: dict | None


@dataclass
class SttResolved:
    provider: str
    api_key: str
    model_name: str
    config: dict | None
    base_url: str | None = None


@dataclass
class EmbeddingResolved:
    provider: str
    base_url: str | None
    api_key: str
    model_name: str
    params_json: dict | None


class _TTLCache[K, V]:
    def __init__(self) -> None:
        self._store: dict[K, tuple[V, float]] = {}

    def get(self, key: K) -> V | None:
        item = self._store.get(key)
        if item is None:
            return None
        value, ts = item
        if time.monotonic() - ts > _TTL_SECONDS:
            self._store.pop(key, None)
            return None
        return value

    def put(self, key: K, value: V) -> None:
        self._store[key] = (value, time.monotonic())

    def clear(self) -> None:
        self._store.clear()


_llm_cache = _TTLCache[str, LlmResolved]()
_stt_cache = _TTLCache[str, SttResolved]()
_logo_cache = _TTLCache[str, LlmResolved]()
_cover_image_cache = _TTLCache[str, LlmResolved]()
_embedding_cache = _TTLCache[str, EmbeddingResolved]()


async def _resolve_default(
    session: AsyncSession, role: str
) -> tuple[Model, Credential]:
    """根据 role 查 default_models → models → credentials，返回 model 与 credential。"""
    d = (
        await session.execute(select(DefaultModel).where(DefaultModel.role == role))
    ).scalar_one_or_none()
    if d is None:
        raise NotFoundError(f"role={role} 没有默认模型（请在 admin 配置）")
    m = await session.get(Model, d.model_id)
    if m is None:
        raise NotFoundError(f"default_models 指向不存在的 model_id={d.model_id}")
    cred = await session.get(Credential, m.credential_id)
    if cred is None:
        raise NotFoundError(f"model 指向不存在的 credential_id={m.credential_id}")
    return m, cred


def _to_llm(m: Model, cred: Credential) -> LlmResolved:
    return LlmResolved(
        provider=m.provider,
        base_url=cred.base_url,
        api_key=decrypt(cred.api_key_enc or ""),
        model_name=m.name,
        params_json=cred.config,
    )


async def get_active_llm(session: AsyncSession) -> LlmResolved:
    cached = _llm_cache.get("active")
    if cached:
        return cached
    m, cred = await _resolve_default(session, "chat")
    resolved = _to_llm(m, cred)
    _llm_cache.put("active", resolved)
    return resolved


async def get_active_logo_llm(session: AsyncSession) -> LlmResolved:
    """生成图标用模型：优先 logo role，未配置则回退 chat。"""
    cached = _logo_cache.get("active")
    if cached:
        return cached
    d = (
        await session.execute(select(DefaultModel).where(DefaultModel.role == "logo"))
    ).scalar_one_or_none()
    if d is not None:
        m, cred = await _resolve_default(session, "logo")
    else:
        m, cred = await _resolve_default(session, "chat")
    resolved = _to_llm(m, cred)
    _logo_cache.put("active", resolved)
    return resolved




async def get_active_cover_image_llm(session: AsyncSession) -> LlmResolved:
    """Notebook cover text-to-image model; requires cover_image role (no chat fallback)."""
    cached = _cover_image_cache.get("active")
    if cached:
        return cached
    m, cred = await _resolve_default(session, "cover_image")
    resolved = _to_llm(m, cred)
    _cover_image_cache.put("active", resolved)
    return resolved



async def get_active_stt(session: AsyncSession) -> SttResolved:
    cached = _stt_cache.get("active")
    if cached:
        return cached
    m, cred = await _resolve_default(session, "stt")
    spec = get_provider(m.provider)
    resolved = SttResolved(
        provider=m.provider,
        api_key=decrypt(cred.api_key_enc or ""),
        model_name=m.name,
        config=cred.config,
        base_url=cred.base_url or (spec.default_base_url if spec else None),
    )
    _stt_cache.put("active", resolved)
    return resolved


async def get_active_embedding(session: AsyncSession) -> EmbeddingResolved:
    cached = _embedding_cache.get("active")
    if cached:
        return cached
    m, cred = await _resolve_default(session, "embedding")
    spec = get_provider(m.provider)
    resolved = EmbeddingResolved(
        provider=m.provider,
        base_url=cred.base_url or (spec.default_base_url if spec else None),
        api_key=decrypt(cred.api_key_enc or ""),
        model_name=m.name,
        params_json=cred.config,
    )
    _embedding_cache.put("active", resolved)
    return resolved


def invalidate(role: str | None = None) -> None:
    """Admin 改了配置后调用。下次读会回 DB 拉。"""
    if role in (None, "chat", "logo", "cover_image", "all"):
        _llm_cache.clear()
        _logo_cache.clear()
        _cover_image_cache.clear()
    if role in (None, "stt", "all"):
        _stt_cache.clear()
    if role in (None, "embedding", "all"):
        _embedding_cache.clear()
    if role and role not in ("chat", "stt", "logo", "cover_image", "embedding", "all"):
        _llm_cache.clear()
        _logo_cache.clear()
        _cover_image_cache.clear()
        _stt_cache.clear()
        _embedding_cache.clear()
