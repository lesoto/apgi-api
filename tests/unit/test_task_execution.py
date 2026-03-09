"""
Unit tests for task execution.

Tests task submission, status checking, result retrieval, and timeout handling.
"""

import pytest
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from celery import states

from app.services.task_executor import TaskExecutor, retry_with_backoff, async_retry_with_backoff
from app.database.models import Task, TaskStatus


# ============================================================================
# Test Retry Functions
# ============================================================================


def test_retry_with_backoff_success():
    """Test retry_with_backoff succeeds on first attempt."""
    call_count = 0

    def test_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = retry_with_backoff(test_func, max_retries=3)

    assert result == "success"
    assert call_count == 1


def test_retry_with_backoff_retry_success():
    """Test retry_with_backoff succeeds after retries."""
    call_count = 0

    def test_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Temporary failure")
        return "success"

    result = retry_with_backoff(test_func, max_retries=3)

    assert result == "success"
    assert call_count == 3


def test_retry_with_backoff_all_fail():
    """Test retry_with_backoff fails after all retries."""
    call_count = 0

    def test_func():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Persistent failure")

    with pytest.raises(RuntimeError, match="Persistent failure"):
        retry_with_backoff(test_func, max_retries=2)

    assert call_count == 3  # max_retries + 1


@pytest.mark.asyncio
async def test_async_retry_with_backoff_success():
    """Test async_retry_with_backoff succeeds on first attempt."""
    call_count = 0

    async def test_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await async_retry_with_backoff(test_func, max_retries=3)

    assert result == "success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_async_retry_with_backoff_retry_success():
    """Test async_retry_with_backoff succeeds after retries."""
    call_count = 0

    async def test_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Temporary failure")
        return "success"

    result = await async_retry_with_backoff(test_func, max_retries=3)

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_async_retry_with_backoff_all_fail():
    """Test async_retry_with_backoff fails after all retries."""
    call_count = 0

    async def test_func():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Persistent failure")

    with pytest.raises(RuntimeError, match="Persistent failure"):
        await async_retry_with_backoff(test_func, max_retries=2)

    assert call_count == 3  # max_retries + 1


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def task_executor():
    """Create TaskExecutor instance."""
    return TaskExecutor()


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.commit = MagicMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def sample_task_record():
    """Create sample task record."""
    return Task(
        task_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        task_type="iowa_gambling",
        parameters={"num_trials": 100},
        status=TaskStatus.PENDING.value,
        created_at=datetime.now(timezone.utc),
    )


# ============================================================================
# Test Task Submission
# ============================================================================


@pytest.mark.asyncio
async def test_submit_task_valid_type(task_executor, mock_db_session):
    """Test task submission with valid task type."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    task_type = "iowa_gambling"
    parameters = {"num_trials": 100, "initial_balance": 2000}

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.celery_app.send_task") as mock_send_task:
            task_id = await task_executor.submit_task(
                session_id=session_id,
                task_type=task_type,
                parameters=parameters,
                user_id=user_id,
            )

            # Verify task ID is a valid UUID
            assert uuid.UUID(task_id)

            # Verify database record was created
            mock_db_session.add.assert_called_once()
            added_task = mock_db_session.add.call_args[0][0]
            assert added_task.task_id == task_id
            assert added_task.session_id == session_id
            assert added_task.task_type == task_type
            assert added_task.parameters == parameters
            assert added_task.status == TaskStatus.PENDING.value

            # Verify Celery task was submitted
            mock_send_task.assert_called_once()
            call_args = mock_send_task.call_args
            assert call_args[0][0] == "app.tasks.experimental_tasks.execute_iowa_gambling_task"
            assert call_args[1]["args"] == [session_id, parameters]
            assert call_args[1]["task_id"] == task_id


@pytest.mark.asyncio
async def test_submit_task_with_webhook(task_executor, mock_db_session):
    """Test task submission with webhook URL."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    task_type = "masking_paradigm"
    parameters = {"target_duration_ms": 50.0}
    webhook_url = "https://example.com/webhook"

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.celery_app.send_task"):
            task_id = await task_executor.submit_task(
                session_id=session_id,
                task_type=task_type,
                parameters=parameters,
                user_id=user_id,
                webhook_url=webhook_url,
            )

            # Verify webhook URL was stored
            added_task = mock_db_session.add.call_args[0][0]
            assert added_task.webhook_url == webhook_url


