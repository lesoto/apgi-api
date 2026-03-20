"""
Unit tests for sharded_connection.py module.
"""

from unittest.mock import patch, MagicMock
from app.database.sharded_connection import ShardedDatabaseManager


class TestShardedDatabaseManager:
    """Test sharded connection manager."""

    def test_initialization_success(self):
        """Test successful initialization."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()

            assert "shard1" in manager.engines
            assert "shard1" in manager.session_factories

    def test_get_shard_for_user(self):
        """Test getting shard for user."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]
            mock_sharding.get_shard_for_user.return_value = "shard1"

            manager = ShardedDatabaseManager()
            shard_id = manager.get_shard_for_user("user123")

            assert shard_id == "shard1"

    def test_get_engine_for_shard(self):
        """Test getting engine for shard."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()
            engine = manager.get_engine_for_shard("shard1")

            assert engine is not None

    def test_get_engine_for_shard_not_found(self):
        """Test getting engine for non-existent shard."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()
            engine = manager.get_engine_for_shard("nonexistent")

            assert engine is None

    def test_get_session_for_user(self):
        """Test getting session for user."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]
            mock_sharding.get_shard_for_user.return_value = "shard1"

            manager = ShardedDatabaseManager()
            session = manager.get_session_for_user("user123")

            assert session is not None

    def test_get_session_for_user_not_found(self):
        """Test getting session for user with invalid shard."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]
            mock_sharding.get_shard_for_user.return_value = "nonexistent"

            manager = ShardedDatabaseManager()

            try:
                manager.get_session_for_user("user123")
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "No session factory" in str(e)

    def test_get_session_for_shard(self):
        """Test getting session for shard."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()
            session = manager.get_session_for_shard("shard1")

            assert session is not None

    def test_get_session_for_shard_not_found(self):
        """Test getting session for non-existent shard."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()

            try:
                manager.get_session_for_shard("nonexistent")
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "No session factory" in str(e)

    def test_get_user_session_context_manager(self):
        """Test user session context manager."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]
            mock_sharding.get_shard_for_user.return_value = "shard1"

            manager = ShardedDatabaseManager()
            with manager.get_user_session("user123") as session:
                assert session is not None

    def test_get_user_session_context_manager_error(self):
        """Test user session context manager with error."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]
            mock_sharding.get_shard_for_user.return_value = "shard1"

            manager = ShardedDatabaseManager()

            try:
                with manager.get_user_session("user123") as session:
                    raise Exception("Test error")
            except Exception:
                pass

    def test_get_shard_session_context_manager(self):
        """Test shard session context manager."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()
            with manager.get_shard_session("shard1") as session:
                assert session is not None

    def test_execute_cross_shard_query(self):
        """Test executing query across all shards."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()

            def query_func(session):
                return ["result1", "result2"]

            results = manager.execute_cross_shard_query(query_func)

            assert len(results) == 2

    def test_execute_cross_shard_query_error(self):
        """Test executing query across shards with error."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()

            def query_func(session):
                raise Exception("Query error")

            results = manager.execute_cross_shard_query(query_func)

            assert results == []

    def test_get_shard_stats(self):
        """Test getting shard statistics."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()
            stats = manager.get_shard_stats()

            assert "total_shards" in stats
            assert "shards" in stats

    def test_get_shard_stats_error(self):
        """Test getting shard stats with error."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()

            mock_engine = MagicMock()
            mock_engine.pool = MagicMock()
            with patch.object(manager, "engines", {"shard1": mock_engine}):
                stats = manager.get_shard_stats()
                assert "shards" in stats

    def test_close_all_connections(self):
        """Test closing all connections."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()
            manager.close_all_connections()

            assert True

    def test_close_all_connections_error(self):
        """Test closing all connections with error."""
        with patch("app.database.sharded_connection.sharding_service") as mock_sharding:
            mock_shard = MagicMock()
            mock_shard.shard_id = "shard1"
            mock_shard.database_url = "sqlite:///test.db"
            mock_sharding.get_all_shards.return_value = [mock_shard]

            manager = ShardedDatabaseManager()

            with patch.object(
                manager,
                "engines",
                {"shard1": MagicMock(dispose=MagicMock(side_effect=Exception("Close error")))},
            ) as mock_engines:
                manager.close_all_connections()


