"""
Authorization Service

Role-Based Access Control (RBAC) for API endpoints.
"""

from enum import Enum
from typing import Dict, List, Set

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.exceptions import AuthorizationError, InvalidTokenError
from app.services.auth_manager import AuthManager, TokenPayload

# ============================================================================
# Roles and Permissions
# ============================================================================


class Role(str, Enum):
    """User roles for RBAC."""

    ADMIN = "admin"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


class Permission(str, Enum):
    """System permissions."""

    # Session permissions
    SESSION_CREATE = "session:create"
    SESSION_READ = "session:read"
    SESSION_UPDATE = "session:update"
    SESSION_DELETE = "session:delete"
    SESSION_CONTROL = "session:control"  # start, pause, stop, reset

    # Template permissions
    TEMPLATE_CREATE = "template:create"
    TEMPLATE_READ = "template:read"
    TEMPLATE_UPDATE = "template:update"
    TEMPLATE_DELETE = "template:delete"

    # Task permissions
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_DELETE = "task:delete"

    # Data permissions
    DATA_EXPORT = "data:export"
    DATA_READ = "data:read"

    # System permissions
    SYSTEM_ADMIN = "system:admin"
    USER_MANAGE = "user:manage"

    # User management permissions (more granular)
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_ADMIN = "user:admin"  # Full user administration


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # Admins have all permissions
        Permission.SESSION_CREATE,
        Permission.SESSION_READ,
        Permission.SESSION_UPDATE,
        Permission.SESSION_DELETE,
        Permission.SESSION_CONTROL,
        Permission.TEMPLATE_CREATE,
        Permission.TEMPLATE_READ,
        Permission.TEMPLATE_UPDATE,
        Permission.TEMPLATE_DELETE,
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_DELETE,
        Permission.DATA_EXPORT,
        Permission.DATA_READ,
        Permission.SYSTEM_ADMIN,
        Permission.USER_MANAGE,
        Permission.USER_CREATE,
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.USER_DELETE,
        Permission.USER_ADMIN,
    },
    Role.RESEARCHER: {
        # Researchers can create and manage their own sessions and tasks
        Permission.SESSION_CREATE,
        Permission.SESSION_READ,
        Permission.SESSION_UPDATE,
        Permission.SESSION_DELETE,
        Permission.SESSION_CONTROL,
        Permission.TEMPLATE_CREATE,
        Permission.TEMPLATE_READ,
        Permission.TEMPLATE_UPDATE,
        Permission.TEMPLATE_DELETE,
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_DELETE,
        Permission.DATA_EXPORT,
        Permission.DATA_READ,
        # Limited user management (can read and update own profile)
        Permission.USER_READ,
    },
    Role.VIEWER: {
        # Viewers can only read data
        Permission.SESSION_READ,
        Permission.TEMPLATE_READ,
        Permission.TASK_READ,
        Permission.DATA_READ,
        # Can read basic user info
        Permission.USER_READ,
    },
}


# ============================================================================
# Authorization Functions
# ============================================================================


def get_permissions_for_roles(roles: List[str]) -> Set[Permission]:
    """
    Get all permissions for a list of roles.

    Args:
        roles: List of role names

    Returns:
        Set of permissions granted by these roles
    """
    permissions = set()
    for role_name in roles:
        try:
            role = Role(role_name)
            permissions.update(ROLE_PERMISSIONS.get(role, set()))
        except ValueError:
            # Unknown role, skip it
            continue
    return permissions


def has_permission(user_roles: List[str], required_permission: Permission) -> bool:
    """
    Check if user has a specific permission.

    Args:
        user_roles: List of user's roles
        required_permission: Permission to check

    Returns:
        True if user has the permission, False otherwise
    """
    user_permissions = get_permissions_for_roles(user_roles)
    return required_permission in user_permissions


def has_any_role(user_roles: List[str], required_roles: List[Role]) -> bool:
    """
    Check if user has any of the required roles.

    Args:
        user_roles: List of user's roles
        required_roles: List of required roles

    Returns:
        True if user has at least one of the required roles
    """
    for role_name in user_roles:
        try:
            role = Role(role_name)
            if role in required_roles:
                return True
        except ValueError:
            continue
    return False


