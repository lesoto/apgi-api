"""
Comprehensive unit tests for sharded database connection module.

Tests the actual sharded_db_manager implementation and related utilities.
"""

import pytest
from unittest.mock import MagicMock, patch
from app.database.sharded_connection import ShardedDatabaseManager


@pytest.fixture
def mock_sharding_service():
    """Mock sharding service."""
    with patch("app.database.sharded_connection.sharding_service") as mock:
        shard_configs = [
            MagicMock(shard_id="shard1", database_url="postgresql://localhost/db1"),
            MagicMock(shard_id="shard2", database_url="postgresql://localhost/db2"),
            MagicMock(shard_id="shard3", database_url="postgresql://localhost/db3"),
        ]
        mock.get_all_shards.return_value = shard_configs
        mock.get_shard_for_user.return_value = "shard1"
        yield mock


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy engine."""
    engine = MagicMock()
    pool = MagicMock()
    pool.size = 10
    pool._pool = {"checkedin": 5, "checkedout": 3}
    pool._overflow = 2
    pool._invalid = 0
    engine.pool = pool
    return engine


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session."""
    session = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def sharded_manager(mock_sharding_service):
    """Create ShardedDatabaseManager instance."""
    return ShardedDatabaseManager()


class TestInitialization:
    """Tests for ShardedDatabaseManager initialization."""

    def test_initialization_creates_engines(self, sharded_manager, mock_sharding_service):
        """Test that initialization creates engines for all shards."""
        assert len(sharded_manager.engines) == 3
        assert "shard1" in sharded_manager.engines
        assert "shard2" in sharded_manager.engines
        assert "shard3" in sharded_manager.engines

    def test_initialization_creates_session_factories(self, sharded_manager):
        """Test that initialization creates session factories."""
        assert len(sharded_manager.session_factories) == 3
        assert "shard1" in sharded_manager.session_factories
        assert "shard2" in sharded_manager.session_factories
        assert "shard3" in sharded_manager.session_factories

    def test_sqlite_engine_configuration(self, mock_sharding_service):
        """Test SQLite engine configuration."""
        mock_sharding_service.get_all_shards.return_value = [
            MagicMock(shard_id="sqlite_shard", database_url="sqlite:///test.db")
        ]
        manager = ShardedDatabaseManager()

        assert "sqlite_shard" in manager.engines
        assert "sqlite_shard" in manager.session_factories

    def test_postgresql_engine_configuration(self, mock_sharding_service):
        """Test PostgreSQL engine configuration."""
        mock_sharding_service.get_all_shards.return_value = [
            MagicMock(shard_id="pg_shard", database_url="postgresql://localhost/db")
        ]
        manager = ShardedDatabaseManager()

        assert "pg_shard" in manager.engines
        assert "pg_shard" in manager.session_factories


class TestGetShardForUser:
    """Tests for get_shard_for_user method."""

    def test_get_shard_for_user(self, sharded_manager, mock_sharding_service):
        """Test getting shard ID for a user."""
        shard_id = sharded_manager.get_shard_for_user("user123")
        assert shard_id == "shard1"
        mock_sharding_service.get_shard_for_user.assert_called_once_with("user123")


class TestGetEngineForShard:
    """Tests for get_engine_for_shard method."""

    def test_get_existing_engine(self, sharded_manager):
        """Test getting engine for existing shard."""
        engine = sharded_manager.get_engine_for_shard("shard1")
        assert engine is not None

    def test_get_nonexistent_engine(self, sharded_manager):
        """Test getting engine for non-existent shard."""
        engine = sharded_manager.get_engine_for_shard("nonexistent")
        assert engine is None


class TestGetSessionForUser:
    """Tests for get_session_for_user method."""

    def test_get_session_for_user(self, sharded_manager, mock_sharding_service):
        """Test getting session for a user."""
        session = sharded_manager.get_session_for_user("user123")
        assert session is not None
        mock_sharding_service.get_shard_for_user.assert_called_once_with("user123")

    def test_get_session_for_user_no_factory(self, sharded_manager):
        """Test getting session when no factory exists."""
        sharded_manager.session_factories = {}

        with pytest.raises(ValueError) as exc_info:
            sharded_manager.get_session_for_user("user123")
        assert "No session factory available" in str(exc_info.value)


class TestGetSessionForShard:
    """Tests for get_session_for_shard method."""

    def test_get_session_for_shard(self, sharded_manager):
        """Test getting session for a specific shard."""
        session = sharded_manager.get_session_for_shard("shard1")
        assert session is not None

    def test_get_session_for_nonexistent_shard(self, sharded_manager):
        """Test getting session for non-existent shard."""
        with pytest.raises(ValueError) as exc_info:
            sharded_manager.get_session_for_shard("nonexistent")
        assert "No session factory available" in str(exc_info.value)


