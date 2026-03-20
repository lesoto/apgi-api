"""
Unit tests for CacheService.

Covers cache operations, TTL handling, and Redis interactions.
Requirements: 2.8
"""

import json

import pytest
from unittest.mock import AsyncMock, patch

from app.services.cache_service import (
    CacheService,
    init_cache_service,
    get_cache_service,
)


@pytest.fixture
def mock_redis():
    """Async Redis client mock."""
    client = AsyncMock()

    # scan_iter is an async generator — default to empty
    async def _empty_scan(pattern):
        return
        yield  # make it an async generator

    client.scan_iter = _empty_scan
    return client


@pytest.fixture
def service(mock_redis):
    """CacheService instance with AsyncMock redis."""
    return CacheService(mock_redis, default_ttl=3600)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    def test_stores_redis_and_ttl(self, mock_redis):
        svc = CacheService(mock_redis, default_ttl=1800)
        assert svc.redis is mock_redis
        assert svc.default_ttl == 1800

    def test_default_ttl_is_3600(self, mock_redis):
        svc = CacheService(mock_redis)
        assert svc.default_ttl == 3600

    def test_prefixes_defined(self, service):
        assert service.prefixes["session"] == "session:"
        assert service.prefixes["user"] == "user:"
        assert service.prefixes["auth"] == "auth:"
        assert service.prefixes["task"] == "task:"
        assert service.prefixes["query"] == "query:"
        assert service.prefixes["response"] == "response:"

    def test_fernet_created(self, service):
        assert service.fernet is not None


# ---------------------------------------------------------------------------
# Global helpers
# ---------------------------------------------------------------------------


class TestGlobalHelpers:
    def test_init_cache_service_sets_global(self, mock_redis):
        import app.services.cache_service as mod

        mod.cache_service = None
        result = init_cache_service(mock_redis, default_ttl=7200)
        assert result is mod.cache_service
        assert result.default_ttl == 7200

    def test_get_cache_service_none_when_not_init(self):
        import app.services.cache_service as mod

        mod.cache_service = None
        assert get_cache_service() is None

    def test_get_cache_service_returns_instance(self, mock_redis):
        init_cache_service(mock_redis)
        assert get_cache_service() is not None


# ---------------------------------------------------------------------------
# _set_json / _get_json
# ---------------------------------------------------------------------------


