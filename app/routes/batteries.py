"""Battery Routes (Phase 2). Creating batteries is staff-only (researcher/admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Battery, Study
from app.models.schemas import ErrorResponse, TokenPayload
from app.schemas.research import BatteryCreateRequest, BatteryResponse
from app.services.authorization import Role, log_audit_event, require_any_role

router = APIRouter(
    prefix="/v1/batteries",
    tags=["Batteries"],
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not Found"},
    },
)


@router.post("", response_model=BatteryResponse, status_code=status.HTTP_201_CREATED)
async def create_battery(
    request: BatteryCreateRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(require_any_role([Role.ADMIN, Role.RESEARCHER])),
) -> Battery:
    study = db.query(Study).filter(Study.study_id == request.study_id).first()
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    battery = Battery(
        study_id=request.study_id,
        name=request.name,
        version=request.version,
        form_label=request.form_label,
        instrument_schema=request.instrument_schema,
    )
    db.add(battery)
    db.commit()
    db.refresh(battery)

    log_audit_event(
        db=db,
        user_id=current_user.user_id,
        action="battery:create",
        resource_type="battery",
        resource_id=battery.battery_id,  # type: ignore[arg-type]
    )
    return battery


@router.get("/{battery_id}", response_model=BatteryResponse)
async def get_battery(battery_id: str, db: Session = Depends(get_db)) -> Battery:
    battery = db.query(Battery).filter(Battery.battery_id == battery_id).first()
    if battery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Battery not found")
    return battery
