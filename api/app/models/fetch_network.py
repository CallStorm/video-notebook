"""抓取网络配置：分平台 Cookie 开关 + 代理（全站一行）。"""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FetchNetworkConfig(Base, TimestampMixin):
    """id 固定为 1。Cookie 正文落盘，不进本表。"""

    __tablename__ = "fetch_network_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    youtube_cookie_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bilibili_cookie_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # legacy column retained for existing DBs; platform removed from product surface
    douyin_cookie_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    proxy_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proxy_url_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # e.g. ["youtube", "bilibili"]
    proxy_apply_to: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    def set_proxy_url(self, raw: str | None) -> None:
        from app.core.crypto import encrypt

        cleaned = (raw or "").strip()
        self.proxy_url_enc = encrypt(cleaned) if cleaned else None

    def get_proxy_url(self) -> str:
        from app.core.crypto import decrypt

        return decrypt(self.proxy_url_enc or "")
