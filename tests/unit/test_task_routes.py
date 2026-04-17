"""
Unit tests for task routes.

Tests task submission, status checking, listing, and cancellation endpoints
by calling route functions directly with mocked dependencies.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from fastapi import status


@pytest.fixture
def mock_task_executor() -> MagicMock:
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
def mock_current_user() -> MagicMock:
    """Create mock current user."""
    user = MagicMock()
    user.id = str(uuid.uuid4())
    user.user_id = str(uuid.uuid4())
    user.username = "test_user"
    return user


@pytest.fixture
def mock_db_session() -> MagicMock:
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
def mock_task_model() -> MagicMock:
    """Mock task model."""
    task = MagicMock()
    task.task_id = "task123"
    task.session_id = "session123"
    task.status = "completed"
    task.result_data = {"result": "success"}
    task.created_at = datetime.now(timezone.utc)
    return task


@pytest.fixture
def mock_session_model() -> MagicMock:
    """Mock session model."""
    session = MagicMock()
    session.session_id = "session123"
    session.user_id = "user123"
    return session


class TestTaskRoutes:
    """Test task management route functions."""

    @pytest.mark.asyncio
    async def test_list_tasks_success(self, mock_task_executor: MagicMock) -> None:
        """Test listing available tasks successfully."""
        from app.routes.tasks import list_tasks

        response = await list_tasks(executor=mock_task_executor, current_user=MagicMock())

        assert response.tasks is not None
        assert len(response.tasks) == 1
        assert response.tasks[0]["task_type"] == "iowa_gambling"

    @pytest.mark.asyncio
    async def test_list_tasks_executor_error(self, mock_task_executor: MagicMock) -> None:
        """Test listing tasks when executor fails."""
        mock_task_executor.list_available_tasks.side_effect = Exception("Executor error")

        from app.routes.tasks import list_tasks

        with pytest.raises(HTTPException) as exc_info:
            await list_tasks(executor=mock_task_executor, current_user=MagicMock())

        assert exc_info.value.status_code == 500
        assert "Failed to list tasks" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_execute_task_success(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test successful task submission."""
        session_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        mock_task_executor.submit_task.return_value = task_id

        from app.models.schemas import TaskSubmitRequest
        from app.routes.tasks import execute_task

        request = TaskSubmitRequest(
            task_type="attentional_blink",
            parameters={"num_trials": 100},
            priority=5,
            webhook_url="https://example.com/webhook",
        )

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
    async def test_execute_task_invalid_type(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test task submission with invalid task type."""
        session_id = str(uuid.uuid4())
        mock_task_executor.submit_task.side_effect = ValueError("Invalid task type")

        from app.models.schemas import TaskSubmitRequest
        from app.routes.tasks import execute_task

        request = TaskSubmitRequest(
            task_type="invalid_task", parameters={}, priority=5, webhook_url=None
        )

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
    async def test_execute_task_executor_error(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test task submission when executor fails."""
        session_id = str(uuid.uuid4())
        mock_task_executor.submit_task.side_effect = Exception("Executor error")

        from app.models.schemas import TaskSubmitRequest
        from app.routes.tasks import execute_task

        request = TaskSubmitRequest(
            task_type="attentional_blink", parameters={}, priority=5, webhook_url=None
        )

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
    async def test_get_task_status_success(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
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
            request=MagicMock(spec=Request),
            task_id=task_id,
            executor=mock_task_executor,
            current_user=mock_current_user,
        )

        # JSONResponse content is accessed via body_decode or similar
        # For testing, we can check the status code and that it returns a response
        assert response.status_code == 200  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test getting status of non-existent task."""
        task_id = str(uuid.uuid4())
        mock_task_executor.get_task_status.side_effect = ValueError("Task not found")

        from app.routes.tasks import get_task_status

        with pytest.raises(HTTPException) as exc_info:
            await get_task_status(
                request=MagicMock(spec=Request),
                task_id=task_id,
                executor=mock_task_executor,
                current_user=mock_current_user,
            )

        assert exc_info.value.status_code == 404
        assert f"Task {task_id} not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_task_status_value_error_other(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test getting task status with a non-not-found ValueError (400 path)."""
        task_id = str(uuid.uuid4())
        mock_task_executor.get_task_status.side_effect = ValueError("Invalid parameter")

        from app.routes.tasks import get_task_status

        with pytest.raises(HTTPException) as exc_info:
            await get_task_status(
                request=MagicMock(spec=Request),
                task_id=task_id,
                executor=mock_task_executor,
                current_user=mock_current_user,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_task_status_executor_error(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test getting task status when executor fails."""
        task_id = str(uuid.uuid4())
        mock_task_executor.get_task_status.side_effect = Exception("Executor error")

        from app.routes.tasks import get_task_status

        with pytest.raises(HTTPException) as exc_info:
            await get_task_status(
                request=MagicMock(spec=Request),
                task_id=task_id,
                executor=mock_task_executor,
                current_user=mock_current_user,
            )

        assert exc_info.value.status_code == 500
        assert "Failed to get task status" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_cancel_task_success(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
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
    async def test_cancel_task_access_denied(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test cancelling task when access is denied (403 path)."""
        task_id = str(uuid.uuid4())
        mock_task_executor.get_task_status.return_value = {"status": "running"}
        mock_task_executor.cancel_task.side_effect = ValueError("Access denied to this task")

        from app.routes.tasks import cancel_task

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task(
                task_id=task_id, executor=mock_task_executor, current_user=mock_current_user
            )

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_cancel_task_http_exception_reraise(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test cancel_task re-raises HTTPException from get_task_status (line 402)."""
        task_id = str(uuid.uuid4())
        mock_task_executor.get_task_status.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

        from app.routes.tasks import cancel_task

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task(
                task_id=task_id, executor=mock_task_executor, current_user=mock_current_user
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_task_value_error_not_found(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test cancelling task with ValueError that is not access denied (404 path)."""
        task_id = str(uuid.uuid4())
        mock_task_executor.get_task_status.return_value = {"status": "running"}
        mock_task_executor.cancel_task.side_effect = ValueError("Task does not exist")

        from app.routes.tasks import cancel_task

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task(
                task_id=task_id, executor=mock_task_executor, current_user=mock_current_user
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_task_executor_error(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
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

    def test_get_task_executor_initialized(self) -> None:
        """Test get_task_executor when initialized."""
        with patch("app.routes.tasks.TaskExecutor"):
            from app.routes.tasks import init_task_routes, get_task_executor

            init_task_routes()
            executor = get_task_executor()
            assert executor is not None

    def test_get_task_executor_not_initialized(self) -> None:
        """Test get_task_executor when not initialized."""
        import app.routes.tasks

        app.routes.tasks._task_executor = None

        from app.routes.tasks import get_task_executor

        with pytest.raises(HTTPException) as exc_info:
            get_task_executor()

        assert exc_info.value.status_code == 503
        assert "Task executor not initialized" in exc_info.value.detail


class TestGetTaskResult:
    """Tests for get_task_result endpoint.

    Note: get_task_result uses two chained .filter() calls:
      db.query(TaskModel).join(...).filter(...).filter(...).first()
    So the mock chain is: .join().filter().filter().first()
    """

    @staticmethod
    def _make_db_for_result(task_return: MagicMock | None) -> MagicMock:
        """Build mock db with .join().filter().filter().first() chain."""
        db = MagicMock(spec=Session)
        db.rollback = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            task_return
        )
        return db

    @pytest.mark.asyncio
    async def test_get_task_result_success(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test successful task result retrieval."""
        db = self._make_db_for_result(mock_task_model)

        from app.routes.tasks import get_task_result

        result = await get_task_result("task123", db, mock_current_user)

        assert result.task_id == "task123"
        assert result.result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_get_task_result_not_found(self, mock_current_user: MagicMock) -> None:
        """Test get_task_result when task not found."""
        db = self._make_db_for_result(None)

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_task_result_not_completed(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test get_task_result when task not completed."""
        mock_task_model.status = "running"
        db = self._make_db_for_result(mock_task_model)

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_get_task_result_no_data(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test get_task_result when no result data."""
        mock_task_model.status = "completed"
        mock_task_model.result_data = None
        db = self._make_db_for_result(mock_task_model)

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_task_result_error(
        self, mock_db_session: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test get_task_result with internal error."""
        mock_db_session.query.side_effect = Exception("Database error")

        from app.routes.tasks import get_task_result

        with pytest.raises(HTTPException) as exc_info:
            await get_task_result("task123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestCancelTaskInSession:
    """Tests for cancel_task_in_session endpoint."""

    @staticmethod
    def _make_db_for_cancel(
        session_return: MagicMock | None, task_return: MagicMock | None
    ) -> MagicMock:
        """
        Build a mock db where:
          - query(SessionModel).filter().first() returns session_return
          - query(TaskModel).filter().first() returns task_return
        """
        db = MagicMock(spec=Session)
        db.commit = MagicMock()
        db.rollback = MagicMock()

        session_query = MagicMock()
        session_query.filter.return_value.first.return_value = session_return

        task_query = MagicMock()
        task_query.filter.return_value.first.return_value = task_return

        db.query.side_effect = [session_query, task_query]
        return db

    @pytest.mark.asyncio
    async def test_cancel_task_in_session_success(
        self,
        mock_task_executor: MagicMock,
        mock_current_user: MagicMock,
        mock_session_model: MagicMock,
        mock_task_model: MagicMock,
    ) -> None:
        """Test successful task cancellation in session."""
        mock_task_executor.cancel_task.return_value = {"status": "cancelled"}
        db = self._make_db_for_cancel(mock_session_model, mock_task_model)

        from app.routes.tasks import cancel_task_in_session

        result = await cancel_task_in_session(
            "session123", "task123", db, mock_task_executor, mock_current_user
        )

        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_task_in_session_session_not_found(
        self, mock_task_executor: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test cancel_task_in_session when session not found."""
        db = self._make_db_for_cancel(None, None)

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", db, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cancel_task_in_session_task_not_found(
        self,
        mock_task_executor: MagicMock,
        mock_current_user: MagicMock,
        mock_session_model: MagicMock,
    ) -> None:
        """Test cancel_task_in_session when task not found."""
        db = self._make_db_for_cancel(mock_session_model, None)

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", db, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cancel_task_in_session_access_denied(
        self,
        mock_task_executor: MagicMock,
        mock_current_user: MagicMock,
        mock_session_model: MagicMock,
        mock_task_model: MagicMock,
    ) -> None:
        """Test cancel_task_in_session when access is denied (403 path)."""
        mock_task_executor.cancel_task.side_effect = ValueError("Access denied to this task")
        db = self._make_db_for_cancel(mock_session_model, mock_task_model)

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", db, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_cancel_task_in_session_value_error_not_found(
        self,
        mock_task_executor: MagicMock,
        mock_current_user: MagicMock,
        mock_session_model: MagicMock,
        mock_task_model: MagicMock,
    ) -> None:
        """Test cancel_task_in_session with ValueError that is not access denied (404 path)."""
        mock_task_executor.cancel_task.side_effect = ValueError("Task does not exist")
        db = self._make_db_for_cancel(mock_session_model, mock_task_model)

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", db, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cancel_task_in_session_error(
        self,
        mock_task_executor: MagicMock,
        mock_current_user: MagicMock,
        mock_session_model: MagicMock,
        mock_task_model: MagicMock,
    ) -> None:
        """Test cancel_task_in_session with internal error."""
        mock_task_executor.cancel_task.side_effect = Exception("Service error")
        db = self._make_db_for_cancel(mock_session_model, mock_task_model)

        from app.routes.tasks import cancel_task_in_session

        with pytest.raises(HTTPException) as exc_info:
            await cancel_task_in_session(
                "session123", "task123", db, mock_task_executor, mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestCreateTaskDependency:
    """Tests for create_task_dependency endpoint."""

    # Fixed UUIDs for use in tests (TaskDependencyCreateRequest validates UUID format)
    TASK_ID = "11111111-1111-1111-1111-111111111111"
    PREREQ_ID = "22222222-2222-2222-2222-222222222222"
    SAME_ID = "11111111-1111-1111-1111-111111111111"

    @staticmethod
    def _make_db_for_dependency(
        dependent_task: MagicMock | None = None,
        prerequisite_task: MagicMock | None = None,
        existing_dep: MagicMock | None = None,
        cycle_deps: list[tuple[str]] | None = None,
    ) -> MagicMock:
        """
        Build a mock db for create_task_dependency.
        Queries in order:
          1. query(TaskModel).join().filter().first() -> dependent_task
          2. query(TaskModel).join().filter().first() -> prerequisite_task
          3. query(TaskDependencyModel).filter().first() -> existing_dep
          4. query(TaskDependencyModel.dependent_task_id).filter().all() -> cycle_deps
        """
        db = MagicMock(spec=Session)
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.add = MagicMock()
        db.refresh = MagicMock()

        dep_task_query = MagicMock()
        dep_task_query.join.return_value.filter.return_value.first.return_value = dependent_task

        prereq_task_query = MagicMock()
        prereq_task_query.join.return_value.filter.return_value.first.return_value = (
            prerequisite_task
        )

        existing_dep_query = MagicMock()
        existing_dep_query.filter.return_value.first.return_value = existing_dep

        cycle_query = MagicMock()
        cycle_query.filter.return_value.all.return_value = cycle_deps or []

        db.query.side_effect = [
            dep_task_query,
            prereq_task_query,
            existing_dep_query,
            cycle_query,
        ]
        return db

    @pytest.mark.asyncio
    async def test_create_task_dependency_success(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test successful task dependency creation."""
        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = self.PREREQ_ID
        mock_prereq_task.session_id = "session123"

        mock_task_model.task_id = self.TASK_ID
        mock_task_model.session_id = "session123"

        db = self._make_db_for_dependency(
            dependent_task=mock_task_model,
            prerequisite_task=mock_prereq_task,
            existing_dep=None,
            cycle_deps=[],
        )

        def refresh_side_effect(obj: MagicMock) -> None:
            obj.id = 1
            obj.dependent_task_id = self.TASK_ID
            obj.prerequisite_task_id = self.PREREQ_ID
            obj.dependency_type = "completion"
            obj.created_at = datetime.now(timezone.utc)

        db.refresh.side_effect = refresh_side_effect

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest  # type: ignore[attr-defined]

        request = TaskDependencyCreateRequest(
            prerequisite_task_id=self.PREREQ_ID, dependency_type="completion"
        )

        result = await create_task_dependency(self.TASK_ID, request, db, mock_current_user)

        assert result.dependent_task_id == self.TASK_ID
        assert result.prerequisite_task_id == self.PREREQ_ID
        db.add.assert_called_once()
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_task_dependency_cycle_detected(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test create_task_dependency when a cycle would be created."""
        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = self.PREREQ_ID
        mock_prereq_task.session_id = "session123"

        mock_task_model.task_id = self.TASK_ID
        mock_task_model.session_id = "session123"

        # Simulate: PREREQ_ID already has TASK_ID as a dependent -> cycle
        cycle_deps = [(self.TASK_ID,)]

        db = self._make_db_for_dependency(
            dependent_task=mock_task_model,
            prerequisite_task=mock_prereq_task,
            existing_dep=None,
            cycle_deps=cycle_deps,
        )

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest  # type: ignore[attr-defined]

        request = TaskDependencyCreateRequest(
            prerequisite_task_id=self.PREREQ_ID, dependency_type="completion"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency(self.TASK_ID, request, db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert "cycle" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_task_dependency_cycle_visited_node(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test cycle detection visits already-visited node (line 506: return False in has_cycle)."""
        THIRD_ID = "33333333-3333-3333-3333-333333333333"

        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = self.PREREQ_ID
        mock_prereq_task.session_id = "session123"

        mock_task_model.task_id = self.TASK_ID
        mock_task_model.session_id = "session123"

        # Graph: PREREQ_ID -> THIRD_ID -> PREREQ_ID (already visited, returns False)
        # This exercises the `if start_task_id in visited: return False` branch
        # First call to has_cycle(PREREQ_ID, TASK_ID, set()):
        #   - visits PREREQ_ID, finds dependent THIRD_ID
        #   - recurses: has_cycle(THIRD_ID, TASK_ID, {PREREQ_ID})
        #     - visits THIRD_ID, finds dependent PREREQ_ID
        #     - recurses: has_cycle(PREREQ_ID, TASK_ID, {PREREQ_ID, THIRD_ID})
        #       - PREREQ_ID in visited -> return False (line 506)
        # No cycle found -> dependency is created

        db = MagicMock(spec=Session)
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.add = MagicMock()
        db.refresh = MagicMock()

        dep_task_query = MagicMock()
        dep_task_query.join.return_value.filter.return_value.first.return_value = mock_task_model

        prereq_task_query = MagicMock()
        prereq_task_query.join.return_value.filter.return_value.first.return_value = (
            mock_prereq_task
        )

        existing_dep_query = MagicMock()
        existing_dep_query.filter.return_value.first.return_value = None  # No existing dep

        # Cycle query returns different results per call
        cycle_query1 = MagicMock()
        cycle_query1.filter.return_value.all.return_value = [(THIRD_ID,)]  # PREREQ_ID -> THIRD_ID

        cycle_query2 = MagicMock()
        cycle_query2.filter.return_value.all.return_value = [
            (self.PREREQ_ID,)
        ]  # THIRD_ID -> PREREQ_ID

        cycle_query3 = MagicMock()
        cycle_query3.filter.return_value.all.return_value = []  # PREREQ_ID already visited

        db.query.side_effect = [
            dep_task_query,
            prereq_task_query,
            existing_dep_query,
            cycle_query1,
            cycle_query2,
            cycle_query3,
        ]

        def refresh_side_effect(obj: MagicMock) -> None:
            obj.id = 1
            obj.dependent_task_id = self.TASK_ID
            obj.prerequisite_task_id = self.PREREQ_ID
            obj.dependency_type = "completion"
            obj.created_at = datetime.now(timezone.utc)

        db.refresh.side_effect = refresh_side_effect

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest  # type: ignore[attr-defined]

        request = TaskDependencyCreateRequest(
            prerequisite_task_id=self.PREREQ_ID, dependency_type="completion"
        )

        # Should succeed (no cycle to TASK_ID)
        result = await create_task_dependency(self.TASK_ID, request, db, mock_current_user)
        assert result.dependent_task_id == self.TASK_ID

    @pytest.mark.asyncio
    async def test_create_task_dependency_dependent_not_found(
        self, mock_db_session: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test create_task_dependency when dependent task not found."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = (
            None
        )

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest  # type: ignore[attr-defined]

        request = TaskDependencyCreateRequest(
            prerequisite_task_id=self.PREREQ_ID, dependency_type="completion"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency(self.TASK_ID, request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_task_dependency_prerequisite_not_found(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test create_task_dependency when prerequisite task not found."""
        db = MagicMock(spec=Session)
        db.rollback = MagicMock()

        dep_task_query = MagicMock()
        dep_task_query.join.return_value.filter.return_value.first.return_value = mock_task_model

        prereq_task_query = MagicMock()
        prereq_task_query.join.return_value.filter.return_value.first.return_value = None

        db.query.side_effect = [dep_task_query, prereq_task_query]

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest  # type: ignore[attr-defined]

        request = TaskDependencyCreateRequest(
            prerequisite_task_id=self.PREREQ_ID, dependency_type="completion"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency(self.TASK_ID, request, db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_task_dependency_different_sessions(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test create_task_dependency when tasks in different sessions."""
        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = self.PREREQ_ID
        mock_prereq_task.session_id = "session456"  # Different session

        mock_task_model.session_id = "session123"

        db = MagicMock(spec=Session)
        db.rollback = MagicMock()

        dep_task_query = MagicMock()
        dep_task_query.join.return_value.filter.return_value.first.return_value = mock_task_model

        prereq_task_query = MagicMock()
        prereq_task_query.join.return_value.filter.return_value.first.return_value = (
            mock_prereq_task
        )

        db.query.side_effect = [dep_task_query, prereq_task_query]

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest  # type: ignore[attr-defined]

        request = TaskDependencyCreateRequest(
            prerequisite_task_id=self.PREREQ_ID, dependency_type="completion"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency(self.TASK_ID, request, db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_task_dependency_self_dependency(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test create_task_dependency with self dependency."""
        mock_task_model.task_id = self.TASK_ID
        mock_task_model.session_id = "session123"

        mock_prereq_same = MagicMock()
        mock_prereq_same.task_id = self.TASK_ID
        mock_prereq_same.session_id = "session123"

        db = MagicMock(spec=Session)
        db.rollback = MagicMock()

        dep_task_query = MagicMock()
        dep_task_query.join.return_value.filter.return_value.first.return_value = mock_task_model

        prereq_task_query = MagicMock()
        prereq_task_query.join.return_value.filter.return_value.first.return_value = (
            mock_prereq_same
        )

        db.query.side_effect = [dep_task_query, prereq_task_query]

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest  # type: ignore[attr-defined]

        # Self-dependency: same task_id as prerequisite_task_id
        request = TaskDependencyCreateRequest(
            prerequisite_task_id=self.TASK_ID, dependency_type="completion"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency(self.TASK_ID, request, db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_task_dependency_already_exists(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test create_task_dependency when dependency already exists."""
        mock_prereq_task = MagicMock()
        mock_prereq_task.task_id = self.PREREQ_ID
        mock_prereq_task.session_id = "session123"

        mock_task_model.task_id = self.TASK_ID
        mock_task_model.session_id = "session123"

        db = self._make_db_for_dependency(
            dependent_task=mock_task_model,
            prerequisite_task=mock_prereq_task,
            existing_dep=MagicMock(),  # Existing dependency found
        )

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest  # type: ignore[attr-defined]

        request = TaskDependencyCreateRequest(
            prerequisite_task_id=self.PREREQ_ID, dependency_type="completion"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency(self.TASK_ID, request, db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_create_task_dependency_error(
        self, mock_db_session: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test create_task_dependency with internal error."""
        mock_db_session.query.side_effect = Exception("Database error")

        from app.routes.tasks import create_task_dependency, TaskDependencyCreateRequest  # type: ignore[attr-defined]

        request = TaskDependencyCreateRequest(
            prerequisite_task_id=self.PREREQ_ID, dependency_type="completion"
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_task_dependency(self.TASK_ID, request, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db_session.rollback.assert_called_once()


class TestListTaskDependencies:
    """Tests for list_task_dependencies endpoint."""

    @pytest.mark.asyncio
    async def test_list_task_dependencies_success(
        self, mock_db_session: MagicMock, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test successful listing of task dependencies."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )

        mock_dep = MagicMock()
        mock_dep.id = 1
        mock_dep.dependent_task_id = "task123"
        mock_dep.prerequisite_task_id = "task456"
        mock_dep.dependency_type = "sequential"
        mock_dep.created_at = datetime.now(timezone.utc)

        mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_dep]

        from app.routes.tasks import list_task_dependencies

        result = await list_task_dependencies("task123", mock_db_session, mock_current_user)

        assert len(result) == 1
        assert result[0].dependent_task_id == "task123"
        assert result[0].prerequisite_task_id == "task456"

    @pytest.mark.asyncio
    async def test_list_task_dependencies_empty(
        self, mock_db_session: MagicMock, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test listing task dependencies when there are none."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = (
            mock_task_model
        )
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        from app.routes.tasks import list_task_dependencies

        result = await list_task_dependencies("task123", mock_db_session, mock_current_user)

        assert result == []

    @pytest.mark.asyncio
    async def test_list_task_dependencies_not_found(
        self, mock_db_session: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test list_task_dependencies when task not found."""
        mock_db_session.query.return_value.join.return_value.filter.return_value.first.return_value = (
            None
        )

        from app.routes.tasks import list_task_dependencies

        with pytest.raises(HTTPException) as exc_info:
            await list_task_dependencies("task123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_task_dependencies_error(
        self, mock_db_session: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test list_task_dependencies with internal error."""
        mock_db_session.query.side_effect = Exception("Database error")

        from app.routes.tasks import list_task_dependencies

        with pytest.raises(HTTPException) as exc_info:
            await list_task_dependencies("task123", mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestDeleteTaskDependency:
    """Tests for delete_task_dependency endpoint."""

    @staticmethod
    def _make_db_for_delete(
        task_return: MagicMock | None, dep_return: MagicMock | None
    ) -> MagicMock:
        """
        Build a mock db for delete_task_dependency.
        Queries in order:
          1. query(TaskModel).join().filter().first() -> task_return
          2. query(TaskDependencyModel).filter().first() -> dep_return
        """
        db = MagicMock(spec=Session)
        db.commit = MagicMock()
        db.rollback = MagicMock()
        db.delete = MagicMock()

        task_query = MagicMock()
        task_query.join.return_value.filter.return_value.first.return_value = task_return

        dep_query = MagicMock()
        dep_query.filter.return_value.first.return_value = dep_return

        db.query.side_effect = [task_query, dep_query]
        return db

    @pytest.mark.asyncio
    async def test_delete_task_dependency_success(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test successful task dependency deletion."""
        mock_dep = MagicMock()
        mock_dep.id = 1

        db = self._make_db_for_delete(mock_task_model, mock_dep)

        from app.routes.tasks import delete_task_dependency

        await delete_task_dependency("task123", 1, db, mock_current_user)

        db.delete.assert_called_once_with(mock_dep)
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_task_dependency_task_not_found(
        self, mock_current_user: MagicMock
    ) -> None:
        """Test delete_task_dependency when task not found."""
        db = self._make_db_for_delete(None, None)

        from app.routes.tasks import delete_task_dependency

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task123", 1, db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_task_dependency_not_found(
        self, mock_current_user: MagicMock, mock_task_model: MagicMock
    ) -> None:
        """Test delete_task_dependency when dependency not found."""
        db = self._make_db_for_delete(mock_task_model, None)

        from app.routes.tasks import delete_task_dependency

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task123", 1, db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_task_dependency_error(
        self, mock_db_session: MagicMock, mock_current_user: MagicMock
    ) -> None:
        """Test delete_task_dependency with internal error."""
        mock_db_session.query.side_effect = Exception("Database error")

        from app.routes.tasks import delete_task_dependency

        with pytest.raises(HTTPException) as exc_info:
            await delete_task_dependency("task123", 1, mock_db_session, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_db_session.rollback.assert_called_once()
