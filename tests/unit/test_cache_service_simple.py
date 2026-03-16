"""Simple unit tests for cache service to achieve basic coverage.

Focuses on testing service methods and error paths without complex dependencies.
"""

import pytest
from unittest.mock import Mock, patch
import redis

from app.services.cache_service import (
    CacheService,
    init_cache_service,
    get_cache_service,
)


class TestCacheService:
    """Test cache service."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return Mock(spec=redis.Redis)

    @pytest.fixture
    def mock_service(self, mock_redis):
        """Mock cache service."""
        return CacheService(mock_redis, default_ttl=3600)

    def test_cache_service_initialization(self, mock_redis):
        """Test cache service initialization."""
        service = CacheService(mock_redis, default_ttl=1800)

        assert service.redis == mock_redis
        assert service.default_ttl == 1800
        assert service.fernet is not None
        assert service.prefixes == {
            "session": "session:",
            "user": "user:",
            "auth": "auth:",
            "task": "task:",
            "query": "query:",
            "response": "response:",
        }

    def test_init_cache_service(self, mock_redis):
        """Test global cache service initialization."""
        # Reset global cache service
        import app.services.cache_service

        app.services.cache_service.cache_service = None

        result = init_cache_service(mock_redis, default_ttl=7200)

        assert result is not None
        assert result.default_ttl == 7200
        assert app.services.cache_service.cache_service == result

    def test_get_cache_service_not_initialized(self):
        """Test getting cache service when not initialized."""
        # Reset global cache service
        import app.services.cache_service

        app.services.cache_service.cache_service = None

        result = get_cache_service()

        assert result is None

    def test_get_cache_service_initialized(self, mock_redis):
        """Test getting cache service when initialized."""
        # Initialize global cache service
        init_cache_service(mock_redis)

        result = get_cache_service()

        assert result is not None
        assert result.redis == mock_redis

    @pytest.mark.asyncio
    async def test_set_session_state_success(self, mock_service):
        """Test successful session state caching."""
        session_id = "session123"
        state = {"user_id": "user123", "is_active": True}

        with patch.object(mock_service, "_set_json", return_value=True) as mock_set:
            result = await mock_service.set_session_state(session_id, state, ttl=1800)

            assert result is True
            mock_set.assert_called_once()
            expected_key = f"{mock_service.prefixes['session']}{session_id}:state"
            mock_set.assert_called_with(expected_key, state, 1800)

    @pytest.mark.asyncio
    async def test_set_session_state_default_ttl(self, mock_service):
        """Test session state caching with default TTL."""
        session_id = "session123"
        state = {"user_id": "user123", "is_active": True}

        with patch.object(mock_service, "_set_json", return_value=True) as mock_set:
            result = await mock_service.set_session_state(session_id, state)

            assert result is True
            expected_key = f"{mock_service.prefixes['session']}{session_id}:state"
            mock_set.assert_called_once_with(expected_key, state, mock_service.default_ttl)

    @pytest.mark.asyncio
    async def test_get_session_state_success(self, mock_service):
        """Test successful session state retrieval."""
        session_id = "session123"
        expected_state = {"user_id": "user123", "is_active": True}

        with patch.object(mock_service, "_get_json", return_value=expected_state) as mock_get:
            result = await mock_service.get_session_state(session_id)

            assert result == expected_state
            expected_key = f"{mock_service.prefixes['session']}{session_id}:state"
            mock_get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_get_session_state_not_found(self, mock_service):
        """Test session state retrieval when not found."""
        with patch.object(mock_service, "_get_json", return_value=None) as mock_get:
            result = await mock_service.get_session_state("nonexistent")

            assert result is None
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_session_metadata_success(self, mock_service):
        """Test successful session metadata caching."""
        session_id = "session123"
        metadata = {"created_at": "2023-01-01T00:00:00Z", "expires_at": "2023-01-02T00:00:00Z"}

        with patch.object(mock_service, "_set_json", return_value=True) as mock_set:
            result = await mock_service.set_session_metadata(session_id, metadata, ttl=1800)

            assert result is True
            expected_key = f"{mock_service.prefixes['session']}{session_id}:metadata"
            mock_set.assert_called_once_with(expected_key, metadata, 1800)

    @pytest.mark.asyncio
    async def test_get_session_metadata_success(self, mock_service):
        """Test successful session metadata retrieval."""
        session_id = "session123"
        expected_metadata = {
            "created_at": "2023-01-01T00:00:00Z",
            "expires_at": "2023-01-02T00:00:00Z",
        }

        with patch.object(mock_service, "_get_json", return_value=expected_metadata) as mock_get:
            result = await mock_service.get_session_metadata(session_id)

            assert result == expected_metadata
            expected_key = f"{mock_service.prefixes['session']}{session_id}:metadata"
            mock_get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_set_user_data_success(self, mock_service):
        """Test successful user data caching."""
        user_id = "user123"
        user_data = {"username": "testuser", "email": "test@example.com"}

        with patch.object(mock_service, "_set_encrypted_json", return_value=True) as mock_set:
            result = await mock_service.set_user_data(user_id, user_data, ttl=1800)

            assert result is True
            expected_key = f"{mock_service.prefixes['user']}{user_id}:data"
            mock_set.assert_called_once_with(expected_key, user_data, 1800)

    @pytest.mark.asyncio
    async def test_get_user_data_success(self, mock_service):
        """Test successful user data retrieval."""
        user_id = "user123"
        expected_user_data = {"username": "testuser", "email": "test@example.com"}

        with patch.object(
            mock_service, "_get_encrypted_json", return_value=expected_user_data
        ) as mock_get:
            result = await mock_service.get_user_data(user_id)

            assert result == expected_user_data
            expected_key = f"{mock_service.prefixes['user']}{user_id}:data"
            mock_get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_set_auth_token_success(self, mock_service):
        """Test successful auth token caching."""
        token_hash = "token123"
        token_data = {"user_id": "user123", "expires_at": "2023-01-01T00:00:00Z"}

        with patch.object(mock_service, "_set_json", return_value=True) as mock_set:
            result = await mock_service.set_auth_token(token_hash, token_data, ttl=3600)

            assert result is True
            expected_key = f"{mock_service.prefixes['auth']}{token_hash}"
            mock_set.assert_called_once_with(expected_key, token_data, 3600)

    @pytest.mark.asyncio
    async def test_get_auth_token_success(self, mock_service):
        """Test successful auth token retrieval."""
        token_hash = "token123"
        expected_token_data = {"user_id": "user123", "expires_at": "2023-01-01T00:00:00Z"}

        with patch.object(mock_service, "_get_json", return_value=expected_token_data) as mock_get:
            result = await mock_service.get_auth_token(token_hash)

            assert result == expected_token_data
            expected_key = f"{mock_service.prefixes['auth']}{token_hash}"
            mock_get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_set_task_result_success(self, mock_service):
        """Test successful task result caching."""
        task_id = "task123"
        result_data = {"status": "completed", "output": "test result"}

        with patch.object(mock_service, "_set_json", return_value=True) as mock_set:
            result = await mock_service.set_task_result(task_id, result_data, ttl=1800)

            assert result is True
            expected_key = f"{mock_service.prefixes['task']}{task_id}:result"
            mock_set.assert_called_once_with(expected_key, result_data, 1800)

    @pytest.mark.asyncio
    async def test_get_task_result_success(self, mock_service):
        """Test successful task result retrieval."""
        task_id = "task123"
        expected_result = {"status": "completed", "output": "test result"}

        with patch.object(mock_service, "_get_json", return_value=expected_result) as mock_get:
            result = await mock_service.get_task_result(task_id)

            assert result == expected_result
            expected_key = f"{mock_service.prefixes['task']}{task_id}:result"
            mock_get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_set_query_result_success(self, mock_service):
        """Test successful query result caching."""
        query_hash = "query123"
        query_result = {"data": ["item1", "item2"], "total": 2}

        with patch.object(mock_service, "_set_json", return_value=True) as mock_set:
            result = await mock_service.set_query_result(
                query_hash, query_result, ttl=900
            )  # 15 minutes

            assert result is True
            expected_key = f"{mock_service.prefixes['query']}{query_hash}"
            mock_set.assert_called_once_with(expected_key, query_result, 900)

    @pytest.mark.asyncio
    async def test_set_query_result_default_ttl(self, mock_service):
        """Test query result caching with default TTL."""
        query_hash = "query123"
        query_result = {"data": ["item1", "item2"], "total": 2}

        with patch.object(mock_service, "_set_json", return_value=True) as mock_set:
            result = await mock_service.set_query_result(query_hash, query_result)

            assert result is True
            expected_key = f"{mock_service.prefixes['query']}{query_hash}"
            mock_set.assert_called_once_with(
                expected_key, query_result, mock_service.default_ttl // 4
            )

    @pytest.mark.asyncio
    async def test_get_query_result_success(self, mock_service):
        """Test successful query result retrieval."""
        query_hash = "query123"
        expected_result = {"data": ["item1", "item2"], "total": 2}

        with patch.object(mock_service, "_get_json", return_value=expected_result) as mock_get:
            result = await mock_service.get_query_result(query_hash)

            assert result == expected_result
            expected_key = f"{mock_service.prefixes['query']}{query_hash}"
            mock_get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_set_api_response_success(self, mock_service):
        """Test successful API response caching."""
        endpoint = "/api/users"
        params_hash = "params123"
        response = {"users": [{"id": 1, "name": "User1"}, {"id": 2, "name": "User2"}]}

        with patch.object(mock_service, "_set_json", return_value=True) as mock_set:
            result = await mock_service.set_api_response(endpoint, params_hash, response, ttl=1800)

            assert result is True
            expected_key = f"{mock_service.prefixes['response']}{endpoint}:{params_hash}"
            mock_set.assert_called_once_with(expected_key, response, 1800)

    @pytest.mark.asyncio
    async def test_set_api_response_default_ttl(self, mock_service):
        """Test API response caching with default TTL."""
        endpoint = "/api/users"
        params_hash = "params123"
        response = {"users": [{"id": 1, "name": "User1"}, {"id": 2, "name": "User2"}]}

        with patch.object(mock_service, "_set_json", return_value=True) as mock_set:
            result = await mock_service.set_api_response(endpoint, params_hash, response)

            assert result is True
            expected_key = f"{mock_service.prefixes['response']}{endpoint}:{params_hash}"
            mock_set.assert_called_once_with(expected_key, response, mock_service.default_ttl // 2)

    @pytest.mark.asyncio
    async def test_get_api_response_success(self, mock_service):
        """Test successful API response retrieval."""
        endpoint = "/api/users"
        params_hash = "params123"
        expected_response = {"users": [{"id": 1, "name": "User1"}, {"id": 2, "name": "2"}]}

        with patch.object(mock_service, "_get_json", return_value=expected_response) as mock_get:
            result = await mock_service.get_api_response(endpoint, params_hash)

            assert result == expected_response
            expected_key = f"{mock_service.prefixes['response']}{endpoint}:{params_hash}"
            mock_get.assert_called_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_invalidate_session_cache_success(self, mock_service):
        """Test successful session cache invalidation."""
        session_id = "session123"

        with patch.object(mock_service.redis, "scan_iter") as mock_scan:
            mock_scan.return_value = [(b"session:session123:state", b"session:session123:metadata")]
            with patch.object(mock_service.redis, "delete", return_value=2) as mock_delete:
                result = await mock_service.invalidate_session_cache(session_id)

                assert result == 2
                mock_delete.assert_called_once_with(
                    b"session:session123:state", b"session:session123:metadata"
                )

    @pytest.mark.asyncio
    async def test_invalidate_session_cache_no_keys(self, mock_service):
        """Test session cache invalidation when no keys found."""
        session_id = "nonexistent"

        with patch.object(mock_service.redis, "scan_iter", return_value=[]) as mock_scan:
            with patch.object(mock_service.redis, "delete", return_value=0) as mock_delete:
                result = await mock_service.invalidate_session_cache(session_id)

                assert result == 0
                mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_user_cache_success(self, mock_service):
        """Test successful user cache invalidation."""
        user_id = "user123"

        with patch.object(mock_service.redis, "scan_iter") as mock_scan:
            mock_scan.return_value = [(b"user:user123:data", b"user:user123:metadata")]
            with patch.object(mock_service.redis, "delete", return_value=2) as mock_delete:
                result = await mock_service.invalidate_user_cache(user_id)

                assert result == 2
                mock_delete.assert_called_once_with(b"user:user123:data", b"user:user123:metadata")

    @pytest.mark.asyncio
    async def test_clear_expired_cache(self, mock_service):
        """Test clearing expired cache entries."""
        with patch.object(mock_service.redis, "scan_iter", return_value=[]) as mock_scan:
            result = await mock_service.clear_expired_cache()

            assert result == 0
            mock_scan.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, mock_service):
        """Test getting cache statistics."""
        mock_stats = {
            "used_memory": "10MB",
            "used_memory_peak": "15MB",
            "connected_clients": 5,
            "total_commands_processed": 1000,
            "cache_hits": 800,
            "cache_misses": 200,
        }

        with patch.object(mock_service.redis, "info", return_value=mock_stats) as mock_info:
            result = await mock_service.get_cache_stats()

            assert result["used_memory"] == "10MB"
            assert result["cache_hits"] == 800
            assert result["cache_misses"] == 200
            mock_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_encrypted_json_success(self, mock_service):
        """Test successful encrypted JSON setting."""
        key = "test_key"
        data = {"sensitive": "data"}

        with patch.object(
            mock_service.fernet, "encrypt", return_value=b"encrypted_data"
        ) as mock_encrypt, patch.object(mock_service.redis, "setex", return_value=True) as mock_set:
            result = await mock_service._set_encrypted_json(key, data, 1800)

            assert result is True
            mock_encrypt.assert_called_once_with(b"data")
            mock_set.assert_called_once_with(key, b"encrypted_data", 1800)

    @pytest.mark.asyncio
    async def test_set_encrypted_json_failure(self, mock_service):
        """Test encrypted JSON setting failure."""
        key = "test_key"
        data = {"sensitive": "data"}

        with patch.object(
            mock_service.fernet, "encrypt", side_effect=Exception("Encryption error")
        ):
            result = await mock_service._set_encrypted_json(key, data, 1800)

            assert result is False

    @pytest.mark.asyncio
    async def test_get_encrypted_json_success(self, mock_service):
        """Test successful encrypted JSON retrieval."""
        key = "test_key"
        expected_data = {"sensitive": "data"}

        with patch.object(mock_service.redis, "get", return_value=b"encrypted_data"), patch.object(
            mock_service.fernet, "decrypt", return_value=b'{"sensitive": "data"}'
        ):
            result = await mock_service._get_encrypted_json(key)

            assert result == expected_data

    @pytest.mark.asyncio
    async def test_get_encrypted_json_invalid_data(self, mock_service):
        """Test encrypted JSON retrieval with invalid data."""
        key = "test_key"

        with patch.object(mock_service.redis, "get", return_value=b"invalid_data"), patch.object(
            mock_service.fernet, "decrypt", side_effect=Exception("Decryption error")
        ):
            result = await mock_service._get_encrypted_json(key)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_encrypted_json_not_found(self, mock_service):
        """Test encrypted JSON retrieval when key not found."""
        key = "nonexistent_key"

        with patch.object(mock_service.redis, "get", return_value=None):
            result = await mock_service._get_encrypted_json(key)

            assert result is None

    @pytest.mark.asyncio
    async def test_set_json_success(self, mock_service):
        """Test successful JSON setting."""
        key = "test_key"
        data = {"test": "data"}

        with patch.object(mock_service.redis, "setex", return_value=True) as mock_set:
            result = await mock_service._set_json(key, data, 1800)

            assert result is True
            mock_set.assert_called_once_with(key, b'{"test": "data"}', 1800)

    @pytest.mark.asyncio
    async def test_set_json_failure(self, mock_service):
        """Test JSON setting failure."""
        key = "test_key"
        data = {"test": "data"}

        with patch("json.dumps", side_effect=Exception("JSON error")):
            result = await mock_service._set_json(key, data, 1800)

            assert result is False

    @pytest.mark.asyncio
    async def test_get_json_success(self, mock_service):
        """Test successful JSON retrieval."""
        key = "test_key"
        expected_data = {"test": "data"}

        with patch.object(mock_service.redis, "get", return_value=b'{"test": "data"}'):
            result = await mock_service._get_json(key)

            assert result == expected_data

    @pytest.mark.asyncio
    async def test_get_json_invalid_json(self, mock_service):
        """Test JSON retrieval with invalid JSON."""
        key = "test_key"

        with patch.object(mock_service.redis, "get", return_value=b"invalid_json"), patch(
            "json.loads", side_effect=Exception("JSON error")
        ):
            result = await mock_service._get_json(key)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_json_not_found(self, mock_service):
        """Test JSON retrieval when key not found."""
        key = "nonexistent"

        with patch.object(mock_service.redis, "get", return_value=None):
            result = await mock_service._get_json(key)

            assert result is None

    def test_edge_case_cache_service_with_different_ttl(self, mock_redis):
        """Test cache service with different default TTL."""
        service = CacheService(mock_redis, default_ttl=7200)

        assert service.default_ttl == 7200

    def test_edge_case_cache_service_with_no_redis(self):
        """Test cache service initialization without Redis client."""
        with pytest.raises(TypeError):
            CacheService(None)
