"""
Unit tests for DBProfilingMiddleware covering query timing, payload metrics, and cache stats.
Requirements: 4.7, 5.1
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestDBProfilingMiddlewareDisabled:
    """Test DBProfilingMiddleware when disabled."""

    def test_dispatch_disabled_passes_through(self) -> None:
        """When disabled, middleware passes request through without profiling."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict[str, bool]:
            return {"ok": True}

        app.add_middleware(DBProfilingMiddleware, enabled=False)

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert "X-Query-Count" not in response.headers

    def test_init_disabled_no_logging(self) -> None:
        """When disabled, no profiling setup occurs."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        mock_app = MagicMock()
        middleware = DBProfilingMiddleware(mock_app, enabled=False)

        assert middleware.enabled is False


class TestDBProfilingMiddlewareEnabled:
    """Test DBProfilingMiddleware when enabled."""

    def test_dispatch_enabled_adds_profiling_headers(self) -> None:
        """When enabled, dispatch adds profiling headers."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        app = FastAPI()

        @app.get("/test")
        async def test_route() -> dict[str, bool]:
            return {"ok": True}

        app.add_middleware(DBProfilingMiddleware, enabled=True)

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Query-Count" in response.headers
        assert "X-Cache-Hits" in response.headers
        assert "X-Cache-Misses" in response.headers

    def test_init_enabled_with_custom_thresholds(self) -> None:
        """Initialize with custom threshold values."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        mock_app = MagicMock()
        middleware = DBProfilingMiddleware(
            mock_app,
            enabled=True,
            slow_query_threshold_ms=50.0,
            large_payload_threshold_bytes=50000,
        )

        assert middleware.enabled is True
        assert middleware.slow_query_threshold_ms == 50.0
        assert middleware.large_payload_threshold_bytes == 50000


class TestQueryMetrics:
    """Test QueryMetrics dataclass."""

    def test_query_metrics_creation(self) -> None:
        """Test creating QueryMetrics instance."""
        from app.middleware.db_profiling import QueryMetrics

        metrics = QueryMetrics(
            query_hash="abc123",
            query_text="SELECT * FROM users",
            duration_ms=25.5,
            rows_returned=10,
            endpoint="/v1/users",
        )

        assert metrics.query_hash == "abc123"
        assert metrics.query_text == "SELECT * FROM users"
        assert metrics.duration_ms == 25.5
        assert metrics.rows_returned == 10
        assert metrics.endpoint == "/v1/users"
        assert metrics.timestamp > 0


class TestPayloadMetrics:
    """Test PayloadMetrics dataclass."""

    def test_payload_metrics_creation(self) -> None:
        """Test creating PayloadMetrics instance."""
        from app.middleware.db_profiling import PayloadMetrics

        metrics = PayloadMetrics(
            endpoint="POST /v1/users",
            request_size_bytes=1000,
            response_size_bytes=5000,
        )

        assert metrics.endpoint == "POST /v1/users"
        assert metrics.request_size_bytes == 1000
        assert metrics.response_size_bytes == 5000
        assert metrics.timestamp > 0


class TestCacheMetrics:
    """Test CacheMetrics dataclass and hit ratio calculation."""

    def test_cache_metrics_creation(self) -> None:
        """Test creating CacheMetrics instance."""
        from app.middleware.db_profiling import CacheMetrics

        metrics = CacheMetrics(endpoint="/v1/users")

        assert metrics.endpoint == "/v1/users"
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.total_lookups == 0

    def test_hit_ratio_zero_lookups(self) -> None:
        """Hit ratio is 0 when no lookups."""
        from app.middleware.db_profiling import CacheMetrics

        metrics = CacheMetrics(endpoint="/v1/users")
        assert metrics.hit_ratio == 0.0

    def test_hit_ratio_calculation(self) -> None:
        """Hit ratio calculated correctly."""
        from app.middleware.db_profiling import CacheMetrics

        metrics = CacheMetrics(endpoint="/v1/users", hits=8, misses=2, total_lookups=10)
        assert metrics.hit_ratio == 0.8


class TestEndpointNormalization:
    """Test endpoint path normalization."""

    def test_normalize_endpoint_uuid(self) -> None:
        """Normalize UUID in path."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        result = middleware._normalize_endpoint("/v1/users/550e8400-e29b-41d4-a716-446655440000")
        assert result == "/v1/users/{id}"

    def test_normalize_endpoint_numeric_id(self) -> None:
        """Normalize numeric ID in path."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        result = middleware._normalize_endpoint("/v1/users/12345")
        assert result == "/v1/users/{id}"

    def test_normalize_endpoint_task_id(self) -> None:
        """Normalize task_ prefix ID in path."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        result = middleware._normalize_endpoint("/v1/tasks/task_abc123")
        assert result == "/v1/tasks/{id}"

    def test_normalize_endpoint_no_id(self) -> None:
        """Path without ID remains unchanged."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        result = middleware._normalize_endpoint("/v1/users")
        assert result == "/v1/users"


class TestLooksLikeId:
    """Test ID detection in path segments."""

    def test_looks_like_id_uuid(self) -> None:
        """Detect UUID as ID."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        assert middleware._looks_like_id("550e8400-e29b-41d4-a716-446655440000") is True

    def test_looks_like_id_numeric(self) -> None:
        """Detect numeric string as ID."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        assert middleware._looks_like_id("12345") is True

    def test_looks_like_id_task_prefix(self) -> None:
        """Detect task_ prefix as ID."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        assert middleware._looks_like_id("task_abc123") is True

    def test_looks_like_id_regular_string(self) -> None:
        """Regular string not detected as ID."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        assert middleware._looks_like_id("users") is False


class TestRecordPayloadMetrics:
    """Test payload metrics recording."""

    def test_record_payload_metrics(self) -> None:
        """Record payload metrics for endpoint."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        middleware._record_payload_metrics("/v1/users", "POST", 1000, 5000)

        assert "POST /v1/users" in middleware.payload_histograms
        assert len(middleware.payload_histograms["POST /v1/users"]) == 1

    def test_record_payload_metrics_limits_size(self) -> None:
        """Keep only last 1000 entries per endpoint."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)

        for i in range(1005):
            middleware._record_payload_metrics("/v1/users", "POST", i, i * 2)

        assert len(middleware.payload_histograms["POST /v1/users"]) == 1000


class TestRecordQueryMetrics:
    """Test query metrics recording."""

    def test_record_query_metrics(self) -> None:
        """Record query metrics for endpoint."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        query_timings = [
            {"query_hash": "abc", "query_text": "SELECT 1", "duration_ms": 10.0, "rows_returned": 1}
        ]
        middleware._record_query_metrics("/v1/users", query_timings)

        assert "/v1/users" in middleware.query_histograms
        assert len(middleware.query_histograms["/v1/users"]) == 1

    def test_record_query_metrics_limits_size(self) -> None:
        """Keep only last 1000 entries per endpoint."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        query_timings = [
            {
                "query_hash": f"abc{i}",
                "query_text": "SELECT 1",
                "duration_ms": float(i),
                "rows_returned": 1,
            }
            for i in range(1005)
        ]
        middleware._record_query_metrics("/v1/users", query_timings)

        assert len(middleware.query_histograms["/v1/users"]) == 1000


class TestRecordCacheMetrics:
    """Test cache metrics recording."""

    def test_record_cache_metrics_new_endpoint(self) -> None:
        """Create new CacheMetrics for new endpoint."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        middleware._record_cache_metrics("/v1/users", {"hits": 5, "misses": 2})

        assert "/v1/users" in middleware.cache_metrics
        assert middleware.cache_metrics["/v1/users"].hits == 5
        assert middleware.cache_metrics["/v1/users"].misses == 2

    def test_record_cache_metrics_accumulates(self) -> None:
        """Accumulate metrics for existing endpoint."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        middleware._record_cache_metrics("/v1/users", {"hits": 5, "misses": 2})
        middleware._record_cache_metrics("/v1/users", {"hits": 3, "misses": 1})

        assert middleware.cache_metrics["/v1/users"].hits == 8
        assert middleware.cache_metrics["/v1/users"].misses == 3


class TestGetQueryHistogram:
    """Test query histogram retrieval."""

    def test_get_query_histogram_empty(self) -> None:
        """Return empty histogram for unknown endpoint."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        result = middleware.get_query_histogram("/v1/unknown")

        assert result["count"] == 0
        assert result["p50"] == 0
        assert result["p95"] == 0
        assert result["p99"] == 0

    def test_get_query_histogram_with_data(self) -> None:
        """Return histogram with percentiles."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        middleware.query_histograms["/v1/users"] = [1, 5, 10, 25, 50, 100, 250, 500, 1000]

        result = middleware.get_query_histogram("/v1/users")

        assert result["count"] == 9
        assert result["p50"] == 50
        assert result["p95"] == 1000
        assert result["p99"] == 1000
        assert result["avg"] == pytest.approx(215.67, abs=0.01)  # Approximate


class TestGetPayloadHistogram:
    """Test payload histogram retrieval."""

    def test_get_payload_histogram_empty(self) -> None:
        """Return empty histogram for unknown endpoint."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        result = middleware.get_payload_histogram("GET /v1/unknown")

        assert result["count"] == 0

    def test_get_payload_histogram_with_data(self) -> None:
        """Return histogram with request/response sizes."""
        from app.middleware.db_profiling import DBProfilingMiddleware, PayloadMetrics

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        middleware.payload_histograms["GET /v1/users"] = [
            PayloadMetrics("GET /v1/users", 100, 1000),
            PayloadMetrics("GET /v1/users", 200, 2000),
        ]

        result = middleware.get_payload_histogram("GET /v1/users")

        assert result["count"] == 2
        assert result["request_sizes"]["avg"] == 150
        assert result["response_sizes"]["avg"] == 1500


