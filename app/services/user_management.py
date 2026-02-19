"""
User Management Service

Handles user CRUD operations and user-related business logic.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Session as SessionModel, User
from app.exceptions import UserNotFoundError, ValidationError
from app.services.auth_manager import AuthManager

logger = logging.getLogger(__name__)


class UserManagementService:
    """Service for managing users."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.auth_manager = AuthManager(db)

    def create_user(
        self, username: str, email: str, password: str, roles: Optional[List[str]] = None
    ) -> User:
        """
        Create a new user account.

        Args:
            username: Unique username
            email: User email address
            password: Plain text password
            roles: List of user roles (defaults to ['user'])

        Returns:
            Created User object

        Raises:
            ValidationError: If username or email already exists
        """
        if roles is None:
            roles = ["user"]

        # Hash the password
        hashed_password = self.auth_manager.hash_password(password)

        user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            roles=roles,
            is_active=True,  # Assume new users are active
        )

        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError:
            self.db.rollback()
            raise ValidationError("Username or email already exists")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create user {username}: {e}")
            raise

    def create_default_user(self, username: str, email: str, password: str) -> User:
        """
        Create a default user with basic permissions.

        Args:
            username: Unique username
            email: User email address
            password: Plain text password

        Returns:
            Created User object
        """
        return self.create_user(username, email, password, roles=["user"])

    def list_users(self, skip: int = 0, limit: int = 100, active_only: bool = True) -> List[User]:
        """
        List users with pagination.

        Args:
            skip: Number of users to skip
            limit: Maximum number of users to return
            active_only: Only return active users

        Returns:
            List of User objects
        """
        query = self.db.query(User)
        if active_only:
            query = query.filter(User.is_active == True)  # noqa: E712
        return query.offset(skip).limit(limit).all()

    def get_user(self, user_id: str) -> User:
        """
        Get a user by ID.

        Args:
            user_id: User identifier

        Returns:
            User object

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")
        return user

    def update_user(
        self,
        user_id: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        roles: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
    ) -> User:
        """
        Update user information.

        Args:
            user_id: User identifier
            email: New email address (optional)
            password: New password (optional)
            roles: New roles (optional)
            is_active: New active status (optional)

        Returns:
            Updated User object

        Raises:
            UserNotFoundError: If user not found
            ValidationError: If email already exists
        """
        user = self.get_user(user_id)

        if email is not None:
            user.email = email  # type: ignore[assignment]
        if password is not None:
            user.password_hash = self.auth_manager.hash_password(password)  # type: ignore[assignment]
        if roles is not None:
            user.roles = roles  # type: ignore[assignment]
        if is_active is not None:
            user.is_active = is_active  # type: ignore[assignment]

        # Update timestamp
        user.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]

        try:
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError:
            self.db.rollback()
            raise ValidationError("Email already exists")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update user {user_id}: {e}")
            raise

    def reset_password(self, user_id: str, new_password: str) -> str:
        """
        Reset a user's password.

        Args:
            user_id: User identifier
            new_password: New plain text password

        Returns:
            The new password (for confirmation in response)

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.get_user(user_id)
        user.password_hash = self.auth_manager.hash_password(new_password)  # type: ignore[assignment]
        user.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]

        try:
            self.db.commit()
            return new_password
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to reset password for user {user_id}: {e}")
            raise

    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user account.

        Args:
            user_id: User identifier

        Returns:
            True if user deleted successfully

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.get_user(user_id)

        try:
            self.db.delete(user)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete user {user_id}: {e}")
            raise

    def get_user_stats(self) -> dict:
        """
        Get user statistics.

        Returns:
            Dictionary with user statistics
        """
        total_users = self.db.query(User).count()
        active_users = self.db.query(User).filter(User.is_active == True).count()  # noqa: E712
        inactive_users = total_users - active_users

        # Count users by role
        from sqlalchemy import func

        role_counts_result = (
            self.db.query(User.roles, func.count(User.user_id)).group_by(User.roles).all()
        )
        role_counts = {str(roles): count for roles, count in role_counts_result}

        total_sessions = self.db.query(SessionModel).count()
        active_sessions = (
            self.db.query(SessionModel)
            .filter(SessionModel.state.in_(["running", "created"]))
            .count()
        )

        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "role_counts": role_counts,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
        }


def get_user_management_service(db: Session) -> UserManagementService:
    """Get user management service instance."""
    return UserManagementService(db)
