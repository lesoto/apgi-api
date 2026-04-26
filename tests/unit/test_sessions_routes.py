"""
Unit tests for session routes.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models import Session as SessionModel
from app.models.schemas import TokenPayload
from app.routes.sessions import (
    cache_idempotency_response,
    check_idempotency_key,
    init_session_routes,
    validate_session_ownership,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

FAKE_USER = TokenPayload(
    user_id="user-123",
    username="testuser",
    roles=["admin"],
    exp=datetime.now(timezone.utc) + timedelta(hours=1),
    token_type="access",
    permissions=[],
)


@asynccontextmanager
async def noop_lifespan(app: object) -> AsyncIterator[None]:
    yield


def _make_session_model(session_id: str = "sess-1", user_id: str = "user-123") -> MagicMock:
    m = MagicMock(spec=SessionModel)
    m.session_id = session_id
    m.user_id = user_id
    m.is_deleted = False
    return m


def _make_sim_session(state_val: str = "running") -> MagicMock:
    s = MagicMock()
    s.session_id = "sess-1"
    s.state = MagicMock()
    s.state.value = state_val
    s.created_at = datetime.now(timezone.utc)
    s.updated_at = datetime.now(timezone.utc)
    s.config = {}
    s.description = "Test session"
    return s


def _make_query_chain(session_model: MagicMock) -> MagicMock:
    """Create a mock query chain that returns the session_model."""
    q = MagicMock()
    q.filter.return_value.filter.return_value.first.return_value = session_model
    return q


def _make_task_query_chain(tasks: list[object]) -> MagicMock:
    """Create a mock query chain that returns the tasks list."""
    q = MagicMock()
    q.filter.return_value.all.return_value = tasks
    return q


# ---------------------------------------------------------------------------
# TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_manager() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_redis() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(mock_db: MagicMock, mock_manager: AsyncMock, mock_redis: AsyncMock) -> TestClient:
    from app.database.connection import get_db
    from app.main import create_app
    from app.routes.sessions import get_redis_client, get_session_manager
    from app.services.authorization import get_current_user

    app = create_app(test_mode=True)
    app.router.lifespan_context = noop_lifespan
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_session_manager] = lambda: mock_manager
    app.dependency_overrides[get_redis_client] = lambda: mock_redis
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests for get_redis_client / get_session_manager error paths
# ---------------------------------------------------------------------------


class TestDependencyErrors:
    def test_get_redis_client_not_initialized(self) -> None:
        """get_redis_client raises ServiceUnavailableError when not initialized."""
        from app.exceptions import ServiceUnavailableError
        from app.routes.sessions import _state, get_redis_client

        original = _state.redis_client
        _state.redis_client = None
        try:
            with pytest.raises(ServiceUnavailableError):
                get_redis_client()
        finally:
            _state.redis_client = original

    def test_get_redis_client_initialized(self) -> None:
        """get_redis_client returns client when initialized."""
        from app.routes.sessions import _state, get_redis_client

        mock_client = MagicMock()
        original = _state.redis_client
        _state.redis_client = mock_client
        try:
            result = get_redis_client()
            assert result is mock_client
        finally:
            _state.redis_client = original

    def test_get_session_manager_not_initialized(self) -> None:
        """get_session_manager raises ServiceUnavailableError when not initialized."""
        from app.exceptions import ServiceUnavailableError
        from app.routes.sessions import _state, get_session_manager

        original = _state.session_manager
        _state.session_manager = None
        try:
            with pytest.raises(ServiceUnavailableError):
                get_session_manager()
        finally:
            _state.session_manager = original

    def test_get_session_manager_initialized(self) -> None:
        """get_session_manager returns manager when initialized."""
        from app.routes.sessions import _state, get_session_manager

        mock_mgr = MagicMock()
        original = _state.session_manager
        _state.session_manager = mock_mgr
        try:
            result = get_session_manager()
            assert result is mock_mgr
        finally:
            _state.session_manager = original


# ---------------------------------------------------------------------------
# Tests for validate_session_ownership (unit-level)
# ---------------------------------------------------------------------------


class TestSessionRoutesValidation:
    @pytest.fixture
    def mock_db(self) -> MagicMock:
        return MagicMock(spec=Session)

    @pytest.fixture
    def mock_manager(self) -> MagicMock:
        return MagicMock()

    @pytest.mark.asyncio
    async def test_validate_session_ownership_success(
        self, mock_db: MagicMock, mock_manager: AsyncMock
    ) -> None:
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
    async def test_validate_session_ownership_not_found(
        self, mock_db: MagicMock, mock_manager: MagicMock
    ) -> None:
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            await validate_session_ownership("session123", "user123", mock_manager, mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_validate_session_ownership_access_denied(
        self, mock_db: MagicMock, mock_manager: MagicMock
    ) -> None:
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
    async def test_validate_session_ownership_admin_bypass(
        self, mock_db: MagicMock, mock_manager: MagicMock
    ) -> None:
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


# ---------------------------------------------------------------------------
# Tests for idempotency helpers
# ---------------------------------------------------------------------------


class TestSessionIdempotency:
    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        request = MagicMock()
        request.headers = {}
        return request

    @pytest.mark.asyncio
    async def test_check_idempotency_key_no_key(
        self, mock_redis: MagicMock, mock_request: MagicMock
    ) -> None:
        result = await check_idempotency_key(mock_request, "user123", mock_redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_check_idempotency_key_too_long(
        self, mock_redis: MagicMock, mock_request: MagicMock
    ) -> None:
        mock_request.headers = {"Idempotency-Key": "a" * 256}
        with pytest.raises(HTTPException) as exc_info:
            await check_idempotency_key(mock_request, "user123", mock_redis)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_check_idempotency_key_cached_response(
        self, mock_redis: MagicMock, mock_request: MagicMock
    ) -> None:
        mock_request.headers = {"Idempotency-Key": "test_key"}
        mock_redis.get = AsyncMock(return_value=b'{"session_id": "test"}')
        result = await check_idempotency_key(mock_request, "user123", mock_redis)
        assert result is not None
        assert result["session_id"] == "test"

    @pytest.mark.asyncio
    async def test_check_idempotency_key_no_cache(
        self, mock_redis: MagicMock, mock_request: MagicMock
    ) -> None:
        mock_request.headers = {"Idempotency-Key": "test_key"}
        mock_redis.get = AsyncMock(return_value=None)
        result = await check_idempotency_key(mock_request, "user123", mock_redis)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_idempotency_response(self, mock_redis: MagicMock) -> None:
        response_data = {"session_id": "test", "status": "created"}
        mock_redis.setex = AsyncMock()
        await cache_idempotency_response("user123", "test_key", response_data, mock_redis)
        mock_redis.setex.assert_called_once()


class TestSessionRoutesInit:
    def test_init_session_routes(self) -> None:
        mock_redis = Mock()
        init_session_routes(mock_redis)  # Should not raise


# ---------------------------------------------------------------------------
# Tests for list_sessions (unit-level)
# ---------------------------------------------------------------------------


class TestListSessionsUnit:
    @pytest.fixture
    def mock_session_manager(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_current_user(self) -> MagicMock:
        user = MagicMock()
        user.user_id = "user123"
        user.roles = ["user"]
        return user

    @pytest.mark.asyncio
    async def test_list_sessions_success(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock
    ) -> None:
        mock_session_manager.list_sessions = AsyncMock(
            return_value={
                "sessions": [
                    Mock(
                        session_id="session1",
                        state="running",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        config={},
                        description="Test session",
                    )
                ],
                "total": 1,
            }
        )
        from app.routes.sessions import list_sessions

        result = await list_sessions(1, 10, None, mock_session_manager, mock_current_user)
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_sessions_invalid_page(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock
    ) -> None:
        from app.routes.sessions import list_sessions

        with pytest.raises(HTTPException) as exc_info:
            await list_sessions(0, 10, None, mock_session_manager, mock_current_user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_sessions_invalid_per_page(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock
    ) -> None:
        from app.routes.sessions import list_sessions

        with pytest.raises(HTTPException) as exc_info:
            await list_sessions(1, 101, None, mock_session_manager, mock_current_user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_sessions_per_page_zero(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock
    ) -> None:
        from app.routes.sessions import list_sessions

        with pytest.raises(HTTPException) as exc_info:
            await list_sessions(1, 0, None, mock_session_manager, mock_current_user)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_list_sessions_error(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock
    ) -> None:
        mock_session_manager.list_sessions = AsyncMock(side_effect=Exception("DB Error"))
        from app.routes.sessions import list_sessions

        with pytest.raises(HTTPException) as exc_info:
            await list_sessions(1, 10, None, mock_session_manager, mock_current_user)
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Route-level tests via TestClient
# ---------------------------------------------------------------------------


class TestListSessionsRoute:
    def test_list_sessions_success(self, client: TestClient, mock_manager: MagicMock) -> None:
        sim_session = MagicMock()
        sim_session.session_id = "sess-1"
        sim_session.state = "running"  # must be a plain string for SessionResponse
        sim_session.created_at = datetime.now(timezone.utc)
        sim_session.updated_at = datetime.now(timezone.utc)
        sim_session.config = {}
        sim_session.description = "Test"
        mock_manager.list_sessions = AsyncMock(
            return_value={
                "sessions": [sim_session],
                "total": 1,
            }
        )
        resp = client.get("/v1/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert data["pagination"]["total"] == 1

    def test_list_sessions_invalid_page(self, client: TestClient) -> None:
        resp = client.get("/v1/sessions?page=0")
        assert resp.status_code == 400

    def test_list_sessions_invalid_per_page(self, client: TestClient) -> None:
        resp = client.get("/v1/sessions?per_page=0")
        assert resp.status_code == 400

    def test_list_sessions_per_page_too_large(self, client: TestClient) -> None:
        resp = client.get("/v1/sessions?per_page=101")
        assert resp.status_code == 400

    def test_list_sessions_500(self, client: TestClient, mock_manager: MagicMock) -> None:
        mock_manager.list_sessions = AsyncMock(side_effect=Exception("DB error"))
        resp = client.get("/v1/sessions")
        assert resp.status_code == 500


class TestCreateSessionRoute:
    def _setup_manager(self, mock_manager: MagicMock, mock_redis: MagicMock) -> None:
        sim_session = _make_sim_session("created")
        mock_manager.create_session = AsyncMock(return_value="sess-1")
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()

    def test_create_session_success(
        self, client: TestClient, mock_manager: MagicMock, mock_redis: MagicMock
    ) -> None:
        self._setup_manager(mock_manager, mock_redis)
        resp = client.post(
            "/v1/sessions",
            json={"config_path": "config/default.yaml"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data

    def test_create_session_no_idempotency_key(
        self, client: TestClient, mock_manager: MagicMock, mock_redis: MagicMock
    ) -> None:
        """Create session without idempotency key (no caching attempted)."""
        self._setup_manager(mock_manager, mock_redis)
        resp = client.post(
            "/v1/sessions",
            json={"config_path": "config/default.yaml"},
        )
        assert resp.status_code == 201

    def test_create_session_with_idempotency_key_covers_cache_line(
        self, client: TestClient, mock_manager: MagicMock, mock_redis: MagicMock
    ) -> None:
        """Idempotency key with cached response (covers cache line)."""
        self._setup_manager(mock_manager, mock_redis)
        with patch(
            "app.routes.sessions.cache_idempotency_response", new_callable=AsyncMock
        ) as mock_cache:
            mock_cache.return_value = None
            resp = client.post(
                "/v1/sessions",
                json={"config_path": "config/default.yaml"},
                headers={"Idempotency-Key": "unique-key-abc"},
            )
        assert resp.status_code == 201

    def test_create_session_idempotency_cached(
        self, client: TestClient, mock_manager: MagicMock, mock_redis: MagicMock
    ) -> None:
        """When idempotency key has cached response, return it directly."""
        import json

        cached = {
            "session_id": "sess-cached",
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "config": {},
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(cached).encode())
        resp = client.post(
            "/v1/sessions",
            json={"config_path": "config/default.yaml"},
            headers={"Idempotency-Key": "existing-key"},
        )
        assert resp.status_code == 201
        assert resp.json()["session_id"] == "sess-cached"

    def test_create_session_idempotency_key_too_long(
        self, client: TestClient, mock_manager: MagicMock, mock_redis: MagicMock
    ) -> None:
        mock_redis.get = AsyncMock(return_value=None)
        resp = client.post(
            "/v1/sessions",
            json={"config_path": "config/default.yaml"},
            headers={"Idempotency-Key": "x" * 256},
        )
        assert resp.status_code == 400


class TestGetSessionRoute:
    def _setup_db(self, mock_db: MagicMock, user_id: str = "user-123") -> None:
        session_model = _make_session_model(user_id=user_id)
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

    def test_get_session_success(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        sim_session = _make_sim_session()
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        resp = client.get("/v1/sessions/sess-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-1"

    def test_get_session_not_found_in_db(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        resp = client.get("/v1/sessions/nonexistent")
        assert resp.status_code == 404

    def test_get_session_not_found_in_manager(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        mock_manager.get_session = AsyncMock(side_effect=ValueError("not found"))
        resp = client.get("/v1/sessions/sess-1")
        assert resp.status_code == 404

    def test_get_session_forbidden(self, client: TestClient, mock_db: MagicMock) -> None:
        """Non-admin user accessing another user's session."""
        from app.database.connection import get_db
        from app.main import create_app
        from app.routes.sessions import get_redis_client, get_session_manager
        from app.services.authorization import get_current_user

        other_user = TokenPayload(
            user_id="other-user",
            username="other",
            roles=["researcher"],
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            token_type="access",
            permissions=[],
        )
        mock_mgr = AsyncMock()
        mock_rd = AsyncMock()
        mock_db2 = MagicMock()
        session_model = _make_session_model(user_id="user-123")  # owned by user-123
        mock_db2.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        app = create_app(test_mode=True)
        app.router.lifespan_context = noop_lifespan
        app.dependency_overrides[get_db] = lambda: mock_db2
        app.dependency_overrides[get_current_user] = lambda: other_user
        app.dependency_overrides[get_session_manager] = lambda: mock_mgr
        app.dependency_overrides[get_redis_client] = lambda: mock_rd
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/v1/sessions/sess-1")
        assert resp.status_code == 403