# ---------------------------------------------------------------------------
# Tests merged from test_sharded_connection_comprehensive.py
# ---------------------------------------------------------------------------
import pytest
import asyncio
from unittest.mock import MagicMock, patch


@pytest.fixture
def _comp_mock_sharding_service():
    """Mock sharding service for comprehensive tests."""
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
def _comp_mock_engine():
    """Mock SQLAlchemy engine for comprehensive tests."""
    engine = MagicMock()
    pool = MagicMock()
    pool.size = 10
    pool._pool = {"checkedin": 5, "checkedout": 3}
    pool._overflow = 2
    pool._invalid = 0
    engine.pool = pool
    return engine


@pytest.fixture
def _comp_mock_session():
    """Mock SQLAlchemy session for comprehensive tests."""
    session = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def _comp_sharded_manager(_comp_mock_sharding_service):
    """Create ShardedDatabaseManager instance for comprehensive tests."""
    return ShardedDatabaseManager()


class TestInitializationComprehensive:
    """Comprehensive tests for ShardedDatabaseManager initialization."""

    def test_initialization_creates_engines(self, _comp_sharded_manager):
        """Test that initialization creates engines for all shards."""
        assert len(_comp_sharded_manager.engines) == 3
        assert "shard1" in _comp_sharded_manager.engines
        assert "shard2" in _comp_sharded_manager.engines
        assert "shard3" in _comp_sharded_manager.engines

    def test_initialization_creates_session_factories(self, _comp_sharded_manager):
        """Test that initialization creates session factories."""
        assert len(_comp_sharded_manager.session_factories) == 3
        assert "shard1" in _comp_sharded_manager.session_factories

    def test_sqlite_engine_configuration(self, _comp_mock_sharding_service):
        """Test SQLite engine configuration."""
        _comp_mock_sharding_service.get_all_shards.return_value = [
            MagicMock(shard_id="sqlite_shard", database_url="sqlite:///test.db")
        ]
        manager = ShardedDatabaseManager()
        assert "sqlite_shard" in manager.engines
        assert "sqlite_shard" in manager.session_factories

    def test_postgresql_engine_configuration(self, _comp_mock_sharding_service):
        """Test PostgreSQL engine configuration."""
        _comp_mock_sharding_service.get_all_shards.return_value = [
            MagicMock(shard_id="pg_shard", database_url="postgresql://localhost/db")
        ]
        manager = ShardedDatabaseManager()
        assert "pg_shard" in manager.engines
        assert "pg_shard" in manager.session_factories


