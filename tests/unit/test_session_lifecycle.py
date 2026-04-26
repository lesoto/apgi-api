"""
Unit tests for SessionLifecycleState transitions.

Verifies that every allowed transition succeeds and every disallowed
transition raises ValueError.
"""

import uuid
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from app.services.session_manager import (
    ALLOWED_TRANSITIONS,
    SessionLifecycleState,
    SimulationSession,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def apgi_patch() -> Generator[MagicMock, None, None]:
    """Patch APGISystem so SimulationSession can be instantiated without the real library."""
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


def _session(state: SessionLifecycleState) -> SimulationSession:
    """Create a SimulationSession pre-set to the given state."""
    s = SimulationSession(str(uuid.uuid4()), {"config_path": "c.yaml"})
    s.state = state
    return s


# ---------------------------------------------------------------------------
# Helpers that map state → transition method
# ---------------------------------------------------------------------------


async def _do_transition(
    session: SimulationSession, target: SessionLifecycleState
) -> dict[str, Any]:
    """Invoke the appropriate method to attempt a transition to `target`."""
    if target == SessionLifecycleState.RUNNING:
        return await session.start()
    elif target == SessionLifecycleState.PAUSED:
        return await session.pause()
    elif target == SessionLifecycleState.STOPPED:
        return await session.stop()
    elif target == SessionLifecycleState.CREATED:
        return await session.reset()
    else:
        raise NotImplementedError(f"No method mapped for target {target}")


# ---------------------------------------------------------------------------
# Allowed transitions — must succeed
# ---------------------------------------------------------------------------


class TestAllowedTransitions:
    """Every entry in ALLOWED_TRANSITIONS should succeed without raising."""

    @pytest.mark.asyncio
    async def test_created_to_running(self) -> None:
        s = _session(SessionLifecycleState.CREATED)
        result = await _do_transition(s, SessionLifecycleState.RUNNING)
        assert s.state == SessionLifecycleState.RUNNING
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_created_to_stopped(self) -> None:
        s = _session(SessionLifecycleState.CREATED)
        result = await _do_transition(s, SessionLifecycleState.STOPPED)
        assert s.state == SessionLifecycleState.STOPPED
        assert result["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_created_to_error(self) -> None:
        """ERROR is in ALLOWED_TRANSITIONS[CREATED] but has no dedicated method;
        verify it is listed and that _can_transition_to returns True."""
        s = _session(SessionLifecycleState.CREATED)
        assert s._can_transition_to(SessionLifecycleState.ERROR) is True

    @pytest.mark.asyncio
    async def test_running_to_paused(self) -> None:
        s = _session(SessionLifecycleState.RUNNING)
        s.is_running = True
        result = await _do_transition(s, SessionLifecycleState.PAUSED)
        assert s.state == SessionLifecycleState.PAUSED
        assert result["status"] == "paused"

    @pytest.mark.asyncio
    async def test_running_to_stopped(self) -> None:
        s = _session(SessionLifecycleState.RUNNING)
        s.is_running = True
        result = await _do_transition(s, SessionLifecycleState.STOPPED)
        assert s.state == SessionLifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_running_to_error(self) -> None:
        s = _session(SessionLifecycleState.RUNNING)
        assert s._can_transition_to(SessionLifecycleState.ERROR) is True

    @pytest.mark.asyncio
    async def test_paused_to_running(self) -> None:
        s = _session(SessionLifecycleState.PAUSED)
        result = await _do_transition(s, SessionLifecycleState.RUNNING)
        assert s.state == SessionLifecycleState.RUNNING

    @pytest.mark.asyncio
    async def test_paused_to_stopped(self) -> None:
        s = _session(SessionLifecycleState.PAUSED)
        result = await _do_transition(s, SessionLifecycleState.STOPPED)
        assert s.state == SessionLifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_paused_to_error(self) -> None:
        s = _session(SessionLifecycleState.PAUSED)
        assert s._can_transition_to(SessionLifecycleState.ERROR) is True

    @pytest.mark.asyncio
    async def test_stopped_to_created(self) -> None:
        s = _session(SessionLifecycleState.STOPPED)
        result = await _do_transition(s, SessionLifecycleState.CREATED)
        assert s.state == SessionLifecycleState.CREATED

    @pytest.mark.asyncio
    async def test_stopped_to_error(self) -> None:
        s = _session(SessionLifecycleState.STOPPED)
        assert s._can_transition_to(SessionLifecycleState.ERROR) is True

    @pytest.mark.asyncio
    async def test_error_to_created(self) -> None:
        s = _session(SessionLifecycleState.ERROR)
        result = await _do_transition(s, SessionLifecycleState.CREATED)
        assert s.state == SessionLifecycleState.CREATED


# ---------------------------------------------------------------------------
# Disallowed transitions — must raise ValueError
# ---------------------------------------------------------------------------


class TestDisallowedTransitions:
    """Every transition NOT in ALLOWED_TRANSITIONS should raise ValueError."""

    @pytest.mark.asyncio
    async def test_created_cannot_pause(self) -> None:
        s = _session(SessionLifecycleState.CREATED)
        with pytest.raises(ValueError):
            await s.pause()

    @pytest.mark.asyncio
    async def test_created_cannot_reset(self) -> None:
        s = _session(SessionLifecycleState.CREATED)
        with pytest.raises(ValueError):
            await s.reset()

    @pytest.mark.asyncio
    async def test_running_cannot_start(self) -> None:
        s = _session(SessionLifecycleState.RUNNING)
        with pytest.raises(ValueError):
            await s.start()

    @pytest.mark.asyncio
    async def test_running_cannot_reset(self) -> None:
        s = _session(SessionLifecycleState.RUNNING)
        with pytest.raises(ValueError):
            await s.reset()

    @pytest.mark.asyncio
    async def test_paused_cannot_pause(self) -> None:
        s = _session(SessionLifecycleState.PAUSED)
        with pytest.raises(ValueError):
            await s.pause()

    @pytest.mark.asyncio
    async def test_paused_cannot_reset(self) -> None:
        s = _session(SessionLifecycleState.PAUSED)
        with pytest.raises(ValueError):
            await s.reset()

    @pytest.mark.asyncio
    async def test_stopped_cannot_start(self) -> None:
        s = _session(SessionLifecycleState.STOPPED)
        with pytest.raises(ValueError):
            await s.start()

    @pytest.mark.asyncio
    async def test_stopped_cannot_pause(self) -> None:
        s = _session(SessionLifecycleState.STOPPED)
        with pytest.raises(ValueError):
            await s.pause()

    @pytest.mark.asyncio
    async def test_stopped_cannot_stop(self) -> None:
        s = _session(SessionLifecycleState.STOPPED)
        with pytest.raises(ValueError):
            await s.stop()

    @pytest.mark.asyncio
    async def test_error_cannot_start(self) -> None:
        s = _session(SessionLifecycleState.ERROR)
        with pytest.raises(ValueError):
            await s.start()

    @pytest.mark.asyncio
    async def test_error_cannot_pause(self) -> None:
        s = _session(SessionLifecycleState.ERROR)
        with pytest.raises(ValueError):
            await s.pause()

    @pytest.mark.asyncio
    async def test_error_cannot_stop(self) -> None:
        s = _session(SessionLifecycleState.ERROR)
        with pytest.raises(ValueError):
            await s.stop()


# ---------------------------------------------------------------------------
# State invariants
# ---------------------------------------------------------------------------


class TestStateInvariants:
    @pytest.mark.asyncio
    async def test_state_unchanged_after_invalid_transition(self) -> None:
        s = _session(SessionLifecycleState.CREATED)
        try:
            await s.pause()
        except ValueError:
            pass
        assert s.state == SessionLifecycleState.CREATED

    def test_all_states_have_transition_entry(self) -> None:
        """Every SessionLifecycleState must appear as a key in ALLOWED_TRANSITIONS."""
        for state in SessionLifecycleState:
            assert state in ALLOWED_TRANSITIONS, f"{state} missing from ALLOWED_TRANSITIONS"

    def test_allowed_transitions_are_valid_states(self) -> None:
        """Every target in ALLOWED_TRANSITIONS must be a valid SessionLifecycleState."""
        valid = set(SessionLifecycleState)
        for src, targets in ALLOWED_TRANSITIONS.items():
            for tgt in targets:
                assert tgt in valid, f"Invalid target {tgt} from {src}"

    @pytest.mark.asyncio
    async def test_full_lifecycle_created_running_paused_running_stopped_created(self) -> None:
        """Happy-path full lifecycle round-trip."""
        s = SimulationSession(str(uuid.uuid4()), {"config_path": "c.yaml"})
        assert s.state == SessionLifecycleState.CREATED
        await s.start()
        assert s.state == SessionLifecycleState.RUNNING  # type: ignore[comparison-overlap]
        await s.pause()
        assert s.state == SessionLifecycleState.PAUSED
        await s.start()  # resume
        assert s.state == SessionLifecycleState.RUNNING
        await s.stop()
        assert s.state == SessionLifecycleState.STOPPED
        await s.reset()
        assert s.state == SessionLifecycleState.CREATED
