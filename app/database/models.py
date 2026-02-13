"""
SQLAlchemy Database Models

ORM models for persistent storage of sessions, tasks, and user data.
"""

import uuid
from enum import Enum

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


# ============================================================================
# Enums
# ============================================================================


class SessionState(str, Enum):
    """Session lifecycle states."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class TaskStatus(str, Enum):
    """Task execution states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Database Models
# ============================================================================


class User(Base):  # type: ignore[misc, valid-type]
    """User account model."""

    __tablename__ = "users"

    user_id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique user identifier",
    )
    username = Column(
        String(100), unique=True, nullable=False, index=True, comment="Unique username"
    )
    email = Column(
        String(255), unique=True, nullable=False, index=True, comment="User email address"
    )
    password_hash = Column(String(255), nullable=False, comment="Hashed password")
    roles = Column(ARRAY(Text), nullable=False, default=list, comment="User roles for RBAC")  # type: ignore[var-annotated]
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Account creation timestamp",
    )
    last_login = Column(DateTime(timezone=True), nullable=True, comment="Last login timestamp")

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(user_id={self.user_id}, username={self.username})>"


class Session(Base):  # type: ignore[misc, valid-type]
    """Simulation session model."""

    __tablename__ = "sessions"

    session_id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique session identifier",
    )
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID",
    )
    config = Column(JSONB, nullable=False, comment="Session configuration as JSON")
    state = Column(
        String(20),
        nullable=False,
        default=SessionState.CREATED.value,
        index=True,
        comment="Current session state",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Session creation timestamp",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp",
    )
    description = Column(Text, nullable=True, comment="Human-readable session description")
    tags = Column(ARRAY(Text), nullable=True, default=list, comment="Session tags for organization")  # type: ignore[var-annotated]

    # Relationships
    user = relationship("User", back_populates="sessions")
    tasks = relationship("Task", back_populates="session", cascade="all, delete-orphan")
    session_data = relationship(
        "SessionData", back_populates="session", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_sessions_user_created", "user_id", "created_at"),
        Index("idx_sessions_state", "state"),
    )

    def __repr__(self):
        return f"<Session(session_id={self.session_id}, state={self.state})>"


class Task(Base):  # type: ignore[misc, valid-type]
    """Experimental task model."""

    __tablename__ = "tasks"

    task_id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique task identifier",
    )
    session_id = Column(
        String(36),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated session ID",
    )
    task_type = Column(String(50), nullable=False, index=True, comment="Type of experimental task")
    parameters = Column(JSONB, nullable=False, comment="Task parameters as JSON")
    status = Column(
        String(20),
        nullable=False,
        default=TaskStatus.PENDING.value,
        index=True,
        comment="Current task status",
    )
    progress = Column(Integer, nullable=True, comment="Progress percentage (0-100)")
    result_data = Column(JSONB, nullable=True, comment="Task results as JSON")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Task creation timestamp",
    )
    started_at = Column(DateTime(timezone=True), nullable=True, comment="Task start timestamp")
    completed_at = Column(
        DateTime(timezone=True), nullable=True, comment="Task completion timestamp"
    )
    error_message = Column(Text, nullable=True, comment="Error message if task failed")
    webhook_url = Column(
        String(500), nullable=True, comment="Webhook URL for completion notification"
    )

    # Relationships
    session = relationship("Session", back_populates="tasks")

    # Indexes
    __table_args__ = (
        Index("idx_tasks_session_created", "session_id", "created_at"),
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_type", "task_type"),
    )

    def __repr__(self):
        return f"<Task(task_id={self.task_id}, type={self.task_type}, status={self.status})>"


class SessionData(Base):  # type: ignore[misc, valid-type]
    """Time series data for simulation sessions."""

    __tablename__ = "session_data"

    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="Auto-incrementing primary key"
    )
    session_id = Column(
        String(36),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated session ID",
    )
    time_ms = Column(Float, nullable=False, comment="Simulation time in milliseconds")
    data = Column(JSONB, nullable=False, comment="State data as JSON")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp",
    )

    # Relationships
    session = relationship("Session", back_populates="session_data")

    # Indexes for efficient time-based queries
    __table_args__ = (
        Index("idx_session_data_session_time", "session_id", "time_ms"),
        Index("idx_session_data_time", "time_ms"),
    )

    def __repr__(self):
        return f"<SessionData(id={self.id}, session_id={self.session_id}, time_ms={self.time_ms})>"


class RefreshToken(Base):  # type: ignore[misc, valid-type]
    """Refresh token storage for authentication."""

    __tablename__ = "refresh_tokens"

    token_id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique token identifier",
    )
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated user ID",
    )
    token_hash = Column(String(255), nullable=False, unique=True, comment="Hashed refresh token")
    expires_at = Column(
        DateTime(timezone=True), nullable=False, index=True, comment="Token expiration timestamp"
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Token creation timestamp",
    )
    revoked = Column(
        Boolean, nullable=False, default=False, comment="Whether token has been revoked"
    )

    # Indexes
    __table_args__ = (
        Index("idx_refresh_tokens_user", "user_id"),
        Index("idx_refresh_tokens_expires", "expires_at"),
    )

    def __repr__(self):
        return f"<RefreshToken(token_id={self.token_id}, user_id={self.user_id})>"


class WebhookDelivery(Base):  # type: ignore[misc, valid-type]
    """Webhook delivery tracking."""

    __tablename__ = "webhook_deliveries"

    delivery_id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique delivery identifier",
    )
    task_id = Column(
        String(36),
        ForeignKey("tasks.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated task ID",
    )
    webhook_url = Column(String(500), nullable=False, comment="Target webhook URL")
    payload = Column(JSONB, nullable=False, comment="Webhook payload as JSON")
    status = Column(String(20), nullable=False, default="pending", comment="Delivery status")
    attempts = Column(Integer, nullable=False, default=0, comment="Number of delivery attempts")
    last_attempt_at = Column(
        DateTime(timezone=True), nullable=True, comment="Last delivery attempt timestamp"
    )
    next_retry_at = Column(DateTime(timezone=True), nullable=True, comment="Next retry timestamp")
    response_status = Column(Integer, nullable=True, comment="HTTP response status code")
    response_body = Column(Text, nullable=True, comment="HTTP response body")
    error_message = Column(Text, nullable=True, comment="Error message if delivery failed")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Delivery record creation timestamp",
    )

    # Indexes
    __table_args__ = (
        Index("idx_webhook_deliveries_task", "task_id"),
        Index("idx_webhook_deliveries_status", "status"),
        Index("idx_webhook_deliveries_next_retry", "next_retry_at"),
    )

    def __repr__(self):
        return f"<WebhookDelivery(delivery_id={self.delivery_id}, status={self.status})>"
