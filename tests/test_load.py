"""
Load testing for APGI API using Locust.

This script defines load tests for key API endpoints to establish performance baselines.
"""

import os
from locust import HttpUser, task, between


class APGIUser(HttpUser):
    """
    Load testing user for APGI API.

    Tests key endpoints with realistic usage patterns.
    """

    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)

    def on_start(self):
        """Set up test user - skip authentication for load testing."""
        # For load testing, we'll test unauthenticated endpoints
        # or use a pre-generated token
        pass

    @task(10)  # 10x more frequent than other tasks
    def test_health_endpoint(self):
        """Test health check endpoint - most frequently accessed."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(5)
    def test_readiness_endpoint(self):
        """Test readiness probe endpoint."""
        with self.client.get("/v1/health/ready", catch_response=True) as response:
            if response.status_code in [200, 503]:  # 503 is acceptable for readiness
                response.success()
            else:
                response.failure(f"Readiness check failed: {response.status_code}")

    @task(3)
    def test_liveness_endpoint(self):
        """Test liveness probe endpoint."""
        with self.client.get("/v1/health/live", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Liveness check failed: {response.status_code}")

    @task(2)
    def test_root_endpoint(self):
        """Test API root endpoint."""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Root endpoint failed: {response.status_code}")

    @task(1)
    def test_openapi_docs(self):
        """Test OpenAPI documentation access."""
        with self.client.get("/docs", catch_response=True) as response:
            if response.status_code in [200, 307]:  # 307 redirect is acceptable
                response.success()
            else:
                response.failure(f"Docs access failed: {response.status_code}")

    @task(1)
    def test_openapi_json(self):
        """Test OpenAPI JSON schema access."""
        with self.client.get("/openapi.json", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"OpenAPI JSON failed: {response.status_code}")


class AuthenticatedAPGIUser(HttpUser):
    """
    Load testing user with authentication.

    Tests authenticated endpoints with proper JWT tokens.
    Note: Requires a valid JWT token to be set in environment.
    """

    wait_time = between(2, 5)

    def on_start(self):
        """Set up authenticated user."""
        # Get token from environment for authenticated testing
        self.token = os.environ.get("LOAD_TEST_JWT_TOKEN")
        if self.token:
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @task(5)
    def test_sessions_list(self):
        """Test listing user sessions."""
        if not self.token:
            return  # Skip if no token

        with self.client.get("/v1/sessions", catch_response=True) as response:
            if response.status_code in [200, 401]:  # 401 if token expired
                response.success()
            else:
                response.failure(f"Sessions list failed: {response.status_code}")

    @task(3)
    def test_tasks_list(self):
        """Test listing available tasks."""
        if not self.token:
            return

        with self.client.get("/v1/tasks", catch_response=True) as response:
            if response.status_code in [200, 401]:
                response.success()
            else:
                response.failure(f"Tasks list failed: {response.status_code}")

    @task(1)
    def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        if not self.token:
            return

        with self.client.get("/metrics", catch_response=True) as response:
            if response.status_code in [200, 401]:
                response.success()
            else:
                response.failure(f"Metrics access failed: {response.status_code}")