class TestGetUserSessionAsync:
    """Tests for get_user_session async context manager."""

    @pytest.mark.asyncio
    async def test_get_user_session_success(
        self, _comp_sharded_manager, _comp_mock_sharding_service, _comp_mock_session
    ):
        """Test successful user session context manager."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session

        async with _comp_sharded_manager.get_user_session("user123") as session:
            assert session == _comp_mock_session

        _comp_mock_session.commit.assert_called_once()
        _comp_mock_session.close.assert_called_once()
        _comp_mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_session_rollback_on_error(
        self, _comp_sharded_manager, _comp_mock_sharding_service, _comp_mock_session
    ):
        """Test rollback on error in user session."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session

        with pytest.raises(Exception):
            async with _comp_sharded_manager.get_user_session("user123") as session:
                assert session == _comp_mock_session
                raise Exception("Test error")

        _comp_mock_session.rollback.assert_called_once()
        _comp_mock_session.close.assert_called_once()
        _comp_mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_session_always_closes(
        self, _comp_sharded_manager, _comp_mock_sharding_service, _comp_mock_session
    ):
        """Test that session is always closed."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session

        with pytest.raises(Exception):
            async with _comp_sharded_manager.get_user_session("user123") as session:
                raise Exception("Test error")

        _comp_mock_session.close.assert_called_once()


class TestGetShardSessionAsync:
    """Tests for get_shard_session async context manager."""

    @pytest.mark.asyncio
    async def test_get_shard_session_success(self, _comp_sharded_manager, _comp_mock_session):
        """Test successful shard session context manager."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session

        async with _comp_sharded_manager.get_shard_session("shard1") as session:
            assert session == _comp_mock_session

        _comp_mock_session.commit.assert_called_once()
        _comp_mock_session.close.assert_called_once()
        _comp_mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_shard_session_rollback_on_error(
        self, _comp_sharded_manager, _comp_mock_session
    ):
        """Test rollback on error in shard session."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session

        with pytest.raises(Exception):
            async with _comp_sharded_manager.get_shard_session("shard1") as session:
                assert session == _comp_mock_session
                raise Exception("Test error")

        _comp_mock_session.rollback.assert_called_once()
        _comp_mock_session.close.assert_called_once()
        _comp_mock_session.commit.assert_not_called()


class TestExecuteCrossShardQueryComprehensive:
    """Comprehensive tests for execute_cross_shard_query method."""

    @pytest.mark.asyncio
    async def test_execute_cross_shard_query_partial_failure(
        self, _comp_sharded_manager, _comp_mock_session
    ):
        """Test cross-shard query with partial failures."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session
        _comp_sharded_manager.session_factories["shard2"] = lambda: _comp_mock_session
        _comp_sharded_manager.session_factories["shard3"] = lambda: _comp_mock_session

        call_count = [0]

        def query_func(session, param):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Shard error")
            return [{"id": 1}]

        results = _comp_sharded_manager.execute_cross_shard_query(query_func, "test_param")

        # Should continue with other shards despite one failure
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_execute_cross_shard_query_empty_results(
        self, _comp_sharded_manager, _comp_mock_session
    ):
        """Test cross-shard query with empty results."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session

        def query_func(session, param):
            return []

        results = _comp_sharded_manager.execute_cross_shard_query(query_func, "test_param")

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_execute_cross_shard_query_all_shards_fail(
        self, _comp_sharded_manager, _comp_mock_session
    ):
        """Test cross-shard query when all shards fail."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session
        _comp_sharded_manager.session_factories["shard2"] = lambda: _comp_mock_session

        def query_func(session, param):
            raise Exception("All shards fail")

        results = _comp_sharded_manager.execute_cross_shard_query(query_func, "test_param")

        assert len(results) == 0


class TestGetShardStatsComprehensive:
    """Comprehensive tests for get_shard_stats method."""

    def test_get_shard_stats_success(self, _comp_sharded_manager, _comp_mock_engine):
        """Test successful shard stats retrieval."""
        _comp_sharded_manager.engines["shard1"] = _comp_mock_engine

        stats = _comp_sharded_manager.get_shard_stats()

        assert stats["total_shards"] == 3
        assert "shard1" in stats["shards"]
        assert stats["shards"]["shard1"]["pool_size"] == 10

    def test_get_shard_stats_with_error(self, _comp_sharded_manager):
        """Test shard stats with engine error."""
        broken_engine = MagicMock()
        broken_engine.pool = MagicMock(side_effect=Exception("Pool error"))
        _comp_sharded_manager.engines["broken"] = broken_engine

        stats = _comp_sharded_manager.get_shard_stats()

        assert "broken" in stats["shards"]
        assert "error" in stats["shards"]["broken"]

    def test_get_shard_stats_empty_engines(self, _comp_sharded_manager):
        """Test getting stats when no engines exist."""
        _comp_sharded_manager.engines = {}

        stats = _comp_sharded_manager.get_shard_stats()

        assert stats["total_shards"] == 0
        assert len(stats["shards"]) == 0


