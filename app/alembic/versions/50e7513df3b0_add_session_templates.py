"""Add session templates

Revision ID: 50e7513df3b0
Revises: 002
Create Date: 2026-02-18 20:19:50.883191

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "50e7513df3b0"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create session_templates table
    op.create_table(
        "session_templates",
        sa.Column(
            "template_id",
            sa.String(length=36),
            nullable=False,
            comment="Unique template identifier",
        ),
        sa.Column("user_id", sa.String(length=36), nullable=False, comment="Owner user ID"),
        sa.Column("name", sa.String(length=100), nullable=False, comment="Template name"),
        sa.Column("description", sa.Text(), nullable=True, comment="Template description"),
        sa.Column(
            "config_path",
            sa.String(length=255),
            nullable=True,
            comment="Path to YAML configuration file",
        ),
        sa.Column(
            "custom_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Default custom configuration overrides",
        ),
        sa.Column(
            "default_description", sa.Text(), nullable=True, comment="Default session description"
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
            comment="Template tags for organization",
        ),
        sa.Column("is_public", sa.Boolean(), nullable=False, comment="Whether template is public"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Template creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last update timestamp",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("template_id"),
    )
    op.create_index("idx_session_templates_user_name", "session_templates", ["user_id", "name"])
    op.create_index("idx_session_templates_public", "session_templates", ["is_public"])
    op.create_index("idx_session_templates_created_at", "session_templates", ["created_at"])

    # Add template_id column to sessions table
    op.add_column(
        "sessions",
        sa.Column(
            "template_id",
            sa.String(length=36),
            nullable=True,
            comment="Template used to create this session",
        ),
    )
    op.create_foreign_key(
        "fk_sessions_template_id",
        "sessions",
        "session_templates",
        ["template_id"],
        ["template_id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_sessions_template", "sessions", ["template_id"])


def downgrade() -> None:
    # Drop foreign key and column from sessions table
    op.drop_constraint("fk_sessions_template_id", "sessions", type_="foreignkey")
    op.drop_index("idx_sessions_template", table_name="sessions")
    op.drop_column("sessions", "template_id")

    # Drop session_templates table
    op.drop_table("session_templates")
