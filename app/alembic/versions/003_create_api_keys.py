"""Create api_keys table

Revision ID: 003
Revises: 002
Create Date: 2025-02-01 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column(
            "key_id",
            sa.String(length=36),
            nullable=False,
            comment="Unique API key identifier",
        ),
        sa.Column("user_id", sa.String(length=36), nullable=False, comment="Owner user ID"),
        sa.Column(
            "name", sa.String(length=100), nullable=False, comment="API key name/description"
        ),
        sa.Column("key_hash", sa.String(length=255), nullable=False, comment="Hashed API key"),
        sa.Column(
            "permissions",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            comment="Permissions for this key",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Expiration timestamp",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            default=True,
            comment="Whether the key is active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Creation timestamp",
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last usage timestamp",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("key_id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("idx_api_keys_user", "api_keys", ["user_id"])
    op.create_index("idx_api_keys_expires", "api_keys", ["expires_at"])
    op.create_index("idx_api_keys_active", "api_keys", ["is_active"])


def downgrade() -> None:
    # Drop api_keys table
    op.drop_table("api_keys")
