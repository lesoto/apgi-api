"""GET /v1/instrument/psychometrics — internal-consistency reliability (Phase 3-4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Battery, ParticipantSession, ParticipantSessionStatus, TrialEvent
from app.models.schemas import ErrorResponse, TokenPayload
from app.schemas.reporting import PsychometricsResponse
from app.services.authorization import get_current_user
from app.services.identifiers import current_release_state
from app.services.stats import cronbachs_alpha

router = APIRouter(
    prefix="/v1/instrument",
    tags=["Instrument"],
    responses={404: {"model": ErrorResponse, "description": "Not Found"}},
)


@router.get("/psychometrics", response_model=PsychometricsResponse)
async def get_psychometrics(
    battery_id: str = Query(...),
    task_type: str = Query(...),
    db: Session = Depends(get_db),
    _current_user: TokenPayload = Depends(get_current_user),
) -> PsychometricsResponse:
    battery = db.query(Battery).filter(Battery.battery_id == battery_id).first()
    if battery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Battery not found")

    sessions = (
        db.query(ParticipantSession)
        .filter(
            ParticipantSession.battery_id == battery_id,
            ParticipantSession.status == ParticipantSessionStatus.COMPLETED,
        )
        .all()
    )

    # Cronbach's alpha needs a rectangular item matrix (same items for every
    # respondent) — use the largest common trial_index set across sessions
    # rather than padding, since a padded 0/1 "item" would bias the estimate.
    per_session_items: list[dict[int, float]] = []
    for session in sessions:
        trials = (
            db.query(TrialEvent)
            .filter(
                TrialEvent.participant_session_id == session.participant_session_id,
                TrialEvent.task_type == task_type,
                TrialEvent.correct.isnot(None),
            )
            .all()
        )
        if trials:
            per_session_items.append(
                {t.trial_index: (1.0 if t.correct else 0.0) for t in trials}  # type: ignore[misc]
            )

    if not per_session_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No graded trials found for battery {battery_id}, task {task_type}",
        )

    common_indices = sorted(set.intersection(*(set(d.keys()) for d in per_session_items)))
    n_sessions = len(per_session_items)
    n_items = len(common_indices)

    if n_items >= 2 and n_sessions >= 2:
        item_matrix = [[d[i] for i in common_indices] for d in per_session_items]
        alpha = cronbachs_alpha(item_matrix)
        totals = [sum(row) for row in item_matrix]
        mean_total = sum(totals) / len(totals)
        sd_total = (
            (sum((x - mean_total) ** 2 for x in totals) / (len(totals) - 1)) ** 0.5
            if len(totals) > 1
            else 0.0
        )
    else:
        alpha, mean_total, sd_total = 0.0, None, None

    release_state = current_release_state()
    note = None
    if n_sessions < 30:
        note = f"n={n_sessions} sessions — reliability estimate is unstable below ~30; treat as provisional."

    return PsychometricsResponse(
        battery_id=battery_id,
        task_type=task_type,
        n_sessions=n_sessions,
        n_items=n_items,
        cronbachs_alpha=alpha,
        mean_total_correct=mean_total,
        sd_total_correct=sd_total,
        release_state=release_state,
        note=note,
    )
