"""
Unit tests for authorization functions.
"""

import pytest
from unittest.mock import Mock, patch
from app.services.authorization import (
    get_permissions_for_roles,
    has_permission,
    has_any_role,
    check_permission,
    get_current_user,
    require_permission,
    require_role,
    require_any_role,
    log_audit_event,
    check_resource_ownership,
    Role,
    Permission,
)
from app.exceptions import AuthorizationError, InvalidTokenError


class TestAuthorizationFunctions:
    """Test authorization utility functions."""

    def test_get_permissions_for_roles_valid_roles(self):
        """Test getting permissions for valid roles."""
        roles = ["admin", "researcher"]
        permissions = get_permissions_for_roles(roles)

        assert isinstance(permissions, set)
        assert len(permissions) > 0
        # Admin should have all permissions
        assert Permission.SESSION_READ in permissions
        assert Permission.SYSTEM_ADMIN in permissions

    def test_get_permissions_for_roles_invalid_role(self):
        """Test getting permissions with invalid role."""
        roles = ["admin", "invalid_role"]
        permissions = get_permissions_for_roles(roles)

        assert isinstance(permissions, set)
        # Should still get admin permissions despite invalid role
        assert Permission.SESSION_READ in permissions

    def test_get_permissions_for_roles_empty_roles(self):
        """Test getting permissions for empty roles list."""
        permissions = get_permissions_for_roles([])

        assert isinstance(permissions, set)
        assert len(permissions) == 0

    def test_has_permission_with_valid_role(self):
        """Test has_permission with valid role."""
        user_roles = ["admin"]
        required_permission = Permission.SESSION_READ

        result = has_permission(user_roles, required_permission)
        assert result is True

    def test_has_permission_with_invalid_role(self):
        """Test has_permission with invalid role."""
        user_roles = ["invalid_role"]
        required_permission = Permission.SESSION_READ

        result = has_permission(user_roles, required_permission)
        assert result is False

    def test_has_permission_without_required_permission(self):
        """Test has_permission when user lacks required permission."""
        user_roles = ["viewer"]  # Viewer can only read
        required_permission = Permission.SESSION_CREATE  # Requires researcher or admin

        result = has_permission(user_roles, required_permission)
        assert result is False

    def test_has_any_role_with_matching_role(self):
        """Test has_any_role with matching role."""
        user_roles = ["admin", "viewer"]
        required_roles = [Role.ADMIN]

        result = has_any_role(user_roles, required_roles)
        assert result is True

    def test_has_any_role_without_matching_role(self):
        """Test has_any_role without matching role."""
        user_roles = ["viewer"]
        required_roles = [Role.ADMIN]

        result = has_any_role(user_roles, required_roles)
        assert result is False

    def test_has_any_role_with_invalid_role(self):
        """Test has_any_role with invalid role in user roles."""
        user_roles = ["invalid_role", "admin"]
        required_roles = [Role.ADMIN]

        result = has_any_role(user_roles, required_roles)
        assert result is True  # Should still work due to valid admin role

    @patch("app.services.authorization.AuthManager")
    @patch("app.services.authorization.log_audit_event")
    def test_check_permission_with_valid_permission(self, mock_log_audit, mock_auth_manager):
        """Test check_permission with valid permission."""
        # Mock user with admin role
        user = Mock()
        user.user_id = "user123"
        user.roles = ["admin"]
        user.permissions = None

        # Should not raise exception
        check_permission(user, Permission.SESSION_READ, "session", "read")

    @patch("app.services.authorization.AuthManager")
    @patch("app.services.authorization.log_audit_event")
    def test_check_permission_with_invalid_permission(self, mock_log_audit, mock_auth_manager):
        """Test check_permission with invalid permission."""
        # Mock user with viewer role (limited permissions)
        user = Mock()
        user.user_id = "user123"
        user.roles = ["viewer"]
        user.permissions = None

        # Should raise AuthorizationError
        with pytest.raises(AuthorizationError):
            check_permission(user, Permission.SESSION_CREATE, "session", "create")

    @patch("app.services.authorization.AuthManager")
    @patch("app.services.authorization.log_audit_event")
    def test_check_permission_with_direct_permissions(self, mock_log_audit, mock_auth_manager):
        """Test check_permission with direct permissions (API key)."""
        # Mock user with direct permissions
        user = Mock()
        user.user_id = "user123"
        user.roles = []
        user.permissions = ["session:read", "session:create"]

        # Should not raise exception
        check_permission(user, Permission.SESSION_READ, "session", "read")

    @patch("app.services.authorization.AuthManager")
    @patch("app.services.authorization.log_audit_event")
    def test_check_permission_with_db_logging(self, mock_log_audit, mock_auth_manager):
        """Test check_permission with database audit logging."""
        mock_db = Mock()

        user = Mock()
        user.user_id = "user123"
        user.roles = ["admin"]
        user.permissions = None

        check_permission(user, Permission.SESSION_READ, "session", "read", db=mock_db)

        # Verify audit logging was called
        mock_log_audit.assert_called_once()


