"""
Comprehensive tests for user routes to achieve 100% coverage.
"""

import pytest
from unittest.mock import Mock
from fastapi import HTTPException
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.routes.users import (
    register_user,
    verify_email,
    create_default_user,
    get_current_user_profile,
    update_user,
    delete_user,
    get_user_stats,
    request_password_reset,
    reset_user_password,
    confirm_password_reset,
    enable_mfa,
    disable_mfa,
    verify_mfa_backup_code,
    regenerate_mfa_backup_codes,
    list_users,
    router,
)
from app.models.schemas import (
    UserCreateRequest,
    UserCreateResponse,
    UserResponse,
    UserUpdateRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    PasswordResetEmailRequest,
    PasswordResetEmailResponse,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    UserStatsResponse,
    MFAEnrollResponse,
    MFADisableRequest,
    MFADisableResponse,
    MFAEnableRequest,
    MFABackupCodeVerifyRequest,
    MFABackupCodeVerifyResponse,
    MFABackupCodeRegenerateResponse,
    UsersListResponse,
)


class TestUserRegistration:
    """Test user registration endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.commit = Mock()
        db.rollback = Mock()
        db.add = Mock()
        return db

    @pytest.fixture
    def mock_user_service(self):
        """Mock user management service."""
        service = Mock()
        return service

    @pytest.mark.asyncio
    async def test_register_user_success(self, mock_db, mock_user_service):
        """Test successful user registration."""
        request = UserCreateRequest(
            username="testuser", email="test@example.com", password="SecurePass123!"
        )

        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.created_at = datetime.utcnow()

        mock_user_service.create_user.return_value = mock_user

        with Mock() as mock_get_service:
            mock_get_service.return_value = mock_user_service

            result = await register_user(request, mock_db)

            assert isinstance(result, UserCreateResponse)
            assert result.user_id == "user123"
            assert result.username == "testuser"
            assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_register_user_duplicate_username(self, mock_db, mock_user_service):
        """Test registration with duplicate username."""
        request = UserCreateRequest(
            username="testuser", email="test@example.com", password="SecurePass123!"
        )

        mock_user_service.create_user.side_effect = ValueError("Username already exists")

        with Mock() as mock_get_service:
            mock_get_service.return_value = mock_user_service

            with pytest.raises(HTTPException) as exc_info:
                await register_user(request, mock_db)
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_register_user_internal_error(self, mock_db, mock_user_service):
        """Test registration with internal error."""
        request = UserCreateRequest(
            username="testuser", email="test@example.com", password="SecurePass123!"
        )

        mock_user_service.create_user.side_effect = Exception("Database error")

        with Mock() as mock_get_service:
            mock_get_service.return_value = mock_user_service

            with pytest.raises(HTTPException) as exc_info:
                await register_user(request, mock_db)
            assert exc_info.value.status_code == 500


class TestEmailVerification:
    """Test email verification endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.commit = Mock()
        db.rollback = Mock()
        return db

    @pytest.mark.asyncio
    async def test_verify_email_success(self, mock_db):
        """Test successful email verification."""
        token = "valid_token_123"

        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.is_active = False
        mock_user.email_verification_token = token
        mock_user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await verify_email(token, mock_db)

        assert result["message"] == "Email verified successfully. You can now log in."
        assert mock_user.is_active is True
        assert mock_user.email_verification_token is None
        assert mock_user.email_verification_expires_at is None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, mock_db):
        """Test email verification with invalid token."""
        token = "invalid_token"

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await verify_email(token, mock_db)
        assert exc_info.value.status_code == 400
        assert "Invalid or expired verification token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_verify_email_expired_token(self, mock_db):
        """Test email verification with expired token."""
        token = "expired_token"

        mock_user = Mock()
        mock_user.email_verification_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await verify_email(token, mock_db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_verify_email_db_error(self, mock_db):
        """Test email verification with database error."""
        token = "valid_token"

        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query
        mock_db.commit.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await verify_email(token, mock_db)
        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_called_once()


class TestDefaultUserCreation:
    """Test default user creation."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.commit = Mock()
        return db

    @pytest.fixture
    def mock_user_service(self):
        """Mock user management service."""
        service = Mock()
        return service

    @pytest.mark.asyncio
    async def test_create_default_user_success(self, mock_db, mock_user_service):
        """Test successful default user creation."""
        mock_user = Mock()
        mock_user.user_id = "admin123"
        mock_user.username = "admin"
        mock_user.email = "admin@example.com"
        mock_user.created_at = datetime.utcnow()

        mock_user_service.create_user.return_value = mock_user

        with Mock() as mock_get_service:
            mock_get_service.return_value = mock_user_service

            result = await create_default_user(mock_db)

            assert isinstance(result, UserCreateResponse)
            assert result.user_id == "admin123"
            assert result.username == "admin"


class TestUserProfile:
    """Test user profile endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock()
        user.user_id = "user123"
        user.username = "testuser"
        user.email = "test@example.com"
        user.roles = ["viewer"]
        return user

    @pytest.mark.asyncio
    async def test_get_current_user_profile_success(self, mock_db, mock_current_user):
        """Test successful profile retrieval."""
        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.created_at = datetime.utcnow()
        mock_user.updated_at = datetime.utcnow()

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await get_current_user_profile(mock_current_user, mock_db)

        assert isinstance(result, UserResponse)
        assert result.user_id == "user123"
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_profile_not_found(self, mock_db, mock_current_user):
        """Test profile retrieval when user not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_profile(mock_current_user, mock_db)
        assert exc_info.value.status_code == 404


class TestUserUpdate:
    """Test user update endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.commit = Mock()
        return db

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock()
        user.user_id = "user123"
        user.username = "testuser"
        user.email = "test@example.com"
        user.roles = ["viewer"]
        return user

    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_db, mock_current_user):
        """Test successful user update."""
        request = UserUpdateRequest(
            email="newemail@example.com", password="newpass123", roles=["viewer"], is_active=True
        )

        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await update_user("user123", request, mock_current_user, mock_db)

        assert isinstance(result, UserResponse)
        # Note: The actual update logic would be in the service
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, mock_db, mock_current_user):
        """Test update when user not found."""
        request = UserUpdateRequest(email="new@example.com")

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await update_user("user999", request, mock_current_user, mock_db)
        assert exc_info.value.status_code == 404


