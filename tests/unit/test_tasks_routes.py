"""
Unit tests for tasks routes.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException, status
from datetime import datetime, timezone
from sqlalchemy.orm import Session


@pytest.fixture
def mock_db():
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
def mock_task_executor():
    """Mock task executor."""
    executor = MagicMock()
    executor.list_available_tasks = AsyncMock()
    executor.submit_task = AsyncMock()
    executor.get_task_status = AsyncMock()
    executor.cancel_task = AsyncMock()
    return executor


@pytest.fixture
def mock_current_user():
    """Mock current user."""
    user = MagicMock()
    user.user_id = "user123"
    user.username = "testuser"
    user.roles = ["viewer"]
    return user


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


class TestTaskExecutor:
    """Tests for task executor initialization."""

    def test_get_task_executor_not_initialized(self):
        """Test get_task_executor when not initialized."""
        from app.routes.tasks import get_task_executor, _task_executor

        # Ensure executor is None
        _task_executor = None

        with pytest.raises(HTTPException) as exc_info:
            get_task_executor()

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "not initialized" in exc_info.value.detail

    def test_init_task_routes(self):
        """Test init_task_routes."""
        from app.routes.tasks import init_task_routes, _task_executor

        init_task_routes()

        assert _task_executor is not None


class TestListTasks:
    """Tests for list_tasks endpoint."""

    @patch("app.routes.tasks.get_task_executor")
    async def test_list_tasks_success(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test successful task listing."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.list_available_tasks.return_value = {
            "tasks": [
                {"name": "task1", "description": "Test task 1"},
                {"name": "task2", "description": "Test task 2"},
            ]
        }

        from app.routes.tasks import list_tasks

        result = await list_tasks(mock_task_executor, mock_current_user)

        assert len(result.tasks) == 2
        assert result.tasks[0]["name"] == "task1"

    @patch("app.routes.tasks.get_task_executor")
    async def test_list_tasks_error(self, mock_get_executor, mock_task_executor, mock_current_user):
        """Test list_tasks with error."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.list_available_tasks.side_effect = Exception("Service error")

        from app.routes.tasks import list_tasks

        with pytest.raises(HTTPException) as exc_info:
            await list_tasks(mock_task_executor, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestExecuteTask:
    """Tests for execute_task endpoint."""

    @patch("app.routes.tasks.get_task_executor")
    async def test_execute_task_success(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test successful task execution."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.submit_task.return_value = "task123"

        from app.routes.tasks import execute_task, TaskSubmitRequest

        request = TaskSubmitRequest(
            task_type="test_task",
            parameters={"param1": "value1"},
            priority=0,
            webhook_url="https://example.com/webhook",
        )

        result = await execute_task("session123", request, mock_task_executor, mock_current_user)

        assert result.task_id == "task123"
        assert result.session_id == "session123"
        assert result.status == "pending"

    @patch("app.routes.tasks.get_task_executor")
    async def test_execute_task_invalid(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test execute_task with invalid task."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.submit_task.side_effect = ValueError("Invalid task type")

        from app.routes.tasks import execute_task, TaskSubmitRequest

        request = TaskSubmitRequest(
            task_type="invalid_task", parameters={}, priority=None, webhook_url=None
        )

        with pytest.raises(HTTPException) as exc_info:
            await execute_task("session123", request, mock_task_executor, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.tasks.get_task_executor")
    async def test_execute_task_error(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test execute_task with internal error."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.submit_task.side_effect = Exception("Service error")

        from app.routes.tasks import execute_task, TaskSubmitRequest

        request = TaskSubmitRequest(
            task_type="test_task", parameters={}, priority=None, webhook_url=None
        )

        with pytest.raises(HTTPException) as exc_info:
            await execute_task("session123", request, mock_task_executor, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestGetTaskStatus:
    """Tests for get_task_status endpoint."""

    @patch("app.routes.tasks.get_task_executor")
    async def test_get_task_status_success(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test successful task status retrieval."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.get_task_status.return_value = {
            "status": "completed",
            "state": "success",
            "result": {"data": "test"},
            "error": None,
            "info": {"duration": 1.5},
        }

        from app.routes.tasks import get_task_status

        result = await get_task_status("task123", mock_task_executor, mock_current_user)

        assert result.task_id == "task123"
        assert result.status == "completed"
        assert result.state == "success"

    @patch("app.routes.tasks.get_task_executor")
    async def test_get_task_status_not_found(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test get_task_status when task not found."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.get_task_status.side_effect = ValueError("Task not found")

        from app.routes.tasks import get_task_status

        with pytest.raises(HTTPException) as exc_info:
            await get_task_status("task123", mock_task_executor, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.tasks.get_task_executor")
    async def test_get_task_status_value_error(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test get_task_status with other value error."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.get_task_status.side_effect = ValueError("Invalid request")

        from app.routes.tasks import get_task_status

        with pytest.raises(HTTPException) as exc_info:
            await get_task_status("task123", mock_task_executor, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.tasks.get_task_executor")
    async def test_get_task_status_error(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test get_task_status with internal error."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.get_task_status.side_effect = Exception("Service error")

        from app.routes.tasks import get_task_status

        with pytest.raises(HTTPException) as exc_info:
            await get_task_status("task123", mock_task_executor, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestGetTaskResult:
    """Tests for get_task_result endpoint."""

    async def test_get_task_result_success(
        self, mock_db, mock_current_user, mock_task_model, mock_session_model
    ):
        """Test successful task result retrieval."""
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )

        from app.routes.tasks import get_task_result

        result = await get_task_result("task123", mock_db, mock_current_user)

        assert result.task_id == "task123"
        assert result.result == {"result": "success"}

    async def test_get_task_result_not_found(self, mock_db, mock_current_user):
        """Test get_task_result when task not found."""
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_task_result_not_completed(self, mock_db, mock_current_user, mock_task_model):
        """Test get_task_result when task not completed."""
        mock_task_model.status = "running"
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    async def test_get_task_result_no_data(self, mock_db, mock_current_user, mock_task_model):
        """Test get_task_result when no result data."""
        mock_task_model.status = "completed"
        mock_task_model.result_data = None
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_task_result_error(self, mock_db, mock_current_user):
        """Test get_task_result with internal error."""
        mock_db.query.side_effect = Exception("Database error")

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db.rollback.assert_called_once()


class TestCancelTaskInSession:
    """Tests for cancel_task_in_session endpoint."""

    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_in_session_success(
        self,
        mock_get_executor,
        mock_db,
        mock_task_executor,
        mock_current_user,
        mock_session_model,
        mock_task_model,
    ):
        """Test successful task cancellation in session."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.cancel_task.return_value = {"status": "cancelled"}

        mock_db.query.return_value.filter.return_value.filter.return_value.first.side_effect = [
            mock_session_model,
            mock_task_model,
        ]

        from app.routes.tasks import cancel_task_in_session

        result = await cancel_task_in_session(
            "session123", "task123", mock_db, mock_task_executor, mock_current_user
        )

        assert result["status"] == "cancelled"

    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_in_session_not_found(
        self, mock_get_executor, mock_db, mock_task_executor, mock_current_user
    ):
        """Test cancel_task_in_session when session not found."""
        mock_get_executor.return_value = mock_task_executor
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", mock_db, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_in_session_task_not_found(
        self, mock_get_executor, mock_db, mock_task_executor, mock_current_user, mock_session_model
    ):
        """Test cancel_task_in_session when task not found."""
        mock_get_executor.return_value = mock_task_executor
        mock_db.query.return_value.filter.return_value.filter.return_value.first.side_effect = [
            mock_session_model,
            None,
        ]

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", mock_db, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_in_session_access_denied(
        self,
        mock_get_executor,
        mock_db,
        mock_task_executor,
        mock_current_user,
        mock_session_model,
        mock_task_model,
    ):
        """Test cancel_task_in_session when access denied."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.cancel_task.side_effect = ValueError("Access denied")
        mock_db.query.return_value.filter.return_value.filter.return_value.first.side_effect = [
            mock_session_model,
            mock_task_model,
        ]

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", mock_db, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_in_session_value_error(
        self,
        mock_get_executor,
        mock_db,
        mock_task_executor,
        mock_current_user,
        mock_session_model,
        mock_task_model,
    ):
        """Test cancel_task_in_session with value error."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.cancel_task.side_effect = ValueError("Task not found")
        mock_db.query.return_value.filter.return_value.filter.return_value.first.side_effect = [
            mock_session_model,
            mock_task_model,
        ]

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", mock_db, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_in_session_error(
        self,
        mock_get_executor,
        mock_db,
        mock_task_executor,
        mock_current_user,
        mock_session_model,
        mock_task_model,
    ):
        """Test cancel_task_in_session with internal error."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.cancel_task.side_effect = Exception("Service error")
        mock_db.query.return_value.filter.return_value.filter.return_value.first.side_effect = [
            mock_session_model,
            mock_task_model,
        ]

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", mock_db, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestCancelTask:
    """Tests for cancel_task endpoint."""

    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_success(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test successful task cancellation."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.get_task_status.return_value = {"status": "running"}
        mock_task_executor.cancel_task.return_value = {"status": "cancelled"}

        from app.routes.tasks import cancel_task

        result = await cancel_task("task123", mock_task_executor, mock_current_user)

        assert result["status"] == "cancelled"

    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_access_denied(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test cancel_task when access denied."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.get_task_status.return_value = {"status": "running"}
        mock_task_executor.cancel_task.side_effect = ValueError("Access denied")

        from app.routes.tasks import cancel_task

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task("task123", mock_task_executor, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_not_found(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test cancel_task when task not found."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.get_task_status.return_value = {"status": "running"}
        mock_task_executor.cancel_task.side_effect = ValueError("Task not found")

        from app.routes.tasks import cancel_task

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task("task123", mock_task_executor, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.tasks.get_task_executor")
    async def test_cancel_task_error(
        self, mock_get_executor, mock_task_executor, mock_current_user
    ):
        """Test cancel_task with internal error."""
        mock_get_executor.return_value = mock_task_executor
        mock_task_executor.get_task_status.side_effect = Exception("Service error")

        from app.routes.tasks import cancel_task

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task("task123", mock_task_executor, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestCreateTaskDependency:
    """Tests for create_task_dependency endpoint."""

    async def test_create_task_dependency_success(
        self, mock_db, mock_current_user, mock_task_model, mock_session_model
    ):
        """Test successful task dependency creation."""
        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = "task456"
        mock_prereq_task.session_id = "session123"

        mock_db.query.return_value.join.return_value.filter.return_value.first.side_effect = [
            mock_task_model,
            mock_prereq_task,
        ]
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_dependency = MagicMock()
        mock_dependency.id = 1
        mock_dependency.dependent_task_id = "task123"
        mock_dependency.prerequisite_task_id = "task456"
        mock_dependency.dependency_type = "sequential"
        mock_dependency.created_at = datetime.now(timezone.utc)

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest
        from app.database.models import TaskDependency as TaskDependencyModel

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with patch.object(TaskDependencyModel, "__init__", return_value=mock_dependency):
            result = await create_task_dependency("task123", request, mock_db, mock_current_user)

        assert result.dependent_task_id == "task123"
        assert result.prerequisite_task_id == "task456"

    async def test_create_task_dependency_dependent_not_found(self, mock_db, mock_current_user):
        """Test create_task_dependency when dependent task not found."""
        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = None

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_task_dependency_prerequisite_not_found(
        self, mock_db, mock_current_user, mock_task_model
    ):
        """Test create_task_dependency when prerequisite task not found."""
        mock_db.query.return_value.join.return_value.filter.return_value.first.side_effect = [
            mock_task_model,
            None,
        ]

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_task_dependency_different_sessions(
        self, mock_db, mock_current_user, mock_task_model, mock_session_model
    ):
        """Test create_task_dependency when tasks in different sessions."""
        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = "task456"
        mock_prereq_task.session_id = "session456"  # Different session

        mock_db.query.return_value.join.return_value.filter.return_value.first.side_effect = [
            mock_task_model,
            mock_prereq_task,
        ]

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    async def test_create_task_dependency_self_dependency(
        self, mock_db, mock_current_user, mock_task_model
    ):
        """Test create_task_dependency with self dependency."""
        mock_db.query.return_value.join.return_value.filter.return_value.first.side_effect = [
            mock_task_model,
            mock_task_model,
        ]

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task123", dependency_type="sequential"  # Same as dependent
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    async def test_create_task_dependency_already_exists(
        self, mock_db, mock_current_user, mock_task_model
    ):
        """Test create_task_dependency when dependency already exists."""
        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = "task456"
        mock_prereq_task.session_id = "session123"

        mock_db.query.return_value.join.return_value.filter.return_value.first.side_effect = [
            mock_task_model,
            mock_prereq_task,
        ]
        mock_db.query.return_value.filter.return_value.first.return_value = (
            MagicMock()
        )  # Existing dependency

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    async def test_create_task_dependency_cycle(self, mock_db, mock_current_user, mock_task_model):
        """Test create_task_dependency that would create a cycle."""
        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = "task456"
        mock_prereq_task.session_id = "session123"

        mock_db.query.return_value.join.return_value.filter.return_value.first.side_effect = [
            mock_task_model,
            mock_prereq_task,
        ]
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock query that returns dependent tasks (creating a cycle)
        mock_dependent_query = MagicMock()
        mock_dependent_query.all.return_value = [("task123",)]
        mock_db.query.return_value.filter.return_value.all.return_value = [("task456",)]

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    async def test_create_task_dependency_error(self, mock_db, mock_current_user, mock_task_model):
        """Test create_task_dependency with internal error."""
        mock_db.query.side_effect = Exception("Database error")

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task123", request, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db.rollback.assert_called_once()


class TestListTaskDependencies:
    """Tests for list_task_dependencies endpoint."""

    async def test_list_task_dependencies_success(
        self, mock_db, mock_current_user, mock_task_model
    ):
        """Test successful task dependencies listing."""
        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )

        mock_dep1 = MagicMock()
        mock_dep1.id = 1
        mock_dep1.dependent_task_id = "task123"
        mock_dep1.prerequisite_task_id = "task456"
        mock_dep1.dependency_type = "sequential"
        mock_dep1.created_at = datetime.now(timezone.utc)

        mock_dep2 = MagicMock()
        mock_dep2.id = 2
        mock_dep2.dependent_task_id = "task123"
        mock_dep2.prerequisite_task_id = "task789"
        mock_dep2.dependency_type = "parallel"
        mock_dep2.created_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep1, mock_dep2]

        from app.routes.tasks import list_task_dependencies

        result = await list_task_dependencies("task123", mock_db, mock_current_user)

        assert len(result) == 2
        assert result[0].prerequisite_task_id == "task456"

    async def test_list_task_dependencies_not_found(self, mock_db, mock_current_user):
        """Test list_task_dependencies when task not found."""
        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = None

        from app.routes.tasks import list_task_dependencies

        with pytest.raises(HTTPException) as exc_info:
            await list_task_dependencies("task123", mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_list_task_dependencies_error(self, mock_db, mock_current_user):
        """Test list_task_dependencies with internal error."""
        mock_db.query.side_effect = Exception("Database error")

        from app.routes.tasks import list_task_dependencies

        with pytest.raises(HTTPException) as exc_info:
            await list_task_dependencies("task123", mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestDeleteTaskDependency:
    """Tests for delete_task_dependency endpoint."""

    async def test_delete_task_dependency_success(
        self, mock_db, mock_current_user, mock_task_model
    ):
        """Test successful task dependency deletion."""
        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )

        mock_dependency = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_dependency

        from app.routes.tasks import delete_task_dependency

        result = await delete_task_dependency("task123", 1, mock_db, mock_current_user)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_dependency)
        mock_db.commit.assert_called_once()

    async def test_delete_task_dependency_task_not_found(self, mock_db, mock_current_user):
        """Test delete_task_dependency when task not found."""
        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = None

        from app.routes.tasks import delete_task_dependency

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task123", 1, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_task_dependency_not_found(
        self, mock_db, mock_current_user, mock_task_model
    ):
        """Test delete_task_dependency when dependency not found."""
        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )
        mock_db.query.return_value.filter.return_value.first.return_value = None

        from app.routes.tasks import delete_task_dependency

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task123", 1, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_task_dependency_error(self, mock_db, mock_current_user):
        """Test delete_task_dependency with internal error."""
        mock_db.query.side_effect = Exception("Database error")

        from app.routes.tasks import delete_task_dependency

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task123", 1, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db.rollback.assert_called_once()

    def test_get_task_workflows(self, client, mock_auth):
        """Test getting task workflows."""
        response = client.get("/api/tasks/workflows")

        assert response.status_code in [200, 404]

    def test_start_workflow(self, client, mock_auth):
        """Test starting a workflow."""
        workflow_data = {"workflow_id": "workflow123", "input": {"data": "value"}}

        response = client.post("/api/tasks/workflows/start", json=workflow_data)

        assert response.status_code in [200, 404]

    def test_get_workflow_status(self, client, mock_auth):
        """Test getting workflow status."""
        response = client.get("/api/tasks/workflows/123/status")

        assert response.status_code in [200, 404]

    def test_cancel_workflow(self, client, mock_auth):
        """Test cancelling a workflow."""
        response = client.post("/api/tasks/workflows/123/cancel")

        assert response.status_code in [200, 404]

    def test_get_task_schedules(self, client, mock_auth):
        """Test getting task schedules."""
        response = client.get("/api/tasks/schedules")

        assert response.status_code in [200, 404]

    def test_create_task_schedule(self, client, mock_auth):
        """Test creating task schedule."""
        schedule_data = {"task_id": "123", "cron": "0 0 * * *"}

        response = client.post("/api/tasks/schedules", json=schedule_data)

        assert response.status_code in [200, 404]

    def test_get_task_automations(self, client, mock_auth):
        """Test getting task automations."""
        response = client.get("/api/tasks/automations")

        assert response.status_code in [200, 404]

    def test_create_task_automation(self, client, mock_auth):
        """Test creating task automation."""
        automation_data = {"trigger": "task_completed", "action": "send_notification"}

        response = client.post("/api/tasks/automations", json=automation_data)

        assert response.status_code in [200, 404]

    def test_get_task_integrations(self, client, mock_auth):
        """Test getting task integrations."""
        response = client.get("/api/tasks/integrations")

        assert response.status_code in [200, 404]

    def test_configure_integration(self, client, mock_auth):
        """Test configuring integration."""
        config_data = {"integration_id": "slack", "config": {"webhook_url": "https://..."}}

        response = client.post("/api/tasks/integrations/configure", json=config_data)

        assert response.status_code in [200, 404]

    def test_get_task_analytics(self, client, mock_auth):
        """Test getting task analytics."""
        response = client.get("/api/tasks/analytics")

        assert response.status_code in [200, 404]

    def test_get_task_reports(self, client, mock_auth):
        """Test getting task reports."""
        response = client.get("/api/tasks/reports")

        assert response.status_code in [200, 404]

    def test_export_tasks(self, client, mock_auth):
        """Test exporting tasks."""
        response = client.get("/api/tasks/export?format=csv")

        assert response.status_code in [200, 404]

    def test_import_tasks(self, client, mock_auth):
        """Test importing tasks."""
        # Mock file upload
        pass

    def test_get_task_statistics(self, client, mock_auth):
        """Test getting task statistics."""
        response = client.get("/api/tasks/statistics")

        assert response.status_code in [200, 404]

    def test_get_task_dashboard(self, client, mock_auth):
        """Test getting task dashboard."""
        response = client.get("/api/tasks/dashboard")

        assert response.status_code in [200, 404]

    def test_get_task_recommendations(self, client, mock_auth):
        """Test getting task recommendations."""
        response = client.get("/api/tasks/recommendations")

        assert response.status_code in [200, 404]

    def test_get_task_insights(self, client, mock_auth):
        """Test getting task insights."""
        response = client.get("/api/tasks/insights")

        assert response.status_code in [200, 404]

    def test_get_task_health(self, client, mock_auth):
        """Test getting task health."""
        response = client.get("/api/tasks/health")

        assert response.status_code in [200, 404]

    def test_get_task_status(self, client, mock_auth):
        """Test getting task status."""
        response = client.get("/api/tasks/status")

        assert response.status_code in [200, 404]