class TestSetGetJson:
    @pytest.mark.asyncio
    async def test_set_json_calls_setex(self, service, mock_redis):
        mock_redis.setex = AsyncMock(return_value=True)
        result = await service._set_json("mykey", {"a": 1}, 60)
        assert result is True
        mock_redis.setex.assert_awaited_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "mykey"
        assert args[1] == 60
        assert json.loads(args[2]) == {"a": 1}

    @pytest.mark.asyncio
    async def test_set_json_returns_false_on_exception(self, service, mock_redis):
        mock_redis.setex = AsyncMock(side_effect=Exception("redis down"))
        result = await service._set_json("k", {}, 60)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_json_returns_parsed_data(self, service, mock_redis):
        mock_redis.get = AsyncMock(return_value=b'{"x": 42}')
        result = await service._get_json("mykey")
        assert result == {"x": 42}

    @pytest.mark.asyncio
    async def test_get_json_returns_none_when_missing(self, service, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        result = await service._get_json("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_json_returns_none_on_exception(self, service, mock_redis):
        mock_redis.get = AsyncMock(side_effect=Exception("err"))
        result = await service._get_json("k")
        assert result is None


# ---------------------------------------------------------------------------
# _set_encrypted_json / _get_encrypted_json
# ---------------------------------------------------------------------------


class TestEncryptedJson:
    @pytest.mark.asyncio
    async def test_set_encrypted_json_encrypts_and_stores(self, service, mock_redis):
        mock_redis.setex = AsyncMock(return_value=True)
        result = await service._set_encrypted_json("ekey", {"secret": "val"}, 120)
        assert result is True
        mock_redis.setex.assert_awaited_once()
        key, ttl, payload = mock_redis.setex.call_args[0]
        assert key == "ekey"
        assert ttl == 120
        # payload should be bytes (encrypted)
        assert isinstance(payload, bytes)

    @pytest.mark.asyncio
    async def test_set_encrypted_json_returns_false_on_error(self, service, mock_redis):
        mock_redis.setex = AsyncMock(side_effect=Exception("fail"))
        result = await service._set_encrypted_json("k", {}, 60)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_encrypted_json_round_trip(self, service, mock_redis):
        """Encrypt then decrypt should return original data."""
        data = {"user": "alice", "role": "admin"}
        encrypted = service.fernet.encrypt(json.dumps(data).encode())
        mock_redis.get = AsyncMock(return_value=encrypted)
        result = await service._get_encrypted_json("ekey")
        assert result == data

    @pytest.mark.asyncio
    async def test_get_encrypted_json_returns_none_when_missing(self, service, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        result = await service._get_encrypted_json("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_encrypted_json_returns_none_on_bad_data(self, service, mock_redis):
        mock_redis.get = AsyncMock(return_value=b"not-valid-fernet-token")
        result = await service._get_encrypted_json("k")
        assert result is None


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------


class TestSessionState:
    @pytest.mark.asyncio
    async def test_set_session_state_uses_correct_key(self, service):
        with patch.object(service, "_set_json", new=AsyncMock(return_value=True)) as m:
            await service.set_session_state("sess1", {"k": "v"}, ttl=300)
            m.assert_awaited_once_with("session:sess1:state", {"k": "v"}, 300)

    @pytest.mark.asyncio
    async def test_set_session_state_default_ttl(self, service):
        with patch.object(service, "_set_json", new=AsyncMock(return_value=True)) as m:
            await service.set_session_state("sess1", {})
            _, _, ttl = m.call_args[0]
            assert ttl == service.default_ttl

    @pytest.mark.asyncio
    async def test_get_session_state_uses_correct_key(self, service):
        with patch.object(service, "_get_json", new=AsyncMock(return_value={"k": "v"})) as m:
            result = await service.get_session_state("sess1")
            m.assert_awaited_once_with("session:sess1:state")
            assert result == {"k": "v"}

    @pytest.mark.asyncio
    async def test_get_session_state_returns_none_when_missing(self, service):
        with patch.object(service, "_get_json", new=AsyncMock(return_value=None)):
            result = await service.get_session_state("missing")
            assert result is None


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------


class TestSessionMetadata:
    @pytest.mark.asyncio
    async def test_set_session_metadata_uses_correct_key(self, service):
        with patch.object(service, "_set_json", new=AsyncMock(return_value=True)) as m:
            await service.set_session_metadata("sess1", {"meta": True}, ttl=600)
            key = m.call_args[0][0]
            assert key == "session:sess1:metadata"

    @pytest.mark.asyncio
    async def test_get_session_metadata_uses_correct_key(self, service):
        with patch.object(service, "_get_json", new=AsyncMock(return_value={"meta": True})) as m:
            result = await service.get_session_metadata("sess1")
            m.assert_awaited_once_with("session:sess1:metadata")
            assert result == {"meta": True}


# ---------------------------------------------------------------------------
# User data (encrypted)
# ---------------------------------------------------------------------------


class TestUserData:
    @pytest.mark.asyncio
    async def test_set_user_data_uses_encrypted_json(self, service):
        with patch.object(service, "_set_encrypted_json", new=AsyncMock(return_value=True)) as m:
            await service.set_user_data("u1", {"email": "a@b.com"}, ttl=900)
            key = m.call_args[0][0]
            assert key == "user:u1:data"

    @pytest.mark.asyncio
    async def test_get_user_data_uses_encrypted_json(self, service):
        with patch.object(
            service, "_get_encrypted_json", new=AsyncMock(return_value={"email": "a@b.com"})
        ) as m:
            result = await service.get_user_data("u1")
            m.assert_awaited_once_with("user:u1:data")
            assert result == {"email": "a@b.com"}


# ---------------------------------------------------------------------------
# Auth token
# ---------------------------------------------------------------------------


class TestAuthToken:
    @pytest.mark.asyncio
    async def test_set_auth_token_uses_correct_key(self, service):
        with patch.object(service, "_set_json", new=AsyncMock(return_value=True)) as m:
            await service.set_auth_token("hash123", {"uid": "u1"}, ttl=3600)
            m.assert_awaited_once_with("auth:hash123", {"uid": "u1"}, 3600)

    @pytest.mark.asyncio
    async def test_get_auth_token_uses_correct_key(self, service):
        with patch.object(service, "_get_json", new=AsyncMock(return_value={"uid": "u1"})) as m:
            result = await service.get_auth_token("hash123")
            m.assert_awaited_once_with("auth:hash123")
            assert result == {"uid": "u1"}


# ---------------------------------------------------------------------------
# Task result
# ---------------------------------------------------------------------------


class TestTaskResult:
    @pytest.mark.asyncio
    async def test_set_task_result_uses_correct_key(self, service):
        with patch.object(service, "_set_json", new=AsyncMock(return_value=True)) as m:
            await service.set_task_result("t1", {"out": "done"}, ttl=1800)
            key = m.call_args[0][0]
            assert key == "task:t1:result"

    @pytest.mark.asyncio
    async def test_get_task_result_uses_correct_key(self, service):
        with patch.object(service, "_get_json", new=AsyncMock(return_value={"out": "done"})) as m:
            result = await service.get_task_result("t1")
            m.assert_awaited_once_with("task:t1:result")
            assert result == {"out": "done"}


# ---------------------------------------------------------------------------
# Query result
# ---------------------------------------------------------------------------


class TestQueryResult:
    @pytest.mark.asyncio
    async def test_set_query_result_default_ttl_is_quarter(self, service):
        with patch.object(service, "_set_json", new=AsyncMock(return_value=True)) as m:
            await service.set_query_result("qhash", [1, 2, 3])
            _, _, ttl = m.call_args[0]
            assert ttl == service.default_ttl // 4

    @pytest.mark.asyncio
    async def test_set_query_result_custom_ttl(self, service):
        with patch.object(service, "_set_json", new=AsyncMock(return_value=True)) as m:
            await service.set_query_result("qhash", [1, 2, 3], ttl=500)
            _, _, ttl = m.call_args[0]
            assert ttl == 500

    @pytest.mark.asyncio
    async def test_get_query_result_uses_correct_key(self, service):
        with patch.object(service, "_get_json", new=AsyncMock(return_value=[1, 2])) as m:
            result = await service.get_query_result("qhash")
            m.assert_awaited_once_with("query:qhash")
            assert result == [1, 2]


# ---------------------------------------------------------------------------
# API response
# ---------------------------------------------------------------------------


class TestApiResponse:
    @pytest.mark.asyncio
    async def test_set_api_response_default_ttl_is_half(self, service):
        with patch.object(service, "_set_json", new=AsyncMock(return_value=True)) as m:
            await service.set_api_response("/v1/users", "p1", {"data": []})
            _, _, ttl = m.call_args[0]
            assert ttl == service.default_ttl // 2

    @pytest.mark.asyncio
    async def test_set_api_response_key_format(self, service):
        with patch.object(service, "_set_json", new=AsyncMock(return_value=True)) as m:
            await service.set_api_response("/v1/users", "p1", {}, ttl=100)
            key = m.call_args[0][0]
            assert key == "response:/v1/users:p1"

    @pytest.mark.asyncio
    async def test_get_api_response_uses_correct_key(self, service):
        with patch.object(service, "_get_json", new=AsyncMock(return_value={"data": []})) as m:
            result = await service.get_api_response("/v1/users", "p1")
            m.assert_awaited_once_with("response:/v1/users:p1")
            assert result == {"data": []}


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------


class TestCacheInvalidation:
    @pytest.mark.asyncio
    async def test_invalidate_session_cache_deletes_matching_keys(self, service, mock_redis):
        keys = [b"session:s1:state", b"session:s1:metadata"]

        async def _scan(pattern):
            for k in keys:
                yield k

        mock_redis.scan_iter = _scan
        mock_redis.delete = AsyncMock(return_value=2)

        result = await service.invalidate_session_cache("s1")

        assert result == 2
        mock_redis.delete.assert_awaited_once_with(*keys)

    @pytest.mark.asyncio
    async def test_invalidate_session_cache_returns_0_when_no_keys(self, service, mock_redis):
        async def _empty(pattern):
            return
            yield

        mock_redis.scan_iter = _empty
        mock_redis.delete = AsyncMock()

        result = await service.invalidate_session_cache("s1")

        assert result == 0
        mock_redis.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalidate_user_cache_deletes_matching_keys(self, service, mock_redis):
        keys = [b"user:u1:data"]

        async def _scan(pattern):
            for k in keys:
                yield k

        mock_redis.scan_iter = _scan
        mock_redis.delete = AsyncMock(return_value=1)

        result = await service.invalidate_user_cache("u1")

        assert result == 1
        mock_redis.delete.assert_awaited_once_with(*keys)

    @pytest.mark.asyncio
    async def test_invalidate_user_cache_returns_0_when_no_keys(self, service, mock_redis):
        async def _empty(pattern):
            return
            yield

        mock_redis.scan_iter = _empty
        mock_redis.delete = AsyncMock()

        result = await service.invalidate_user_cache("u1")

        assert result == 0

    @pytest.mark.asyncio
    async def test_clear_expired_cache_returns_0(self, service):
        """Redis handles expiry automatically; this method always returns 0."""
        result = await service.clear_expired_cache()
        assert result == 0


# ---------------------------------------------------------------------------
# Cache stats
# ---------------------------------------------------------------------------


class TestCacheStats:
    @pytest.mark.asyncio
    async def test_get_cache_stats_returns_key_counts(self, service, mock_redis):
        async def _scan(pattern):
            # yield 2 keys for every prefix
            yield b"key1"
            yield b"key2"

        mock_redis.scan_iter = _scan
        mock_redis.info = AsyncMock(return_value={"used_memory": 1024, "maxmemory": 0})

        stats = await service.get_cache_stats()

        # 6 prefixes × 2 keys each
        for prefix_name in service.prefixes:
            assert stats[f"{prefix_name}_keys"] == 2

        assert stats["redis_used_memory"] == 1024
