"""n-of-1 Experiment Engine Routes (Phase 5)."""

from __future__ import annotations

import statistics
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import NOf1Experiment, NOf1Observation, Participant
from app.models.schemas import ErrorResponse, TokenPayload
from app.schemas.nof1 import (
    NOf1AnalysisResponse,
    NOf1ExperimentCreateRequest,
    NOf1ExperimentResponse,
    NOf1ObservationCreateRequest,
    NOf1ObservationResponse,
    NOf1PhaseSummary,
)
from app.services.authorization import Role, get_current_user, has_any_role, log_audit_event
from app.services.rls import set_rls_context
from app.services.stats import two_phase_contrast

router = APIRouter(
    prefix="/v1/n-of-1",
    tags=["n-of-1"],
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not Found"},
    },
)


def _get_experiment_or_404(db: Session, experiment_id: str) -> NOf1Experiment:
    experiment = (
        db.query(NOf1Experiment).filter(NOf1Experiment.experiment_id == experiment_id).first()
    )
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    return experiment


def _check_experiment_access(
    db: Session, experiment: NOf1Experiment, current_user: TokenPayload
) -> None:
    if has_any_role(current_user.roles, [Role.ADMIN, Role.RESEARCHER]):
        return
    participant = (
        db.query(Participant)
        .filter(Participant.participant_id == experiment.participant_id)
        .first()
    )
    if participant is None or participant.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this experiment"
        )


@router.post(
    "/experiments", response_model=NOf1ExperimentResponse, status_code=status.HTTP_201_CREATED
)
async def create_experiment(
    request: NOf1ExperimentCreateRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> NOf1Experiment:
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

    experiment = NOf1Experiment(
        participant_id=request.participant_id,
        study_id=request.study_id,
        name=request.name,
        phase_sequence=request.phase_sequence,
        outcome_metric_name=request.outcome_metric_name,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)

    log_audit_event(
        db=db,
        user_id=current_user.user_id,
        action="nof1_experiment:create",
        resource_type="nof1_experiment",
        resource_id=experiment.experiment_id,  # type: ignore[arg-type]
    )
    return experiment


@router.get("/experiments/{experiment_id}", response_model=NOf1ExperimentResponse)
async def get_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> NOf1Experiment:
    set_rls_context(db, current_user)
    experiment = _get_experiment_or_404(db, experiment_id)
    _check_experiment_access(db, experiment, current_user)
    return experiment


@router.post(
    "/experiments/{experiment_id}/observations",
    response_model=NOf1ObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_observation(
    experiment_id: str,
    request: NOf1ObservationCreateRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> NOf1Observation:
    set_rls_context(db, current_user)
    experiment = _get_experiment_or_404(db, experiment_id)
    _check_experiment_access(db, experiment, current_user)

    if request.phase_label not in experiment.phase_sequence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"phase_label must be one of the experiment's declared phases: {experiment.phase_sequence}",
        )

    next_index = (
        db.query(NOf1Observation).filter(NOf1Observation.experiment_id == experiment_id).count()
    )

    observation = NOf1Observation(
        experiment_id=experiment_id,
        sequence_index=next_index,
        phase_label=request.phase_label,
        value=request.value,
    )
    db.add(observation)
    db.commit()
    db.refresh(observation)
    return observation


@router.get("/experiments/{experiment_id}/analysis", response_model=NOf1AnalysisResponse)
async def get_analysis(
    experiment_id: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> NOf1AnalysisResponse:
    set_rls_context(db, current_user)
    experiment = _get_experiment_or_404(db, experiment_id)
    _check_experiment_access(db, experiment, current_user)

    observations: List[NOf1Observation] = (
        db.query(NOf1Observation)
        .filter(NOf1Observation.experiment_id == experiment_id)
        .order_by(NOf1Observation.sequence_index)
        .all()
    )

    if not observations:
        return NOf1AnalysisResponse(
            experiment_id=experiment_id,
            n_observations=0,
            phase_summaries=[],
            contrast=None,
            note="No observations recorded yet.",
        )

    by_phase: dict[str, list[float]] = {}
    for obs in observations:
        by_phase.setdefault(obs.phase_label, []).append(obs.value)  # type: ignore[arg-type]

    phase_summaries = [
        NOf1PhaseSummary(
            phase_label=label,
            n=len(values),
            mean=round(statistics.mean(values), 4),
            sd=round(statistics.stdev(values), 4) if len(values) > 1 else None,
        )
        for label, values in by_phase.items()
    ]

    contrast = None
    note = None
    distinct_labels = list(by_phase.keys())
    if len(distinct_labels) == 2:
        contrast = two_phase_contrast(by_phase[distinct_labels[0]], by_phase[distinct_labels[1]])
        contrast["reference_phase"] = distinct_labels[0]  # type: ignore[assignment]
        contrast["compared_phase"] = distinct_labels[1]  # type: ignore[assignment]
    elif len(distinct_labels) > 2:
        note = f"{len(distinct_labels)} distinct phase labels observed — pairwise contrast is only computed for exactly 2."
    else:
        note = "Only one phase has been observed so far — no contrast to compute yet."

    return NOf1AnalysisResponse(
        experiment_id=experiment_id,
        n_observations=len(observations),
        phase_summaries=phase_summaries,
        contrast=contrast,
        note=note,
    )
