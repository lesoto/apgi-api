"""
Tests for API key management routes.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.models import APIKey
from app.models.schemas import APIKeyCreateRequest
from app.routes.api_keys import create_api_key, router


class TestAPIKeysRoutes:
    """Test API key management endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        from app.services.authorization import TokenPayload

        return TokenPayload(
            user_id="user-1", username="testuser", permissions=[], roles=[], exp=1234567890
        )

    @pytest.fixture
    def sample_api_key(self):
        """Sample API key for testing."""
        return APIKey(
            api_key_id="key-1",
            user_id="user-1",
            name="Test Key",
            key_hash="hashed_key",
            key_prefix="apgi_abc123",
            permissions=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            is_active=True,
        )

    @pytest.mark.asyncio
    @patch("app.routes.api_keys.AuthManager")
    @patch("app.routes.api_keys.secrets.token_urlsafe")
    async def test_create_api_key_success(
        self, mock_token_urlsafe, mock_auth_manager_class, mock_db, mock_current_user
    ):
        """Test successful API key creation."""
        mock_token_urlsafe.return_value = "randomstring"
        mock_auth_manager = MagicMock()
        mock_auth_manager.hash_password.return_value = "hashed_key"
        mock_auth_manager_class.return_value = mock_auth_manager

        # Mock db.refresh to populate key_id and created_at
        def mock_refresh(obj):
            obj.key_id = "key-123"
            obj.created_at = datetime.now(timezone.utc)
            obj.name = "Test Key"
            obj.permissions = ["read"]
            obj.expires_at = datetime.now(timezone.utc) + timedelta(days=365)

        mock_db.refresh = mock_refresh

        request = APIKeyCreateRequest(name="Test Key", permissions=["read"])

        with patch("app.routes.api_keys.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test_secret"

            response = await create_api_key(request, mock_db, mock_current_user)

            assert response.name == "Test Key"
            assert response.permissions == ["read"]
            assert mock_db.add.called
            assert mock_db.commit.called

    @pytest.mark.asyncio
    @patch("app.routes.api_keys.AuthManager")
    @patch("app.routes.api_keys.secrets.token_urlsafe")
    async def test_create_api_key_with_expiry(
        self, mock_token_urlsafe, mock_auth_manager_class, mock_db, mock_current_user
    ):
        """Test API key creation with custom expiry."""
        mock_token_urlsafe.return_value = "randomstring"
        mock_auth_manager = MagicMock()
        mock_auth_manager.hash_password.return_value = "hashed_key"
        mock_auth_manager_class.return_value = mock_auth_manager

        # Mock db.refresh to populate key_id and created_at
        def mock_refresh(obj):
            obj.key_id = "key-123"
            obj.created_at = datetime.now(timezone.utc)
            obj.name = "Test Key"
            obj.permissions = ["read"]
            obj.expires_at = datetime.now(timezone.utc) + timedelta(days=180)

        mock_db.refresh = mock_refresh

        custom_expiry = datetime.now(timezone.utc) + timedelta(days=180)
        request = APIKeyCreateRequest(
            name="Test Key", permissions=["read"], expires_at=custom_expiry
        )

        with patch("app.routes.api_keys.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test_secret"

            response = await create_api_key(request, mock_db, mock_current_user)

            # Compare with tolerance due to microsecond precision
            assert abs((response.expires_at - custom_expiry).total_seconds()) < 1

    @pytest.mark.asyncio
    @patch("app.routes.api_keys.AuthManager")
    @patch("app.routes.api_keys.secrets.token_urlsafe")
    async def test_create_api_key_default_expiry(
        self, mock_token_urlsafe, mock_auth_manager_class, mock_db, mock_current_user
    ):
        """Test API key creation uses default expiry when not provided."""
        mock_token_urlsafe.return_value = "randomstring"
        mock_auth_manager = MagicMock()
        mock_auth_manager.hash_password.return_value = "hashed_key"
        mock_auth_manager_class.return_value = mock_auth_manager

        # Mock db.refresh to populate key_id and created_at
        def mock_refresh(obj):
            obj.key_id = "key-123"
            obj.created_at = datetime.now(timezone.utc)
            obj.name = "Test Key"
            obj.permissions = ["read"]
            obj.expires_at = datetime.now(timezone.utc) + timedelta(days=365)

        mock_db.refresh = mock_refresh

        request = APIKeyCreateRequest(name="Test Key", permissions=["read"])

        with patch("app.routes.api_keys.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test_secret"

            response = await create_api_key(request, mock_db, mock_current_user)

            # Should be approximately 365 days from now
            expected_expiry = datetime.now(timezone.utc) + timedelta(days=365)
            assert abs((response.expires_at - expected_expiry).total_seconds()) < 10

    @pytest.mark.asyncio
    @patch("app.routes.api_keys.AuthManager")
    @patch("app.routes.api_keys.secrets.token_urlsafe")
    async def test_create_api_key_database_error(
        self, mock_token_urlsafe, mock_auth_manager_class, mock_db, mock_current_user
    ):
        """Test API key creation handles database errors."""
        mock_token_urlsafe.return_value = "randomstring"
        mock_auth_manager = MagicMock()
        mock_auth_manager.hash_password.return_value = "hashed_key"
        mock_auth_manager_class.return_value = mock_auth_manager
        mock_db.commit.side_effect = Exception("Database error")

        request = APIKeyCreateRequest(name="Test Key", permissions=["read"])

        with patch("app.routes.api_keys.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test_secret"

            with pytest.raises(HTTPException) as exc_info:
                await create_api_key(request, mock_db, mock_current_user)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_router_configuration(self):
        """Test router is properly configured."""
        assert router.prefix == "/v1/api-keys"
        assert router.tags == ["API Key Management"]
        assert 401 in router.responses
        assert 403 in router.responses
