"""
Pydantic Request and Response Models

Defines the data schemas for API requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionCreateRequest(BaseModel):
    """Request to create new simulation session."""

    config_path: Optional[str] = Field(None, description="Path to YAML configuration file")
    custom_config: Optional[Dict[str, Any]] = Field(
        None, description="Custom configuration overrides"
    )
    description: Optional[str] = Field(
        None, description="Human-readable description of the session"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "config_path": "config/default.yaml",
                "description": "Baseline simulation experiment",
            }
        }
    )


class LoginRequest(BaseModel):
    """Request for user authentication."""

    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="User password", min_length=1)
    remember_me: Optional[bool] = Field(False, description="Extend session duration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "user@example.com",
                "password": "secure_password",
                "remember_me": False,
            }
        }
    )


class TokenRefreshRequest(BaseModel):
    """Request to refresh access token."""

    refresh_token: str = Field(..., description="Valid refresh token")

    model_config = ConfigDict(
        json_schema_extra={"example": {"refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."}}
    )


class TokenResponse(BaseModel):
    """Response containing authentication tokens."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration time in seconds")
    refresh_expires_in: int = Field(..., description="Refresh token expiration time in seconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "refresh_expires_in": 86400,
            }
        }
    )


class SessionCreateResponse(BaseModel):
    """Response for session creation."""

    session_id: str = Field(..., description="Unique session identifier")
    status: str = Field(..., description="Session status")
    created_at: datetime = Field(..., description="Session creation timestamp")
    config: Dict[str, Any] = Field(..., description="Session configuration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "status": "created",
                "created_at": "2024-01-15T10:30:00Z",
                "config": {"description": "Test session"},
            }
        }
    )


class SessionResponse(BaseModel):
    """Response for session details."""

    session_id: str = Field(..., description="Unique session identifier")
    status: str = Field(..., description="Session status")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    config: Dict[str, Any] = Field(..., description="Session configuration")
    description: Optional[str] = Field(None, description="Session description")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "status": "running",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:35:00Z",
                "config": {"description": "Test session"},
                "description": "Test session",
            }
        }
    )


class SessionActionResponse(BaseModel):
    """Response for session action (start/pause/stop)."""

    session_id: str = Field(..., description="Unique session identifier")
    status: str = Field(..., description="New session status")
    timestamp: datetime = Field(..., description="Action timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "status": "running",
                "timestamp": "2024-01-15T10:35:00Z",
            }
        }
    )


class TaskSubmitRequest(BaseModel):
    """Request to submit async task."""

    task_type: str = Field(..., description="Type of task to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    webhook_url: Optional[str] = Field(
        None, description="Webhook URL for task completion notification"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_type": "attentional_blink",
                "parameters": {"duration": 100, "trials": 50},
                "webhook_url": "https://example.com/webhook",
            }
        }
    )


class TaskSubmitResponse(BaseModel):
    """Response for task submission."""

    task_id: str = Field(..., description="Unique task identifier")
    session_id: str = Field(..., description="Session identifier")
    task_type: str = Field(..., description="Type of task")
    status: str = Field(..., description="Task status")
    status_url: str = Field(..., description="URL to check task status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "task_xyz789",
                "session_id": "sess_abc123",
                "task_type": "attentional_blink",
                "status": "pending",
                "status_url": "/v1/tasks/task_xyz789",
            }
        }
    )


class TaskStatusResponse(BaseModel):
    """Response for task status."""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status (pending/running/completed/failed)")
    state: Optional[str] = Field(None, description="Celery task state")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    info: Optional[Dict[str, Any]] = Field(None, description="Additional task information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "task_xyz789",
                "status": "completed",
                "state": "SUCCESS",
                "result": {"accuracy": 0.85, "trials_completed": 50},
            }
        }
    )


