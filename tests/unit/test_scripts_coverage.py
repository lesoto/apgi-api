"""
Coverage tests for standalone scripts in app/
"""

from unittest.mock import MagicMock, patch

import psycopg2


def test_create_db_script():
    """Test create_db.py script."""
    from app.create_db import create_database

    with patch("app.create_db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Test success path
        create_database()
        assert mock_connect.called

    # Test DuplicateDatabase path - need fresh mock
    with patch("app.create_db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.errors.DuplicateDatabase("error")
        # Should not raise
        create_database()
        assert mock_connect.called

    # Test generic exception - need fresh mock
    with patch("app.create_db.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("General error")
        # Should not raise
        create_database()
        assert mock_connect.called


def test_alter_alembic_script():
    """Test alter_alembic.py script."""
    from app.alter_alembic import alter_alembic_version

    with patch("app.alter_alembic.engine.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.dialect.name = "postgresql"

        # Mock fetchone to return None first (version doesn't exist)
        mock_conn.execute.return_value.fetchone.return_value = None
        # Mock fetchall for current versions
        mock_conn.execute.return_value.fetchall.return_value = [("old_version",)]

        alter_alembic_version()
        assert mock_conn.execute.called


def test_create_demo_user_script():
    """Test create_demo_user.py script."""
    from app.create_demo_user import create_demo_user

    with patch("app.create_demo_user.SessionLocal") as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock User search to return None (user doesn't exist)
        mock_session.query.return_value.filter.return_value.first.return_value = None

        create_demo_user()
        assert mock_session.add.called
        assert mock_session.commit.called
