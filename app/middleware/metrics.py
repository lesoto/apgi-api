"""
Prometheus Metrics Middleware

Provides Prometheus metrics for monitoring API performance and health.
"""

import time
from typing import Any, Awaitable, Callable

import psutil
from fastapi import Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from starlette.types import ASGIApp

# Define Prometheus metrics

# Request counter by endpoint, method, and status
request_counter = Counter(
    "apgi_api_requests_total", "Total number of API requests", ["method", "endpoint", "status_code"]
)

# Request duration histogram with DB/Redis timing tags
request_duration = Histogram(
    "apgi_api_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint", "has_db", "has_redis"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
)

# Active sessions gauge
active_sessions = Gauge("apgi_api_active_sessions", "Number of active simulation sessions")

# Task queue length gauge
task_queue_length = Gauge("apgi_api_task_queue_length", "Number of pending async tasks")

# Error counter by type
error_counter = Counter(
    "apgi_api_errors_total", "Total number of errors", ["error_type", "endpoint"]
)

# Active requests gauge
active_requests = Gauge("apgi_api_active_requests", "Number of requests currently being processed")

# Memory usage gauge
memory_usage_bytes = Gauge("apgi_api_memory_usage_bytes", "Current memory usage in bytes")

# CPU usage gauge
cpu_usage_percent = Gauge("apgi_api_cpu_usage_percent", "Current CPU usage percentage")

# Database connection pool metrics
database_connections_active = Gauge(
    "apgi_api_database_connections_active", "Number of active database connections"
)
database_connections_idle = Gauge(
    "apgi_api_database_connections_idle", "Number of idle database connections"
)
database_connections_used = Gauge(
    "apgi_api_database_connections_used", "Number of used database connections"
)
database_connections_overflow = Gauge(
    "apgi_api_database_connections_overflow", "Number of overflow database connections"
)

# Redis metrics
redis_connections_active = Gauge(
    "apgi_api_redis_connections_active", "Number of active Redis connections"
)
redis_memory_used_bytes = Gauge("apgi_api_redis_memory_used_bytes", "Redis memory usage in bytes")
redis_keys_total = Gauge("apgi_api_redis_keys_total", "Total number of keys in Redis")
redis_hit_rate = Gauge("apgi_api_redis_hit_rate", "Redis cache hit rate (0.0-1.0)")

# Celery metrics
celery_active_workers = Gauge("apgi_api_celery_active_workers", "Number of active Celery workers")
celery_active_tasks = Gauge("apgi_api_celery_active_tasks", "Number of currently executing tasks")
celery_scheduled_tasks = Gauge("apgi_api_celery_scheduled_tasks", "Number of scheduled tasks")
celery_queued_tasks = Gauge("apgi_api_celery_queued_tasks", "Number of tasks in queue")

# Cache metrics
cache_hits = Counter("apgi_api_cache_hits_total", "Total number of cache hits")
cache_misses = Counter("apgi_api_cache_misses_total", "Total number of cache misses")
cache_sets = Counter("apgi_api_cache_sets_total", "Total number of cache sets")

# Authentication metrics
auth_attempts = Counter("apgi_api_auth_attempts_total", "Total authentication attempts", ["result"])
auth_tokens_issued = Counter("apgi_api_auth_tokens_issued_total", "Total JWT tokens issued")
auth_tokens_revoked = Counter("apgi_api_auth_tokens_revoked_total", "Total JWT tokens revoked")

# Rate limiting metrics
rate_limit_exceeded = Counter(
    "apgi_api_rate_limit_exceeded_total", "Total rate limit violations", ["endpoint"]
)
rate_limit_allowed = Counter(
    "apgi_api_rate_limit_allowed_total", "Total allowed requests under rate limit", ["endpoint"]
)

# Response size histogram
response_size_bytes = Histogram(
    "apgi_api_response_size_bytes",
    "Response size in bytes",
    ["method", "endpoint"],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000),
)

# Business-specific metrics

# User activity metrics
user_registrations = Counter(
    "apgi_api_user_registrations_total", "Total number of user registrations"
)
user_logins = Counter("apgi_api_user_logins_total", "Total number of user logins", ["login_method"])
user_logouts = Counter("apgi_api_user_logouts_total", "Total number of user logouts")
active_users = Gauge("apgi_api_active_users", "Number of currently active users")

