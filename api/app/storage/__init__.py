"""Object storage 抽象 + 本地 FS 实现（v1）。

接口对齐设计 §S4：`put / get / delete / head / signed_url`。
LocalFsStorage 走内容寻址（sha1），同内容天然去重。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class ObjectInfo:
    key: str
    size: int
    content_type: str | None = None


class ObjectStorage(Protocol):
    def put(self, *, data: bytes, content_type: str | None, suffix: str = "") -> str: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def head(self, key: str) -> ObjectInfo | None: ...
    def exists(self, key: str) -> bool: ...
    def signed_url(self, key: str, *, expires_seconds: int = 3600) -> str: ...
    def verify_signed_token(self, key: str, token: str, *, max_age_seconds: int) -> bool: ...


def content_hash(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def path_for(root: Path, sha1_hex: str, suffix: str) -> Path:
    return root / sha1_hex[:2] / f"{sha1_hex}{suffix}"


class LocalFsStorage:
    """本地文件系统存储。v1 写盘用，v2 换 S3 只需换实现。"""

    def __init__(self, root: str | Path, *, signed_token_secret: str = "change-me") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._secret = signed_token_secret.encode("utf-8")

    # ── 写入 ──────────────────────────────────────────────
    def put(self, *, data: bytes, content_type: str | None, suffix: str = "") -> str:
        h = content_hash(data)
        path = path_for(self.root, h, suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        # 旁挂 content_type 到 <key>.meta.json（小 v1 简化做法）
        if content_type:
            import json

            meta_path = path.with_suffix(path.suffix + ".meta.json")
            meta_path.write_text(
                json.dumps({"content_type": content_type}), encoding="utf-8"
            )
        return h + suffix  # key = sha1 + 扩展名

    # ── 读取 ──────────────────────────────────────────────
    def get(self, key: str) -> bytes:
        return self._path_for_key(key).read_bytes()

    def head(self, key: str) -> ObjectInfo | None:
        path = self._path_for_key(key)
        if not path.exists():
            return None
        # 读旁挂的 meta
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        ct: str | None = None
        if meta_path.exists():
            import json

            try:
                ct = json.loads(meta_path.read_text("utf-8")).get("content_type")
            except Exception:  # noqa: BLE001
                ct = None
        return ObjectInfo(key=key, size=path.stat().st_size, content_type=ct)

    def exists(self, key: str) -> bool:
        return self._path_for_key(key).exists()

    def delete(self, key: str) -> None:
        p = self._path_for_key(key)
        if p.exists():
            p.unlink()

    # ── 签名 URL（开发期用代理 token 模拟） ───────────────
    def signed_url(self, key: str, *, expires_seconds: int = 3600) -> str:
        # 真正签 URL 由后端 /api/storage/{key} 端点消费 token。
        # 这里只返 token，前端拼完整 URL 调我们自己的代理。
        token = self._make_token(key, expires_seconds)
        return f"/api/storage/{key}?token={token}"

    def verify_signed_token(self, key: str, token: str, *, max_age_seconds: int) -> bool:
        """校验 token；max_age_seconds 是调用方允许的过期时间。"""
        try:
            payload_b64, sig_b64 = token.split(".", 1)
            payload = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
            expected_sig = hmac.new(self._secret, payload, hashlib.sha256).digest()
            actual_sig = base64.urlsafe_b64decode(sig_b64.encode("ascii"))
            if not hmac.compare_digest(expected_sig, actual_sig):
                return False
            # payload: "key|exp"
            text = payload.decode("utf-8")
            ks, exp_s = text.rsplit("|", 1)
            if ks != key:
                return False
            exp = int(exp_s)
            if exp < int(time.time()):
                return False
            return True
        except (ValueError, KeyError):
            return False

    def _make_token(self, key: str, expires_seconds: int) -> str:
        exp = int(time.time()) + expires_seconds
        payload = f"{key}|{exp}".encode()
        sig = hmac.new(self._secret, payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(payload).decode("ascii") + "." + base64.urlsafe_b64encode(sig).decode("ascii")

    def local_path(self, key: str) -> Path:
        return self._path_for_key(key)

    def _path_for_key(self, key: str) -> Path:
        # key 形如 "<sha1>" 或 "<sha1>.<ext>"；sha1[:2] 作为子目录
        sha1 = key.split(".", 1)[0]
        if len(sha1) != 40:
            raise ValueError(f"bad object key: {key}")
        # 拼上原来 key 里的扩展名（如果 key 形如 "<sha1>.<ext>"）
        suffix = key[len(sha1):]
        return self.root / sha1[:2] / f"{sha1}{suffix}"


_singleton: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    """根据配置返回单例。"""
    global _singleton
    if _singleton is None:
        from app.core.config import get_settings

        settings = get_settings()
        _singleton = LocalFsStorage(
            root=settings.storage_root,
            signed_token_secret=settings.master_secret or "change-me",
        )
    return _singleton


def reset_storage_singleton() -> None:
    """测试用：清掉单例。"""
    global _singleton
    _singleton = None
