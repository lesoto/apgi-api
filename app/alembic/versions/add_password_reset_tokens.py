"""Add password reset token fields to User model

Revision ID: add_password_reset_tokens
Revises: add_unique_constraint_user_name_session_templates
Create Date: 2025-01-20 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_password_reset_tokens"
down_revision = "add_unique_constraint_user_name_session_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add password_reset_token column to users table
    op.add_column(
        "users",
        sa.Column(
            "password_reset_token",
            sa.String(255),
            nullable=True,
            comment="Token for password reset",
        ),
    )

    # Add password_reset_expires_at column to users table
    op.add_column(
        "users",
        sa.Column(
            "password_reset_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Password reset token expiration",
        ),
    )


def downgrade() -> None:
    # Remove password_reset_expires_at column from users table
    op.drop_column("users", "password_reset_expires_at")

    # Remove password_reset_token column from users table
    op.drop_column("users", "password_reset_token")
