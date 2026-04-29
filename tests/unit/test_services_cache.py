"""
Tests for cache service.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.cache_service import CacheService


class TestCacheService:
    """Test cache service."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def cache_service(self, mock_redis):
        """Cache service instance."""
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test_secret_key_for_encryption"
            return CacheService(mock_redis)

    @pytest.mark.asyncio
    async def test_set_session_state(self, cache_service, mock_redis):
        """Test setting session state."""
        state = {"user_id": "user-1", "data": "test"}
        mock_redis.setex.return_value = True

        result = await cache_service.set_session_state("session-1", state)

        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_state(self, cache_service, mock_redis):
        """Test getting session state."""
        state = {"user_id": "user-1", "data": "test"}
        mock_redis.get.return_value = b'{"user_id": "user-1", "data": "test"}'

        result = await cache_service.get_session_state("session-1")

        assert result == state

    @pytest.mark.asyncio
    async def test_get_session_state_not_found(self, cache_service, mock_redis):
        """Test getting session state when not found."""
        mock_redis.get.return_value = None

        result = await cache_service.get_session_state("session-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_session_metadata(self, cache_service, mock_redis):
        """Test setting session metadata."""
        metadata = {"created_at": "2024-01-01", "ip": "127.0.0.1"}
        mock_redis.setex.return_value = True

        result = await cache_service.set_session_metadata("session-1", metadata)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_session_state(self, cache_service, mock_redis):
        """Test deleting session state."""
        mock_redis.delete.return_value = 1

        result = await cache_service.delete_session_state("session-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_cache_key_prefixes(self, cache_service):
        """Test cache key prefixes are set correctly."""
        assert "session" in cache_service.prefixes
        assert "user" in cache_service.prefixes
        assert "task" in cache_service.prefixes
        assert cache_service.prefixes["session"] == "session:"

    def test_encryption_initialization(self):
        """Test encryption is initialized with proper key."""
        mock_redis = AsyncMock()

        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test_secret_key"
            service = CacheService(mock_redis)

            assert service.fernet is not None

    def test_encryption_initialization_no_secret(self):
        """Test encryption initialization fails without secret."""
        mock_redis = AsyncMock()

        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.jwt_secret_key = None

            with pytest.raises(ValueError, match="JWT secret key is required"):
                CacheService(mock_redis)
