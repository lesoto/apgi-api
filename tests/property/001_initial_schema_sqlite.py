"""SQLite-compatible initial schema for testing.

This is a modified version of 001_initial_schema.py that uses SQLite-compatible types.
"""

import sqlalchemy as sa
from alembic import op

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
            "roles", sa.Text(), nullable=False, comment="User roles for RBAC (JSON array as text)"
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
        sa.Column("user_id", sa.String(length=36), nullable=False, comment="User ID"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Session creation timestamp",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Session expiration timestamp",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="Whether session is active"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )

    # Create tasks table
    op.create_table(
        "tasks",
        sa.Column(
            "task_id", sa.String(length=36), nullable=False, comment="Unique task identifier"
        ),
        sa.Column("session_id", sa.String(length=36), nullable=False, comment="Session ID"),
        sa.Column("task_type", sa.String(length=100), nullable=False, comment="Type of task"),
        sa.Column("status", sa.String(length=50), nullable=False, comment="Task status"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Task creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Task update timestamp",
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
        sa.Column("parameters", sa.Text(), nullable=True, comment="Task parameters (JSON)"),
        sa.Column("result_data", sa.Text(), nullable=True, comment="Task results (JSON)"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error message if failed"),
        sa.Column(
            "webhook_url",
            sa.String(length=500),
            nullable=True,
            comment="Webhook URL for notifications",
        ),
        sa.Column("priority", sa.Integer(), nullable=True, comment="Task priority"),
        sa.Column("max_retries", sa.Integer(), nullable=True, comment="Maximum retry attempts"),
        sa.Column("retry_count", sa.Integer(), nullable=True, comment="Current retry count"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.PrimaryKeyConstraint("task_id"),
    )

    # Create session_data table
    op.create_table(
        "session_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False, comment="Session ID"),
        sa.Column("key", sa.String(length=255), nullable=False, comment="Data key"),
        sa.Column("value", sa.Text(), nullable=True, comment="Data value (JSON)"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last update timestamp",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "token_id", sa.String(length=36), nullable=False, comment="Unique token identifier"
        ),
        sa.Column("user_id", sa.String(length=36), nullable=False, comment="User ID"),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Token expiration timestamp",
        ),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, comment="Whether token is revoked"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Token creation timestamp",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create webhook_deliveries table
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "delivery_id",
            sa.String(length=36),
            nullable=False,
            comment="Unique delivery identifier",
        ),
        sa.Column("task_id", sa.String(length=36), nullable=False, comment="Task ID"),
        sa.Column("webhook_url", sa.String(length=500), nullable=False, comment="Webhook URL"),
        sa.Column("status", sa.String(length=50), nullable=False, comment="Delivery status"),
        sa.Column(
            "attempt_count", sa.Integer(), nullable=False, comment="Number of delivery attempts"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Delivery creation timestamp",
        ),
        sa.Column(
            "last_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last delivery attempt timestamp",
        ),
        sa.Column("response_data", sa.Text(), nullable=True, comment="Response data (JSON)"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error message if failed"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.task_id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # Drop tables in reverse order of creation (to handle foreign key constraints)
    op.drop_table("webhook_deliveries")
    op.drop_table("refresh_tokens")
    op.drop_table("session_data")
    op.drop_table("tasks")
    op.drop_table("sessions")
    op.drop_table("users")
