"""Add unique constraint on (user_id, name) for session_templates

Revision ID: add_unique_constraint_user_name_session_templates
Revises: add_key_prefix_to_api_keys
Create Date: 2025-02-27 09:33:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_unique_constraint_user_name_session_templates"
down_revision = "add_key_prefix_to_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint on (user_id, name) for session_templates table
    op.create_unique_constraint(
        "uq_session_templates_user_name",
        "session_templates",
        ["user_id", "name"],
    )


def downgrade() -> None:
    # Remove unique constraint on (user_id, name) for session_templates table
    op.drop_constraint(
        "uq_session_templates_user_name",
        "session_templates",
        type_="unique",
    )
