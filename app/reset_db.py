#!/usr/bin/env python3

import os
import re

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load environment variables
load_dotenv()


def _parse_database_url() -> tuple[str, str, str, str, str]:
    """Parse DATABASE_URL to get connection parameters."""
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")

    # Parse postgresql://user:password@host:port/database
    match = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", DATABASE_URL)
    if not match:
        raise ValueError("Invalid DATABASE_URL format")

    user, password, host, port, database = match.groups()
    return user, password, host, port, database


def get_db_params() -> tuple[str, str, str, str, str]:
    """Get database connection parameters."""
    return _parse_database_url()


def recreate_database() -> None:
    """
    Recreate the application database.

    This function tries to drop and recreate the database.
    If the user doesn't have sufficient privileges, it will attempt to
    clear all tables instead as a fallback.
    """
    DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME = get_db_params()
    print(f"Connecting to PostgreSQL at {DB_HOST}:{DB_PORT} as user {DB_USER}")

    try:
        # Try the full database recreation first
        _drop_and_create_database(DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME)
    except psycopg2.errors.InsufficientPrivilege:
        print("Insufficient privileges to drop database. Attempting to clear all tables instead...")
        _clear_all_tables(DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME)
    except Exception as e:
        print(f"Error during database recreation: {e}")
        print("Attempting to clear all tables instead...")
        _clear_all_tables(DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME)


def _drop_and_create_database(
    DB_USER: str, DB_PASSWORD: str, DB_HOST: str, DB_PORT: str, DB_NAME: str
) -> None:
    """Drop and recreate the database (requires superuser privileges)."""
    # Connect to default postgres database
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Terminate active connections to the database
    cursor.execute(f"""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '{DB_NAME}';
    """)

    # Drop the database if it exists
    cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME};")
    print(f"Database {DB_NAME} dropped.")

    # Create the database
    cursor.execute(f"CREATE DATABASE {DB_NAME};")
    print(f"Database {DB_NAME} created.")

    cursor.close()
    conn.close()


def _clear_all_tables(
    DB_USER: str, DB_PASSWORD: str, DB_HOST: str, DB_PORT: str, DB_NAME: str
) -> None:
    """Clear all tables in the database (fallback method)."""
    # Connect to the target database
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
    """)
    tables = [row[0] for row in cursor.fetchall()]

    # Drop all tables in dependency order (handle foreign key constraints)
    # First drop tables that might be referenced by others
    for table in sorted(tables, reverse=True):
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
            print(f"Dropped table: {table}")
        except Exception as e:
            print(f"Error dropping table {table}: {e}")

    cursor.close()
    conn.close()
    print(f"All tables cleared in database {DB_NAME}")


if __name__ == "__main__":
    recreate_database()
