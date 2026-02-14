"""
Unit tests for task routes.

Tests task submission, status checking, listing, and cancellation endpoints
by calling route functions directly with mocked dependencies.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

"""
Unit tests for task routes.

Tests task submission, status checking, listing, and cancellation endpoints
by calling route functions directly with mocked dependencies.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


@pytest.fixture
def mock_task_executor():
    """Create mock TaskExecutor."""
    executor = MagicMock()
    executor.list_available_tasks = AsyncMock(
        return_value={
            "tasks": [
                {
                    "task_type": "iowa_gambling",
                    "name": "Iowa Gambling Task",
                    "description": "Decision making task",
                    "parameters": {},
                }
            ]
        }
    )
    executor.submit_task = AsyncMock(return_value=str(uuid.uuid4()))
    executor.get_task_status = AsyncMock(
        return_value={
            "status": "completed",
            "state": "SUCCESS",
            "result": {"accuracy": 0.85},
            "error": None,
            "info": None,
        }
    )
    executor.cancel_task = AsyncMock(
        return_value={"task_id": str(uuid.uuid4()), "status": "cancelled"}
    )
    return executor


@pytest.fixture
def mock_current_user():
    """Create mock current user."""
    user = MagicMock()
    user.id = str(uuid.uuid4())
    user.username = "test_user"
    return user


