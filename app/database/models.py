"""
SQLAlchemy Database Models

ORM models for persistent storage of sessions, tasks, and user data.
"""

import uuid
from enum import Enum as PythonEnum

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy.sql import func

Base = declarative_base()


# ============================================================================
# Enums
# ============================================================================


class SessionState(str, PythonEnum):
    """Session lifecycle states."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class TaskStatus(str, PythonEnum):
    """Task execution states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    is_active = Column(
        Boolean, nullable=False, default=True, comment="Whether the user account is active"
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Account creation timestamp",
    )
    last_login = Column(DateTime(timezone=True), nullable=True, comment="Last login timestamp")

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    session_templates = relationship(
        "SessionTemplate", back_populates="user", cascade="all, delete-orphan"
    )
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(user_id={self.user_id}, username={self.username})>"


class SessionTemplate(Base):  # type: ignore[misc, valid-type]
    """Session template model for reusable session configurations."""

    __tablename__ = "session_templates"

    template_id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique template identifier",
    )
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID",
    )
    name = Column(String(100), nullable=False, index=True, comment="Template name")
    description = Column(Text, nullable=True, comment="Template description")
    config_path = Column(String(255), nullable=True, comment="Path to YAML configuration file")
    custom_config = Column(JSONB, nullable=True, comment="Default custom configuration overrides")
    default_description = Column(Text, nullable=True, comment="Default session description")
    tags = Column(ARRAY(Text), nullable=True, default=list, comment="Template tags for organization")  # type: ignore[var-annotated]
    is_public = Column(Boolean, nullable=False, default=False, comment="Whether template is public")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Template creation timestamp",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp",
    )

    # Relationships
    user = relationship("User", back_populates="session_templates")
    sessions = relationship("Session", back_populates="template")

    # Indexes
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_session_templates_user_name"),
        Index("idx_session_templates_user_name", "user_id", "name"),
        Index("idx_session_templates_public", "is_public"),
        Index("idx_session_templates_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<SessionTemplate(template_id={self.template_id}, name={self.name})>"


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
    template_id = Column(
        String(36),
        ForeignKey("session_templates.template_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Template used to create this session",
    )
    config = Column(JSONB, nullable=False, comment="Session configuration as JSON")
    full_state = Column(JSONB, nullable=True, comment="Full APGI system state for persistence")
    state: Mapped[SessionState] = mapped_column(
        SQLEnum(SessionState),
        nullable=False,
        default=SessionState.CREATED,
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
    template = relationship("SessionTemplate", back_populates="sessions")
    tasks = relationship("Task", back_populates="session", cascade="all, delete-orphan")
    session_data = relationship(
        "SessionData", back_populates="session", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_sessions_user_created", "user_id", "created_at"),
        Index("idx_sessions_state", "state"),
        Index("idx_sessions_created_at", "created_at"),
        Index("idx_sessions_user_state", "user_id", "state"),
        Index("idx_sessions_template", "template_id"),
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
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus),
        name="status",
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
        comment="Current task status",
    )
    priority = Column(
        Integer, nullable=False, default=5, comment="Task priority (1=highest, 10=lowest)"
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
    dependencies = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.dependent_task_id",
        back_populates="dependent_task",
        cascade="all, delete-orphan",
    )
    prerequisite_for = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.prerequisite_task_id",
        back_populates="prerequisite_task",
        passive_deletes=True,
    )

    # Indexes
    __table_args__ = (
        Index("idx_tasks_session_created", "session_id", "created_at"),
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_type", "task_type"),
        Index("idx_tasks_priority", "priority"),
    )

    def __repr__(self):
        return f"<Task(task_id={self.task_id}, type={self.task_type}, status={self.status})>"


class TaskDependency(Base):  # type: ignore[misc, valid-type]
    """Task dependency model for managing task execution order."""

    __tablename__ = "task_dependencies"

    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="Auto-incrementing primary key"
    )
    dependent_task_id = Column(
        String(36),
        ForeignKey("tasks.task_id", ondelete="CASCADE"),
        nullable=False,
        comment="Task that depends on the prerequisite",
    )
    prerequisite_task_id = Column(
        String(36),
        ForeignKey("tasks.task_id", ondelete="CASCADE"),
        nullable=False,
        comment="Task that must complete before the dependent task",
    )
    dependency_type = Column(
        String(20),
        nullable=False,
        default="completion",
        comment="Type of dependency (completion, success, failure)",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Dependency creation timestamp",
    )

    # Relationships
    dependent_task = relationship(
        "Task", foreign_keys=[dependent_task_id], back_populates="dependencies"
    )
    prerequisite_task = relationship(
        "Task", foreign_keys=[prerequisite_task_id], back_populates="prerequisite_for"
    )

    # Indexes
    __table_args__ = (
        Index("idx_task_dependencies_dependent", "dependent_task_id"),
        Index("idx_task_dependencies_prerequisite", "prerequisite_task_id"),
        Index(
            "idx_task_dependencies_unique", "dependent_task_id", "prerequisite_task_id", unique=True
        ),
    )

    def __repr__(self):
        return f"<TaskDependency(dependent={self.dependent_task_id}, prerequisite={self.prerequisite_task_id})>"


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


