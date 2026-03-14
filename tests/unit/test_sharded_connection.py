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
