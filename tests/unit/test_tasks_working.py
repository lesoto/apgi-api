"""
Working tests for task routes to achieve coverage.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException
from datetime import datetime
from sqlalchemy.orm import Session

# Import the actual route functions
from app.routes.tasks import (
    get_task_executor,
    init_task_routes,
    list_tasks,
    execute_task,
    get_task_status,
    get_task_result,
    cancel_task_in_session,
    cancel_task,
    create_task_dependency,
    list_task_dependencies,
    delete_task_dependency,
    router,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def mock_task_executor():
    """Mock task executor."""
    executor = AsyncMock()
    return executor


@pytest.fixture
def mock_current_user():
    """Mock current user."""
    user = MagicMock()
    user.user_id = "user123"
    user.username = "testuser"
    user.roles = ["viewer"]
    return user


class TestTaskExecutor:
    """Test task executor dependency."""

    def test_get_task_executor_success(self):
        """Test successful task executor retrieval."""
        # Initialize the task executor first
        init_task_routes()

        result = get_task_executor()
        assert result is not None

    def test_get_task_executor_not_initialized(self):
        """Test task executor retrieval when not initialized."""
        # Reset the global variable
        import app.routes.tasks

        app.routes.tasks._task_executor = None

        with pytest.raises(HTTPException) as exc_info:
            get_task_executor()
        assert exc_info.value.status_code == 503
        assert "Task executor not initialized" in str(exc_info.value.detail)


class TestTaskRoutes:
    """Test task route endpoints."""

    @pytest.mark.asyncio
    async def test_init_task_routes(self):
        """Test task routes initialization."""
        # Reset the global variable first
        import app.routes.tasks

        app.routes.tasks._task_executor = None

        init_task_routes()

        assert app.routes.tasks._task_executor is not None

    @pytest.mark.asyncio
    async def test_list_tasks_success(self, mock_task_executor, mock_current_user):
        """Test successful task listing."""
        mock_task_executor.list_available_tasks.return_value = {
            "tasks": [
                {
                    "name": "test_task",
                    "description": "Test task description",
                    "parameters": {"param1": "string"},
                }
            ]
        }

        with MagicMock() as mock_get_executor:
            mock_get_executor.return_value = mock_task_executor

            result = await list_tasks(mock_task_executor, mock_current_user)

            assert len(result.tasks) == 1
            assert result.tasks[0]["name"] == "test_task"

    @pytest.mark.asyncio
    async def test_list_tasks_error(self, mock_task_executor, mock_current_user):
        """Test task listing with error."""
        mock_task_executor.list_available_tasks.side_effect = Exception("Database error")

        with MagicMock() as mock_get_executor:
            mock_get_executor.return_value = mock_task_executor

            with pytest.raises(HTTPException) as exc_info:
                await list_tasks(mock_task_executor, mock_current_user)
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_execute_task_success(self, mock_task_executor, mock_current_user):
        """Test successful task execution."""
        from app.models.schemas import TaskSubmitRequest

        request = TaskSubmitRequest(
            task_type="test_task",
            parameters={"param1": "value1"},
            priority=1,
            webhook_url="http://example.com/webhook",
        )

        mock_task_executor.submit_task.return_value = "task123"

        with MagicMock() as mock_get_executor:
            mock_get_executor.return_value = mock_task_executor

            result = await execute_task(
                "session123", request, mock_task_executor, mock_current_user
            )

            assert result.task_id == "task123"
            assert result.session_id == "session123"
            assert result.task_type == "test_task"
            assert result.status == "pending"

    @pytest.mark.asyncio
    async def test_execute_task_validation_error(self, mock_task_executor, mock_current_user):
        """Test task execution with validation error."""
        from app.models.schemas import TaskSubmitRequest

        request = TaskSubmitRequest(task_type="invalid_task", parameters={})

        mock_task_executor.submit_task.side_effect = ValueError("Invalid task type")

        with MagicMock() as mock_get_executor:
            mock_get_executor.return_value = mock_task_executor

            with pytest.raises(HTTPException) as exc_info:
                await execute_task("session123", request, mock_task_executor, mock_current_user)
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_task_status_success(self, mock_task_executor, mock_current_user):
        """Test successful task status retrieval."""
        mock_task_executor.get_task_status.return_value = {
            "status": "completed",
            "state": "success",
            "result": {"output": "test result"},
            "error": None,
            "info": {"duration": 1.5},
        }

        with MagicMock() as mock_get_executor:
            mock_get_executor.return_value = mock_task_executor

            result = await get_task_status("task123", mock_task_executor, mock_current_user)

            assert result.task_id == "task123"
            assert result.status == "completed"
            assert result.result["output"] == "test result"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, mock_task_executor, mock_current_user):
        """Test task status retrieval when task not found."""
        mock_task_executor.get_task_status.side_effect = ValueError("Task not found")

        with MagicMock() as mock_get_executor:
            mock_get_executor.return_value = mock_task_executor

            with pytest.raises(HTTPException) as exc_info:
                await get_task_status("task999", mock_task_executor, mock_current_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_task_result_success(self, mock_db, mock_current_user):
        """Test successful task result retrieval."""
        mock_task = MagicMock()
        mock_task.task_id = "task123"
        mock_task.status = "completed"
        mock_task.result_data = {"output": "test result"}

        mock_session = MagicMock()
        mock_session.user_id = "user123"

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task
        )
        mock_db.query.return_value = mock_query

        result = await get_task_result("task123", mock_db, mock_current_user)

        assert result.task_id == "task123"
        assert result.result["output"] == "test result"

    @pytest.mark.asyncio
    async def test_get_task_result_not_found(self, mock_db, mock_current_user):
        """Test task result retrieval when task not found."""
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task999", mock_db, mock_current_user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_task_result_not_completed(self, mock_db, mock_current_user):
        """Test task result retrieval when task not completed."""
        mock_task = MagicMock()
        mock_task.task_id = "task123"
        mock_task.status = "running"
        mock_task.result_data = None

        mock_session = MagicMock()
        mock_session.user_id = "user123"

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task
        )
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", mock_db, mock_current_user)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_task_in_session_success(
        self, mock_db, mock_task_executor, mock_current_user
    ):
        """Test successful task cancellation in session."""
        mock_session = MagicMock()
        mock_session.session_id = "session123"
        mock_session.user_id = "user123"

        mock_task = MagicMock()
        mock_task.task_id = "task123"
        mock_task.session_id = "session123"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value = mock_query

        mock_query2 = MagicMock()
        mock_query2.filter.return_value.filter.return_value.first.return_value = mock_task
        mock_db.query.return_value = mock_query2

        mock_task_executor.cancel_task.return_value = {"status": "cancelled"}

        with MagicMock() as mock_get_executor:
            mock_get_executor.return_value = mock_task_executor

            result = await cancel_task_in_session(
                "session123", "task123", mock_db, mock_task_executor, mock_current_user
            )

            assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_task_in_session_not_found(
        self, mock_db, mock_task_executor, mock_current_user
    ):
        """Test task cancellation when session not found."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session999", "task123", mock_db, mock_task_executor, mock_current_user
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_task_success(self, mock_task_executor, mock_current_user):
        """Test successful task cancellation."""
        mock_task_executor.get_task_status.return_value = {"status": "running"}
        mock_task_executor.cancel_task.return_value = {"status": "cancelled"}

        with MagicMock() as mock_get_executor:
            mock_get_executor.return_value = mock_task_executor

            result = await cancel_task("task123", mock_task_executor, mock_current_user)

            assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, mock_task_executor, mock_current_user):
        """Test task cancellation when task not found."""
        mock_task_executor.get_task_status.side_effect = ValueError("Task not found")

        with MagicMock() as mock_get_executor:
            mock_get_executor.return_value = mock_task_executor

            with pytest.raises(HTTPException) as exc_info:
                await cancel_task("task999", mock_task_executor, mock_current_user)
            assert exc_info.value.status_code == 404


