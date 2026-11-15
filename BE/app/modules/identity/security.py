"""Credential primitives. Plaintext values never cross this module unnecessarily."""

from __future__ import annotations

import hashlib
import re
import secrets

from pwdlib import PasswordHash


_password_hash = PasswordHash.recommended()
_email_pattern = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str) -> str:
    email = value.strip().casefold()
    if len(email) > 320 or not _email_pattern.fullmatch(email):
        raise ValueError("email không hợp lệ")
    return email


def validate_password(value: str) -> str:
    if len(value) < 10 or len(value) > 128:
        raise ValueError("mật khẩu phải từ 10 đến 128 ký tự")
    if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
        raise ValueError("mật khẩu cần có chữ và số")
    return value


def hash_password(value: str) -> str:
    return _password_hash.hash(validate_password(value))


def verify_password(value: str, encoded: str) -> bool:
    try:
        return _password_hash.verify(value, encoded)
    except Exception:
        return False


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
