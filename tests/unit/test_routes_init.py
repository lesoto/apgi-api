"""
Unit tests for app/routes/__init__.py
"""

from app.routes import (
    __all__,
    api_keys_router,
    auth_router,
    export_router,
    health_router,
    metrics_router,
    sessions_router,
    state_router,
    tasks_router,
    users_router,
    version_router,
    webhooks_router,
)


class TestRoutesInit:
    """Test routes/__init__.py imports."""

    def test_all_routers_imported(self):
        """Test that all routers are imported successfully."""
        assert auth_router is not None
        assert users_router is not None
        assert sessions_router is not None
        assert state_router is not None
        assert tasks_router is not None
        assert export_router is not None
        assert health_router is not None
        assert metrics_router is not None
        assert version_router is not None
        assert api_keys_router is not None
        assert webhooks_router is not None

    def test_all_list_complete(self):
        """Test that __all__ contains all routers."""
        assert "auth_router" in __all__
        assert "users_router" in __all__
        assert "sessions_router" in __all__
        assert "state_router" in __all__
        assert "tasks_router" in __all__
        assert "export_router" in __all__
        assert "health_router" in __all__
        assert "metrics_router" in __all__
        assert "version_router" in __all__
        assert "api_keys_router" in __all__
        assert "webhooks_router" in __all__

    def test_all_list_length(self):
        """Test that __all__ has the correct length."""
        assert len(__all__) == 11
