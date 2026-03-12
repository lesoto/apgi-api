"""
Unit tests for session lifecycle management.

Tests session creation, state transitions, invalid transition rejection,
session deletion, and session expiration.
Validates Requirements 18.3, 18.4, 18.5, 18.6, 18.7.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import uuid

from app.services.session_manager import (
    SessionManager,
    SimulationSession,
    SessionLifecycleState,
)
from app.models.schemas import SessionCreateRequest
from app.database.models import SessionState


@pytest.fixture
def mock_redis():
    """Create a mock async Redis client."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock()
    redis_mock.delete = AsyncMock()
    return redis_mock


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    db_mock = MagicMock()
    db_mock.add = MagicMock()
    db_mock.commit = MagicMock()
    db_mock.rollback = MagicMock()
    db_mock.close = MagicMock()
    db_mock.execute = MagicMock()
    db_mock.delete = MagicMock()
    # Mock scalar to return integer for count queries
    db_mock.scalar.return_value = 0
    return db_mock


@pytest.fixture
def mock_db_session_factory(mock_db_session):
    """Create a mock database session factory."""
    return lambda: mock_db_session


@pytest.fixture
def session_manager(mock_redis, mock_db_session_factory):
    """Create a SessionManager instance with mocked dependencies."""
    return SessionManager(mock_redis, mock_db_session_factory)


@pytest.fixture
def sample_config():
    """Create a sample session configuration."""
    return {
        "config_path": "configs/default.yaml",
        "custom_config": {"workspace": {"size": 10}},
        "description": "Test session",
    }


@pytest.fixture
def mock_apgi_system():
    """Create a mock APGI system."""
    with patch("app.services.session_manager.APGISystem") as mock:
        mock_instance = MagicMock()
        mock_instance.config = {}
        mock_instance.reset = MagicMock()
        mock_instance.step = MagicMock(return_value={})
        mock_instance.get_state = MagicMock(return_value={"time": 0.0, "history": {}})
        mock_instance._initialize_subsystems = MagicMock()
        mock.return_value = mock_instance
        yield mock


class TestSessionCreation:
    """Test session creation functionality."""

    @pytest.mark.asyncio
    async def test_create_session_returns_valid_session_id(
        self, session_manager, sample_config, mock_apgi_system
    ):
        """Test that create_session returns a valid UUID session ID."""
        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)

        # Verify session ID is a valid UUID
        assert isinstance(session_id, str)
        assert len(session_id) == 36  # UUID format: 8-4-4-4-12
        uuid.UUID(session_id)  # Should not raise ValueError

    @pytest.mark.asyncio
    async def test_create_session_initializes_in_created_state(
        self, session_manager, sample_config, mock_apgi_system
    ):
        """Test that newly created session is in CREATED state."""
        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)
        session = await session_manager.get_session(session_id)

        assert session.state == SessionLifecycleState.CREATED

    @pytest.mark.asyncio
    async def test_create_session_persists_to_database(
        self, session_manager, mock_db_session, sample_config, mock_apgi_system
    ):
        """Test that create_session persists session to database."""
        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        await session_manager.create_session(request)

        # Verify database operations were called
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_caches_in_redis(
        self, session_manager, mock_redis, sample_config, mock_apgi_system
    ):
        """Test that create_session caches session metadata in Redis."""
        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)

        # Verify Redis setex was called with session key
        mock_redis.setex.assert_called()
        call_args = mock_redis.setex.call_args
        assert f"session:{session_id}" in call_args[0]

    @pytest.mark.asyncio
    async def test_create_session_stores_configuration(
        self, session_manager, sample_config, mock_apgi_system
    ):
        """Test that create_session stores the provided configuration."""
        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)
        session = await session_manager.get_session(session_id)

        assert session.config["config_path"] == sample_config["config_path"]
        assert session.config["custom_config"] == sample_config["custom_config"]
        assert session.config["description"] == sample_config["description"]


