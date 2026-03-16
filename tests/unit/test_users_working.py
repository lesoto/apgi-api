"""
Working tests for user routes to achieve coverage.
"""

import pytest
from unittest.mock import Mock, MagicMock
from fastapi import HTTPException
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

# Import the actual route functions
from app.routes.users import (
    register_user,
    verify_email,
    create_default_user,
    get_current_user_profile,
    list_users,
    get_user_stats,
    request_password_reset,
    delete_user,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    return db


@pytest.fixture
def mock_user_service():
    """Mock user management service."""
    service = MagicMock()
    return service


class TestUserRegistration:
    """Test user registration endpoints."""

    @pytest.mark.asyncio
    async def test_register_user_success(self, mock_db, mock_user_service):
        """Test successful user registration."""
        # Import here to avoid circular imports
        from app.models.schemas import UserCreateRequest

        request = UserCreateRequest(
            username="testuser", email="test@example.com", password="SecurePass123!"
        )

        mock_user = MagicMock()
        mock_user.user_id = "user123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.created_at = datetime.utcnow()

        mock_user_service.create_user.return_value = mock_user

        with MagicMock() as mock_get_service:
            mock_get_service.return_value = mock_user_service

            result = await register_user(request, mock_db)

            assert result.user_id == "user123"
            assert result.username == "testuser"
            assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_register_user_validation_error(self, mock_db, mock_user_service):
        """Test registration with validation error."""
        mock_user_service.create_user.side_effect = ValueError("Username already exists")

        with MagicMock() as mock_get_service:
            mock_get_service.return_value = mock_user_service

            with pytest.raises(HTTPException) as exc_info:
                await register_user(
                    Mock(username="testuser", email="test@example.com", password="pass"), mock_db
                )
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_register_user_internal_error(self, mock_db, mock_user_service):
        """Test registration with internal error."""
        mock_user_service.create_user.side_effect = Exception("Database error")

        with MagicMock() as mock_get_service:
            mock_get_service.return_value = mock_user_service

            with pytest.raises(HTTPException) as exc_info:
                await register_user(
                    Mock(username="testuser", email="test@example.com", password="pass"), mock_db
                )
            assert exc_info.value.status_code == 500


class TestEmailVerification:
    """Test email verification endpoints."""

    @pytest.mark.asyncio
    async def test_verify_email_success(self, mock_db):
        """Test successful email verification."""
        token = "valid_token_123"

        mock_user = MagicMock()
        mock_user.user_id = "user123"
        mock_user.is_active = False
        mock_user.email_verification_token = token
        mock_user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await verify_email(token, mock_db)

        assert result["message"] == "Email verified successfully. You can now log in."
        assert mock_user.is_active is True
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, mock_db):
        """Test email verification with invalid token."""
        token = "invalid_token"

        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await verify_email(token, mock_db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_verify_email_db_error(self, mock_db):
        """Test email verification with database error."""
        token = "valid_token"

        mock_user = MagicMock()
        mock_user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query
        mock_db.commit.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await verify_email(token, mock_db)
        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_called_once()


class TestDefaultUserCreation:
    """Test default user creation."""

    @pytest.mark.asyncio
    async def test_create_default_user_success(self, mock_db, mock_user_service):
        """Test successful default user creation."""
        mock_user = MagicMock()
        mock_user.user_id = "admin123"
        mock_user.username = "admin"
        mock_user.email = "admin@example.com"
        mock_user.created_at = datetime.utcnow()

        mock_user_service.create_user.return_value = mock_user

        with MagicMock() as mock_get_service:
            mock_get_service.return_value = mock_user_service

            result = await create_default_user(mock_db)

            assert result.user_id == "admin123"
            assert result.username == "admin"


class TestUserProfile:
    """Test user profile endpoints."""

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = MagicMock()
        user.user_id = "user123"
        user.username = "testuser"
        user.email = "test@example.com"
        user.roles = ["viewer"]
        return user

    @pytest.mark.asyncio
    async def test_get_current_user_profile_success(self, mock_db, mock_current_user):
        """Test successful profile retrieval."""
        mock_user = MagicMock()
        mock_user.user_id = "user123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.created_at = datetime.utcnow()

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await get_current_user_profile(mock_current_user, mock_db)

        assert result.user_id == "user123"
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_profile_not_found(self, mock_db, mock_current_user):
        """Test profile retrieval when user not found."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_profile(mock_current_user, mock_db)
        assert exc_info.value.status_code == 404


class TestUserList:
    """Test user list endpoints."""

    @pytest.fixture
    def mock_current_user(self):
        """Mock current admin user."""
        user = MagicMock()
        user.user_id = "admin123"
        user.roles = ["admin"]
        return user

    @pytest.mark.asyncio
    async def test_list_users_success(self, mock_db, mock_current_user):
        """Test successful user listing."""
        mock_query = MagicMock()
        mock_query.count.return_value = 10
        mock_query.limit.return_value.offset.return_value.all.return_value = [
            MagicMock(user_id="user1", username="user1", email="user1@example.com"),
            MagicMock(user_id="user2", username="user2", email="user2@example.com"),
        ]
        mock_db.query.return_value = mock_query

        result = await list_users(1, 10, mock_current_user, mock_db)

        assert len(result.users) == 2
        assert result.pagination.total == 10


class TestUserStats:
    """Test user statistics endpoints."""

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = MagicMock()
        user.user_id = "user123"
        user.roles = ["viewer"]
        return user

    @pytest.mark.asyncio
    async def test_get_user_stats_success(self, mock_db, mock_current_user):
        """Test successful user stats retrieval."""
        mock_query = MagicMock()
        mock_query.count.return_value = 5
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        result = await get_user_stats(mock_db)

        assert result.total_sessions == 5


class TestPasswordReset:
    """Test password reset endpoints."""

    @pytest.mark.asyncio
    async def test_request_password_reset_success(self, mock_db):
        """Test successful password reset request."""
        from app.models.schemas import PasswordResetEmailRequest

        request = PasswordResetEmailRequest(email="test@example.com")

        mock_user = MagicMock()
        mock_user.user_id = "user123"
        mock_user.email = "test@example.com"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await request_password_reset(request, mock_db)

        assert result.message == "Password reset instructions sent to your email"

    @pytest.mark.asyncio
    async def test_request_password_reset_user_not_found(self, mock_db):
        """Test password reset request for non-existent user."""
        from app.models.schemas import PasswordResetEmailRequest

        request = PasswordResetEmailRequest(email="nonexistent@example.com")

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        # Should still return success for security (don't reveal if user exists)
        result = await request_password_reset(request, mock_db)

        assert result.message == "Password reset instructions sent to your email"


class TestUserDeletion:
    """Test user deletion endpoints."""

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = MagicMock()
        user.user_id = "user123"
        user.roles = ["viewer"]
        return user

    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_db, mock_current_user):
        """Test successful user deletion."""
        mock_user = MagicMock()
        mock_user.user_id = "user123"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await delete_user("user123", mock_db)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_user)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_db, mock_current_user):
        """Test deletion when user not found."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await delete_user("user999", mock_db)
        assert exc_info.value.status_code == 404


class TestRouter:
    """Test router configuration."""

    def test_router_configuration(self):
        """Test that router is properly configured."""
        from app.routes.users import router

        assert router.prefix == "/v1/users"
        assert "User Management" in router.tags
        assert 401 in router.responses
        assert 403 in router.responses
        assert 404 in router.responses
        assert 500 in router.responses
