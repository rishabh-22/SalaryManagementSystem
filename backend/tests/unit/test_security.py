# ruff: noqa: E501
from datetime import timedelta

import jwt
import pytest

from app.core import security
from app.core.config import settings


def test_hash_is_not_plaintext_and_verifies():
    hashed = security.hash_password("S3cret!pass")
    assert hashed != "S3cret!pass"
    assert security.verify_password("S3cret!pass", hashed)


def test_verify_rejects_wrong_password():
    hashed = security.hash_password("S3cret!pass")
    assert not security.verify_password("other", hashed)


def test_hash_is_salted():
    assert security.hash_password("same") != security.hash_password("same")


def test_token_round_trip_carries_claims():
    token = security.create_access_token("42", "hr_manager")
    claims = security.decode_access_token(token)
    assert claims["sub"] == "42"
    assert claims["role"] == "hr_manager"
    assert "exp" in claims


def test_expired_token_is_rejected():
    token = security.create_access_token("1", "admin", expires_delta=timedelta(seconds=-5))
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(token)


def test_tampered_token_is_rejected():
    token = security.create_access_token("1", "viewer")
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(token[:-2] + ("AA" if not token.endswith("AA") else "BB"))


def test_token_signed_with_other_secret_is_rejected():
    forged = jwt.encode({"sub": "1", "role": "admin"}, "not-the-secret", algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(forged)