class TestFastApiDependencies:
    """Test FastAPI dependency functions."""

    @patch("app.services.authorization.AuthManager")
    @patch("app.services.authorization.get_db")
    async def test_get_current_user_with_api_key(self, mock_get_db, mock_auth_manager):
        """Test get_current_user with API key authentication."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        # Mock request with user already set by middleware
        request = Mock()
        request.state.user = Mock(user_id="user123", roles=["admin"], permissions=None)

        user = await get_current_user(request, None, mock_db)

        assert user.user_id == "user123"
        assert user.roles == ["admin"]

    @patch("app.services.authorization.AuthManager")
    @patch("app.services.authorization.get_db")
    async def test_get_current_user_with_jwt_token(self, mock_get_db, mock_auth_manager):
        """Test get_current_user with JWT token authentication."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        # Mock AuthManager to return valid payload
        mock_auth_manager_instance = Mock()
        mock_auth_manager.return_value = mock_auth_manager_instance
        mock_payload = Mock(user_id="user123", roles=["admin"])
        mock_auth_manager_instance.verify_token.return_value = mock_payload

        # Mock request without API key user
        request = Mock()
        del request.state  # Simulate no state.user

        # Mock credentials
        credentials = Mock()
        credentials.credentials = "valid.jwt.token"

        user = await get_current_user(request, credentials, mock_db)

        assert user.user_id == "user123"
        mock_auth_manager_instance.verify_token.assert_called_once_with(
            "valid.jwt.token", expected_type="access"
        )

    @patch("app.services.authorization.AuthManager")
    @patch("app.services.authorization.get_db")
    async def test_get_current_user_without_credentials(self, mock_get_db, mock_auth_manager):
        """Test get_current_user without any credentials."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db

        request = Mock()
        del request.state

        with pytest.raises(InvalidTokenError):
            await get_current_user(request, None, mock_db)

    def test_require_permission_decorator(self):
        """Test require_permission decorator creation."""
        dependency = require_permission(Permission.SESSION_READ)

        assert callable(dependency)

    def test_require_role_decorator(self):
        """Test require_role decorator creation."""
        dependency = require_role(Role.ADMIN)

        assert callable(dependency)

    def test_require_any_role_decorator(self):
        """Test require_any_role decorator creation."""
        dependency = require_any_role([Role.ADMIN, Role.RESEARCHER])

        assert callable(dependency)


class TestAuditLogging:
    """Test audit logging functionality."""

    def test_log_audit_event_with_db(self):
        """Test audit logging with database session."""
        mock_db = Mock()

        log_audit_event(
            db=mock_db,
            user_id="user123",
            action="login",
            resource_type="user",
            resource_id="user123",
            status="success",
        )

        # Verify database operations were called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_log_audit_event_without_db(self):
        """Test audit logging without database session."""
        # Should not raise any errors
        log_audit_event(
            db=None, user_id="user123", action="login", resource_type="user", status="success"
        )


class TestResourceOwnership:
    """Test resource ownership checks."""

    @patch("app.services.authorization.log_audit_event")
    def test_check_resource_ownership_as_owner(self, mock_log_audit):
        """Test resource ownership check when user owns resource."""
        owner_id = "user123"
        user = Mock()
        user.user_id = "user123"
        user.roles = ["viewer"]

        # Should not raise exception
        check_resource_ownership(owner_id, user)

    @patch("app.services.authorization.log_audit_event")
    def test_check_resource_ownership_as_admin(self, mock_log_audit):
        """Test resource ownership check when user is admin."""
        owner_id = "user456"
        user = Mock()
        user.user_id = "user123"
        user.roles = ["admin"]

        # Should not raise exception
        check_resource_ownership(owner_id, user, allow_admin=True)

    @patch("app.services.authorization.log_audit_event")
    def test_check_resource_ownership_denied(self, mock_log_audit):
        """Test resource ownership check when access should be denied."""
        owner_id = "user456"
        user = Mock()
        user.user_id = "user123"
        user.roles = ["viewer"]

        with pytest.raises(AuthorizationError):
            check_resource_ownership(owner_id, user, allow_admin=False)


class TestEnums:
    """Test permission and role enumerations."""

    def test_permission_values(self):
        """Test permission enum values."""
        assert Permission.SESSION_CREATE.value == "session:create"
        assert Permission.SESSION_READ.value == "session:read"
        assert Permission.TEMPLATE_CREATE.value == "template:create"
        assert Permission.TASK_READ.value == "task:read"
        assert Permission.DATA_EXPORT.value == "data:export"
        assert Permission.SYSTEM_ADMIN.value == "system:admin"
        assert Permission.USER_MANAGE.value == "user:manage"
        assert Permission.USER_CREATE.value == "user:create"
        assert Permission.USER_READ.value == "user:read"
        assert Permission.USER_UPDATE.value == "user:update"
        assert Permission.USER_DELETE.value == "user:delete"
        assert Permission.USER_ADMIN.value == "user:admin"

    def test_role_values(self):
        """Test role enum values."""
        assert Role.ADMIN.value == "admin"
        assert Role.RESEARCHER.value == "researcher"
        assert Role.VIEWER.value == "viewer"

    def test_permission_comparison(self):
        """Test permission comparison."""
        assert Permission.SESSION_READ != Permission.SESSION_CREATE
        assert Permission.SESSION_READ == Permission.SESSION_READ

    def test_role_comparison(self):
        """Test role comparison."""
        assert Role.ADMIN != Role.VIEWER
        assert Role.ADMIN == Role.ADMIN
