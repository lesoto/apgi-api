"""Add is_active and updated_at to User model

Revision ID: 002
Revises: 001
Create Date: 2025-01-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_active column to users table
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            default=True,
            comment="Whether the user account is active",
        ),
    )

    # Add updated_at column to users table
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last update timestamp",
        ),
    )


def downgrade() -> None:
    # Remove updated_at column from users table
    op.drop_column("users", "updated_at")

    # Remove is_active column from users table
    op.drop_column("users", "is_active")