class TestGetUserSession:
    """Tests for get_user_session context manager."""

    @pytest.mark.asyncio
    async def test_get_user_session_success(
        self, sharded_manager, mock_sharding_service, mock_session
    ):
        """Test successful user session context manager."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        async with sharded_manager.get_user_session("user123") as session:
            assert session == mock_session

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_session_rollback_on_error(
        self, sharded_manager, mock_sharding_service, mock_session
    ):
        """Test rollback on error in user session."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        with pytest.raises(Exception):
            async with sharded_manager.get_user_session("user123") as session:
                assert session == mock_session
                raise Exception("Test error")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_session_always_closes(
        self, sharded_manager, mock_sharding_service, mock_session
    ):
        """Test that session is always closed."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        with pytest.raises(Exception):
            async with sharded_manager.get_user_session("user123") as session:
                raise Exception("Test error")

        mock_session.close.assert_called_once()


class TestGetShardSession:
    """Tests for get_shard_session context manager."""

    @pytest.mark.asyncio
    async def test_get_shard_session_success(self, sharded_manager, mock_session):
        """Test successful shard session context manager."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        async with sharded_manager.get_shard_session("shard1") as session:
            assert session == mock_session

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_shard_session_rollback_on_error(self, sharded_manager, mock_session):
        """Test rollback on error in shard session."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        with pytest.raises(Exception):
            async with sharded_manager.get_shard_session("shard1") as session:
                assert session == mock_session
                raise Exception("Test error")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.commit.assert_not_called()


class TestExecuteCrossShardQuery:
    """Tests for execute_cross_shard_query method."""

    @pytest.mark.asyncio
    async def test_execute_cross_shard_query_success(self, sharded_manager, mock_session):
        """Test successful cross-shard query execution."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session
        sharded_manager.session_factories["shard2"] = lambda: mock_session
        sharded_manager.session_factories["shard3"] = lambda: mock_session

        def query_func(session, param):
            return [{"id": 1, "shard": "test"}]

        results = sharded_manager.execute_cross_shard_query(query_func, "test_param")

        assert len(results) == 3  # One result per shard

    @pytest.mark.asyncio
    async def test_execute_cross_shard_query_partial_failure(self, sharded_manager, mock_session):
        """Test cross-shard query with partial failures."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session
        sharded_manager.session_factories["shard2"] = lambda: mock_session
        sharded_manager.session_factories["shard3"] = lambda: mock_session

        call_count = [0]

        def query_func(session, param):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Shard error")
            return [{"id": 1}]

        results = sharded_manager.execute_cross_shard_query(query_func, "test_param")

        # Should continue with other shards despite one failure
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_execute_cross_shard_query_empty_results(self, sharded_manager, mock_session):
        """Test cross-shard query with empty results."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        def query_func(session, param):
            return []

        results = sharded_manager.execute_cross_shard_query(query_func, "test_param")

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_execute_cross_shard_query_with_kwargs(self, sharded_manager, mock_session):
        """Test cross-shard query with keyword arguments."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        def query_func(session, param, limit=10):
            return [{"id": i} for i in range(limit)]

        results = sharded_manager.execute_cross_shard_query(query_func, "test_param", limit=5)

        assert len(results) == 5


class TestGetShardStats:
    """Tests for get_shard_stats method."""

    def test_get_shard_stats_success(self, sharded_manager, mock_engine):
        """Test successful shard stats retrieval."""
        sharded_manager.engines["shard1"] = mock_engine

        stats = sharded_manager.get_shard_stats()

        assert stats["total_shards"] == 3
        assert "shard1" in stats["shards"]
        assert stats["shards"]["shard1"]["pool_size"] == 10

    def test_get_shard_stats_with_error(self, sharded_manager):
        """Test shard stats with engine error."""
        broken_engine = MagicMock()
        broken_engine.pool = MagicMock(side_effect=Exception("Pool error"))
        sharded_manager.engines["broken"] = broken_engine

        stats = sharded_manager.get_shard_stats()

        assert "broken" in stats["shards"]
        assert "error" in stats["shards"]["broken"]


class TestCloseAllConnections:
    """Tests for close_all_connections method."""

    def test_close_all_connections(self, sharded_manager, mock_engine):
        """Test closing all connections."""
        sharded_manager.engines["shard1"] = mock_engine
        sharded_manager.engines["shard2"] = mock_engine
        sharded_manager.engines["shard3"] = mock_engine

        sharded_manager.close_all_connections()

        assert mock_engine.dispose.call_count == 3

    def test_close_all_connections_with_error(self, sharded_manager):
        """Test closing connections with one failing."""
        good_engine = MagicMock()
        bad_engine = MagicMock()
        bad_engine.dispose.side_effect = Exception("Dispose error")

        sharded_manager.engines["shard1"] = good_engine
        sharded_manager.engines["shard2"] = bad_engine
        sharded_manager.engines["shard3"] = good_engine

        sharded_manager.close_all_connections()

        # Should continue closing other engines despite one failure
        assert good_engine.dispose.call_count == 2


class TestGlobalInstance:
    """Tests for global sharded_db_manager instance."""

    @patch("app.database.sharded_connection.settings")
    def test_global_instance_enabled(self, mock_settings):
        """Test global instance when sharding is enabled."""
        mock_settings.database_shards_enabled = True

        with patch("app.database.sharded_connection.ShardedDatabaseManager") as mock_manager_class:
            mock_instance = MagicMock()
            mock_manager_class.return_value = mock_instance

            # Re-import to trigger initialization
            import importlib
            import app.database.sharded_connection

            importlib.reload(app.database.sharded_connection)

            assert app.database.sharded_connection.sharded_db_manager == mock_instance

    @patch("app.database.sharded_connection.settings")
    def test_global_instance_disabled(self, mock_settings):
        """Test global instance when sharding is disabled."""
        mock_settings.database_shards_enabled = False

        with patch("app.database.sharded_connection.ShardedDatabaseManager") as mock_manager_class:
            # Re-import to trigger initialization
            import importlib
            import app.database.sharded_connection

            importlib.reload(app.database.sharded_connection)

            assert app.database.sharded_connection.sharded_db_manager is None


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_shard_list(self, mock_sharding_service):
        """Test initialization with no shards."""
        mock_sharding_service.get_all_shards.return_value = []

        manager = ShardedDatabaseManager()

        assert len(manager.engines) == 0
        assert len(manager.session_factories) == 0

    def test_get_session_for_user_with_exception(self, sharded_manager, mock_sharding_service):
        """Test getting session when factory raises exception."""
        sharded_manager.session_factories["shard1"] = MagicMock(
            side_effect=Exception("Factory error")
        )

        with pytest.raises(Exception):
            sharded_manager.get_session_for_user("user123")

    @pytest.mark.asyncio
    async def test_cross_shard_query_all_shards_fail(self, sharded_manager, mock_session):
        """Test cross-shard query when all shards fail."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session
        sharded_manager.session_factories["shard2"] = lambda: mock_session

        def query_func(session, param):
            raise Exception("All shards fail")

        results = sharded_manager.execute_cross_shard_query(query_func, "test_param")

        # Should return empty list rather than raising
        assert len(results) == 0

    def test_get_shard_stats_empty_engines(self, sharded_manager):
        """Test getting stats when no engines exist."""
        sharded_manager.engines = {}

        stats = sharded_manager.get_shard_stats()

        assert stats["total_shards"] == 0
        assert len(stats["shards"]) == 0

    def test_close_all_connections_empty(self, sharded_manager):
        """Test closing connections when no engines exist."""
        sharded_manager.engines = {}

        # Should not raise exception
        sharded_manager.close_all_connections()