class TestTaskDependencies:
    """Test task dependency endpoints."""

    @pytest.mark.asyncio
    async def test_create_task_dependency_success(self, mock_db, mock_current_user):
        """Test successful task dependency creation."""
        from app.models.schemas import TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        # Mock dependent task
        mock_dependent_task = MagicMock()
        mock_dependent_task.task_id = "task123"
        mock_dependent_task.session_id = "session123"

        # Mock prerequisite task
        mock_prerequisite_task = MagicMock()
        mock_prerequisite_task.task_id = "task456"
        mock_prerequisite_task.session_id = "session123"

        # Mock dependency model
        mock_dependency = MagicMock()
        mock_dependency.id = 1
        mock_dependency.dependent_task_id = "task123"
        mock_dependency.prerequisite_task_id = "task456"
        mock_dependency.dependency_type = "sequential"
        mock_dependency.created_at = datetime.utcnow()

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.filter.return_value.first.side_effect = [
            mock_dependent_task,  # First call returns dependent task
            mock_prerequisite_task,  # Second call returns prerequisite task
        ]
        mock_db.query.return_value = mock_query

        mock_query2 = MagicMock()
        mock_query2.filter.return_value.first.return_value = None  # No existing dependency
        mock_db.query.return_value = mock_query2

        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        result = await create_task_dependency("task123", request, mock_db, mock_current_user)

        assert result.dependent_task_id == "task123"
        assert result.prerequisite_task_id == "task456"

    @pytest.mark.asyncio
    async def test_create_task_dependency_dependent_not_found(self, mock_db, mock_current_user):
        """Test task dependency creation when dependent task not found."""
        from app.models.schemas import TaskDependencyCreateRequest

        request = TaskDependencyCreateRequest(
            prerequisite_task_id="task456", dependency_type="sequential"
        )

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("task999", request, mock_db, mock_current_user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_task_dependencies_success(self, mock_db, mock_current_user):
        """Test successful task dependency listing."""
        mock_task = MagicMock()
        mock_task.task_id = "task123"

        mock_dependency1 = MagicMock()
        mock_dependency1.id = 1
        mock_dependency1.dependent_task_id = "task123"
        mock_dependency1.prerequisite_task_id = "task456"
        mock_dependency1.dependency_type = "sequential"
        mock_dependency1.created_at = datetime.utcnow()

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task
        )
        mock_db.query.return_value = mock_query

        mock_query2 = MagicMock()
        mock_query2.filter.return_value.all.return_value = [mock_dependency1]
        mock_db.query.return_value = mock_query2

        result = await list_task_dependencies("task123", mock_db, mock_current_user)

        assert len(result) == 1
        assert result[0].dependent_task_id == "task123"

    @pytest.mark.asyncio
    async def test_list_task_dependencies_task_not_found(self, mock_db, mock_current_user):
        """Test task dependency listing when task not found."""
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await list_task_dependencies("task999", mock_db, mock_current_user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_task_dependency_success(self, mock_db, mock_current_user):
        """Test successful task dependency deletion."""
        mock_task = MagicMock()
        mock_task.task_id = "task123"

        mock_dependency = MagicMock()
        mock_dependency.id = 1
        mock_dependency.dependent_task_id = "task123"

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task
        )
        mock_db.query.return_value = mock_query

        mock_query2 = MagicMock()
        mock_query2.filter.return_value.first.return_value = mock_dependency
        mock_db.query.return_value = mock_query2

        result = await delete_task_dependency("task123", 1, mock_db, mock_current_user)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_dependency)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_task_dependency_not_found(self, mock_db, mock_current_user):
        """Test task dependency deletion when task not found."""
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task999", 1, mock_db, mock_current_user)
        assert exc_info.value.status_code == 404


class TestRouter:
    """Test router configuration."""

    def test_router_configuration(self):
        """Test that router is properly configured."""
        assert router.prefix == "/v1"
        assert "Tasks" in router.tags
        assert 404 in router.responses
        assert 500 in router.responses
