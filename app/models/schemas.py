"""
Pydantic Request and Response Models

Defines the data schemas for API requests and responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SessionTemplateCreateRequest(BaseModel):
    """Request to create a new session template."""

    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    config_path: Optional[str] = Field(None, description="Path to YAML configuration file")
    custom_config: Optional[Dict[str, Any]] = Field(
        None, description="Default custom configuration overrides"
    )
    default_description: Optional[str] = Field(None, description="Default session description")
    tags: Optional[List[str]] = Field(default=[], description="Template tags")
    is_public: Optional[bool] = Field(False, description="Whether template is public")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate template name."""
        if not v or not v.strip():
            raise ValueError("Template name cannot be empty")

        if len(v) > 100:
            raise ValueError("Template name is too long (max 100 characters)")

        return v.strip()

    @field_validator("config_path")
    @classmethod
    def validate_config_path(cls, v):
        """Validate configuration file path."""
        if v is None:
            return v

        if not isinstance(v, str) or not v.strip():
            raise ValueError("Configuration path must be a non-empty string")

        # Basic path validation - prevent directory traversal
        if ".." in v or v.startswith("/"):
            raise ValueError("Invalid configuration path: directory traversal not allowed")

        # Check for valid file extension
        if not v.endswith((".yaml", ".yml")):
            raise ValueError("Configuration file must have .yaml or .yml extension")

        # Reasonable path length limit
        if len(v) > 255:
            raise ValueError("Configuration path is too long (max 255 characters)")

        return v.strip()

    @field_validator("custom_config")
    @classmethod
    def validate_custom_config(cls, v):
        """Validate custom configuration."""
        if v is None:
            return v

        if not isinstance(v, dict):
            raise ValueError("Custom configuration must be a dictionary")

        # Validate configuration keys and values
        for key, value in v.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"Configuration key must be a non-empty string, got: {key}")

            # Prevent certain dangerous configuration keys
            dangerous_keys = {"database_url", "secret_key", "password", "token"}
            if key.lower() in dangerous_keys:
                raise ValueError(f'Configuration key "{key}" is not allowed in custom config')

        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate template tags."""
        if v is None:
            return []

        if not isinstance(v, list):
            raise ValueError("Tags must be a list")

        for tag in v:
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError("Each tag must be a non-empty string")

            if len(tag) > 50:
                raise ValueError("Tag is too long (max 50 characters)")

        return [tag.strip() for tag in v]

    @model_validator(mode="after")
    def validate_config_consistency(self):
        """Validate consistency between config_path and custom_config."""
        if self.config_path and self.custom_config:
            # Having both is allowed but warn about potential conflicts
            pass
        elif not self.config_path and not self.custom_config:
            raise ValueError("Either config_path or custom_config must be provided")

        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Default Experiment",
                "description": "Standard configuration for attentional blink experiments",
                "config_path": "config/default.yaml",
                "default_description": "Attentional blink task",
                "tags": ["attentional_blink", "experiment"],
                "is_public": False,
            }
        }
    )


class SessionTemplateUpdateRequest(BaseModel):
    """Request to update a session template."""

    name: Optional[str] = Field(None, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    config_path: Optional[str] = Field(None, description="Path to YAML configuration file")
    custom_config: Optional[Dict[str, Any]] = Field(
        None, description="Default custom configuration overrides"
    )
    default_description: Optional[str] = Field(None, description="Default session description")
    tags: Optional[List[str]] = Field(None, description="Template tags")
    is_public: Optional[bool] = Field(None, description="Whether template is public")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate template name."""
        if v is None:
            return v

        if not v.strip():
            raise ValueError("Template name cannot be empty")

        if len(v) > 100:
            raise ValueError("Template name is too long (max 100 characters)")

        return v.strip()

    @field_validator("config_path")
    @classmethod
    def validate_config_path(cls, v):
        """Validate configuration file path."""
        if v is None:
            return v

        if not isinstance(v, str) or not v.strip():
            raise ValueError("Configuration path must be a non-empty string")

        # Basic path validation - prevent directory traversal
        if ".." in v or v.startswith("/"):
            raise ValueError("Invalid configuration path: directory traversal not allowed")

        # Check for valid file extension
        if not v.endswith((".yaml", ".yml")):
            raise ValueError("Configuration file must have .yaml or .yml extension")

        # Reasonable path length limit
        if len(v) > 255:
            raise ValueError("Configuration path is too long (max 255 characters)")

        return v.strip()

    @field_validator("custom_config")
    @classmethod
    def validate_custom_config(cls, v):
        """Validate custom configuration."""
        if v is None:
            return v

        if not isinstance(v, dict):
            raise ValueError("Custom configuration must be a dictionary")

        # Validate configuration keys and values
        for key, value in v.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"Configuration key must be a non-empty string, got: {key}")

            # Prevent certain dangerous configuration keys
            dangerous_keys = {"database_url", "secret_key", "password", "token"}
            if key.lower() in dangerous_keys:
                raise ValueError(f'Configuration key "{key}" is not allowed in custom config')

        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate template tags."""
        if v is None:
            return v

        if not isinstance(v, list):
            raise ValueError("Tags must be a list")

        for tag in v:
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError("Each tag must be a non-empty string")

            if len(tag) > 50:
                raise ValueError("Tag is too long (max 50 characters)")

        return [tag.strip() for tag in v]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Experiment",
                "description": "Updated configuration for attentional blink experiments",
                "tags": ["attentional_blink", "experiment", "updated"],
                "is_public": True,
            }
        }
    )


class SessionTemplateResponse(BaseModel):
    """Response for session template details."""

    template_id: str = Field(..., description="Unique template identifier")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    config_path: Optional[str] = Field(None, description="Path to YAML configuration file")
    custom_config: Optional[Dict[str, Any]] = Field(
        None, description="Default custom configuration overrides"
    )
    default_description: Optional[str] = Field(None, description="Default session description")
    tags: List[str] = Field(default_factory=list, description="Template tags")
    is_public: bool = Field(..., description="Whether template is public")
    created_at: datetime = Field(..., description="Template creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_id": "tmpl_abc123",
                "user_id": "user_123",
                "name": "Default Experiment",
                "description": "Standard configuration for attentional blink experiments",
                "config_path": "config/default.yaml",
                "custom_config": {"experiment_type": "attentional_blink"},
                "default_description": "Attentional blink task",
                "tags": ["attentional_blink", "experiment"],
                "is_public": False,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
            }
        }
    )


class SessionTemplateListResponse(BaseModel):
    """Response for session templates list."""

    templates: list[SessionTemplateResponse] = Field(..., description="List of templates")
    pagination: PaginationInfo = Field(..., description="Pagination information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "templates": [
                    {
                        "template_id": "tmpl_abc123",
                        "user_id": "user_123",
                        "name": "Default Experiment",
                        "description": "Standard configuration for attentional blink experiments",
                        "config_path": "config/default.yaml",
                        "custom_config": {"experiment_type": "attentional_blink"},
                        "default_description": "Attentional blink task",
                        "tags": ["attentional_blink", "experiment"],
                        "is_public": False,
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:00Z",
                    }
                ],
                "pagination": {
                    "page": 1,
                    "per_page": 10,
                    "total": 1,
                },
            }
        }
    )


class SessionCreateRequest(BaseModel):
    """Request to create new simulation session."""

    template_id: Optional[str] = Field(None, description="Template ID to use for session creation")
    config_path: Optional[str] = Field(None, description="Path to YAML configuration file")
    custom_config: Optional[Dict[str, Any]] = Field(
        None, description="Custom configuration overrides"
    )
    description: Optional[str] = Field(
        None, description="Human-readable description of the session"
    )

    @field_validator("template_id")
    @classmethod
    def validate_template_id(cls, v):
        """Validate template ID format."""
        if v is None:
            return v

        if not isinstance(v, str) or not v.strip():
            raise ValueError("Template ID must be a non-empty string")

        # UUID validation pattern
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError(f"Invalid template ID format: {v}")

        return v.strip()

    @field_validator("config_path")
    @classmethod
    def validate_config_path(cls, v):
        """Validate configuration file path."""
        if v is None:
            return v

        if not isinstance(v, str) or not v.strip():
            raise ValueError("Configuration path must be a non-empty string")

        # Basic path validation - prevent directory traversal
        if ".." in v or v.startswith("/"):
            raise ValueError("Invalid configuration path: directory traversal not allowed")

        # Check for valid file extension
        if not v.endswith((".yaml", ".yml")):
            raise ValueError("Configuration file must have .yaml or .yml extension")

        # Reasonable path length limit
        if len(v) > 255:
            raise ValueError("Configuration path is too long (max 255 characters)")

        return v.strip()

    @field_validator("custom_config")
    @classmethod
    def validate_custom_config(cls, v):
        """Validate custom configuration."""
        if v is None:
            return v

        if not isinstance(v, dict):
            raise ValueError("Custom configuration must be a dictionary")

        # Validate configuration keys and values
        for key, value in v.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"Configuration key must be a non-empty string, got: {key}")

            # Prevent certain dangerous configuration keys
            dangerous_keys = {"database_url", "secret_key", "password", "token"}
            if key.lower() in dangerous_keys:
                raise ValueError(f'Configuration key "{key}" is not allowed in custom config')

        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        """Validate session description."""
        if v is None:
            return v

        if not isinstance(v, str):
            raise ValueError("Description must be a string")

        # Reasonable length limit
        if len(v) > 500:
            raise ValueError("Description is too long (max 500 characters)")

        return v.strip()

    @model_validator(mode="after")
    def validate_config_consistency(self):
        """Validate consistency between template_id, config_path and custom_config."""
        if self.template_id:
            # If using template, config_path and custom_config are optional overrides
            pass
        elif self.config_path and self.custom_config:
            # Having both is allowed but warn about potential conflicts
            pass
        elif not self.config_path and not self.custom_config:
            raise ValueError("Either template_id, config_path, or custom_config must be provided")

        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_id": "tmpl_abc123",
                "description": "Baseline simulation experiment",
            }
        }
    )


class LoginRequest(BaseModel):
    """Request for user authentication."""

    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="User password", min_length=1)
    remember_me: Optional[bool] = Field(False, description="Extend session duration")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        """Validate username format."""
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")

        # Check for valid email format if it looks like an email
        if "@" in v:
            email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_regex, v):
                raise ValueError("Invalid email format")

        # Check username format (alphanumeric, underscore, dash, min 3 chars)
        elif not re.match(r"^[a-zA-Z0-9_-]{3,50}$", v):
            raise ValueError(
                "Username must be 3-50 characters, alphanumeric with underscores or dashes"
            )

        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        """Validate password strength."""
        if not v or len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")

        # Check for at least one uppercase, one lowercase, one digit
        if not (re.search(r"[A-Z]", v) and re.search(r"[a-z]", v) and re.search(r"\d", v)):
            raise ValueError(
                "Password must contain at least one uppercase letter, one lowercase letter, and one digit"
            )

        return v

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
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration time in seconds")
    refresh_expires_in: Optional[int] = Field(
        None, description="Refresh token expiration time in seconds"
    )

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


class TokenRefreshResponse(BaseModel):
    """Response for token refresh without refresh token fields."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration time in seconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
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