class TestSessionStateTransitions:
    """Test valid session state transitions."""

    @pytest.mark.asyncio
    async def test_transition_created_to_running(self, sample_config, mock_apgi_system):
        """Test transition from CREATED to RUNNING state."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        assert session.state == SessionLifecycleState.CREATED

        result = await session.start()

        assert session.state == SessionLifecycleState.RUNNING  # type: ignore
        assert result["status"] == SessionLifecycleState.RUNNING.value
        assert result["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_transition_running_to_paused(self, sample_config, mock_apgi_system):
        """Test transition from RUNNING to PAUSED state."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        # Start session first
        await session.start()
        assert session.state == SessionLifecycleState.RUNNING

        # Pause session
        result = await session.pause()

        assert session.state == SessionLifecycleState.PAUSED  # type: ignore
        assert result["status"] == SessionLifecycleState.PAUSED.value
        assert result["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_transition_paused_to_running(self, sample_config, mock_apgi_system):
        """Test transition from PAUSED to RUNNING state (resume)."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        # Start, then pause
        await session.start()
        await session.pause()
        assert session.state == SessionLifecycleState.PAUSED

        # Resume (start again)
        result = await session.start()

        assert session.state == SessionLifecycleState.RUNNING  # type: ignore
        assert result["status"] == SessionLifecycleState.RUNNING.value

    @pytest.mark.asyncio
    async def test_transition_running_to_stopped(self, sample_config, mock_apgi_system):
        """Test transition from RUNNING to STOPPED state."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        # Start session first
        await session.start()
        assert session.state == SessionLifecycleState.RUNNING

        # Stop session
        result = await session.stop()

        assert session.state == SessionLifecycleState.STOPPED  # type: ignore
        assert result["status"] == SessionLifecycleState.STOPPED.value
        assert result["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_transition_paused_to_stopped(self, sample_config, mock_apgi_system):
        """Test transition from PAUSED to STOPPED state."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        # Start, then pause
        await session.start()
        await session.pause()
        assert session.state == SessionLifecycleState.PAUSED

        # Stop session
        result = await session.stop()

        assert session.state == SessionLifecycleState.STOPPED  # type: ignore
        assert result["status"] == SessionLifecycleState.STOPPED.value

    @pytest.mark.asyncio
    async def test_transition_stopped_to_created_via_reset(self, sample_config, mock_apgi_system):
        """Test transition from STOPPED to CREATED state via reset."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        # Start and stop session
        await session.start()
        await session.stop()
        assert session.state == SessionLifecycleState.STOPPED

        # Reset session
        result = await session.reset()

        assert session.state == SessionLifecycleState.CREATED  # type: ignore
        assert result["status"] == SessionLifecycleState.CREATED.value
        assert result["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_transition_created_to_stopped(self, sample_config, mock_apgi_system):
        """Test transition from CREATED to STOPPED state (direct stop)."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        assert session.state == SessionLifecycleState.CREATED

        # Stop session without starting
        result = await session.stop()

        assert session.state == SessionLifecycleState.STOPPED  # type: ignore
        assert result["status"] == SessionLifecycleState.STOPPED.value


class TestInvalidStateTransitions:
    """Test invalid state transition rejection."""

    @pytest.mark.asyncio
    async def test_cannot_pause_created_session(self, sample_config, mock_apgi_system):
        """Test that pausing a CREATED session raises error."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        assert session.state == SessionLifecycleState.CREATED

        with pytest.raises(ValueError) as exc_info:
            await session.pause()

        assert "cannot pause session in state created" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cannot_pause_stopped_session(self, sample_config, mock_apgi_system):
        """Test that pausing a STOPPED session raises error."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        # Start and stop session
        await session.start()
        await session.stop()
        assert session.state == SessionLifecycleState.STOPPED

        with pytest.raises(ValueError) as exc_info:
            await session.pause()

        assert "cannot pause session in state stopped" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cannot_pause_paused_session(self, sample_config, mock_apgi_system):
        """Test that pausing a PAUSED session raises error."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        # Start and pause
        await session.start()
        await session.pause()
        assert session.state == SessionLifecycleState.PAUSED

        with pytest.raises(ValueError) as exc_info:
            await session.pause()

        assert "cannot pause session in state paused" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cannot_start_running_session(self, sample_config, mock_apgi_system):
        """Test that starting a RUNNING session raises error."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        # Start session
        await session.start()
        assert session.state == SessionLifecycleState.RUNNING

        with pytest.raises(ValueError) as exc_info:
            await session.start()

        assert "cannot start session in state running" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_state_remains_unchanged_after_invalid_transition(
        self, sample_config, mock_apgi_system
    ):
        """Test that state remains unchanged after invalid transition attempt."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        original_state = session.state

        # Try invalid transition
        try:
            await session.pause()
        except ValueError:
            pass

        # State should remain unchanged
        assert session.state == original_state


class TestSessionDeletion:
    """Test session deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_session_removes_from_cache(
        self, session_manager, mock_redis, sample_config, mock_apgi_system
    ):
        """Test that delete_session removes session from memory cache."""
        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)

        # Verify session exists in cache
        assert session_id in session_manager.sessions

        # Delete session
        await session_manager.delete_session(session_id)

        # Verify session removed from cache
        assert session_id not in session_manager.sessions

    @pytest.mark.asyncio
    async def test_delete_session_removes_from_redis(
        self, session_manager, mock_redis, sample_config, mock_apgi_system
    ):
        """Test that delete_session removes session from Redis."""
        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)

        # Delete session
        await session_manager.delete_session(session_id)

        # Verify Redis delete was called
        mock_redis.delete.assert_called()
        call_args = mock_redis.delete.call_args
        assert f"session:{session_id}" in call_args[0]

    @pytest.mark.asyncio
    async def test_delete_session_removes_from_database(
        self, session_manager, mock_db_session, sample_config, mock_apgi_system
    ):
        """Test that delete_session removes session from database."""
        # Mock database query result
        mock_result = MagicMock()
        mock_db_model = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_db_model
        mock_db_session.execute.return_value = mock_result

        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)

        # Delete session
        await session_manager.delete_session(session_id)

        # Verify database soft delete was performed
        assert mock_db_model.is_deleted
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session_does_not_raise_error(
        self, session_manager, mock_db_session
    ):
        """Test that deleting a non-existent session does not raise error."""
        # Mock database query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        fake_session_id = str(uuid.uuid4())

        # Should not raise error
        await session_manager.delete_session(fake_session_id)

    @pytest.mark.asyncio
    async def test_delete_session_with_invalid_id_raises_error(self, session_manager):
        """Test that deleting session with invalid ID raises ValueError."""
        invalid_ids = [
            "not-a-uuid",
            "12345",
            "abc-def-ghi",
        ]

        for invalid_id in invalid_ids:
            with pytest.raises(ValueError) as exc_info:
                await session_manager.delete_session(invalid_id)

            # Check that error message mentions the problem
            error_msg = str(exc_info.value).lower()
            assert "invalid" in error_msg or "session id" in error_msg

        # Test empty string separately
        with pytest.raises(ValueError) as exc_info:
            await session_manager.delete_session("")

        error_msg = str(exc_info.value).lower()
        assert "non-empty" in error_msg or "session id" in error_msg


class TestSessionExpiration:
    """Test session expiration functionality."""

    @pytest.mark.asyncio
    async def test_expired_sessions_removed_from_cache(
        self, session_manager, sample_config, mock_apgi_system
    ):
        """Test that expired sessions are removed from memory cache."""
        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)

        # Manually set last access time to expired
        import time

        expired_time = time.time() - (session_manager.session_ttl_seconds + 100)
        session_data, _ = session_manager.sessions[session_id]
        session_manager.sessions[session_id] = (session_data, expired_time)

        # Trigger cleanup
        async with session_manager.cache_lock:
            session_manager._cleanup_expired_sessions()

        # Verify session was removed
        assert session_id not in session_manager.sessions

    @pytest.mark.asyncio
    async def test_active_sessions_not_removed_from_cache(
        self, session_manager, sample_config, mock_apgi_system
    ):
        """Test that active sessions are not removed during cleanup."""
        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)

        # Trigger cleanup
        async with session_manager.cache_lock:
            session_manager._cleanup_expired_sessions()

        # Verify session still exists
        assert session_id in session_manager.sessions

    @pytest.mark.asyncio
    async def test_cache_size_limit_enforced(
        self, session_manager, sample_config, mock_apgi_system
    ):
        """Test that cache size limit is enforced by evicting oldest sessions."""
        # Set a small cache size for testing
        session_manager.session_cache_max_size = 3

        # Create more sessions than the limit
        session_ids = []
        for i in range(5):
            request = SessionCreateRequest(
                config_path=sample_config["config_path"],
                custom_config=sample_config["custom_config"],
                template_id=None,
                description=f"Test session {i}",
            )
            session_id = await session_manager.create_session(request)
            session_ids.append(session_id)

        # Verify cache size is at limit
        assert len(session_manager.sessions) <= session_manager.session_cache_max_size

        # Verify oldest sessions were evicted
        assert session_ids[0] not in session_manager.sessions
        assert session_ids[1] not in session_manager.sessions

        # Verify newest sessions are still in cache
        assert session_ids[-1] in session_manager.sessions

    @pytest.mark.asyncio
    async def test_accessing_session_updates_expiration(
        self, session_manager, sample_config, mock_apgi_system
    ):
        """Test that accessing a session updates its expiration time."""
        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)

        # Get initial access time
        _, initial_time = session_manager.sessions[session_id]

        # Wait a bit
        await asyncio.sleep(0.1)

        # Access session
        await session_manager.get_session(session_id)

        # Get updated access time
        _, updated_time = session_manager.sessions[session_id]

        # Verify access time was updated
        assert updated_time > initial_time


class TestSessionStateConsistency:
    """Test session state consistency across operations."""

    @pytest.mark.asyncio
    async def test_session_state_persisted_after_transition(
        self, session_manager, mock_db_session, sample_config, mock_apgi_system
    ):
        """Test that session state is persisted to database after transition."""
        # Mock database query result
        mock_result = MagicMock()
        mock_db_model = MagicMock()
        mock_db_model.state = SessionState.CREATED.value
        mock_result.scalar_one_or_none.return_value = mock_db_model
        mock_db_session.execute.return_value = mock_result

        request = SessionCreateRequest(
            config_path=sample_config["config_path"],
            custom_config=sample_config["custom_config"],
            description=sample_config["description"],
            template_id=None,
        )

        session_id = await session_manager.create_session(request)

        # Update session state
        await session_manager.update_session_state(session_id, SessionLifecycleState.RUNNING)

        # Verify database commit was called
        assert mock_db_session.commit.call_count >= 2  # Once for create, once for update

    @pytest.mark.asyncio
    async def test_session_timestamps_updated_on_state_change(
        self, sample_config, mock_apgi_system
    ):
        """Test that session timestamps are updated on state changes."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        initial_updated_at = session.updated_at

        # Wait a bit
        await asyncio.sleep(0.1)

        # Change state
        await session.start()

        # Verify updated_at changed
        assert session.updated_at > initial_updated_at

    @pytest.mark.asyncio
    async def test_concurrent_access_uses_lock(self, sample_config, mock_apgi_system):
        """Test that concurrent access to session uses lock for thread safety."""
        session_id = str(uuid.uuid4())
        session = SimulationSession(session_id, sample_config)

        # Start session
        await session.start()

        # Create concurrent tasks
        async def access_session():
            async with session.lock:
                # Simulate some work
                await asyncio.sleep(0.01)
                return session.state

        # Run multiple concurrent accesses
        tasks = [access_session() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed and return consistent state
        assert all(state == SessionLifecycleState.RUNNING for state in results)
