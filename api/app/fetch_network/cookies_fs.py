"""Cookie 文件落盘（Netscape）。"""
from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.fetch_network.types import PLATFORMS, PlatformKey

_DOMAIN: dict[PlatformKey, str] = {
    "youtube": ".youtube.com",
    "bilibili": ".bilibili.com",
}


def cookies_dir() -> Path:
    path = get_settings().storage_root / "secrets" / "cookies"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cookie_path(platform: PlatformKey) -> Path:
    return cookies_dir() / f"{platform}.txt"


def cookie_exists(platform: PlatformKey) -> bool:
    path = cookie_path(platform)
    return path.is_file() and path.stat().st_size > 0


def read_cookie_text(platform: PlatformKey) -> str | None:
    path = cookie_path(platform)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    return text or None


def write_cookie_text(platform: PlatformKey, raw: str) -> None:
    normalized = normalize_cookie_text(platform, raw)
    path = cookie_path(platform)
    path.write_text(normalized, encoding="utf-8")


def clear_cookie(platform: PlatformKey) -> None:
    path = cookie_path(platform)
    if path.is_file():
        path.unlink()


def normalize_cookie_text(platform: PlatformKey, raw: str) -> str:
    text = raw.strip().replace("\r\n", "\n")
    if not text:
        raise ValueError("cookie 内容为空")
    if _looks_like_netscape(text):
        if not text.startswith("#"):
            text = "# Netscape HTTP Cookie File\n" + text
        return text + ("\n" if not text.endswith("\n") else "")
    # name=value; name2=value2
    if "=" in text and "\t" not in text.split("\n", 1)[0]:
        return _header_to_netscape(platform, text)
    raise ValueError("无法识别 cookie 格式，请粘贴 Netscape 或 name=value; ...")


def _looks_like_netscape(text: str) -> bool:
    head = text.lstrip()[:80].lower()
    if "netscape" in head:
        return True
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        return line.count("\t") >= 5 or line.startswith(".")
    return False


def _header_to_netscape(platform: PlatformKey, header: str) -> str:
    domain = _DOMAIN[platform]
    lines = ["# Netscape HTTP Cookie File", "# Converted from Cookie header"]
    for part in header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name, value = name.strip(), value.strip()
        if not name:
            continue
        # domain, flag, path, secure, expiry, name, value
        lines.append(f"{domain}\tTRUE\t/\tFALSE\t0\t{name}\t{value}")
    if len(lines) <= 2:
        raise ValueError("未解析到有效 cookie 键值")
    return "\n".join(lines) + "\n"


def cookie_header_from_file(platform: PlatformKey) -> str | None:
    """从 Netscape 文件拼 Cookie 请求头（给 httpx）。"""
    text = read_cookie_text(platform)
    if not text:
        return None
    pairs: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        name, value = parts[5], parts[6]
        pairs.append(f"{name}={value}")
    return "; ".join(pairs) if pairs else None


def assert_known_platform(value: str) -> PlatformKey:
    if value not in PLATFORMS:
        raise ValueError(f"unknown platform: {value}")
    return value  # type: ignore[return-value]