class SessionListResponse(BaseModel):
    """Response for sessions list."""

    sessions: list[SessionResponse] = Field(..., description="List of sessions")
    pagination: PaginationInfo = Field(..., description="Pagination information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sessions": [
                    {
                        "session_id": "sess_abc123",
                        "status": "running",
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:35:00Z",
                        "config": {"description": "Test session"},
                        "description": "Test session",
                    }
                ],
                "pagination": {
                    "page": 1,
                    "per_page": 10,
                    "total": 1,
                },
            }
        }
    )


class SessionMetricsResponse(BaseModel):
    """Response for session metrics."""

    session_id: str = Field(..., description="Unique session identifier")
    ignition_frequency: float = Field(..., description="Frequency of ignition events")
    free_energy: float = Field(..., description="Current free energy level")
    metabolic_load: float = Field(..., description="Current metabolic load")
    additional_metrics: Optional[Dict[str, Any]] = Field(
        None, description="Additional computed metrics"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "ignition_frequency": 0.15,
                "free_energy": -2.5,
                "metabolic_load": 1.8,
                "additional_metrics": {"precision": 0.85, "coherence": 0.92},
            }
        }
    )


class SessionActionResponse(BaseModel):
    """Response for session action operations."""

    session_id: str = Field(..., description="Unique session identifier")
    status: str = Field(..., description="Updated session status")
    timestamp: datetime = Field(..., description="Action timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123",
                "status": "stopped",
                "timestamp": "2024-01-15T10:35:00Z",
            }
        }
    )


