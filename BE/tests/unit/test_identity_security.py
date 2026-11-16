from __future__ import annotations

import pytest

from BE.app.modules.identity.security import (
    hash_password,
    new_secret,
    normalize_email,
    secret_hash,
    validate_password,
    verify_password,
)
from BE.app.modules.identity.domain import Principal
from uuid import uuid4


def test_email_normalization_is_case_insensitive() -> None:
    assert normalize_email("  Demo.User@Example.COM ") == "demo.user@example.com"


@pytest.mark.parametrize("value", ["missing-at", "a@b", "a b@example.com"])
def test_invalid_email_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_email(value)


def test_argon2_password_hash_is_one_way_and_salted() -> None:
    first = hash_password("TravelDemo123")
    second = hash_password("TravelDemo123")
    assert first != second
    assert "TravelDemo123" not in first
    assert verify_password("TravelDemo123", first)
    assert not verify_password("wrong-password", first)


@pytest.mark.parametrize("value", ["short1", "onlyletterslong", "12345678901"])
def test_password_policy(value: str) -> None:
    with pytest.raises(ValueError):
        validate_password(value)


def test_opaque_secrets_are_random_and_only_hashes_compare() -> None:
    first, second = new_secret(), new_secret()
    assert first != second
    assert len(first) >= 40
    assert secret_hash(first) == secret_hash(first)
    assert secret_hash(first) != secret_hash(second)
    assert first not in secret_hash(first)


def test_principal_role_policy_denies_by_default() -> None:
    principal = Principal(uuid4(), uuid4(), frozenset({"traveler"}), "test-correlation")
    assert principal.requires("traveler") is principal
    with pytest.raises(PermissionError):
        principal.requires("administrator")
