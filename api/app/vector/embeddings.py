"""OpenAI 兼容 embeddings 客户端（POST {base}/embeddings）。"""
from __future__ import annotations

import logging

import httpx

from app.llm.config_service import EmbeddingResolved

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    pass


def _embeddings_url(base_url: str | None) -> str:
    base = (base_url or "https://api.openai.com/v1").rstrip("/")
    if base.endswith("/embeddings"):
        return base
    return f"{base}/embeddings"


async def embed_texts(
    resolved: EmbeddingResolved,
    texts: list[str],
    *,
    timeout: float = 60.0,
) -> list[list[float]]:
    """对多段文本做 embedding，返回与 texts 同序的向量列表。"""
    if not texts:
        return []
    if not resolved.api_key:
        raise EmbeddingError("向量模型凭证没有 API Key")
    url = _embeddings_url(resolved.base_url)
    headers = {
        "Authorization": f"Bearer {resolved.api_key}",
        "Content-Type": "application/json",
    }
    # 部分兼容网关要求 input 为单字符串；多段时分批或一次数组均可。
    # OpenAI 官方支持 list[str]。
    payload = {
        "model": resolved.model_name,
        "input": texts if len(texts) > 1 else texts[0],
        "encoding_format": "float",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=15.0)) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            detail = resp.text[:500]
            raise EmbeddingError(
                f"embeddings HTTP {resp.status_code}: {detail}"
            )
        data = resp.json()
    items = data.get("data")
    if not isinstance(items, list) or not items:
        raise EmbeddingError("embeddings 响应缺少 data")
    # data 可能乱序，按 index 排
    ordered = sorted(items, key=lambda x: int(x.get("index", 0)))
    vectors: list[list[float]] = []
    for item in ordered:
        emb = item.get("embedding")
        if not isinstance(emb, list) or not emb:
            raise EmbeddingError("embeddings 响应缺少 embedding 向量")
        vectors.append([float(v) for v in emb])
    if len(vectors) != len(texts):
        # 单字符串 input 时 data 只有一条
        if len(texts) == 1 and len(vectors) == 1:
            return vectors
        raise EmbeddingError(
            f"embeddings 条数不匹配：input={len(texts)} data={len(vectors)}"
        )
    return vectors


async def embed_query(resolved: EmbeddingResolved, text: str) -> list[float]:
    vecs = await embed_texts(resolved, [text])
    return vecs[0]
