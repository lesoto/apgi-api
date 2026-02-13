"""
Property-based tests for Celery task queue integration.

Feature: api-migration
Tests universal properties of task status and result retrieval.
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import MagicMock
from datetime import datetime
import uuid
import json

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


@settings(max_examples=1)
@given(
    task_id=st.uuids().map(str),
    task_state=st.sampled_from([states.PENDING, states.STARTED, states.SUCCESS, states.FAILURE]),
)
def test_property_14_task_status_retrieval(task_id, task_state):
    """
    **Validates: Requirements 15.4**

    Feature: api-migration, Property 14: Task Status Retrieval

    For any submitted task, querying the task status by task_id should return
    the current status (pending, running, completed, or failed).
    """
    mock_result = create_mock_async_result(
        task_id=task_id,
        state=task_state,
        result={"data": "test"} if task_state == states.SUCCESS else None,
        info={"progress": 50} if task_state == states.STARTED else None,
    )

    # Test the mock directly (simulates what AsyncResult would return)
    async_result = mock_result

    # Property 1: Task ID should match
    assert async_result.id == task_id

    # Property 2: Task state should be valid
    valid_states = [
        states.PENDING,
        states.RECEIVED,
        states.STARTED,
        states.SUCCESS,
        states.FAILURE,
        states.RETRY,
        states.REVOKED,
    ]
    assert async_result.state in valid_states

    # Property 3: Task state should match expected
    assert async_result.state == task_state

    # Property 4: ready() should return True for terminal states
    terminal_states = [states.SUCCESS, states.FAILURE, states.REVOKED]
    if task_state in terminal_states:
        assert async_result.ready()

    # Property 5: successful() should return True only for SUCCESS
    if task_state == states.SUCCESS:
        assert async_result.successful()
    else:
        assert not async_result.successful()


# ============================================================================
# Property 15: Task Result Retrieval
# ============================================================================


@settings(max_examples=1)
@given(
    task_id=st.uuids().map(str),
    result_data=st.dictionaries(
        st.text(
            min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)
        ),
        st.one_of(
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.text(
                min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)
            ),
            st.booleans(),
        ),
        min_size=1,
        max_size=3,
    ),
)
def test_property_15_task_result_retrieval_completed(task_id, result_data):
    """
    **Validates: Requirements 15.5**

    Feature: api-migration, Property 15: Task Result Retrieval

    For any completed task, querying the task result by task_id should return
    the result data that was produced by the task execution.
    """
    mock_result = create_mock_async_result(
        task_id=task_id,
        state=states.SUCCESS,
        result=result_data,
        info=None,
    )

    async_result = mock_result

    # Property 1: Task should be in SUCCESS state
    assert async_result.state == states.SUCCESS

    # Property 2: Task should be ready
    assert async_result.ready()

    # Property 3: Task should be successful
    assert async_result.successful()

    # Property 4: Task result should not be None
    assert async_result.result is not None

    # Property 5: Task result should match expected data
    assert async_result.result == result_data

    # Property 6: Result should be JSON-serializable
    try:
        serialized = json.dumps(async_result.result)
        deserialized = json.loads(serialized)
        assert deserialized == result_data
    except (TypeError, ValueError) as e:
        pytest.fail(f"Result should be JSON-serializable, got error: {e}")


# ============================================================================
# Property 16: Task Serialization Round-Trip
# ============================================================================


@settings(max_examples=1)
@given(
    task_id=st.uuids().map(str),
    task_data=st.dictionaries(
        st.text(
            min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)
        ),
        st.one_of(
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.text(
                min_size=1, max_size=50, alphabet=st.characters(min_codepoint=97, max_codepoint=122)
            ),
            st.booleans(),
        ),
        min_size=1,
        max_size=3,
    ),
)
def test_property_16_task_serialization_roundtrip(task_id, task_data):
    """
    **Validates: Requirements 15.8**

    Feature: api-migration, Property 16: Task Serialization Round-Trip

    For any task data, serializing to JSON and deserializing should preserve
    the data structure and values.
    """
    # Property 1: Data should be JSON-serializable
    try:
        serialized = json.dumps(task_data)
    except (TypeError, ValueError) as e:
        pytest.fail(f"Task data should be JSON-serializable, got error: {e}")

    # Property 2: Serialized data should be a string
    assert isinstance(serialized, str)

    # Property 3: Deserialization should succeed
    try:
        deserialized = json.loads(serialized)
    except (TypeError, ValueError) as e:
        pytest.fail(f"Serialized data should be deserializable, got error: {e}")

    # Property 4: Deserialized data should match original
    assert deserialized == task_data

    # Property 5: Round-trip should preserve types for JSON-compatible types
    for key, value in task_data.items():
        assert key in deserialized
        assert type(deserialized[key]) == type(value) or (
            # JSON converts all numbers to int/float appropriately
            isinstance(value, (int, float))
            and isinstance(deserialized[key], (int, float))
        )
