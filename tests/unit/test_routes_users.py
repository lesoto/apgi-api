"""
Tests for user management routes.
"""

from app.routes.users import router


class TestUsersRoutes:
    """Test user management endpoints."""

    def test_router_configuration(self):
        """Test router is properly configured."""
        assert router.tags == ["User Management"]
        assert router.prefix == "/v1/users"
        assert len(router.routes) > 0
