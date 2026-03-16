"""
Focused tests for session routes to achieve 100% coverage.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.routes.sessions import (
    validate_session_ownership,
    check_idempotency_key,
    cache_idempotency_response,
    init_session_routes,
    get_redis_client,
    get_session_manager,
    list_sessions,
    create_session,
    get_session,
    get_session_metrics,
    get_session_tasks,
    start_session,
    pause_session,
    stop_session,
    reset_session,
    delete_session,
    step_session,
    SessionRoutesState,
    _state,
)
from app.database.models import Session as SessionModel, Task
from app.models.schemas import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionActionResponse,
    SessionListResponse,
    SessionMetricsResponse,
    SessionResponse,
    SessionTaskListResponse,
)
from app.exceptions import ServiceUnavailableError, SessionNotFoundError


class TestSessionRoutesState:
    """Test SessionRoutesState class."""

    def test_session_routes_state_init(self):
        """Test SessionRoutesState initialization."""
        state = SessionRoutesState()
        assert state.redis_client is None
        assert state.session_manager is None


class TestDependencyFunctions:
    """Test dependency injection functions."""

    def test_get_redis_client_success(self):
        """Test successful Redis client retrieval."""
        mock_redis = Mock()
        _state.redis_client = mock_redis

        result = get_redis_client()
        assert result == mock_redis

    def test_get_redis_client_not_initialized(self):
        """Test Redis client retrieval when not initialized."""
        _state.redis_client = None

        with pytest.raises(ServiceUnavailableError) as exc_info:
            get_redis_client()
        assert "Redis client not initialized" in str(exc_info.value)

    def test_get_session_manager_success(self):
        """Test successful session manager retrieval."""
        mock_manager = Mock()
        _state.session_manager = mock_manager

        result = get_session_manager()
        assert result == mock_manager

    def test_get_session_manager_not_initialized(self):
        """Test session manager retrieval when not initialized."""
        _state.session_manager = None

        with pytest.raises(ServiceUnavailableError) as exc_info:
            get_session_manager()
        assert "Session manager not initialized" in str(exc_info.value)


class TestSessionOwnershipValidation:
    """Test session ownership validation."""

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

        result = await validate_session_ownership(
            "session123", "user123", mock_manager, mock_db, is_admin=True
        )

        assert result == session


class TestIdempotencyFunctions:
    """Test idempotency functions."""

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


class TestInitSessionRoutes:
    """Test session routes initialization."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return Mock()

    def test_init_session_routes(self, mock_redis):
        """Test session routes initialization."""
        init_session_routes(mock_redis)

        assert _state.redis_client == mock_redis
        assert _state.session_manager is not None