class TaskListResponse(BaseModel):
    """Response for task list."""

    tasks: list[Dict[str, Any]] = Field(..., description="List of available tasks")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tasks": [
                    {
                        "name": "attentional_blink",
                        "description": "Attentional blink experiment",
                        "parameters": ["duration", "trials"],
                    }
                ]
            }
        }
    )


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    timestamp: datetime = Field(..., description="Error timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request payload",
                "timestamp": "2024-01-15T10:30:00Z",
                "details": {"field": "username", "error": "Field required"},
            }
        }
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail = Field(..., description="Error details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Session not found",
                    "timestamp": "2024-01-15T10:30:00Z",
                }
            }
        }
    )


# User Management Schemas
class UserCreateRequest(BaseModel):
    """Request to create new user."""

    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    roles: list[str] = Field(default_factory=list, description="User roles")


class UserCreateResponse(BaseModel):
    """Response for user creation."""

    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")


class UserResponse(BaseModel):
    """Response for user details."""

    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    roles: list[str] = Field(..., description="User roles")
    created_at: datetime = Field(..., description="Creation timestamp")


class UserUpdateRequest(BaseModel):
    """Request to update user."""

    email: Optional[str] = Field(None, description="Email address")
    password: Optional[str] = Field(None, description="New password")


class PasswordResetRequest(BaseModel):
    """Request to reset password."""

    email: str = Field(..., description="Email address")


class PasswordResetResponse(BaseModel):
    """Response for password reset."""

    message: str = Field(..., description="Reset message")


class UserStatsResponse(BaseModel):
    """Response for user statistics."""

    total_sessions: int = Field(..., description="Total sessions created")
    active_sessions: int = Field(..., description="Active sessions")


# State Schemas
class AllostaticState(BaseModel):
    """Allostatic state representation."""

    load: float = Field(..., description="Allostatic load")
    threshold: float = Field(..., description="Allostatic threshold")


class BodyState(BaseModel):
    """Body state representation."""

    energy: float = Field(..., description="Energy level")
    arousal: float = Field(..., description="Arousal level")


class IgnitionEvent(BaseModel):
    """Ignition event representation."""

    timestamp: datetime = Field(..., description="Event timestamp")
    type: str = Field(..., description="Event type")


class IgnitionHistoryResponse(BaseModel):
    """Response for ignition history."""

    events: list[IgnitionEvent] = Field(..., description="Ignition events")


class IgnitionState(BaseModel):
    """Ignition state representation."""

    active: bool = Field(..., description="Ignition active")
    intensity: float = Field(..., description="Ignition intensity")


class MetabolicState(BaseModel):
    """Metabolic state representation."""

    rate: float = Field(..., description="Metabolic rate")


class MinimalSelfState(BaseModel):
    """Minimal self state representation."""

    coherence: float = Field(..., description="Self coherence")


class NarrativeSelfState(BaseModel):
    """Narrative self state representation."""

    narrative: str = Field(..., description="Self narrative")


class PaginationInfo(BaseModel):
    """Pagination information."""

    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total items")


class PrecisionState(BaseModel):
    """Precision state representation."""

    value: float = Field(..., description="Precision value")


class SelfModelState(BaseModel):
    """Self model state representation."""

    confidence: float = Field(..., description="Model confidence")


class SystemStateResponse(BaseModel):
    """Response for system state."""

    allostatic: AllostaticState = Field(..., description="Allostatic state")
    body: BodyState = Field(..., description="Body state")
    ignition: IgnitionState = Field(..., description="Ignition state")


# Export Schemas
class SummaryStatistics(BaseModel):
    """Summary statistics for export."""

    mean: float = Field(..., description="Mean value")
    std: float = Field(..., description="Standard deviation")
    min: float = Field(..., description="Minimum value")
    max: float = Field(..., description="Maximum value")


class WorkspaceState(BaseModel):
    """Workspace state representation."""

    active: bool = Field(..., description="Workspace active")
    content: str = Field(..., description="Workspace content")


class PredictionErrorsResponse(BaseModel):
    """Response for prediction errors."""

    errors: list[float] = Field(..., description="Prediction errors")


class SomaticMarkersResponse(BaseModel):
    """Response for somatic markers."""

    markers: list[float] = Field(..., description="Somatic markers")
