"""
State Access Routes

API endpoints for accessing APGI system state, ignition history, and subsystem data.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.models.schemas import (
    AllostaticState,
    BodyState,
    ErrorResponse,
    IgnitionEvent,
    IgnitionHistoryResponse,
    IgnitionState,
    MetabolicState,
    MinimalSelfState,
    NarrativeSelfState,
    PrecisionState,
    PredictionErrorsResponse,
    SelfModelState,
    SomaticMarkersResponse,
    SystemStateResponse,
    WorkspaceState,
)
from app.routes.sessions import get_session_manager, validate_session_ownership
from app.services.auth_manager import TokenPayload
from app.services.authorization import Permission, get_current_user, require_permission
from app.services.k7_gate import K7Parameter, is_cleared
from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)


# Create router
router = APIRouter(
    prefix="/v1/sessions",
    tags=["State Access"],
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


@router.get(
    "/{session_id}/state",
    response_model=SystemStateResponse,
    response_model_exclude_none=True,
    summary="Get complete system state",
    description="Retrieve the complete current state of all APGI subsystems for the specified session",
    dependencies=[Depends(require_permission(Permission.SESSION_READ))],
)
async def get_system_state(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemStateResponse:
    """
    Get complete system state.

    Returns comprehensive state information including:
    - Ignition status and dynamics
    - Global workspace state
    - Interoceptive body state
    - Allostatic regulation
    - Precision weighting
    - Metabolic reserves
    - Self-model state

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        SystemStateResponse with complete state

    Raises:
        HTTPException: If session not found or state cannot be retrieved
    """
    # Validate session ownership
    await validate_session_ownership(session_id, current_user.user_id, manager, db)

    try:
        # Get session with ownership validation
        sim_session = await manager.get_session(session_id, current_user.user_id)

        # Get complete state
        state = await sim_session.get_state()

        # Extract and format state components
        ignition_data = state.get("ignition", {})
        workspace_data = state.get("workspace", {})
        body_data = state.get("body", {})
        allostasis_data = state.get("allostasis", {})
        precision_data = state.get("precision", {})
        metabolism_data = state.get("metabolism", {})
        self_model_data = state.get("self_model", {})

        # Build response
        response = SystemStateResponse(
            time_ms=state.get("time", 0.0),
            ignition=IgnitionState(
                ignition_occurred=ignition_data.get("ignition_occurred", False),
                total_signal=ignition_data.get("total_signal", 0.0),
                threshold=(
                    ignition_data.get("threshold", 0.0)
                    if is_cleared(K7Parameter.IGNITION_THRESHOLD)
                    else None
                ),
                duration_ms=ignition_data.get("duration_ms"),
            ),
            workspace=WorkspaceState(
                is_broadcasting=workspace_data.get("is_broadcasting", False),
                content=workspace_data.get("content"),
                broadcast_duration_ms=workspace_data.get("broadcast_duration_ms"),
            ),
            body=BodyState(
                heart_rate=(
                    body_data.get("heart_rate", 70.0)
                    if is_cleared(K7Parameter.INTEROCEPTIVE_BODY_STATE)
                    else None
                ),
                cortisol=(
                    body_data.get("cortisol", 0.1)
                    if is_cleared(K7Parameter.INTEROCEPTIVE_BODY_STATE)
                    else None
                ),
                temperature=(
                    body_data.get("temperature", 37.0)
                    if is_cleared(K7Parameter.INTEROCEPTIVE_BODY_STATE)
                    else None
                ),
            ),
            allostasis=AllostaticState(allostatic_load=allostasis_data.get("allostatic_load", 0.0)),
            precision=PrecisionState(
                exteroceptive=(
                    precision_data.get("exteroceptive", 1.0)
                    if is_cleared(K7Parameter.PRECISION_EXTEROCEPTIVE)
                    else None
                ),
                interoceptive=(
                    precision_data.get("interoceptive", 1.0)
                    if is_cleared(K7Parameter.PRECISION_INTEROCEPTIVE)
                    else None
                ),
            ),
            metabolism=MetabolicState(
                reserves=metabolism_data.get("reserves", 1000.0),
                reserve_fraction=metabolism_data.get("reserve_fraction", 1.0),
            ),
            self_model=SelfModelState(
                minimal=MinimalSelfState(
                    coherence=self_model_data.get("minimal", {}).get("coherence", 0.5)
                ),
                narrative=NarrativeSelfState(
                    narrative=self_model_data.get("narrative", {}).get("narrative", "")
                ),
            ),
        )

        logger.info(f"Retrieved state for session {session_id}")
        return response

    except ValueError as e:
        logger.warning(f"Session {session_id} not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found"
        )
    except Exception as e:
        logger.exception("Failed to get system state")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.get(
    "/{session_id}/ignition-history",
    response_model=IgnitionHistoryResponse,
    summary="Get ignition event history",
    description="Retrieve historical ignition events with optional filtering and pagination",
    dependencies=[Depends(require_permission(Permission.SESSION_READ))],
)
async def get_ignition_history(  # noqa: C901
    session_id: str,
    start_time: Optional[float] = Query(None, description="Filter events after this time (ms)"),
    end_time: Optional[float] = Query(None, description="Filter events before this time (ms)"),
    limit: Optional[int] = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of events to return (warning: values > 500 may be slow)",
    ),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    manager: SessionManager = Depends(get_session_manager),
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IgnitionHistoryResponse:
    """
    Get ignition event history.

    Returns a list of ignition events that occurred during the simulation,
    with optional time-based filtering and pagination support.

    Args:
        session_id: Unique session identifier
        start_time: Optional start time filter (milliseconds)
        end_time: Optional end time filter (milliseconds)
        limit: Maximum number of events to return (1-1000)
        cursor: Pagination cursor for fetching next page
        manager: Session manager dependency

    Returns:
        IgnitionHistoryResponse with events and pagination info

    Raises:
        HTTPException: If session not found or history cannot be retrieved
    """
    # Validate session ownership
    await validate_session_ownership(session_id, current_user.user_id, manager, db)

    try:
        # Warn about potentially expensive queries
        if limit and limit > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Limit {limit} is too large. Maximum allowed limit is 500. Consider using smaller limits or time filters.",
            )

        # Get session
        sim_session = await manager.get_session(session_id, current_user.user_id)

        # Get complete state to access history
        state = await sim_session.get_state()
        history = state.get("history", {})

        # Extract ignition events from history
        times = history.get("time", [])
        ignitions = history.get("ignitions", [])

        # Build event list
        events = []
        for i, (time_val, ignition_val) in enumerate(zip(times, ignitions)):
            if ignition_val:  # Only include actual ignition events
                # Apply time filters
                if start_time is not None and time_val < start_time:
                    continue
                if end_time is not None and time_val > end_time:
                    continue

                # Get ignition data - use historical if available, otherwise current
                ignition_signals = history.get("ignition_signals", [])
                ignition_thresholds = history.get("ignition_thresholds", [])
                if i < len(ignition_signals) and i < len(ignition_thresholds):
                    total_signal = ignition_signals[i]
                    threshold = ignition_thresholds[i]
                else:
                    # Fallback to current values if historical not available
                    ignition_data = state.get("ignition", {})
                    total_signal = ignition_data.get("total_signal", 0.0)
                    threshold = ignition_data.get("threshold", 2.0)

                # Estimate duration based on signal decay (simplified calculation)
                duration_ms = min(500.0, max(100.0, total_signal * 100))

                # Use historical or current signal and threshold values
                events.append(
                    IgnitionEvent(
                        time_ms=time_val,
                        duration_ms=duration_ms,
                        trigger_signal=total_signal,
                        threshold=threshold,
                    )
                )

        # Apply pagination
        limit_val = limit or 100  # Default to 100 if None
        limit_val = min(limit_val, 500)  # Hard cap to prevent expensive queries
        start_idx = 0
        if cursor:
            try:
                import base64
                import hashlib
                import hmac
                import json

                signed_cursor = base64.b64decode(cursor).decode()
                json_str, signature = signed_cursor.rsplit(".", 1)
                expected_signature = hmac.new(
                    settings.cursor_signing_key.encode(), json_str.encode(), hashlib.sha256  # type: ignore[union-attr]
                ).hexdigest()

                if not hmac.compare_digest(signature, expected_signature):
                    raise ValueError("Invalid cursor signature")

                cursor_data = json.loads(json_str)
                start_idx = cursor_data.get("offset", 0)
            except Exception as e:
                logger.warning(f"Invalid cursor: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid cursor provided",
                )

        end_idx = start_idx + limit_val
        paginated_events = events[start_idx:end_idx]
        has_more = end_idx < len(events)

        # Generate next cursor
        next_cursor = None
        if has_more:
            import base64
            import hashlib
            import hmac
            import json

            cursor_data = {"offset": end_idx}
            json_str = json.dumps(cursor_data)
            signature = hmac.new(
                settings.cursor_signing_key.encode(), json_str.encode(), hashlib.sha256  # type: ignore[union-attr]
            ).hexdigest()
            signed_cursor = json_str + "." + signature
            next_cursor = base64.b64encode(signed_cursor.encode()).decode()

        response = IgnitionHistoryResponse(
            events=paginated_events,
            pagination=None,
        )

        logger.info(f"Retrieved {len(paginated_events)} ignition events for session {session_id}")
        return response

    except ValueError as e:  # pragma: no cover
        logger.warning(f"Session {session_id} not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found"
        )
    except HTTPException:
        # Re-raise HTTPException without modification
        raise
    except Exception as e:
        logger.exception("Failed to get ignition history")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.get(
    "/{session_id}/interoception",
    response_model=BodyState,
    response_model_exclude_none=True,
    summary="Get interoceptive body state",
    description="Retrieve current interoceptive state including physiological parameters",
    dependencies=[Depends(require_permission(Permission.SESSION_READ))],
)
async def get_interoceptive_state(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BodyState:
    """
    Get interoceptive body state.

    Returns current physiological state including:
    - Heart rate
    - Cortisol levels
    - Body temperature

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        BodyState with current interoceptive parameters

    Raises:
        HTTPException: If session not found or state cannot be retrieved
    """
    # Validate session ownership
    await validate_session_ownership(session_id, current_user.user_id, manager, db)

    try:
        # Get session
        sim_session = await manager.get_session(session_id, current_user.user_id)

        # Get complete state
        state = await sim_session.get_state()
        body_data = state.get("body", {})

        cleared = is_cleared(K7Parameter.INTEROCEPTIVE_BODY_STATE)
        response = BodyState(
            heart_rate=body_data.get("heart_rate", 70.0) if cleared else None,
            cortisol=body_data.get("cortisol", 0.1) if cleared else None,
            temperature=body_data.get("temperature", 37.0) if cleared else None,
        )

        logger.info(f"Retrieved interoceptive state for session {session_id}")
        return response

    except ValueError as e:
        logger.warning(f"Session {session_id} not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found"
        )
    except Exception as e:
        logger.exception("Failed to get interoceptive state")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.get(
    "/{session_id}/prediction-errors",
    response_model=PredictionErrorsResponse,
    response_model_exclude_none=True,
    summary="Get prediction errors",
    description="Retrieve hierarchical prediction errors from all levels of the predictive processing hierarchy",
    dependencies=[Depends(require_permission(Permission.SESSION_READ))],
)
async def get_prediction_errors(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionErrorsResponse:
    """
    Get prediction errors.

    Returns hierarchical prediction errors showing the discrepancy between
    predictions and actual observations at each level of the processing hierarchy.

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        Dict with prediction error information

    Raises:
        HTTPException: If session not found or errors cannot be retrieved
    """
    # Validate session ownership
    await validate_session_ownership(session_id, current_user.user_id, manager, db)

    try:
        # Get session
        sim_session = await manager.get_session(session_id, current_user.user_id)

        # Get complete state
        state = await sim_session.get_state()
        prediction_data = state.get("prediction", {})

        # Extract prediction errors
        extero_cleared = is_cleared(K7Parameter.PREDICTION_ERROR_EXTEROCEPTIVE)
        intero_cleared = is_cleared(K7Parameter.PREDICTION_ERROR_INTEROCEPTIVE)
        response = PredictionErrorsResponse(
            session_id=session_id,
            time_ms=state.get("time", 0.0),
            prediction_errors=(
                prediction_data.get("errors", {}) if (extero_cleared and intero_cleared) else None
            ),
            exteroceptive_stats=(
                prediction_data.get("exteroceptive_stats", {}) if extero_cleared else None
            ),
            interoceptive_stats=(
                prediction_data.get("interoceptive_stats", {}) if intero_cleared else None
            ),
        )

        logger.info(f"Retrieved prediction errors for session {session_id}")
        return response

    except ValueError as e:
        logger.warning(f"Session {session_id} not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found"
        )
    except Exception as e:
        logger.exception("Failed to get prediction errors")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )


@router.get(
    "/{session_id}/somatic-markers",
    response_model=SomaticMarkersResponse,
    response_model_exclude_none=True,
    summary="Get somatic markers",
    description="Retrieve stored somatic markers (context-action-outcome associations)",
    dependencies=[Depends(require_permission(Permission.SESSION_READ))],
)
async def get_somatic_markers(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    current_user: TokenPayload = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SomaticMarkersResponse:
    """
    Get somatic markers.

    Returns stored context-action-outcome associations with gain values,
    representing learned emotional/bodily responses to situations.

    Args:
        session_id: Unique session identifier
        manager: Session manager dependency

    Returns:
        Dict with somatic marker information

    Raises:
        HTTPException: If session not found or markers cannot be retrieved
    """
    # Validate session ownership
    await validate_session_ownership(session_id, current_user.user_id, manager, db)

    try:
        # Get session
        sim_session = await manager.get_session(session_id, current_user.user_id)

        # Get complete state
        state = await sim_session.get_state()

        # Extract somatic marker data from interoception subsystem
        interoception_data = state.get("interoception", {})
        somatic_data = interoception_data.get("somatic_markers", {})

        cleared = is_cleared(K7Parameter.SOMATIC_BIAS)
        response = SomaticMarkersResponse(
            session_id=session_id,
            time_ms=state.get("time", 0.0),
            num_markers=somatic_data.get("num_markers", 0) if cleared else None,
            total_retrievals=somatic_data.get("total_retrievals", 0) if cleared else None,
            successful_retrievals=(
                somatic_data.get("successful_retrievals", 0) if cleared else None
            ),
            retrieval_rate=somatic_data.get("retrieval_rate", 0.0) if cleared else None,
            markers=somatic_data.get("markers", []) if cleared else None,
        )

        logger.info(f"Retrieved somatic markers for session {session_id}")
        return response

    except ValueError as e:
        logger.warning(f"Session {session_id} not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {session_id} not found"
        )
    except Exception as e:
        logger.exception("Failed to get somatic markers")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred",
        )