class TaskDependencyCreateRequest(BaseModel):
    """Request to create a task dependency."""

    prerequisite_task_id: str = Field(
        ..., description="Task ID that must complete before the dependent task"
    )
    dependency_type: Optional[str] = Field("completion", description="Type of dependency")

    @field_validator("prerequisite_task_id")
    @classmethod
    def validate_prerequisite_task_id(cls, v):
        """Validate prerequisite task ID format."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Prerequisite task ID must be a non-empty string")

        # UUID validation pattern
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
        )
        if not uuid_pattern.match(v):
            raise ValueError(f"Invalid prerequisite task ID format: {v}")

        return v.strip()

    @field_validator("dependency_type")
    @classmethod
    def validate_dependency_type(cls, v):
        """Validate dependency type."""
        if v is None:
            return "completion"

        valid_types = ["completion", "success", "failure"]
        if v not in valid_types:
            raise ValueError(f"Dependency type must be one of: {', '.join(valid_types)}")

        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prerequisite_task_id": "task_prereq_123",
                "dependency_type": "completion",
            }
        }
    )


class TaskDependencyResponse(BaseModel):
    """Response for task dependency details."""

    id: int = Field(..., description="Dependency ID")
    dependent_task_id: str = Field(..., description="Task that depends on the prerequisite")
    prerequisite_task_id: str = Field(
        ..., description="Task that must complete before the dependent task"
    )
    dependency_type: str = Field(..., description="Type of dependency")
    created_at: datetime = Field(..., description="Dependency creation timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "dependent_task_id": "task_dep_123",
                "prerequisite_task_id": "task_prereq_123",
                "dependency_type": "completion",
                "created_at": "2024-01-15T10:30:00Z",
            }
        }
    )


class TaskSubmitRequest(BaseModel):
    """Request to submit async task."""

    task_type: str = Field(..., description="Type of task to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    priority: Optional[int] = Field(5, description="Task priority (1=highest, 10=lowest)")
    webhook_url: Optional[str] = Field(
        None, description="Webhook URL for task completion notification"
    )

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, v):
        """Validate task type."""
        if not v or not v.strip():
            raise ValueError("Task type cannot be empty")

        return v.strip()

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v):
        """Validate task parameters."""
        if not isinstance(v, dict):
            raise ValueError("Parameters must be a dictionary")

        # Basic validation - ensure parameter names are reasonable
        for key, value in v.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"Parameter key must be a non-empty string, got: {key}")

            # Basic type checking for common parameter types
            if isinstance(value, (int, float)):
                if value < 0:
                    raise ValueError(f"Numeric parameter {key} cannot be negative")
            elif isinstance(value, str):
                if len(value) > 1000:  # Reasonable limit
                    raise ValueError(f"String parameter {key} is too long (max 1000 characters)")

        return v

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v):
        """Validate webhook URL format."""
        if v is None:
            return v

        if not isinstance(v, str) or not v.strip():
            raise ValueError("Webhook URL must be a non-empty string")

        # Basic URL validation
        url_regex = r"^https?://[^\s/$.?#].[^\s]*$"
        if not re.match(url_regex, v):
            raise ValueError("Invalid webhook URL format. Must be a valid HTTP/HTTPS URL")

        # Additional security check - only allow HTTPS in production
        if not v.startswith("https://"):
            # In a real app, you'd check environment here
            # For now, we'll allow HTTP but warn about it
            pass

        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_type": "attentional_blink",
                "parameters": {
                    "stream_length": 15,
                    "item_duration_ms": 100.0,
                    "num_trials_per_lag": 20,
                    "lags": [1, 2, 3, 4, 8],
                    "target_salience": 2.0,
                },
                "webhook_url": "https://example.com/webhook/task_complete",
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


class TaskResultResponse(BaseModel):
    """Response for task result."""

    task_id: str = Field(..., description="Unique task identifier")
    result: Dict[str, Any] = Field(..., description="Task result data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "task_xyz789",
                "result": {
                    "accuracy": 0.85,
                    "trials_completed": 50,
                    "response_times": [0.5, 0.6, 0.4],
                },
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
            "examples": [
                {
                    "summary": "Completed task",
                    "value": {
                        "task_id": "task_xyz789",
                        "status": "completed",
                        "state": "SUCCESS",
                        "result": {
                            "accuracy": 0.85,
                            "trials_completed": 50,
                            "response_times": [0.5, 0.6, 0.4, 0.7, 0.3],
                            "lag_performance": {
                                "lag_1": {"accuracy": 0.9, "rt_mean": 0.45},
                                "lag_2": {"accuracy": 0.8, "rt_mean": 0.52},
                            },
                        },
                    },
                },
                {
                    "summary": "Running task",
                    "value": {
                        "task_id": "task_xyz789",
                        "status": "running",
                        "state": "PROGRESS",
                        "info": {"current_trial": 25, "total_trials": 100, "progress": 0.25},
                    },
                },
                {
                    "summary": "Failed task",
                    "value": {
                        "task_id": "task_xyz789",
                        "status": "failed",
                        "state": "FAILURE",
                        "error": "Task execution failed: Invalid parameters provided",
                    },
                },
                {
                    "summary": "Pending task",
                    "value": {
                        "task_id": "task_xyz789",
                        "status": "pending",
                        "state": "PENDING",
                    },
                },
            ]
        }
    )


class TaskListResponse(BaseModel):
    """Response for list of available tasks."""

    tasks: list[Dict[str, Any]] = Field(..., description="List of available tasks")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tasks": [
                    {
                        "task_type": "iowa_gambling",
                        "name": "Iowa Gambling Task",
                        "description": "Decision-making task with four decks of cards",
                        "parameters": {
                            "num_trials": {
                                "type": "integer",
                                "default": 100,
                                "description": "Number of trials",
                            },
                            "initial_balance": {
                                "type": "integer",
                                "default": 2000,
                                "description": "Starting balance",
                            },
                            "deck_stimulus_strength": {
                                "type": "float",
                                "default": 1.5,
                                "description": "Deck visual strength",
                            },
                            "outcome_stimulus_strength": {
                                "type": "float",
                                "default": 2.0,
                                "description": "Outcome strength",
                            },
                            "interoceptive_gain": {
                                "type": "float",
                                "default": 1.0,
                                "description": "Interoceptive signal multiplier",
                            },
                            "deck_selection_strategy": {
                                "type": "string",
                                "default": "balanced",
                                "description": "Selection strategy",
                            },
                        },
                    },
                    {
                        "task_type": "attentional_blink",
                        "name": "Attentional Blink Task",
                        "description": "RSVP task measuring attentional blink effect",
                        "parameters": {
                            "stream_length": {
                                "type": "integer",
                                "default": 15,
                                "description": "Number of items in RSVP stream",
                            },
                            "item_duration_ms": {
                                "type": "float",
                                "default": 100.0,
                                "description": "Duration of each item",
                            },
                            "num_trials_per_lag": {
                                "type": "integer",
                                "default": 20,
                                "description": "Trials per lag condition",
                            },
                            "lags": {
                                "type": "array",
                                "default": [1, 2, 3, 4, 8],
                                "description": "Lags to test",
                            },
                            "target_salience": {
                                "type": "float",
                                "default": 2.0,
                                "description": "Target salience boost",
                            },
                        },
                    },
                ]
            }
        }
    )


class SessionTaskListResponse(BaseModel):
    """Response for session tasks list."""

    tasks: list[TaskStatusResponse] = Field(..., description="List of tasks for the session")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tasks": [
                    {
                        "task_id": "task_xyz789",
                        "status": "completed",
                        "state": "SUCCESS",
                        "result": {"accuracy": 0.85, "trials_completed": 50},
                        "created_at": "2024-01-15T10:30:00Z",
                    }
                ],
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

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        """Validate username format."""
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")

        # Check username format (alphanumeric, underscore, dash, min 3 chars)
        if not re.match(r"^[a-zA-Z0-9_-]{3,50}$", v):
            raise ValueError(
                "Username must be 3-50 characters, alphanumeric with underscores or dashes"
            )

        return v.strip()

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        """Validate email format."""
        if not v or not v.strip():
            raise ValueError("Email cannot be empty")

        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, v):
            raise ValueError("Invalid email format")

        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        """Validate password strength."""
        if not v or len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")

        # Check for at least one uppercase, one lowercase, one digit
        if not (re.search(r"[A-Z]", v) and re.search(r"[a-z]", v) and re.search(r"\d", v)):
            raise ValueError(
                "Password must contain at least one uppercase letter, one lowercase letter, and one digit"
            )

        return v


class UserCreateResponse(BaseModel):
    """Response for user creation."""

    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    roles: list[str] = Field(..., description="User roles")
    created_at: datetime = Field(..., description="Creation timestamp")
    message: str = Field(..., description="Response message")


class UserResponse(BaseModel):
    """Response for user details."""

    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    roles: list[str] = Field(..., description="User roles")
    is_active: bool = Field(..., description="Whether user is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")


class UserUpdateRequest(BaseModel):
    """Request to update user."""

    email: Optional[str] = Field(None, description="Email address")
    password: Optional[str] = Field(None, description="New password")
    roles: Optional[List[str]] = Field(None, description="User roles")
    is_active: Optional[bool] = Field(None, description="Whether user is active")


class PasswordResetRequest(BaseModel):
    """Request to reset password."""

    new_password: str = Field(..., description="New password")


class PasswordResetResponse(BaseModel):
    """Response for password reset."""

    user_id: str = Field(..., description="User identifier")
    message: str = Field(..., description="Reset message")


class UserStatsResponse(BaseModel):
    """Response for user statistics."""

    total_users: int = Field(..., description="Total number of users")
    active_users: int = Field(..., description="Number of active users")
    inactive_users: int = Field(..., description="Number of inactive users")
    role_counts: dict = Field(..., description="Count of users by role")
    total_sessions: int = Field(..., description="Total number of sessions")
    active_sessions: int = Field(..., description="Number of active sessions")


# State Schemas
class AllostaticState(BaseModel):
    """Allostatic state representation."""

    allostatic_load: float = Field(..., description="Allostatic load")


class BodyState(BaseModel):
    """Body state representation."""

    heart_rate: float = Field(..., description="Heart rate")
    cortisol: float = Field(..., description="Cortisol level")
    temperature: float = Field(..., description="Body temperature")


class IgnitionEvent(BaseModel):
    """Ignition event representation."""

    time_ms: float = Field(..., description="Event time in milliseconds")
    duration_ms: Optional[float] = Field(None, description="Event duration in milliseconds")
    trigger_signal: float = Field(..., description="Trigger signal")
    threshold: float = Field(..., description="Signal threshold")


class IgnitionHistoryResponse(BaseModel):
    """Response for ignition history."""

    events: list[IgnitionEvent] = Field(..., description="Ignition events")
    pagination: Optional[PaginationInfo] = Field(None, description="Pagination information")


class IgnitionState(BaseModel):
    """Ignition state representation."""

    ignition_occurred: bool = Field(..., description="Whether ignition has occurred")
    total_signal: float = Field(..., description="Total ignition signal")
    threshold: float = Field(..., description="Ignition threshold")
    duration_ms: Optional[float] = Field(None, description="Ignition duration in milliseconds")


class MetabolicState(BaseModel):
    """Metabolic state representation."""

    reserves: float = Field(..., description="Metabolic reserves")
    reserve_fraction: float = Field(..., description="Reserve fraction")


class MinimalSelfState(BaseModel):
    """Minimal self state representation."""

    coherence: float = Field(..., description="Self coherence")


class NarrativeSelfState(BaseModel):
    """Narrative self state representation."""

    narrative: str = Field(..., description="Self narrative")


class PaginationInfo(BaseModel):
    """Pagination information."""

    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "page": 1,
                "per_page": 10,
                "total": 25,
            }
        }
    )


class PrecisionState(BaseModel):
    """Precision state representation."""

    exteroceptive: float = Field(..., description="Exteroceptive precision")
    interoceptive: float = Field(..., description="Interoceptive precision")


class SelfModelState(BaseModel):
    """Self model state representation."""

    minimal: MinimalSelfState = Field(..., description="Minimal self state")
    narrative: NarrativeSelfState = Field(..., description="Narrative self state")


class SystemStateResponse(BaseModel):
    """Response for system state."""

    time_ms: float = Field(..., description="Current simulation time in milliseconds")
    ignition: IgnitionState = Field(..., description="Ignition state")
    workspace: WorkspaceState = Field(..., description="Workspace state")
    body: BodyState = Field(..., description="Body state")
    allostasis: AllostaticState = Field(..., description="Allostatic state")
    precision: PrecisionState = Field(..., description="Precision state")
    metabolism: MetabolicState = Field(..., description="Metabolic state")
    self_model: SelfModelState = Field(..., description="Self model state")


# Export Schemas
class SummaryStatistics(BaseModel):
    """Summary statistics for export."""

    mean: float = Field(..., description="Mean value")
    std: float = Field(..., description="Standard deviation")
    min: float = Field(..., description="Minimum value")
    max: float = Field(..., description="Maximum value")


class WorkspaceState(BaseModel):
    """Workspace state representation."""

    is_broadcasting: bool = Field(..., description="Whether workspace is broadcasting")
    content: Optional[str] = Field(None, description="Workspace content")
    broadcast_duration_ms: Optional[float] = Field(
        None, description="Broadcast duration in milliseconds"
    )


class PredictionErrorsResponse(BaseModel):
    """Response for prediction errors."""

    session_id: str = Field(..., description="Session identifier")
    time_ms: float = Field(..., description="Current time in milliseconds")
    prediction_errors: Dict[str, Any] = Field(..., description="Prediction errors")
    exteroceptive_stats: Dict[str, Any] = Field(..., description="Exteroceptive statistics")
    interoceptive_stats: Dict[str, Any] = Field(..., description="Interoceptive statistics")


class SomaticMarkersResponse(BaseModel):
    """Response for somatic markers."""

    session_id: str = Field(..., description="Session identifier")
    time_ms: float = Field(..., description="Current time in milliseconds")
    num_markers: int = Field(..., description="Number of markers")
    total_retrievals: int = Field(..., description="Total retrievals")
    successful_retrievals: int = Field(..., description="Successful retrievals")
    retrieval_rate: float = Field(..., description="Retrieval rate")
    markers: list[Dict[str, Any]] = Field(..., description="Somatic markers")


# API Key Management Schemas
class APIKeyCreateRequest(BaseModel):
    """Request to create a new API key."""

    name: str = Field(..., description="API key name/description")
    permissions: List[str] = Field(default_factory=list, description="Permissions for this key")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration timestamp")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate API key name."""
        if not v or not v.strip():
            raise ValueError("API key name cannot be empty")

        if len(v) > 100:
            raise ValueError("API key name is too long (max 100 characters)")

        return v.strip()

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v):
        """Validate permissions list."""
        if v is None:
            return []

        if not isinstance(v, list):
            raise ValueError("Permissions must be a list")

        valid_permissions = {"read", "write", "admin", "delete"}
        for perm in v:
            if not isinstance(perm, str) or not perm.strip():
                raise ValueError("Each permission must be a non-empty string")
            if perm not in valid_permissions:
                raise ValueError(
                    f"Invalid permission: {perm}. Must be one of: {', '.join(valid_permissions)}"
                )

        return [perm.strip() for perm in v]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "My API Key",
                "permissions": ["read", "write"],
                "expires_at": "2025-01-15T10:30:00Z",
            }
        }
    )