class TestListSessions:
    """Test list sessions endpoint."""

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

    @pytest.mark.asyncio
    async def test_list_sessions_success(self, mock_session_manager, mock_current_user):
        """Test successful session listing."""
        mock_session = Mock()
        mock_session.session_id = "session1"
        mock_session.state = "running"
        mock_session.created_at = datetime.utcnow()
        mock_session.updated_at = datetime.utcnow()
        mock_session.config = {"param": "value"}
        mock_session.description = "Test session"

        mock_session_manager.list_sessions.return_value = {
            "sessions": [mock_session],
            "total": 1,
        }

        result = await list_sessions(1, 10, None, mock_session_manager, mock_current_user)

        assert isinstance(result, SessionListResponse)
        assert len(result.sessions) == 1

    @pytest.mark.asyncio
    async def test_list_sessions_invalid_page(self, mock_session_manager, mock_current_user):
        """Test session listing with invalid page."""
        with pytest.raises(HTTPException) as exc_info:
            await list_sessions(0, 10, None, mock_session_manager, mock_current_user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_sessions_invalid_per_page(self, mock_session_manager, mock_current_user):
        """Test session listing with invalid per_page."""
        with pytest.raises(HTTPException) as exc_info:
            await list_sessions(1, 101, None, mock_session_manager, mock_current_user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_sessions_service_error(self, mock_session_manager, mock_current_user):
        """Test session listing with service error."""
        mock_session_manager.list_sessions.side_effect = Exception("DB Error")

        with pytest.raises(HTTPException) as exc_info:
            await list_sessions(1, 10, None, mock_session_manager, mock_current_user)
        assert exc_info.value.status_code == 500


class TestCreateSession:
    """Test create session endpoint."""

    @pytest.fixture
    def mock_session_manager(self):
        """Mock session manager."""
        return AsyncMock()

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        user = Mock()
        user.user_id = "user123"
        user.roles = ["user"]
        return user

    @pytest.fixture
    def mock_request(self):
        """Mock HTTP request."""
        request = Mock()
        request.headers = {}
        return request

    @pytest.mark.asyncio
    async def test_create_session_success(
        self, mock_session_manager, mock_redis_client, mock_current_user, mock_request
    ):
        """Test successful session creation."""
        session_request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )

        mock_session = Mock()
        mock_session.session_id = "session123"
        mock_session.state.value = "created"
        mock_session.created_at = datetime.utcnow()
        mock_session.config = {"param": "value"}

        mock_session_manager.create_session.return_value = "session123"
        mock_session_manager.get_session.return_value = mock_session

        result = await create_session(
            session_request,
            mock_request,
            mock_session_manager,
            mock_redis_client,
            mock_current_user,
        )

        assert isinstance(result, SessionCreateResponse)
        assert result.session_id == "session123"

    @pytest.mark.asyncio
    async def test_create_session_with_idempotency_cache_hit(
        self, mock_session_manager, mock_redis_client, mock_current_user, mock_request
    ):
        """Test session creation with idempotency cache hit."""
        session_request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )

        mock_request.headers = {"Idempotency-Key": "test_key"}
        cached_response = {
            "session_id": "cached_session",
            "status": "created",
            "created_at": datetime.utcnow().isoformat(),
            "config": {},
        }
        mock_redis_client.get.return_value = json.dumps(cached_response).encode()

        result = await create_session(
            session_request,
            mock_request,
            mock_session_manager,
            mock_redis_client,
            mock_current_user,
        )

        assert result.session_id == "cached_session"


class TestGetSession:
    """Test get session endpoint."""

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
        session.created_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
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

        result = await get_session("session123", mock_session_manager, mock_current_user, mock_db)

        assert isinstance(result, SessionResponse)
        assert result.session_id == "session123"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, mock_session_manager, mock_current_user, mock_db):
        """Test session retrieval when not found."""
        mock_session_manager.get_session.side_effect = ValueError("Session not found")

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        with pytest.raises(SessionNotFoundError):
            await get_session("session123", mock_session_manager, mock_current_user, mock_db)


class TestGetSessionMetrics:
    """Test get session metrics endpoint."""

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
    async def test_get_session_metrics_success(
        self, mock_session_manager, mock_current_user, mock_db
    ):
        """Test successful session metrics retrieval."""
        session = Mock()
        session.get_state = AsyncMock(
            return_value={
                "allostatic": {"load": 0.8, "threshold": 0.7},
                "body": {"energy": 0.6, "arousal": 0.5},
                "ignition": {"intensity": 0.9, "active": True},
            }
        )

        mock_session_manager.get_session.return_value = session

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        result = await get_session_metrics(
            "session123", mock_session_manager, mock_current_user, mock_db
        )

        assert isinstance(result, SessionMetricsResponse)
        assert result.session_id == "session123"


