"""
End-to-End Testing Framework

Comprehensive testing framework for API-level end-to-end testing of critical user journeys.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Any, Optional, AsyncGenerator, cast

import httpx
import pytest
from faker import Faker

logger = logging.getLogger(__name__)


class APITestClient:
    """Enhanced HTTP client for API testing with authentication and session management."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url, timeout=httpx.Timeout(30.0, connect=10.0)
        )
        self.auth_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.current_user: Optional[Dict[str, Any]] = None

    async def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user and store tokens."""
        response = await self.client.post(
            "/v1/auth/login", json={"username": username, "password": password}
        )
        response.raise_for_status()

        data = cast(Dict[str, Any], response.json())
        self.auth_token = data["access_token"]
        self.refresh_token = data.get("refresh_token")
        self.current_user = data.get("user", {})

        # Set authorization header for future requests
        self.client.headers["Authorization"] = f"Bearer {self.auth_token}"

        return data

    async def refresh_auth_token(self) -> Dict[str, Any]:
        """Refresh authentication token."""
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        response = await self.client.post(
            "/v1/auth/refresh", json={"refresh_token": self.refresh_token}
        )
        response.raise_for_status()

        data = cast(Dict[str, Any], response.json())
        self.auth_token = data["access_token"]
        self.refresh_token = data.get("refresh_token")

        # Update authorization header
        self.client.headers["Authorization"] = f"Bearer {self.auth_token}"

        return data

    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user."""
        response = await self.client.post("/v1/users", json=user_data)
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def list_sessions(self, **params: Any) -> Dict[str, Any]:
        """List user sessions."""
        response = await self.client.get("/v1/sessions", params=params)
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new session."""
        response = await self.client.post("/v1/sessions", json=session_data)
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session details."""
        response = await self.client.get(f"/v1/sessions/{session_id}")
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def start_session(self, session_id: str) -> Dict[str, Any]:
        """Start a session."""
        response = await self.client.post(f"/v1/sessions/{session_id}/start")
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def stop_session(self, session_id: str) -> Dict[str, Any]:
        """Stop a session."""
        response = await self.client.post(f"/v1/sessions/{session_id}/stop")
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def create_task(self, session_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task for a session."""
        response = await self.client.post(f"/v1/sessions/{session_id}/tasks", json=task_data)
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status."""
        response = await self.client.get(f"/v1/tasks/{task_id}")
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def list_templates(self, **params: Any) -> Dict[str, Any]:
        """List session templates."""
        response = await self.client.get("/v1/templates", params=params)
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def create_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a session template."""
        response = await self.client.post("/v1/templates", json=template_data)
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())

    async def wait_for_task_completion(self, task_id: str, timeout: int = 300) -> Dict[str, Any]:
        """Wait for task to complete."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            status_data = await self.get_task_status(task_id)

            if status_data["status"] in ["completed", "failed"]:
                return status_data

            await asyncio.sleep(2)  # Wait 2 seconds before checking again

        raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


class E2ETestFramework:
    """End-to-end testing framework for comprehensive API testing."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.faker = Faker()
        self.faker.seed_instance(42)  # For reproducible test data

    @asynccontextmanager
    async def authenticated_client(
        self, user_data: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[APITestClient, None]:
        """Context manager that provides an authenticated API client."""
        client = APITestClient(self.base_url)

        try:
            # Create test user if not provided
            if not user_data:
                user_data = {
                    "username": self.faker.user_name(),
                    "email": self.faker.email(),
                    "password": "TestPass123!",
                }
                await client.create_user(user_data)

            # Authenticate
            await client.authenticate(user_data["username"], user_data["password"])

            yield client

        finally:
            await client.close()

    async def run_user_registration_journey(self) -> Dict[str, Any]:
        """Test complete user registration journey."""
        client = APITestClient(self.base_url)

        try:
            # Generate user data
            user_data = {
                "username": self.faker.user_name(),
                "email": self.faker.email(),
                "password": "TestPass123!",
            }

            # Create user
            registration_response = await client.create_user(user_data)
            assert "user_id" in registration_response

            # Authenticate with new user
            auth_response = await client.authenticate(user_data["username"], user_data["password"])
            assert "access_token" in auth_response

            # Verify we can access protected endpoints
            sessions_response = await client.list_sessions()
            assert "sessions" in sessions_response

            return {
                "success": True,
                "user_id": registration_response["user_id"],
                "username": user_data["username"],
                "email": user_data["email"],
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stage": "user_registration_journey",
            }
        finally:
            await client.close()

    async def run_session_lifecycle_journey(self) -> Dict[str, Any]:
        """Test complete session lifecycle journey."""
        async with self.authenticated_client() as client:
            try:
                # Create session
                session_data = {
                    "config_path": "config/basic_attention.yaml",
                    "custom_config": {
                        "experiment_type": "attentional_blink",
                        "trial_count": 10,
                    },
                    "description": "E2E test session",
                }

                session_response = await client.create_session(session_data)
                session_id = session_response["session_id"]

                # Get session details
                session_details = await client.get_session(session_id)
                assert session_details["session_id"] == session_id
                assert session_details["status"] == "created"

                # Start session
                start_response = await client.start_session(session_id)
                assert start_response["status"] == "running"

                # Create and run a task
                task_data = {
                    "task_type": "attentional_blink",
                    "parameters": {
                        "stream_length": 10,
                        "target_position": 5,
                    },
                }

                task_response = await client.create_task(session_id, task_data)
                task_id = task_response["task_id"]

                # Wait for task completion
                final_status = await client.wait_for_task_completion(task_id, timeout=60)

                # Stop session
                stop_response = await client.stop_session(session_id)
                assert stop_response["status"] == "stopped"

                return {
                    "success": True,
                    "session_id": session_id,
                    "task_id": task_id,
                    "task_final_status": final_status["status"],
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "stage": "session_lifecycle_journey",
                }

    async def run_template_workflow_journey(self) -> Dict[str, Any]:
        """Test template creation and usage journey."""
        async with self.authenticated_client() as client:
            try:
                # Create a template
                template_data = {
                    "name": "E2E Test Template",
                    "description": "Template for end-to-end testing",
                    "config_path": "config/basic_attention.yaml",
                    "custom_config": {
                        "experiment_type": "attentional_blink",
                        "trial_count": 5,
                    },
                    "default_description": "Session from E2E template",
                    "tags": ["e2e", "test"],
                    "is_public": True,
                }

                template_response = await client.create_template(template_data)
                template_id = template_response["template_id"]

                # List templates to verify creation
                templates_list = await client.list_templates()
                template_found = any(
                    t["template_id"] == template_id for t in templates_list["templates"]
                )
                assert template_found, "Created template not found in list"

                # Create session using template
                session_data = {
                    "template_id": template_id,
                    "description": "Session created from template",
                }

                session_response = await client.create_session(session_data)
                session_id = session_response["session_id"]

                # Verify session was created with template config
                session_details = await client.get_session(session_id)
                assert (
                    session_details["config"]["custom_config"]["experiment_type"]
                    == "attentional_blink"
                )

                return {
                    "success": True,
                    "template_id": template_id,
                    "session_id": session_id,
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "stage": "template_workflow_journey",
                }

    async def run_concurrent_workload_test(
        self, num_users: int = 5, num_sessions_per_user: int = 2
    ) -> Dict[str, Any]:
        """Test concurrent workload handling."""
        results: List[Dict[str, Any]] = []

        async def user_workflow(user_id: int) -> Dict[str, Any]:
            """Simulate a user's complete workflow."""
            user_data = {
                "username": f"concurrent_user_{user_id}",
                "email": f"concurrent_{user_id}@test.com",
                "password": "TestPass123!",
            }

            async with self.authenticated_client(user_data) as client:
                user_results = []

                try:
                    for session_num in range(num_sessions_per_user):
                        # Create session
                        session_data = {
                            "config_path": "config/basic_attention.yaml",
                            "custom_config": {"trial_count": 5},
                            "description": f"Concurrent test session {session_num}",
                        }

                        session_response = await client.create_session(session_data)
                        session_id = session_response["session_id"]

                        # Create task
                        task_data = {
                            "task_type": "attentional_blink",
                            "parameters": {"stream_length": 8, "target_position": 4},
                        }

                        task_response = await client.create_task(session_id, task_data)
                        task_id = task_response["task_id"]

                        user_results.append(
                            {
                                "session_id": session_id,
                                "task_id": task_id,
                            }
                        )

                    return {
                        "user_id": user_id,
                        "success": True,
                        "sessions_created": len(user_results),
                    }

                except Exception as e:
                    return {
                        "user_id": user_id,
                        "success": False,
                        "error": str(e),
                    }

        # Run concurrent workflows
        tasks = [user_workflow(i) for i in range(num_users)]
        workflow_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results
        successful_workflows = [
            r for r in workflow_results if isinstance(r, dict) and r.get("success")
        ]
        failed_workflows = [
            r for r in workflow_results if isinstance(r, dict) and not r.get("success")
        ]

        return {
            "success": len(failed_workflows) == 0,
            "total_users": num_users,
            "successful_workflows": len(successful_workflows),
            "failed_workflows": len(failed_workflows),
            "results": workflow_results,
        }

    async def run_performance_baseline_test(self) -> Dict[str, Any]:
        """Establish performance baseline for key operations."""
        async with self.authenticated_client() as client:
            import time

            results = {}

            try:
                # Test session creation performance
                session_times = []
                for i in range(10):
                    start_time = time.time()
                    session_data = {
                        "config_path": "config/basic_attention.yaml",
                        "custom_config": {"trial_count": 5},
                        "description": f"Performance test session {i}",
                    }
                    await client.create_session(session_data)
                    session_times.append(time.time() - start_time)

                results["session_creation"] = {
                    "avg_time": sum(session_times) / len(session_times),
                    "min_time": min(session_times),
                    "max_time": max(session_times),
                    "samples": len(session_times),
                }

                # Test template listing performance
                template_times = []
                for i in range(10):
                    start_time = time.time()
                    await client.list_templates()
                    template_times.append(time.time() - start_time)

                results["template_listing"] = {
                    "avg_time": sum(template_times) / len(template_times),
                    "min_time": min(template_times),
                    "max_time": max(template_times),
                    "samples": len(template_times),
                }

                return {
                    "success": True,
                    "performance_metrics": results,
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "stage": "performance_baseline_test",
                }


# Pytest fixtures for E2E testing
@pytest.fixture
async def api_client() -> AsyncGenerator[APITestClient, None]:
    """Fixture providing an API test client."""
    client = APITestClient()
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
async def authenticated_api_client(api_client: APITestClient) -> APITestClient:
    """Fixture providing an authenticated API test client."""
    # Create test user
    user_data = {
        "username": "test_user",
        "email": "test@example.com",
        "password": "TestPass123!",
    }

    await api_client.create_user(user_data)
    await api_client.authenticate(user_data["username"], user_data["password"])

    return api_client


@pytest.fixture
def e2e_framework() -> E2ETestFramework:
    """Fixture providing the E2E testing framework."""
    return E2ETestFramework()
