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

        # Generate email verification token
        import secrets
        from datetime import timedelta

        verification_token = secrets.token_urlsafe(32)
        verification_expires = datetime.now(timezone.utc) + timedelta(hours=24)

        user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            roles=roles,
            is_active=False,  # Require email verification before activation
            email_verification_token=verification_token,
            email_verification_expires_at=verification_expires,
        )

        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            # Send verification email
            self._send_verification_email(user.email, verification_token)  # type: ignore[arg-type]

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
        query = self.db.query(User).filter(User.is_deleted.is_(False))
        if active_only:
            query = query.filter(User.is_active)
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
        user = (
            self.db.query(User)
            .filter(User.user_id == user_id)
            .filter(User.is_deleted.is_(False))
            .first()
        )
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
        user.updated_at = datetime.now(timezone.utc)

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

    def reset_password(self, user_id: str, new_password: Optional[str] = None) -> str:
        """
        Reset a user's password by generating a new random password and emailing it,
        or using the provided password if specified.

        Args:
            user_id: User identifier
            new_password: Optional new password to set. If not provided, generates random.

        Returns:
            Success message (password not returned for security)

        Raises:
            UserNotFoundError: If user not found
        """
        import secrets
        import string

        user = self.get_user(user_id)

        # Use provided password or generate a secure random password
        if new_password is not None:
            password_to_set = new_password
        else:
            # Generate a secure random password
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password_to_set = "".join(secrets.choice(alphabet) for _ in range(12))

        user.password_hash = self.auth_manager.hash_password(password_to_set)  # type: ignore[assignment]
        user.updated_at = datetime.now(timezone.utc)

        try:
            self.db.commit()

            # Send new password via email
            self._send_password_reset_email(user.email, password_to_set)  # type: ignore[arg-type]

            return "Password reset successful. Check your email for the new password."
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to reset password for user {user_id}: {e}")
            raise

    def _send_password_reset_email(self, email: str, new_password: str) -> None:
        """
        Send password reset email with new password.

        Args:
            email: User's email address
            new_password: New password to send
        """
        from app.config import settings
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        if not settings.smtp_server:
            logger.warning("SMTP server not configured, cannot send password reset email")
            logger.info(f"Password reset for {email}: new password is {new_password}")
            return

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = settings.smtp_from_email
            msg["To"] = email
            msg["Subject"] = "Your APGI API Password Has Been Reset"

            # Email body
            body = f"""
Hello,

Your password for the APGI API has been reset.

Your new password is: {new_password}

Please log in with this password and change it to something you can remember.

If you did not request this password reset, please contact support immediately.

Best regards,
APGI API Team
            """

            msg.attach(MIMEText(body, "plain"))

            # Send email
            server = smtplib.SMTP(settings.smtp_server, settings.smtp_port)
            server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, email, msg.as_string())
            server.quit()

            logger.info(f"Password reset email sent to {email}")

        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {e}")
            # Don't raise exception to avoid breaking password reset
            # Log the password so it can be manually communicated if needed
            logger.warning(
                f"Password reset failed to send email, password for {email}: {new_password}"
            )

    def _send_verification_email(self, email: str, verification_token: str) -> None:
        """
        Send email verification email with verification link.

        Args:
            email: User's email address
            verification_token: Verification token
        """
        from app.config import settings
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        if not settings.smtp_server:
            logger.warning("SMTP server not configured, cannot send verification email")
            logger.info(f"Email verification for {email}: token is {verification_token}")
            return

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = settings.smtp_from_email
            msg["To"] = email
            msg["Subject"] = "Verify Your APGI API Account"

            # Email body with verification link
            verification_url = f"{settings.base_url}/verify-email?token={verification_token}"
            body = f"""
Hello,

Thank you for registering with the APGI API.

Please verify your email address by clicking the link below:

{verification_url}

This link will expire in 24 hours.

If you did not create this account, please ignore this email.

Best regards,
APGI API Team
            """

            msg.attach(MIMEText(body, "plain"))

            # Send email
            server = smtplib.SMTP(settings.smtp_server, settings.smtp_port)
            server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, email, msg.as_string())
            server.quit()

            logger.info(f"Verification email sent to {email}")

        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {e}")
            # Don't raise exception to avoid breaking registration
            logger.warning(
                f"Verification email failed to send, token for {email}: {verification_token}"
            )

    def delete_user(self, user_id: str) -> bool:
        """
        Soft delete a user account.

        Args:
            user_id: User identifier

        Returns:
            True if user soft deleted successfully

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.get_user(user_id)  # This already filters not deleted

        user.is_deleted = True
        user.updated_at = datetime.now(timezone.utc)

        try:
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to soft delete user {user_id}: {e}")
            raise

    def get_user_stats(self) -> dict:
        """
        Get user statistics.

        Returns:
            Dictionary with user statistics
        """
        total_users = self.db.query(User).filter(User.is_deleted.is_(False)).count()
        active_users = (
            self.db.query(User).filter(User.is_active).filter(User.is_deleted.is_(False)).count()
        )  # noqa: E712
        inactive_users = total_users - active_users

        # Count users by role
        # Get all users and count roles in Python to avoid GROUP BY on array column
        users = self.db.query(User).filter(User.is_deleted.is_(False)).all()
        role_counts: dict[tuple[str, ...], int] = {}
        for user in users:
            roles_list = list(user.roles or []) if user.roles else []
            roles_tuple = tuple(sorted(roles_list))
            role_counts[roles_tuple] = role_counts.get(roles_tuple, 0) + 1
        role_counts_str: dict[str, int] = {str(k): v for k, v in role_counts.items()}

        total_sessions = (
            self.db.query(SessionModel).filter(SessionModel.is_deleted.is_(False)).count()
        )
        active_sessions = (
            self.db.query(SessionModel)
            .filter(SessionModel.state.in_(["running", "created"]))
            .filter(SessionModel.is_deleted.is_(False))
            .count()
        )

        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "role_counts": role_counts_str,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
        }


def get_user_management_service(db: Session) -> UserManagementService:
    """Get user management service instance."""
    return UserManagementService(db)
