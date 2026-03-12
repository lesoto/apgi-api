"""
Unit tests for database sharding service.

Tests sharding logic, configuration, and shard management.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.sharding_service import DatabaseShardingService, ShardConfig, ShardInfo


@pytest.fixture
def sharding_service():
    """Create DatabaseShardingService instance."""
    return DatabaseShardingService()


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.database_url = "sqlite:///test.db"
    settings.database_shards_count = 1
    return settings


class TestDatabaseShardingService:
    """Test DatabaseShardingService functionality."""

    def test_init_single_shard(self, mock_settings):
        """Test initialization with single shard."""
        with patch("app.services.sharding_service.settings", mock_settings):
            service = DatabaseShardingService()

            assert len(service.shards) == 1
            assert "shard_0" in service.shards
            assert service.shards["shard_0"].database_url == "sqlite:///test.db"
            assert service.num_shards == 1

    def test_init_multiple_shards(self, mock_settings):
        """Test initialization with multiple shards."""
        mock_settings.database_shards_count = 3

        with patch("app.services.sharding_service.settings", mock_settings):
            service = DatabaseShardingService()

            assert len(service.shards) == 3
            assert all(f"shard_{i}" in service.shards for i in range(3))
            assert service.num_shards == 3

    def test_get_shard_for_user_single_shard(self, sharding_service):
        """Test shard assignment for single shard setup."""
        shard_id = sharding_service.get_shard_for_user("user123")

        assert shard_id == "shard_0"

    def test_get_shard_for_user_multiple_shards(self, mock_settings):
        """Test shard assignment for multiple shard setup."""
        mock_settings.database_shards_count = 4

        with patch("app.services.sharding_service.settings", mock_settings):
            service = DatabaseShardingService()

            # Test that same user always gets same shard (consistent hashing)
            user_id = "test_user_123"
            shard1 = service.get_shard_for_user(user_id)
            shard2 = service.get_shard_for_user(user_id)

            assert shard1 == shard2
            assert shard1 in [f"shard_{i}" for i in range(4)]

    def test_get_shard_config_existing(self, sharding_service):
        """Test getting config for existing shard."""
        config = sharding_service.get_shard_config("shard_0")

        assert config is not None
        assert config.shard_id == "shard_0"
        assert isinstance(config, ShardConfig)

    def test_get_shard_config_nonexistent(self, sharding_service):
        """Test getting config for non-existent shard."""
        config = sharding_service.get_shard_config("shard_999")

        assert config is None

    def test_get_all_shards_single_shard(self, sharding_service):
        """Test getting all shards for single shard setup."""
        shards = sharding_service.get_all_shards()

        assert len(shards) == 1
        assert isinstance(shards[0], ShardInfo)
        assert shards[0].shard_id == "shard_0"
        assert shards[0].is_active is True

    def test_get_all_shards_multiple_shards(self, mock_settings):
        """Test getting all shards for multiple shard setup."""
        mock_settings.database_shards_count = 2

        with patch("app.services.sharding_service.settings", mock_settings):
            service = DatabaseShardingService()
            shards = service.get_all_shards()

            assert len(shards) == 2
            shard_ids = [s.shard_id for s in shards]
            assert "shard_0" in shard_ids
            assert "shard_1" in shard_ids

            for shard in shards:
                assert isinstance(shard, ShardInfo)
                assert shard.is_active is True
                assert len(shard.user_range_start) > 0
                assert len(shard.user_range_end) > 0

    def test_migrate_user_data(self, sharding_service):
        """Test user data migration (placeholder implementation)."""
        result = sharding_service.migrate_user_data("user123", "shard_0", "shard_1")

        assert isinstance(result, dict)
        assert result["user_id"] == "user123"
        assert result["from_shard"] == "shard_0"
        assert result["to_shard"] == "shard_1"
        assert result["status"] == "not_implemented"

    def test_get_shard_stats(self, sharding_service):
        """Test getting shard statistics."""
        stats = sharding_service.get_shard_stats()

        assert isinstance(stats, dict)
        assert "total_shards" in stats
        assert "active_shards" in stats
        assert "read_replicas" in stats
        assert "sharding_strategy" in stats
        assert "shard_key" in stats
        assert "shards" in stats

        assert stats["total_shards"] == 1
        assert stats["active_shards"] == 1
        assert stats["sharding_strategy"] == "consistent_hashing"
        assert stats["shard_key"] == "user_id"

    def test_validate_sharding_setup_single_shard(self, sharding_service):
        """Test sharding setup validation for single shard."""
        result = sharding_service.validate_sharding_setup()

        assert isinstance(result, dict)
        assert result["valid"] is True
        assert isinstance(result["issues"], list)
        assert isinstance(result["warnings"], list)
        assert result["shard_count"] == 1
        assert result["configured_shards"] == 1

    def test_validate_sharding_setup_multiple_shards_same_url(self, mock_settings):
        """Test sharding setup validation for multiple shards with same URL."""
        mock_settings.database_shards_count = 3
        # Configure mock to return None for shard URLs, so all use same database_url
        mock_settings.database_shard_0_url = None
        mock_settings.database_shard_1_url = None
        mock_settings.database_shard_2_url = None

        with patch("app.services.sharding_service.settings", mock_settings):
            service = DatabaseShardingService()
            result = service.validate_sharding_setup()

            assert isinstance(result, dict)
            # Should have warning about same database URL
            assert len(result["warnings"]) > 0
            assert any(
                "Multiple shards configured but all using the same database URL" in w
                for w in result["warnings"]
            )

    def test_shard_config_dataclass(self):
        """Test ShardConfig dataclass."""
        config = ShardConfig(
            shard_id="test_shard", database_url="sqlite:///test.db", weight=2, is_read_replica=True
        )

        assert config.shard_id == "test_shard"
        assert config.database_url == "sqlite:///test.db"
        assert config.weight == 2
        assert config.is_read_replica is True

    def test_shard_info_dataclass(self):
        """Test ShardInfo dataclass."""
        info = ShardInfo(
            shard_id="test_shard",
            user_range_start="0000",
            user_range_end="ffff",
            database_url="sqlite:///test.db",
            is_active=False,
        )

        assert info.shard_id == "test_shard"
        assert info.user_range_start == "0000"
        assert info.user_range_end == "ffff"
        assert info.database_url == "sqlite:///test.db"
        assert info.is_active is False


class TestShardConfig:
    """Test ShardConfig dataclass."""

    def test_default_values(self):
        """Test default values for ShardConfig."""
        config = ShardConfig(shard_id="test", database_url="sqlite:///test.db")

        assert config.shard_id == "test"
        assert config.database_url == "sqlite:///test.db"
        assert config.weight == 1
        assert config.is_read_replica is False


class TestShardInfo:
    """Test ShardInfo dataclass."""

    def test_default_values(self):
        """Test default values for ShardInfo."""
        info = ShardInfo(
            shard_id="test",
            user_range_start="0000",
            user_range_end="ffff",
            database_url="sqlite:///test.db",
        )

        assert info.shard_id == "test"
        assert info.user_range_start == "0000"
        assert info.user_range_end == "ffff"
        assert info.database_url == "sqlite:///test.db"
        assert info.is_active is True
