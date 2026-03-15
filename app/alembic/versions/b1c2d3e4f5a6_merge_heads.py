"""merge_heads

Merge the two divergent migration heads into a single linear chain:
  - 45ba6d327ae0 (add_updated_at_to_users branch)
  - add_mfa_backup_codes (add_mfa_backup_codes branch)

Revision ID: b1c2d3e4f5a6
Revises: 45ba6d327ae0, add_mfa_backup_codes
Create Date: 2026-03-15 00:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = ("45ba6d327ae0", "add_mfa_backup_codes")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This is a merge migration — no schema changes needed.
    pass


def downgrade() -> None:
    # This is a merge migration — no schema changes needed.
    pass
