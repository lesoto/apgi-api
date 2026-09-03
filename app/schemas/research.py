"""
Pydantic schemas for the research pilot domain (participants, consent,
studies, batteries, participant sessions, trial events).

Every request schema sets `extra="forbid"`: a client-supplied field that
isn't explicitly declared (e.g. trying to set `is_deleted`, `session_index`,
or `status` directly on a create request) is rejected with a 422 rather
than silently ignored or silently accepted — the hidden-field tampering
control called for in the governing doc's Phase 2 checklist.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import ConsentType, ParticipantSessionStatus, StudyStatus

_FORBID_EXTRA = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------


class ParticipantCreateRequest(BaseModel):
    model_config = _FORBID_EXTRA

    external_ref: Optional[str] = Field(
        None, max_length=255, description="Pseudonymous panel/recruitment ID"
    )
    contact_email: Optional[str] = Field(
        None, max_length=320, description="Contact email (will be encrypted at rest)"
    )
    demographics: Optional[dict[str, Any]] = Field(
        None, description="Self-reported demographics (will be encrypted at rest)"
    )


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    participant_id: str
    external_ref: Optional[str] = None
    is_deleted: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------


class ConsentGrantRequest(BaseModel):
    model_config = _FORBID_EXTRA

    consent_type: ConsentType
    consent_text: str = Field(
        ..., min_length=1, description="Exact consent text shown to the participant"
    )


class ConsentRevokeRequest(BaseModel):
    model_config = _FORBID_EXTRA

    consent_type: ConsentType


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consent_id: str
    consent_type: ConsentType
    version: str
    granted_at: datetime
    revoked_at: Optional[datetime] = None


class ConsentStatusResponse(BaseModel):
    """Effective (unrevoked, current-version) status for both required consents."""

    research_participation: bool
    data_sharing: bool


# ---------------------------------------------------------------------------
# Studies
# ---------------------------------------------------------------------------


class StudyCreateRequest(BaseModel):
    model_config = _FORBID_EXTRA

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    osf_registration_url: Optional[str] = Field(None, max_length=500)


class StudyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    study_id: str
    name: str
    description: Optional[str] = None
    osf_registration_url: Optional[str] = None
    status: StudyStatus
    created_at: datetime


# ---------------------------------------------------------------------------
# Batteries
# ---------------------------------------------------------------------------


class BatteryCreateRequest(BaseModel):
    model_config = _FORBID_EXTRA

    study_id: str
    name: str = Field(..., min_length=1, max_length=200)
    version: str = Field(..., min_length=1, max_length=20)
    form_label: str = Field("A", max_length=10)
    instrument_schema: Optional[dict[str, Any]] = None


class BatteryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    battery_id: str
    study_id: str
    name: str
    version: str
    form_label: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Participant Sessions
# ---------------------------------------------------------------------------


class ParticipantSessionCreateRequest(BaseModel):
    model_config = _FORBID_EXTRA

    participant_id: str
    study_id: str
    battery_id: str


class ParticipantSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    participant_session_id: str
    participant_id: str
    study_id: str
    battery_id: str
    session_index: int
    status: ParticipantSessionStatus
    scores: Optional[dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    release_state: str


# ---------------------------------------------------------------------------
# Trial events
# ---------------------------------------------------------------------------


class TrialEventIngestRequest(BaseModel):
    model_config = _FORBID_EXTRA

    task_type: str = Field(..., min_length=1, max_length=50)
    trial_index: int = Field(..., ge=0)
    response_value: Optional[dict[str, Any]] = None
    rt_ms: Optional[float] = Field(None, ge=0)
    correct: Optional[bool] = None
    raw_payload: Optional[dict[str, Any]] = Field(
        None,
        description="Full raw trial payload (RT distributions, logs) — written to restricted storage, not Postgres",
    )


class TrialEventBatchIngestRequest(BaseModel):
    model_config = _FORBID_EXTRA

    events: list[TrialEventIngestRequest] = Field(..., min_length=1, max_length=500)


class TrialEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trial_event_id: str
    task_type: str
    trial_index: int
    received_at: datetime


class SessionCompletionResponse(BaseModel):
    """The session-completion contract: what a client gets back once a
    participant session is marked complete and handed to scoring."""

    participant_session_id: str
    status: ParticipantSessionStatus
    trial_count: int
    completed_at: datetime
