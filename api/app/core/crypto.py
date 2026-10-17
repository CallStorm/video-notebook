"""AES-GCM 加解密（Phase 3 起，用 env MASTER_SECRET 主密钥）。

格式：base64( nonce(12) || ciphertext || tag(16) )
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings
from app.core.errors import AppError

_NONCE_LEN = 12


class CryptoError(AppError):
    status_code = 500
    code = "crypto_error"


def _key() -> bytes:
    raw = get_settings().master_secret.encode("utf-8")
    if len(raw) < 32:
        # 短于 32 字节右补 0；长于 32 字节截断。生产请保证恰好 32 字节。
        raw = raw.ljust(32, b"\x00")[:32]
    return raw


def encrypt(plaintext: str) -> str:
    if plaintext == "":
        return ""
    try:
        aes = AESGCM(_key())
        nonce = os.urandom(_NONCE_LEN)
        ct = aes.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
        return base64.b64encode(nonce + ct).decode("ascii")
    except Exception as exc:
        raise CryptoError(f"encrypt failed: {exc.__class__.__name__}") from exc


def decrypt(ciphertext_b64: str) -> str:
    if not ciphertext_b64:
        return ""
    try:
        raw = base64.b64decode(ciphertext_b64.encode("ascii"))
        nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
        aes = AESGCM(_key())
        plain = aes.decrypt(nonce, ct, associated_data=None)
        return plain.decode("utf-8")
    except Exception as exc:
        raise CryptoError(f"decrypt failed: {exc.__class__.__name__}") from exc
