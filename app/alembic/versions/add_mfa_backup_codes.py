"""Add MFA backup codes field to User model

Revision ID: add_mfa_backup_codes
Revises: add_password_reset_tokens
Create Date: 2025-01-20 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_mfa_backup_codes"
down_revision = "add_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add mfa_backup_codes column to users table
    op.add_column(
        "users",
        sa.Column(
            "mfa_backup_codes",
            sa.JSON,
            nullable=True,
            comment="One-time backup codes for MFA recovery",
        ),
    )


def downgrade() -> None:
    # Remove mfa_backup_codes column from users table
    op.drop_column("users", "mfa_backup_codes")