class TestGetCacheMetrics:
    """Test cache metrics retrieval."""

    def test_get_cache_metrics_single_endpoint(self) -> None:
        """Get metrics for specific endpoint."""
        from app.middleware.db_profiling import CacheMetrics, DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        middleware.cache_metrics["/v1/users"] = CacheMetrics(
            "/v1/users", hits=10, misses=2, total_lookups=12
        )

        result = middleware.get_cache_metrics("/v1/users")

        assert result["hits"] == 10
        assert result["misses"] == 2
        assert result["hit_ratio"] == 10 / 12

    def test_get_cache_metrics_all_endpoints(self) -> None:
        """Get metrics for all endpoints."""
        from app.middleware.db_profiling import CacheMetrics, DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        middleware.cache_metrics["/v1/users"] = CacheMetrics(
            "/v1/users", hits=10, misses=2, total_lookups=12
        )
        middleware.cache_metrics["/v1/tasks"] = CacheMetrics(
            "/v1/tasks", hits=5, misses=5, total_lookups=10
        )

        result = middleware.get_cache_metrics()

        assert "/v1/users" in result
        assert "/v1/tasks" in result

    def test_get_cache_metrics_unknown_endpoint(self) -> None:
        """Return zero metrics for unknown endpoint."""
        from app.middleware.db_profiling import DBProfilingMiddleware

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        result = middleware.get_cache_metrics("/v1/unknown")

        assert result["hits"] == 0
        assert result["misses"] == 0
        assert result["hit_ratio"] == 0.0


