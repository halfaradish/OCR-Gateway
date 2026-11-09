from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

API_KEY_PREFIX = "ocr_"
CREDENTIAL_AAD = b"account-credentials"
ADMIN_SALT = "admin-session"


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def display_prefix(key: str, length: int = 12) -> str:
    return key[:length]


def _admin_secret(master_key: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=ADMIN_SALT.encode("utf-8"),
    ).derive(master_key)


def _serializer(master_key: bytes) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_admin_secret(master_key), salt=ADMIN_SALT)


def create_admin_token(master_key: bytes, session_version: int) -> str:
    """Signed admin token embedding the session version (revoked by bumping the version)."""
    return _serializer(master_key).dumps({"sub": "admin", "sv": session_version})


def verify_admin_token(
    master_key: bytes, token: str, max_age: int, session_version: int
) -> bool:
    try:
        data = _serializer(master_key).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return False
    return (
        isinstance(data, dict)
        and data.get("sub") == "admin"
        and data.get("sv") == session_version
    )


def encrypt_credentials(master_key: bytes, credentials: dict[str, Any]) -> str:
    plaintext = json.dumps(credentials, ensure_ascii=False, sort_keys=True).encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = AESGCM(master_key).encrypt(nonce, plaintext, CREDENTIAL_AAD)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_credentials(master_key: bytes, encoded: str) -> dict[str, Any]:
    raw = base64.b64decode(encoded.encode("ascii"))
    nonce, ciphertext = raw[:12], raw[12:]
    plaintext = AESGCM(master_key).decrypt(nonce, ciphertext, CREDENTIAL_AAD)
    data = json.loads(plaintext.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("credentials payload is not an object")
    return data


def mask_secret(value: str, visible: int = 4) -> str:
    if len(value) <= visible:
        return "****"
    return value[:visible] + "****"