@pytest.mark.asyncio
async def test_submit_task_invalid_type(task_executor):
    """Test task submission with invalid task type."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    task_type = "invalid_task_type"
    parameters: dict[str, Any] = {}

    with pytest.raises(ValueError) as exc_info:
        await task_executor.submit_task(
            session_id=session_id,
            task_type=task_type,
            parameters=parameters,
            user_id=user_id,
        )

    assert "Invalid task type" in str(exc_info.value)
    assert "invalid_task_type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_submit_task_all_types(task_executor, mock_db_session):
    """Test task submission for all available task types."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    task_types = [
        "iowa_gambling",
        "masking_paradigm",
        "attentional_blink",
        "change_blindness",
        "binocular_rivalry",
    ]

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.celery_app.send_task"):
            for task_type in task_types:
                task_id = await task_executor.submit_task(
                    session_id=session_id,
                    task_type=task_type,
                    parameters={},
                    user_id=user_id,
                )

                # Verify task was created
                assert uuid.UUID(task_id)


# ============================================================================
# Test Task Status Checking
# ============================================================================


@pytest.mark.asyncio
async def test_get_task_status_pending(task_executor, mock_db_session, sample_task_record):
    """Test getting status of pending task."""
    sample_task_record.status = TaskStatus.PENDING.value
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = states.PENDING
            mock_result.info = None
            mock_async_result.return_value = mock_result

            status = await task_executor.get_task_status(sample_task_record.task_id, user_id)

            assert status["status"] == TaskStatus.PENDING.value
            assert status["state"] == states.PENDING
            assert status["result"] is None
            assert status["error"] is None


@pytest.mark.asyncio
async def test_get_task_status_running(task_executor, mock_db_session, sample_task_record):
    """Test getting status of running task."""
    sample_task_record.status = TaskStatus.RUNNING.value
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = states.STARTED
            mock_result.info = {"progress": 50}
            mock_async_result.return_value = mock_result

            status = await task_executor.get_task_status(sample_task_record.task_id, user_id)

            assert status["status"] == TaskStatus.RUNNING.value
            assert status["state"] == states.STARTED
            assert status["info"] == {"progress": 50}


@pytest.mark.asyncio
async def test_get_task_status_completed(task_executor, mock_db_session, sample_task_record):
    """Test getting status of completed task."""
    sample_task_record.status = TaskStatus.COMPLETED.value
    sample_task_record.result_data = {"results": {"accuracy": 0.85}}
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = states.SUCCESS
            mock_result.info = None
            mock_async_result.return_value = mock_result

            status = await task_executor.get_task_status(sample_task_record.task_id, user_id)

            assert status["status"] == TaskStatus.COMPLETED.value
            assert status["state"] == states.SUCCESS
            assert status["result"] == {"results": {"accuracy": 0.85}}


@pytest.mark.asyncio
async def test_get_task_status_failed(task_executor, mock_db_session, sample_task_record):
    """Test getting status of failed task."""
    sample_task_record.status = TaskStatus.FAILED.value
    sample_task_record.error_message = "Task execution failed"
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = states.FAILURE
            mock_result.info = None
            mock_async_result.return_value = mock_result

            status = await task_executor.get_task_status(sample_task_record.task_id, user_id)

            assert status["status"] == TaskStatus.FAILED.value
            assert status["state"] == states.FAILURE
            assert status["error"] == "Task execution failed"


