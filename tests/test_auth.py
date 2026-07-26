"""Tests for authentication services — tokens, passwords, edge cases."""
import pytest
from datetime import datetime, timedelta, timezone
from app.services.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, verify_refresh_token,
    create_reset_token, verify_reset_token,
    create_email_verification_token, verify_email_token,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("testpass123")
        assert verify_password("testpass123", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("testpass123")
        assert not verify_password("wrongpass", hashed)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt

    def test_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed)
        assert not verify_password("notempty", hashed)


class TestAccessTokens:
    def test_create_access_token(self):
        token = create_access_token(42)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_access_token_contains_user_id(self):
        from jose import jwt
        from app.config import settings
        token = create_access_token(99)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "99"
        assert payload["type"] == "access"


class TestRefreshTokens:
    def test_create_and_verify(self):
        token = create_refresh_token(42)
        user_id = verify_refresh_token(token)
        assert user_id == 42

    def test_invalid_token_returns_none(self):
        assert verify_refresh_token("garbage.token.here") is None

    def test_access_token_rejected_as_refresh(self):
        token = create_access_token(42)
        assert verify_refresh_token(token) is None

    def test_expired_token_returns_none(self):
        from jose import jwt
        from app.config import settings
        payload = {"sub": "42", "exp": datetime.now(timezone.utc) - timedelta(hours=1), "type": "refresh"}
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        assert verify_refresh_token(token) is None


class TestResetTokens:
    def test_create_and_verify(self):
        token = create_reset_token(55)
        user_id = verify_reset_token(token)
        assert user_id == 55

    def test_invalid_token_returns_none(self):
        assert verify_reset_token("bad") is None

    def test_refresh_token_rejected_as_reset(self):
        token = create_refresh_token(55)
        assert verify_reset_token(token) is None

    def test_expired_reset_returns_none(self):
        from jose import jwt
        from app.config import settings
        payload = {"sub": "55", "exp": datetime.now(timezone.utc) - timedelta(hours=2), "type": "reset"}
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        assert verify_reset_token(token) is None


class TestEmailVerificationTokens:
    def test_create_and_verify(self):
        token = create_email_verification_token(77)
        user_id = verify_email_token(token)
        assert user_id == 77

    def test_wrong_type_rejected(self):
        token = create_access_token(77)
        assert verify_email_token(token) is None

    def test_invalid_returns_none(self):
        assert verify_email_token("nope") is None
