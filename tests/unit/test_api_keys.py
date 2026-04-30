"""
Unit tests for API key management routes.

Tests API key creation, listing, updating, rotation, and deletion endpoints.
Validates Requirements 8.1, 8.2, 8.3.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

try:
    from app.models.schemas import APIKeyCreateRequest, APIKeyUpdateRequest
    from app.routes.api_keys import (
        create_api_key,
        delete_api_key,
        get_api_key,
        list_api_keys,
        rotate_api_key,
        update_api_key,
    )
    from app.services.auth_manager import TokenPayload
except ImportError:
    pytest.skip(
        "Required app modules not available - skipping API keys tests", allow_module_level=True
    )


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def mock_current_user() -> TokenPayload:
    """Create a mock current user."""
    return TokenPayload(
        user_id="test_user_123",
        username="testuser",
        roles=["user"],
        exp=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.fixture
def mock_api_key() -> MagicMock:
    """Create a mock API key database object."""
    api_key = MagicMock()
    api_key.key_id = "test_key_123"
    api_key.user_id = "test_user_123"
    api_key.name = "Test API Key"
    api_key.key_hash = "hashed_key"
    api_key.key_prefix = "prefix123"
    api_key.permissions = ["read", "write"]
    api_key.expires_at = datetime.now(timezone.utc) + timedelta(days=365)
    api_key.is_active = True
    api_key.created_at = datetime.now(timezone.utc)
    api_key.last_used_at = None
    return api_key


class TestCreateAPIKey:
    """Test API key creation."""

    @pytest.mark.asyncio
    async def test_create_api_key_success(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test successful API key creation."""
        request = APIKeyCreateRequest(
            name="Test Key",
            permissions=["read", "write"],
            expires_at=None,
        )

        # Mock the database add/commit/refresh
        mock_db_session.add = MagicMock()
        mock_db_session.commit = MagicMock()
        mock_db_session.refresh = MagicMock()

        # Mock the API key object returned after refresh
        mock_created_key = MagicMock()
        mock_created_key.key_id = "new_key_123"
        mock_created_key.name = "Test Key"
        mock_created_key.permissions = ["read", "write"]
        mock_created_key.expires_at = datetime.now(timezone.utc) + timedelta(days=365)
        mock_created_key.created_at = datetime.now(timezone.utc)

        mock_db_session.refresh.side_effect = lambda obj: (
            setattr(obj, "key_id", "new_key_123") if hasattr(obj, "name") else None
        )

        with patch("app.routes.api_keys.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.hash_password.return_value = "hashed_password"
            mock_auth_manager_class.return_value = mock_auth_manager

            with patch("app.routes.api_keys.secrets.token_urlsafe", return_value="test_token"):
                with patch("hmac.new") as mock_hmac:
                    mock_digest = MagicMock()
                    mock_digest.hexdigest.return_value = "12345678901234567890"
                    mock_hmac.return_value = mock_digest

                    # Mock the APIKey constructor
                    with patch("app.routes.api_keys.APIKey") as mock_apikey_class:
                        mock_apikey_instance = MagicMock()
                        mock_apikey_class.return_value = mock_apikey_instance

                        # Set attributes after creation
                        mock_apikey_instance.key_id = "new_key_123"
                        mock_apikey_instance.name = "Test Key"
                        mock_apikey_instance.permissions = ["read", "write"]
                        mock_apikey_instance.expires_at = datetime.now(timezone.utc) + timedelta(
                            days=365
                        )
                        mock_apikey_instance.created_at = datetime.now(timezone.utc)

                        result = await create_api_key(request, mock_db_session, mock_current_user)

                        assert result.key_id == "new_key_123"
                        assert result.name == "Test Key"
                        assert result.permissions == ["read", "write"]
                        assert "apgi_test_token" in result.key

    @pytest.mark.asyncio
    async def test_create_api_key_database_error(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test API key creation with database error."""
        request = APIKeyCreateRequest(
            name="Test Key",
            permissions=["read"],
            expires_at=None,
        )

        mock_db_session.commit.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await create_api_key(request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 500


class TestListAPIKeys:
    """Test API key listing."""

    @pytest.mark.asyncio
    async def test_list_api_keys_success(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload, mock_api_key: MagicMock
    ) -> None:
        """Test successful API key listing."""
        mock_db_session.query.return_value.filter.return_value.count.return_value = 1
        mock_db_session.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_api_key
        ]

        result = await list_api_keys(1, 10, mock_db_session, mock_current_user)

        assert len(result.api_keys) == 1
        assert result.api_keys[0].key_id == "test_key_123"
        assert result.pagination.total == 1

    @pytest.mark.asyncio
    async def test_list_api_keys_invalid_per_page(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test API key listing with invalid per_page."""
        with pytest.raises(HTTPException) as exc_info:
            await list_api_keys(1, 0, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_api_keys_database_error(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test API key listing with database error."""
        mock_db_session.query.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await list_api_keys(1, 10, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 500


class TestGetAPIKey:
    """Test API key retrieval."""

    @pytest.mark.asyncio
    async def test_get_api_key_success(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload, mock_api_key: MagicMock
    ) -> None:
        """Test successful API key retrieval."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_api_key

        result = await get_api_key("test_key_123", mock_db_session, mock_current_user)

        assert result.key_id == "test_key_123"
        assert result.name == "Test API Key"

    @pytest.mark.asyncio
    async def test_get_api_key_not_found(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test API key retrieval when key not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_api_key("nonexistent_key", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 404


class TestUpdateAPIKey:
    """Test API key updating."""

    @pytest.mark.asyncio
    async def test_update_api_key_success(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload, mock_api_key: MagicMock
    ) -> None:
        """Test successful API key update."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_api_key

        request = APIKeyUpdateRequest(
            name="Updated Name",
            permissions=["read"],
            is_active=False,
        )

        result = await update_api_key("test_key_123", request, mock_db_session, mock_current_user)

        assert result.name == "Updated Name"
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_api_key_not_found(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test API key update when key not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        request = APIKeyUpdateRequest(name="New Name", permissions=None, is_active=None)

        with pytest.raises(HTTPException) as exc_info:
            await update_api_key("nonexistent_key", request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_api_key_database_error(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload, mock_api_key: MagicMock
    ) -> None:
        """Test API key update with database error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_api_key
        mock_db_session.commit.side_effect = Exception("Database error")

        request = APIKeyUpdateRequest(name="New Name", permissions=None, is_active=None)

        with pytest.raises(HTTPException) as exc_info:
            await update_api_key("test_key_123", request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 500


class TestRotateAPIKey:
    """Test API key rotation."""

    @pytest.mark.asyncio
    async def test_rotate_api_key_success(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload, mock_api_key: MagicMock
    ) -> None:
        """Test successful API key rotation."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_api_key

        with patch("app.routes.api_keys.AuthManager") as mock_auth_manager_class:
            mock_auth_manager = MagicMock()
            mock_auth_manager.hash_password.return_value = "new_hashed_password"
            mock_auth_manager_class.return_value = mock_auth_manager

            with patch("app.routes.api_keys.secrets.token_urlsafe", return_value="new_test_token"):
                with patch("hmac.new") as mock_hmac:
                    mock_digest = MagicMock()
                    mock_digest.hexdigest.return_value = "new12345678901234567890"
                    mock_hmac.return_value = mock_digest

                    with patch("app.routes.api_keys.APIKey") as mock_apikey_class:
                        mock_new_key = MagicMock()
                        mock_new_key.key_id = "new_rotated_key_123"
                        mock_new_key.name = "Test API Key"
                        mock_new_key.permissions = ["read", "write"]
                        mock_new_key.expires_at = mock_api_key.expires_at
                        mock_new_key.created_at = datetime.now(timezone.utc)
                        mock_apikey_class.return_value = mock_new_key

                        result = await rotate_api_key(
                            "test_key_123", True, mock_db_session, mock_current_user
                        )

                        assert result.key_id == "new_rotated_key_123"
                        assert "apgi_new_test_token" in result.key
                        assert not mock_api_key.is_active

    @pytest.mark.asyncio
    async def test_rotate_api_key_not_found(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test API key rotation when key not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await rotate_api_key("nonexistent_key", True, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_rotate_api_key_database_error(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload, mock_api_key: MagicMock
    ) -> None:
        """Test API key rotation with database error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_api_key
        mock_db_session.commit.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await rotate_api_key("test_key_123", True, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 500


class TestDeleteAPIKey:
    """Test API key deletion."""

    @pytest.mark.asyncio
    async def test_delete_api_key_success(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload, mock_api_key: MagicMock
    ) -> None:
        """Test successful API key deletion."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_api_key

        result = await delete_api_key("test_key_123", mock_db_session, mock_current_user)  # type: ignore[func-returns-value]

        assert result is None  # 204 No Content
        mock_db_session.delete.assert_called_once_with(mock_api_key)
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_api_key_not_found(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload
    ) -> None:
        """Test API key deletion when key not found."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await delete_api_key("nonexistent_key", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_api_key_database_error(
        self, mock_db_session: MagicMock, mock_current_user: TokenPayload, mock_api_key: MagicMock
    ) -> None:
        """Test API key deletion with database error."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_api_key
        mock_db_session.commit.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await delete_api_key("test_key_123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == 500
