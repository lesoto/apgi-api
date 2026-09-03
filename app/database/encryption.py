"""
Field-level encryption for participant PII (governing doc §7.2).

Participant contact/demographic fields are stored ciphertext-only using
Fernet (AES-128-CBC + HMAC-SHA256, authenticated). The key lives in Secret
Manager in deployed environments (PII_ENCRYPTION_KEY, see
deployment/terraform/gcp/secrets.tf) and is never derived from anything
else — losing it means the PII is unrecoverable by design, which is the
desired failure mode for a right-to-erasure-compliant store (see
app/tasks/deletion_tasks.py: destroying the key alone renders any residual
backup copy of these columns unreadable).
"""

from __future__ import annotations

from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.config import settings


class EncryptionNotConfiguredError(RuntimeError):
    """Raised when PII_ENCRYPTION_KEY is required but not set."""


def _fernet() -> Fernet:
    if not settings.pii_encryption_key:
        raise EncryptionNotConfiguredError(
            "PII_ENCRYPTION_KEY is not configured. Set it before reading or "
            "writing any encrypted participant field."
        )
    return Fernet(settings.pii_encryption_key.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a single string value, returning a base64 ciphertext token."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext token produced by `encrypt_value`."""
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Ciphertext is invalid or was encrypted with a different key.") from exc


class EncryptedString(TypeDecorator[str]):
    """SQLAlchemy column type: transparently encrypts on write, decrypts on read.

    Ciphertext is ~2.7x the plaintext length plus a fixed overhead; the
    backing column is sized generously to avoid truncation.
    """

    impl = String(1024)
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return encrypt_value(value)

    def process_result_value(self, value: Optional[str], dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return decrypt_value(value)