class APIKeyCreateResponse(BaseModel):
    """Response for API key creation."""

    key_id: str = Field(..., description="Unique API key identifier")
    key: str = Field(..., description="The actual API key (only shown once)")
    name: str = Field(..., description="API key name")
    permissions: List[str] = Field(..., description="Permissions for this key")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key_id": "key_abc123",
                "key": "apgi_abc123def456...",
                "name": "My API Key",
                "permissions": ["read", "write"],
                "expires_at": "2025-01-15T10:30:00Z",
                "created_at": "2024-01-15T10:30:00Z",
            }
        }
    )


class APIKeyResponse(BaseModel):
    """Response for API key details (without the actual key)."""

    key_id: str = Field(..., description="Unique API key identifier")
    name: str = Field(..., description="API key name")
    permissions: List[str] = Field(..., description="Permissions for this key")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    is_active: bool = Field(..., description="Whether the key is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key_id": "key_abc123",
                "name": "My API Key",
                "permissions": ["read", "write"],
                "expires_at": "2025-01-15T10:30:00Z",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z",
                "last_used_at": "2024-01-16T08:45:00Z",
            }
        }
    )


class APIKeyListResponse(BaseModel):
    """Response for API keys list."""

    api_keys: List[APIKeyResponse] = Field(..., description="List of API keys")
    pagination: PaginationInfo = Field(..., description="Pagination information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "api_keys": [
                    {
                        "key_id": "key_abc123",
                        "name": "My API Key",
                        "permissions": ["read", "write"],
                        "expires_at": "2025-01-15T10:30:00Z",
                        "is_active": True,
                        "created_at": "2024-01-15T10:30:00Z",
                        "last_used_at": "2024-01-16T08:45:00Z",
                    }
                ],
                "pagination": {
                    "page": 1,
                    "per_page": 10,
                    "total": 1,
                },
            }
        }
    )


