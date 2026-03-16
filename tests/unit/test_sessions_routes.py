"""
Unit tests for session routes.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.routes.sessions import (
    validate_session_ownership,
    check_idempotency_key,
    cache_idempotency_response,
    init_session_routes,
)
from app.database.models import Session as SessionModel


class TestSessionRoutesValidation:
    """Test session route validation functions."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_manager(self):
        """Mock session manager."""
        return Mock()

    @pytest.fixture
    def mock_user(self):
        """Mock current user."""
        user = Mock()
        user.user_id = "user123"
        user.roles = ["user"]
        return user

    @pytest.mark.asyncio
    async def test_validate_session_ownership_success(self, mock_db, mock_manager, mock_user):
        """Test successful session ownership validation."""
        session = Mock(spec=SessionModel)
        session.session_id = "session123"
        session.user_id = "user123"
        session.is_deleted = False

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session
        )

        result = await validate_session_ownership("session123", "user123", mock_manager, mock_db)

        assert result == session

    @pytest.mark.asyncio
    async def test_validate_session_ownership_not_found(self, mock_db, mock_manager, mock_user):
        """Test session ownership validation when session not found."""
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await validate_session_ownership("session123", "user123", mock_manager, mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_validate_session_ownership_access_denied(self, mock_db, mock_manager, mock_user):
        """Test session ownership validation when access denied."""
        session = Mock(spec=SessionModel)
        session.session_id = "session123"
        session.user_id = "other_user"
        session.is_deleted = False

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session
        )

        with pytest.raises(HTTPException) as exc_info:
            await validate_session_ownership("session123", "user123", mock_manager, mock_db)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_validate_session_ownership_admin_bypass(self, mock_db, mock_manager, mock_user):
        """Test admin bypass for session ownership validation."""
        session = Mock(spec=SessionModel)
        session.session_id = "session123"
        session.user_id = "other_user"
        session.is_deleted = False

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session
        )
        mock_user.roles = ["admin"]

        result = await validate_session_ownership(
            "session123", "user123", mock_manager, mock_db, is_admin=True
        )

        assert result == session


class TestSessionIdempotency:
    """Test session idempotency functions."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def mock_request(self):
        """Mock HTTP request."""
        request = Mock()
        request.headers = {}
        return request

    @pytest.mark.asyncio
    async def test_check_idempotency_key_no_key(self, mock_redis, mock_request):
        """Test idempotency check with no key."""
        result = await check_idempotency_key(mock_request, "user123", mock_redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_check_idempotency_key_too_long(self, mock_redis, mock_request):
        """Test idempotency check with key too long."""
        mock_request.headers = {"Idempotency-Key": "a" * 256}

        with pytest.raises(HTTPException) as exc_info:
            await check_idempotency_key(mock_request, "user123", mock_redis)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_check_idempotency_key_cached_response(self, mock_redis, mock_request):
        """Test idempotency check with cached response."""
        mock_request.headers = {"Idempotency-Key": "test_key"}
        mock_redis.get.return_value = b'{"session_id": "test"}'

        result = await check_idempotency_key(mock_request, "user123", mock_redis)
        assert result is not None
        assert result["session_id"] == "test"

    @pytest.mark.asyncio
    async def test_check_idempotency_key_no_cache(self, mock_redis, mock_request):
        """Test idempotency check with no cached response."""
        mock_request.headers = {"Idempotency-Key": "test_key"}
        mock_redis.get.return_value = None

        result = await check_idempotency_key(mock_request, "user123", mock_redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_idempotency_response(self, mock_redis):
        """Test caching idempotency response."""
        response_data = {"session_id": "test", "status": "created"}

        await cache_idempotency_response("user123", "test_key", response_data, mock_redis)

        mock_redis.setex.assert_called_once()


class TestSessionRoutesInit:
    """Test session routes initialization."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return Mock()

    def test_init_session_routes(self, mock_redis):
        """Test session routes initialization."""
        init_session_routes(mock_redis)

        # Should not raise any errors


