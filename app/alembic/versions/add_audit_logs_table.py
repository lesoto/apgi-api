"""Add audit_logs table

Revision ID: add_audit_logs_table
Revises: add_retry_config_to_webhook_deliveries
Create Date: 2025-02-27 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "add_audit_logs_table"
down_revision = "add_retry_config_to_webhook_deliveries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column(
            "audit_id",
            sa.String(36),
            primary_key=True,
            default=sa.text("gen_random_uuid()"),
            comment="Unique audit event identifier",
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.user_id"),
            nullable=True,
            index=True,
            comment="User who performed the action (null for anonymous actions)",
        ),
        sa.Column(
            "action",
            sa.String(100),
            nullable=False,
            index=True,
            comment="Action performed",
        ),
        sa.Column(
            "resource_type",
            sa.String(50),
            nullable=False,
            index=True,
            comment="Type of resource affected",
        ),
        sa.Column(
            "resource_id",
            sa.String(255),
            nullable=True,
            index=True,
            comment="ID of the affected resource",
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="When the action occurred",
        ),
        sa.Column(
            "details",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="Additional details about the action",
        ),
        sa.Column(
            "ip_address",
            sa.String(45),
            nullable=True,
            comment="Client IP address",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="Client user agent string",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            default="success",
            comment="Action outcome",
        ),
        comment="Audit log for tracking user actions and access events",
    )

    # Create indexes
    op.create_index("idx_audit_logs_user_timestamp", "audit_logs", ["user_id", "timestamp"])
    op.create_index("idx_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("idx_audit_logs_timestamp", "audit_logs", ["timestamp"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("idx_audit_logs_resource", table_name="audit_logs")
    op.drop_index("idx_audit_logs_user_timestamp", table_name="audit_logs")

    # Drop table
    op.drop_table("audit_logs")