def check_permission(
    user_roles: List[str],
    required_permission: Permission,
    resource: str = "resource",
    action: str = "access",
) -> None:
    """
    Check if user has permission, raise exception if not.

    Args:
        user_roles: List of user's roles
        required_permission: Permission to check
        resource: Resource being accessed (for error message)
        action: Action being performed (for error message)

    Raises:
        AuthorizationError: If user lacks the required permission
    """
    if not has_permission(user_roles, required_permission):
        # Find which role would grant this permission
        required_role = None
        for role, perms in ROLE_PERMISSIONS.items():
            if required_permission in perms:
                required_role = role.value
                break

        raise AuthorizationError(resource=resource, action=action, required_role=required_role)


# ============================================================================
# FastAPI Dependencies
# ============================================================================

# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)
) -> TokenPayload:
    """
    FastAPI dependency to get current authenticated user from JWT token.

    Args:
        credentials: HTTP authorization credentials
        db: Database session

    Returns:
        TokenPayload with user information

    Raises:
        InvalidTokenError: If token is invalid or expired
    """
    if not credentials or not credentials.credentials:
        raise InvalidTokenError(
            "Missing authorization token. Please provide a valid JWT token in the Authorization header."
        )

    token = credentials.credentials
    auth_manager = AuthManager(db)

    try:
        payload = auth_manager.verify_token(token, expected_type="access")
        return payload
    except Exception as e:
        # Provide more helpful error messages based on the exception type
        error_msg = str(e)
        if "expired" in error_msg.lower():
            raise InvalidTokenError("Token has expired. Please log in again to get a new token.")
        elif "invalid" in error_msg.lower() or "malformed" in error_msg.lower():
            raise InvalidTokenError("Invalid token format. Please provide a valid JWT token.")
        elif "token type" in error_msg.lower():
            raise InvalidTokenError(
                "Invalid token type. Please use an access token, not a refresh token."
            )
        else:
            raise InvalidTokenError(
                "Authentication failed. Please check your credentials and try again."
            )


def require_permission(permission: Permission):
    """
    Create a FastAPI dependency that requires a specific permission.

    Args:
        permission: Required permission

    Returns:
        FastAPI dependency function

    Example:
        @app.get("/sessions", dependencies=[Depends(require_permission(Permission.SESSION_READ))])
        async def list_sessions():
            ...
    """

    async def permission_checker(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        """Check if current user has required permission."""
        check_permission(
            user_roles=current_user.roles,
            required_permission=permission,
            resource=permission.value.split(":")[0],
            action=permission.value.split(":")[1],
        )
        return current_user

    return permission_checker


def require_role(role: Role):
    """
    Create a FastAPI dependency that requires a specific role.

    Args:
        role: Required role

    Returns:
        FastAPI dependency function

    Example:
        @app.delete("/users/{user_id}", dependencies=[Depends(require_role(Role.ADMIN))])
        async def delete_user(user_id: str):
            ...
    """

    async def role_checker(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        """Check if current user has required role."""
        if not has_any_role(current_user.roles, [role]):
            raise AuthorizationError(resource="endpoint", action="access", required_role=role.value)
        return current_user

    return role_checker


def require_any_role(roles: List[Role]):
    """
    Create a FastAPI dependency that requires any of the specified roles.

    Args:
        roles: List of acceptable roles

    Returns:
        FastAPI dependency function
    """

    async def role_checker(current_user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        """Check if current user has any of the required roles."""
        if not has_any_role(current_user.roles, roles):
            role_names = [r.value for r in roles]
            raise AuthorizationError(
                resource="endpoint",
                action="access",
                required_role=f"one of: {', '.join(role_names)}",
            )
        return current_user

    return role_checker


# ============================================================================
# Resource Ownership Checks
# ============================================================================


def check_resource_ownership(
    resource_owner_id: str, current_user: TokenPayload, allow_admin: bool = True
) -> None:
    """
    Check if user owns a resource or is an admin.

    Args:
        resource_owner_id: User ID of resource owner
        current_user: Current authenticated user
        allow_admin: Whether admins can access any resource

    Raises:
        AuthorizationError: If user doesn't own resource and isn't admin
    """
    # Check if user owns the resource
    if resource_owner_id == current_user.user_id:
        return

    # Check if user is admin (if allowed)
    if allow_admin and has_any_role(current_user.roles, [Role.ADMIN]):
        return

    raise AuthorizationError(resource="resource", action="access", required_role="owner or admin")
