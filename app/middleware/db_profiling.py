"""
Database Profiling Middleware

Provides detailed database query profiling, payload size tracking, and
cache hit ratio metrics by endpoint for performance dashboards.
"""

import time
import logging
from typing import Any, Callable, Dict, List, Optional
from contextvars import ContextVar
from dataclasses import dataclass, field

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Context variables for tracking request-scoped metrics
query_timings_var: ContextVar[List[Dict[str, Any]]] = ContextVar("query_timings", default=[])
payload_sizes_var: ContextVar[List[int]] = ContextVar("payload_sizes", default=[])
cache_stats_var: ContextVar[Dict[str, int]] = ContextVar(
    "cache_stats", default={"hits": 0, "misses": 0}
)


@dataclass
class QueryMetrics:
    """Metrics for a single database query."""

    query_hash: str
    query_text: str
    duration_ms: float
    rows_returned: int
    endpoint: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class PayloadMetrics:
    """Metrics for request/response payload sizes."""

    endpoint: str
    request_size_bytes: int
    response_size_bytes: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class CacheMetrics:
    """Cache hit/miss metrics by endpoint."""

    endpoint: str
    hits: int = 0
    misses: int = 0
    total_lookups: int = 0

    @property
    def hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        if self.total_lookups == 0:
            return 0.0
        return self.hits / self.total_lookups


class DBProfilingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for database profiling and payload metrics collection.

    Tracks:
    - Query execution times with histogram bucketing
    - Request/response payload sizes by endpoint
    - Cache hit/miss ratios by endpoint
    """

    def __init__(
        self,
        app: ASGIApp,
        enabled: bool = True,
        slow_query_threshold_ms: float = 100.0,
        large_payload_threshold_bytes: int = 100_000,
    ):
        """
        Initialize DB profiling middleware.

        Args:
            app: ASGI application
            enabled: Whether profiling is enabled
            slow_query_threshold_ms: Threshold for slow query warnings (ms)
            large_payload_threshold_bytes: Threshold for large payload warnings
        """
        super().__init__(app)
        self.enabled = enabled
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.large_payload_threshold_bytes = large_payload_threshold_bytes

        # In-memory metrics storage (would be replaced with time-series DB in production)
        self.query_histograms: Dict[str, List[float]] = {}
        self.payload_histograms: Dict[str, List[PayloadMetrics]] = {}
        self.cache_metrics: Dict[str, CacheMetrics] = {}

        if enabled:
            logger.info("DB profiling middleware enabled")

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        """Process request with profiling metrics collection."""
        if not self.enabled:
            return await call_next(request)

        # Initialize context variables for this request
        query_timings_var.set([])
        payload_sizes_var.set([])
        cache_stats_var.set({"hits": 0, "misses": 0})

        endpoint = self._normalize_endpoint(request.url.path)
        method = request.method

        # Get request body size if available
        request_size = 0
        if request.headers.get("content-length"):
            request_size = int(request.headers.get("content-length", 0))

        start_time = time.time()

        try:
            response = await call_next(request)

            duration = time.time() - start_time
            response_size = 0
            if hasattr(response, "headers") and "content-length" in response.headers:
                response_size = int(response.headers["content-length"])

            # Record payload metrics
            self._record_payload_metrics(endpoint, method, request_size, response_size)

            # Get query timings from context
            query_timings = query_timings_var.get([])
            self._record_query_metrics(endpoint, query_timings)

            # Get cache stats from context
            cache_stats = cache_stats_var.get({"hits": 0, "misses": 0})
            self._record_cache_metrics(endpoint, cache_stats)

            # Add profiling headers
            if hasattr(response, "headers"):
                response.headers["X-Query-Count"] = str(len(query_timings))
                response.headers["X-Cache-Hits"] = str(cache_stats.get("hits", 0))
                response.headers["X-Cache-Misses"] = str(cache_stats.get("misses", 0))

                total_cache_ops = cache_stats.get("hits", 0) + cache_stats.get("misses", 0)
                if total_cache_ops > 0:
                    hit_ratio = cache_stats.get("hits", 0) / total_cache_ops
                    response.headers["X-Cache-Hit-Ratio"] = f"{hit_ratio:.2f}"

            return response

        except Exception:
            raise

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path by replacing IDs with placeholders."""
        parts = path.split("/")
        normalized_parts = []

        for part in parts:
            if self._looks_like_id(part):
                normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)

        return "/".join(normalized_parts)

    def _looks_like_id(self, part: str) -> bool:
        """Check if a path part looks like an ID."""
        if len(part) == 36 and part.count("-") == 4:
            return True
        if part.isdigit():
            return True
        if part.startswith("task_"):
            return True
        return False

    def _record_payload_metrics(
        self, endpoint: str, method: str, request_size: int, response_size: int
    ) -> None:
        """Record payload size metrics."""
        key = f"{method} {endpoint}"

        if key not in self.payload_histograms:
            self.payload_histograms[key] = []

        metrics = PayloadMetrics(
            endpoint=key,
            request_size_bytes=request_size,
            response_size_bytes=response_size,
        )
        self.payload_histograms[key].append(metrics)

        # Keep only last 1000 entries per endpoint
        self.payload_histograms[key] = self.payload_histograms[key][-1000:]

        # Log warnings for large payloads
        if request_size > self.large_payload_threshold_bytes:
            logger.warning(f"Large request payload detected: {request_size} bytes on {key}")
        if response_size > self.large_payload_threshold_bytes:
            logger.warning(f"Large response payload detected: {response_size} bytes on {key}")

    def _record_query_metrics(self, endpoint: str, query_timings: List[Dict[str, Any]]) -> None:
        """Record query timing metrics."""
        if endpoint not in self.query_histograms:
            self.query_histograms[endpoint] = []

        for timing in query_timings:
            duration_ms = timing.get("duration_ms", 0)
            self.query_histograms[endpoint].append(duration_ms)

            # Log slow queries
            if duration_ms > self.slow_query_threshold_ms:
                logger.warning(
                    f"Slow query detected: {duration_ms:.2f}ms on {endpoint} - "
                    f"{timing.get('query_text', 'unknown')[:100]}"
                )

        # Keep only last 1000 entries per endpoint
        self.query_histograms[endpoint] = self.query_histograms[endpoint][-1000:]

    def _record_cache_metrics(self, endpoint: str, cache_stats: Dict[str, int]) -> None:
        """Record cache hit/miss metrics."""
        if endpoint not in self.cache_metrics:
            self.cache_metrics[endpoint] = CacheMetrics(endpoint=endpoint)

        self.cache_metrics[endpoint].hits += cache_stats.get("hits", 0)
        self.cache_metrics[endpoint].misses += cache_stats.get("misses", 0)
        self.cache_metrics[endpoint].total_lookups += cache_stats.get("hits", 0) + cache_stats.get(
            "misses", 0
        )

    def get_query_histogram(self, endpoint: str) -> Dict[str, Any]:
        """
        Get query timing histogram for an endpoint.

        Returns:
            Dict with histogram buckets and statistics
        """
        timings = self.query_histograms.get(endpoint, [])
        if not timings:
            return {"count": 0, "buckets": {}, "p50": 0, "p95": 0, "p99": 0}

        # Define histogram buckets (ms)
        buckets = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
        bucket_counts = {f"<{b}ms": 0 for b in buckets}
        bucket_counts[">=5000ms"] = 0

        for t in timings:
            placed = False
            for b in buckets:
                if t < b:
                    bucket_counts[f"<{b}ms"] += 1
                    placed = True
                    break
            if not placed:
                bucket_counts[">=5000ms"] += 1

        # Calculate percentiles
        sorted_timings = sorted(timings)
        n = len(sorted_timings)
        p50 = sorted_timings[int(n * 0.5)] if n > 0 else 0
        p95 = sorted_timings[int(n * 0.95)] if n > 0 else 0
        p99 = sorted_timings[int(n * 0.99)] if n > 0 else 0

        return {
            "count": len(timings),
            "buckets": bucket_counts,
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "avg": sum(timings) / len(timings) if timings else 0,
        }

    def get_payload_histogram(self, endpoint: str) -> Dict[str, Any]:
        """
        Get payload size histogram for an endpoint.

        Returns:
            Dict with request and response size histograms
        """
        metrics = self.payload_histograms.get(endpoint, [])
        if not metrics:
            return {
                "count": 0,
                "request_sizes": {},
                "response_sizes": {},
            }

        request_sizes = [m.request_size_bytes for m in metrics]
        response_sizes = [m.response_size_bytes for m in metrics]

        # Define size buckets (bytes)
        buckets = [100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]

        def make_histogram(sizes: List[int]) -> Dict[str, int]:
            counts = {f"<{b}b": 0 for b in buckets}
            counts[">=1MB"] = 0
            for s in sizes:
                placed = False
                for b in buckets:
                    if s < b:
                        counts[f"<{b}b"] += 1
                        placed = True
                        break
                if not placed:
                    counts[">=1MB"] += 1
            return counts

        return {
            "count": len(metrics),
            "request_sizes": {
                "histogram": make_histogram(request_sizes),
                "avg": sum(request_sizes) / len(request_sizes) if request_sizes else 0,
                "max": max(request_sizes) if request_sizes else 0,
            },
            "response_sizes": {
                "histogram": make_histogram(response_sizes),
                "avg": sum(response_sizes) / len(response_sizes) if response_sizes else 0,
                "max": max(response_sizes) if response_sizes else 0,
            },
        }

    def get_cache_metrics(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        Get cache hit ratio metrics.

        Args:
            endpoint: Optional endpoint filter

        Returns:
            Dict with cache metrics by endpoint or overall
        """
        if endpoint:
            metrics = self.cache_metrics.get(endpoint)
            if not metrics:
                return {"hits": 0, "misses": 0, "hit_ratio": 0.0}
            return {
                "hits": metrics.hits,
                "misses": metrics.misses,
                "hit_ratio": metrics.hit_ratio,
            }

        # Return all endpoints
        return {
            ep: {
                "hits": m.hits,
                "misses": m.misses,
                "hit_ratio": m.hit_ratio,
            }
            for ep, m in self.cache_metrics.items()
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all profiling metrics for dashboard."""
        return {
            "query_histograms": {
                ep: self.get_query_histogram(ep) for ep in self.query_histograms.keys()
            },
            "payload_histograms": {
                ep: self.get_payload_histogram(ep) for ep in self.payload_histograms.keys()
            },
            "cache_metrics": self.get_cache_metrics(),
        }


# Global middleware instance for access from other modules
db_profiling_middleware: Optional[DBProfilingMiddleware] = None


def record_query_timing(
    query_hash: str, query_text: str, duration_ms: float, rows: int = 0
) -> None:
    """
    Record a query timing from database layer.

    Args:
        query_hash: Hash of the query for deduplication
        query_text: The SQL query text
        duration_ms: Query execution time in milliseconds
        rows: Number of rows returned
    """
    try:
        timings = query_timings_var.get([])
        timings.append(
            {
                "query_hash": query_hash,
                "query_text": query_text,
                "duration_ms": duration_ms,
                "rows_returned": rows,
            }
        )
        query_timings_var.set(timings)
    except Exception:
        pass  # Silently fail if context not available


def record_cache_hit() -> None:
    """Record a cache hit from cache layer."""
    try:
        stats = cache_stats_var.get({"hits": 0, "misses": 0})
        stats["hits"] = stats.get("hits", 0) + 1
        cache_stats_var.set(stats)
    except Exception:
        pass


def record_cache_miss() -> None:
    """Record a cache miss from cache layer."""
    try:
        stats = cache_stats_var.get({"hits": 0, "misses": 0})
        stats["misses"] = stats.get("misses", 0) + 1
        cache_stats_var.set(stats)
    except Exception:
        pass
