"""抖音解析服务配置：域名规则与同步读取。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_DOUYIN_PARSER_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_DOUYIN_HOST_RULES: tuple[str, ...] = (
    "v.douyin.com",
    "douyin.com",
    "iesdouyin.com",
)


class DouyinRuleError(ValueError):
    """一条域名规则无法识别。"""


@dataclass(frozen=True)
class DouyinParserConfig:
    base_url: str
    api_key: str | None
    host_rules: tuple[str, ...]


def normalize_host_rule(raw: str) -> str:
    """把用户输入收成主机名。接受裸域名，也接受粘进来的整段链接。"""
    text = (raw or "").strip().lower()
    if not text:
        raise DouyinRuleError("域名为空")
    if "://" in text or "/" in text:
        parsed = urlparse(text if "://" in text else f"https://{text}")
        host = (parsed.hostname or "").lower().rstrip(".")
    else:
        host = text.rstrip(".")
    if not host or any(ch in host for ch in " /\\"):
        raise DouyinRuleError(f"无法识别的域名: {raw.strip()[:80]}")
    if len(host) > 253:
        raise DouyinRuleError("域名过长")
    return host


def normalize_host_rules(raw_rules: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_rules:
        host = normalize_host_rule(raw)
        if host in seen:
            continue
        seen.add(host)
        out.append(host)
    if len(out) > 30:
        raise DouyinRuleError("域名规则最多 30 条")
    return out


def match_host_rule(url: str, rules: list[str] | tuple[str, ...]) -> str | None:
    """命中域名本身或其子域名。多条同时命中时取更长的那条。"""
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if not host:
        return None
    matches = [rule for rule in rules if host == rule or host.endswith(f".{rule}")]
    if not matches:
        return None
    return max(matches, key=len)


def read_douyin_parser() -> DouyinParserConfig:
    """每次从数据库读。抓取进程和 API 进程不共享内存缓存。"""
    try:
        return _read_douyin_parser_from_db()
    except Exception as exc:  # noqa: BLE001
        logger.warning("load douyin parser config failed: %s", exc)
        return DouyinParserConfig(
            base_url=DEFAULT_DOUYIN_PARSER_BASE_URL,
            api_key=None,
            host_rules=DEFAULT_DOUYIN_HOST_RULES,
        )


def _read_douyin_parser_from_db() -> DouyinParserConfig:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.core.config import get_settings
    from app.models.fetch_network import FetchNetworkConfig

    engine = create_engine(get_settings().database_sync_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            row = session.get(FetchNetworkConfig, 1)
            if row is None:
                return DouyinParserConfig(
                    base_url=DEFAULT_DOUYIN_PARSER_BASE_URL,
                    api_key=None,
                    host_rules=DEFAULT_DOUYIN_HOST_RULES,
                )
            rules_raw = row.douyin_host_rules or []
            rules = tuple(str(item) for item in rules_raw if str(item).strip())
            base = (row.douyin_parser_base_url or "").strip() or DEFAULT_DOUYIN_PARSER_BASE_URL
            key = row.get_douyin_parser_api_key().strip() or None
            return DouyinParserConfig(base_url=base.rstrip("/"), api_key=key, host_rules=rules)
    finally:
        engine.dispose()
