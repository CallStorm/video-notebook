"""VectorStore 抽象 + Qdrant 实现。"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class VectorStoreError(RuntimeError):
    pass


@dataclass
class VectorPoint:
    notebook_id: int
    vector: list[float]
    payload: dict[str, Any]
    point_id: str | int | None = None


@dataclass
class VectorHit:
    notebook_id: int
    score: float
    payload: dict[str, Any]


class VectorStore(ABC):
    @abstractmethod
    async def ensure_collection(self, dim: int) -> None: ...

    @abstractmethod
    async def upsert(self, point: VectorPoint) -> None: ...

    @abstractmethod
    async def delete(self, notebook_id: int) -> None: ...

    async def upsert_many(self, points: list[VectorPoint]) -> None:
        for point in points:
            await self.upsert(point)

    async def delete_points(self, point_ids: list[str | int]) -> None:
        raise VectorStoreError("当前向量后端不支持按点删除")

    async def scroll_notebook(
        self, notebook_id: int
    ) -> list[tuple[str | int, dict[str, Any]]]:
        return []

    async def set_payload(self, notebook_id: int, payload: dict[str, Any]) -> None:
        return None

    @abstractmethod
    async def search(
        self,
        vector: list[float],
        *,
        limit: int = 20,
        notebook_ids: list[int] | None = None,
        score_threshold: float | None = None,
    ) -> list[VectorHit]: ...

    @abstractmethod
    async def healthcheck(self) -> None: ...


class QdrantVectorStore(VectorStore):
    """HTTP 客户端实现，不强制依赖 qdrant-client SDK。"""

    def __init__(
        self,
        *,
        url: str,
        collection: str,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base = url.rstrip("/")
        self._collection = collection
        self._api_key = (api_key or "").strip() or None
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["api-key"] = self._api_key
        return h

    async def healthcheck(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.get(f"{self._base}/readyz", headers=self._headers())
                if r.status_code >= 400:
                    # 旧版可能没有 readyz，再试根
                    r2 = await client.get(f"{self._base}/", headers=self._headers())
                    if r2.status_code >= 400:
                        raise VectorStoreError(
                            f"Qdrant 不可达：HTTP {r.status_code} ({self._base})"
                        )
        except httpx.HTTPError as exc:
            raise VectorStoreError(f"Qdrant 连接失败：{exc}") from exc

    async def ensure_collection(self, dim: int) -> None:
        await self.healthcheck()
        want = int(dim)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            info = await client.get(
                f"{self._base}/collections/{self._collection}",
                headers=self._headers(),
            )
            if info.status_code == 200:
                result = (info.json() or {}).get("result") or {}
                params = ((result.get("config") or {}).get("params") or {}).get("vectors") or {}
                if isinstance(params, dict) and "size" in params:
                    existing = int(params.get("size") or 0)
                elif isinstance(params, dict) and params:
                    first = next(iter(params.values()), {}) or {}
                    existing = int(first.get("size") or 0)
                else:
                    existing = 0
                points = int(result.get("points_count") or 0)
                if existing == want:
                    await self._ensure_notebook_index(client)
                    return
                if points == 0:
                    logger.warning(
                        "Qdrant collection %s dim mismatch empty existing=%s want=%s; recreating",
                        self._collection,
                        existing,
                        want,
                    )
                    deleted = await client.delete(
                        f"{self._base}/collections/{self._collection}",
                        headers=self._headers(),
                    )
                    if deleted.status_code >= 400 and deleted.status_code != 404:
                        raise VectorStoreError(
                            f"删除维度不匹配的 Qdrant collection 失败：HTTP {deleted.status_code} {deleted.text[:200]}"
                        )
                else:
                    raise VectorStoreError(
                        f"Qdrant collection `{self._collection}` 维度是 {existing}，"
                        f"当前向量模型是 {want}。请删掉该 collection 后全量重建，"
                        f"或改用匹配维度的 embedding 模型（现有 {points} 个点）。"
                    )
            elif info.status_code not in (404, 400):
                raise VectorStoreError(
                    f"查询 Qdrant collection 失败：HTTP {info.status_code} {info.text[:200]}"
                )
            body = {
                "vectors": {
                    "size": want,
                    "distance": "Cosine",
                }
            }
            created = await client.put(
                f"{self._base}/collections/{self._collection}",
                headers=self._headers(),
                json=body,
            )
            if created.status_code >= 400:
                raise VectorStoreError(
                    f"创建 Qdrant collection 失败：HTTP {created.status_code} {created.text[:300]}"
                )
            await self._ensure_notebook_index(client)

    async def _ensure_notebook_index(self, client: httpx.AsyncClient) -> None:
        """分组检索要求 notebook_id 有整数索引。已存在时忽略。"""
        created = await client.put(
            f"{self._base}/collections/{self._collection}/index",
            headers=self._headers(),
            params={"wait": "true"},
            json={"field_name": "notebook_id", "field_schema": "integer"},
        )
        if created.status_code < 400:
            return
        text = created.text.lower()
        if "already" in text or "exist" in text:
            return
        raise VectorStoreError(
            f"创建 notebook_id 索引失败：HTTP {created.status_code} {created.text[:300]}"
        )

    def _point_body(self, point: VectorPoint) -> dict[str, Any]:
        point_id = point.point_id if point.point_id is not None else int(point.notebook_id)
        return {
            "id": point_id,
            "vector": point.vector,
            "payload": {
                **point.payload,
                "notebook_id": int(point.notebook_id),
            },
        }

    async def upsert(self, point: VectorPoint) -> None:
        await self.upsert_many([point])

    async def upsert_many(self, points: list[VectorPoint]) -> None:
        if not points:
            return
        payload = {"points": [self._point_body(point) for point in points]}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.put(
                f"{self._base}/collections/{self._collection}/points",
                headers=self._headers(),
                params={"wait": "true"},
                json=payload,
            )
            if r.status_code >= 400:
                raise VectorStoreError(
                    f"Qdrant upsert 失败：HTTP {r.status_code} {r.text[:300]}"
                )

    async def delete(self, notebook_id: int) -> None:
        await self._delete_matching(notebook_id)
        await self.delete_points([int(notebook_id)])

    async def delete_points(self, point_ids: list[str | int]) -> None:
        ids = [point_id for point_id in point_ids if point_id is not None and point_id != ""]
        if not ids:
            return
        await self._delete_body({"points": ids})

    async def _delete_matching(self, notebook_id: int) -> None:
        await self._delete_body(
            {
                "filter": {
                    "must": [
                        {
                            "key": "notebook_id",
                            "match": {"value": int(notebook_id)},
                        }
                    ]
                }
            }
        )

    async def _delete_body(self, body: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(
                f"{self._base}/collections/{self._collection}/points/delete",
                headers=self._headers(),
                params={"wait": "true"},
                json=body,
            )
            if r.status_code == 404:
                return
            if r.status_code >= 400:
                raise VectorStoreError(
                    f"Qdrant delete 失败：HTTP {r.status_code} {r.text[:300]}"
                )

    async def scroll_notebook(self, notebook_id: int) -> list[tuple[str | int, dict[str, Any]]]:
        found: list[tuple[str | int, dict[str, Any]]] = []
        offset: Any = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            while True:
                body: dict[str, Any] = {
                    "filter": {
                        "must": [
                            {
                                "key": "notebook_id",
                                "match": {"value": int(notebook_id)},
                            }
                        ]
                    },
                    "limit": 128,
                    "with_payload": True,
                    "with_vector": False,
                }
                if offset is not None:
                    body["offset"] = offset
                r = await client.post(
                    f"{self._base}/collections/{self._collection}/points/scroll",
                    headers=self._headers(),
                    json=body,
                )
                if r.status_code == 404:
                    return []
                if r.status_code >= 400:
                    raise VectorStoreError(
                        f"Qdrant scroll 失败：HTTP {r.status_code} {r.text[:300]}"
                    )
                result = (r.json() or {}).get("result") or {}
                for row in result.get("points") or []:
                    found.append((row.get("id"), dict(row.get("payload") or {})))
                offset = result.get("next_page_offset")
                if offset is None:
                    break
        return found

    async def set_payload(self, notebook_id: int, payload: dict[str, Any]) -> None:
        body = {
            "payload": payload,
            "filter": {
                "must": [
                    {
                        "key": "notebook_id",
                        "match": {"value": int(notebook_id)},
                    }
                ]
            },
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(
                f"{self._base}/collections/{self._collection}/points/payload",
                headers=self._headers(),
                params={"wait": "true"},
                json=body,
            )
            if r.status_code == 404:
                return
            if r.status_code >= 400:
                raise VectorStoreError(
                    f"Qdrant payload 更新失败：HTTP {r.status_code} {r.text[:300]}"
                )

    async def search(
        self,
        vector: list[float],
        *,
        limit: int = 20,
        notebook_ids: list[int] | None = None,
        score_threshold: float | None = None,
    ) -> list[VectorHit]:
        """按 notebook_id 分组，每本笔记本只返回分数最高的一段。"""
        body: dict[str, Any] = {
            "vector": vector,
            "limit": max(1, int(limit)),
            "group_by": "notebook_id",
            "group_size": 1,
            "with_payload": True,
        }
        if score_threshold is not None:
            body["score_threshold"] = float(score_threshold)
        if notebook_ids is not None:
            body["filter"] = {
                "must": [
                    {
                        "key": "notebook_id",
                        "match": {"any": [int(i) for i in notebook_ids]},
                    }
                ]
            }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            url = f"{self._base}/collections/{self._collection}/points/search/groups"
            r = await client.post(url, headers=self._headers(), json=body)
            if r.status_code >= 400 and "index" in r.text.lower():
                await self._ensure_notebook_index(client)
                r = await client.post(url, headers=self._headers(), json=body)
            if r.status_code >= 400:
                raise VectorStoreError(
                    f"Qdrant search 失败：HTTP {r.status_code} {r.text[:300]}"
                )
            return hits_from_search_groups(r.json())


def hits_from_search_groups(data: dict[str, Any]) -> list[VectorHit]:
    result = data.get("result") or {}
    groups = result.get("groups") if isinstance(result, dict) else None
    if not isinstance(groups, list):
        return []
    hits: list[VectorHit] = []
    for group in groups:
        rows = group.get("hits") or []
        if not rows:
            continue
        row = max(rows, key=lambda item: float(item.get("score") or 0.0))
        payload = row.get("payload") or {}
        nid = payload.get("notebook_id", group.get("id"))
        try:
            nid_int = int(nid)
        except (TypeError, ValueError):
            continue
        hits.append(
            VectorHit(
                notebook_id=nid_int,
                score=float(row.get("score") or 0.0),
                payload=dict(payload),
            )
        )
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits


def make_vector_store(
    *,
    backend: str,
    qdrant_url: str,
    qdrant_collection: str,
    qdrant_api_key: str | None = None,
) -> VectorStore:
    name = (backend or "qdrant").strip().lower()
    if name in ("qdrant",):
        return QdrantVectorStore(
            url=qdrant_url,
            collection=qdrant_collection,
            api_key=qdrant_api_key,
        )
    if name in ("pending", "none", "noop"):
        raise VectorStoreError(
            f"向量后端尚未就绪（backend={name}）。请在后台「向量配置」选择 Qdrant 并填写地址。"
        )
    raise VectorStoreError(f"未知向量后端：{backend}")
