"""
Tamper-evident signing for audit log entries (governing doc §7.4).

Score generation and report-access events are the ones the plan calls out
by name, but every audit entry is signed uniformly — there is no reliable
way to guarantee only "sensitive" actions ever get logged as such, and an
unsigned subset would just be an unverified subset. HMAC-SHA256 over the
canonical fields means altering `details`, `status`, or the actor after the
fact is detectable without needing a separate immutable log store.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Optional

from app.config import settings


class AuditSigningNotConfiguredError(RuntimeError):
    pass


def _canonical_payload(
    audit_id: str,
    user_id: Optional[str],
    action: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    status: str,
    details: Optional[dict[str, Any]],
) -> bytes:
    # sort_keys=True makes this deterministic regardless of dict insertion order.
    payload = {
        "audit_id": audit_id,
        "user_id": user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "status": status,
        "details": details or {},
    }
    return json.dumps(payload, sort_keys=True, default=str).encode("utf-8")


def sign_audit_entry(
    audit_id: str,
    user_id: Optional[str],
    action: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    status: str,
    details: Optional[dict[str, Any]],
) -> str:
    if not settings.audit_signing_key:
        raise AuditSigningNotConfiguredError(
            "AUDIT_SIGNING_KEY is not configured. Set it before writing audit log entries."
        )
    payload = _canonical_payload(
        audit_id, user_id, action, resource_type, resource_id, status, details
    )
    return hmac.new(settings.audit_signing_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_audit_entry(
    audit_id: str,
    user_id: Optional[str],
    action: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    status: str,
    details: Optional[dict[str, Any]],
    signature: Optional[str],
) -> bool:
    """True iff `signature` matches the entry's fields. A NULL signature
    (legacy, pre-signing rows) is never "valid" — callers that need to
    distinguish "legacy" from "tampered" should check `signature is None`
    themselves before calling this."""
    if not signature or not settings.audit_signing_key:
        return False
    expected = sign_audit_entry(
        audit_id, user_id, action, resource_type, resource_id, status, details
    )
    return hmac.compare_digest(expected, signature)
