"""
Authentication Manager Service

Handles JWT token creation/verification and password hashing for user authentication.
"""

import hmac
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import bcrypt
import jwt

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import RefreshToken, User
from app.exceptions import AuthenticationError, ExpiredTokenError, InvalidTokenError

logger = logging.getLogger(__name__)


class TokenPayload:
    """JWT token payload data."""

    def __init__(
        self,
        user_id: str,
        username: str,
        roles: List[str],
        exp: datetime,
        token_type: str = "access",
    ):
        self.user_id = user_id
        self.username = username
        self.roles = roles
        self.exp = exp
        self.token_type = token_type

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JWT encoding."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "roles": self.roles,
            "exp": int(self.exp.timestamp()),
            "token_type": self.token_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenPayload":
        """Create from dictionary after JWT decoding."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            roles=data["roles"],
            exp=datetime.fromtimestamp(data["exp"]),
            token_type=data.get("token_type", "access"),
        )


class AuthManager:
    """
    Manages authentication and authorization.

    Responsibilities:
    - JWT token creation and verification
    - Password hashing and verification
    - User authentication
    - Token refresh
    """

    def __init__(self, db: Session):
        """
        Initialize AuthManager.

        Args:
            db: Database session for user lookups
        """
        self.db = db
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.jwt_access_token_expire_minutes
        self.refresh_token_expire_days = settings.jwt_refresh_token_expire_days

    # ========================================================================
    # Password Hashing
    # ========================================================================

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        # Truncate password to 72 bytes (bcrypt limit)
        password_bytes = password.encode("utf-8")
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password to compare against

        Returns:
            True if password matches, False otherwise
        """
        # Truncate password to 72 bytes (bcrypt limit) - must match hash_password behavior
        password_bytes = plain_password.encode("utf-8")
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)

    # ========================================================================
    # Token Creation
    # ========================================================================

    def create_access_token(self, user_id: str, username: str, roles: List[str]) -> str:
        """
        Create a JWT access token.

        Args:
            user_id: User identifier
            username: Username
            roles: List of user roles

        Returns:
            Encoded JWT token string
        """
        expires_at = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        payload = TokenPayload(
            user_id=user_id, username=username, roles=roles, exp=expires_at, token_type="access"
        )

        token = jwt.encode(payload.to_dict(), self.secret_key, algorithm=self.algorithm)

        return token

    def create_refresh_token(self, user_id: str, username: str, roles: List[str]) -> str:
        """
        Create a JWT refresh token.

        Args:
            user_id: User identifier
            username: Username
            roles: List of user roles

        Returns:
            Encoded JWT refresh token string
        """
        expires_at = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        payload = TokenPayload(
            user_id=user_id, username=username, roles=roles, exp=expires_at, token_type="refresh"
        )

        token = jwt.encode(payload.to_dict(), self.secret_key, algorithm=self.algorithm)

        return token

    # ========================================================================
    # Token Verification
    # ========================================================================

    def verify_token(self, token: str, expected_type: str = "access") -> TokenPayload:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string
            expected_type: Expected token type ("access" or "refresh")

        Returns:
            TokenPayload with decoded token data

        Raises:
            InvalidTokenError: If token is invalid or malformed
            ExpiredTokenError: If token has expired
        """
        try:
            # Decode token
            payload_dict = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Parse payload
            payload = TokenPayload.from_dict(payload_dict)

            # Verify token type
            if payload.token_type != expected_type:
                raise InvalidTokenError(
                    f"Invalid token type: expected {expected_type}, got {payload.token_type}"
                )

            # Check expiration (jwt.decode already checks this, but we handle it explicitly)
            if datetime.utcnow() > payload.exp:
                raise ExpiredTokenError("Token has expired")

            return payload

        except jwt.ExpiredSignatureError:
            raise ExpiredTokenError("Token has expired")
        except ExpiredTokenError:
            # Re-raise our own ExpiredTokenError
            raise
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid token: {str(e)}")
        except Exception as e:
            raise InvalidTokenError(f"Token verification failed: {str(e)}")

    # ========================================================================
    # User Authentication
    # ========================================================================

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user with username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            User object if authentication successful, None otherwise
        """
        # Look up user
        user = self.db.query(User).filter(User.username == username).first()

        if not user:
            return None

        # Verify password
        if not self.verify_password(password, user.password_hash):  # type: ignore[arg-type]
            return None

        # Update last login
        try:
            user.last_login = datetime.utcnow()  # type: ignore[assignment]
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update last login for user {username}: {e}")
            # Still return user since login succeeded, just log the error

        return user

    def create_tokens_for_user(self, user: User) -> Dict[str, Any]:
        """
        Create access and refresh tokens for a user.

        Args:
            user: User object

        Returns:
            Dictionary with access_token, refresh_token, token_type, and expires_in
        """
        access_token = self.create_access_token(
            user_id=user.user_id, username=user.username, roles=user.roles  # type: ignore[arg-type]
        )

        refresh_token = self.create_refresh_token(
            user_id=user.user_id, username=user.username, roles=user.roles  # type: ignore[arg-type]
        )

        # Store refresh token in database
        token_hash = self.hash_password(refresh_token)
        expires_at = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        try:
            db_refresh_token = RefreshToken(
                user_id=user.user_id, token_hash=token_hash, expires_at=expires_at
            )
            self.db.add(db_refresh_token)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create refresh token for user {user.user_id}: {e}")
            raise

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60,
        }

    # ========================================================================
    # Token Refresh
    # ========================================================================

    @staticmethod
    def constant_time_compare(val1: str, val2: str) -> bool:
        """
        Constant-time comparison to prevent timing attacks.

        Args:
            val1: First value to compare
            val2: Second value to compare

        Returns:
            True if values are equal, False otherwise
        """
        return hmac.compare_digest(val1.encode(), val2.encode())

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Create a new access token using a refresh token.

        Args:
            refresh_token: Refresh token string

        Returns:
            Dictionary with new access_token, token_type, and expires_in

        Raises:
            InvalidTokenError: If refresh token is invalid
            ExpiredTokenError: If refresh token has expired
            AuthenticationError: If refresh token has been revoked
        """
        # Verify refresh token
        payload = self.verify_token(refresh_token, expected_type="refresh")

        # Hash the provided token to lookup the exact token in database
        token_hash = self.hash_password(refresh_token)

        # Look up the specific token by hash and user_id (not just first non-revoked)
        db_token = (
            self.db.query(RefreshToken)
            .filter(
                and_(
                    RefreshToken.user_id == payload.user_id,
                    RefreshToken.token_hash == token_hash,
                    not RefreshToken.revoked,  # type: ignore[arg-type, assignment]
                )
            )
            .first()
        )

        if not db_token:
            raise AuthenticationError("Invalid or revoked refresh token")

        # Use constant-time comparison for token verification
        if not self.constant_time_compare(refresh_token, db_token.token_hash):  # type: ignore[arg-type]
            raise AuthenticationError("Invalid refresh token")

        # Check expiration in database
        if datetime.utcnow() > db_token.expires_at:
            raise ExpiredTokenError("Refresh token has expired")

        # Create new access token
        access_token = self.create_access_token(
            user_id=payload.user_id, username=payload.username, roles=payload.roles
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60,
        }

    # ========================================================================
    # Token Revocation
    # ========================================================================

    def revoke_refresh_token(self, refresh_token: str) -> bool:
        """
        Revoke a refresh token (logout).

        Args:
            refresh_token: Refresh token to revoke

        Returns:
            True if token was revoked, False if not found
        """
        try:
            # Verify token to get user_id
            payload = self.verify_token(refresh_token, expected_type="refresh")

            # Hash the provided token to lookup the exact token in database
            token_hash = self.hash_password(refresh_token)

            # Find and revoke the specific token by hash and user_id
            db_token = (
                self.db.query(RefreshToken)
                .filter(
                    and_(
                        RefreshToken.user_id == payload.user_id,
                        RefreshToken.token_hash == token_hash,
                        not RefreshToken.revoked,  # type: ignore[arg-type, assignment]
                    )
                )
                .first()
            )

            try:
                if db_token:
                    db_token.revoked = True  # type: ignore[assignment]
                    self.db.commit()
                    return True
                return False
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to revoke refresh token {token_hash}: {e}")
                return False

        except (InvalidTokenError, ExpiredTokenError):
            # Token is already invalid, consider it revoked
            return False

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """
        Revoke all refresh tokens for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of tokens revoked
        """
        try:
            tokens = (
                self.db.query(RefreshToken)
                .filter(and_(RefreshToken.user_id == user_id, not RefreshToken.revoked))  # type: ignore[arg-type, assignment]
                .all()
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to retrieve tokens for user {user_id}: {e}")
            raise

        count = 0
        try:
            for token in tokens:
                token.revoked = True  # type: ignore[assignment]
                count += 1

            self.db.commit()
            return count
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to revoke tokens for user {user_id}: {e}")
            raise