# Session metrics
sessions_created = Counter(
    "apgi_api_sessions_created_total", "Total number of sessions created", ["session_type"]
)
sessions_completed = Counter(
    "apgi_api_sessions_completed_total", "Total number of sessions completed", ["session_type"]
)
sessions_failed = Counter(
    "apgi_api_sessions_failed_total",
    "Total number of sessions failed",
    ["session_type", "failure_reason"],
)
session_duration = Histogram(
    "apgi_api_session_duration_seconds",
    "Session duration in seconds",
    ["session_type"],
    buckets=(60, 300, 600, 1800, 3600, 7200, 14400, 28800),  # 1min to 8hrs
)

# Task metrics
tasks_created = Counter(
    "apgi_api_tasks_created_total", "Total number of tasks created", ["task_type"]
)
tasks_completed = Counter(
    "apgi_api_tasks_completed_total", "Total number of tasks completed", ["task_type"]
)
tasks_failed = Counter(
    "apgi_api_tasks_failed_total", "Total number of tasks failed", ["task_type", "failure_reason"]
)
task_duration = Histogram(
    "apgi_api_task_duration_seconds",
    "Task execution duration in seconds",
    ["task_type"],
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 300, 600),  # 0.1s to 10min
)
task_queue_wait_time = Histogram(
    "apgi_api_task_queue_wait_time_seconds",
    "Time tasks spend waiting in queue",
    ["task_type"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60),  # 10ms to 1min
)

