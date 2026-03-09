"""
Route handlers for the standalone API.

This package contains all API route definitions organized by resource type.
"""

from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from app.routes.sessions import router as sessions_router
from app.routes.state import router as state_router
from app.routes.tasks import router as tasks_router
from app.routes.export import router as export_router
from app.routes.health import router as health_router
from app.routes.metrics import router as metrics_router
from app.routes.version import router as version_router
from app.routes.api_keys import router as api_keys_router
from app.routes.webhooks import router as webhooks_router

__all__ = [
    "auth_router",
    "users_router",
    "sessions_router",
    "state_router",
    "tasks_router",
    "export_router",
    "health_router",
    "metrics_router",
    "version_router",
    "api_keys_router",
    "webhooks_router",
]
