"""
Coverage tests for app/routes/sessions.py
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

import app.routes.sessions as sessions
from app.services.authorization import Permission, Role, TokenPayload


@pytest.fixture
def mock_manager():
    manager = MagicMock()
    # Mocking init_session_routes effect
    sessions._state.session_manager = manager
    return manager


@pytest.fixture
def mock_redis():
    redis_client = AsyncMock()
    sessions._state.redis_client = redis_client
    return redis_client


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_current_user():
    return TokenPayload(
        user_id="user-1",
        username="testuser",
        roles=[Role.RESEARCHER],
        permissions=[
            Permission.SESSION_READ,
            Permission.SESSION_CREATE,
            Permission.SESSION_CONTROL,
            Permission.SESSION_DELETE,
        ],
        exp=1234567890,
    )


@pytest.mark.asyncio
async def test_list_sessions_success(mock_manager, mock_current_user):
    """Test listing sessions successfully."""
    mock_manager.list_sessions.return_async_value = {
        "sessions": [
            MagicMock(
                session_id="s1",
                state="running",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                config={},
                description="desc",
            )
        ],
        "total": 1,
    }
    # Need to use patch to return the async value because list_sessions is async
    with patch.object(mock_manager, "list_sessions", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = {
            "sessions": [
                MagicMock(
                    session_id="s1",
                    state="running",
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    config={},
                    description="desc",
                )
            ],
            "total": 1,
        }
        response = await sessions.list_sessions(
            page=1, per_page=10, state=None, manager=mock_manager, current_user=mock_current_user
        )
        assert len(response.sessions) == 1
        assert response.pagination.total == 1


@pytest.mark.asyncio
async def test_list_sessions_invalid_params(mock_manager, mock_current_user):
    """Test listing sessions with invalid parameters."""
    with pytest.raises(HTTPException) as exc:
        await sessions.list_sessions(
            page=0, per_page=10, manager=mock_manager, current_user=mock_current_user
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_session_idempotency_hit(mock_redis, mock_current_user):
    """Test creating session with idempotency cache hit."""
    mock_redis.get.return_value = b'{"session_id": "s1", "status": "created", "created_at": "2026-01-01T00:00:00+00:00", "config": {}}'
    mock_req = MagicMock(spec=Request)
    mock_req.headers = {"Idempotency-Key": "key1"}

    response = await sessions.create_session(
        request=MagicMock(),
        req=mock_req,
        manager=MagicMock(),
        redis_client=mock_redis,
        current_user=mock_current_user,
    )
    assert response.session_id == "s1"
    assert mock_redis.get.called


@pytest.mark.asyncio
async def test_create_session_success(mock_redis, mock_manager, mock_current_user):
    """Test creating session successfully."""
    mock_redis.get.return_value = None
    mock_manager.create_session = AsyncMock(return_value="s1")
    mock_session = MagicMock()
    mock_session.state = MagicMock(value="created")
    mock_session.created_at = datetime.now(timezone.utc)
    mock_session.config = {}
    mock_manager.get_session = AsyncMock(return_value=mock_session)

    mock_req = MagicMock(spec=Request)
    mock_req.headers = {"Idempotency-Key": "key1"}

    with patch(
        "app.routes.sessions.cache_idempotency_response", new_callable=AsyncMock
    ) as mock_cache:
        response = await sessions.create_session(
            request=MagicMock(),
            req=mock_req,
            manager=mock_manager,
            redis_client=mock_redis,
            current_user=mock_current_user,
        )
        assert response.session_id == "s1"
        assert mock_cache.called


@pytest.mark.asyncio
async def test_validate_session_ownership_success(mock_db, mock_manager):
    """Test validating session ownership."""
    mock_session = MagicMock()
    mock_session.user_id = "user-1"

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_session)
        result = await sessions.validate_session_ownership("s1", "user-1", mock_manager, mock_db)
        assert result == mock_session


@pytest.mark.asyncio
async def test_validate_session_ownership_forbidden(mock_db, mock_manager):
    """Test validating session ownership forbidden."""
    mock_session = MagicMock()
    mock_session.user_id = "other-user"

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_session)
        with pytest.raises(HTTPException) as exc:
            await sessions.validate_session_ownership("s1", "user-1", mock_manager, mock_db)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_start_session_success(mock_manager, mock_current_user, mock_db):
    """Test starting a session."""
    mock_session = AsyncMock()
    mock_session.state = MagicMock(value="created")
    mock_session.updated_at = datetime.now()
    mock_session.start.return_value = {"status": "running"}
    mock_manager.get_session = AsyncMock(return_value=mock_session)
    mock_manager.update_session_state = AsyncMock()

    with patch("app.routes.sessions.validate_session_ownership", new_callable=AsyncMock):
        response = await sessions.start_session(
            "s1", manager=mock_manager, current_user=mock_current_user, db=mock_db
        )
        assert response.status == "running"
        assert mock_manager.update_session_state.called


@pytest.mark.asyncio
async def test_delete_session_success(mock_manager, mock_current_user, mock_db):
    """Test deleting a session."""
    mock_manager.get_session = AsyncMock()
    mock_manager.delete_session = AsyncMock()

    with patch("app.routes.sessions.validate_session_ownership", new_callable=AsyncMock):
        await sessions.delete_session(
            "s1", manager=mock_manager, current_user=mock_current_user, db=mock_db
        )
        assert mock_manager.delete_session.called


@pytest.mark.asyncio
async def test_get_session_metrics(mock_manager, mock_current_user, mock_db):
    """Test getting session metrics."""
    mock_session = AsyncMock()
    mock_session.get_state.return_value = {
        "allostatic": {"load": 0.5},
        "body": {"energy": 100},
        "ignition": {"intensity": 0.8},
    }
    mock_manager.get_session = AsyncMock(return_value=mock_session)

    with patch("app.routes.sessions.validate_session_ownership", new_callable=AsyncMock):
        response = await sessions.get_session_metrics(
            "s1", manager=mock_manager, current_user=mock_current_user, db=mock_db
        )
        assert response.ignition_frequency == 0.8
        assert response.free_energy == 0.5


@pytest.mark.asyncio
async def test_get_session_tasks_success(mock_db, mock_current_user):
    """Test getting session tasks."""
    mock_task = MagicMock()
    mock_task.task_id = "t1"
    mock_task.status = "completed"
    mock_task.result_data = {"res": "ok"}
    mock_task.error_message = None

    with patch("asyncio.get_running_loop") as mock_loop:
        # Mocking the _blocking_get_tasks inner result
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=[mock_task])
        response = await sessions.get_session_tasks(
            "s1", db=mock_db, current_user=mock_current_user
        )
        assert len(response.tasks) == 1
        assert response.tasks[0].task_id == "t1"


@pytest.mark.asyncio
async def test_step_session_success(mock_manager, mock_current_user, mock_db):
    """Test stepping a session."""
    mock_session = AsyncMock()
    mock_session.updated_at = datetime.now()
    mock_session.step.return_value = {"new": "state"}
    mock_manager.get_session = AsyncMock(return_value=mock_session)

    with patch("app.routes.sessions.validate_session_ownership", new_callable=AsyncMock):
        response = await sessions.step_session(
            "s1",
            extero_input={"key": "val"},
            manager=mock_manager,
            current_user=mock_current_user,
            db=mock_db,
        )
        assert response.status == "stepped"
        mock_session.step.assert_called_with({"key": "val"})


def test_init_session_routes():
    """Test init_session_routes."""
    mock_redis_inst = MagicMock()
    with patch("app.routes.sessions.SessionManager") as mock_sm:
        sessions.init_session_routes(mock_redis_inst)
        assert sessions._state.redis_client == mock_redis_inst
        assert mock_sm.called


def test_get_dependencies_fail():
    """Test dependency getters failing when not initialized."""
    sessions._state.redis_client = None
    sessions._state.session_manager = None
    with pytest.raises(Exception):  # ServiceUnavailableError
        sessions.get_redis_client()
    with pytest.raises(Exception):
        sessions.get_session_manager()
