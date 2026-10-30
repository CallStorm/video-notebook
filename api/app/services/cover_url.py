"""Cover URL helpers: storage-backed images; legacy gen: tokens still pass through."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.storage import get_storage

STORAGE_PREFIX = "storage:"
# Long-lived enough for list/detail caching; re-expanded on each API read.
_SIGNED_EXPIRES = 7 * 24 * 3600
_KEY_RE = re.compile(r"^[0-9a-f]{40}(\.[A-Za-z0-9]{1,16})?$")
_PATH_RE = re.compile(
    r"^/api/storage/([0-9a-f]{40}(?:\.[A-Za-z0-9]{1,16})?)(?:\?.*)?$"
)


def is_storage_cover(cover_url: str | None) -> bool:
    return bool(cover_url) and cover_url.startswith(STORAGE_PREFIX)


def is_gen_cover(cover_url: str | None) -> bool:
    return bool(cover_url) and cover_url.startswith("gen:")


def storage_key_from_cover(cover_url: str | None) -> str | None:
    if not cover_url:
        return None
    raw = cover_url.strip()
    if raw.startswith(STORAGE_PREFIX):
        key = raw[len(STORAGE_PREFIX) :]
        return key if _KEY_RE.fullmatch(key) else None
    m = _PATH_RE.match(raw)
    if m:
        return m.group(1)
    # absolute URL ending with /api/storage/{key}
    try:
        path = urlsplit(raw).path
    except Exception:
        return None
    m2 = _PATH_RE.match(path if path.startswith("/api/") else f"/api{path}" if path.startswith("/storage/") else path)
    if m2:
        return m2.group(1)
    if path.startswith("/storage/"):
        m3 = re.match(
            r"^/storage/([0-9a-f]{40}(?:\.[A-Za-z0-9]{1,16})?)$", path
        )
        if m3:
            return m3.group(1)
    return None


def normalize_cover_url(cover_url: str | None) -> str | None:
    """Persist form: storage:{key} | gen:* | other remote URL | None."""
    if cover_url is None:
        return None
    raw = cover_url.strip()
    if not raw:
        return None
    if raw.startswith("gen:"):
        return raw
    if raw.startswith(STORAGE_PREFIX):
        key = raw[len(STORAGE_PREFIX) :]
        if not _KEY_RE.fullmatch(key):
            return raw
        return f"{STORAGE_PREFIX}{key}"
    key = storage_key_from_cover(raw)
    if key:
        return f"{STORAGE_PREFIX}{key}"
    return raw


def expand_cover_url(cover_url: str | None) -> str | None:
    """API response form: signed /api/storage/... for storage: keys."""
    if cover_url is None:
        return None
    raw = cover_url.strip()
    if not raw:
        return None
    if raw.startswith(STORAGE_PREFIX):
        key = raw[len(STORAGE_PREFIX) :]
        if not _KEY_RE.fullmatch(key):
            return raw
        return get_storage().signed_url(key, expires_seconds=_SIGNED_EXPIRES)
    return raw


def put_cover_image(*, data: bytes, content_type: str) -> str:
    """Write image bytes; return storage:{key}."""
    suffix = ".png"
    ct = (content_type or "").lower()
    if "jpeg" in ct or "jpg" in ct:
        suffix = ".jpg"
    elif "webp" in ct:
        suffix = ".webp"
    elif "png" in ct:
        suffix = ".png"
    key = get_storage().put(data=data, content_type=content_type or "image/png", suffix=suffix)
    return f"{STORAGE_PREFIX}{key}"