class TestGetSessionMetricsRoute:
    def _setup_db(self, mock_db: MagicMock) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

    def test_get_metrics_success(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        sim_session = _make_sim_session()
        sim_session.get_state = AsyncMock(
            return_value={
                "allostatic": {"load": 1.0, "threshold": 0.5},
                "body": {"energy": 2.0, "arousal": 0.3},
                "ignition": {"intensity": 0.8, "active": True},
            }
        )
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        resp = client.get("/v1/sessions/sess-1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "ignition_frequency" in data
        assert "free_energy" in data

    def test_get_metrics_session_not_found_in_db(
        self, client: TestClient, mock_db: MagicMock
    ) -> None:
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        resp = client.get("/v1/sessions/nonexistent/metrics")
        assert resp.status_code == 404

    def test_get_metrics_session_not_found_in_manager(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        mock_manager.get_session = AsyncMock(side_effect=ValueError("not found"))
        resp = client.get("/v1/sessions/sess-1/metrics")
        assert resp.status_code == 404

    def test_get_metrics_empty_state(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        """Metrics with empty state dict uses defaults."""
        self._setup_db(mock_db)
        sim_session = _make_sim_session()
        sim_session.get_state = AsyncMock(return_value={})
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        resp = client.get("/v1/sessions/sess-1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ignition_frequency"] == 0.0
        assert data["free_energy"] == 0.0


class TestGetSessionTasksRoute:
    def _setup_db_with_tasks(self, mock_db: MagicMock, user_id: str = "user-123") -> None:
        from app.database.models import Task

        session_model = _make_session_model(user_id=user_id)
        task = MagicMock(spec=Task)
        task.task_id = "task-1"
        task.status = "SUCCESS"
        task.result_data = {"result": "ok"}
        task.error_message = None
        mock_db.query.side_effect = lambda model: (
            _make_query_chain(session_model)
            if model.__name__ == "Session"
            else _make_task_query_chain([task])
        )

    def test_get_tasks_success(self, client: TestClient, mock_db: MagicMock) -> None:
        session_model = _make_session_model()
        task = MagicMock()
        task.task_id = "task-1"
        task.status = "SUCCESS"
        task.result_data = None
        task.error_message = None

        call_count = [0]

        def query_side_effect(model: type) -> MagicMock:
            q = MagicMock()
            if call_count[0] == 0:
                call_count[0] += 1
                q.filter.return_value.first.return_value = session_model
            else:
                q.filter.return_value.all.return_value = [task]
            return q

        mock_db.query.side_effect = query_side_effect
        resp = client.get("/v1/sessions/sess-1/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data

    def test_get_tasks_session_not_found(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.query.return_value.filter.return_value.first.return_value = None
        resp = client.get("/v1/sessions/nonexistent/tasks")
        assert resp.status_code == 404

    def test_get_tasks_forbidden(self, client: TestClient, mock_db: MagicMock) -> None:
        """Non-admin user accessing another user's session tasks."""
        from app.database.connection import get_db
        from app.main import create_app
        from app.routes.sessions import get_redis_client, get_session_manager
        from app.services.authorization import get_current_user

        other_user = TokenPayload(
            user_id="other-user",
            username="other",
            roles=["researcher"],
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            token_type="access",
            permissions=[],
        )
        mock_db2 = MagicMock()
        session_model = _make_session_model(user_id="user-123")  # owned by user-123
        mock_db2.query.return_value.filter.return_value.first.return_value = session_model

        app = create_app(test_mode=True)
        app.router.lifespan_context = noop_lifespan
        app.dependency_overrides[get_db] = lambda: mock_db2
        app.dependency_overrides[get_current_user] = lambda: other_user
        app.dependency_overrides[get_session_manager] = lambda: AsyncMock()
        app.dependency_overrides[get_redis_client] = lambda: AsyncMock()
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/v1/sessions/sess-1/tasks")
        assert resp.status_code == 403

    def test_get_tasks_with_error_message(self, client: TestClient, mock_db: MagicMock) -> None:
        """Tasks with error_message are returned correctly."""
        session_model = _make_session_model()
        task = MagicMock()
        task.task_id = "task-2"
        task.status = "FAILURE"
        task.result_data = None
        task.error_message = "Something went wrong"

        call_count = [0]

        def query_side_effect(model: type) -> MagicMock:
            q = MagicMock()
            if call_count[0] == 0:
                call_count[0] += 1
                q.filter.return_value.first.return_value = session_model
            else:
                q.filter.return_value.all.return_value = [task]
            return q

        mock_db.query.side_effect = query_side_effect
        resp = client.get("/v1/sessions/sess-1/tasks")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Action routes: start, pause, stop, reset, delete, step
# ---------------------------------------------------------------------------


class TestStartSessionRoute:
    def _setup(
        self, mock_db: MagicMock, mock_manager: MagicMock, state_val: str = "running"
    ) -> MagicMock:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session(state_val)
        sim_session.start = AsyncMock(return_value={"status": state_val})
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        mock_manager.update_session_state = AsyncMock()
        return sim_session

    def test_start_session_success(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup(mock_db, mock_manager)
        resp = client.post("/v1/sessions/sess-1/start")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "sess-1"

    def test_start_session_not_found_in_db(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        resp = client.post("/v1/sessions/nonexistent/start")
        assert resp.status_code == 404

    def test_start_session_not_found_in_manager(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        mock_manager.get_session = AsyncMock(side_effect=ValueError("not found"))
        resp = client.post("/v1/sessions/sess-1/start")
        assert resp.status_code == 404

    def test_start_session_state_conflict(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session("running")
        sim_session.start = AsyncMock(side_effect=ValueError("already running"))
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        resp = client.post("/v1/sessions/sess-1/start")
        assert resp.status_code == 409


class TestPauseSessionRoute:
    def _setup(self, mock_db: MagicMock, mock_manager: MagicMock) -> MagicMock:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session("paused")
        sim_session.pause = AsyncMock(return_value={"status": "paused"})
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        mock_manager.update_session_state = AsyncMock()
        return sim_session

    def test_pause_session_success(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup(mock_db, mock_manager)
        resp = client.post("/v1/sessions/sess-1/pause")
        assert resp.status_code == 200

    def test_pause_session_not_found_in_db(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        resp = client.post("/v1/sessions/nonexistent/pause")
        assert resp.status_code == 404

    def test_pause_session_not_found_in_manager(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        mock_manager.get_session = AsyncMock(side_effect=ValueError("not found"))
        resp = client.post("/v1/sessions/sess-1/pause")
        assert resp.status_code == 404

    def test_pause_session_state_conflict(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session("stopped")
        sim_session.pause = AsyncMock(side_effect=ValueError("cannot pause"))
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        resp = client.post("/v1/sessions/sess-1/pause")
        assert resp.status_code == 409


class TestStopSessionRoute:
    def _setup(self, mock_db: MagicMock, mock_manager: MagicMock) -> MagicMock:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session("stopped")
        sim_session.stop = AsyncMock(return_value={"status": "stopped"})
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        mock_manager.update_session_state = AsyncMock()
        return sim_session

    def test_stop_session_success(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup(mock_db, mock_manager)
        resp = client.post("/v1/sessions/sess-1/stop")
        assert resp.status_code == 200

    def test_stop_session_not_found_in_db(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        resp = client.post("/v1/sessions/nonexistent/stop")
        assert resp.status_code == 404

    def test_stop_session_not_found_in_manager(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        mock_manager.get_session = AsyncMock(side_effect=ValueError("not found"))
        resp = client.post("/v1/sessions/sess-1/stop")
        assert resp.status_code == 404

    def test_stop_session_state_conflict(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session("created")
        sim_session.stop = AsyncMock(side_effect=ValueError("cannot stop"))
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        resp = client.post("/v1/sessions/sess-1/stop")
        assert resp.status_code == 409


class TestResetSessionRoute:
    def _setup(self, mock_db: MagicMock, mock_manager: MagicMock) -> MagicMock:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session("created")
        sim_session.reset = AsyncMock(return_value={"status": "created"})
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        mock_manager.update_session_state = AsyncMock()
        return sim_session

    def test_reset_session_success(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup(mock_db, mock_manager)
        resp = client.post("/v1/sessions/sess-1/reset")
        assert resp.status_code == 200

    def test_reset_session_not_found_in_db(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        resp = client.post("/v1/sessions/nonexistent/reset")
        assert resp.status_code == 404

    def test_reset_session_not_found_in_manager(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        mock_manager.get_session = AsyncMock(side_effect=ValueError("not found"))
        resp = client.post("/v1/sessions/sess-1/reset")
        assert resp.status_code == 404

    def test_reset_session_state_conflict(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session("running")
        sim_session.reset = AsyncMock(side_effect=ValueError("cannot reset"))
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        resp = client.post("/v1/sessions/sess-1/reset")
        assert resp.status_code == 409


class TestDeleteSessionRoute:
    def _setup(self, mock_db: MagicMock, mock_manager: MagicMock) -> MagicMock:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session()
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        mock_manager.delete_session = AsyncMock()
        return sim_session

    def test_delete_session_success(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup(mock_db, mock_manager)
        resp = client.delete("/v1/sessions/sess-1")
        assert resp.status_code == 204

    def test_delete_session_not_found_in_db(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        resp = client.delete("/v1/sessions/nonexistent")
        assert resp.status_code == 404

    def test_delete_session_not_found_in_manager(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        mock_manager.get_session = AsyncMock(side_effect=ValueError("not found"))
        resp = client.delete("/v1/sessions/sess-1")
        assert resp.status_code == 404


class TestStepSessionRoute:
    def _setup(self, mock_db: MagicMock, mock_manager: MagicMock) -> MagicMock:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session("running")
        sim_session.step = AsyncMock(return_value={"allostatic": {}})
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        return sim_session

    def test_step_session_success(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup(mock_db, mock_manager)
        resp = client.post("/v1/sessions/sess-1/step")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stepped"

    def test_step_session_not_found_in_db(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        resp = client.post("/v1/sessions/nonexistent/step")
        assert resp.status_code == 404

    def test_step_session_not_found_in_manager(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        mock_manager.get_session = AsyncMock(side_effect=ValueError("not found"))
        resp = client.post("/v1/sessions/sess-1/step")
        assert resp.status_code == 404

    def test_step_session_invalid_state(
        self, client: TestClient, mock_manager: MagicMock, mock_db: MagicMock
    ) -> None:
        session_model = _make_session_model()
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )
        sim_session = _make_sim_session("paused")
        sim_session.step = AsyncMock(side_effect=ValueError("not running"))
        mock_manager.get_session = AsyncMock(return_value=sim_session)
        resp = client.post("/v1/sessions/sess-1/step")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Unit-level action tests (kept for completeness / direct function coverage)
# ---------------------------------------------------------------------------


class TestSessionRoutesGetSession:
    @pytest.fixture
    def mock_session_manager(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_current_user(self) -> MagicMock:
        user = MagicMock()
        user.user_id = "user123"
        user.roles = ["user"]
        return user

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        return MagicMock(spec=Session)

    @pytest.mark.asyncio
    async def test_get_session_success(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        session = Mock()
        session.session_id = "session123"
        session.state.value = "running"
        session.created_at = datetime.now(timezone.utc)
        session.updated_at = datetime.now(timezone.utc)
        session.config = {}
        session.description = "Test session"
        mock_session_manager.get_session = AsyncMock(return_value=session)

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
    async def test_get_session_not_found(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        """Session not found in manager after ownership check passes."""
        mock_session_manager.get_session = AsyncMock(side_effect=ValueError("Session not found"))

        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = "user123"
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

        from app.exceptions import SessionNotFoundError
        from app.routes.sessions import get_session

        with pytest.raises(SessionNotFoundError):
            await get_session("session123", mock_session_manager, mock_current_user, mock_db)


class TestSessionRoutesActions:
    @pytest.fixture
    def mock_session_manager(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_current_user(self) -> MagicMock:
        user = MagicMock()
        user.user_id = "user123"
        user.roles = ["user"]
        return user

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        return MagicMock(spec=Session)

    def _setup_db(self, mock_db: MagicMock, user_id: str = "user123") -> None:
        session_model = Mock(spec=SessionModel)
        session_model.session_id = "session123"
        session_model.user_id = user_id
        session_model.is_deleted = False
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            session_model
        )

    @pytest.mark.asyncio
    async def test_start_session_success(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = MagicMock()
        session.state = MagicMock()
        session.state.value = "running"
        session.updated_at = datetime.now(timezone.utc)
        mock_session_manager.get_session = AsyncMock(return_value=session)
        mock_session_manager.update_session_state = AsyncMock()
        session.start = AsyncMock(return_value={"status": "running"})

        from app.routes.sessions import start_session

        result = await start_session("session123", mock_session_manager, mock_current_user, mock_db)
        assert result is not None

    @pytest.mark.asyncio
    async def test_start_session_state_conflict(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = MagicMock()
        session.state = MagicMock()
        session.state.value = "running"
        session.updated_at = datetime.now(timezone.utc)
        mock_session_manager.get_session = AsyncMock(return_value=session)
        mock_session_manager.update_session_state = AsyncMock()
        session.start = AsyncMock(side_effect=ValueError("already running"))

        from app.exceptions import SessionStateConflictError
        from app.routes.sessions import start_session

        with pytest.raises(SessionStateConflictError):
            await start_session("session123", mock_session_manager, mock_current_user, mock_db)

    @pytest.mark.asyncio
    async def test_pause_session_success(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = MagicMock()
        session.state = MagicMock()
        session.state.value = "paused"
        session.updated_at = datetime.now(timezone.utc)
        mock_session_manager.get_session = AsyncMock(return_value=session)
        mock_session_manager.update_session_state = AsyncMock()
        session.pause = AsyncMock(return_value={"status": "paused"})

        from app.routes.sessions import pause_session

        result = await pause_session("session123", mock_session_manager, mock_current_user, mock_db)
        assert result is not None

    @pytest.mark.asyncio
    async def test_pause_session_state_conflict(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = MagicMock()
        session.state = MagicMock()
        session.state.value = "stopped"
        session.updated_at = datetime.now(timezone.utc)
        mock_session_manager.get_session = AsyncMock(return_value=session)
        mock_session_manager.update_session_state = AsyncMock()
        session.pause = AsyncMock(side_effect=ValueError("cannot pause"))

        from app.exceptions import SessionStateConflictError
        from app.routes.sessions import pause_session

        with pytest.raises(SessionStateConflictError):
            await pause_session("session123", mock_session_manager, mock_current_user, mock_db)

    @pytest.mark.asyncio
    async def test_stop_session_success(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = MagicMock()
        session.state = MagicMock()
        session.state.value = "stopped"
        session.updated_at = datetime.now(timezone.utc)
        mock_session_manager.get_session = AsyncMock(return_value=session)
        mock_session_manager.update_session_state = AsyncMock()
        session.stop = AsyncMock(return_value={"status": "stopped"})

        from app.routes.sessions import stop_session

        result = await stop_session("session123", mock_session_manager, mock_current_user, mock_db)
        assert result is not None

    @pytest.mark.asyncio
    async def test_stop_session_state_conflict(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = MagicMock()
        session.state = MagicMock()
        session.state.value = "created"
        session.updated_at = datetime.now(timezone.utc)
        mock_session_manager.get_session = AsyncMock(return_value=session)
        mock_session_manager.update_session_state = AsyncMock()
        session.stop = AsyncMock(side_effect=ValueError("cannot stop"))

        from app.exceptions import SessionStateConflictError
        from app.routes.sessions import stop_session

        with pytest.raises(SessionStateConflictError):
            await stop_session("session123", mock_session_manager, mock_current_user, mock_db)

    @pytest.mark.asyncio
    async def test_reset_session_success(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = MagicMock()
        session.state = MagicMock()
        session.state.value = "created"
        session.updated_at = datetime.now(timezone.utc)
        mock_session_manager.get_session = AsyncMock(return_value=session)
        mock_session_manager.update_session_state = AsyncMock()
        session.reset = AsyncMock(return_value={"status": "created"})

        from app.routes.sessions import reset_session

        result = await reset_session("session123", mock_session_manager, mock_current_user, mock_db)
        assert result is not None

    @pytest.mark.asyncio
    async def test_reset_session_state_conflict(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = AsyncMock()
        session.state.value = "running"
        session.updated_at = datetime.now(timezone.utc)
        mock_session_manager.get_session = AsyncMock(return_value=session)
        mock_session_manager.update_session_state = AsyncMock()
        session.reset = AsyncMock(side_effect=ValueError("cannot reset"))

        from app.exceptions import SessionStateConflictError
        from app.routes.sessions import reset_session

        with pytest.raises(SessionStateConflictError):
            await reset_session("session123", mock_session_manager, mock_current_user, mock_db)

    @pytest.mark.asyncio
    async def test_step_session_success(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = AsyncMock()
        session.state.value = "running"
        session.updated_at = datetime.now(timezone.utc)
        session.step = AsyncMock(return_value={"allostatic": {}})
        mock_session_manager.get_session = AsyncMock(return_value=session)

        from app.routes.sessions import step_session

        result = await step_session(
            "session123", None, mock_session_manager, mock_current_user, mock_db
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_step_session_invalid_state(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = AsyncMock()
        session.state.value = "paused"
        session.updated_at = datetime.now(timezone.utc)
        session.step = AsyncMock(side_effect=ValueError("not running"))
        mock_session_manager.get_session = AsyncMock(return_value=session)

        from app.routes.sessions import step_session

        with pytest.raises(HTTPException) as exc_info:
            await step_session("session123", None, mock_session_manager, mock_current_user, mock_db)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_session_success(
        self, mock_session_manager: MagicMock, mock_current_user: MagicMock, mock_db: MagicMock
    ) -> None:
        self._setup_db(mock_db)
        session = AsyncMock()
        session.session_id = "session123"
        mock_session_manager.get_session = AsyncMock(return_value=session)
        mock_session_manager.delete_session = AsyncMock()

        from app.routes.sessions import delete_session

        result = await delete_session(
            "session123", mock_session_manager, mock_current_user, mock_db
        )  # type: ignore[func-returns-value]
        assert result is None