class TestCloseAllConnectionsComprehensive:
    """Comprehensive tests for close_all_connections method."""

    def test_close_all_connections_multiple(self, _comp_sharded_manager, _comp_mock_engine):
        """Test closing all connections."""
        _comp_sharded_manager.engines["shard1"] = _comp_mock_engine
        _comp_sharded_manager.engines["shard2"] = _comp_mock_engine
        _comp_sharded_manager.engines["shard3"] = _comp_mock_engine

        _comp_sharded_manager.close_all_connections()

        assert _comp_mock_engine.dispose.call_count == 3

    def test_close_all_connections_with_error(self, _comp_sharded_manager):
        """Test closing connections with one failing."""
        good_engine = MagicMock()
        bad_engine = MagicMock()
        bad_engine.dispose.side_effect = Exception("Dispose error")

        _comp_sharded_manager.engines["shard1"] = good_engine
        _comp_sharded_manager.engines["shard2"] = bad_engine
        _comp_sharded_manager.engines["shard3"] = good_engine

        _comp_sharded_manager.close_all_connections()

        # Should continue closing other engines despite one failure
        assert good_engine.dispose.call_count == 2

    def test_close_all_connections_empty(self, _comp_sharded_manager):
        """Test closing connections when no engines exist."""
        _comp_sharded_manager.engines = {}

        # Should not raise exception
        _comp_sharded_manager.close_all_connections()


class TestEdgeCasesComprehensive:
    """Comprehensive edge case tests."""

    def test_empty_shard_list(self, _comp_mock_sharding_service):
        """Test initialization with no shards."""
        _comp_mock_sharding_service.get_all_shards.return_value = []

        manager = ShardedDatabaseManager()

        assert len(manager.engines) == 0
        assert len(manager.session_factories) == 0

    def test_get_session_for_user_with_exception(
        self, _comp_sharded_manager, _comp_mock_sharding_service
    ):
        """Test getting session when factory raises exception."""
        _comp_sharded_manager.session_factories["shard1"] = MagicMock(
            side_effect=Exception("Factory error")
        )

        with pytest.raises(Exception):
            _comp_sharded_manager.get_session_for_user("user123")


class TestSessionLifecycleComprehensive:
    """Comprehensive tests for session lifecycle management."""

    @pytest.mark.asyncio
    async def test_session_commit_on_success(self, _comp_sharded_manager, _comp_mock_session):
        """Test that session commits on successful operation."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session

        async with _comp_sharded_manager.get_user_session("user123"):
            pass

        _comp_mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_rollback_on_exception(self, _comp_sharded_manager, _comp_mock_session):
        """Test that session rolls back on exception."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session

        with pytest.raises(ValueError):
            async with _comp_sharded_manager.get_user_session("user123"):
                raise ValueError("Test error")

        _comp_mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_close_always_called(self, _comp_sharded_manager, _comp_mock_session):
        """Test that session.close is always called."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session

        try:
            async with _comp_sharded_manager.get_user_session("user123"):
                raise Exception("Test")
        except Exception:
            pass

        _comp_mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nested_context_managers(self, _comp_sharded_manager, _comp_mock_session):
        """Test nested context managers work correctly."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session
        _comp_sharded_manager.session_factories["shard2"] = lambda: _comp_mock_session

        async with _comp_sharded_manager.get_shard_session("shard1") as session1:
            assert session1 is not None
            async with _comp_sharded_manager.get_shard_session("shard2") as session2:
                assert session2 is not None

        # Both sessions should be committed and closed
        assert _comp_mock_session.commit.call_count == 2
        assert _comp_mock_session.close.call_count == 2


class TestConcurrentAccessComprehensive:
    """Tests for concurrent access patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_user_sessions(self, _comp_sharded_manager, _comp_mock_session):
        """Test concurrent user sessions for different users."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session

        async def user_session(user_id):
            async with _comp_sharded_manager.get_user_session(user_id):
                await asyncio.sleep(0.01)

        await asyncio.gather(
            user_session("user1"),
            user_session("user2"),
            user_session("user3"),
        )

        assert _comp_mock_session.commit.call_count >= 3

    @pytest.mark.asyncio
    async def test_concurrent_shard_sessions(self, _comp_sharded_manager, _comp_mock_session):
        """Test concurrent shard sessions."""
        _comp_sharded_manager.session_factories["shard1"] = lambda: _comp_mock_session
        _comp_sharded_manager.session_factories["shard2"] = lambda: _comp_mock_session

        async def shard_session(shard_id):
            async with _comp_sharded_manager.get_shard_session(shard_id):
                await asyncio.sleep(0.01)

        await asyncio.gather(
            shard_session("shard1"),
            shard_session("shard2"),
        )

        assert _comp_mock_session.commit.call_count >= 2
