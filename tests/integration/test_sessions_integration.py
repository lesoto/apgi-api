"""
Integration tests for session routes.

Tests for session management, lifecycle, and cleanup.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.models.schemas import SessionCreateRequest


@pytest.fixture
def mock_db() -> MagicMock:
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
def mock_current_user() -> MagicMock:
    """Mock current authenticated user."""
    user = MagicMock()
    user.user_id = "user123"
    user.email = "test@example.com"
    user.roles = ["user"]
    return user


@pytest.fixture
def mock_request() -> MagicMock:
    """Mock FastAPI Request object."""
    request = MagicMock()
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_manager() -> MagicMock:
    """Mock SessionManager."""
    manager = MagicMock()
    return manager


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Mock Redis client."""
    redis_client = MagicMock()
    return redis_client


@pytest.fixture
def mock_session_service() -> MagicMock:
    """Mock session service."""
    service = MagicMock()
    service.create_session = AsyncMock(
        return_value={
            "id": "session123",
            "user_id": "user123",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
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
        self,
        mock_db: MagicMock,
        mock_current_user: MagicMock,
        mock_request: MagicMock,
        mock_manager: MagicMock,
        mock_redis_client: MagicMock,
    ) -> None:
        """Test successful session creation."""
        from app.models.schemas import SessionCreateRequest
        from app.routes.sessions import create_session

        session_request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )

        with (
            patch("app.routes.sessions.get_session_manager") as mock_get_service,
            patch("app.routes.sessions.get_redis_client") as mock_get_redis,
            patch("app.routes.sessions.get_current_user", return_value=mock_current_user),
            patch(
                "app.routes.sessions.require_permission", return_value=lambda func: func
            ),  # Mock permission decorator
            patch(
                "app.routes.sessions.check_idempotency_key", return_value=None
            ),  # Mock idempotency check
            patch(
                "app.routes.sessions.cache_idempotency_response", return_value=None
            ),  # Mock cache function
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.create_session = AsyncMock(return_value="session123")
            mock_sim_session = MagicMock()
            mock_sim_session.state.value = "active"
            mock_sim_session.created_at = datetime.now(timezone.utc)
            mock_sim_session.config = {}
            mock_manager_instance.get_session = AsyncMock(return_value=mock_sim_session)

            mock_get_service.return_value = mock_manager_instance
            mock_get_redis.return_value = mock_redis_client

            result = await create_session(
                session_request,
                mock_request,
                manager=mock_manager_instance,  # Pass the manager directly
                redis_client=mock_redis_client,
                current_user=mock_current_user,
            )

            assert result.session_id == "session123"
            assert result.status == "active"
            mock_manager_instance.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_with_custom_expiry(
        self,
        mock_db: MagicMock,
        mock_current_user: MagicMock,
        mock_request: MagicMock,
        mock_manager: MagicMock,
        mock_redis_client: MagicMock,
    ) -> None:
        """Test session creation with custom expiry."""
        from app.routes.sessions import create_session

        session_request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )

        with (
            patch("app.routes.sessions.get_session_manager") as mock_get_service,
            patch("app.routes.sessions.get_redis_client") as mock_get_redis,
            patch("app.routes.sessions.get_current_user", return_value=mock_current_user),
            patch(
                "app.routes.sessions.require_permission", return_value=lambda func: func
            ),  # Mock permission decorator
            patch(
                "app.routes.sessions.check_idempotency_key", return_value=None
            ),  # Mock idempotency check
            patch(
                "app.routes.sessions.cache_idempotency_response", return_value=None
            ),  # Mock cache function
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.create_session = AsyncMock(return_value="session123")
            mock_sim_session = MagicMock()
            mock_sim_session.state.value = "active"
            mock_sim_session.created_at = datetime.now(timezone.utc)
            mock_sim_session.config = {}
            mock_manager_instance.get_session = AsyncMock(return_value=mock_sim_session)

            mock_get_service.return_value = mock_manager_instance
            mock_get_redis.return_value = mock_redis_client

            result = await create_session(
                session_request,
                mock_request,
                manager=mock_manager_instance,
                redis_client=mock_redis_client,
                current_user=mock_current_user,
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_create_session_invalid_device_type(
        self,
        mock_db: MagicMock,
        mock_current_user: MagicMock,
        mock_request: MagicMock,
        mock_manager: MagicMock,
        mock_redis_client: MagicMock,
    ) -> None:
        """Test session creation with invalid device type."""
        from app.routes.sessions import create_session

        session_request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )

        with (
            patch("app.routes.sessions.get_session_manager") as mock_get_service,
            patch("app.routes.sessions.get_redis_client") as mock_get_redis,
            patch("app.routes.sessions.get_current_user", return_value=mock_current_user),
            patch(
                "app.routes.sessions.require_permission", return_value=lambda func: func
            ),  # Mock permission decorator
            patch(
                "app.routes.sessions.check_idempotency_key", return_value=None
            ),  # Mock idempotency check
            patch(
                "app.routes.sessions.cache_idempotency_response", return_value=None
            ),  # Mock cache function
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.create_session = AsyncMock(
                side_effect=HTTPException(status_code=400, detail="Invalid device")
            )

            mock_get_service.return_value = mock_manager_instance
            mock_get_redis.return_value = mock_redis_client

            with pytest.raises(HTTPException) as exc_info:
                await create_session(
                    session_request,
                    mock_request,
                    manager=mock_manager_instance,
                    redis_client=mock_redis_client,
                    current_user=mock_current_user,
                )

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_session_concurrent_limit(
        self,
        mock_db: MagicMock,
        mock_current_user: MagicMock,
        mock_request: MagicMock,
        mock_manager: MagicMock,
        mock_redis_client: MagicMock,
    ) -> None:
        """Test session creation respects concurrent session limit."""
        from app.routes.sessions import create_session

        session_request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )

        with (
            patch("app.routes.sessions.get_session_manager") as mock_get_service,
            patch("app.routes.sessions.get_redis_client") as mock_get_redis,
            patch("app.routes.sessions.get_current_user", return_value=mock_current_user),
            patch(
                "app.routes.sessions.require_permission", return_value=lambda func: func
            ),  # Mock permission decorator
            patch(
                "app.routes.sessions.check_idempotency_key", return_value=None
            ),  # Mock idempotency check
            patch(
                "app.routes.sessions.cache_idempotency_response", return_value=None
            ),  # Mock cache function
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.create_session = AsyncMock(
                side_effect=HTTPException(status_code=400, detail="Concurrent limit exceeded")
            )

            mock_get_service.return_value = mock_manager_instance
            mock_get_redis.return_value = mock_redis_client

            with pytest.raises(HTTPException) as exc_info:
                await create_session(
                    session_request,
                    mock_request,
                    manager=mock_manager_instance,
                    redis_client=mock_redis_client,
                    current_user=mock_current_user,
                )

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestSessionValidation:
    """Tests for session validation endpoints."""

    @pytest.mark.asyncio
    async def test_validate_session_ownership_success(
        self, mock_db: MagicMock, mock_current_user: MagicMock, mock_manager: MagicMock
    ) -> None:
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
            session_id="session123",
            user_id=mock_current_user.user_id,
            manager=mock_manager,
            db_session=mock_db,
            is_admin=False,
        )

        assert result.session_id == "session123"
        assert result.user_id == mock_current_user.user_id

    @pytest.mark.asyncio
    async def test_validate_session_ownership_not_found(
        self, mock_db: MagicMock, mock_current_user: MagicMock, mock_manager: MagicMock
    ) -> None:
        """Test validating ownership of non-existent session."""
        from fastapi import status

        from app.routes.sessions import validate_session_ownership

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await validate_session_ownership(
                session_id="session999",
                user_id=mock_current_user.user_id,
                manager=mock_manager,
                db_session=mock_db,
                is_admin=False,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_validate_session_ownership_unauthorized(
        self, mock_db: MagicMock, mock_current_user: MagicMock, mock_manager: MagicMock
    ) -> None:
        """Test validating ownership of another user's session."""
        from fastapi import status

        from app.routes.sessions import validate_session_ownership

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = "other_user"
        mock_session.is_deleted = False

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        with pytest.raises(HTTPException) as exc_info:
            await validate_session_ownership(
                session_id="session123",
                user_id=mock_current_user.user_id,
                manager=mock_manager,
                db_session=mock_db,
                is_admin=False,
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_validate_session_ownership_admin_bypass(
        self, mock_db: MagicMock, mock_current_user: MagicMock, mock_manager: MagicMock
    ) -> None:
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
            session_id="session123",
            user_id=mock_current_user.user_id,
            manager=mock_manager,
            db_session=mock_db,
            is_admin=True,
        )

        assert result.session_id == "session123"


class TestSessionDeletion:
    """Tests for session deletion endpoints."""

    @pytest.mark.asyncio
    async def test_delete_session_success(
        self, mock_db: MagicMock, mock_current_user: MagicMock, mock_manager: MagicMock
    ) -> None:
        """Test successful session deletion."""
        from app.routes.sessions import delete_session

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = mock_current_user.user_id
        mock_session.is_deleted = False

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        mock_sim_session = MagicMock()
        mock_manager.get_session = AsyncMock(return_value=mock_sim_session)
        mock_manager.delete_session = AsyncMock(return_value=None)

        result = await delete_session(
            session_id="session123",
            manager=mock_manager,
            current_user=mock_current_user,
            db=mock_db,
        )  # type: ignore[func-returns-value]

        assert result is None
        mock_manager.delete_session.assert_called_once_with("session123")

    @pytest.mark.asyncio
    async def test_delete_session_unauthorized(
        self, mock_db: MagicMock, mock_current_user: MagicMock, mock_manager: MagicMock
    ) -> None:
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
            await delete_session(
                session_id="session123",
                manager=mock_manager,
                current_user=mock_current_user,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestSessionMaintenance:
    """Tests for session maintenance operations."""

    @pytest.mark.asyncio
    async def test_session_state_updates(
        self, mock_db: MagicMock, mock_current_user: MagicMock, mock_manager: MagicMock
    ) -> None:
        """Test session state update operations."""
        from app.routes.sessions import (
            pause_session,
            reset_session,
            start_session,
            stop_session,
        )

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = mock_current_user.user_id
        mock_session.is_deleted = False
        mock_session.updated_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        mock_sim_session = MagicMock()
        mock_sim_session.state.value = "running"
        mock_sim_session.updated_at = datetime.now(timezone.utc)
        mock_manager.get_session = AsyncMock(return_value=mock_sim_session)
        mock_manager.update_session_state = AsyncMock(return_value=None)
        mock_sim_session.start = AsyncMock(return_value={"status": "running"})
        mock_sim_session.pause = AsyncMock(return_value={"status": "paused"})
        mock_sim_session.stop = AsyncMock(return_value={"status": "stopped"})
        mock_sim_session.reset = AsyncMock(return_value={"status": "created"})

        # Test start
        result = await start_session(
            session_id="session123",
            manager=mock_manager,
            current_user=mock_current_user,
            db=mock_db,
        )
        assert result.session_id == "session123"

        # Test pause
        result = await pause_session(
            session_id="session123",
            manager=mock_manager,
            current_user=mock_current_user,
            db=mock_db,
        )
        assert result.session_id == "session123"

        # Test stop
        result = await stop_session(
            session_id="session123",
            manager=mock_manager,
            current_user=mock_current_user,
            db=mock_db,
        )
        assert result.session_id == "session123"

        # Test reset
        result = await reset_session(
            session_id="session123",
            manager=mock_manager,
            current_user=mock_current_user,
            db=mock_db,
        )
        assert result.session_id == "session123"


class TestSessionList:
    """Tests for session list endpoints."""

    @pytest.mark.asyncio
    async def test_list_sessions(
        self, mock_db: MagicMock, mock_current_user: MagicMock, mock_manager: MagicMock
    ) -> None:
        """Test listing user's sessions."""
        from app.models.schemas import SessionListResponse
        from app.routes.sessions import list_sessions

        mock_sessions_data = {
            "sessions": [
                MagicMock(
                    session_id="session123",
                    state="active",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    config={},
                    description="Test session",
                ),
                MagicMock(
                    session_id="session456",
                    state="inactive",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    config={},
                    description="Test session 2",
                ),
            ],
            "total": 2,
        }
        mock_manager.list_sessions = AsyncMock(return_value=mock_sessions_data)

        result = await list_sessions(current_user=mock_current_user, manager=mock_manager)

        assert isinstance(result, SessionListResponse)
        assert len(result.sessions) == 2
        assert result.sessions[0].session_id == "session123"
        assert result.sessions[1].session_id == "session456"

    @pytest.mark.asyncio
    async def test_list_sessions_with_pagination(
        self, mock_db: MagicMock, mock_current_user: MagicMock, mock_manager: MagicMock
    ) -> None:
        """Test listing sessions with pagination."""
        from app.models.schemas import SessionListResponse
        from app.routes.sessions import list_sessions

        mock_sessions_data = {
            "sessions": [
                MagicMock(
                    session_id="session123",
                    state="active",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    config={},
                    description="Test session",
                )
            ],
            "total": 5,
        }
        mock_manager.list_sessions = AsyncMock(return_value=mock_sessions_data)

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
    async def test_session_reset(
        self, mock_db: MagicMock, mock_current_user: MagicMock, mock_manager: MagicMock
    ) -> None:
        """Test resetting session to initial state."""
        from app.routes.sessions import reset_session

        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = mock_current_user.user_id
        mock_session.is_deleted = False
        mock_session.updated_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        mock_sim_session = MagicMock()
        mock_sim_session.state.value = "created"
        mock_sim_session.updated_at = datetime.now(timezone.utc)
        mock_manager.get_session = AsyncMock(return_value=mock_sim_session)
        mock_manager.update_session_state = AsyncMock(return_value=None)
        mock_sim_session.reset = AsyncMock(return_value={"status": "created"})

        result = await reset_session(
            session_id="session123",
            manager=mock_manager,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert result.session_id == "session123"
        assert result.status == "created"
