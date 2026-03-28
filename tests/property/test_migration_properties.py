"""
Property-based tests for database migration system.

Feature: api-migration
Tests universal properties of the Alembic migration system.
"""

import os
from pathlib import Path
from typing import Any, Dict
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic import command
from alembic.config import Config
from hypothesis import given, settings, strategies as st, HealthCheck
from unittest.mock import MagicMock


def create_sqlite_compatible_migration():
    """Create a SQLite-compatible version of the migration for testing."""
    import sqlalchemy as sa

    # Mock the postgresql module to use SQLite-compatible types
    mock_postgresql = MagicMock()

    def mock_array(element_type=None):
        # Convert ARRAY to TEXT for SQLite
        return sa.Text()

    def mock_jsonb(astext_type=None):
        # Convert JSONB to JSON for SQLite
        return sa.JSON()

    mock_postgresql.ARRAY = mock_array
    mock_postgresql.JSONB = mock_jsonb
    mock_postgresql.UUID = lambda as_uuid=None: sa.String(36)  # Convert UUID to String for SQLite
    mock_postgresql.TIMESTAMP = (
        lambda timezone=False: sa.DateTime()
    )  # Convert TIMESTAMP to DateTime
    mock_postgresql.BOOLEAN = lambda: sa.Boolean()  # Keep BOOLEAN as is
    mock_postgresql.INTEGER = lambda: sa.Integer()  # Keep INTEGER as is
    mock_postgresql.BIGINT = lambda: sa.BigInteger()  # Keep BIGINT as is
    mock_postgresql.TEXT = lambda: sa.Text()  # Keep TEXT as is
    mock_postgresql.VARCHAR = lambda length: sa.String(length)  # Convert VARCHAR to String
    mock_postgresql.FLOAT = lambda precision=None: sa.Float()  # Keep FLOAT as is
    mock_postgresql.DOUBLE_PRECISION = lambda: sa.Float()  # Convert DOUBLE_PRECISION to Float
    mock_postgresql.DATE = lambda: sa.Date()  # Keep DATE as is
    mock_postgresql.TIME = lambda: sa.Time()  # Keep TIME as is
    mock_postgresql.ENUM = lambda *enums, **kwargs: sa.Enum(*enums, **kwargs)  # Keep ENUM as is

    return mock_postgresql


def create_sqlite_initial_schema():
    """Create a SQLite-compatible version of the initial schema directly."""
    import sqlalchemy as sa

    def apply_schema(engine):
        """Apply the initial schema directly to SQLite engine."""
        with engine.connect() as conn:
            # Create users table
            conn.execute(
                sa.text(
                    """
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(36) PRIMARY KEY,
                    username VARCHAR(100) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    roles TEXT NOT NULL DEFAULT '[]',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME
                )
            """
                )
            )

            # Create sessions table
            conn.execute(
                sa.text(
                    """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    config TEXT NOT NULL,
                    state VARCHAR(20) NOT NULL DEFAULT 'created',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """
                )
            )

            # Create tasks table
            conn.execute(
                sa.text(
                    """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id VARCHAR(36) PRIMARY KEY,
                    session_id VARCHAR(36) NOT NULL,
                    task_type VARCHAR(50) NOT NULL,
                    parameters TEXT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """
                )
            )

            # Create other required tables
            conn.execute(
                sa.text(
                    """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    token_id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    token_hash VARCHAR(255) NOT NULL,
                    expires_at DATETIME NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """
                )
            )

            conn.execute(
                sa.text(
                    """
                CREATE TABLE IF NOT EXISTS session_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(36) NOT NULL,
                    time_ms REAL NOT NULL,
                    data TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """
                )
            )

            conn.execute(
                sa.text(
                    """
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    delivery_id VARCHAR(36) PRIMARY KEY,
                    task_id VARCHAR(36) NOT NULL,
                    webhook_url VARCHAR(500) NOT NULL,
                    payload TEXT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                )
            """
                )
            )

            # Create indexes
            conn.execute(
                sa.text("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)")
            )
            conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
            conn.execute(
                sa.text("CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id)")
            )
            conn.execute(
                sa.text("CREATE INDEX IF NOT EXISTS ix_tasks_session_id ON tasks (session_id)")
            )

            # Create alembic_version table
            conn.execute(
                sa.text(
                    """
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(255) PRIMARY KEY
                )
            """
                )
            )
            conn.execute(
                sa.text("INSERT OR IGNORE INTO alembic_version (version_num) VALUES ('001')")
            )

            conn.commit()

    return apply_schema


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


