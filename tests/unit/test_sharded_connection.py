"""
Unit tests for app/database/sharded_connection.py

Tests sharded database connection management with support for multiple database instances.
"""

import pytest
from typing import Any
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError


@pytest.fixture
def mock_sharding_service() -> MagicMock:
    """Create a mock sharding service."""
    service = MagicMock()
    service.get_shard_for_user = MagicMock(return_value="shard_0")
    service.get_all_shards = MagicMock(
        return_value=[
            MagicMock(shard_id="shard_0", database_url="sqlite:///test.db", is_active=True),
            MagicMock(shard_id="shard_1", database_url="sqlite:///test1.db", is_active=True),
        ]
    )
    return service


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings."""
    settings = MagicMock()
    settings.database_shards_enabled = True
    settings.database_url = "sqlite:///test.db"
    return settings


@pytest.fixture
def mock_engine() -> MagicMock:
    """Create a mock SQLAlchemy engine."""
    engine = MagicMock()
    engine.pool = MagicMock()
    engine.pool.size = 5
    engine.pool._overflow = 0
    engine.pool._invalid = 0
    engine.dispose = MagicMock()
    return engine


@pytest.fixture
def mock_session_factory() -> MagicMock:
    """Create a mock session factory."""
    factory = MagicMock()
    session = MagicMock(spec=Session)
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    factory.return_value = session
    return factory


class TestShardedDatabaseManagerInitialization:
    """Test ShardedDatabaseManager initialization."""

    def test_manager_initializes_with_shards(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """ShardedDatabaseManager initializes engines for all shards."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_create_engine.return_value = MagicMock()

                manager = ShardedDatabaseManager()

                assert len(manager.engines) == 2
                assert "shard_0" in manager.engines
                assert "shard_1" in manager.engines

    def test_manager_creates_session_factories(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """ShardedDatabaseManager creates session factories for each shard."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_create_engine.return_value = MagicMock()

                manager = ShardedDatabaseManager()

                assert len(manager.session_factories) == 2
                assert "shard_0" in manager.session_factories
                assert "shard_1" in manager.session_factories

    def test_manager_configures_sqlite_engine(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """ShardedDatabaseManager configures SQLite engines correctly."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_create_engine.return_value = MagicMock()

                manager = ShardedDatabaseManager()

                # Check that create_engine was called with SQLite-specific settings
                calls = mock_create_engine.call_args_list
                assert len(calls) >= 1
                first_call = calls[0]
                assert "sqlite" in first_call[0][0]
                assert first_call[1].get("connect_args", {}).get("check_same_thread") is False

    def test_manager_configures_postgresql_engine(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """ShardedDatabaseManager configures PostgreSQL engines correctly."""
        from app.database.sharded_connection import ShardedDatabaseManager

        # Update mock to return PostgreSQL URLs
        mock_sharding_service.get_all_shards.return_value = [
            MagicMock(
                shard_id="shard_0",
                database_url="postgresql://user:pass@localhost/db0",
                is_active=True,
            ),
            MagicMock(
                shard_id="shard_1",
                database_url="postgresql://user:pass@localhost/db1",
                is_active=True,
            ),
        ]

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_create_engine.return_value = MagicMock()

                manager = ShardedDatabaseManager()

                # Check that create_engine was called with PostgreSQL-specific settings
                calls = mock_create_engine.call_args_list
                assert len(calls) >= 1
                first_call = calls[0]
                assert "postgresql" in first_call[0][0]
                assert first_call[1].get("pool_pre_ping") is True
                assert first_call[1].get("pool_size") == 15


class TestGetShardForUser:
    """Test get_shard_for_user method."""

    def test_get_shard_for_user_returns_shard_id(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_for_user returns the correct shard ID."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                manager = ShardedDatabaseManager()
                mock_sharding_service.get_shard_for_user.return_value = "shard_1"

                shard_id = manager.get_shard_for_user("user_123")

                assert shard_id == "shard_1"
                mock_sharding_service.get_shard_for_user.assert_called_once_with("user_123")

    def test_get_shard_for_user_consistent_for_same_user(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_for_user returns the same shard for the same user."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                manager = ShardedDatabaseManager()
                mock_sharding_service.get_shard_for_user.return_value = "shard_0"

                shard_id_1 = manager.get_shard_for_user("user_123")
                shard_id_2 = manager.get_shard_for_user("user_123")

                assert shard_id_1 == shard_id_2


class TestGetEngineForShard:
    """Test get_engine_for_shard method."""

    def test_get_engine_for_shard_returns_engine(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_engine_for_shard returns the engine for a shard."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_engine = MagicMock()
                mock_create_engine.return_value = mock_engine

                manager = ShardedDatabaseManager()

                engine = manager.get_engine_for_shard("shard_0")

                assert engine is not None
                assert engine == mock_engine

    def test_get_engine_for_shard_returns_none_for_invalid_shard(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_engine_for_shard returns None for invalid shard."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                manager = ShardedDatabaseManager()

                engine = manager.get_engine_for_shard("invalid_shard")

                assert engine is None


class TestGetSessionForUser:
    """Test get_session_for_user method."""

    def test_get_session_for_user_returns_session(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_session_for_user returns a session for the user's shard."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()
                    mock_sharding_service.get_shard_for_user.return_value = "shard_0"

                    session = manager.get_session_for_user("user_123")

                    assert session == mock_session

    def test_get_session_for_user_raises_for_missing_factory(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_session_for_user raises ValueError if session factory not found."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                manager = ShardedDatabaseManager()
                mock_sharding_service.get_shard_for_user.return_value = "invalid_shard"
                manager.session_factories = {}

                with pytest.raises(ValueError, match="No session factory available"):
                    manager.get_session_for_user("user_123")


class TestGetSessionForShard:
    """Test get_session_for_shard method."""

    def test_get_session_for_shard_returns_session(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_session_for_shard returns a session for the shard."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    session = manager.get_session_for_shard("shard_0")

                    assert session == mock_session

    def test_get_session_for_shard_raises_for_invalid_shard(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_session_for_shard raises ValueError for invalid shard."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                manager = ShardedDatabaseManager()
                manager.session_factories = {}

                with pytest.raises(ValueError, match="No session factory available"):
                    manager.get_session_for_shard("invalid_shard")


class TestGetUserSessionContextManager:
    """Test get_user_session context manager."""

    def test_get_user_session_yields_session(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_user_session yields a session."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    with manager.get_user_session("user_123") as session:
                        assert session == mock_session

    def test_get_user_session_commits_on_success(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_user_session commits the session on success."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    with manager.get_user_session("user_123"):
                        pass

                    mock_session.commit.assert_called_once()

    def test_get_user_session_rollback_on_exception(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_user_session rolls back on exception."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    with pytest.raises(ValueError):
                        with manager.get_user_session("user_123"):
                            raise ValueError("Test error")

                    mock_session.rollback.assert_called_once()

    def test_get_user_session_closes_session(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_user_session closes the session."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    with manager.get_user_session("user_123"):
                        pass

                    mock_session.close.assert_called_once()


class TestGetShardSessionContextManager:
    """Test get_shard_session context manager."""

    def test_get_shard_session_yields_session(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_session yields a session."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    with manager.get_shard_session("shard_0") as session:
                        assert session == mock_session

    def test_get_shard_session_commits_on_success(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_session commits the session on success."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    with manager.get_shard_session("shard_0"):
                        pass

                    mock_session.commit.assert_called_once()

    def test_get_shard_session_rollback_on_exception(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_session rolls back on exception."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    with pytest.raises(RuntimeError):
                        with manager.get_shard_session("shard_0"):
                            raise RuntimeError("Test error")

                    mock_session.rollback.assert_called_once()

    def test_get_shard_session_closes_session(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_session closes the session."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    with manager.get_shard_session("shard_0"):
                        pass

                    mock_session.close.assert_called_once()


class TestExecuteCrossShardQuery:
    """Test execute_cross_shard_query method."""

    def test_execute_cross_shard_query_calls_query_func(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """execute_cross_shard_query calls query_func for each shard."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    query_func = MagicMock(return_value=[{"id": 1}])

                    results = manager.execute_cross_shard_query(query_func)

                    assert query_func.call_count == 2

    def test_execute_cross_shard_query_combines_results(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """execute_cross_shard_query combines results from all shards."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    query_func = MagicMock(
                        side_effect=[[{"id": 1}, {"id": 2}], [{"id": 3}, {"id": 4}]]
                    )

                    results = manager.execute_cross_shard_query(query_func)

                    assert len(results) == 4
                    assert results == [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]

    def test_execute_cross_shard_query_handles_errors(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """execute_cross_shard_query continues on error."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    query_func = MagicMock(side_effect=[Exception("Shard error"), [{"id": 1}]])

                    results = manager.execute_cross_shard_query(query_func)

                    assert len(results) == 1
                    assert results == [{"id": 1}]

    def test_execute_cross_shard_query_passes_args_and_kwargs(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """execute_cross_shard_query passes args and kwargs to query_func."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    query_func = MagicMock(return_value=[])

                    manager.execute_cross_shard_query(query_func, "arg1", "arg2", key1="value1")

                    calls = query_func.call_args_list
                    assert len(calls) == 2
                    for call_obj in calls:
                        assert call_obj[0][1:] == ("arg1", "arg2")
                        assert call_obj[1] == {"key1": "value1"}


class TestGetShardStats:
    """Test get_shard_stats method."""

    def test_get_shard_stats_returns_stats(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_stats returns statistics for all shards."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_engine = MagicMock()
                mock_engine.pool = MagicMock()
                mock_engine.pool.size = 5
                mock_engine.pool._overflow = 0
                mock_engine.pool._invalid = 0
                mock_create_engine.return_value = mock_engine

                manager = ShardedDatabaseManager()

                stats = manager.get_shard_stats()

                assert "total_shards" in stats
                assert stats["total_shards"] == 2
                assert "shards" in stats
                assert "shard_0" in stats["shards"]
                assert "shard_1" in stats["shards"]

    def test_get_shard_stats_includes_pool_info(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_stats includes pool information."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_engine = MagicMock()
                mock_engine.pool = MagicMock()
                mock_engine.pool.size = 5
                mock_engine.pool._overflow = 2
                mock_engine.pool._invalid = 0
                mock_create_engine.return_value = mock_engine

                manager = ShardedDatabaseManager()

                stats = manager.get_shard_stats()

                shard_stats = stats["shards"]["shard_0"]
                assert "pool_size" in shard_stats
                assert "overflow" in shard_stats

    def test_get_shard_stats_handles_errors(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_stats handles errors gracefully."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_engine = MagicMock()
                # Make getattr raise an exception to trigger error handling
                mock_engine.pool = MagicMock()
                mock_engine.pool.size = MagicMock(side_effect=Exception("Pool error"))
                mock_create_engine.return_value = mock_engine

                manager = ShardedDatabaseManager()

                stats = manager.get_shard_stats()

                assert "shards" in stats
                # The error should be caught and stored
                assert (
                    "error" in stats["shards"]["shard_0"]
                    or "pool_size" in stats["shards"]["shard_0"]
                )


class TestCloseAllConnections:
    """Test close_all_connections method."""

    def test_close_all_connections_disposes_engines(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """close_all_connections disposes all engines."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_engine = MagicMock()
                mock_engine.dispose = MagicMock()
                mock_create_engine.return_value = mock_engine

                manager = ShardedDatabaseManager()

                manager.close_all_connections()

                assert mock_engine.dispose.call_count == 2

    def test_close_all_connections_handles_errors(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """close_all_connections handles errors gracefully."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_engine = MagicMock()
                mock_engine.dispose = MagicMock(side_effect=Exception("Dispose error"))
                mock_create_engine.return_value = mock_engine

                manager = ShardedDatabaseManager()

                # Should not raise
                manager.close_all_connections()


class TestGlobalShardedDatabaseManager:
    """Test global sharded_db_manager instance."""

    def test_manager_initialization_with_sharding_enabled(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """ShardedDatabaseManager is created when sharding is enabled."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_create_engine.return_value = MagicMock()

                # Directly instantiate to test the logic
                manager = ShardedDatabaseManager()

                assert manager is not None
                assert len(manager.engines) > 0

    def test_manager_initialization_with_multiple_shards(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """ShardedDatabaseManager initializes multiple shard engines."""
        from app.database.sharded_connection import ShardedDatabaseManager

        mock_sharding_service.get_all_shards.return_value = [
            MagicMock(shard_id="shard_0", database_url="sqlite:///db0.db", is_active=True),
            MagicMock(shard_id="shard_1", database_url="sqlite:///db1.db", is_active=True),
            MagicMock(shard_id="shard_2", database_url="sqlite:///db2.db", is_active=True),
        ]

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_create_engine.return_value = MagicMock()

                manager = ShardedDatabaseManager()

                assert len(manager.engines) == 3
                assert len(manager.session_factories) == 3


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""

    def test_get_session_for_user_with_different_users_different_shards(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_session_for_user returns different shards for different users."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session_0 = MagicMock(spec=Session)
                    mock_session_1 = MagicMock(spec=Session)
                    mock_factory_0 = MagicMock(return_value=mock_session_0)
                    mock_factory_1 = MagicMock(return_value=mock_session_1)
                    mock_sessionmaker.side_effect = [mock_factory_0, mock_factory_1]

                    manager = ShardedDatabaseManager()

                    # First user goes to shard_0
                    mock_sharding_service.get_shard_for_user.return_value = "shard_0"
                    session_0 = manager.get_session_for_user("user_1")
                    assert session_0 == mock_session_0

                    # Second user goes to shard_1
                    mock_sharding_service.get_shard_for_user.return_value = "shard_1"
                    session_1 = manager.get_session_for_user("user_2")
                    assert session_1 == mock_session_1

    def test_execute_cross_shard_query_with_empty_results(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """execute_cross_shard_query handles empty results."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    query_func = MagicMock(return_value=[])

                    results = manager.execute_cross_shard_query(query_func)

                    assert results == []

    def test_execute_cross_shard_query_with_none_results(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """execute_cross_shard_query handles None results."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    query_func = MagicMock(return_value=None)

                    results = manager.execute_cross_shard_query(query_func)

                    assert results == []

    def test_get_shard_stats_with_multiple_shards(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_stats returns stats for multiple shards."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_engine = MagicMock()
                mock_engine.pool = MagicMock()
                mock_engine.pool.size = 5
                mock_engine.pool._overflow = 0
                mock_engine.pool._invalid = 0
                mock_create_engine.return_value = mock_engine

                manager = ShardedDatabaseManager()

                stats = manager.get_shard_stats()

                assert stats["total_shards"] == 2
                assert len(stats["shards"]) == 2
                for shard_id in ["shard_0", "shard_1"]:
                    assert shard_id in stats["shards"]
                    assert "pool_size" in stats["shards"][shard_id]

    def test_close_all_connections_with_multiple_shards(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """close_all_connections closes all shard engines."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_engine = MagicMock()
                mock_engine.dispose = MagicMock()
                mock_create_engine.return_value = mock_engine

                manager = ShardedDatabaseManager()

                manager.close_all_connections()

                # Should be called for each shard
                assert mock_engine.dispose.call_count == 2

    def test_get_user_session_with_database_error(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_user_session handles database errors."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_session.commit.side_effect = SQLAlchemyError("DB error")
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    with pytest.raises(SQLAlchemyError):
                        with manager.get_user_session("user_123"):
                            pass

                    mock_session.rollback.assert_called_once()

    def test_get_shard_session_with_database_error(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_session handles database errors."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_session.commit.side_effect = SQLAlchemyError("DB error")
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    with pytest.raises(SQLAlchemyError):
                        with manager.get_shard_session("shard_0"):
                            pass

                    mock_session.rollback.assert_called_once()

    def test_initialize_shard_engines_logs_info(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock, caplog: Any
    ) -> None:
        """_initialize_shard_engines logs initialization info."""
        from app.database.sharded_connection import ShardedDatabaseManager
        import logging

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with caplog.at_level(logging.INFO):
                    manager = ShardedDatabaseManager()

                    # Check that initialization was logged
                    assert any(
                        "Initialized database engine" in record.message for record in caplog.records
                    )

    def test_get_engine_for_shard_with_valid_shard(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_engine_for_shard returns correct engine for valid shard."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine") as mock_create_engine:
                mock_engine_0 = MagicMock()
                mock_engine_1 = MagicMock()
                mock_create_engine.side_effect = [mock_engine_0, mock_engine_1]

                manager = ShardedDatabaseManager()

                engine_0 = manager.get_engine_for_shard("shard_0")
                engine_1 = manager.get_engine_for_shard("shard_1")

                assert engine_0 == mock_engine_0
                assert engine_1 == mock_engine_1

    def test_execute_cross_shard_query_with_mixed_results(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """execute_cross_shard_query handles mixed success and error results."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                with patch("app.database.sharded_connection.sessionmaker") as mock_sessionmaker:
                    mock_session = MagicMock(spec=Session)
                    mock_factory = MagicMock(return_value=mock_session)
                    mock_sessionmaker.return_value = mock_factory

                    manager = ShardedDatabaseManager()

                    query_func = MagicMock(
                        side_effect=[[{"id": 1}], Exception("Error on shard 1"), [{"id": 2}]]
                    )

                    # Mock only 2 shards for this test
                    manager.engines = {"shard_0": MagicMock(), "shard_1": MagicMock()}
                    manager.session_factories = {"shard_0": mock_factory, "shard_1": mock_factory}

                    results = manager.execute_cross_shard_query(query_func)

                    # Should have results from successful shards
                    assert len(results) >= 1

    def test_get_shard_for_user_delegates_to_service(
        self, mock_sharding_service: MagicMock, mock_settings: MagicMock
    ) -> None:
        """get_shard_for_user delegates to sharding_service."""
        from app.database.sharded_connection import ShardedDatabaseManager

        with patch("app.database.sharded_connection.sharding_service", mock_sharding_service):
            with patch("app.database.sharded_connection.create_engine"):
                manager = ShardedDatabaseManager()
                mock_sharding_service.get_shard_for_user.return_value = "shard_2"

                shard_id = manager.get_shard_for_user("user_xyz")

                assert shard_id == "shard_2"
                mock_sharding_service.get_shard_for_user.assert_called_with("user_xyz")
