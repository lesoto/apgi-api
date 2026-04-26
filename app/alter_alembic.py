#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text

from app.database.connection import engine


def alter_alembic_version() -> None:
    with engine.connect() as conn:
        # Ensure alembic_version table exists (similar to alembic env.py)
        if conn.dialect.name == "postgresql":
            import sqlalchemy as sa

            conn.execute(
                sa.text(
                    "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(255) PRIMARY KEY)"
                )
            )
            conn.execute(
                sa.text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)")
            )
            conn.commit()

        # Check if version already exists
        result = conn.execute(
            text(
                "SELECT version_num FROM alembic_version WHERE version_num = 'add_audit_logs_table'"
            )
        )
        if result.fetchone():
            print("Version 'add_audit_logs_table' already exists in alembic_version")
            return

        # Get current versions to see what we're working with
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        current_versions = [row[0] for row in result.fetchall()]

        if current_versions:
            print(f"Found existing versions: {current_versions}")
            # Delete all existing versions (there should only be one, but handle multiple)
            conn.execute(text("DELETE FROM alembic_version"))
            print("Deleted existing alembic_version entries")

        # Insert the target version
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('add_audit_logs_table')")
        )
        print("Set alembic_version to 'add_audit_logs_table'")

        conn.commit()


if __name__ == "__main__":
    alter_alembic_version()