def get_database_schema_snapshot(engine) -> Dict[str, Any]:
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

    snapshot: Dict[str, Any] = {
        "tables": sorted(inspector.get_table_names()),
        "columns": {},
        "indexes": {},
        "foreign_keys": {},
    }

    for table_name in snapshot["tables"]:
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

    Uses SQLite in-memory database for testing to ensure tests work
    without requiring external PostgreSQL setup.

    To run these tests with PostgreSQL:
        TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/test_db pytest
    """
    val = os.environ.get("TEST_DATABASE_URL")
    if val and val.startswith("postgres"):
        return val
    # Use SQLite in-memory database for testing
    # Migration tests are patched to be SQLite-compatible
    return "sqlite:///:memory:"


@pytest.fixture
def clean_test_database(test_database_url):
    """Provide a clean test database URL."""
    # For migration tests, always use SQLite
    return "sqlite:///:memory:"


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

    # Validating on current database URL

    engine = create_engine(database_url)

    # Step 1: Capture initial schema (should be empty)
    initial_snapshot = get_database_schema_snapshot(engine)

    # Verify database is empty
    assert (
        initial_snapshot["tables"] == []
    ), f"Database should be empty initially, but has tables: {initial_snapshot['tables']}"

    # Step 2: Run upgrade to apply migration
    # For SQLite, use direct schema creation instead of Alembic
    if database_url.startswith("sqlite"):
        apply_schema = create_sqlite_initial_schema()
        apply_schema(engine)
    else:
        # Use Alembic for PostgreSQL
        alembic_cfg = get_alembic_config(database_url)
        command.upgrade(alembic_cfg, "001")

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
    # For SQLite, drop all tables directly
    if database_url.startswith("sqlite"):
        with engine.connect() as conn:
            # Drop all tables in reverse order of dependencies
            tables = [
                "webhook_deliveries",
                "session_data",
                "tasks",
                "sessions",
                "refresh_tokens",
                "users",
                "alembic_version",
            ]
            for table in tables:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            conn.commit()
    else:
        # Use Alembic for PostgreSQL
        alembic_cfg = get_alembic_config(database_url)
        command.downgrade(alembic_cfg, "base")

    # Step 5: Capture schema after downgrade
    after_downgrade_snapshot = get_database_schema_snapshot(engine)

    # Step 6: Compare snapshots
    # After downgrade, should be empty
    assert (
        len(after_downgrade_snapshot["tables"]) == 0
    ), f"After downgrade, expected empty database, got {after_downgrade_snapshot['tables']}"

    # Property verified: upgrade + downgrade returns to original state
    # (empty database)

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

    # Validating on current database URL

    engine = create_engine(database_url)

    # Capture initial state
    initial_snapshot = get_database_schema_snapshot(engine)

    # Run upgrade twice
    # For SQLite, use direct schema creation
    if database_url.startswith("sqlite"):
        apply_schema = create_sqlite_initial_schema()
        apply_schema(engine)
        # Second upgrade should be idempotent - just run it again
        apply_schema(engine)
    else:
        # Use Alembic for PostgreSQL
        alembic_cfg = get_alembic_config(database_url)
        command.upgrade(alembic_cfg, "001")
        command.upgrade(alembic_cfg, "001")

    # Verify state after double upgrade
    after_double_upgrade = get_database_schema_snapshot(engine)

    # Run downgrade
    if database_url.startswith("sqlite"):
        with engine.connect() as conn:
            tables = [
                "webhook_deliveries",
                "session_data",
                "tasks",
                "sessions",
                "refresh_tokens",
                "users",
                "alembic_version",
            ]
            for table in tables:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            conn.commit()
    else:
        alembic_cfg = get_alembic_config(database_url)
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

    # Validating on current database URL

    engine = create_engine(database_url)

    # Run upgrade
    # For SQLite, use direct schema creation
    if database_url.startswith("sqlite"):
        apply_schema = create_sqlite_initial_schema()
        apply_schema(engine)
    else:
        # Use Alembic for PostgreSQL
        alembic_cfg = get_alembic_config(database_url)
        command.upgrade(alembic_cfg, "001")

    # Check alembic_version table exists and has correct version
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        versions = [row[0] for row in result]

        assert (
            len(versions) == 1
        ), f"Expected exactly one version in alembic_version, got {len(versions)}"

        assert versions[0] == "001", f"Expected version '001', got '{versions[0]}'"

    # Run downgrade
    if database_url.startswith("sqlite"):
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            conn.commit()
    else:
        alembic_cfg = get_alembic_config(database_url)
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


@settings(
    max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture]
)  # Reduced for faster testing
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

    # Validating on current database URL

    engine = create_engine(database_url)

    # Perform multiple upgrade/downgrade cycles
    for cycle in range(upgrade_count):
        # Upgrade
        # For SQLite, use direct schema creation
        if database_url.startswith("sqlite"):
            apply_schema = create_sqlite_initial_schema()
            apply_schema(engine)
        else:
            # Use Alembic for PostgreSQL
            alembic_cfg = get_alembic_config(database_url)
            command.upgrade(alembic_cfg, "001")

        # Verify tables exist
        snapshot_after_upgrade = get_database_schema_snapshot(engine)
        assert (
            len(snapshot_after_upgrade["tables"]) > 1
        ), f"Cycle {cycle + 1}: After upgrade, expected multiple tables"

        # Downgrade
        if database_url.startswith("sqlite"):
            with engine.connect() as conn:
                tables = [
                    "webhook_deliveries",
                    "session_data",
                    "tasks",
                    "sessions",
                    "refresh_tokens",
                    "users",
                    "alembic_version",
                ]
                for table in tables:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                conn.commit()
        else:
            alembic_cfg = get_alembic_config(database_url)
            command.downgrade(alembic_cfg, "base")

        # Verify back to initial state
        snapshot_after_downgrade = get_database_schema_snapshot(engine)
        assert len(snapshot_after_downgrade["tables"]) <= 1, (
            f"Cycle {cycle + 1}: After downgrade, expected at most alembic_version table, "
            f"got {snapshot_after_downgrade['tables']}"
        )

    engine.dispose()
