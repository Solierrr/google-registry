"""Testes de app.infrastructure.auth.bearer_auth.require_authenticated_user"""

import time
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwk, jwt

from app.config import get_settings
from app.infrastructure.auth.bearer_auth import require_authenticated_user
from app.infrastructure.auth.jwks_client import JwksUnavailableError

KID = "key-1"
ISSUER = "solaria-auth"


def _pair() -> tuple[bytes, dict[str, Any]]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return pem, {**jwk.construct(pem, "RS256").public_key().to_dict(), "kid": KID}


PRIVATE_PEM, PUBLIC_JWK = _pair()
OTHER_PEM, _ = _pair()


class FakeJwks:
    def __init__(self, keys: dict[str, dict[str, Any]] | None = None, unavailable: bool = False) -> None:
        self.keys = keys if keys is not None else {KID: PUBLIC_JWK}
        self.unavailable = unavailable
        self.requested: list[str] = []

    async def get_key(self, kid: str) -> dict[str, Any] | None:
        self.requested.append(kid)
        if self.unavailable:
            raise JwksUnavailableError
        return self.keys.get(kid)


def _token(pem: bytes = PRIVATE_PEM, kid: str | None = KID, **claims: Any) -> str:
    payload = {"sub": "user-1", "iss": ISSUER, "exp": int(time.time()) + 300, "token_type": "access", **claims}
    headers = {"kid": kid} if kid else {}
    return jwt.encode({k: v for k, v in payload.items() if v is not None}, pem, algorithm="RS256", headers=headers)


async def _authenticate(token: str | None, jwks: FakeJwks | None = None) -> str:
    credentials = None if token is None else HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return await require_authenticated_user(credentials, jwks or FakeJwks(), get_settings())


async def _status(token: str | None, jwks: FakeJwks | None = None) -> int:
    with pytest.raises(HTTPException) as raised:
        await _authenticate(token, jwks)
    return raised.value.status_code


async def test_valid_access_token_returns_the_subject():
    jwks = FakeJwks()

    assert await _authenticate(_token(), jwks) == "user-1"
    assert jwks.requested == [KID]


async def test_non_text_subject_is_401():
    assert await _status(_token(sub=42)) == 401


async def test_missing_credentials_are_401():
    assert await _status(None) == 401


async def test_malformed_token_is_401():
    assert await _status("isto-nao-e-um-jwt") == 401


async def test_token_without_kid_is_401():
    assert await _status(_token(kid=None)) == 401


async def test_unknown_kid_is_401():
    assert await _status(_token(kid="outra"), FakeJwks()) == 401


async def test_token_signed_with_another_key_is_401():
    assert await _status(_token(pem=OTHER_PEM)) == 401


async def test_expired_token_is_401():
    assert await _status(_token(exp=int(time.time()) - 10)) == 401


async def test_token_without_expiration_is_401():
    payload = {"sub": "user-1", "iss": ISSUER, "token_type": "access"}
    token = jwt.encode(payload, PRIVATE_PEM, algorithm="RS256", headers={"kid": KID})

    assert await _status(token) == 401


async def test_token_from_another_issuer_is_401():
    assert await _status(_token(iss="outro-emissor")) == 401


@pytest.mark.parametrize("token_type", ["refresh", None, "service"])
async def test_only_access_tokens_are_accepted(token_type):
    assert await _status(_token(token_type=token_type)) == 401


async def test_token_without_subject_is_401():
    assert await _status(_token(sub=None)) == 401


async def test_unavailable_jwks_is_503():
    assert await _status(_token(), FakeJwks(unavailable=True)) == 503