class TestSessionLifecycle:
    """Tests for session lifecycle management."""

    @pytest.mark.asyncio
    async def test_session_commit_on_success(self, sharded_manager, mock_session):
        """Test that session commits on successful operation."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        async with sharded_manager.get_user_session("user123"):
            pass

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_rollback_on_exception(self, sharded_manager, mock_session):
        """Test that session rolls back on exception."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        with pytest.raises(ValueError):
            async with sharded_manager.get_user_session("user123"):
                raise ValueError("Test error")

        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_close_always_called(self, sharded_manager, mock_session):
        """Test that session.close is always called."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        try:
            async with sharded_manager.get_user_session("user123"):
                raise Exception("Test")
        except Exception:
            pass

        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nested_context_managers(self, sharded_manager, mock_session):
        """Test nested context managers work correctly."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session
        sharded_manager.session_factories["shard2"] = lambda: mock_session

        async with sharded_manager.get_shard_session("shard1") as session1:
            assert session1 is not None
            async with sharded_manager.get_shard_session("shard2") as session2:
                assert session2 is not None

        # Both sessions should be committed and closed
        assert mock_session.commit.call_count == 2
        assert mock_session.close.call_count == 2


class TestConcurrentAccess:
    """Tests for concurrent access patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_user_sessions(self, sharded_manager, mock_session):
        """Test concurrent user sessions for different users."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session

        import asyncio

        async def user_session(user_id):
            async with sharded_manager.get_user_session(user_id):
                await asyncio.sleep(0.01)

        # Run concurrent sessions
        await asyncio.gather(
            user_session("user1"),
            user_session("user2"),
            user_session("user3"),
        )

        # All should complete successfully
        assert mock_session.commit.call_count >= 3

    @pytest.mark.asyncio
    async def test_concurrent_shard_sessions(self, sharded_manager, mock_session):
        """Test concurrent shard sessions."""
        sharded_manager.session_factories["shard1"] = lambda: mock_session
        sharded_manager.session_factories["shard2"] = lambda: mock_session

        import asyncio

        async def shard_session(shard_id):
            async with sharded_manager.get_shard_session(shard_id):
                await asyncio.sleep(0.01)

        await asyncio.gather(
            shard_session("shard1"),
            shard_session("shard2"),
        )

        assert mock_session.commit.call_count >= 2