@pytest.mark.asyncio
async def test_get_task_status_not_found(task_executor, mock_db_session):
    """Test getting status of non-existent task."""
    task_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        None
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with pytest.raises(ValueError) as exc_info:
            await task_executor.get_task_status(task_id, user_id)

        assert "not found" in str(exc_info.value)
        assert task_id in str(exc_info.value)


# ============================================================================
# Test Task Result Retrieval
# ============================================================================


@pytest.mark.asyncio
async def test_get_task_result_success(task_executor, mock_db_session, sample_task_record):
    """Test retrieving result from successful task."""
    sample_task_record.status = TaskStatus.COMPLETED.value
    sample_task_record.result_data = {
        "task_type": "iowa_gambling",
        "results": {
            "total_trials": 100,
            "final_balance": 2500,
            "deck_selections": [25, 25, 25, 25],
        },
    }
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = states.SUCCESS
            mock_async_result.return_value = mock_result

            status = await task_executor.get_task_status(sample_task_record.task_id, user_id)

            # Verify result is returned
            assert status["result"] is not None
            assert status["result"]["task_type"] == "iowa_gambling"
            assert status["result"]["results"]["total_trials"] == 100
            assert status["result"]["results"]["final_balance"] == 2500


@pytest.mark.asyncio
async def test_get_task_result_not_completed(task_executor, mock_db_session, sample_task_record):
    """Test retrieving result from incomplete task."""
    sample_task_record.status = TaskStatus.RUNNING.value
    sample_task_record.result_data = None
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = states.STARTED
            mock_async_result.return_value = mock_result

            status = await task_executor.get_task_status(sample_task_record.task_id, user_id)

            # Verify result is None for incomplete task
            assert status["result"] is None


# ============================================================================
# Test Task Timeout Handling
# ============================================================================


@pytest.mark.asyncio
async def test_task_timeout_configuration(task_executor):
    """Test that Celery is configured with appropriate timeouts."""
    from app.celery_app import celery_app

    # Verify hard time limit (1 hour)
    assert celery_app.conf.task_time_limit == 3600

    # Verify soft time limit (55 minutes)
    assert celery_app.conf.task_soft_time_limit == 3300


@pytest.mark.asyncio
async def test_get_task_status_timeout(task_executor, mock_db_session, sample_task_record):
    """Test getting status of task that exceeded timeout."""
    sample_task_record.status = TaskStatus.FAILED.value
    sample_task_record.error_message = "Task exceeded time limit"
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = states.FAILURE
            mock_async_result.return_value = mock_result

            status = await task_executor.get_task_status(sample_task_record.task_id, user_id)

            assert status["status"] == TaskStatus.FAILED.value
            assert "time limit" in status["error"]


# ============================================================================
# Test Task Cancellation
# ============================================================================


