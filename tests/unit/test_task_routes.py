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
            task_type="attentional_blink",
            parameters={"num_trials": 100},
            priority=5,
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
        assert response.task_type == "attentional_blink"
        assert response.status == "pending"
        assert response.status_url == f"/v1/tasks/{task_id}"

    @pytest.mark.asyncio
    async def test_execute_task_invalid_type(self, mock_task_executor, mock_current_user):
        """Test task submission with invalid task type."""
        session_id = str(uuid.uuid4())

        from app.models.schemas import TaskSubmitRequest

        request = TaskSubmitRequest(
            task_type="invalid_task", parameters={}, priority=5, webhook_url=None
        )

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

        request = TaskSubmitRequest(
            task_type="attentional_blink", parameters={}, priority=5, webhook_url=None
        )

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

        # Ensure the mock returns the expected dict
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
        assert response.result["accuracy"] == 0.85  # type: ignore[union-attr]

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


# ---------------------------------------------------------------------------
# Tests merged from test_tasks_routes.py
# ---------------------------------------------------------------------------
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import status


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.query = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def mock_task_model():
    """Mock task model."""
    task = MagicMock()
    task.task_id = "task123"
    task.session_id = "session123"
    task.status = "completed"
    task.result_data = {"result": "success"}
    task.created_at = datetime.now(timezone.utc)
    return task


@pytest.fixture
def mock_session_model():
    """Mock session model."""
    session = MagicMock()
    session.session_id = "session123"
    session.user_id = "user123"
    return session


class TestGetTaskResult:
    """Tests for get_task_result endpoint."""

    @pytest.mark.asyncio
    async def test_get_task_result_success(
        self, mock_db_session, mock_current_user, mock_task_model, mock_session_model
    ):
        """Test successful task result retrieval."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )

        from app.routes.tasks import get_task_result

        result = await get_task_result("task123", mock_db_session, mock_current_user)

        assert result.task_id == "task123"
        assert result.result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_get_task_result_not_found(self, mock_db_session, mock_current_user):
        """Test get_task_result when task not found."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_task_result_not_completed(
        self, mock_db_session, mock_current_user, mock_task_model
    ):
        """Test get_task_result when task not completed."""
        mock_task_model.status = "running"
        mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_get_task_result_no_data(
        self, mock_db_session, mock_current_user, mock_task_model
    ):
        """Test get_task_result when no result data."""
        mock_task_model.status = "completed"
        mock_task_model.result_data = None
        mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_task_result_error(self, mock_db_session, mock_current_user):
        """Test get_task_result with internal error."""
        mock_db_session.query.side_effect = Exception("Database error")

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db_session.rollback.assert_called_once()


