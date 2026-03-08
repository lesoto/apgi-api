"""
Unit tests for session manager service.

Tests session lifecycle management, caching, and database persistence.
Validates Requirements 8.1, 8.2, 8.3.
"""

import pytest
import json
import time
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from app.services.session_manager import (
    SessionManager,
    SimulationSession,
    SessionLifecycleState,
    validate_session_id,
    ALLOWED_TRANSITIONS,
)

VALID_UUID = "12345678-1234-1234-1234-123456789abc"
TEMPLATE_UUID = "87654321-4321-4321-4321-cba987654321"


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    client = AsyncMock()
    client.get.return_value = None
    return client


@pytest.fixture
def mock_db_session_factory():
    """Create a mock database session factory."""
    return MagicMock()


@pytest.fixture
def session_manager(mock_redis, mock_db_session_factory):
    """Create a SessionManager instance."""
    return SessionManager(mock_redis, mock_db_session_factory)


@pytest.fixture
def mock_session_config():
    """Create a mock session configuration."""
    return {
        "config_path": "/path/to/config.yaml",
        "custom_config": {"param": "value"},
        "description": "Test session",
    }


class TestValidateSessionId:
    """Test session ID validation."""

    def test_validate_session_id_valid(self):
        """Test validation of valid UUID."""
        valid_uuid = VALID_UUID
        result = validate_session_id(valid_uuid)
        assert result == valid_uuid

    def test_validate_session_id_invalid_format(self):
        """Test validation rejects invalid UUID format."""
        with pytest.raises(ValueError, match="Invalid session ID format"):
            validate_session_id("invalid-uuid")

    def test_validate_session_id_empty(self):
        """Test validation rejects empty string."""
        with pytest.raises(ValueError, match="Session ID must be a non-empty string"):
            validate_session_id("")

    def test_validate_session_id_none(self):
        """Test validation rejects None."""
        with pytest.raises(ValueError, match="Session ID must be a non-empty string"):
            validate_session_id(None)  # type: ignore[arg-type]


