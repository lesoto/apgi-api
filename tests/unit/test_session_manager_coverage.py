"""
Coverage tests for app/services/session_manager.py
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import SessionCreateRequest
from app.services.session_manager import (
    SessionLifecycleState,
    SessionManager,
    SimulationSession,
    validate_session_id,
)


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def mock_db_factory():
    factory = MagicMock()
    session = MagicMock()
    factory.return_value = session
    return factory


@pytest.fixture
def session_manager(mock_redis, mock_db_factory):
    return SessionManager(redis_client=mock_redis, db_session_factory=mock_db_factory)


def test_validate_session_id_invalid():
    """Test validate_session_id with invalid inputs."""
    with pytest.raises(ValueError, match="non-empty string"):
        validate_session_id(None)
    with pytest.raises(ValueError, match="Invalid session ID format"):
        validate_session_id("invalid-uuid")


@pytest.mark.asyncio
async def test_simulation_session_lifecycle():
    """Test SimulationSession state transitions."""
    with patch("app.services.session_manager.APGISystem") as mock_apgi:
        session_id = "550e8400-e29b-41d4-a716-446655440000"
        sim_session = SimulationSession(session_id, {"config_path": "path"})

        # Start
        await sim_session.start()
        assert sim_session.state == SessionLifecycleState.RUNNING

        # Pause
        mock_apgi.return_value.get_state.return_value = {"time": 1.0}
        await sim_session.pause()
        assert sim_session.state == SessionLifecycleState.PAUSED

        # Resume
        await sim_session.start()
        assert sim_session.state == SessionLifecycleState.RUNNING

        # Step
        await sim_session.step({"input": 1})
        assert mock_apgi.return_value.step.called

        # Stop
        await sim_session.stop()
        assert sim_session.state == SessionLifecycleState.STOPPED

        # Reset
        await sim_session.reset()
        assert sim_session.state == SessionLifecycleState.CREATED


@pytest.mark.asyncio
async def test_session_manager_create_session_limit(session_manager, mock_db_factory):
    """Test SessionManager session limit enforcement."""
    mock_db = mock_db_factory.return_value
    mock_db.scalar.return_value = 100  # Current count

    with patch("app.services.session_manager.settings") as mock_settings:
        mock_settings.max_sessions_per_user = 10  # Limit
        with pytest.raises(ValueError, match="has reached the maximum number of sessions"):
            await session_manager.create_session(
                SessionCreateRequest(description="test", config_path="config.yaml"), user_id="user1"
            )


@pytest.mark.asyncio
async def test_session_manager_get_session_cache_hit(session_manager, mock_redis):
    """Test session manager memory cache hit."""
    session_id = "550e8400-e29b-41d4-a716-446655440000"
    mock_session = MagicMock(spec=SimulationSession)
    mock_session.session_id = session_id
    import time

    session_manager.sessions[session_id] = (mock_session, time.time())
    # Mock Redis to return None so it uses memory cache
    mock_redis.get.return_value = None

    result = await session_manager.get_session(session_id)
    assert result == mock_session


@pytest.mark.asyncio
async def test_session_manager_get_session_redis_hit(session_manager, mock_redis):
    """Test session manager Redis cache hit."""
    session_id = "550e8400-e29b-41d4-a716-446655440000"
    metadata = {
        "user_id": "user1",
        "config": {"config_path": "path"},
        "state": "created",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    mock_redis.get.return_value = bytes(json.dumps(metadata), "utf-8")

    with patch("app.services.session_manager.SimulationSession"):
        result = await session_manager.get_session(session_id, user_id="user1")
        assert result is not None


@pytest.mark.asyncio
async def test_session_manager_delete_session(session_manager, mock_db_factory):
    """Test session manager delete session."""
    session_id = "550e8400-e29b-41d4-a716-446655440000"
    mock_db = mock_db_factory.return_value
    mock_model = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = mock_model

    await session_manager.delete_session(session_id)
    assert mock_model.is_deleted is True
    assert mock_db.commit.called
