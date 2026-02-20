"""
Performance Profiling Middleware

Middleware for detailed performance profiling of API endpoints.
"""

import cProfile
import io
import pstats
import time
import logging
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from app.services.profiling_service import ProfilingService

logger = logging.getLogger(__name__)


class ProfilingMiddleware(BaseHTTPMiddleware):
    """Middleware for profiling API endpoint performance."""

    def __init__(
        self,
        app,
        enabled: bool = False,
        memory_tracing: bool = False,
        profile_functions: bool = False,
    ):
        """
        Initialize profiling middleware.

        Args:
            app: ASGI application
            enabled: Whether profiling is enabled
            memory_tracing: Whether to enable memory tracing
            profile_functions: Whether to profile function calls with cProfile
        """
        super().__init__(app)
        self.enabled = enabled
        self.memory_tracing = memory_tracing
        self.profile_functions = profile_functions
        self.profiling_service: Optional[ProfilingService] = None

        if enabled:
            self.profiling_service = ProfilingService()
            if memory_tracing:
                self.profiling_service.start_memory_tracing()
            logger.info("Performance profiling middleware enabled")

    async def dispatch(self, request: Request, call_next):
        """Process the request with profiling if enabled."""
        if not self.enabled or not self.profiling_service:
            return await call_next(request)

        # Start profiling
        start_time = time.time()
        profiler = None

        if self.profile_functions:
            profiler = cProfile.Profile()
            profiler.enable()

        # Process request
        response = await call_next(request)

        # End profiling
        end_time = time.time()
        duration = end_time - start_time

        if self.profile_functions and profiler:
            profiler.disable()

            # Get profiling stats
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
            ps.print_stats(20)  # Top 20 functions
            profile_stats = s.getvalue()

            # Log detailed profiling info
            logger.info(
                f"Detailed profiling for {request.method} {request.url.path}:\n{profile_stats}"
            )

        # Record performance data
        endpoint = f"{request.method} {request.url.path}"
        logger.info(f"Endpoint performance: {endpoint} took {duration:.3f}s")

        # Add profiling headers to response
        if hasattr(response, "headers"):
            response.headers["X-Request-Duration"] = f"{duration:.3f}s"
            if self.profile_functions:
                response.headers["X-Profiled"] = "true"

        return response
