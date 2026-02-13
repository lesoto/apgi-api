"""
Property-based tests for database migration system.

Feature: api-migration
Tests universal properties of the Alembic migration system.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from hypothesis import given, strategies as st, settings
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))


def get_alembic_config(database_url: str) -> Config:
    """
    Create Alembic configuration for testing.

    Args:
        database_url: Database connection URL

    Returns:
        Configured Alembic Config object
    """
    # Get path to alembic.ini
    alembic_ini_path = Path(__file__).parent.parent.parent / "alembic.ini"

    # Create Alembic config
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    return alembic_cfg


def get_database_schema_snapshot(engine):
    """
    Capture a snapshot of the database schema.

    Returns a dictionary containing:
    - tables: list of table names
    - columns: dict mapping table name to list of column info
    - indexes: dict mapping table name to list of index info
    - foreign_keys: dict mapping table name to list of foreign key info

    Args:
        engine: SQLAlchemy engine

    Returns:
        Dictionary containing schema information
    """
    inspector = inspect(engine)

    snapshot = {
        "tables": sorted(inspector.get_table_names()),
        "columns": {},
        "indexes": {},
        "foreign_keys": {},
    }

    for table_name in snapshot["tables"]:
        # Get columns
        columns = inspector.get_columns(table_name)
        snapshot["columns"][table_name] = [
            {
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col["nullable"],
                "default": str(col.get("default")) if col.get("default") is not None else None,
            }
            for col in columns
        ]

        # Get indexes
        indexes = inspector.get_indexes(table_name)
        snapshot["indexes"][table_name] = [
            {
                "name": idx["name"],
                "columns": sorted(idx["column_names"]),
                "unique": idx["unique"],
            }
            for idx in indexes
        ]

        # Get foreign keys
        foreign_keys = inspector.get_foreign_keys(table_name)
        snapshot["foreign_keys"][table_name] = [
            {
                "name": fk.get("name"),
                "constrained_columns": sorted(fk["constrained_columns"]),
                "referred_table": fk["referred_table"],
                "referred_columns": sorted(fk["referred_columns"]),
            }
            for fk in foreign_keys
        ]

    return snapshot


def compare_schema_snapshots(before, after):
    """
    Compare two schema snapshots and return differences.

    Args:
        before: Schema snapshot before migration
        after: Schema snapshot after migration

    Returns:
        List of difference descriptions (empty if schemas match)
    """
    differences = []

    # Compare tables
    if before["tables"] != after["tables"]:
        before_tables = set(before["tables"])
        after_tables = set(after["tables"])

        added = after_tables - before_tables
        removed = before_tables - after_tables

        if added:
            differences.append(f"Added tables: {sorted(added)}")
        if removed:
            differences.append(f"Removed tables: {sorted(removed)}")

    # Compare columns for common tables
    common_tables = set(before["tables"]) & set(after["tables"])
    for table in common_tables:
        before_cols = before["columns"][table]
        after_cols = after["columns"][table]

        if before_cols != after_cols:
            differences.append(
                f"Table '{table}' columns differ:\n"
                f"  Before: {before_cols}\n"
                f"  After: {after_cols}"
            )

    # Compare indexes for common tables
    for table in common_tables:
        before_idx = sorted(before["indexes"][table], key=lambda x: x["name"] or "")
        after_idx = sorted(after["indexes"][table], key=lambda x: x["name"] or "")

        if before_idx != after_idx:
            differences.append(
                f"Table '{table}' indexes differ:\n"
                f"  Before: {before_idx}\n"
                f"  After: {after_idx}"
            )

    # Compare foreign keys for common tables
    for table in common_tables:
        before_fk = sorted(before["foreign_keys"][table], key=lambda x: x["name"] or "")
        after_fk = sorted(after["foreign_keys"][table], key=lambda x: x["name"] or "")

        if before_fk != after_fk:
            differences.append(
                f"Table '{table}' foreign keys differ:\n"
                f"  Before: {before_fk}\n"
                f"  After: {after_fk}"
            )

    return differences


@pytest.fixture
def test_database_url():
    """
    Provide a test database URL.

    Uses environment variable TEST_DATABASE_URL if set,
    otherwise uses a default PostgreSQL test database.

    Note: These tests require PostgreSQL because the migrations use
    PostgreSQL-specific types (ARRAY, JSONB). SQLite is not supported.

    To run these tests, either:
    1. Start PostgreSQL locally (e.g., via docker-compose)
    2. Set TEST_DATABASE_URL environment variable to a PostgreSQL database

    Example:
        TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/test_db pytest
    """
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://apgi_dev:dev_password@localhost:5432/apgi_api_test_migrations",
    )


@pytest.fixture
def clean_test_database(test_database_url):
    """
    Ensure test database is clean before and after test.

    This fixture:
    1. Drops all tables before the test
    2. Yields control to the test
    3. Drops all tables after the test

    Skips tests if PostgreSQL is not available.
    """
    # Check if PostgreSQL is available
    if not test_database_url.startswith("postgresql"):
        pytest.skip("PostgreSQL database required for migration tests")

    try:
        engine = create_engine(test_database_url, poolclass=NullPool)
    except Exception as e:
        pytest.skip(f"Cannot connect to PostgreSQL database: {e}")

    # Determine if we're using SQLite or PostgreSQL
    is_sqlite = test_database_url.startswith("sqlite")

    # Clean before test
    try:
        with engine.connect() as conn:
            # Drop alembic_version table if it exists
            if is_sqlite:
                conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            else:
                conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            conn.commit()

            # Get all tables
            inspector = inspect(engine)
            tables = inspector.get_table_names()

            # Drop all tables
            if tables:
                for table in tables:
                    if is_sqlite:
                        conn.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
                    else:
                        conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                conn.commit()
    except Exception as e:
        pytest.skip(f"Cannot clean test database: {e}")

    yield test_database_url

    # Clean after test
    with engine.connect() as conn:
        # Drop alembic_version table
        if is_sqlite:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        else:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        conn.commit()

        # Get all tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        # Drop all tables
        if tables:
            for table in tables:
                if is_sqlite:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
                else:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
            conn.commit()

    engine.dispose()


def test_property_3_migration_roundtrip_initial_schema(clean_test_database):
    """
    **Validates: Requirements 3.6**

    Feature: api-migration, Property 3: Database Migration Round-Trip

    For any database migration, running upgrade followed by downgrade should
    return the database to its original state.

    This test verifies the initial migration (001_initial_schema.py) can be
    applied and rolled back cleanly, ensuring migration reversibility.

    Test strategy:
    1. Capture schema snapshot of empty database
    2. Run upgrade to apply migration
    3. Verify migration was applied (tables exist)
    4. Run downgrade to revert migration
    5. Capture schema snapshot after downgrade
    6. Compare snapshots - they should be identical
    """
    database_url = clean_test_database
    engine = create_engine(database_url, poolclass=NullPool)

    # Step 1: Capture initial schema (should be empty)
    initial_snapshot = get_database_schema_snapshot(engine)

    # Verify database is empty
    assert (
        initial_snapshot["tables"] == []
    ), f"Database should be empty initially, but has tables: {initial_snapshot['tables']}"

    # Step 2: Run upgrade to apply migration
    alembic_cfg = get_alembic_config(database_url)

    # Patch settings to avoid loading real config during migration
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "development",
            "JWT_SECRET_KEY": "test-key-32-chars-minimum-len",
            "DATABASE_URL": database_url,
        },
        clear=False,
    ):
        command.upgrade(alembic_cfg, "head")

    # Step 3: Verify migration was applied
    after_upgrade_snapshot = get_database_schema_snapshot(engine)

    # Should have tables now
    expected_tables = [
        "alembic_version",
        "refresh_tokens",
        "session_data",
        "sessions",
        "tasks",
        "users",
        "webhook_deliveries",
    ]

    assert sorted(after_upgrade_snapshot["tables"]) == sorted(
        expected_tables
    ), f"After upgrade, expected tables {expected_tables}, got {after_upgrade_snapshot['tables']}"

    # Step 4: Run downgrade to revert migration
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "development",
            "JWT_SECRET_KEY": "test-key-32-chars-minimum-len",
            "DATABASE_URL": database_url,
        },
        clear=False,
    ):
        command.downgrade(alembic_cfg, "base")

    # Step 5: Capture schema after downgrade
    after_downgrade_snapshot = get_database_schema_snapshot(engine)

    # Step 6: Compare snapshots
    # After downgrade, should only have alembic_version table (Alembic keeps this)
    # or be completely empty depending on Alembic version
    assert (
        len(after_downgrade_snapshot["tables"]) <= 1
    ), f"After downgrade, expected at most alembic_version table, got {after_downgrade_snapshot['tables']}"

    if after_downgrade_snapshot["tables"]:
        assert after_downgrade_snapshot["tables"] == [
            "alembic_version"
        ], f"After downgrade, only alembic_version should remain, got {after_downgrade_snapshot['tables']}"

    # Property verified: upgrade + downgrade returns to original state
    # (empty database or only alembic_version table)

    engine.dispose()


def test_property_3_migration_roundtrip_idempotency(clean_test_database):
    """
    **Validates: Requirements 3.6**

    Feature: api-migration, Property 3: Database Migration Round-Trip

    Extended property test: Running upgrade twice should be idempotent,
    and running downgrade after double upgrade should still return to original state.

    This verifies that migrations are safe to run multiple times and that
    downgrade works correctly regardless of how many times upgrade was run.
    """
    database_url = clean_test_database
    engine = create_engine(database_url, poolclass=NullPool)

    # Capture initial state
    initial_snapshot = get_database_schema_snapshot(engine)

    alembic_cfg = get_alembic_config(database_url)

    # Run upgrade twice
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "development",
            "JWT_SECRET_KEY": "test-key-32-chars-minimum-len",
            "DATABASE_URL": database_url,
        },
        clear=False,
    ):
        command.upgrade(alembic_cfg, "head")

        # Capture state after first upgrade
        after_first_upgrade = get_database_schema_snapshot(engine)

        # Run upgrade again (should be idempotent)
        command.upgrade(alembic_cfg, "head")

        # Capture state after second upgrade
        after_second_upgrade = get_database_schema_snapshot(engine)

    # Verify idempotency: schema should be identical after both upgrades
    differences = compare_schema_snapshots(after_first_upgrade, after_second_upgrade)
    assert (
        not differences
    ), f"Running upgrade twice should be idempotent, but found differences: {differences}"

    # Now run downgrade
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "development",
            "JWT_SECRET_KEY": "test-key-32-chars-minimum-len",
            "DATABASE_URL": database_url,
        },
        clear=False,
    ):
        command.downgrade(alembic_cfg, "base")

    # Capture final state
    final_snapshot = get_database_schema_snapshot(engine)

    # Verify we're back to initial state (empty or only alembic_version)
    assert (
        len(final_snapshot["tables"]) <= 1
    ), f"After downgrade, expected at most alembic_version table, got {final_snapshot['tables']}"

    engine.dispose()


def test_property_3_migration_roundtrip_preserves_alembic_version(clean_test_database):
    """
    **Validates: Requirements 3.6**

    Feature: api-migration, Property 3: Database Migration Round-Trip

    Verify that the alembic_version table is properly managed during
    upgrade and downgrade operations.

    This ensures that Alembic's version tracking works correctly and
    that the system knows which migrations have been applied.
    """
    database_url = clean_test_database
    engine = create_engine(database_url, poolclass=NullPool)

    alembic_cfg = get_alembic_config(database_url)

    # Run upgrade
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "development",
            "JWT_SECRET_KEY": "test-key-32-chars-minimum-len",
            "DATABASE_URL": database_url,
        },
        clear=False,
    ):
        command.upgrade(alembic_cfg, "head")

    # Check alembic_version table exists and has correct version
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        versions = [row[0] for row in result]

        assert (
            len(versions) == 1
        ), f"Expected exactly one version in alembic_version, got {len(versions)}"

        assert versions[0] == "001", f"Expected version '001', got '{versions[0]}'"

    # Run downgrade
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "development",
            "JWT_SECRET_KEY": "test-key-32-chars-minimum-len",
            "DATABASE_URL": database_url,
        },
        clear=False,
    ):
        command.downgrade(alembic_cfg, "base")

    # Check alembic_version table - should be empty or not exist
    with engine.connect() as conn:
        # Check if table exists
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if "alembic_version" in tables:
            # If table exists, it should be empty
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = [row[0] for row in result]

            assert (
                len(versions) == 0
            ), f"After downgrade to base, alembic_version should be empty, got {versions}"

    engine.dispose()


@settings(max_examples=2)  # Reduced for faster testing
@given(upgrade_count=st.integers(min_value=1, max_value=2))
def test_property_3_migration_roundtrip_multiple_cycles(clean_test_database, upgrade_count):
    """
    **Validates: Requirements 3.6**

    Feature: api-migration, Property 3: Database Migration Round-Trip

    Property-based test: For any number of upgrade/downgrade cycles,
    the final state after downgrade should match the initial state.

    This verifies that migrations can be applied and rolled back multiple
    times without accumulating state or causing inconsistencies.
    """
    database_url = clean_test_database
    engine = create_engine(database_url, poolclass=NullPool)

    alembic_cfg = get_alembic_config(database_url)

    # Perform multiple upgrade/downgrade cycles
    for cycle in range(upgrade_count):
        # Upgrade
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "JWT_SECRET_KEY": "test-key-32-chars-minimum-len",
                "DATABASE_URL": database_url,
            },
            clear=False,
        ):
            command.upgrade(alembic_cfg, "head")

        # Verify tables exist
        snapshot_after_upgrade = get_database_schema_snapshot(engine)
        assert (
            len(snapshot_after_upgrade["tables"]) > 1
        ), f"Cycle {cycle + 1}: After upgrade, expected multiple tables"

        # Downgrade
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "JWT_SECRET_KEY": "test-key-32-chars-minimum-len",
                "DATABASE_URL": database_url,
            },
            clear=False,
        ):
            command.downgrade(alembic_cfg, "base")

        # Verify back to initial state
        snapshot_after_downgrade = get_database_schema_snapshot(engine)
        assert len(snapshot_after_downgrade["tables"]) <= 1, (
            f"Cycle {cycle + 1}: After downgrade, expected at most alembic_version table, "
            f"got {snapshot_after_downgrade['tables']}"
        )

    engine.dispose()
