"""
Integration tests for session routes.

Tests for session management, lifecycle, and cleanup.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException, status
from datetime import datetime, timedelta
from app.models.schemas import SessionCreateRequest


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.query = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    db.delete = MagicMock()
    return db


@pytest.fixture
def mock_current_user():
    """Mock current authenticated user."""
    user = MagicMock()
    user.user_id = "user123"
    user.email = "test@example.com"
    user.roles = ["user"]
    return user


@pytest.fixture
def mock_request():
    """Mock FastAPI Request object."""
    request = MagicMock()
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_manager():
    """Mock SessionManager."""
    manager = MagicMock()
    return manager


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    redis_client = MagicMock()
    return redis_client


@pytest.fixture
def mock_session_service():
    """Mock session service."""
    service = MagicMock()
    service.create_session = AsyncMock(
        return_value={
            "id": "session123",
            "user_id": "user123",
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=24),
            "is_active": True,
        }
    )
    service.validate_session = AsyncMock(return_value=True)
    service.invalidate_session = AsyncMock(return_value=True)
    service.cleanup_expired_sessions = AsyncMock(return_value=10)
    return service


class TestSessionCreation:
    """Tests for session creation endpoints."""

    @pytest.mark.asyncio
    async def test_create_session_success(
        self, mock_db, mock_current_user, mock_request, mock_manager, mock_redis_client
    ):
        """Test successful session creation."""
        from app.routes.sessions import create_session
        from app.models.schemas import SessionCreateRequest

        session_request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )

        with patch("app.routes.sessions.get_session_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.create_session = AsyncMock(
                return_value={
                    "id": "session123",
                    "user_id": "user123",
                    "created_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(hours=24),
                    "is_active": True,
                }
            )
            mock_get_service.return_value = mock_service

            result = await create_session(
                session_request,
                mock_request,
                mock_manager,
                mock_redis_client,
                mock_current_user,
            )

            assert result.session_id == "session123"
            assert result.status == "active"
            mock_service.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_with_custom_expiry(self, mock_db, mock_current_user):
        """Test session creation with custom expiry."""
        from app.routes.sessions import create_session

        session_request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )

        with patch("app.routes.sessions.get_session_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.create_session = AsyncMock(
                return_value={
                    "id": "session123",
                    "user_id": "user123",
                    "expires_at": datetime.utcnow() + timedelta(hours=48),
                    "is_active": True,
                }
            )
            mock_get_service.return_value = mock_service

            result = await create_session(session_request, mock_db, mock_current_user)

            assert result is not None

    @pytest.mark.asyncio
    async def test_create_session_invalid_device_type(self, mock_db, mock_current_user):
        """Test session creation with invalid device type."""
        from app.routes.sessions import create_session

        session_request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_session(session_request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_session_concurrent_limit(self, mock_db, mock_current_user):
        """Test session creation respects concurrent session limit."""
        from app.routes.sessions import create_session

        session_request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )

        mock_db.query.return_value.filter.return_value.count.return_value = 5

        with pytest.raises(HTTPException) as exc_info:
            await create_session(session_request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestSessionValidation:
    """Tests for session validation endpoints."""

    @pytest.mark.asyncio
    async def test_validate_session_ownership_success(
        self, mock_db, mock_current_user, mock_manager
    ):
        """Test successful session ownership validation."""
        from app.routes.sessions import validate_session_ownership

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = mock_current_user.user_id
        mock_session.is_deleted = False

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        result = await validate_session_ownership(
            "user123", mock_current_user.user_id, mock_manager, mock_db, is_admin=False
        )

        assert result.session_id == "session123"
        assert result.user_id == mock_current_user.user_id

    @pytest.mark.asyncio
    async def test_validate_session_ownership_not_found(
        self, mock_db, mock_current_user, mock_manager
    ):
        """Test validating ownership of non-existent session."""
        from app.routes.sessions import validate_session_ownership
        from fastapi import status

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await validate_session_ownership(
                "session999",
                mock_current_user.user_id,
                mock_manager,
                mock_db,
                is_admin=False,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_validate_session_ownership_unauthorized(
        self, mock_db, mock_current_user, mock_manager
    ):
        """Test validating ownership of another user's session."""
        from app.routes.sessions import validate_session_ownership
        from fastapi import status

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = "other_user"
        mock_session.is_deleted = False

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        with pytest.raises(HTTPException) as exc_info:
            await validate_session_ownership(
                "session123",
                mock_current_user.user_id,
                mock_manager,
                mock_db,
                is_admin=False,
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_validate_session_ownership_admin_bypass(
        self, mock_db, mock_current_user, mock_manager
    ):
        """Test that admin can validate any session ownership."""
        from app.routes.sessions import validate_session_ownership

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = "other_user"
        mock_session.is_deleted = False

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        result = await validate_session_ownership(
            "session123", mock_current_user.user_id, mock_manager, mock_db, is_admin=True
        )

        assert result.session_id == "session123"


class TestSessionDeletion:
    """Tests for session deletion endpoints."""

    @pytest.mark.asyncio
    async def test_delete_session_success(self, mock_db, mock_current_user, mock_manager):
        """Test successful session deletion."""
        from app.routes.sessions import delete_session

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = mock_current_user.user_id
        mock_session.is_deleted = False

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        with patch.object(mock_manager, "get_session") as mock_get_session, patch.object(
            mock_manager, "delete_session"
        ) as mock_delete:
            mock_get_session.return_value = MagicMock()

            result = await delete_session("session123", mock_manager, mock_current_user, mock_db)

            assert result is None
            mock_delete.assert_called_once_with("session123")

    @pytest.mark.asyncio
    async def test_delete_session_unauthorized(self, mock_db, mock_current_user, mock_manager):
        """Test deleting another user's session."""
        from app.routes.sessions import delete_session

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = "other_user"
        mock_session.is_deleted = False

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        with pytest.raises(HTTPException) as exc_info:
            await delete_session("session123", mock_manager, mock_current_user, mock_db)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestSessionMaintenance:
    """Tests for session maintenance operations."""

    @pytest.mark.asyncio
    async def test_session_state_updates(self, mock_db, mock_current_user, mock_manager):
        """Test session state update operations."""
        from app.routes.sessions import (
            start_session,
            pause_session,
            stop_session,
            reset_session,
        )

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = mock_current_user.user_id
        mock_session.is_deleted = False
        mock_session.updated_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        with patch.object(mock_manager, "get_session") as mock_get_session, patch.object(
            mock_manager, "update_session_state"
        ) as mock_update:
            mock_sim_session = MagicMock()
            mock_sim_session.state.value = "running"
            mock_sim_session.updated_at = datetime.utcnow()
            mock_get_session.return_value = mock_sim_session
            mock_sim_session.start.return_value = {"status": "running"}
            mock_sim_session.pause.return_value = {"status": "paused"}
            mock_sim_session.stop.return_value = {"status": "stopped"}
            mock_sim_session.reset.return_value = {"status": "created"}

            # Test start
            result = await start_session("session123", mock_manager, mock_current_user, mock_db)
            assert result.session_id == "session123"

            # Test pause
            result = await pause_session("session123", mock_manager, mock_current_user, mock_db)
            assert result.session_id == "session123"

            # Test stop
            result = await stop_session("session123", mock_manager, mock_current_user, mock_db)
            assert result.session_id == "session123"

            # Test reset
            result = await reset_session("session123", mock_manager, mock_current_user, mock_db)
            assert result.session_id == "session123"


class TestSessionList:
    """Tests for session list endpoints."""

    @pytest.mark.asyncio
    async def test_list_sessions(self, mock_db, mock_current_user, mock_manager):
        """Test listing user's sessions."""
        from app.routes.sessions import list_sessions
        from app.models.schemas import SessionListResponse

        with patch.object(mock_manager, "list_sessions") as mock_list:
            mock_sessions_data = {
                "sessions": [
                    MagicMock(
                        session_id="session123",
                        state="active",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        config={},
                        description="Test session",
                    ),
                    MagicMock(
                        session_id="session456",
                        state="inactive",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        config={},
                        description="Test session 2",
                    ),
                ],
                "total": 2,
            }
            mock_list.return_value = mock_sessions_data

            result = await list_sessions(current_user=mock_current_user, manager=mock_manager)

            assert isinstance(result, SessionListResponse)
            assert len(result.sessions) == 2
            assert result.sessions[0].session_id == "session123"
            assert result.sessions[1].session_id == "session456"

    @pytest.mark.asyncio
    async def test_list_sessions_with_pagination(self, mock_db, mock_current_user, mock_manager):
        """Test listing sessions with pagination."""
        from app.routes.sessions import list_sessions
        from app.models.schemas import SessionListResponse

        with patch.object(mock_manager, "list_sessions") as mock_list:
            mock_sessions_data = {
                "sessions": [
                    MagicMock(
                        session_id="session123",
                        state="active",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        config={},
                        description="Test session",
                    )
                ],
                "total": 5,
            }
            mock_list.return_value = mock_sessions_data

            result = await list_sessions(
                page=1,
                per_page=10,
                manager=mock_manager,
                current_user=mock_current_user,
            )

            assert isinstance(result, SessionListResponse)
            assert len(result.sessions) == 1
            assert result.pagination.page == 1
            assert result.pagination.per_page == 10
            assert result.pagination.total == 5


class TestSessionPersistence:
    """Tests for session persistence across requests."""

    @pytest.mark.asyncio
    async def test_session_reset(self, mock_db, mock_current_user, mock_manager):
        """Test resetting session to initial state."""
        from app.routes.sessions import reset_session

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = mock_current_user.user_id
        mock_session.is_deleted = False
        mock_session.updated_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        with patch.object(mock_manager, "get_session") as mock_get_session, patch.object(
            mock_manager, "update_session_state"
        ) as mock_update:
            mock_sim_session = MagicMock()
            mock_sim_session.state.value = "created"
            mock_sim_session.updated_at = datetime.utcnow()
            mock_get_session.return_value = mock_sim_session
            mock_sim_session.reset.return_value = {"status": "created"}

            result = await reset_session("session123", mock_manager, mock_current_user, mock_db)

            assert result.session_id == "session123"
            assert result.status == "created"
