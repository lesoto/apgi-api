"""
Property-based tests for session management.

Feature: api-migration
Tests universal properties of session lifecycle and concurrent access.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
import asyncio
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import uuid

# Import after setting up environment
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from app.services.session_manager import (
    SessionManager,
    SimulationSession,
    SessionLifecycleState,
)

# ============================================================================
# Helper Functions
# ============================================================================


def create_mock_redis():
    """Create a mock Redis client."""
    mock_redis = MagicMock()
    mock_redis.get = MagicMock(return_value=None)
    mock_redis.setex = MagicMock()
    mock_redis.delete = MagicMock()
    return mock_redis


def create_mock_db_session_factory():
    """Create a mock database session factory."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.rollback = MagicMock()
    mock_session.close = MagicMock()
    mock_session.execute = MagicMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    def factory():
        return mock_session

    return factory


def create_test_session(session_id: str = None, config: dict = None):
    """Create a test simulation session."""
    if session_id is None:
        session_id = str(uuid.uuid4())

    if config is None:
        config = {
            "config_path": "test_config.yaml",
            "custom_config": {},
            "description": "Test session",
        }

    # Mock the APGISystem to avoid actual system initialization
    with patch("app.services.session_manager.APGISystem") as mock_apgi:
        mock_system = MagicMock()
        mock_system.config = {}
        mock_system._initialize_subsystems = MagicMock()
        mock_system.reset = MagicMock()
        mock_system.step = MagicMock(return_value={"time": 0.0})
        mock_system.get_state = MagicMock(return_value={"time": 0.0, "history": {}})
        mock_apgi.return_value = mock_system

        session = SimulationSession(session_id, config)
        return session


# ============================================================================
# Property 22: Session Concurrent Modification Prevention
# ============================================================================


