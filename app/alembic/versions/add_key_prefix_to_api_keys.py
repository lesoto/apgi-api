"""Add key_prefix column to api_keys table

Revision ID: add_key_prefix_to_api_keys
Revises: add_server_onupdate_to_updated_at
Create Date: 2025-02-27 09:33:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_key_prefix_to_api_keys"
down_revision = "add_server_onupdate_to_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add key_prefix column to api_keys table
    op.add_column(
        "api_keys",
        sa.Column(
            "key_prefix",
            sa.String(16),
            nullable=False,
            index=True,
            comment="HMAC prefix for fast lookup",
        ),
    )


def downgrade() -> None:
    # Remove key_prefix column from api_keys table
    op.drop_column("api_keys", "key_prefix")
