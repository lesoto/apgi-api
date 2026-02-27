"""Add server_onupdate to updated_at columns

Revision ID: add_server_onupdate_to_updated_at
Revises: add_full_state_to_sessions
Create Date: 2025-02-27 09:33:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_server_onupdate_to_updated_at"
down_revision = "add_full_state_to_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add server_onupdate to updated_at column in users table
    op.alter_column(
        "users",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_onupdate=sa.text("now()"),
        existing_nullable=False,
    )

    # Add server_onupdate to updated_at column in session_templates table
    op.alter_column(
        "session_templates",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_onupdate=sa.text("now()"),
        existing_nullable=False,
    )

    # Add server_onupdate to updated_at column in sessions table
    op.alter_column(
        "sessions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_onupdate=sa.text("now()"),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Remove server_onupdate from updated_at column in sessions table
    op.alter_column(
        "sessions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_onupdate=None,
        existing_nullable=False,
    )

    # Remove server_onupdate from updated_at column in session_templates table
    op.alter_column(
        "session_templates",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_onupdate=None,
        existing_nullable=False,
    )

    # Remove server_onupdate from updated_at column in users table
    op.alter_column(
        "users",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_onupdate=None,
        existing_nullable=False,
    )