class APIKey(Base):  # type: ignore[misc, valid-type]
    """API key for authentication."""

    __tablename__ = "api_keys"

    key_id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique API key identifier",
    )
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user ID",
    )
    name = Column(String(100), nullable=False, comment="API key name/description")
    key_hash = Column(String(255), nullable=False, unique=True, comment="Hashed API key")
    key_prefix = Column(
        String(16), nullable=False, index=True, comment="HMAC prefix for fast lookup"
    )
    permissions = Column(ARRAY(Text), nullable=False, default=list, comment="Permissions for this key")  # type: ignore[var-annotated]
    expires_at = Column(DateTime(timezone=True), nullable=True, comment="Expiration timestamp")
    is_active = Column(Boolean, nullable=False, default=True, comment="Whether the key is active")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Creation timestamp",
    )
    last_used_at = Column(DateTime(timezone=True), nullable=True, comment="Last usage timestamp")

    # Relationships
    user = relationship("User", back_populates="api_keys")

    # Indexes
    __table_args__ = (
        Index("idx_api_keys_user", "user_id"),
        Index("idx_api_keys_expires", "expires_at"),
        Index("idx_api_keys_active", "is_active"),
    )

    def __repr__(self):
        return f"<APIKey(key_id={self.key_id}, name={self.name})>"


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
    retry_count = Column(Integer, nullable=False, default=5, comment="Maximum retry attempts")
    retry_delays = Column(
        JSONB,
        nullable=False,
        default=lambda: [5, 30, 300, 1800, 3600],
        comment="Retry delay schedule in seconds",
    )
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


class AuditLog(Base):  # type: ignore[misc, valid-type]
    """Audit log for tracking user actions and access events."""

    __tablename__ = "audit_logs"

    audit_id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique audit event identifier",
    )
    user_id = Column(
        String(36),
        ForeignKey("users.user_id"),
        nullable=True,
        index=True,
        comment="User who performed the action (null for anonymous actions)",
    )
    action = Column(String(100), nullable=False, index=True, comment="Action performed")
    resource_type = Column(
        String(50), nullable=False, index=True, comment="Type of resource affected"
    )
    resource_id = Column(
        String(255), nullable=True, index=True, comment="ID of the affected resource"
    )
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the action occurred",
    )
    details = Column(JSONB, nullable=True, comment="Additional details about the action")
    ip_address = Column(String(45), nullable=True, comment="Client IP address")
    user_agent = Column(Text, nullable=True, comment="Client user agent string")
    status = Column(String(20), nullable=False, default="success", comment="Action outcome")

    # Relationships
    user = relationship("User", backref="audit_logs")

    # Indexes
    __table_args__ = (
        Index("idx_audit_logs_user_timestamp", "user_id", "timestamp"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_timestamp", "timestamp"),
    )

    def __repr__(self):
        return f"<AuditLog(audit_id={self.audit_id}, user_id={self.user_id}, action={self.action})>"
