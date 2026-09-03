"""
Longitudinal Metrics and MDC-Gated Change Reporting (Phase 5).

GET /v1/longitudinal/metrics computes ICC/SEM/MDC95 for a battery+task+metric
across all participants with completed sessions at both requested indices —
a research-facing aggregate endpoint, same permission level as /v1/norms and
/v1/instrument/psychometrics (any authenticated user).

GET /v1/participants/{id}/change-report is the MDC-gated feature itself: it
is only available to an active subscriber (or staff, for research use) and
it reports a delta as a real change only once it clears the population's
MDC95 — never the raw, possibly noise-driven, difference.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import (
    Participant,
    ParticipantSession,
    ParticipantSessionStatus,
    Subscription,
)
from app.models.schemas import ErrorResponse, TokenPayload
from app.schemas.reporting import ChangeReportResponse, LongitudinalMetricsResponse
from app.services.authorization import Role, get_current_user, has_any_role
from app.services.identifiers import current_release_state
from app.services.longitudinal_metrics import classify_change, compute_longitudinal_metrics
from app.services.rls import set_rls_context

router = APIRouter(
    tags=["Longitudinal"],
    responses={404: {"model": ErrorResponse, "description": "Not Found"}},
)

_ALLOWED_METRICS = {"accuracy", "mean_rt_ms", "median_rt_ms"}


def _score_at_index(
    db: Session,
    participant_id: str,
    study_id: str,
    battery_id: str,
    session_index: int,
    task_type: str,
    metric: str,
) -> Optional[float]:
    session = (
        db.query(ParticipantSession)
        .filter(
            ParticipantSession.participant_id == participant_id,
            ParticipantSession.study_id == study_id,
            ParticipantSession.battery_id == battery_id,
            ParticipantSession.session_index == session_index,
            ParticipantSession.status == ParticipantSessionStatus.COMPLETED,
            ParticipantSession.scores.isnot(None),
        )
        .first()
    )
    if session is None:
        return None
    session_scores: dict[str, Any] = session.scores or {}  # type: ignore[assignment]
    value = session_scores.get("tasks", {}).get(task_type, {}).get(metric)
    return float(value) if value is not None else None


def _paired_measurements(
    db: Session,
    study_id: str,
    battery_id: str,
    task_type: str,
    metric: str,
    index_a: int,
    index_b: int,
) -> list[list[float]]:
    participant_ids = [
        row[0]
        for row in db.query(ParticipantSession.participant_id)
        .filter(
            ParticipantSession.study_id == study_id, ParticipantSession.battery_id == battery_id
        )
        .distinct()
        .all()
    ]
    pairs = []
    for participant_id in participant_ids:
        a = _score_at_index(db, participant_id, study_id, battery_id, index_a, task_type, metric)
        b = _score_at_index(db, participant_id, study_id, battery_id, index_b, task_type, metric)
        if a is not None and b is not None:
            pairs.append([a, b])
    return pairs


@router.get("/v1/longitudinal/metrics", response_model=LongitudinalMetricsResponse)
async def get_longitudinal_metrics(
    study_id: str = Query(...),
    battery_id: str = Query(...),
    task_type: str = Query(...),
    metric: str = Query(...),
    session_index_a: int = Query(1, ge=1),
    session_index_b: int = Query(2, ge=1),
    db: Session = Depends(get_db),
    _current_user: TokenPayload = Depends(get_current_user),
) -> LongitudinalMetricsResponse:
    if metric not in _ALLOWED_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"metric must be one of {sorted(_ALLOWED_METRICS)}",
        )
    if session_index_a == session_index_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_index_a and session_index_b must differ",
        )

    pairs = _paired_measurements(
        db, study_id, battery_id, task_type, metric, session_index_a, session_index_b
    )
    if len(pairs) < 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fewer than 2 participants have completed sessions at both index {session_index_a} "
            f"and {session_index_b} for this battery/task — cannot compute ICC/SEM/MDC95.",
        )

    result = compute_longitudinal_metrics(pairs)
    release_state = current_release_state()
    note = None
    if result.n_subjects < 30:
        note = f"n={result.n_subjects} — ICC/SEM/MDC95 are unstable below ~30 paired observations; treat as provisional."

    return LongitudinalMetricsResponse(
        study_id=study_id,
        battery_id=battery_id,
        task_type=task_type,
        metric=metric,
        session_index_a=session_index_a,
        session_index_b=session_index_b,
        n_subjects=result.n_subjects,
        icc=result.icc,
        sem=result.sem,
        mdc95=result.mdc95,
        release_state=release_state,
        note=note,
    )


@router.get("/v1/participants/{participant_id}/change-report", response_model=ChangeReportResponse)
async def get_change_report(
    participant_id: str,
    study_id: str = Query(...),
    battery_id: str = Query(...),
    task_type: str = Query(...),
    metric: str = Query(...),
    session_index_a: int = Query(1, ge=1),
    session_index_b: int = Query(2, ge=1),
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> ChangeReportResponse:
    if metric not in _ALLOWED_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"metric must be one of {sorted(_ALLOWED_METRICS)}",
        )

    set_rls_context(db, current_user)
    participant = db.query(Participant).filter(Participant.participant_id == participant_id).first()
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")

    is_staff = has_any_role(current_user.roles, [Role.ADMIN, Role.RESEARCHER])
    if not is_staff:
        if participant.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this participant"
            )

        subscription = (
            db.query(Subscription)
            .filter(Subscription.user_id == current_user.user_id, Subscription.status == "active")
            .first()
        )
        if subscription is None:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Change reports require an active subscription.",
            )

    score_a = _score_at_index(
        db, participant_id, study_id, battery_id, session_index_a, task_type, metric
    )
    score_b = _score_at_index(
        db, participant_id, study_id, battery_id, session_index_b, task_type, metric
    )
    if score_a is None or score_b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Participant is missing a scored session at index {session_index_a} or {session_index_b}.",
        )

    delta = score_b - score_a
    pairs = _paired_measurements(
        db, study_id, battery_id, task_type, metric, session_index_a, session_index_b
    )

    if len(pairs) < 2:
        return ChangeReportResponse(
            participant_id=participant_id,
            task_type=task_type,
            metric=metric,
            session_index_a=session_index_a,
            session_index_b=session_index_b,
            score_a=score_a,
            score_b=score_b,
            delta=round(delta, 4),
            mdc95=None,
            reference_n_subjects=len(pairs),
            classification="insufficient_reference_data",
            release_state=current_release_state(),
        )

    result = compute_longitudinal_metrics(pairs)
    classification = classify_change(delta, result.mdc95)

    return ChangeReportResponse(
        participant_id=participant_id,
        task_type=task_type,
        metric=metric,
        session_index_a=session_index_a,
        session_index_b=session_index_b,
        score_a=score_a,
        score_b=score_b,
        delta=round(delta, 4),
        mdc95=result.mdc95,
        reference_n_subjects=result.n_subjects,
        classification=classification,
        release_state=current_release_state(),
    )
