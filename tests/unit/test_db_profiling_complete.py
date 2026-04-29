"""
Additional unit tests for DBProfilingMiddleware to achieve 100% coverage.

Covers:
- Exception handling paths
- Edge cases in histogram calculations
- Empty data scenarios
- All branches in metrics recording
"""

from typing import Any, Awaitable, Callable, MutableMapping
from unittest.mock import MagicMock, patch

import pytest

from app.middleware.db_profiling import (
    DBProfilingMiddleware,
    record_cache_hit,
    record_cache_miss,
    record_query_timing,
)


class TestDBProfilingMiddlewareExceptions:
    """Test exception handling in DBProfilingMiddleware."""

    def test_dispatch_exception_handling(self) -> None:
        """Test that exceptions during dispatch are properly re-raised."""
        import asyncio

        async def mock_call_next(request: Any) -> Any:
            raise ValueError("App error")

        async def mock_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]
        mock_request = MagicMock()
        mock_request.url.path = "/test"
        mock_request.method = "GET"
        mock_request.headers = {}

        with pytest.raises(ValueError, match="App error"):
            asyncio.run(middleware.dispatch(mock_request, mock_call_next))

    def test_dispatch_disabled_exception_handling(self) -> None:
        """Test that exceptions are re-raised when disabled."""
        import asyncio

        async def mock_call_next(request: Any) -> Any:
            raise RuntimeError("Disabled app error")

        async def mock_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=False)  # type: ignore[arg-type]
        mock_request = MagicMock()

        with pytest.raises(RuntimeError, match="Disabled app error"):
            asyncio.run(middleware.dispatch(mock_request, mock_call_next))


class TestRecordQueryTimingExceptions:
    """Test exception handling in record_query_timing."""

    def test_record_query_timing_no_context(self) -> None:
        """Test that record_query_timing handles missing context."""
        # Should not raise when context variable not set
        record_query_timing("hash123", "SELECT * FROM users", 10.5, 5)
        # If we get here, exception was handled

    def test_record_query_timing_exception_silent(self) -> None:
        """Test that record_query_timing silently handles exceptions."""
        # This should not raise any exception
        record_query_timing("hash", "query", 1.0)


class TestRecordCacheHitMissExceptions:
    """Test exception handling in cache hit/miss recording."""

    def test_record_cache_hit_no_context(self) -> None:
        """Test that record_cache_hit handles missing context."""
        record_cache_hit()
        # Should not raise

    def test_record_cache_miss_no_context(self) -> None:
        """Test that record_cache_miss handles missing context."""
        record_cache_miss()
        # Should not raise


class TestDBProfilingMiddlewareMetricsEmptyData:
    """Test metrics calculation with empty data."""

    def test_get_query_histogram_empty(self) -> None:
        """Test histogram with no data."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]

        result = middleware.get_query_histogram("/unknown")

        assert result["count"] == 0
        assert result["p50"] == 0
        assert result["p95"] == 0
        assert result["p99"] == 0
        assert result["avg"] == 0

    def test_get_payload_histogram_empty(self) -> None:
        """Test payload histogram with no data."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]

        result = middleware.get_payload_histogram("GET /unknown")

        assert result["count"] == 0
        assert result["request_sizes"] == {}
        assert result["response_sizes"] == {}

    def test_get_cache_metrics_empty(self) -> None:
        """Test cache metrics with no data."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]

        result = middleware.get_cache_metrics("/unknown")

        assert result["hits"] == 0
        assert result["misses"] == 0
        assert result["hit_ratio"] == 0.0

    def test_get_cache_metrics_no_endpoint(self) -> None:
        """Test getting all cache metrics without endpoint filter."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]

        # Add some metrics first
        middleware._record_cache_metrics("/test", {"hits": 5, "misses": 5})

        result = middleware.get_cache_metrics()

        assert "/test" in result
        assert result["/test"]["hits"] == 5
        assert result["/test"]["misses"] == 5
        assert result["/test"]["hit_ratio"] == 0.5


