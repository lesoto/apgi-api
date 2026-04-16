"""
Integration Tests for Task Routes

Tests task submission, status checking, listing, and cancellation endpoints
through HTTP requests with authentication.
"""

import pytest
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def authenticated_client(
    test_environment: None, mock_database_connection: None
) -> AsyncGenerator[AsyncClient, None]:
    """Create authenticated test client for task integration tests."""
    from app.main import create_app
    from app.services.auth_manager import AuthManager
    from unittest.mock import AsyncMock, patch

    # Mock Redis for the lifespan
    mock_redis_client = AsyncMock()
    mock_redis_client.ping = AsyncMock()
    mock_redis_client.aclose = AsyncMock()

    # Mock User for authentication
    mock_user = MagicMock()
    mock_user.user_id = str(uuid.uuid4())
    mock_user.username = "test_user"
    mock_user.roles = ["admin"]

    # Create a real JWT token for the mock user
    auth_manager = AuthManager(db=None)  # type: ignore[arg-type]  # We don't need DB for token creation
    access_token = auth_manager.create_access_token(
        user_id=mock_user.user_id, username=mock_user.username, roles=mock_user.roles
    )

    with (
        patch("redis.asyncio.from_url", return_value=mock_redis_client),
        patch("app.services.auth_manager.AuthManager.authenticate_user", return_value=mock_user),
    ):
        app = create_app(test_mode=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Add the JWT token to default headers
            ac.headers.update({"Authorization": f"Bearer {access_token}"})
            yield ac


@pytest.fixture
def mock_task_executor() -> MagicMock:
    """Create mock TaskExecutor for integration tests."""
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
    executor.cancel_task = AsyncMock()
    return executor


class TestTaskRoutesIntegration:
    """Integration tests for task management endpoints."""

    @pytest.mark.asyncio
    async def test_list_tasks_authenticated(
        self, authenticated_client: AsyncClient, mock_task_executor: MagicMock
    ) -> None:
        """Test listing available tasks with authentication."""
        from app.routes.tasks import init_task_routes

        # Initialize the task executor with mock
        init_task_routes()
        # Replace the global executor with our mock
        import app.routes.tasks

        app.routes.tasks._task_executor = mock_task_executor

        response = await authenticated_client.get("/v1/tasks")

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_type"] == "iowa_gambling"

    @pytest.mark.asyncio
    async def test_execute_task_authenticated(
        self, authenticated_client: AsyncClient, mock_task_executor: MagicMock
    ) -> None:
        """Test successful task submission with authentication."""
        from app.routes.tasks import init_task_routes

        session_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        mock_task_executor.submit_task.return_value = task_id

        # Initialize the task executor with mock
        init_task_routes()
        import app.routes.tasks

        app.routes.tasks._task_executor = mock_task_executor

        request_data = {
            "task_type": "iowa_gambling",
            "parameters": {"num_trials": 100},
            "webhook_url": "https://example.com/webhook",
        }

        response = await authenticated_client.post(
            f"/v1/sessions/{session_id}/tasks", json=request_data
        )

        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == task_id
        assert data["session_id"] == session_id
        assert data["task_type"] == "iowa_gambling"
        assert data["status"] == "pending"
        assert "status_url" in data

    @pytest.mark.asyncio
    async def test_execute_task_invalid_type_authenticated(
        self, authenticated_client: AsyncClient, mock_task_executor: MagicMock
    ) -> None:
        """Test task submission with invalid task type."""
        from app.routes.tasks import init_task_routes

        session_id = str(uuid.uuid4())
        mock_task_executor.submit_task.side_effect = ValueError("Invalid task type")

        # Initialize the task executor with mock
        init_task_routes()
        import app.routes.tasks

        app.routes.tasks._task_executor = mock_task_executor

        request_data = {"task_type": "invalid_task", "parameters": {}}

        response = await authenticated_client.post(
            f"/v1/sessions/{session_id}/tasks", json=request_data
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["message"] == "Invalid task type"

    @pytest.mark.asyncio
    async def test_get_task_status_authenticated(
        self, authenticated_client: AsyncClient, mock_task_executor: MagicMock
    ) -> None:
        """Test getting task status with authentication."""
        from app.routes.tasks import init_task_routes

        task_id = str(uuid.uuid4())

        # Initialize the task executor with mock
        init_task_routes()
        import app.routes.tasks

        app.routes.tasks._task_executor = mock_task_executor

        response = await authenticated_client.get(f"/v1/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "completed"
        assert data["state"] == "SUCCESS"
        assert data["result"]["accuracy"] == 0.85

    @pytest.mark.asyncio
    async def test_cancel_task_authenticated(
        self, authenticated_client: AsyncClient, mock_task_executor: MagicMock
    ) -> None:
        """Test cancelling a task with authentication."""
        from app.routes.tasks import init_task_routes

        task_id = str(uuid.uuid4())
        mock_task_executor.get_task_status.return_value = {"status": "running"}
        mock_task_executor.cancel_task.return_value = {"task_id": task_id, "status": "cancelled"}

        # Initialize the task executor with mock
        init_task_routes()
        import app.routes.tasks

        app.routes.tasks._task_executor = mock_task_executor

        response = await authenticated_client.delete(f"/v1/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found_authenticated(
        self, authenticated_client: AsyncClient, mock_task_executor: MagicMock
    ) -> None:
        """Test getting status of non-existent task."""
        from app.routes.tasks import init_task_routes

        task_id = str(uuid.uuid4())
        mock_task_executor.get_task_status.side_effect = ValueError("Task not found")

        # Initialize the task executor with mock
        init_task_routes()
        import app.routes.tasks

        app.routes.tasks._task_executor = mock_task_executor

        response = await authenticated_client.get(f"/v1/tasks/{task_id}")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["message"] == f"Task {task_id} not found"

    @pytest.mark.asyncio
    async def test_cancel_task_not_found_authenticated(
        self, authenticated_client: AsyncClient, mock_task_executor: MagicMock
    ) -> None:
        """Test cancelling non-existent task."""
        from app.routes.tasks import init_task_routes

        task_id = str(uuid.uuid4())
        # Make sure get_task_status returns None to simulate task not found
        mock_task_executor.get_task_status.return_value = None
        # Make sure cancel_task also raises an appropriate exception
        mock_task_executor.cancel_task.side_effect = ValueError(f"Task {task_id} not found")

        # Initialize the task executor with mock
        init_task_routes()
        import app.routes.tasks

        app.routes.tasks._task_executor = mock_task_executor

        response = await authenticated_client.delete(f"/v1/tasks/{task_id}")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["message"] == f"Task {task_id} not found"

    @pytest.mark.asyncio
    async def test_task_submission_celery_integration(
        self, authenticated_client: AsyncClient
    ) -> None:
        """Test that task submission properly integrates with Celery."""
        from unittest.mock import patch, MagicMock
        from app.routes.tasks import init_task_routes
        from app.database.connection import init_db, close_db

        # Initialize database for this test
        init_db()

        try:
            # Initialize task routes with real executor
            init_task_routes()

            session_id = str(uuid.uuid4())

            # Create a mock Celery task result
            mock_celery_result = MagicMock()
            mock_celery_result.id = str(uuid.uuid4())

            # Patch celery_app.send_task to verify it's called correctly
            with patch("app.services.task_executor.celery_app.send_task") as mock_send_task:
                mock_send_task.return_value = mock_celery_result

                request_data = {
                    "task_type": "iowa_gambling",
                    "parameters": {"num_trials": 50},
                    "priority": 5,
                }

                response = await authenticated_client.post(
                    f"/v1/sessions/{session_id}/tasks", json=request_data
                )

                # Should return 202 Accepted
                assert response.status_code == 202
                data = response.json()
                assert "task_id" in data
                assert data["session_id"] == session_id
                assert data["task_type"] == "iowa_gambling"

                # Verify Celery send_task was called with correct arguments
                mock_send_task.assert_called_once()
                call_args = mock_send_task.call_args
                assert call_args[0][0] == "app.tasks.experimental_tasks.execute_iowa_gambling_task"
                assert call_args[1]["args"] == [session_id, {"num_trials": 50}]
                assert "task_id" in call_args[1]

        finally:
            close_db()
