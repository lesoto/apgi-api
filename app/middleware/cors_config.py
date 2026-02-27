"""
CORS Middleware Configuration

Helper module for configuring CORS middleware with environment-based settings.
"""

import logging
from typing import TYPE_CHECKING

from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from fastapi import FastAPI

from app.config import settings

logger = logging.getLogger(__name__)


def configure_cors(app: "FastAPI") -> None:
    """
    Configure CORS middleware for the FastAPI application.

    This function adds CORS middleware with settings from the configuration system.
    It supports:
    - Configurable allowed origins via CORS_ORIGINS environment variable
    - Configurable credentials support via CORS_ALLOW_CREDENTIALS
    - Configurable allowed methods via CORS_ALLOW_METHODS
    - Configurable allowed headers via CORS_ALLOW_HEADERS

    Security considerations:
    - Wildcard origins (*) with credentials enabled is rejected in production
    - Wildcard origins without credentials triggers a warning
    - Production requires explicit origin configuration

    Args:
        app: FastAPI application instance

    Requirements:
        - 7.1: CORS middleware configured via environment variables
        - 7.2: Accepts comma-separated list of allowed origins
        - 7.3: Supports preflight OPTIONS requests
        - 7.4: Includes appropriate CORS headers in responses
        - 7.5: Logs security warning for wildcard origins
        - 7.6: Supports credentials when configured
    """
    # Log CORS configuration for debugging
    logger.info(
        f"Configuring CORS with origins: {settings.cors_origins}, "
        f"credentials: {settings.cors_allow_credentials}, "
        f"methods: {settings.cors_allow_methods}, "
        f"headers: {settings.cors_allow_headers}"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],  # Expose specific headers only
        max_age=600,  # Cache preflight requests for 10 minutes
    )

    logger.info("CORS middleware configured successfully")