class TestUserDeletion:
    """Test user deletion endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.commit = Mock()
        db.delete = Mock()
        return db

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock()
        user.user_id = "user123"
        user.username = "testuser"
        user.email = "test@example.com"
        user.roles = ["viewer"]
        return user

    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_db, mock_current_user):
        """Test successful user deletion."""
        mock_user = Mock()
        mock_user.user_id = "user123"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await delete_user("user123", mock_db)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_user)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_db, mock_current_user):
        """Test deletion when user not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await delete_user("user999", mock_current_user, mock_db)
        assert exc_info.value.status_code == 404


class TestUserStats:
    """Test user statistics endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock()
        user.user_id = "user123"
        user.roles = ["viewer"]
        return user

    @pytest.mark.asyncio
    async def test_get_user_stats_success(self, mock_db, mock_current_user):
        """Test successful user stats retrieval."""
        mock_query = Mock()
        mock_query.count.return_value = 5
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        result = await get_user_stats(mock_db)

        assert isinstance(result, UserStatsResponse)
        assert result.total_sessions == 5


class TestPasswordReset:
    """Test password reset endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.commit = Mock()
        return db

    @pytest.mark.asyncio
    async def test_request_password_reset_success(self, mock_db):
        """Test successful password reset request."""
        request = PasswordResetRequest(new_password="NewSecurePass123!")

        # Mock user lookup
        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.password_hash = "old_hash"
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await reset_user_password("user123", request, mock_db)

        assert isinstance(result, PasswordResetEmailResponse)
        assert result.message == "Password reset instructions sent to your email"

    @pytest.mark.asyncio
    async def test_request_password_reset_user_not_found(self, mock_db):
        """Test password reset request for non-existent user."""
        request = PasswordResetEmailRequest(email="nonexistent@example.com")

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        # Should still return success for security (don't reveal if user exists)
        result = await request_password_reset(request, mock_db)

        assert isinstance(result, PasswordResetEmailResponse)

    @pytest.mark.asyncio
    async def test_reset_password_success(self, mock_db):
        """Test successful password reset."""
        request = PasswordResetRequest(new_password="NewSecurePass123!")

        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.password_reset_token = "valid_token"
        mock_user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await reset_user_password("user123", request, mock_db)

        assert isinstance(result, PasswordResetResponse)
        assert result.message == "Password reset successfully"

    @pytest.mark.asyncio
    async def test_reset_password_confirm_success(self, mock_db):
        """Test successful password reset confirmation."""
        request = PasswordResetConfirmRequest(token="valid_token", new_password="NewSecurePass123!")

        # Mock user lookup
        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.password_reset_token = "valid_token"
        mock_user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        result = await confirm_password_reset(request, mock_db)

        assert isinstance(result, PasswordResetConfirmResponse)
        assert result.message == "Password confirmed successfully"