class TestSimulationSession:
    """Test simulation session functionality."""

    @pytest.fixture(autouse=True)
    def mock_apgi_system(self):
        """Mock APGISystem for all SimulationSession tests."""
        with patch("app.services.session_manager.APGISystem") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            # Mock relevant sub-components
            mock_instance.allostasis = MagicMock()
            mock_instance.body = MagicMock()
            mock_instance.precision = MagicMock()
            mock_instance.workspace = MagicMock()
            mock_instance.self_model = MagicMock()
            mock_instance.ignition = MagicMock()
            yield mock_instance

    def test_simulation_session_initialization(self, mock_session_config):
        """Test session initialization."""
        session_id = VALID_UUID
        session = SimulationSession(session_id, mock_session_config)

        assert session.session_id == session_id
        assert session.config == mock_session_config
        assert session.state == SessionLifecycleState.CREATED
        assert session.is_running is False
        assert session.is_paused is False

    def test_can_transition_to_valid(self):
        """Test valid state transitions."""
        session = SimulationSession(VALID_UUID, {})
        session.state = SessionLifecycleState.CREATED

        assert session._can_transition_to(SessionLifecycleState.RUNNING) is True
        assert session._can_transition_to(SessionLifecycleState.STOPPED) is True

    def test_can_transition_to_invalid(self):
        """Test invalid state transitions."""
        session = SimulationSession(VALID_UUID, {})
        session.state = SessionLifecycleState.RUNNING

        assert session._can_transition_to(SessionLifecycleState.CREATED) is False

    @pytest.mark.asyncio
    async def test_start_from_created(self, mock_session_config):
        """Test starting session from created state."""
        session = SimulationSession(VALID_UUID, mock_session_config)
        session.apgi_system.reset = MagicMock()

        result = await session.start()

        assert session.state == SessionLifecycleState.RUNNING
        assert session.is_running
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_start_invalid_transition(self):
        """Test starting session from invalid state."""
        session = SimulationSession(VALID_UUID, {})
        session.state = SessionLifecycleState.STOPPED

        with pytest.raises(ValueError, match="Cannot start session in state stopped"):
            await session.start()

    @pytest.mark.asyncio
    async def test_pause_running_session(self):
        """Test pausing a running session."""
        session = SimulationSession(VALID_UUID, {})
        session.state = SessionLifecycleState.RUNNING
        session.is_running = True

        with patch.object(session, "_capture_state", return_value={"state": "captured"}):
            result = await session.pause()

            assert session.state == SessionLifecycleState.PAUSED
            assert not session.is_running
            assert session.is_paused
            assert result["status"] == "paused"

    @pytest.mark.asyncio
    async def test_stop_session(self):
        """Test stopping a session."""
        session = SimulationSession(VALID_UUID, {})
        session.state = SessionLifecycleState.RUNNING
        session.is_running = True

        result = await session.stop()

        assert session.state == SessionLifecycleState.STOPPED
        assert not session.is_running
        assert result["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_reset_session(self):
        """Test resetting a session."""
        session = SimulationSession(VALID_UUID, {})
        session.state = SessionLifecycleState.STOPPED
        session.apgi_system.reset = MagicMock()

        result = await session.reset()

        assert session.state == SessionLifecycleState.CREATED
        assert not session.is_running
        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_step_running_session(self):
        """Test executing step on running session."""
        session = SimulationSession(VALID_UUID, {})
        session.is_running = True

        mock_state = {"time": 1.0, "history": {"ignition_signals": []}}
        session.apgi_system.step.return_value = mock_state

        result = await session.step("input")

        assert "history" in result
        assert "ignition_signals" in result["history"]

    @pytest.mark.asyncio
    async def test_step_not_running(self):
        """Test stepping a non-running session."""
        session = SimulationSession(VALID_UUID, {})

        with pytest.raises(ValueError, match="is not running"):
            await session.step("input")

    @pytest.mark.asyncio
    async def test_get_state(self):
        """Test getting session state."""
        session = SimulationSession(VALID_UUID, {})

        mock_state = {"time": 0.0}
        session.apgi_system.get_state.return_value = mock_state

        result = await session.get_state()

        assert result["session_metadata"]["session_id"] == VALID_UUID
        assert result["session_metadata"]["state"] == "created"

    def test_capture_state(self):
        """Test capturing session state."""
        session = SimulationSession(VALID_UUID, {})

        mock_state = {"time": 0.0}
        session.apgi_system.get_state.return_value = mock_state
        session.apgi_system.allostasis.save_state.return_value = {}
        session.apgi_system.body.save_state.return_value = {}
        session.apgi_system.precision.save_state.return_value = {}
        session.apgi_system.workspace.save_state.return_value = {}
        session.apgi_system.self_model.save_state.return_value = {}
        session.apgi_system.ignition.save_state.return_value = {}

        result = session._capture_state()

        assert "allostasis" in result

    def test_restore_state(self):
        """Test restoring session state."""
        session = SimulationSession(VALID_UUID, {})

        state = {
            "time": 1.0,
            "history": {"events": []},
            "allostasis": {},
            "body": {},
            "precision": {},
            "workspace": {},
            "self_model": {},
            "ignition": {},
        }

        # Mock load_state methods
        session.apgi_system.allostasis.load_state = MagicMock()
        session.apgi_system.body.load_state = MagicMock()
        session.apgi_system.precision.load_state = MagicMock()
        session.apgi_system.workspace.load_state = MagicMock()
        session.apgi_system.self_model.load_state = MagicMock()
        session.apgi_system.ignition.load_state = MagicMock()

        session._restore_state(state)

        # Check that system attributes were set
        assert session.apgi_system.time == 1.0
        assert session.apgi_system.history == {"events": []}


class TestSessionManager:
    """Test session manager functionality."""

    @pytest.mark.asyncio
    async def test_create_session_basic(self, session_manager, mock_session_config):
        """Test creating a basic session."""
        from app.models.schemas import SessionCreateRequest

        request = SessionCreateRequest(
            config_path="/path/to/config.yaml",
            description="Test session",
            custom_config={"param": "value"},
            template_id=None,
        )

        mock_db_session = MagicMock()
        session_manager.db_session_factory.return_value = mock_db_session

        with patch("app.services.session_manager.SimulationSession") as mock_sim_class:
            with patch("app.services.session_manager.SessionModel") as mock_session_model:
                mock_sim_instance = MagicMock()
                mock_sim_instance.state = SessionLifecycleState.CREATED
                mock_sim_instance.config = mock_session_config
                mock_sim_instance.get_state = AsyncMock(return_value={"allostasis": {}})
                mock_sim_instance.created_at = datetime.now(timezone.utc)
                mock_sim_instance.updated_at = datetime.now(timezone.utc)

                mock_sim_class.return_value = mock_sim_instance
                mock_model_instance = MagicMock()
                mock_session_model.return_value = mock_model_instance

                session_id = await session_manager.create_session(request, "user_123")

                assert isinstance(session_id, str)
                mock_db_session.add.assert_called_once()
                mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_with_template(self, session_manager):
        """Test creating session with template."""
        from app.models.schemas import SessionCreateRequest

        request = SessionCreateRequest(
            template_id=TEMPLATE_UUID,
            custom_config={"param": "override"},
        )

        mock_db_session = MagicMock()
        session_manager.db_session_factory.return_value = mock_db_session

        mock_template = MagicMock()
        mock_template.template_id = TEMPLATE_UUID
        mock_template.is_public = True
        mock_template.config_path = "/path/to/config.yaml"
        mock_template.custom_config = {"param": "value"}

        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_template

        with patch("app.services.session_manager.SimulationSession") as mock_sim_class:
            with patch("app.services.session_manager.SessionModel") as mock_session_model:
                mock_sim_instance = MagicMock()
                mock_sim_instance.state = SessionLifecycleState.CREATED
                mock_sim_instance.config = {"config_path": "/path/to/config.yaml"}
                mock_sim_instance.get_state = AsyncMock(return_value={})
                mock_sim_instance.created_at = datetime.now(timezone.utc)
                mock_sim_instance.updated_at = datetime.now(timezone.utc)

                mock_sim_class.return_value = mock_sim_instance
                mock_session_model.return_value = MagicMock()

                session_id = await session_manager.create_session(request, "user_123")

                assert isinstance(session_id, str)

    @pytest.mark.asyncio
    async def test_get_session_from_cache(self, session_manager):
        """Test getting session from memory cache."""
        session_id = VALID_UUID
        mock_sim_session = MagicMock()
        # Use current time to avoid expiration
        session_manager.sessions[session_id] = (mock_sim_session, time.time())

        result = await session_manager.get_session(session_id)

        assert result == mock_sim_session

    @pytest.mark.asyncio
    async def test_get_session_from_redis(self, session_manager, mock_session_config):
        """Test getting session from Redis cache."""
        session_id = VALID_UUID

        metadata = {
            "session_id": session_id,
            "user_id": "user_123",
            "state": "running",
            "config": mock_session_config,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        }

        session_manager.redis.get.return_value = json.dumps(metadata).encode()

        with patch("app.services.session_manager.SimulationSession") as mock_sim_class:
            with patch("app.services.session_manager.APGISystem"):
                mock_sim_instance = MagicMock()
                mock_sim_instance.session_id = session_id
                mock_sim_instance.state = SessionLifecycleState.RUNNING
                mock_sim_instance.config = mock_session_config
                mock_sim_instance.created_at = datetime.fromisoformat("2023-01-01T00:00:00+00:00")
                mock_sim_instance.updated_at = datetime.fromisoformat("2023-01-01T00:00:00+00:00")
                mock_sim_class.return_value = mock_sim_instance

                result = await session_manager.get_session(session_id)

                assert result.session_id == session_id
                assert result.state == SessionLifecycleState.RUNNING

    @pytest.mark.asyncio
    async def test_get_session_from_database(self, session_manager, mock_session_config):
        """Test getting session from database."""
        session_id = VALID_UUID

        session_manager.redis.get.return_value = None

        mock_db_session = MagicMock()
        session_manager.db_session_factory.return_value = mock_db_session

        mock_db_model = MagicMock()
        mock_db_model.session_id = session_id
        mock_db_model.config = mock_session_config
        mock_db_model.state = "created"
        mock_db_model.created_at = datetime.now(timezone.utc)
        mock_db_model.updated_at = datetime.now(timezone.utc)
        mock_db_model.full_state = {"param": "value"}
        mock_db_model.user_id = "user_123"

        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_db_model

        with patch("app.services.session_manager.SimulationSession") as mock_sim_class:
            with patch("app.services.session_manager.APGISystem"):
                mock_sim_instance = MagicMock()
                mock_sim_instance.session_id = session_id
                mock_sim_instance.state = SessionLifecycleState.CREATED
                mock_sim_instance.config = mock_session_config
                mock_sim_instance.get_state = AsyncMock(return_value={})
                mock_sim_instance.created_at = datetime.now(timezone.utc)
                mock_sim_instance.updated_at = datetime.now(timezone.utc)
                mock_sim_class.return_value = mock_sim_instance

                result = await session_manager.get_session(session_id)

                assert result.session_id == session_id
                assert result.state == SessionLifecycleState.CREATED

    def test_get_session_invalid_id(self, session_manager):
        """Test getting session with invalid ID."""
        with pytest.raises(ValueError, match="Invalid session ID format"):
            validate_session_id("invalid-id")

    @pytest.mark.asyncio
    async def test_delete_session(self, session_manager):
        """Test deleting a session."""
        session_id = VALID_UUID

        mock_db_session = MagicMock()
        session_manager.db_session_factory.return_value = mock_db_session

        mock_db_model = MagicMock()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_db_model

        await session_manager.delete_session(session_id)

        mock_db_model.is_deleted = True
        mock_db_session.commit.assert_called_once()
        session_manager.redis.delete.assert_called_once_with(f"session:{session_id}")

    @pytest.mark.asyncio
    async def test_update_session_state(self, session_manager):
        """Test updating session state."""
        session_id = VALID_UUID
        new_state = SessionLifecycleState.RUNNING

        mock_db_session = MagicMock()
        session_manager.db_session_factory.return_value = mock_db_session

        mock_db_model = MagicMock()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_db_model

        await session_manager.update_session_state(session_id, new_state)

        assert mock_db_model.state == "running"
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_sessions(self, session_manager):
        """Test listing sessions."""
        mock_db_session = MagicMock()
        session_manager.db_session_factory.return_value = mock_db_session

        mock_sessions = [MagicMock(), MagicMock()]
        mock_db_session.scalar.return_value = 2
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_sessions

        result = await session_manager.list_sessions(user_id="user_123", page=1, per_page=10)

        assert result["total"] == 2
        assert result["sessions"] == mock_sessions


class TestStateTransitions:
    """Test session state transition logic."""

    def test_allowed_transitions_created(self):
        """Test transitions from CREATED state."""
        assert SessionLifecycleState.RUNNING in ALLOWED_TRANSITIONS[SessionLifecycleState.CREATED]
        assert SessionLifecycleState.ERROR in ALLOWED_TRANSITIONS[SessionLifecycleState.CREATED]

    def test_allowed_transitions_running(self):
        """Test transitions from RUNNING state."""
        assert SessionLifecycleState.PAUSED in ALLOWED_TRANSITIONS[SessionLifecycleState.RUNNING]
        assert SessionLifecycleState.STOPPED in ALLOWED_TRANSITIONS[SessionLifecycleState.RUNNING]
        assert SessionLifecycleState.ERROR in ALLOWED_TRANSITIONS[SessionLifecycleState.RUNNING]

    def test_allowed_transitions_paused(self):
        """Test transitions from PAUSED state."""
        assert SessionLifecycleState.RUNNING in ALLOWED_TRANSITIONS[SessionLifecycleState.PAUSED]
        assert SessionLifecycleState.STOPPED in ALLOWED_TRANSITIONS[SessionLifecycleState.PAUSED]
        assert SessionLifecycleState.ERROR in ALLOWED_TRANSITIONS[SessionLifecycleState.PAUSED]

    def test_allowed_transitions_stopped(self):
        """Test transitions from STOPPED state."""
        assert SessionLifecycleState.CREATED in ALLOWED_TRANSITIONS[SessionLifecycleState.STOPPED]
        assert SessionLifecycleState.ERROR in ALLOWED_TRANSITIONS[SessionLifecycleState.STOPPED]

    def test_allowed_transitions_error(self):
        """Test transitions from ERROR state."""
        assert SessionLifecycleState.CREATED in ALLOWED_TRANSITIONS[SessionLifecycleState.ERROR]
