from __future__ import annotations

from datetime import timedelta

import pytest
from jwt.exceptions import ExpiredSignatureError

from app.shared.security import (
    create_access_token,
    decode_access_token,
    token_fingerprint,
)


def test_token_fingerprint_is_stable_and_does_not_expose_token() -> None:
    token = "secret-token"

    fingerprint = token_fingerprint(token)

    assert fingerprint == token_fingerprint(token)
    assert fingerprint != token
    assert len(fingerprint) == 12


def test_created_token_decodes_to_original_subject() -> None:
    token, expires_in = create_access_token("42")

    first_payload = decode_access_token(token)
    second_payload = decode_access_token(token)

    assert first_payload == second_payload
    assert first_payload["sub"] == "42"
    assert expires_in > 0


def test_expired_token_raises_expired_signature_error() -> None:
    token, expires_in = create_access_token("42", expires_delta=timedelta(seconds=-1))

    assert expires_in < 0
    with pytest.raises(ExpiredSignatureError):
        decode_access_token(token)
