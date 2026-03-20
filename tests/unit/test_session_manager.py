"""
Unit tests for SessionManager service.

Covers create_session, get_session, delete_session, update_session_state,
list_sessions, and SimulationSession lifecycle methods.
Uses MagicMock DB session and AsyncMock Redis client.
Validates Requirements 2.3.
"""

import json
import time
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.session_manager import (
    SessionManager,
    SimulationSession,
    SessionLifecycleState,
    ALLOWED_TRANSITIONS,
    validate_session_id,
)

VALID_UUID = "12345678-1234-1234-1234-123456789abc"
TEMPLATE_UUID = "87654321-4321-4321-4321-cba987654321"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.setex = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    return client


def _make_db_session(scalar_return=0, model_return=None):
    """Build a MagicMock DB session with sensible defaults."""
    db = MagicMock()
    db.scalar = MagicMock(return_value=scalar_return)
    result = MagicMock()
    result.scalar_one_or_none.return_value = model_return
    result.scalars.return_value.all.return_value = []
    db.execute = MagicMock(return_value=result)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.close = MagicMock()
    return db


@pytest.fixture
def mock_db():
    return _make_db_session()


@pytest.fixture
def session_manager(mock_redis, mock_db):
    return SessionManager(mock_redis, lambda: mock_db)


@pytest.fixture
def apgi_patch():
    """Patch APGISystem for all SimulationSession tests."""
    with patch("app.services.session_manager.APGISystem") as mock_cls:
        inst = MagicMock()
        inst.config = {}
        inst.reset = MagicMock()
        inst.step = MagicMock(return_value={"time": 0.0, "history": {}})
        inst.get_state = MagicMock(return_value={"time": 0.0})
        inst._initialize_subsystems = MagicMock()
        for sub in ("allostasis", "body", "precision", "workspace", "self_model", "ignition"):
            sub_mock = MagicMock()
            sub_mock.save_state = MagicMock(return_value={})
            sub_mock.load_state = MagicMock()
            setattr(inst, sub, sub_mock)
        mock_cls.return_value = inst
        yield inst


# ---------------------------------------------------------------------------
# validate_session_id
# ---------------------------------------------------------------------------


class TestValidateSessionId:
    def test_valid_uuid_passes(self):
        assert validate_session_id(VALID_UUID) == VALID_UUID

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid session ID format"):
            validate_session_id("not-a-uuid")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            validate_session_id("")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            validate_session_id(None)  # type: ignore[arg-type]

    def test_uppercase_uuid_passes(self):
        upper = VALID_UUID.upper()
        assert validate_session_id(upper) == upper


# ---------------------------------------------------------------------------
# SimulationSession
# ---------------------------------------------------------------------------


