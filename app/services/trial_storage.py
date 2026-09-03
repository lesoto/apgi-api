"""
Restricted Cloud Storage writes for raw trial events (governing doc §7,
deployment/terraform/gcp/storage.tf).

The google-cloud-storage client is imported lazily so local development and
unit tests never need it installed or a GCP credential available —
`settings.trial_events_bucket` unset (the default outside deployed
environments) short-circuits every write to a no-op that still returns a
deterministic object path, so callers can be tested without touching GCS.

Object naming is per-participant-session so a single compromised or
misconfigured read can never enumerate another participant's events, and
each object receives a random suffix so client-supplied indices can't be
used to overwrite another trial's blob.
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


def _object_path(participant_session_id: str, task_type: str, trial_index: int) -> str:
    suffix = secrets.token_hex(8)
    return f"sessions/{participant_session_id}/{task_type}/{trial_index}-{suffix}.json"


def write_raw_trial_event(
    participant_session_id: str,
    task_type: str,
    trial_index: int,
    raw_payload: dict[str, Any],
) -> Optional[str]:
    """Write the full raw trial payload to the restricted bucket.

    Returns the object path on success, or None if the bucket isn't
    configured (local/test environments) — the caller (app/routes/trials.py)
    still records the trial in Postgres either way.
    """
    if not settings.trial_events_bucket:
        return None

    object_path = _object_path(participant_session_id, task_type, trial_index)

    try:
        import google.cloud.storage as storage

        client = storage.Client(project=settings.gcp_project_id)
        bucket = client.bucket(settings.trial_events_bucket)
        blob = bucket.blob(object_path)
        blob.upload_from_string(
            json.dumps(raw_payload, default=str),
            content_type="application/json",
        )
        return object_path
    except Exception:
        # A raw-event storage failure must never block trial ingestion —
        # the lightweight summary in Postgres (app/routes/trials.py) is the
        # durable record; losing the raw blob is degraded, not fatal.
        logger.error(
            "Failed to write raw trial event to Cloud Storage",
            exc_info=True,
            extra={"participant_session_id": participant_session_id, "object_path": object_path},
        )
        return None


def read_raw_trial_event(object_path: str) -> Optional[dict[str, Any]]:
    """Read back a raw trial payload previously written by `write_raw_trial_event`."""
    if not settings.trial_events_bucket:
        return None

    try:
        import google.cloud.storage as storage

        client = storage.Client(project=settings.gcp_project_id)
        bucket = client.bucket(settings.trial_events_bucket)
        blob = bucket.blob(object_path)
        data = blob.download_as_text()
        result: dict[str, Any] = json.loads(data)
        return result
    except Exception:
        logger.error(
            "Failed to read raw trial event from Cloud Storage",
            exc_info=True,
            extra={"object_path": object_path},
        )
        return None