class TestDBProfilingMiddlewareQueryHistogramCalculations:
    """Test query histogram calculations."""

    def test_get_query_histogram_with_data(self) -> None:
        """Test histogram calculations with actual data."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]

        # Add timing data
        middleware.query_histograms["/test"] = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500]

        result = middleware.get_query_histogram("/test")

        assert result["count"] == 10
        assert result["p50"] > 0
        assert result["p95"] > 0
        assert result["p99"] > 0
        assert result["avg"] > 0
        assert len(result["buckets"]) > 0

    def test_get_query_histogram_large_values(self) -> None:
        """Test histogram with large timing values."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]

        # Add timing data that exceeds largest bucket
        middleware.query_histograms["/test"] = [6000, 7000, 8000]

        result = middleware.get_query_histogram("/test")

        assert result["count"] == 3
        assert result["buckets"][">=5000ms"] == 3


class TestDBProfilingMiddlewarePayloadHistogramCalculations:
    """Test payload histogram calculations."""

    def test_get_payload_histogram_with_data(self) -> None:
        """Test payload histogram with actual data."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]

        from app.middleware.db_profiling import PayloadMetrics

        metrics = [
            PayloadMetrics(endpoint="GET /test", request_size_bytes=100, response_size_bytes=200),
            PayloadMetrics(
                endpoint="GET /test", request_size_bytes=5000, response_size_bytes=10000
            ),
            PayloadMetrics(
                endpoint="GET /test", request_size_bytes=2000000, response_size_bytes=3000000
            ),
        ]
        middleware.payload_histograms["GET /test"] = metrics

        result = middleware.get_payload_histogram("GET /test")

        assert result["count"] == 3
        assert "request_sizes" in result
        assert "response_sizes" in result
        assert result["request_sizes"]["max"] == 2000000
        assert result["response_sizes"]["max"] == 3000000


class TestDBProfilingMiddlewareNormalization:
    """Test endpoint normalization."""

    def test_normalize_endpoint_with_id(self) -> None:
        """Test normalization replaces IDs."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]

        result = middleware._normalize_endpoint("/v1/users/550e8400-e29b-41d4-a716-446655440000")
        assert result == "/v1/users/{id}"

    def test_normalize_endpoint_with_numeric_id(self) -> None:
        """Test normalization replaces numeric IDs."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]

        result = middleware._normalize_endpoint("/v1/users/12345")
        assert result == "/v1/users/{id}"

    def test_normalize_endpoint_with_task_prefix(self) -> None:
        """Test normalization replaces task_ prefixed IDs."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True)  # type: ignore[arg-type]

        result = middleware._normalize_endpoint("/v1/tasks/task_abc123")
        assert result == "/v1/tasks/{id}"


class TestDBProfilingMiddlewareSlowQueryLogging:
    """Test slow query logging."""

    def test_record_query_metrics_slow_query(self) -> None:
        """Test logging of slow queries."""

        async def mock_app(scope: dict[str, Any], receive: MagicMock, send: MagicMock) -> None:
            pass

        middleware = DBProfilingMiddleware(mock_app, enabled=True, slow_query_threshold_ms=50.0)  # type: ignore[arg-type]

        with patch("app.middleware.db_profiling.logger") as mock_logger:
            middleware._record_query_metrics(
                "/test",
                [{"duration_ms": 100.0, "query_text": "SELECT * FROM very_large_table"}],
            )

            mock_logger.warning.assert_called_once()
            assert "Slow query" in mock_logger.warning.call_args[0][0]


class TestDBProfilingMiddlewareLargePayloadLogging:
    """Test large payload logging."""

    def test_record_payload_metrics_large_payload(self) -> None:
        """Test logging of large payloads."""

        async def mock_app(
            scope: MutableMapping[str, Any],
            receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
            send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
        ) -> None:
            pass

        middleware = DBProfilingMiddleware(
            mock_app, enabled=True, large_payload_threshold_bytes=1000
        )

        with patch("app.middleware.db_profiling.logger") as mock_logger:
            middleware._record_payload_metrics("/test", "GET", 5000, 10000)

            # Both request and response exceed threshold
            assert mock_logger.warning.call_count == 2
