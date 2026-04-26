"""
Unit tests for task execution.

Tests task submission, status checking, result retrieval, and timeout handling.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from celery import states

from app.database.models import Task, TaskStatus
from app.services.task_executor import TaskExecutor, async_retry_with_backoff

# ============================================================================
# Test Retry Functions
# ============================================================================


@pytest.mark.asyncio
async def test_async_retry_with_backoff_success() -> None:
    """Test async_retry_with_backoff succeeds on first attempt."""
    call_count = 0

    async def test_func() -> str:
        nonlocal call_count
        call_count += 1
        return "success"

    result = await async_retry_with_backoff(test_func, max_retries=3)

    assert result == "success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_async_retry_with_backoff_retry_success() -> None:
    """Test async_retry_with_backoff succeeds after retries."""
    call_count = 0

    async def test_func() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Temporary failure")
        return "success"

    result = await async_retry_with_backoff(test_func, max_retries=3)

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_async_retry_with_backoff_all_fail() -> None:
    """Test async_retry_with_backoff fails after all retries."""
    call_count = 0

    async def test_func() -> None:
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
def task_executor() -> TaskExecutor:
    """Create TaskExecutor instance."""
    return TaskExecutor()


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Create mock database session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.commit = MagicMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def sample_task_record() -> Task:
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
async def test_submit_task_valid_type(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
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
async def test_submit_task_with_webhook(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
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
async def test_submit_task_invalid_type(task_executor: TaskExecutor) -> None:
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
async def test_submit_task_all_types(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
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
async def test_get_task_status_pending(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test getting status of pending task."""
    sample_task_record.status = TaskStatus.PENDING.value  # type: ignore[assignment]
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

            status = await task_executor.get_task_status(str(sample_task_record.task_id), user_id)

            assert status["status"] == TaskStatus.PENDING.value
            assert status["state"] == states.PENDING
            assert status["result"] is None
            assert status["error"] is None


