"""Add task dependencies and priority

Revision ID: 9af3534145e0
Revises: 50e7513df3b0
Create Date: 2026-02-18 20:21:47.136786

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9af3534145e0"
down_revision = "50e7513df3b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add priority column to tasks table
    op.add_column(
        "tasks",
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            default=5,
            comment="Task priority (1=highest, 10=lowest)",
        ),
    )

    # Create task_dependencies table
    op.create_table(
        "task_dependencies",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            comment="Auto-incrementing primary key",
        ),
        sa.Column(
            "dependent_task_id",
            sa.String(length=36),
            nullable=False,
            comment="Task that depends on the prerequisite",
        ),
        sa.Column(
            "prerequisite_task_id",
            sa.String(length=36),
            nullable=False,
            comment="Task that must complete before the dependent task",
        ),
        sa.Column(
            "dependency_type",
            sa.String(length=20),
            nullable=False,
            default="completion",
            comment="Type of dependency (completion, success, failure)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Dependency creation timestamp",
        ),
        sa.ForeignKeyConstraint(["dependent_task_id"], ["tasks.task_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prerequisite_task_id"], ["tasks.task_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_task_dependencies_dependent", "task_dependencies", ["dependent_task_id"])
    op.create_index(
        "idx_task_dependencies_prerequisite", "task_dependencies", ["prerequisite_task_id"]
    )
    op.create_index(
        "idx_task_dependencies_unique",
        "task_dependencies",
        ["dependent_task_id", "prerequisite_task_id"],
        unique=True,
    )
    op.create_index("idx_tasks_priority", "tasks", ["priority"])


def downgrade() -> None:
    # Drop task_dependencies table
    op.drop_table("task_dependencies")

    # Drop priority column from tasks table
    op.drop_column("tasks", "priority")
