"""
Participant Session and Trial Event Routes (Phase 2).

Trial ingestion is the hot path apgi-battery's jsPsych tasks hit once per
trial (or once per batch at the end of a block): every write is gated on
RESEARCH_PARTICIPATION consent, ownership-checked against the parent
participant session, rate-limited by the global RateLimitingMiddleware
(app/middleware/rate_limiting.py — no per-route opt-in needed), and
schema-validated with `extra="forbid"` so a client can't smuggle fields
like `correct` for a task type whose grading happens server-side only via
raw_payload.

The session-completion contract (POST .../complete) is what apgi-battery
calls exactly once, at the end of a battery administration: it is
idempotent (repeat calls return the same completed state rather than
erroring) and is the hook Phase 3-4's scoring pipeline attaches to.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    Battery,
    ConsentType,
    Participant,
    ParticipantSession,
    ParticipantSessionStatus,
    Study,
    TrialEvent,
)
from app.models.schemas import ErrorResponse, TokenPayload
from app.schemas.research import (
    ParticipantSessionCreateRequest,
    ParticipantSessionResponse,
    SessionCompletionResponse,
    TrialEventBatchIngestRequest,
    TrialEventResponse,
)
from app.services.authorization import Role, get_current_user, has_any_role, log_audit_event
from app.services.consent import require_consent
from app.services.rls import set_rls_context
from app.services.trial_storage import write_raw_trial_event

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Trials"],
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not Found"},
    },
)


def _get_session_or_404(db: Session, participant_session_id: str) -> ParticipantSession:
    session = (
        db.query(ParticipantSession)
        .filter(ParticipantSession.participant_session_id == participant_session_id)
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Participant session not found"
        )
    return session


def _check_session_access(
    db: Session, session: ParticipantSession, current_user: TokenPayload
) -> Participant:
    if has_any_role(current_user.roles, [Role.ADMIN, Role.RESEARCHER]):
        participant = (
            db.query(Participant)
            .filter(Participant.participant_id == session.participant_id)
            .first()
        )
        if participant is None:  # pragma: no cover - FK guarantees this can't happen
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found"
            )
        return participant

    participant = (
        db.query(Participant).filter(Participant.participant_id == session.participant_id).first()
    )
    if participant is None or participant.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this session"
        )
    return participant


@router.post(
    "/v1/participant-sessions",
    response_model=ParticipantSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_participant_session(
    request: ParticipantSessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> ParticipantSession:
    set_rls_context(db, current_user)

    participant = (
        db.query(Participant).filter(Participant.participant_id == request.participant_id).first()
    )
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    if (
        not has_any_role(current_user.roles, [Role.ADMIN, Role.RESEARCHER])
        and participant.user_id != current_user.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this participant"
        )

    if db.query(Study).filter(Study.study_id == request.study_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if db.query(Battery).filter(Battery.battery_id == request.battery_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Battery not found")

    require_consent(db, request.participant_id, ConsentType.RESEARCH_PARTICIPATION)

    next_index = (
        db.query(func.max(ParticipantSession.session_index))
        .filter(
            ParticipantSession.participant_id == request.participant_id,
            ParticipantSession.study_id == request.study_id,
        )
        .scalar()
        or 0
    ) + 1

    session = ParticipantSession(
        participant_id=request.participant_id,
        study_id=request.study_id,
        battery_id=request.battery_id,
        session_index=next_index,
        status=ParticipantSessionStatus.IN_PROGRESS,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    log_audit_event(
        db=db,
        user_id=current_user.user_id,
        action="participant_session:create",
        resource_type="participant_session",
        resource_id=session.participant_session_id,
        details={"session_index": next_index},
    )
    return session


@router.post(
    "/v1/participant-sessions/{participant_session_id}/trials",
    response_model=List[TrialEventResponse],
    status_code=status.HTTP_201_CREATED,
)
async def ingest_trial_events(
    participant_session_id: str,
    request: TrialEventBatchIngestRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> List[TrialEvent]:
    set_rls_context(db, current_user)
    session = _get_session_or_404(db, participant_session_id)
    _check_session_access(db, session, current_user)

    if session.status not in (
        ParticipantSessionStatus.IN_PROGRESS,
        ParticipantSessionStatus.SCHEDULED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot ingest trials into a session with status {session.status.value}",
        )

    require_consent(db, str(session.participant_id), ConsentType.RESEARCH_PARTICIPATION)

    created: List[TrialEvent] = []
    for event in request.events:
        raw_gcs_object = None
        if event.raw_payload is not None:
            raw_gcs_object = write_raw_trial_event(
                participant_session_id, event.task_type, event.trial_index, event.raw_payload
            )

        trial = TrialEvent(
            participant_session_id=participant_session_id,
            task_type=event.task_type,
            trial_index=event.trial_index,
            response_value=event.response_value,
            rt_ms=event.rt_ms,
            correct=event.correct,
            raw_gcs_object=raw_gcs_object,
        )
        db.add(trial)
        created.append(trial)

    if session.status == ParticipantSessionStatus.SCHEDULED:
        session.status = ParticipantSessionStatus.IN_PROGRESS  # type: ignore[assignment]
        session.started_at = datetime.now(timezone.utc)  # type: ignore[assignment]

    db.commit()
    for trial in created:
        db.refresh(trial)

    return created


@router.post(
    "/v1/participant-sessions/{participant_session_id}/complete",
    response_model=SessionCompletionResponse,
    summary="Session completion contract",
    description="Marks a participant session complete. Idempotent: calling this again on an "
    "already-completed session returns the same result rather than erroring.",
)
async def complete_participant_session(
    participant_session_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> SessionCompletionResponse:
    set_rls_context(db, current_user)
    session = _get_session_or_404(db, participant_session_id)
    _check_session_access(db, session, current_user)

    trial_count = (
        db.query(func.count(TrialEvent.trial_event_id))
        .filter(TrialEvent.participant_session_id == participant_session_id)
        .scalar()
        or 0
    )

    if session.status != ParticipantSessionStatus.COMPLETED:
        session.status = ParticipantSessionStatus.COMPLETED  # type: ignore[assignment]
        session.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        db.commit()
        db.refresh(session)

        log_audit_event(
            db=db,
            user_id=current_user.user_id,
            action="participant_session:complete",
            resource_type="participant_session",
            resource_id=participant_session_id,
            details={"trial_count": trial_count},
        )

        # Phase 3-4 attaches scoring here (app/services/scoring.py). Enqueued
        # best-effort — a scoring failure must never fail session completion
        # for the client, which has already finished the battery.
        try:
            from app.tasks.scoring_tasks import score_participant_session

            score_participant_session.delay(participant_session_id)  # type: ignore[attr-defined]
        except Exception:
            logger.info(
                "Scoring task not enqueued (scoring pipeline not yet configured)",
                extra={"participant_session_id": participant_session_id},
            )

    return SessionCompletionResponse(
        participant_session_id=participant_session_id,
        status=session.status,
        trial_count=trial_count,
        completed_at=session.completed_at,
    )