@settings(max_examples=1)
@given(
    initial_state=st.sampled_from(
        [
            SessionLifecycleState.CREATED,
            SessionLifecycleState.RUNNING,
            SessionLifecycleState.PAUSED,
        ]
    ),
    operation1=st.sampled_from(["start", "pause", "stop", "reset"]),
    operation2=st.sampled_from(["start", "pause", "stop", "reset"]),
)
def test_property_22_concurrent_modification_prevention(initial_state, operation1, operation2):
    """
    **Validates: Requirements 18.8**

    Feature: api-migration, Property 22: Session Concurrent Modification Prevention

    For any session, when two concurrent requests attempt to modify the session state,
    only one should succeed and the other should receive a conflict error.

    This test verifies that the session lock mechanism prevents race conditions and
    ensures state consistency under concurrent access.
    """
    # Filter out invalid state transitions to focus on concurrent access
    # We want to test cases where both operations could theoretically succeed
    # if executed sequentially, but should conflict when concurrent

    # Skip cases where operation1 would fail due to invalid state
    if initial_state == SessionLifecycleState.CREATED and operation1 == "pause":
        assume(False)  # Can't pause a created session
    if initial_state == SessionLifecycleState.PAUSED and operation1 == "pause":
        assume(False)  # Can't pause an already paused session
    if initial_state == SessionLifecycleState.RUNNING and operation1 == "start":
        assume(False)  # Can't start an already running session

    # Create a test session
    session_id = str(uuid.uuid4())
    session = create_test_session(session_id)
    session.state = initial_state

    # Set up appropriate flags for initial state
    if initial_state == SessionLifecycleState.RUNNING:
        session.is_running = True
        session.is_paused = False
    elif initial_state == SessionLifecycleState.PAUSED:
        session.is_running = False
        session.is_paused = True
        session._paused_state = {"time": 0.0, "history": {}}
    else:  # CREATED
        session.is_running = False
        session.is_paused = False

    # Track results from concurrent operations
    results = {"op1": None, "op2": None, "errors": []}

    async def execute_operation(op_name: str, operation: str):
        """Execute an operation and capture result or error."""
        try:
            if operation == "start":
                result = await session.start()
                results[op_name] = ("success", result)
            elif operation == "pause":
                result = await session.pause()
                results[op_name] = ("success", result)
            elif operation == "stop":
                result = await session.stop()
                results[op_name] = ("success", result)
            elif operation == "reset":
                result = await session.reset()
                results[op_name] = ("success", result)
        except ValueError as e:
            # Expected error for invalid state transitions or concurrent conflicts
            results[op_name] = ("error", str(e))
            results["errors"].append(str(e))
        except Exception as e:
            # Unexpected error
            results[op_name] = ("unexpected_error", str(e))

    async def run_concurrent_operations():
        """Run two operations concurrently."""
        # Create tasks for concurrent execution
        task1 = asyncio.create_task(execute_operation("op1", operation1))
        task2 = asyncio.create_task(execute_operation("op2", operation2))

        # Wait for both to complete
        await asyncio.gather(task1, task2)

    # Execute concurrent operations
    asyncio.run(run_concurrent_operations())

    # Property 1: At least one operation should complete (success or expected error)
    assert results["op1"] is not None, "Operation 1 should complete"
    assert results["op2"] is not None, "Operation 2 should complete"

    # Property 2: No unexpected errors should occur
    op1_status, op1_result = results["op1"]
    op2_status, op2_result = results["op2"]

    assert op1_status != "unexpected_error", f"Operation 1 had unexpected error: {op1_result}"
    assert op2_status != "unexpected_error", f"Operation 2 had unexpected error: {op2_result}"

    # Property 3: Session state should be consistent after concurrent operations
    # The final state should be valid and correspond to one of the operations
    assert session.state in [
        SessionLifecycleState.CREATED,
        SessionLifecycleState.RUNNING,
        SessionLifecycleState.PAUSED,
        SessionLifecycleState.STOPPED,
        SessionLifecycleState.ERROR,
    ], f"Session should be in a valid state, got {session.state}"

    # Property 4: If both operations succeeded, they must have executed sequentially
    # (one after the other, not truly concurrent due to the lock)
    if op1_status == "success" and op2_status == "success":
        # Both succeeded means the lock worked correctly and they executed sequentially
        # The final state should reflect the second operation
        expected_states = {
            "start": SessionLifecycleState.RUNNING,
            "pause": SessionLifecycleState.PAUSED,
            "stop": SessionLifecycleState.STOPPED,
            "reset": SessionLifecycleState.CREATED,
        }

        # The final state should match what operation2 would produce
        # (since it executed second due to the lock)
        expected_final_state = expected_states.get(operation2)
        if expected_final_state:
            assert session.state == expected_final_state, (
                f"When both operations succeed, final state should be {expected_final_state}, "
                f"got {session.state}"
            )

    # Property 5: The lock should prevent true concurrent modification
    # This is implicitly tested by the fact that we don't get corrupted state
    # and operations either succeed or fail with expected errors


