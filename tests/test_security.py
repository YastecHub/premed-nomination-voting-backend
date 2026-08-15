"""
Tests for the security utility module.

These are pure unit tests — no DB, no network.
"""

import pytest
from app.core.security import hash_matric, hash_pin, verify_pin, create_access_token, decode_access_token


def test_hash_matric_is_deterministic():
    """Same matric always produces same hash."""
    h1 = hash_matric("19/0000")
    h2 = hash_matric("19/0000")
    assert h1 == h2


def test_hash_matric_is_case_insensitive():
    """Matric numbers are normalized to uppercase before hashing."""
    assert hash_matric("19/abcd") == hash_matric("19/ABCD")


def test_hash_matric_strips_whitespace():
    assert hash_matric("  19/0000  ") == hash_matric("19/0000")


def test_hash_matric_student_vs_admin_differ():
    """Student and admin hashes of the same matric must differ (different peppers)."""
    student_hash = hash_matric("19/0000", admin=False)
    admin_hash = hash_matric("19/0000", admin=True)
    assert student_hash != admin_hash


def test_hash_matric_never_plaintext():
    """Hash output must not contain the input matric."""
    matric = "19/ADMIN"
    result = hash_matric(matric)
    assert matric not in result
    assert matric.lower() not in result


def test_hash_pin_bcrypt():
    pin = "123456"
    hashed = hash_pin(pin)
    assert hashed != pin
    assert verify_pin(pin, hashed)


def test_verify_pin_wrong():
    hashed = hash_pin("correct")
    assert not verify_pin("wrong", hashed)


def test_jwt_round_trip():
    token = create_access_token("abc123hash", "student")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "abc123hash"
    assert payload["role"] == "student"


def test_jwt_invalid_token():
    result = decode_access_token("not.a.real.token")
    assert result is None


def test_jwt_does_not_contain_matric():
    """The JWT must not embed the original matric number in any field."""
    import base64, json
    matric = "19/STUDENT"
    from app.core.security import hash_matric
    hashed = hash_matric(matric)
    token = create_access_token(hashed, "student")
    # Decode payload without verification
    parts = token.split(".")
    padded = parts[1] + "=="
    decoded = json.loads(base64.urlsafe_b64decode(padded))
    assert matric not in str(decoded)
    assert matric.lower() not in str(decoded)