class APIKeyUpdateRequest(BaseModel):
    """Request to update an API key."""

    name: Optional[str] = Field(None, description="API key name")
    permissions: Optional[List[str]] = Field(None, description="Permissions for this key")
    is_active: Optional[bool] = Field(None, description="Whether the key is active")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate API key name."""
        if v is None:
            return v

        if not v.strip():
            raise ValueError("API key name cannot be empty")

        if len(v) > 100:
            raise ValueError("API key name is too long (max 100 characters)")

        return v.strip()

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v):
        """Validate permissions list."""
        if v is None:
            return v

        if not isinstance(v, list):
            raise ValueError("Permissions must be a list")

        valid_permissions = {"read", "write", "admin", "delete"}
        for perm in v:
            if not isinstance(perm, str) or not perm.strip():
                raise ValueError("Each permission must be a non-empty string")
            if perm not in valid_permissions:
                raise ValueError(
                    f"Invalid permission: {perm}. Must be one of: {', '.join(valid_permissions)}"
                )

        return [perm.strip() for perm in v]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated API Key Name",
                "permissions": ["read", "write", "admin"],
                "is_active": False,
            }
        }
    )


# Webhook Delivery Management Schemas
class WebhookDeliveryResponse(BaseModel):
    """Response for webhook delivery details."""

    delivery_id: str = Field(..., description="Unique delivery identifier")
    task_id: str = Field(..., description="Associated task ID")
    webhook_url: str = Field(..., description="Target webhook URL")
    status: str = Field(..., description="Delivery status")
    attempts: int = Field(..., description="Number of delivery attempts")
    last_attempt_at: Optional[datetime] = Field(None, description="Last delivery attempt timestamp")
    next_retry_at: Optional[datetime] = Field(None, description="Next retry timestamp")
    response_status: Optional[int] = Field(None, description="HTTP response status code")
    response_body: Optional[str] = Field(None, description="HTTP response body")
    error_message: Optional[str] = Field(None, description="Error message if delivery failed")
    created_at: datetime = Field(..., description="Delivery record creation timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "delivery_id": "delivery_abc123",
                "task_id": "task_xyz789",
                "webhook_url": "https://example.com/webhook",
                "status": "delivered",
                "attempts": 1,
                "last_attempt_at": "2024-01-15T10:35:00Z",
                "next_retry_at": None,
                "response_status": 200,
                "response_body": '{"status": "success"}',
                "error_message": None,
                "created_at": "2024-01-15T10:30:00Z",
            }
        }
    )


class WebhookDeliveryListResponse(BaseModel):
    """Response for webhook deliveries list."""

    deliveries: List[WebhookDeliveryResponse] = Field(..., description="List of webhook deliveries")
    pagination: PaginationInfo = Field(..., description="Pagination information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "deliveries": [
                    {
                        "delivery_id": "delivery_abc123",
                        "task_id": "task_xyz789",
                        "webhook_url": "https://example.com/webhook",
                        "status": "delivered",
                        "attempts": 1,
                        "last_attempt_at": "2024-01-15T10:35:00Z",
                        "next_retry_at": None,
                        "response_status": 200,
                        "response_body": '{"status": "success"}',
                        "error_message": None,
                        "created_at": "2024-01-15T10:30:00Z",
                    }
                ],
                "pagination": {
                    "page": 1,
                    "per_page": 10,
                    "total": 1,
                },
            }
        }
    )


class WebhookRetryResponse(BaseModel):
    """Response for webhook retry operation."""

    delivery_id: str = Field(..., description="Delivery identifier")
    success: bool = Field(..., description="Whether the retry was successful")
    status: str = Field(..., description="Updated delivery status")
    attempts: int = Field(..., description="Updated number of attempts")
    last_attempt_at: datetime = Field(..., description="Last attempt timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "delivery_id": "delivery_abc123",
                "success": True,
                "status": "delivered",
                "attempts": 2,
                "last_attempt_at": "2024-01-15T10:40:00Z",
            }
        }
    )
