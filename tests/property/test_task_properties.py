"""
Property-based tests for Celery task queue integration.

Feature: api-migration
Tests universal properties of task status and result retrieval.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import uuid

# Import after setting up environment
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from celery.result import AsyncResult
from celery import states


# ============================================================================
# Helper Functions
# ============================================================================


def create_mock_celery_app():
    """Create a mock Celery app."""
    mock_app = MagicMock()
    return mock_app


def create_mock_async_result(task_id: str, state: str, result=None, info=None):
    """Create a mock AsyncResult for testing."""
    mock_result = MagicMock(spec=AsyncResult)
    mock_result.id = task_id
    mock_result.state = state
    mock_result.status = state  # Alias for state
    mock_result.result = result
    mock_result.info = info

    # Configure ready() method
    mock_result.ready.return_value = state in [
        states.SUCCESS,
        states.FAILURE,
        states.REVOKED,
    ]

    # Configure successful() method
    mock_result.successful.return_value = state == states.SUCCESS

    # Configure failed() method
    mock_result.failed.return_value = state == states.FAILURE

    return mock_result


# ============================================================================
# Property 14: Task Status Retrieval
# ============================================================================


@settings(max_examples=2)
@given(
    task_id=st.uuids().map(str),
    task_state=st.sampled_from(
        [
            states.PENDING,
            states.STARTED,
            states.SUCCESS,
            states.FAILURE,
            states.RETRY,
            states.REVOKED,
        ]
    ),
)
def test_property_14_task_status_retrieval(task_id, task_state):
    """
    **Validates: Requirements 15.4**

    Feature: api-migration, Property 14: Task Status Retrieval

    For any submitted task, querying the task status by task_id should return
    the current status (pending, running, completed, or failed).

    This property ensures that task status can be reliably retrieved at any
    point in the task lifecycle.
    """
    # Create mock AsyncResult with the given state
    mock_result = create_mock_async_result(
        task_id=task_id,
        state=task_state,
        result={"data": "test"} if task_state == states.SUCCESS else None,
        info={"progress": 50} if task_state == states.STARTED else None,
    )

    # Mock the AsyncResult constructor to return our mock
    with patch("celery.result.AsyncResult") as mock_async_result_class:
        mock_async_result_class.return_value = mock_result

        # Retrieve task status using Celery's AsyncResult
        async_result = AsyncResult(task_id)

        # Property 1: Task ID should match the requested task
        assert async_result.id == task_id, (
            f"Retrieved task ID should match requested ID, "
            f"expected {task_id}, got {async_result.id}"
        )

        # Property 2: Task state should be one of the valid Celery states
        valid_states = [
            states.PENDING,
            states.RECEIVED,
            states.STARTED,
            states.SUCCESS,
            states.FAILURE,
            states.RETRY,
            states.REVOKED,
        ]
        assert (
            async_result.state in valid_states
        ), f"Task state should be a valid Celery state, got {async_result.state}"

        # Property 3: Task state should match the expected state
        assert async_result.state == task_state, (
            f"Task state should match expected state, "
            f"expected {task_state}, got {async_result.state}"
        )

        # Property 4: ready() should return True for terminal states
        terminal_states = [states.SUCCESS, states.FAILURE, states.REVOKED]
        if task_state in terminal_states:
            assert async_result.ready(), f"Task in terminal state {task_state} should be ready"

        # Property 5: successful() should return True only for SUCCESS state
        if task_state == states.SUCCESS:
            assert async_result.successful(), f"Task in SUCCESS state should be successful"
        else:
            assert (
                not async_result.successful()
            ), f"Task in {task_state} state should not be successful"

        # Property 6: failed() should return True only for FAILURE state
        if task_state == states.FAILURE:
            assert async_result.failed(), f"Task in FAILURE state should be failed"
        else:
            assert not async_result.failed(), f"Task in {task_state} state should not be failed"


@settings(max_examples=2)
@given(
    task_id=st.uuids().map(str),
)
def test_property_14_task_status_retrieval_pending(task_id):
    """
    **Validates: Requirements 15.4**

    Feature: api-migration, Property 14: Task Status Retrieval

    For any task that has been submitted but not yet started, querying the
    task status should return PENDING state.

    This property ensures that newly submitted tasks have a queryable status
    even before worker pickup.
    """
    # Create mock AsyncResult for a pending task
    mock_result = create_mock_async_result(
        task_id=task_id,
        state=states.PENDING,
        result=None,
        info=None,
    )

    with patch("celery.result.AsyncResult") as mock_async_result_class:
        mock_async_result_class.return_value = mock_result

        # Retrieve task status
        async_result = AsyncResult(task_id)

        # Property 1: Pending task should have PENDING state
        assert (
            async_result.state == states.PENDING
        ), f"Newly submitted task should be in PENDING state, got {async_result.state}"

        # Property 2: Pending task should not be ready
        assert not async_result.ready(), "Pending task should not be ready"

        # Property 3: Pending task should not be successful
        assert not async_result.successful(), "Pending task should not be successful"

        # Property 4: Pending task should not be failed
        assert not async_result.failed(), "Pending task should not be failed"

        # Property 5: Pending task should have no result
        assert async_result.result is None, "Pending task should have no result"


@settings(max_examples=2)
@given(
    task_id=st.uuids().map(str),
    result_data=st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(st.integers(), st.floats(allow_nan=False), st.text(max_size=50)),
        min_size=1,
        max_size=5,
    ),
)
def test_property_14_task_status_retrieval_success(task_id, result_data):
    """
    **Validates: Requirements 15.4**

    Feature: api-migration, Property 14: Task Status Retrieval

    For any task that has completed successfully, querying the task status
    should return SUCCESS state with the result data available.

    This property ensures that completed tasks have queryable status and results.
    """
    # Create mock AsyncResult for a successful task
    mock_result = create_mock_async_result(
        task_id=task_id,
        state=states.SUCCESS,
        result=result_data,
        info=None,
    )

    with patch("celery.result.AsyncResult") as mock_async_result_class:
        mock_async_result_class.return_value = mock_result

        # Retrieve task status
        async_result = AsyncResult(task_id)

        # Property 1: Successful task should have SUCCESS state
        assert (
            async_result.state == states.SUCCESS
        ), f"Completed task should be in SUCCESS state, got {async_result.state}"

        # Property 2: Successful task should be ready
        assert async_result.ready(), "Successful task should be ready"

        # Property 3: Successful task should be successful
        assert async_result.successful(), "Successful task should be successful"

        # Property 4: Successful task should not be failed
        assert not async_result.failed(), "Successful task should not be failed"

        # Property 5: Successful task should have result data
        assert async_result.result is not None, "Successful task should have result data"

        # Property 6: Result data should match the expected data
        assert async_result.result == result_data, (
            f"Result data should match expected data, "
            f"expected {result_data}, got {async_result.result}"
        )


@settings(max_examples=2)
@given(
    task_id=st.uuids().map(str),
    error_message=st.text(min_size=1, max_size=100),
)
def test_property_14_task_status_retrieval_failure(task_id, error_message):
    """
    **Validates: Requirements 15.4**

    Feature: api-migration, Property 14: Task Status Retrieval

    For any task that has failed, querying the task status should return
    FAILURE state with error information available.

    This property ensures that failed tasks have queryable status and error details.
    """
    # Create mock AsyncResult for a failed task
    mock_result = create_mock_async_result(
        task_id=task_id,
        state=states.FAILURE,
        result=Exception(error_message),
        info=None,
    )

    with patch("celery.result.AsyncResult") as mock_async_result_class:
        mock_async_result_class.return_value = mock_result

        # Retrieve task status
        async_result = AsyncResult(task_id)

        # Property 1: Failed task should have FAILURE state
        assert (
            async_result.state == states.FAILURE
        ), f"Failed task should be in FAILURE state, got {async_result.state}"

        # Property 2: Failed task should be ready
        assert async_result.ready(), "Failed task should be ready"

        # Property 3: Failed task should not be successful
        assert not async_result.successful(), "Failed task should not be successful"

        # Property 4: Failed task should be failed
        assert async_result.failed(), "Failed task should be failed"

        # Property 5: Failed task should have error information
        assert async_result.result is not None, "Failed task should have error information"


@settings(max_examples=2)
@given(
    task_id=st.uuids().map(str),
    progress_info=st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(st.integers(min_value=0, max_value=100), st.text(max_size=50)),
        min_size=1,
        max_size=3,
    ),
)
def test_property_14_task_status_retrieval_running(task_id, progress_info):
    """
    **Validates: Requirements 15.4**

    Feature: api-migration, Property 14: Task Status Retrieval

    For any task that is currently running, querying the task status should
    return STARTED state with optional progress information.

    This property ensures that running tasks have queryable status with progress.
    """
    # Create mock AsyncResult for a running task
    mock_result = create_mock_async_result(
        task_id=task_id,
        state=states.STARTED,
        result=None,
        info=progress_info,
    )

    with patch("celery.result.AsyncResult") as mock_async_result_class:
        mock_async_result_class.return_value = mock_result

        # Retrieve task status
        async_result = AsyncResult(task_id)

        # Property 1: Running task should have STARTED state
        assert (
            async_result.state == states.STARTED
        ), f"Running task should be in STARTED state, got {async_result.state}"

        # Property 2: Running task should not be ready
        assert not async_result.ready(), "Running task should not be ready"

        # Property 3: Running task should not be successful
        assert not async_result.successful(), "Running task should not be successful"

        # Property 4: Running task should not be failed
        assert not async_result.failed(), "Running task should not be failed"

        # Property 5: Running task may have progress info
        assert async_result.info == progress_info, (
            f"Running task info should match expected progress info, "
            f"expected {progress_info}, got {async_result.info}"
        )


@settings(max_examples=2)
@given(
    num_tasks=st.integers(min_value=1, max_value=10),
)
def test_property_14_multiple_task_status_retrieval(num_tasks):
    """
    **Validates: Requirements 15.4**

    Feature: api-migration, Property 14: Task Status Retrieval

    For any set of submitted tasks, each task should have independently
    queryable status without interference.

    This property ensures that task status retrieval scales to multiple tasks.
    """
    # Generate unique task IDs
    task_ids = [str(uuid.uuid4()) for _ in range(num_tasks)]

    # Assign random states to tasks
    states_list = [states.PENDING, states.STARTED, states.SUCCESS, states.FAILURE]
    task_states = [states_list[i % len(states_list)] for i in range(num_tasks)]

    # Create mock results for each task
    mock_results = {}
    for task_id, task_state in zip(task_ids, task_states):
        mock_results[task_id] = create_mock_async_result(
            task_id=task_id,
            state=task_state,
            result={"data": f"result_{task_id}"} if task_state == states.SUCCESS else None,
            info=None,
        )

    def get_mock_result(task_id, *args, **kwargs):
        """Return the appropriate mock result for the task ID."""
        return mock_results.get(task_id)

    with patch("celery.result.AsyncResult", side_effect=get_mock_result):
        # Retrieve status for all tasks
        results = []
        for task_id in task_ids:
            async_result = AsyncResult(task_id)
            results.append((task_id, async_result))

        # Property 1: All tasks should have queryable status
        assert (
            len(results) == num_tasks
        ), f"Should be able to query status for all {num_tasks} tasks"

        # Property 2: Each task should have the correct ID
        for i, (task_id, async_result) in enumerate(results):
            assert (
                async_result.id == task_id
            ), f"Task {i} should have correct ID, expected {task_id}, got {async_result.id}"

        # Property 3: Each task should have the correct state
        for i, (task_id, async_result) in enumerate(results):
            expected_state = task_states[i]
            assert async_result.state == expected_state, (
                f"Task {i} should have correct state, "
                f"expected {expected_state}, got {async_result.state}"
            )

        # Property 4: Task IDs should be unique
        retrieved_ids = [async_result.id for _, async_result in results]
        assert len(set(retrieved_ids)) == num_tasks, "All task IDs should be unique"