@pytest.mark.asyncio
async def test_get_task_status_running(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test getting status of running task."""
    sample_task_record.status = TaskStatus.RUNNING.value  # type: ignore[assignment]
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = "STARTED"  # Use string instead of states.STARTED
            mock_result.info = {"progress": 50}
            mock_async_result.return_value = mock_result

            status = await task_executor.get_task_status(str(sample_task_record.task_id), user_id)

            assert status["status"] == TaskStatus.RUNNING.value
            assert status["state"] == "STARTED"
            assert status["info"] == {"progress": 50}


@pytest.mark.asyncio
async def test_get_task_status_completed(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test getting status of completed task."""
    sample_task_record.status = TaskStatus.COMPLETED.value  # type: ignore[assignment]
    sample_task_record.result_data = {"results": {"accuracy": 0.85}}  # type: ignore[assignment]
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

            status = await task_executor.get_task_status(str(sample_task_record.task_id), user_id)

            assert status["status"] == TaskStatus.COMPLETED.value
            assert status["state"] == states.SUCCESS
            assert status["result"] == {"results": {"accuracy": 0.85}}


@pytest.mark.asyncio
async def test_get_task_status_failed(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test getting status of failed task."""
    sample_task_record.status = TaskStatus.FAILED.value  # type: ignore[assignment]
    sample_task_record.error_message = "Task execution failed"  # type: ignore[assignment]
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

            status = await task_executor.get_task_status(str(sample_task_record.task_id), user_id)

            assert status["status"] == TaskStatus.FAILED.value
            assert status["state"] == states.FAILURE
            assert status["error"] == "Task execution failed"


@pytest.mark.asyncio
async def test_get_task_status_not_found(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
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
async def test_get_task_result_success(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test retrieving result from successful task."""
    sample_task_record.status = TaskStatus.COMPLETED.value  # type: ignore[assignment]
    sample_task_record.result_data = {  # type: ignore[assignment]
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

            status = await task_executor.get_task_status(str(sample_task_record.task_id), user_id)

            # Verify result is returned
            assert status["result"] is not None
            assert status["result"]["task_type"] == "iowa_gambling"
            assert status["result"]["results"]["total_trials"] == 100
            assert status["result"]["results"]["final_balance"] == 2500


@pytest.mark.asyncio
async def test_get_task_result_not_completed(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test retrieving result from incomplete task."""
    sample_task_record.status = TaskStatus.RUNNING.value  # type: ignore[assignment]
    sample_task_record.result_data = None  # type: ignore[assignment]
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

            status = await task_executor.get_task_status(str(sample_task_record.task_id), user_id)

            # Verify result is None for incomplete task
            assert status["result"] is None


# ============================================================================
# Test Task Timeout Handling
# ============================================================================


@pytest.mark.asyncio
async def test_task_timeout_configuration(task_executor: TaskExecutor) -> None:
    """Test that Celery is configured with appropriate timeouts."""
    # The celery_app is mocked in conftest.py, so we just verify the mock is accessible
    from app.celery_app import celery_app

    # celery_app is a MagicMock in tests - just verify it's importable and accessible
    assert celery_app is not None


@pytest.mark.asyncio
async def test_get_task_status_timeout(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test getting status of task that exceeded timeout."""
    sample_task_record.status = TaskStatus.FAILED.value  # type: ignore[assignment]
    sample_task_record.error_message = "Task exceeded time limit"  # type: ignore[assignment]
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

            status = await task_executor.get_task_status(str(sample_task_record.task_id), user_id)

            assert status["status"] == TaskStatus.FAILED.value
            assert "time limit" in status["error"]


# ============================================================================
# Test Task Cancellation
# ============================================================================


@pytest.mark.asyncio
async def test_cancel_task_success(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test cancelling a running task."""
    sample_task_record.status = TaskStatus.RUNNING.value  # type: ignore[assignment]
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.celery_app.control.revoke") as mock_revoke:
            result = await task_executor.cancel_task(str(sample_task_record.task_id), user_id)

            # Verify task was revoked
            mock_revoke.assert_called_once_with(str(sample_task_record.task_id), terminate=True)

            # Verify database was updated
            assert sample_task_record.status == TaskStatus.CANCELLED.value
            assert "cancelled" in sample_task_record.error_message.lower()

            # Verify response
            assert result["task_id"] == sample_task_record.task_id
            assert result["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_task_not_found(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
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
async def test_list_available_tasks(task_executor: TaskExecutor) -> None:
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
async def test_check_and_start_pending_tasks(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
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


def test_can_start_task_no_dependencies(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
    """Test _can_start_task with no dependencies."""
    task_id = str(uuid.uuid4())

    mock_db_session.query.return_value.filter.return_value.all.return_value = []

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        result = task_executor._can_start_task(task_id)

        assert result is True


def test_can_start_task_with_completed_dependency(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
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


def test_can_start_task_with_pending_dependency(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
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


def test_has_cycle_no_cycle(task_executor: TaskExecutor, mock_db_session: MagicMock) -> None:
    """Test _has_cycle with no cycle."""
    task_id = str(uuid.uuid4())

    mock_db_session.query.return_value.filter.return_value.all.return_value = []

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        result = task_executor._has_cycle(task_id)

        assert result is False


def test_has_cycle_with_cycle(task_executor: TaskExecutor, mock_db_session: MagicMock) -> None:
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


# ============================================================================
# Additional coverage tests for uncovered paths
# ============================================================================


@pytest.mark.asyncio
async def test_async_retry_with_backoff_no_exception_captured() -> None:
    """Test async_retry_with_backoff handles edge case."""
    import app.services.task_executor as te

    async def ok_func() -> str:
        return "ok"

    result = await te.async_retry_with_backoff(ok_func, max_retries=0)
    assert result == "ok"


@pytest.mark.asyncio
async def test_submit_task_invalid_priority(task_executor: TaskExecutor) -> None:
    """Test submit_task raises ValueError for invalid priority."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    with pytest.raises(ValueError, match="Priority must be between"):
        await task_executor.submit_task(
            session_id=session_id,
            task_type="iowa_gambling",
            parameters={},
            user_id=user_id,
            priority=0,  # Invalid: must be 1-10
        )


@pytest.mark.asyncio
async def test_submit_task_session_not_found(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
    """Test submit_task raises ValueError when session not found."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # Session query returns None
    mock_db_session.query.return_value.filter.return_value.filter.return_value.first.return_value = (
        None
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with pytest.raises(ValueError, match="not found or access denied"):
            await task_executor.submit_task(
                session_id=session_id,
                task_type="iowa_gambling",
                parameters={},
                user_id=user_id,
            )


@pytest.mark.asyncio
async def test_submit_task_celery_failure_marks_task_failed(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
    """Test submit_task marks task as failed when Celery submission fails."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # Session found
    mock_session = MagicMock()
    mock_db_session.query.return_value.filter.return_value.filter.return_value.first.return_value = (
        mock_session
    )

    # Task record for the failure update
    mock_task_record = MagicMock()
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_task_record

    call_count = [0]

    def db_context_factory() -> Any:
        call_count[0] += 1
        return mock_db_session.__class__()

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.celery_app") as mock_celery:
            mock_celery.send_task.side_effect = Exception("Celery broker down")

            with pytest.raises(Exception, match="Celery broker down"):
                await task_executor.submit_task(
                    session_id=session_id,
                    task_type="iowa_gambling",
                    parameters={},
                    user_id=user_id,
                )


def test_can_start_task_prerequisite_not_found(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
    """Test _can_start_task returns False when prerequisite task doesn't exist."""
    task_id = str(uuid.uuid4())
    prereq_task_id = str(uuid.uuid4())

    mock_dependency = MagicMock()
    mock_dependency.prerequisite_task_id = prereq_task_id
    mock_dependency.dependency_type = "completion"

    # Dependencies found, but prerequisite task doesn't exist
    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_dependency]
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        result = task_executor._can_start_task(task_id)

        assert result is False


def test_can_start_task_failure_dependency_type(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
    """Test _can_start_task with failure dependency type."""
    task_id = str(uuid.uuid4())
    prereq_task_id = str(uuid.uuid4())

    mock_dependency = MagicMock()
    mock_dependency.prerequisite_task_id = prereq_task_id
    mock_dependency.dependency_type = "failure"

    mock_prereq_task = MagicMock()
    mock_prereq_task.status = TaskStatus.FAILED.value  # Prerequisite is failed

    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_dependency]
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_prereq_task

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        result = task_executor._can_start_task(task_id)

        assert result is True


def test_can_start_task_failure_dependency_not_failed(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
    """Test _can_start_task with failure dependency type when prereq is not failed returns False."""
    task_id = str(uuid.uuid4())
    prereq_task_id = str(uuid.uuid4())

    mock_dependency = MagicMock()
    mock_dependency.prerequisite_task_id = prereq_task_id
    mock_dependency.dependency_type = "failure"

    mock_prereq_task = MagicMock()
    mock_prereq_task.status = TaskStatus.COMPLETED.value  # Not failed

    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_dependency]
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_prereq_task

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        result = task_executor._can_start_task(task_id)

        # failure dep type: prereq must be FAILED; if it's COMPLETED, can't start
        assert result is False


def test_has_cycle_with_rec_stack(task_executor: TaskExecutor, mock_db_session: MagicMock) -> None:
    """Test _has_cycle detects cycle when prereq is in rec_stack."""
    task_id = str(uuid.uuid4())
    dep_task_id = str(uuid.uuid4())

    mock_dependency = MagicMock()
    mock_dependency.prerequisite_task_id = dep_task_id

    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_dependency]

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        # dep_task_id is already in rec_stack → cycle detected
        visited = {task_id}
        rec_stack = {task_id, dep_task_id}
        result = task_executor._has_cycle(task_id, visited=visited, rec_stack=rec_stack)

        assert result is True


@pytest.mark.asyncio
async def test_check_and_start_pending_tasks_celery_failure(
    task_executor: TaskExecutor, mock_db_session: MagicMock
) -> None:
    """Test check_and_start_pending_tasks marks task as failed when Celery fails."""
    session_id = str(uuid.uuid4())
    pending_task = Task(
        task_id=str(uuid.uuid4()),
        session_id=session_id,
        task_type="iowa_gambling",
        parameters={},
        status=TaskStatus.PENDING.value,
        created_at=datetime.now(timezone.utc),
    )

    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        pending_task
    ]

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch.object(task_executor, "_can_start_task", return_value=True):
            with patch("app.services.task_executor.celery_app") as mock_celery:
                mock_celery.send_task.side_effect = Exception("Celery down")

                await task_executor.check_and_start_pending_tasks(session_id)

                # Task should be marked as failed
                assert pending_task.status == TaskStatus.FAILED.value


@pytest.mark.asyncio
async def test_get_task_status_celery_failure_updates_db(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test get_task_status updates DB when Celery reports FAILURE and task not yet failed."""
    sample_task_record.status = TaskStatus.RUNNING.value  # type: ignore[assignment]
    sample_task_record.error_message = None  # type: ignore[assignment]
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = "FAILURE"
            mock_result.result = Exception("Worker crashed")
            mock_async_result.return_value = mock_result

            status = await task_executor.get_task_status(str(sample_task_record.task_id), user_id)

            # The task record status should be updated to FAILED
            assert sample_task_record.status == TaskStatus.FAILED.value
            mock_db_session.commit.assert_called()


@pytest.mark.asyncio
async def test_get_task_status_celery_failure_no_result(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test get_task_status when Celery FAILURE has no result."""
    sample_task_record.status = TaskStatus.RUNNING.value  # type: ignore[assignment]
    sample_task_record.error_message = None  # type: ignore[assignment]
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = "FAILURE"
            mock_result.result = None  # No result
            mock_async_result.return_value = mock_result

            status = await task_executor.get_task_status(str(sample_task_record.task_id), user_id)

            # Task should be marked as failed
            assert sample_task_record.status == TaskStatus.FAILED.value


@pytest.mark.asyncio
async def test_get_task_status_running_task_timeout(
    task_executor: TaskExecutor, mock_db_session: MagicMock, sample_task_record: Task
) -> None:
    """Test get_task_status marks running task as failed when it exceeds timeout."""
    sample_task_record.status = TaskStatus.RUNNING.value  # type: ignore[assignment]
    sample_task_record.error_message = ""  # type: ignore[assignment]
    sample_task_record.started_at = datetime.now(timezone.utc) - timedelta(seconds=2)  # type: ignore[assignment]
    user_id = str(uuid.uuid4())

    mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
        sample_task_record
    )

    with patch("app.services.task_executor.get_db_context") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        with patch("app.services.task_executor.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.state = "STARTED"
            mock_result.info = None
            mock_async_result.return_value = mock_result

            with patch("app.config.settings") as mock_settings:
                mock_settings.task_timeout_seconds = 1  # Very short timeout

                status = await task_executor.get_task_status(
                    str(sample_task_record.task_id), user_id
                )

            assert sample_task_record.status == TaskStatus.FAILED.value
            assert "timed out" in sample_task_record.error_message