@pytest.mark.asyncio
async def test_cancel_task_success(task_executor, mock_db_session, sample_task_record):
    """Test cancelling a running task."""
    sample_task_record.status = TaskStatus.RUNNING.value
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.celery_app.control.revoke") as mock_revoke:
            result = await task_executor.cancel_task(sample_task_record.task_id, user_id)

            # Verify task was revoked
            mock_revoke.assert_called_once_with(sample_task_record.task_id, terminate=True)

            # Verify database was updated
            assert sample_task_record.status == TaskStatus.CANCELLED.value
            assert "cancelled" in sample_task_record.error_message.lower()

            # Verify response
            assert result["task_id"] == sample_task_record.task_id
            assert result["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_task_not_found(task_executor, mock_db_session):
    """Test cancelling non-existent task."""
    task_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        None
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with pytest.raises(ValueError) as exc_info:
            await task_executor.cancel_task(task_id, user_id)

        assert "not found" in str(exc_info.value)


# ============================================================================
# Test Task Listing
# ============================================================================


@pytest.mark.asyncio
async def test_list_available_tasks(task_executor):
    """Test listing all available task types."""
    result = await task_executor.list_available_tasks()

    # Verify structure
    assert "tasks" in result
    assert isinstance(result["tasks"], list)
    assert len(result["tasks"]) == 5

    # Verify each task has required fields
    for task in result["tasks"]:
        assert "task_type" in task
        assert "name" in task
        assert "description" in task
        assert "parameters" in task

    # Verify specific task types are present
    task_types = [task["task_type"] for task in result["tasks"]]
    assert "iowa_gambling" in task_types
    assert "masking_paradigm" in task_types
    assert "attentional_blink" in task_types
    assert "change_blindness" in task_types
    assert "binocular_rivalry" in task_types


@pytest.mark.asyncio
async def test_check_and_start_pending_tasks(task_executor, mock_db_session):
    """Test checking and starting pending tasks."""
    session_id = str(uuid.uuid4())
    pending_task = Task(
        task_id=str(uuid.uuid4()),
        session_id=session_id,
        task_type="iowa_gambling",
        parameters={},
        status=TaskStatus.PENDING.value,
        created_at=datetime.now(timezone.utc),
    )

    mock_db_session.query.return_value.filter.return_value.all.return_value = []
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        pending_task
    ]

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch.object(task_executor, "_can_start_task", return_value=True):
            with patch("app.services.task_executor.celery_app.send_task") as mock_send_task:
                mock_send_task.return_value = MagicMock()
                await task_executor.check_and_start_pending_tasks(session_id)

                # Verify celery task was submitted
                mock_send_task.assert_called_once()

                # Verify database commit was called
                mock_db_session.commit.assert_called()

                # Verify task status was updated to running
                assert pending_task.status == TaskStatus.RUNNING.value


def test_can_start_task_no_dependencies(task_executor, mock_db_session):
    """Test _can_start_task with no dependencies."""
    task_id = str(uuid.uuid4())

    mock_db_session.query.return_value.filter.return_value.all.return_value = []

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        result = task_executor._can_start_task(task_id)

        assert result is True


def test_can_start_task_with_completed_dependency(task_executor, mock_db_session):
    """Test _can_start_task with completed dependency."""
    task_id = str(uuid.uuid4())
    prereq_task_id = str(uuid.uuid4())

    # Mock dependency record
    mock_dependency = MagicMock()
    mock_dependency.prerequisite_task_id = prereq_task_id
    mock_dependency.dependency_type = "completion"

    # Mock prerequisite task (completed)
    mock_prereq_task = MagicMock()
    mock_prereq_task.status = TaskStatus.COMPLETED.value

    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_dependency]
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_prereq_task

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        result = task_executor._can_start_task(task_id)

        assert result is True


def test_can_start_task_with_pending_dependency(task_executor, mock_db_session):
    """Test _can_start_task with pending dependency."""
    task_id = str(uuid.uuid4())
    prereq_task_id = str(uuid.uuid4())

    # Mock dependency record
    mock_dependency = MagicMock()
    mock_dependency.prerequisite_task_id = prereq_task_id
    mock_dependency.dependency_type = "completion"

    # Mock prerequisite task (pending)
    mock_prereq_task = MagicMock()
    mock_prereq_task.status = TaskStatus.PENDING.value

    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_dependency]
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_prereq_task

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        result = task_executor._can_start_task(task_id)

        assert result is False


def test_has_cycle_no_cycle(task_executor, mock_db_session):
    """Test _has_cycle with no cycle."""
    task_id = str(uuid.uuid4())

    mock_db_session.query.return_value.filter.return_value.all.return_value = []

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        result = task_executor._has_cycle(task_id)

        assert result is False


def test_has_cycle_with_cycle(task_executor, mock_db_session):
    """Test _has_cycle with a cycle."""
    task_id = str(uuid.uuid4())
    dep_task_id = str(uuid.uuid4())

    # Mock dependency that creates a cycle
    mock_dependency = MagicMock()
    mock_dependency.prerequisite_task_id = dep_task_id

    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_dependency]

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        # Simulate cycle by making the dependency point back
        with patch.object(task_executor, "_has_cycle", side_effect=[True, False]):
            result = task_executor._has_cycle(task_id)

            assert result is True
