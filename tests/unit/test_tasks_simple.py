"""Simple unit tests for task routes to achieve basic coverage.

Focuses on testing function calls and error paths without complex dependencies.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.routes.tasks import (
    list_tasks,
    execute_task,
    get_task_status,
    get_task_result,
    cancel_task_in_session,
    cancel_task,
    create_task_dependency,
    list_task_dependencies,
    delete_task_dependency,
    get_task_executor,
    init_task_routes,
)
from app.database.models import Task
from app.models.schemas import (
    TaskSubmitRequest,
    TaskDependencyCreateRequest,
)
from app.services.authorization import TokenPayload


class TestTaskRoutes:
    """Test task route endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user token payload."""
        return TokenPayload(
            user_id="user123",
            username="testuser",
            roles=["user"],
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    @pytest.fixture
    def mock_executor(self):
        """Mock task executor."""
        executor = Mock()
        executor.list_tasks.return_value = [
            {"name": "test_task", "description": "Test task description", "parameters": {}}
        ]
        executor.submit_task.return_value = "task123"
        executor.get_task_status.return_value = {
            "task_id": "task123",
            "status": "running",
            "result": None,
        }
        executor.get_task_result.return_value = {"task_id": "task123", "result": {"data": "test"}}
        executor.cancel_task.return_value = True
        return executor

    def test_get_task_executor_success(self):
        """Test getting task executor when initialized."""
        # First initialize the routes
        init_task_routes()

        # Now get the executor
        executor = get_task_executor()
        assert executor is not None

    def test_get_task_executor_not_initialized(self):
        """Test getting task executor when not initialized."""
        # Reset the global executor
        import app.routes.tasks

        app.routes.tasks._task_executor = None

        with pytest.raises(HTTPException) as exc_info:
            get_task_executor()
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_list_tasks_success(self, mock_executor, mock_current_user):
        """Test successful task listing."""
        with patch("app.routes.tasks.get_task_executor", return_value=mock_executor):
            result = await list_tasks(mock_executor, mock_current_user)

            assert len(result.tasks) == 1
            assert result.tasks[0]["name"] == "test_task"

    @pytest.mark.asyncio
    async def test_execute_task_success(self, mock_executor, mock_current_user):
        """Test successful task execution."""
        request = TaskSubmitRequest(task_name="test_task", parameters={"param1": "value1"})

        with patch("app.routes.tasks.get_task_executor", return_value=mock_executor):
            result = await execute_task("session123", request, mock_executor, mock_current_user)

            assert result.task_id == "task123"
            assert result.status == "submitted"

    @pytest.mark.asyncio
    async def test_get_task_status_success(self, mock_executor, mock_current_user):
        """Test successful task status retrieval."""
        with patch("app.routes.tasks.get_task_executor", return_value=mock_executor):
            result = await get_task_status("task123", mock_executor, mock_current_user)

            assert result.task_id == "task123"
            assert result.status == "running"

    @pytest.mark.asyncio
    async def test_get_task_result_success(self, mock_db, mock_current_user):
        """Test successful task result retrieval."""
        # Mock database query
        mock_task = Mock(spec=Task)
        mock_task.task_id = "task123"
        mock_task.result_data = {"data": "test"}
        mock_task.status = "completed"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        result = await get_task_result("task123", mock_db, mock_current_user)

        assert result.task_id == "task123"
        assert result.result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_get_task_result_not_found(self, mock_db, mock_current_user):
        """Test task result retrieval when task not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("nonexistent", mock_db, mock_current_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_task_in_session_success(self, mock_db, mock_current_user):
        """Test successful task cancellation in session."""
        # Mock database query
        mock_task = Mock(spec=Task)
        mock_task.task_id = "task123"
        mock_task.session_id = "session123"
        mock_task.status = "running"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        with patch("app.routes.tasks.get_task_executor", return_value=Mock()) as mock_executor:
            mock_executor.cancel_task.return_value = True

            result = await cancel_task_in_session(
                "session123", "task123", mock_db, mock_current_user
            )

            assert result.message == "Task task123 cancelled successfully"

    @pytest.mark.asyncio
    async def test_cancel_task_in_session_not_found(self, mock_db, mock_current_user):
        """Test task cancellation in session when task not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session("session123", "nonexistent", mock_db, mock_current_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_task_success(self, mock_executor, mock_current_user):
        """Test successful task cancellation."""
        with patch("app.routes.tasks.get_task_executor", return_value=mock_executor):
            result = await cancel_task("task123", mock_executor, mock_current_user)

            assert result.message == "Task task123 cancelled successfully"

    @pytest.mark.asyncio
    async def test_create_task_dependency_success(self, mock_db, mock_current_user):
        """Test successful task dependency creation."""
        request = TaskDependencyCreateRequest(
            depends_on_task_id="task456", dependency_type="success"
        )

        # Mock database query
        mock_task = Mock(spec=Task)
        mock_task.task_id = "task123"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        # Mock dependency creation
        mock_dependency = Mock()
        mock_dependency.id = 1
        mock_dependency.depends_on_task_id = "task456"
        mock_dependency.dependency_type = "success"

        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch("app.routes.tasks.TaskDependency", return_value=mock_dependency):
            result = await create_task_dependency("task123", request, mock_db, mock_current_user)

            assert result.depends_on_task_id == "task456"
            assert result.dependency_type == "success"

    @pytest.mark.asyncio
    async def test_create_task_dependency_task_not_found(self, mock_db, mock_current_user):
        """Test task dependency creation when task not found."""
        request = TaskDependencyCreateRequest(
            depends_on_task_id="task456", dependency_type="success"
        )

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency("nonexistent", request, mock_db, mock_current_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_task_dependencies_success(self, mock_db, mock_current_user):
        """Test successful task dependency listing."""
        # Mock database query
        mock_task = Mock(spec=Task)
        mock_task.task_id = "task123"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        # Mock dependencies
        mock_dependency1 = Mock()
        mock_dependency1.id = 1
        mock_dependency1.depends_on_task_id = "task456"

        mock_dependency2 = Mock()
        mock_dependency2.id = 2
        mock_dependency2.depends_on_task_id = "task789"

        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_dependency1,
            mock_dependency2,
        ]

        result = await list_task_dependencies("task123", mock_db, mock_current_user)

        assert len(result) == 2
        assert result[0].depends_on_task_id == "task456"

    @pytest.mark.asyncio
    async def test_list_task_dependencies_task_not_found(self, mock_db, mock_current_user):
        """Test task dependency listing when task not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await list_task_dependencies("nonexistent", mock_db, mock_current_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_task_dependency_success(self, mock_db, mock_current_user):
        """Test successful task dependency deletion."""
        # Mock database queries
        mock_task = Mock(spec=Task)
        mock_task.task_id = "task123"

        mock_dependency = Mock()
        mock_dependency.id = 1
        mock_dependency.task_id = "task123"

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_task,
            mock_dependency,
        ]
        mock_db.delete.return_value = None
        mock_db.commit.return_value = None

        result = await delete_task_dependency("task123", 1, mock_db, mock_current_user)

        assert result is None
        mock_db.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_task_dependency_task_not_found(self, mock_db, mock_current_user):
        """Test task dependency deletion when task not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("nonexistent", 1, mock_db, mock_current_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_task_dependency_not_found(self, mock_db, mock_current_user):
        """Test task dependency deletion when dependency not found."""
        # Mock task exists but dependency doesn't
        mock_task = Mock(spec=Task)
        mock_task.task_id = "task123"

        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_task, None]

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task123", 999, mock_db, mock_current_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_task_invalid_session(self, mock_executor, mock_current_user):
        """Test task execution with invalid session."""
        request = TaskSubmitRequest(task_name="test_task", parameters={})

        with patch("app.routes.tasks.get_task_executor", return_value=mock_executor):
            # Mock executor to raise exception for invalid session
            mock_executor.submit_task.side_effect = Exception("Invalid session")

            with pytest.raises(HTTPException) as exc_info:
                await execute_task("invalid_session", request, mock_executor, mock_current_user)
                assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, mock_executor, mock_current_user):
        """Test task status when task not found."""
        with patch("app.routes.tasks.get_task_executor", return_value=mock_executor):
            # Mock executor to raise exception for non-existent task
            mock_executor.get_task_status.side_effect = Exception("Task not found")

            with pytest.raises(HTTPException) as exc_info:
                await get_task_status("nonexistent", mock_executor, mock_current_user)
                assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, mock_executor, mock_current_user):
        """Test task cancellation when task not found."""
        with patch("app.routes.tasks.get_task_executor", return_value=mock_executor):
            # Mock executor to raise exception for non-existent task
            mock_executor.cancel_task.side_effect = Exception("Task not found")

            with pytest.raises(HTTPException) as exc_info:
                await cancel_task("nonexistent", mock_executor, mock_current_user)
                assert exc_info.value.status_code == 404