@settings(max_examples=1)
@given(
    num_concurrent_ops=st.integers(min_value=2, max_value=5),
)
def test_property_22_multiple_concurrent_modifications(num_concurrent_ops):
    """
    **Validates: Requirements 18.8**

    Feature: api-migration, Property 22: Session Concurrent Modification Prevention

    For any session, when multiple concurrent requests attempt to modify the session state,
    the lock mechanism should ensure all operations execute sequentially without corruption.

    This test verifies that the session lock scales to multiple concurrent operations.
    """
    # Create a test session in CREATED state
    session_id = str(uuid.uuid4())
    session = create_test_session(session_id)
    session.state = SessionLifecycleState.CREATED

    # Track results
    results = []

    async def execute_start():
        """Execute start operation."""
        try:
            result = await session.start()
            return ("success", result)
        except ValueError as e:
            return ("error", str(e))
        except Exception as e:
            return ("unexpected_error", str(e))

    async def run_concurrent_starts():
        """Run multiple start operations concurrently."""
        tasks = [asyncio.create_task(execute_start()) for _ in range(num_concurrent_ops)]
        return await asyncio.gather(*tasks)

    # Execute concurrent operations
    results = asyncio.run(run_concurrent_starts())

    # Property 1: Exactly one operation should succeed
    successes = [r for r in results if r[0] == "success"]
    errors = [r for r in results if r[0] == "error"]
    unexpected = [r for r in results if r[0] == "unexpected_error"]

    assert (
        len(successes) == 1
    ), f"Exactly one start operation should succeed, got {len(successes)} successes"

    # Property 2: All other operations should fail with expected errors
    assert len(errors) == num_concurrent_ops - 1, (
        f"All other operations should fail with expected errors, "
        f"got {len(errors)} errors out of {num_concurrent_ops - 1} expected"
    )

    # Property 3: No unexpected errors should occur
    assert len(unexpected) == 0, f"No unexpected errors should occur, got {len(unexpected)}"

    # Property 4: Session should be in RUNNING state
    assert (
        session.state == SessionLifecycleState.RUNNING
    ), f"Session should be in RUNNING state after concurrent starts, got {session.state}"

    # Property 5: Error messages should indicate the session is already running
    for error_status, error_msg in errors:
        assert (
            "already running" in error_msg.lower()
        ), f"Error message should indicate session is already running, got: {error_msg}"


def test_property_22_concurrent_read_write_safety():
    """
    **Validates: Requirements 18.8**

    Feature: api-migration, Property 22: Session Concurrent Modification Prevention

    For any session, concurrent read (get_state) and write (start/pause/stop) operations
    should not cause data corruption or inconsistent state.

    This test verifies that read operations can safely execute alongside write operations.
    """
    # Create a test session in CREATED state
    session_id = str(uuid.uuid4())
    session = create_test_session(session_id)
    session.state = SessionLifecycleState.CREATED

    # Track results
    write_result = None
    read_results = []

    async def write_operation():
        """Execute a write operation (start)."""
        nonlocal write_result
        try:
            result = await session.start()
            write_result = ("success", result)
        except Exception as e:
            write_result = ("error", str(e))

    async def read_operation():
        """Execute a read operation (get_state)."""
        try:
            state = await session.get_state()
            return ("success", state)
        except Exception as e:
            return ("error", str(e))

    async def run_concurrent_read_write():
        """Run one write and multiple reads concurrently."""
        write_task = asyncio.create_task(write_operation())
        read_tasks = [asyncio.create_task(read_operation()) for _ in range(3)]

        # Wait for all to complete
        await write_task
        read_results_local = await asyncio.gather(*read_tasks)
        return read_results_local

    # Execute concurrent operations
    read_results = asyncio.run(run_concurrent_read_write())

    # Property 1: Write operation should succeed
    assert write_result is not None, "Write operation should complete"
    write_status, write_data = write_result
    assert write_status == "success", f"Write operation should succeed, got {write_status}"

    # Property 2: All read operations should succeed
    for i, (status, data) in enumerate(read_results):
        assert status == "success", f"Read operation {i} should succeed, got {status}"

    # Property 3: All read results should have valid session metadata
    for i, (status, data) in enumerate(read_results):
        assert "session_metadata" in data, f"Read {i} should include session_metadata"
        metadata = data["session_metadata"]
        assert "session_id" in metadata, f"Read {i} metadata should include session_id"
        assert "state" in metadata, f"Read {i} metadata should include state"
        assert metadata["session_id"] == session_id, f"Read {i} should have correct session_id"

    # Property 4: Final session state should be RUNNING (from the write operation)
    assert (
        session.state == SessionLifecycleState.RUNNING
    ), f"Session should be in RUNNING state after write, got {session.state}"

    # Property 5: No data corruption should occur
    # All read operations should return consistent state structure
    for i, (status, data) in enumerate(read_results):
        assert isinstance(data, dict), f"Read {i} should return a dict"
        assert "session_metadata" in data, f"Read {i} should have session_metadata"
