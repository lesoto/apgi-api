"""Pydantic schemas for the n-of-1 experiment engine (Phase 5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.database.models import NOf1ExperimentStatus

_FORBID_EXTRA = ConfigDict(extra="forbid")


class NOf1ExperimentCreateRequest(BaseModel):
    model_config = _FORBID_EXTRA

    participant_id: str
    study_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    phase_sequence: list[str] = Field(..., min_length=2, description='e.g. ["A", "B", "A", "B"]')
    outcome_metric_name: str = Field(..., min_length=1, max_length=100)


class NOf1ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    experiment_id: str
    participant_id: str
    study_id: Optional[str] = None
    name: str
    phase_sequence: list[str]
    outcome_metric_name: str
    status: NOf1ExperimentStatus
    created_at: datetime


class NOf1ObservationCreateRequest(BaseModel):
    model_config = _FORBID_EXTRA

    phase_label: str = Field(..., min_length=1, max_length=20)
    value: float


class NOf1ObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observation_id: str
    sequence_index: int
    phase_label: str
    value: float
    recorded_at: datetime


class NOf1PhaseSummary(BaseModel):
    phase_label: str
    n: int
    mean: float
    sd: Optional[float] = None


class NOf1AnalysisResponse(BaseModel):
    experiment_id: str
    n_observations: int
    phase_summaries: list[NOf1PhaseSummary]
    contrast: Optional[dict[str, Any]] = Field(
        None,
        description="Two-phase comparison (present only when exactly two distinct phase labels "
        "have been observed): mean difference, Cohen's d, and a permutation-test p-value.",
    )
    note: Optional[str] = None