class TestGetSessionTasks:
    """Test get session tasks endpoint."""

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
    async def test_get_session_tasks_success(self, mock_current_user, mock_db):
        """Test successful session tasks retrieval."""
        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False

        task1 = Mock(spec=Task)
        task1.task_id = "task1"
        task1.status = "completed"
        task1.result_data = '{"result": "success"}'
        task1.error_message = None

        mock_db.query.return_value.filter.return_value.first.return_value = session_model
        mock_db.query.return_value.filter.return_value.all.return_value = [task1]

        result = await get_session_tasks("session123", mock_db, mock_current_user)

        assert isinstance(result, SessionTaskListResponse)
        assert len(result.tasks) == 1
        assert result.tasks[0].task_id == "task1"

    @pytest.mark.asyncio
    async def test_get_session_tasks_session_not_found(self, mock_current_user, mock_db):
        """Test session tasks retrieval when session not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_session_tasks("session123", mock_db, mock_current_user)
        assert exc_info.value.status_code == 404


class TestSessionActions:
    """Test session action endpoints."""

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
        session.updated_at = datetime.utcnow()
        session.start = AsyncMock(return_value={"status": "running"})

        mock_session_manager.get_session.return_value = session

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        result = await start_session("session123", mock_session_manager, mock_current_user, mock_db)

        assert isinstance(result, SessionActionResponse)
        assert result.session_id == "session123"

    @pytest.mark.asyncio
    async def test_pause_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session pause."""
        session = Mock()
        session.state.value = "paused"
        session.updated_at = datetime.utcnow()
        session.pause = AsyncMock(return_value={"status": "paused"})

        mock_session_manager.get_session.return_value = session

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        result = await pause_session("session123", mock_session_manager, mock_current_user, mock_db)

        assert isinstance(result, SessionActionResponse)
        assert result.status == "paused"

    @pytest.mark.asyncio
    async def test_stop_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session stop."""
        session = Mock()
        session.state.value = "stopped"
        session.updated_at = datetime.utcnow()
        session.stop = AsyncMock(return_value={"status": "stopped"})

        mock_session_manager.get_session.return_value = session

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        result = await stop_session("session123", mock_session_manager, mock_current_user, mock_db)

        assert isinstance(result, SessionActionResponse)
        assert result.status == "stopped"

    @pytest.mark.asyncio
    async def test_reset_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session reset."""
        session = Mock()
        session.state.value = "created"
        session.updated_at = datetime.utcnow()
        session.reset = AsyncMock(return_value={"status": "created"})

        mock_session_manager.get_session.return_value = session

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        result = await reset_session("session123", mock_session_manager, mock_current_user, mock_db)

        assert isinstance(result, SessionActionResponse)
        assert result.status == "created"

    @pytest.mark.asyncio
    async def test_step_session_success(self, mock_session_manager, mock_current_user, mock_db):
        """Test successful session step."""
        session = Mock()
        session.state.value = "running"
        session.updated_at = datetime.utcnow()
        session.step = AsyncMock(return_value={"allostatic": {}})

        mock_session_manager.get_session.return_value = session

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        result = await step_session(
            "session123", None, mock_session_manager, mock_current_user, mock_db
        )

        assert isinstance(result, SessionActionResponse)
        assert result.status == "stepped"

    @pytest.mark.asyncio
    async def test_step_session_with_input(self, mock_session_manager, mock_current_user, mock_db):
        """Test session step with input."""
        session = Mock()
        session.state.value = "running"
        session.updated_at = datetime.utcnow()
        session.step = AsyncMock(return_value={"allostatic": {}})

        mock_session_manager.get_session.return_value = session

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        extero_input = {"stimulus": "test"}
        result = await step_session(
            "session123", extero_input, mock_session_manager, mock_current_user, mock_db
        )

        assert result.status == "stepped"

    @pytest.mark.asyncio
    async def test_step_session_error(self, mock_session_manager, mock_current_user, mock_db):
        """Test session step with error."""
        session = Mock()
        session.state.value = "running"
        session.step = AsyncMock(side_effect=ValueError("Cannot step"))

        mock_session_manager.get_session.return_value = session

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        with pytest.raises(HTTPException) as exc_info:
            await step_session("session123", None, mock_session_manager, mock_current_user, mock_db)
        assert exc_info.value.status_code == 400

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

        result = await delete_session(
            "session123", mock_session_manager, mock_current_user, mock_db
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, mock_session_manager, mock_current_user, mock_db):
        """Test session deletion when not found."""
        mock_session_manager.get_session.side_effect = ValueError("Session not found")

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        with pytest.raises(SessionNotFoundError):
            await delete_session("session123", mock_session_manager, mock_current_user, mock_db)


class TestEdgeCases:
    """Test edge cases and error conditions."""

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
    async def test_large_idempotency_key(self, mock_redis):
        """Test idempotency key at maximum length."""
        mock_request = Mock()
        mock_request.headers = {"Idempotency-Key": "a" * 255}

        result = await check_idempotency_key(mock_request, "user123", mock_redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_deleted_session_filter(self, mock_session_manager, mock_current_user, mock_db):
        """Test that deleted sessions are filtered out."""
        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = True  # Deleted session

        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        with pytest.raises(HTTPException) as exc_info:
            await validate_session_ownership("session123", "user123", mock_session_manager, mock_db)
        assert exc_info.value.status_code == 404
