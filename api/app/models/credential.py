"""Provider 的凭据表。一条 credential = 一个 provider 的一个账号。

Auth 信息（api_key）以 AES-GCM 密文存储（api_key_enc）。其它厂商特性字段放进
`config` JSON 字段；典型如 Azure 的 api_version、Vertex 的 project/location。
"""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Credential(Base, TimestampMixin):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # 支持的 modality 列表（"language" / "embedding" / "speech_to_text" / "text_to_speech"）
    modalities_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    api_key_enc: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(nullable=True)

    # ── 密码 ──
    def set_api_key(self, raw: str) -> None:
        from app.core.crypto import encrypt

        self.api_key_enc = encrypt(raw) if raw else None

    def get_api_key(self) -> str:
        from app.core.crypto import decrypt

        return decrypt(self.api_key_enc or "")

    def mask(self) -> str:
        """仅显示前 4 + ***。admin GET 时使用。"""
        api_key = self.get_api_key()
        if not api_key:
            return ""
        if len(api_key) <= 4:
            return "***"
        return api_key[:4] + "***"
