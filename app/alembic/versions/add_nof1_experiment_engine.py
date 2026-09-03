"""Add n-of-1 experiment engine tables (Phase 5).

Revision ID: add_nof1_experiment_engine
Revises: add_research_pilot_domain
Create Date: 2026-09-03 00:00:01.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_nof1_experiment_engine"
down_revision = "add_research_pilot_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = postgresql.JSONB() if is_postgres else sa.JSON()
    uuid_default = sa.text("gen_random_uuid()") if is_postgres else None

    op.create_table(
        "nof1_experiments",
        sa.Column("experiment_id", sa.String(36), primary_key=True, default=uuid_default),
        sa.Column(
            "participant_id",
            sa.String(36),
            sa.ForeignKey("participants.participant_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "study_id",
            sa.String(36),
            sa.ForeignKey("studies.study_id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phase_sequence", json_type, nullable=False),
        sa.Column("outcome_metric_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        comment="Single-subject alternating-phase experiments",
    )

    op.create_table(
        "nof1_observations",
        sa.Column("observation_id", sa.String(36), primary_key=True, default=uuid_default),
        sa.Column(
            "experiment_id",
            sa.String(36),
            sa.ForeignKey("nof1_experiments.experiment_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("phase_label", sa.String(20), nullable=False, index=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "experiment_id", "sequence_index", name="uq_nof1_observations_experiment_sequence"
        ),
        comment="Recorded outcome values within an n-of-1 experiment",
    )


def downgrade() -> None:
    op.drop_table("nof1_observations")
    op.drop_table("nof1_experiments")
