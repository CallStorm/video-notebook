"""Crypto 单元测试：AES-GCM 加解密应可逆。"""
from __future__ import annotations

from app.core.crypto import CryptoError, decrypt, encrypt


def test_encrypt_decrypt_round_trip():
    plain = "sk-test-12345678"
    cipher = encrypt(plain)
    assert cipher and cipher != plain
    assert decrypt(cipher) == plain


def test_encrypt_empty_returns_empty():
    assert encrypt("") == ""
    assert decrypt("") == ""


def test_decrypt_garbage_raises_crypto_error():
    import pytest

    with pytest.raises(CryptoError):
        decrypt("not-base64-!!!")


def test_two_encrypts_of_same_text_differ():
    """AES-GCM 用随机 nonce，相同明文两次加密结果应该不同。"""
    a = encrypt("same-text")
    b = encrypt("same-text")
    assert a != b
    assert decrypt(a) == decrypt(b) == "same-text"