class TestGetAllMetrics:
    """Test retrieving all metrics."""

    def test_get_all_metrics(self) -> None:
        """Return all profiling metrics."""
        from app.middleware.db_profiling import CacheMetrics, DBProfilingMiddleware, PayloadMetrics

        middleware = DBProfilingMiddleware(MagicMock(), enabled=True)
        middleware.query_histograms["/v1/users"] = [1, 5, 10]
        middleware.payload_histograms["GET /v1/users"] = [
            PayloadMetrics("GET /v1/users", 100, 1000)
        ]
        middleware.cache_metrics["/v1/users"] = CacheMetrics(
            "/v1/users", hits=5, misses=1, total_lookups=6
        )

        result = middleware.get_all_metrics()

        assert "query_histograms" in result
        assert "payload_histograms" in result
        assert "cache_metrics" in result


class TestRecordQueryTiming:
    """Test global record_query_timing function."""

    def test_record_query_timing_with_context(self) -> None:
        """Record query timing when context available."""
        from app.middleware.db_profiling import query_timings_var, record_query_timing

        # Set up context
        query_timings_var.set([])

        record_query_timing("hash1", "SELECT 1", 10.0, 1)

        timings = query_timings_var.get([])
        assert len(timings) == 1
        assert timings[0]["query_hash"] == "hash1"


class TestRecordCacheHit:
    """Test global record_cache_hit function."""

    def test_record_cache_hit_with_context(self) -> None:
        """Record cache hit when context available."""
        from app.middleware.db_profiling import cache_stats_var, record_cache_hit

        # Set up context
        cache_stats_var.set({"hits": 0, "misses": 0})

        record_cache_hit()

        stats = cache_stats_var.get({})
        assert stats["hits"] == 1


class TestRecordCacheMiss:
    """Test global record_cache_miss function."""

    def test_record_cache_miss_with_context(self) -> None:
        """Record cache miss when context available."""
        from app.middleware.db_profiling import cache_stats_var, record_cache_miss

        # Set up context
        cache_stats_var.set({"hits": 0, "misses": 0})

        record_cache_miss()

        stats = cache_stats_var.get({})
        assert stats["misses"] == 1


class TestGlobalMiddlewareInstance:
    """Test global db_profiling_middleware instance."""

    def test_global_instance_initially_none(self) -> None:
        """Global instance starts as None."""
        from app.middleware.db_profiling import db_profiling_middleware

        assert db_profiling_middleware is None
