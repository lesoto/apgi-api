"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2025-12-03 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column(
            "user_id", sa.String(length=36), nullable=False, comment="Unique user identifier"
        ),
        sa.Column("username", sa.String(length=100), nullable=False, comment="Unique username"),
        sa.Column("email", sa.String(length=255), nullable=False, comment="User email address"),
        sa.Column(
            "password_hash", sa.String(length=255), nullable=False, comment="Hashed password"
        ),
        sa.Column(
            "roles", postgresql.ARRAY(sa.Text()), nullable=False, comment="User roles for RBAC"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Account creation timestamp",
        ),
        sa.Column(
            "last_login", sa.DateTime(timezone=True), nullable=True, comment="Last login timestamp"
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Create sessions table
    op.create_table(
        "sessions",
        sa.Column(
            "session_id", sa.String(length=36), nullable=False, comment="Unique session identifier"
        ),
        sa.Column("user_id", sa.String(length=36), nullable=False, comment="Owner user ID"),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Session configuration as JSON",
        ),
        sa.Column("state", sa.String(length=20), nullable=False, comment="Current session state"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Session creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last update timestamp",
        ),
        sa.Column(
            "description", sa.Text(), nullable=True, comment="Human-readable session description"
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
            comment="Session tags for organization",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("idx_sessions_user_created", "sessions", ["user_id", "created_at"])
    op.create_index("idx_sessions_state", "sessions", ["state"])

    # Create tasks table
    op.create_table(
        "tasks",
        sa.Column(
            "task_id", sa.String(length=36), nullable=False, comment="Unique task identifier"
        ),
        sa.Column(
            "session_id", sa.String(length=36), nullable=False, comment="Associated session ID"
        ),
        sa.Column(
            "task_type", sa.String(length=50), nullable=False, comment="Type of experimental task"
        ),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Task parameters as JSON",
        ),
        sa.Column("status", sa.String(length=20), nullable=False, comment="Current task status"),
        sa.Column("progress", sa.Integer(), nullable=True, comment="Progress percentage (0-100)"),
        sa.Column(
            "result_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Task results as JSON",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Task creation timestamp",
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=True, comment="Task start timestamp"
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Task completion timestamp",
        ),
        sa.Column(
            "error_message", sa.Text(), nullable=True, comment="Error message if task failed"
        ),
        sa.Column(
            "webhook_url",
            sa.String(length=500),
            nullable=True,
            comment="Webhook URL for completion notification",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("idx_tasks_session_created", "tasks", ["session_id", "created_at"])
    op.create_index("idx_tasks_status", "tasks", ["status"])
    op.create_index("idx_tasks_type", "tasks", ["task_type"])

    # Create session_data table
    op.create_table(
        "session_data",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            comment="Auto-incrementing primary key",
        ),
        sa.Column(
            "session_id", sa.String(length=36), nullable=False, comment="Associated session ID"
        ),
        sa.Column("time_ms", sa.Float(), nullable=False, comment="Simulation time in milliseconds"),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="State data as JSON",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_session_data_session_time", "session_data", ["session_id", "time_ms"])
    op.create_index("idx_session_data_time", "session_data", ["time_ms"])

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "token_id", sa.String(length=36), nullable=False, comment="Unique token identifier"
        ),
        sa.Column("user_id", sa.String(length=36), nullable=False, comment="Associated user ID"),
        sa.Column(
            "token_hash", sa.String(length=255), nullable=False, comment="Hashed refresh token"
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Token expiration timestamp",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Token creation timestamp",
        ),
        sa.Column(
            "revoked", sa.Boolean(), nullable=False, comment="Whether token has been revoked"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_id"),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("idx_refresh_tokens_user", "refresh_tokens", ["user_id"])
    op.create_index("idx_refresh_tokens_expires", "refresh_tokens", ["expires_at"])

    # Create webhook_deliveries table
    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "delivery_id",
            sa.String(length=36),
            nullable=False,
            comment="Unique delivery identifier",
        ),
        sa.Column("task_id", sa.String(length=36), nullable=False, comment="Associated task ID"),
        sa.Column(
            "webhook_url", sa.String(length=500), nullable=False, comment="Target webhook URL"
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Webhook payload as JSON",
        ),
        sa.Column("status", sa.String(length=20), nullable=False, comment="Delivery status"),
        sa.Column("attempts", sa.Integer(), nullable=False, comment="Number of delivery attempts"),
        sa.Column(
            "last_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last delivery attempt timestamp",
        ),
        sa.Column(
            "next_retry_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Next retry timestamp",
        ),
        sa.Column(
            "response_status", sa.Integer(), nullable=True, comment="HTTP response status code"
        ),
        sa.Column("response_body", sa.Text(), nullable=True, comment="HTTP response body"),
        sa.Column(
            "error_message", sa.Text(), nullable=True, comment="Error message if delivery failed"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Delivery record creation timestamp",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.task_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("delivery_id"),
    )
    op.create_index("idx_webhook_deliveries_task", "webhook_deliveries", ["task_id"])
    op.create_index("idx_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("idx_webhook_deliveries_next_retry", "webhook_deliveries", ["next_retry_at"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("webhook_deliveries")
    op.drop_table("refresh_tokens")
    op.drop_table("session_data")
    op.drop_table("tasks")
    op.drop_table("sessions")
    op.drop_table("users")
