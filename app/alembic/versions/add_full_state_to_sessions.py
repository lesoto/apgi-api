"""Add full_state column to sessions table

Revision ID: add_full_state_to_sessions
Revises: 9af3534145e0
Create Date: 2025-02-27 09:33:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_full_state_to_sessions"
down_revision = "9af3534145e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add full_state column to sessions table
    op.add_column(
        "sessions",
        sa.Column(
            "full_state",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="Full APGI system state for persistence",
        ),
    )


def downgrade() -> None:
    # Remove full_state column from sessions table
    op.drop_column("sessions", "full_state")