class TestSessionRoutesHelpers:
    """Test session route helper functions."""

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def mock_session_manager(self):
        """Mock session manager."""
        return AsyncMock()

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock()
        user.user_id = "user123"
        user.roles = ["user"]
        return user

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_list_sessions_success(self, mock_session_manager, mock_current_user):
        """Test successful session listing."""
        mock_session_manager.list_sessions.return_value = {
            "sessions": [
                Mock(
                    session_id="session1",
                    state="running",
                    created_at="2024-01-01",
                    updated_at="2024-01-02",
                    config={},
                    description="Test session",
                )
            ],
            "total": 1,
        }

        # Import after mocking to avoid circular imports
        from app.routes.sessions import list_sessions

        result = await list_sessions(1, 10, None, mock_session_manager, mock_current_user)

        assert result is not None

    @pytest.mark.asyncio
    async def test_list_sessions_invalid_page(self, mock_session_manager, mock_current_user):
        """Test session listing with invalid page."""
        from app.routes.sessions import list_sessions

        with pytest.raises(HTTPException) as exc_info:
            await list_sessions(0, 10, None, mock_session_manager, mock_current_user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_sessions_invalid_per_page(self, mock_session_manager, mock_current_user):
        """Test session listing with invalid per_page."""
        from app.routes.sessions import list_sessions

        with pytest.raises(HTTPException) as exc_info:
            await list_sessions(1, 101, None, mock_session_manager, mock_current_user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_sessions_error(self, mock_session_manager, mock_current_user):
        """Test session listing with error."""
        mock_session_manager.list_sessions.side_effect = Exception("DB Error")

        from app.routes.sessions import list_sessions

        with pytest.raises(HTTPException) as exc_info:
            await list_sessions(1, 10, None, mock_session_manager, mock_current_user)
        assert exc_info.value.status_code == 500


class TestSessionRoutesGetSession:
    """Test get session route."""

    @pytest.fixture
    def mock_session_manager(self):
        """Mock session manager."""
        return AsyncMock()

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock()
        user.user_id = "user123"
        user.roles = ["user"]
        return user

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_get_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session retrieval."""
        session = Mock()
        session.session_id = "session123"
        session.state.value = "running"
        session.created_at = "2024-01-01"
        session.updated_at = "2024-01-02"
        session.config = {}
        session.description = "Test session"

        mock_session_manager.get_session.return_value = session

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        from app.routes.sessions import get_session

        result = await get_session("session123", mock_session_manager, mock_current_user, mock_db)

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, mock_session_manager, mock_current_user, mock_db):
        """Test session retrieval when not found."""
        mock_session_manager.get_session.side_effect = ValueError("Session not found")

        from app.routes.sessions import get_session
        from app.exceptions import SessionNotFoundError

        with pytest.raises(SessionNotFoundError):
            await get_session("session123", mock_session_manager, mock_current_user, mock_db)


class TestSessionRoutesActions:
    """Test session action routes."""

    @pytest.fixture
    def mock_session_manager(self):
        """Mock session manager."""
        return AsyncMock()

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock()
        user.user_id = "user123"
        user.roles = ["user"]
        return user

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.mark.asyncio
    async def test_start_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session start."""
        session = Mock()
        session.state.value = "running"
        session.updated_at = "2024-01-02"

        mock_session_manager.get_session.return_value = session
        session.start = AsyncMock(return_value={"status": "running"})

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        from app.routes.sessions import start_session

        result = await start_session("session123", mock_session_manager, mock_current_user, mock_db)

        assert result is not None

    @pytest.mark.asyncio
    async def test_pause_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session pause."""
        session = Mock()
        session.state.value = "paused"
        session.updated_at = "2024-01-02"

        mock_session_manager.get_session.return_value = session
        session.pause = AsyncMock(return_value={"status": "paused"})

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        from app.routes.sessions import pause_session

        result = await pause_session("session123", mock_session_manager, mock_current_user, mock_db)

        assert result is not None

    @pytest.mark.asyncio
    async def test_stop_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session stop."""
        session = Mock()
        session.state.value = "stopped"
        session.updated_at = "2024-01-02"

        mock_session_manager.get_session.return_value = session
        session.stop = AsyncMock(return_value={"status": "stopped"})

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        from app.routes.sessions import stop_session

        result = await stop_session("session123", mock_session_manager, mock_current_user, mock_db)

        assert result is not None

    @pytest.mark.asyncio
    async def test_reset_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session reset."""
        session = Mock()
        session.state.value = "created"
        session.updated_at = "2024-01-02"

        mock_session_manager.get_session.return_value = session
        session.reset = AsyncMock(return_value={"status": "created"})

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        from app.routes.sessions import reset_session

        result = await reset_session("session123", mock_session_manager, mock_current_user, mock_db)

        assert result is not None

    @pytest.mark.asyncio
    async def test_step_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session step."""
        session = Mock()
        session.state.value = "running"
        session.updated_at = "2024-01-02"
        session.step = AsyncMock(return_value={"allostatic": {}})

        mock_session_manager.get_session.return_value = session

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        from app.routes.sessions import step_session

        result = await step_session(
            "session123", None, mock_session_manager, mock_current_user, mock_db
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_delete_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session deletion."""
        session = Mock()
        session.session_id = "session123"

        mock_session_manager.get_session.return_value = session
        mock_session_manager.delete_session = AsyncMock()

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        from app.routes.sessions import delete_session

        result = await delete_session(
            "session123", mock_session_manager, mock_current_user, mock_db
        )

        assert result is None