class TestTaskRoutes:
    """Test task management route functions."""

    @pytest.mark.asyncio
    async def test_list_tasks_success(self, mock_task_executor):
        """Test listing available tasks successfully."""
        from app.routes.tasks import list_tasks

        response = await list_tasks(executor=mock_task_executor, current_user=MagicMock())

        assert response.tasks is not None
        assert len(response.tasks) == 1
        assert response.tasks[0]["task_type"] == "iowa_gambling"

    @pytest.mark.asyncio
    async def test_list_tasks_executor_error(self, mock_task_executor):
        """Test listing tasks when executor fails."""
        mock_task_executor.list_available_tasks.side_effect = Exception("Executor error")

        from app.routes.tasks import list_tasks

        with pytest.raises(HTTPException) as exc_info:
            await list_tasks(executor=mock_task_executor, current_user=MagicMock())

        assert exc_info.value.status_code == 500
        assert "Failed to list tasks" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_execute_task_success(self, mock_task_executor, mock_current_user):
        """Test successful task submission."""
        session_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        mock_task_executor.submit_task.return_value = task_id

        from app.models.schemas import TaskSubmitRequest

        request = TaskSubmitRequest(
            task_type="iowa_gambling",
            parameters={"num_trials": 100},
            webhook_url="https://example.com/webhook",
        )

        from app.routes.tasks import execute_task

        response = await execute_task(
            session_id=session_id,
            request=request,
            executor=mock_task_executor,
            current_user=mock_current_user,
        )

        assert response.task_id == task_id
        assert response.session_id == session_id
        assert response.task_type == "iowa_gambling"
        assert response.status == "pending"
        assert response.status_url == f"/v1/tasks/{task_id}"

    @pytest.mark.asyncio
    async def test_execute_task_invalid_type(self, mock_task_executor, mock_current_user):
        """Test task submission with invalid task type."""
        session_id = str(uuid.uuid4())

        from app.models.schemas import TaskSubmitRequest

        request = TaskSubmitRequest(task_type="invalid_task", parameters={})

        mock_task_executor.submit_task.side_effect = ValueError("Invalid task type")

        from app.routes.tasks import execute_task

        with pytest.raises(HTTPException) as exc_info:
            await execute_task(
                session_id=session_id,
                request=request,
                executor=mock_task_executor,
                current_user=mock_current_user,
            )

        assert exc_info.value.status_code == 400
        assert "Invalid task type" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_execute_task_executor_error(self, mock_task_executor, mock_current_user):
        """Test task submission when executor fails."""
        session_id = str(uuid.uuid4())

        from app.models.schemas import TaskSubmitRequest

        request = TaskSubmitRequest(task_type="iowa_gambling", parameters={})

        mock_task_executor.submit_task.side_effect = Exception("Executor error")

        from app.routes.tasks import execute_task

        with pytest.raises(HTTPException) as exc_info:
            await execute_task(
                session_id=session_id,
                request=request,
                executor=mock_task_executor,
                current_user=mock_current_user,
            )

        assert exc_info.value.status_code == 500
        assert "Failed to submit task" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_task_status_success(self, mock_task_executor, mock_current_user):
        """Test getting task status successfully."""
        task_id = str(uuid.uuid4())

        mock_task_executor.get_task_status.return_value = {
            "status": "completed",
            "state": "SUCCESS",
            "result": {"accuracy": 0.85},
            "error": None,
            "info": None,
        }

        from app.routes.tasks import get_task_status

        response = await get_task_status(
            task_id=task_id, executor=mock_task_executor, current_user=mock_current_user
        )

        assert response.task_id == task_id
        assert response.status == "completed"
        assert response.state == "SUCCESS"
        assert response.result["accuracy"] == 0.85

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, mock_task_executor, mock_current_user):
        """Test getting status of non-existent task."""
        task_id = str(uuid.uuid4())

        mock_task_executor.get_task_status.side_effect = ValueError("Task not found")

        from app.routes.tasks import get_task_status

        with pytest.raises(HTTPException) as exc_info:
            await get_task_status(
                task_id=task_id, executor=mock_task_executor, current_user=mock_current_user
            )

        assert exc_info.value.status_code == 404
        assert f"Task {task_id} not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_task_status_executor_error(self, mock_task_executor, mock_current_user):
        """Test getting task status when executor fails."""
        task_id = str(uuid.uuid4())

        mock_task_executor.get_task_status.side_effect = Exception("Executor error")

        from app.routes.tasks import get_task_status

        with pytest.raises(HTTPException) as exc_info:
            await get_task_status(
                task_id=task_id, executor=mock_task_executor, current_user=mock_current_user
            )

        assert exc_info.value.status_code == 500
        assert "Failed to get task status" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_cancel_task_success(self, mock_task_executor, mock_current_user):
        """Test successful task cancellation."""
        task_id = str(uuid.uuid4())

        mock_task_executor.get_task_status.return_value = {"status": "running"}
        mock_task_executor.cancel_task.return_value = {"task_id": task_id, "status": "cancelled"}

        from app.routes.tasks import cancel_task

        response = await cancel_task(
            task_id=task_id, executor=mock_task_executor, current_user=mock_current_user
        )

        assert response["task_id"] == task_id
        assert response["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, mock_task_executor, mock_current_user):
        """Test cancelling non-existent task."""
        task_id = str(uuid.uuid4())

        mock_task_executor.get_task_status.return_value = None

        from app.routes.tasks import cancel_task

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task(
                task_id=task_id, executor=mock_task_executor, current_user=mock_current_user
            )

        assert exc_info.value.status_code == 404
        assert f"Task {task_id} not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_cancel_task_executor_error(self, mock_task_executor, mock_current_user):
        """Test task cancellation when executor fails."""
        task_id = str(uuid.uuid4())

        mock_task_executor.get_task_status.return_value = {"status": "running"}
        mock_task_executor.cancel_task.side_effect = Exception("Executor error")

        from app.routes.tasks import cancel_task

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task(
                task_id=task_id, executor=mock_task_executor, current_user=mock_current_user
            )

        assert exc_info.value.status_code == 500
        assert "Failed to cancel task" in exc_info.value.detail

    def test_get_task_executor_initialized(self):
        """Test get_task_executor when initialized."""
        with patch("app.routes.tasks.TaskExecutor"):
            from app.routes.tasks import init_task_routes, get_task_executor

            init_task_routes()
            executor = get_task_executor()
            assert executor is not None

    def test_get_task_executor_not_initialized(self):
        """Test get_task_executor when not initialized."""
        from app.routes.tasks import get_task_executor

        # Reset the global executor
        import app.routes.tasks

        app.routes.tasks._task_executor = None

        with pytest.raises(HTTPException) as exc_info:
            get_task_executor()

        assert exc_info.value.status_code == 503
        assert "Task executor not initialized" in exc_info.value.detail