class TestMFA:
    """Test Multi-Factor Authentication endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.commit = Mock()
        return db

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock()
        user.user_id = "user123"
        user.roles = ["viewer"]
        return user

    @pytest.mark.asyncio
    async def test_enable_mfa_success(self, mock_db, mock_current_user):
        """Test successful MFA enable."""
        request = MFAEnableRequest(code="123456")

        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.password_hash = "hashed_password"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        # Mock the MFA service
        mock_mfa_service = Mock()
        mock_mfa_service.enable_mfa.return_value = {
            "secret": "JBSWY3DPEHPK3PXP",
            "backup_codes": ["123456", "789012"],
            "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
        }

        with Mock() as mock_get_mfa:
            mock_get_mfa.return_value = mock_mfa_service

            result = await enable_mfa(request, mock_current_user, mock_db)

            assert isinstance(result, MFAEnrollResponse)

    @pytest.mark.asyncio
    async def test_disable_mfa_success(self, mock_db, mock_current_user):
        """Test successful MFA disable."""
        request = MFADisableRequest(password="currentpass123")

        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.password_hash = "hashed_password"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        # Mock the MFA service
        mock_mfa_service = Mock()
        mock_mfa_service.disable_mfa.return_value = True

        with Mock() as mock_get_mfa:
            mock_get_mfa.return_value = mock_mfa_service

            result = await disable_mfa(request, mock_current_user, mock_db)

            assert isinstance(result, MFADisableResponse)
            assert result.message == "MFA disabled successfully"

    @pytest.mark.asyncio
    async def test_verify_mfa_backup_code_success(self, mock_db, mock_current_user):
        """Test successful MFA backup code verification."""
        request = MFABackupCodeVerifyRequest(code="123456")

        mock_user = Mock()
        mock_user.user_id = "user123"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        # Mock the MFA service
        mock_mfa_service = Mock()
        mock_mfa_service.verify_backup_code.return_value = True

        with Mock() as mock_get_mfa:
            mock_get_mfa.return_value = mock_mfa_service

            result = await verify_mfa_backup_code(request, mock_current_user, mock_db)

            assert isinstance(result, MFABackupCodeVerifyResponse)
            assert result.message == "Backup code verified successfully"

    @pytest.mark.asyncio
    async def test_regenerate_mfa_backup_codes_success(self, mock_db, mock_current_user):
        """Test successful MFA backup codes regeneration."""
        mock_user = Mock()
        mock_user.user_id = "user123"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_user
        mock_db.query.return_value = mock_query

        # Mock the MFA service
        mock_mfa_service = Mock()
        mock_mfa_service.regenerate_backup_codes.return_value = ["123456", "789012", "345678"]

        with Mock() as mock_get_mfa:
            mock_get_mfa.return_value = mock_mfa_service

            result = await regenerate_mfa_backup_codes(mock_current_user, mock_db)

            assert isinstance(result, MFABackupCodeRegenerateResponse)
            assert len(result.backup_codes) == 3


class TestUserList:
    """Test user list endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def mock_current_user(self):
        """Mock current admin user."""
        user = Mock()
        user.user_id = "admin123"
        user.roles = ["admin"]
        return user

    @pytest.mark.asyncio
    async def test_list_users_success(self, mock_db, mock_current_user):
        """Test successful user listing."""
        mock_query = Mock()
        mock_query.count.return_value = 10
        mock_query.limit.return_value.offset.return_value.all.return_value = [
            Mock(user_id="user1", username="user1", email="user1@example.com"),
            Mock(user_id="user2", username="user2", email="user2@example.com"),
        ]
        mock_db.query.return_value = mock_query

        result = await list_users(mock_db, page=1, per_page=10)

        assert isinstance(result, UsersListResponse)
        assert len(result.users) == 2
        assert result.pagination.total == 10


class TestRouter:
    """Test router configuration."""

    def test_router_configuration(self):
        """Test that router is properly configured."""
        assert router.prefix == "/v1/users"
        assert "User Management" in router.tags
        assert 401 in router.responses
        assert 403 in router.responses
        assert 404 in router.responses
        assert 500 in router.responses
