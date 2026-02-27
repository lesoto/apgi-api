"""Add retry_count and retry_delays columns to webhook_deliveries table

Revision ID: add_retry_config_to_webhook_deliveries
Revises: add_unique_constraint_user_name_session_templates
Create Date: 2025-02-27 09:33:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_retry_config_to_webhook_deliveries"
down_revision = "add_unique_constraint_user_name_session_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add retry_count column to webhook_deliveries table
    op.add_column(
        "webhook_deliveries",
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            default=5,
            comment="Maximum retry attempts",
        ),
    )

    # Add retry_delays column to webhook_deliveries table
    op.add_column(
        "webhook_deliveries",
        sa.Column(
            "retry_delays",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            default=sa.text("'[5, 30, 300, 1800, 3600]'"),
            comment="Retry delay schedule in seconds",
        ),
    )


def downgrade() -> None:
    # Remove retry_delays column from webhook_deliveries table
    op.drop_column("webhook_deliveries", "retry_delays")

    # Remove retry_count column from webhook_deliveries table
    op.drop_column("webhook_deliveries", "retry_count")