# Data export metrics
exports_requested = Counter(
    "apgi_api_exports_requested_total", "Total number of data exports requested", ["export_format"]
)
exports_completed = Counter(
    "apgi_api_exports_completed_total", "Total number of data exports completed", ["export_format"]
)
export_size_bytes = Histogram(
    "apgi_api_export_size_bytes",
    "Size of exported data in bytes",
    ["export_format"],
    buckets=(1000, 10000, 50000, 100000, 500000, 1000000, 5000000, 10000000),  # 1KB to 10MB
)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware that collects Prometheus metrics for all HTTP requests.

    Tracks:
    - Request count by endpoint, method, and status
    - Request duration by endpoint and method
    - Active requests
    - Errors by type
    - Response sizes
    - System metrics (memory and CPU usage)
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Any], Awaitable[StarletteResponse]]
    ) -> StarletteResponse:
        """
        Process request and collect metrics.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        # Skip metrics collection for the metrics endpoint itself
        if request.url.path == "/metrics":
            response = await call_next(request)
            return response

        # Normalize endpoint path (remove IDs for better aggregation)
        endpoint = self._normalize_endpoint(request.url.path)
        method = request.method

        # Increment active requests
        active_requests.inc()

        # Record start time
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Record metrics
            duration = time.time() - start_time
            status_code = response.status_code

            request_counter.labels(method=method, endpoint=endpoint, status_code=status_code).inc()

            # Determine if DB/Redis were used (based on context vars if available)
            from app.middleware.db_profiling import cache_stats_var, query_timings_var

            has_db = "true" if len(query_timings_var.get([])) > 0 else "false"

            cache_stats = cache_stats_var.get({"hits": 0, "misses": 0})
            has_redis = "true" if (cache_stats["hits"] + cache_stats["misses"]) > 0 else "false"

            request_duration.labels(
                method=method, endpoint=endpoint, has_db=has_db, has_redis=has_redis
            ).observe(duration)

            # Track response size
            if hasattr(response, "headers") and "content-length" in response.headers:
                response_size = int(response.headers["content-length"])
                response_size_bytes.labels(method=method, endpoint=endpoint).observe(response_size)

            # Track errors (4xx and 5xx)
            if status_code >= 400:
                error_type = "client_error" if status_code < 500 else "server_error"
                error_counter.labels(error_type=error_type, endpoint=endpoint).inc()

            # Update system metrics
            self._update_system_metrics()

            return response

        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time

            error_counter.labels(error_type=type(e).__name__, endpoint=endpoint).inc()

            request_duration.labels(method=method, endpoint=endpoint).observe(duration)

            # Re-raise exception
            raise

        finally:
            # Decrement active requests
            active_requests.dec()

    def _normalize_endpoint(self, path: str) -> str:
        """
        Normalize endpoint path by replacing IDs with placeholders.

        This helps aggregate metrics across similar endpoints.

        Args:
            path: Original request path

        Returns:
            Normalized path with ID placeholders
        """
        parts = path.split("/")
        normalized_parts = []

        for part in parts:
            # Replace UUIDs and numeric IDs with placeholders
            if self._looks_like_id(part):
                normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)

        return "/".join(normalized_parts)

    def _looks_like_id(self, part: str) -> bool:
        """
        Check if a path part looks like an ID.

        Args:
            part: Path component

        Returns:
            True if it looks like an ID
        """
        # Check for UUID pattern
        if len(part) == 36 and part.count("-") == 4:
            return True

        # Check for numeric ID
        if part.isdigit():
            return True

        # Check for task ID pattern (task_xxx)
        if part.startswith("task_"):
            return True

        return False

    def _update_system_metrics(self) -> None:
        """Update system-level metrics (memory and CPU usage)."""
        try:
            # Memory usage
            memory_info = psutil.virtual_memory()
            memory_usage_bytes.set(memory_info.used)

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_usage_percent.set(cpu_percent)
        except Exception:  # nosec: B110
            # Silently fail if psutil is not available or other errors occur
            pass


class MetricsCollector:
    """
    Helper class for updating application-specific metrics.
    """

    @staticmethod
    def set_active_sessions(count: int) -> None:
        """
        Update the active sessions gauge.

        Args:
            count: Number of active sessions
        """
        active_sessions.set(count)

    @staticmethod
    def set_task_queue_length(count: int) -> None:
        """
        Update the task queue length gauge.

        Args:
            count: Number of pending tasks
        """
        task_queue_length.set(count)

    @staticmethod
    def increment_error(error_type: str, endpoint: str) -> None:
        """
        Increment error counter.

        Args:
            error_type: Type of error
            endpoint: Endpoint where error occurred
        """
        error_counter.labels(error_type=error_type, endpoint=endpoint).inc()

    @staticmethod
    def record_user_registration() -> None:
        """Increment user registration counter."""
        user_registrations.inc()

    @staticmethod
    def record_user_login(login_method: str = "password") -> None:
        """
        Increment user login counter.

        Args:
            login_method: Method used for login (e.g., "password", "token")
        """
        user_logins.labels(login_method=login_method).inc()

    @staticmethod
    def record_user_logout() -> None:
        """Increment user logout counter."""
        user_logouts.inc()

    @staticmethod
    def set_active_users(count: int) -> None:
        """
        Update active users gauge.

        Args:
            count: Number of currently active users
        """
        active_users.set(count)

    @staticmethod
    def record_session_created(session_type: str = "default") -> None:
        """
        Increment session creation counter.

        Args:
            session_type: Type of session created
        """
        sessions_created.labels(session_type=session_type).inc()

    @staticmethod
    def record_session_completed(session_type: str = "default") -> None:
        """
        Increment session completion counter.

        Args:
            session_type: Type of session completed
        """
        sessions_completed.labels(session_type=session_type).inc()

    @staticmethod
    def record_session_failed(
        session_type: str = "default", failure_reason: str = "unknown"
    ) -> None:
        """
        Increment session failure counter.

        Args:
            session_type: Type of session
            failure_reason: Reason for failure
        """
        sessions_failed.labels(session_type=session_type, failure_reason=failure_reason).inc()

    @staticmethod
    def record_session_duration(session_type: str, duration_seconds: float) -> None:
        """
        Record session duration.

        Args:
            session_type: Type of session
            duration_seconds: Session duration in seconds
        """
        session_duration.labels(session_type=session_type).observe(duration_seconds)

    @staticmethod
    def record_task_created(task_type: str) -> None:
        """
        Increment task creation counter.

        Args:
            task_type: Type of task created
        """
        tasks_created.labels(task_type=task_type).inc()

    @staticmethod
    def record_task_completed(task_type: str) -> None:
        """
        Increment task completion counter.

        Args:
            task_type: Type of task completed
        """
        tasks_completed.labels(task_type=task_type).inc()

    @staticmethod
    def record_task_failed(task_type: str, failure_reason: str = "unknown") -> None:
        """
        Increment task failure counter.

        Args:
            task_type: Type of task
            failure_reason: Reason for failure
        """
        tasks_failed.labels(task_type=task_type, failure_reason=failure_reason).inc()

    @staticmethod
    def record_task_duration(task_type: str, duration_seconds: float) -> None:
        """
        Record task execution duration.

        Args:
            task_type: Type of task
            duration_seconds: Task duration in seconds
        """
        task_duration.labels(task_type=task_type).observe(duration_seconds)

    @staticmethod
    def record_task_queue_wait_time(task_type: str, wait_seconds: float) -> None:
        """
        Record time task spent waiting in queue.

        Args:
            task_type: Type of task
            wait_seconds: Time spent waiting in seconds
        """
        task_queue_wait_time.labels(task_type=task_type).observe(wait_seconds)

    @staticmethod
    def record_export_requested(export_format: str) -> None:
        """
        Increment export request counter.

        Args:
            export_format: Format of the export (e.g., "json", "csv")
        """
        exports_requested.labels(export_format=export_format).inc()

    @staticmethod
    def record_export_completed(export_format: str) -> None:
        """
        Increment export completion counter.

        Args:
            export_format: Format of the export
        """
        exports_completed.labels(export_format=export_format).inc()

    @staticmethod
    def update_database_metrics(active: int, idle: int, used: int, overflow: int) -> None:
        """
        Update database connection pool metrics.

        Args:
            active: Number of active connections
            idle: Number of idle connections
            used: Number of used connections
            overflow: Number of overflow connections
        """
        database_connections_active.set(active)
        database_connections_idle.set(idle)
        database_connections_used.set(used)
        database_connections_overflow.set(overflow)

    @staticmethod
    def update_redis_metrics(
        connections: int, memory_bytes: int, keys: int, hit_rate: float
    ) -> None:
        """
        Update Redis metrics.

        Args:
            connections: Number of active connections
            memory_bytes: Memory usage in bytes
            keys: Total number of keys
            hit_rate: Cache hit rate (0.0-1.0)
        """
        redis_connections_active.set(connections)
        redis_memory_used_bytes.set(memory_bytes)
        redis_keys_total.set(keys)
        redis_hit_rate.set(hit_rate)

    @staticmethod
    def update_celery_metrics(
        active_workers: int, active_tasks: int, scheduled: int, queued: int
    ) -> None:
        """
        Update Celery metrics.

        Args:
            active_workers: Number of active workers
            active_tasks: Number of currently executing tasks
            scheduled: Number of scheduled tasks
            queued: Number of tasks in queue
        """
        celery_active_workers.set(active_workers)
        celery_active_tasks.set(active_tasks)
        celery_scheduled_tasks.set(scheduled)
        celery_queued_tasks.set(queued)

    @staticmethod
    def record_cache_hit() -> None:
        """Increment cache hit counter."""
        cache_hits.inc()

    @staticmethod
    def record_cache_miss() -> None:
        """Increment cache miss counter."""
        cache_misses.inc()

    @staticmethod
    def record_cache_set() -> None:
        """Increment cache set counter."""
        cache_sets.inc()

    @staticmethod
    def record_auth_attempt(result: str) -> None:
        """
        Record authentication attempt.

        Args:
            result: Result of authentication ("success", "failure", "invalid_credentials", etc.)
        """
        auth_attempts.labels(result=result).inc()

    @staticmethod
    def record_token_issued() -> None:
        """Increment token issued counter."""
        auth_tokens_issued.inc()

    @staticmethod
    def record_token_revoked() -> None:
        """Increment token revoked counter."""
        auth_tokens_revoked.inc()

    @staticmethod
    def record_rate_limit_exceeded(endpoint: str) -> None:
        """
        Record rate limit violation.

        Args:
            endpoint: Endpoint where rate limit was exceeded
        """
        rate_limit_exceeded.labels(endpoint=endpoint).inc()

    @staticmethod
    def record_rate_limit_allowed(endpoint: str) -> None:
        """
        Record allowed request under rate limit.

        Args:
            endpoint: Endpoint that was allowed
        """
        rate_limit_allowed.labels(endpoint=endpoint).inc()


# Global metrics collector instance
metrics_collector = MetricsCollector()


def get_metrics_response() -> StarletteResponse:
    """
    Generate Prometheus metrics response.

    Returns:
        Response with Prometheus metrics in text format
    """
    metrics_data = generate_latest()
    return StarletteResponse(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