class TestSimulationSession:
    def test_initial_state_is_created(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {"config_path": "c.yaml"})
        assert s.state == SessionLifecycleState.CREATED
        assert s.is_running is False
        assert s.is_paused is False

    def test_can_transition_to_allowed(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        assert s._can_transition_to(SessionLifecycleState.RUNNING) is True

    def test_can_transition_to_disallowed(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        # CREATED → PAUSED is not allowed
        assert s._can_transition_to(SessionLifecycleState.PAUSED) is False

    @pytest.mark.asyncio
    async def test_start_from_created(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        result = await s.start()
        assert s.state == SessionLifecycleState.RUNNING
        assert s.is_running is True
        assert result["status"] == "running"
        assert result["session_id"] == VALID_UUID

    @pytest.mark.asyncio
    async def test_start_invalid_raises(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        s.state = SessionLifecycleState.STOPPED
        with pytest.raises(ValueError, match="Cannot start session in state stopped"):
            await s.start()

    @pytest.mark.asyncio
    async def test_pause_from_running(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        await s.start()
        result = await s.pause()
        assert s.state == SessionLifecycleState.PAUSED
        assert s.is_paused is True
        assert s.is_running is False
        assert result["status"] == "paused"

    @pytest.mark.asyncio
    async def test_pause_invalid_raises(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        with pytest.raises(ValueError, match="Cannot pause session in state created"):
            await s.pause()

    @pytest.mark.asyncio
    async def test_resume_from_paused(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        await s.start()
        await s.pause()
        result = await s.start()  # resume = start from paused
        assert s.state == SessionLifecycleState.RUNNING
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_stop_from_running(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        await s.start()
        result = await s.stop()
        assert s.state == SessionLifecycleState.STOPPED
        assert s.is_running is False
        assert result["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_stop_from_created(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        result = await s.stop()
        assert s.state == SessionLifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_invalid_raises(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        s.state = SessionLifecycleState.ERROR
        with pytest.raises(ValueError, match="Cannot stop session in state error"):
            await s.stop()

    @pytest.mark.asyncio
    async def test_reset_from_stopped(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        await s.start()
        await s.stop()
        result = await s.reset()
        assert s.state == SessionLifecycleState.CREATED
        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_reset_invalid_raises(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        # CREATED → CREATED is not in ALLOWED_TRANSITIONS[CREATED]
        s.state = SessionLifecycleState.RUNNING
        with pytest.raises(ValueError, match="Cannot reset session in state running"):
            await s.reset()

    @pytest.mark.asyncio
    async def test_step_running_session(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        s.is_running = True
        apgi_patch.step.return_value = {"time": 1.0, "history": {}}
        result = await s.step("input_data")
        assert "history" in result
        assert "ignition_signals" in result["history"]

    @pytest.mark.asyncio
    async def test_step_not_running_raises(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        with pytest.raises(ValueError, match="is not running"):
            await s.step("input")

    @pytest.mark.asyncio
    async def test_get_state_includes_metadata(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        apgi_patch.get_state.return_value = {"time": 0.0}
        result = await s.get_state()
        assert result["session_metadata"]["session_id"] == VALID_UUID
        assert result["session_metadata"]["state"] == "created"

    def test_capture_state(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        apgi_patch.get_state.return_value = {"time": 0.0}
        state = s._capture_state()
        assert "allostasis" in state
        assert "body" in state

    def test_restore_state(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        state = {
            "time": 5.0,
            "history": {"events": []},
            "allostasis": {},
            "body": {},
            "precision": {},
            "workspace": {},
            "self_model": {},
            "ignition": {},
        }
        s._restore_state(state)
        assert apgi_patch.time == 5.0

    def test_restore_empty_state_logs_warning(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        # Should not raise
        s._restore_state({})

    @pytest.mark.asyncio
    async def test_pause_captures_state(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        await s.start()
        apgi_patch.get_state.return_value = {"time": 1.0}
        await s.pause()
        assert s._paused_state is not None

    @pytest.mark.asyncio
    async def test_resume_restores_paused_state(self, apgi_patch):
        s = SimulationSession(VALID_UUID, {})
        await s.start()
        apgi_patch.get_state.return_value = {"time": 2.0}
        await s.pause()
        paused_state = s._paused_state
        await s.start()  # resume
        assert s._paused_state is None


# ---------------------------------------------------------------------------
# SessionManager.create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_create_session_returns_uuid(self, session_manager, mock_db, apgi_patch):
        from app.models.schemas import SessionCreateRequest

        req = SessionCreateRequest(
            config_path="configs/default.yaml", custom_config={}, template_id=None
        )
        session_id = await session_manager.create_session(req, "user1")
        assert len(session_id) == 36
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_caches_in_redis(
        self, session_manager, mock_redis, mock_db, apgi_patch
    ):
        from app.models.schemas import SessionCreateRequest

        req = SessionCreateRequest(
            config_path="configs/default.yaml", custom_config={}, template_id=None
        )
        session_id = await session_manager.create_session(req, "user1")
        mock_redis.setex.assert_awaited()
        call_key = mock_redis.setex.call_args[0][0]
        assert f"session:{session_id}" == call_key

    @pytest.mark.asyncio
    async def test_create_session_raises_when_max_sessions_reached(
        self, session_manager, mock_db, apgi_patch
    ):
        from app.models.schemas import SessionCreateRequest
        from app.config import settings

        mock_db.scalar.return_value = settings.max_sessions_per_user
        req = SessionCreateRequest(
            config_path="configs/default.yaml", custom_config={}, template_id=None
        )
        with pytest.raises(ValueError, match="maximum number of sessions"):
            await session_manager.create_session(req, "user1")

    @pytest.mark.asyncio
    async def test_create_session_raises_without_config(self, session_manager, mock_db, apgi_patch):
        from app.models.schemas import SessionCreateRequest
        from pydantic import ValidationError

        # The schema itself rejects all-None input
        with pytest.raises((ValidationError, ValueError)):
            req = SessionCreateRequest(config_path=None, custom_config=None, template_id=None)
            await session_manager.create_session(req, "user1")

    @pytest.mark.asyncio
    async def test_create_session_with_template(self, session_manager, mock_db, apgi_patch):
        from app.models.schemas import SessionCreateRequest

        template = MagicMock()
        template.template_id = TEMPLATE_UUID
        template.is_public = True
        template.config_path = "configs/template.yaml"
        template.custom_config = {}
        template.default_description = "tmpl desc"
        mock_db.execute.return_value.scalar_one_or_none.return_value = template

        req = SessionCreateRequest(template_id=TEMPLATE_UUID, config_path=None, custom_config=None)
        session_id = await session_manager.create_session(req, "user1")
        assert len(session_id) == 36

    @pytest.mark.asyncio
    async def test_create_session_template_not_found_raises(
        self, session_manager, mock_db, apgi_patch
    ):
        from app.models.schemas import SessionCreateRequest

        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        req = SessionCreateRequest(template_id=TEMPLATE_UUID, config_path=None, custom_config=None)
        with pytest.raises(ValueError, match="not found"):
            await session_manager.create_session(req, "user1")

    @pytest.mark.asyncio
    async def test_create_session_template_access_denied(
        self, session_manager, mock_db, apgi_patch
    ):
        from app.models.schemas import SessionCreateRequest

        template = MagicMock()
        template.template_id = TEMPLATE_UUID
        template.is_public = False
        template.user_id = "other_user"
        mock_db.execute.return_value.scalar_one_or_none.return_value = template
        req = SessionCreateRequest(template_id=TEMPLATE_UUID, config_path=None, custom_config=None)
        with pytest.raises(ValueError, match="not accessible"):
            await session_manager.create_session(req, "user1")

    @pytest.mark.asyncio
    async def test_create_session_db_error_rolls_back(self, session_manager, mock_db, apgi_patch):
        from app.models.schemas import SessionCreateRequest

        mock_db.commit.side_effect = Exception("DB error")
        req = SessionCreateRequest(
            config_path="configs/default.yaml", custom_config={}, template_id=None
        )
        with pytest.raises(Exception, match="DB error"):
            await session_manager.create_session(req, "user1")
        mock_db.rollback.assert_called()


# ---------------------------------------------------------------------------
# SessionManager.get_session
# ---------------------------------------------------------------------------


class TestGetSession:
    @pytest.mark.asyncio
    async def test_get_session_from_memory_cache(self, session_manager, apgi_patch):
        mock_sim = MagicMock()
        session_manager.sessions[VALID_UUID] = (mock_sim, time.time())
        result = await session_manager.get_session(VALID_UUID)
        assert result is mock_sim

    @pytest.mark.asyncio
    async def test_get_session_from_redis(self, session_manager, mock_redis, apgi_patch):
        metadata = {
            "session_id": VALID_UUID,
            "user_id": "u1",
            "state": "running",
            "config": {"config_path": "/c.yaml"},
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        }
        mock_redis.get.return_value = json.dumps(metadata).encode()
        result = await session_manager.get_session(VALID_UUID)
        assert result.state == SessionLifecycleState.RUNNING

    @pytest.mark.asyncio
    async def test_get_session_from_database(
        self, session_manager, mock_redis, mock_db, apgi_patch
    ):
        mock_redis.get.return_value = None
        db_model = MagicMock()
        db_model.session_id = VALID_UUID
        db_model.config = {"config_path": "/c.yaml"}
        db_model.state = "created"
        db_model.created_at = datetime.now(timezone.utc)
        db_model.updated_at = datetime.now(timezone.utc)
        db_model.full_state = None
        db_model.user_id = "u1"
        mock_db.execute.return_value.scalar_one_or_none.return_value = db_model
        result = await session_manager.get_session(VALID_UUID)
        assert result.state == SessionLifecycleState.CREATED

    @pytest.mark.asyncio
    async def test_get_session_not_found_raises(
        self, session_manager, mock_redis, mock_db, apgi_patch
    ):
        mock_redis.get.return_value = None
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await session_manager.get_session(VALID_UUID)

    @pytest.mark.asyncio
    async def test_get_session_invalid_id_raises(self, session_manager):
        with pytest.raises(ValueError, match="Invalid session ID format"):
            await session_manager.get_session("bad-id")

    @pytest.mark.asyncio
    async def test_get_session_restores_full_state(
        self, session_manager, mock_redis, mock_db, apgi_patch
    ):
        mock_redis.get.return_value = None
        db_model = MagicMock()
        db_model.session_id = VALID_UUID
        db_model.config = {"config_path": "/c.yaml"}
        db_model.state = "paused"
        db_model.created_at = datetime.now(timezone.utc)
        db_model.updated_at = datetime.now(timezone.utc)
        db_model.full_state = {"time": 3.0, "history": {}}
        db_model.user_id = "u1"
        mock_db.execute.return_value.scalar_one_or_none.return_value = db_model
        result = await session_manager.get_session(VALID_UUID)
        assert result is not None


# ---------------------------------------------------------------------------
# SessionManager.delete_session
# ---------------------------------------------------------------------------


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_delete_removes_from_memory_cache(self, session_manager, mock_db, apgi_patch):
        mock_sim = MagicMock()
        session_manager.sessions[VALID_UUID] = (mock_sim, time.time())
        mock_db.execute.return_value.scalar_one_or_none.return_value = MagicMock()
        await session_manager.delete_session(VALID_UUID)
        assert VALID_UUID not in session_manager.sessions

    @pytest.mark.asyncio
    async def test_delete_calls_redis_delete(
        self, session_manager, mock_redis, mock_db, apgi_patch
    ):
        mock_db.execute.return_value.scalar_one_or_none.return_value = MagicMock()
        await session_manager.delete_session(VALID_UUID)
        mock_redis.delete.assert_awaited_with(f"session:{VALID_UUID}")

    @pytest.mark.asyncio
    async def test_delete_soft_deletes_in_db(self, session_manager, mock_db, apgi_patch):
        db_model = MagicMock()
        db_model.is_deleted = False
        mock_db.execute.return_value.scalar_one_or_none.return_value = db_model
        await session_manager.delete_session(VALID_UUID)
        assert db_model.is_deleted is True
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_does_not_raise(self, session_manager, mock_db, apgi_patch):
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        await session_manager.delete_session(VALID_UUID)  # should not raise

    @pytest.mark.asyncio
    async def test_delete_invalid_id_raises(self, session_manager):
        with pytest.raises(ValueError, match="Invalid session ID format"):
            await session_manager.delete_session("not-a-uuid")


# ---------------------------------------------------------------------------
# SessionManager.update_session_state
# ---------------------------------------------------------------------------


class TestUpdateSessionState:
    @pytest.mark.asyncio
    async def test_update_state_commits_to_db(self, session_manager, mock_db, apgi_patch):
        db_model = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = db_model
        await session_manager.update_session_state(VALID_UUID, SessionLifecycleState.RUNNING)
        assert db_model.state == SessionLifecycleState.RUNNING.value
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_state_invalid_id_raises(self, session_manager):
        with pytest.raises(ValueError, match="Invalid session ID format"):
            await session_manager.update_session_state("bad", SessionLifecycleState.RUNNING)

    @pytest.mark.asyncio
    async def test_update_state_db_error_rolls_back(self, session_manager, mock_db, apgi_patch):
        mock_db.commit.side_effect = Exception("DB error")
        mock_db.execute.return_value.scalar_one_or_none.return_value = MagicMock()
        with pytest.raises(Exception, match="DB error"):
            await session_manager.update_session_state(VALID_UUID, SessionLifecycleState.RUNNING)
        mock_db.rollback.assert_called()


# ---------------------------------------------------------------------------
# SessionManager.list_sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    @pytest.mark.asyncio
    async def test_list_sessions_returns_dict(self, session_manager, mock_db, apgi_patch):
        mock_db.scalar.return_value = 2
        mock_db.execute.return_value.scalars.return_value.all.return_value = [
            MagicMock(),
            MagicMock(),
        ]
        result = await session_manager.list_sessions(user_id="u1", page=1, per_page=10)
        assert isinstance(result, dict)
        assert "sessions" in result
        assert "total" in result

    @pytest.mark.asyncio
    async def test_list_sessions_no_filter(self, session_manager, mock_db, apgi_patch):
        mock_db.scalar.return_value = 0
        result = await session_manager.list_sessions()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# SessionManager cache eviction
# ---------------------------------------------------------------------------


class TestCacheEviction:
    @pytest.mark.asyncio
    async def test_expired_sessions_cleaned_up(self, session_manager, apgi_patch):
        mock_sim = MagicMock()
        expired_time = time.time() - (session_manager.session_ttl_seconds + 100)
        session_manager.sessions[VALID_UUID] = (mock_sim, expired_time)
        async with session_manager.cache_lock:
            session_manager._cleanup_expired_sessions()
        assert VALID_UUID not in session_manager.sessions

    @pytest.mark.asyncio
    async def test_active_sessions_not_cleaned(self, session_manager, apgi_patch):
        mock_sim = MagicMock()
        session_manager.sessions[VALID_UUID] = (mock_sim, time.time())
        async with session_manager.cache_lock:
            session_manager._cleanup_expired_sessions()
        assert VALID_UUID in session_manager.sessions


# ---------------------------------------------------------------------------
# ALLOWED_TRANSITIONS table
# ---------------------------------------------------------------------------


class TestAllowedTransitions:
    def test_created_can_go_to_running(self):
        assert SessionLifecycleState.RUNNING in ALLOWED_TRANSITIONS[SessionLifecycleState.CREATED]

    def test_created_can_go_to_stopped(self):
        assert SessionLifecycleState.STOPPED in ALLOWED_TRANSITIONS[SessionLifecycleState.CREATED]

    def test_running_can_go_to_paused(self):
        assert SessionLifecycleState.PAUSED in ALLOWED_TRANSITIONS[SessionLifecycleState.RUNNING]

    def test_running_can_go_to_stopped(self):
        assert SessionLifecycleState.STOPPED in ALLOWED_TRANSITIONS[SessionLifecycleState.RUNNING]

    def test_paused_can_go_to_running(self):
        assert SessionLifecycleState.RUNNING in ALLOWED_TRANSITIONS[SessionLifecycleState.PAUSED]

    def test_paused_can_go_to_stopped(self):
        assert SessionLifecycleState.STOPPED in ALLOWED_TRANSITIONS[SessionLifecycleState.PAUSED]

    def test_stopped_can_go_to_created(self):
        assert SessionLifecycleState.CREATED in ALLOWED_TRANSITIONS[SessionLifecycleState.STOPPED]

    def test_error_can_go_to_created(self):
        assert SessionLifecycleState.CREATED in ALLOWED_TRANSITIONS[SessionLifecycleState.ERROR]


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


class TestApplyCustomConfig:
    """Test _apply_custom_config is called when custom_config is provided."""

    def test_apply_custom_config_called(self, apgi_patch):
        """SimulationSession calls _apply_custom_config when custom_config is truthy."""
        config = {"config_path": "c.yaml", "custom_config": {"key": "val"}}
        s = SimulationSession(VALID_UUID, config)
        # _apply_custom_config calls _initialize_subsystems
        apgi_patch._initialize_subsystems.assert_called()

    def test_apply_custom_config_deep_merge(self, apgi_patch):
        """_apply_custom_config deep-merges nested dicts."""
        apgi_patch.config = {"nested": {"a": 1, "b": 2}}
        s = SimulationSession(VALID_UUID, {"config_path": "c.yaml"})
        s._apply_custom_config({"nested": {"b": 99, "c": 3}})
        assert apgi_patch.config["nested"]["a"] == 1
        assert apgi_patch.config["nested"]["b"] == 99
        assert apgi_patch.config["nested"]["c"] == 3


class TestGetSessionEdgeCases:
    """Additional get_session coverage."""

    @pytest.mark.asyncio
    async def test_get_session_redis_ownership_mismatch_falls_through_to_db(
        self, session_manager, mock_redis, mock_db, apgi_patch
    ):
        """When Redis has session but user_id doesn't match, fall through to DB."""
        metadata = {
            "session_id": VALID_UUID,
            "user_id": "other_user",
            "state": "created",
            "config": {"config_path": "c.yaml"},
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        }
        mock_redis.get.return_value = json.dumps(metadata).encode()

        db_model = MagicMock()
        db_model.session_id = VALID_UUID
        db_model.config = {"config_path": "c.yaml"}
        db_model.state = "created"
        db_model.created_at = datetime.now(timezone.utc)
        db_model.updated_at = datetime.now(timezone.utc)
        db_model.full_state = None
        db_model.user_id = "user1"
        mock_db.execute.return_value.scalar_one_or_none.return_value = db_model

        result = await session_manager.get_session(VALID_UUID, user_id="user1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_session_not_found_without_user_id(
        self, session_manager, mock_redis, mock_db, apgi_patch
    ):
        """When session not found and no user_id, raises 'not found'."""
        mock_redis.get.return_value = None
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await session_manager.get_session(VALID_UUID, user_id=None)


class TestDeleteSessionError:
    """Test delete_session error path."""

    @pytest.mark.asyncio
    async def test_delete_session_db_error_rolls_back(self, session_manager, mock_db, apgi_patch):
        """When DB commit fails during delete, rollback is called and exception re-raised."""
        db_model = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = db_model
        mock_db.commit.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            await session_manager.delete_session(VALID_UUID)
        mock_db.rollback.assert_called()


class TestUpdateSessionStateWithUserId:
    """Test update_session_state with user_id triggers Redis cache update."""

    @pytest.mark.asyncio
    async def test_update_state_with_user_id_updates_redis(
        self, session_manager, mock_redis, mock_db, apgi_patch
    ):
        """When user_id is provided, Redis cache is updated after DB update."""
        db_model = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = db_model

        # For the get_session call triggered by user_id, return from memory cache
        mock_sim = MagicMock()
        mock_sim.state = SessionLifecycleState.RUNNING
        mock_sim.config = {"config_path": "c.yaml"}
        mock_sim.created_at = datetime.now(timezone.utc)
        mock_sim.updated_at = datetime.now(timezone.utc)
        session_manager.sessions[VALID_UUID] = (mock_sim, time.time())

        await session_manager.update_session_state(
            VALID_UUID, SessionLifecycleState.RUNNING, user_id="user1"
        )
        mock_redis.setex.assert_awaited()


class TestListSessionsNoBranch:
    """Test list_sessions when whereclause is None (no filters)."""

    @pytest.mark.asyncio
    async def test_list_sessions_no_user_no_state(self, session_manager, mock_db, apgi_patch):
        """list_sessions with no filters uses count without whereclause."""
        mock_db.scalar.return_value = 0
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = await session_manager.list_sessions()
        assert result["total"] == 0
        assert result["sessions"] == []


class TestPersistSession:
    """Test _persist_session coverage."""

    @pytest.mark.asyncio
    async def test_persist_session_not_in_cache_returns_early(self, session_manager, apgi_patch):
        """_persist_session returns early when session not in memory cache."""
        # Should not raise
        await session_manager._persist_session("nonexistent-id")

    @pytest.mark.asyncio
    async def test_persist_session_updates_db(self, session_manager, mock_db, apgi_patch):
        """_persist_session updates full_state in DB."""
        mock_sim = MagicMock()
        mock_sim.get_state = AsyncMock(return_value={"time": 1.0, "session_metadata": {}})
        session_manager.sessions[VALID_UUID] = (mock_sim, time.time())

        db_model = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = db_model

        await session_manager._persist_session(VALID_UUID)

        assert db_model.full_state is not None
        mock_db.commit.assert_called()


class TestEvictOldestSessions:
    """Test _evict_oldest_sessions coverage."""

    @pytest.mark.asyncio
    async def test_evict_oldest_when_over_limit(self, session_manager, mock_db, apgi_patch):
        """_evict_oldest_sessions removes oldest entries when over limit."""
        session_manager.session_cache_max_size = 2

        # Add 3 sessions
        for i in range(3):
            sid = f"1234567{i}-1234-1234-1234-123456789abc"
            mock_sim = MagicMock()
            mock_sim.get_state = AsyncMock(return_value={"time": float(i)})
            session_manager.sessions[sid] = (mock_sim, time.time() + i)

        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        async with session_manager.cache_lock:
            await session_manager._evict_oldest_sessions()

        assert len(session_manager.sessions) <= session_manager.session_cache_max_size
