"""Reversible sealed box for Intervention Queue secrets (DEC-013).

Not for KG / TZ payload. Ciphertext only. No third-party crypto dependency.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from core.config import get_settings

_VERSION = b"asf1"


class SecretsBoxError(ValueError):
    """Seal/unseal failed."""


def intervention_key_material() -> bytes:
    settings = get_settings()
    explicit = (settings.asf_intervention_key or "").strip()
    if explicit:
        return hashlib.sha256(explicit.encode("utf-8")).digest()
    derived = "|".join(
        [
            (settings.console_token or "").strip(),
            (settings.owner_telegram_id or "").strip(),
            "asf-intervention-v1",
        ]
    )
    return hashlib.sha256(derived.encode("utf-8")).digest()


def _stream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def seal_secret(plaintext: str) -> str:
    raw = (plaintext or "").encode("utf-8")
    if not raw:
        raise SecretsBoxError("empty secret")
    key = intervention_key_material()
    nonce = secrets.token_bytes(16)
    ct = bytes(a ^ b for a, b in zip(raw, _stream(key, nonce, len(raw))))
    mac = hmac.new(key, _VERSION + nonce + ct, hashlib.sha256).digest()
    blob = _VERSION + nonce + mac + ct
    return base64.urlsafe_b64encode(blob).decode("ascii")


def unseal_secret(token: str) -> str:
    try:
        blob = base64.urlsafe_b64decode((token or "").encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise SecretsBoxError("invalid sealed secret") from exc
    if len(blob) < 16 + 32 + len(_VERSION):
        raise SecretsBoxError("invalid sealed secret")
    version, rest = blob[:4], blob[4:]
    if version != _VERSION:
        raise SecretsBoxError("unsupported secret box version")
    nonce, mac, ct = rest[:16], rest[16:48], rest[48:]
    key = intervention_key_material()
    expected = hmac.new(key, _VERSION + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise SecretsBoxError("secret box MAC mismatch")
    raw = bytes(a ^ b for a, b in zip(ct, _stream(key, nonce, len(ct))))
    return raw.decode("utf-8")