class TestCancelTaskInSession:
    """Tests for cancel_task_in_session endpoint."""

    @pytest.mark.asyncio
    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_in_session_success(
        self,
        mock_get_executor,
        mock_db_session,
        mock_task_executor,
        mock_current_user,
        mock_session_model,
        mock_task_model,
    ):
        """Test successful task cancellation in session."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.cancel_task.return_value = {"status": "cancelled"}

        mock_db_session.query.return_value.filter.return_value.filter.return_value.first.side_effect = [
            mock_session_model,
            mock_task_model,
        ]

        from app.routes.tasks import cancel_task_in_session

        result = await cancel_task_in_session(
            "session123", "task123", mock_db_session, mock_task_executor, mock_current_user
        )

        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_in_session_not_found(
        self, mock_get_executor, mock_db_session, mock_task_executor, mock_current_user
    ):
        """Test cancel_task_in_session when session not found."""
        mock_get_executor.return_value = mock_task_executor
        mock_db_session.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", mock_db_session, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_in_session_task_not_found(
        self,
        mock_get_executor,
        mock_db_session,
        mock_task_executor,
        mock_current_user,
        mock_session_model,
    ):
        """Test cancel_task_in_session when task not found."""
        mock_get_executor.return_value = mock_task_executor
        mock_db_session.query.return_value.filter.return_value.filter.return_value.first.side_effect = [
            mock_session_model,
            None,
        ]

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", mock_db_session, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_in_session_error(
        self,
        mock_get_executor,
        mock_db_session,
        mock_task_executor,
        mock_current_user,
        mock_session_model,
        mock_task_model,
    ):
        """Test cancel_task_in_session with internal error."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.cancel_task.side_effect = Exception("Service error")
        mock_db_session.query.return_value.filter.return_value.filter.return_value.first.side_effect = [
            mock_session_model,
            mock_task_model,
        ]

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", mock_db_session, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestCreateTaskDependency:
    """Tests for create_task_dependency endpoint."""

    @pytest.mark.asyncio
    async def test_create_task_dependency_dependent_not_found(
        self, mock_db_session, mock_current_user
    ):
        """Test create_task_dependency when dependent task not found."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = (
            None
        )

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_task_dependency_prerequisite_not_found(
        self, mock_db_session, mock_current_user, mock_task_model
    ):
        """Test create_task_dependency when prerequisite task not found."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.side_effect = [
            mock_task_model,
            None,
        ]

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_task_dependency_different_sessions(
        self, mock_db_session, mock_current_user, mock_task_model
    ):
        """Test create_task_dependency when tasks in different sessions."""
        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = "task456"
        mock_prereq_task.session_id = "session456"  # Different session

        mock_db_session.query.return_value.join.return_value.filter.return_value.first.side_effect = [
            mock_task_model,
            mock_prereq_task,
        ]

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_task_dependency_self_dependency(
        self, mock_db_session, mock_current_user, mock_task_model
    ):
        """Test create_task_dependency with self dependency."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.side_effect = [
            mock_task_model,
            mock_task_model,
        ]

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task123", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_task_dependency_already_exists(
        self, mock_db_session, mock_current_user, mock_task_model
    ):
        """Test create_task_dependency when dependency already exists."""
        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = "task456"
        mock_prereq_task.session_id = "session123"

        mock_db_session.query.return_value.join.return_value.filter.return_value.first.side_effect = [
            mock_task_model,
            mock_prereq_task,
        ]
        mock_db_session.query.return_value.filter.return_value.first.return_value = MagicMock()

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_create_task_dependency_error(
        self, mock_db_session, mock_current_user, mock_task_model
    ):
        """Test create_task_dependency with internal error."""
        mock_db_session.query.side_effect = Exception("Database error")

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db_session.rollback.assert_called_once()


class TestListTaskDependencies:
    """Tests for list_task_dependencies endpoint."""

    @pytest.mark.asyncio
    async def test_list_task_dependencies_not_found(self, mock_db_session, mock_current_user):
        """Test list_task_dependencies when task not found."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = (
            None
        )

        from app.routes.tasks import list_task_dependencies

        with pytest.raises(HTTPException) as exc_info:
            await list_task_dependencies("task123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_task_dependencies_error(self, mock_db_session, mock_current_user):
        """Test list_task_dependencies with internal error."""
        mock_db_session.query.side_effect = Exception("Database error")

        from app.routes.tasks import list_task_dependencies

        with pytest.raises(HTTPException) as exc_info:
            await list_task_dependencies("task123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestDeleteTaskDependency:
    """Tests for delete_task_dependency endpoint."""

    @pytest.mark.asyncio
    async def test_delete_task_dependency_task_not_found(self, mock_db_session, mock_current_user):
        """Test delete_task_dependency when task not found."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = (
            None
        )

        from app.routes.tasks import delete_task_dependency

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task123", 1, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_task_dependency_not_found(
        self, mock_db_session, mock_current_user, mock_task_model
    ):
        """Test delete_task_dependency when dependency not found."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        from app.routes.tasks import delete_task_dependency

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task123", 1, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_task_dependency_error(self, mock_db_session, mock_current_user):
        """Test delete_task_dependency with internal error."""
        mock_db_session.query.side_effect = Exception("Database error")

        from app.routes.tasks import delete_task_dependency

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task123", 1, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db_session.rollback.assert_called_once()
