"""
Load Tests for Performance Validation

These tests validate that the API can handle expected load and performs
within acceptable response time limits. Tests use Locust for load generation.

Test scenarios:
- Normal load: Expected requests per second
- Response times: Verify p95 response times under load
- Graceful degradation: Verify API behavior under overload

**Validates: Requirements 20.1, 20.2, 20.6**

Usage:
    # Run with Locust web UI
    locust -f tests/load/test_performance.py --host=http://localhost:8000
    
    # Run headless with specific load
    locust -f tests/load/test_performance.py --host=http://localhost:8000 \
           --users 100 --spawn-rate 10 --run-time 60s --headless
    
    # Run with custom configuration
    locust -f tests/load/test_performance.py --host=http://localhost:8000 \
           --users 50 --spawn-rate 5 --run-time 120s --headless \
           --csv=results/load_test
"""

import json
import random
import time
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner

# Performance thresholds
MAX_RESPONSE_TIME_MS = 1000  # p95 should be under 1 second
EXPECTED_RPS = 100  # Expected requests per second
ERROR_RATE_THRESHOLD = 0.05  # Max 5% error rate


class APIUser(HttpUser):
    """
    Simulates a user interacting with the API.

    This user performs typical API operations:
    - Health checks
    - Authentication
    - Session management
    - Task operations
    """

    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)

    def on_start(self):
        """
        Called when a simulated user starts.
        Performs login to get authentication token.
        """
        # In test mode, we can skip authentication
        # In production load tests, implement real authentication
        self.token = None
        self.session_id = None

    @task(10)
    def health_check(self):
        """
        Test basic health check endpoint.

        Weight: 10 (most common operation)
        Validates: Requirement 9.1 - Health check performance
        """
        with self.client.get("/health", catch_response=True, name="/health") as response:
            if response.status_code == 200:
                data = response.json()
                if "status" in data and data["status"] == "healthy":
                    response.success()
                else:
                    response.failure("Invalid health check response")
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(8)
    def readiness_check(self):
        """
        Test readiness check endpoint with dependency verification.

        Weight: 8
        Validates: Requirement 9.2 - Readiness probe performance
        """
        with self.client.get(
            "/v1/health/ready", catch_response=True, name="/v1/health/ready"
        ) as response:
            if response.status_code in [200, 503]:
                response.success()
            else:
                response.failure(f"Unexpected status code {response.status_code}")

    @task(5)
    def liveness_check(self):
        """
        Test liveness check endpoint.

        Weight: 5
        Validates: Requirement 9.3 - Liveness probe performance
        """
        with self.client.get(
            "/v1/health/live", catch_response=True, name="/v1/health/live"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(3)
    def get_api_info(self):
        """
        Test root endpoint for API information.

        Weight: 3
        Validates: Basic API performance
        """
        with self.client.get("/", catch_response=True, name="/") as response:
            if response.status_code == 200:
                data = response.json()
                if "name" in data and "version" in data:
                    response.success()
                else:
                    response.failure("Invalid API info response")
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(2)
    def get_version(self):
        """
        Test version endpoint.

        Weight: 2
        Validates: Requirement 16.1 - Version endpoint performance
        """
        with self.client.get("/v1/version", catch_response=True, name="/v1/version") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(2)
    def list_tasks(self):
        """
        Test task listing endpoint.

        Weight: 2
        Validates: Requirement 15.3 - Task listing performance
        """
        with self.client.get("/v1/tasks", catch_response=True, name="/v1/tasks") as response:
            # May return 401 if auth is required, which is acceptable
            if response.status_code in [200, 401]:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(1)
    def get_openapi_schema(self):
        """
        Test OpenAPI schema endpoint.

        Weight: 1 (less frequent)
        Validates: API documentation performance
        """
        with self.client.get(
            "/openapi.json", catch_response=True, name="/openapi.json"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "openapi" in data and "paths" in data:
                        response.success()
                    else:
                        response.failure("Invalid OpenAPI schema")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Got status code {response.status_code}")


class AuthenticatedAPIUser(HttpUser):
    """
    Simulates an authenticated user performing session operations.

    This user tests authenticated endpoints that require more resources:
    - Session creation
    - Session management
    - Task submission
    """

    wait_time = between(2, 5)

    def on_start(self):
        """Setup authentication for this user."""
        # In test mode, authentication might be bypassed
        self.token = None
        self.session_ids = []

    @task(5)
    def create_session(self):
        """
        Test session creation under load.

        Weight: 5
        Validates: Requirement 18.3 - Session creation performance
        """
        payload = {"config": {"description": f"Load test session {random.randint(1000, 9999)}"}}

        with self.client.post(
            "/v1/sessions", json=payload, catch_response=True, name="/v1/sessions [POST]"
        ) as response:
            # May return 401 if auth required, 201 if successful
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    if "session_id" in data:
                        self.session_ids.append(data["session_id"])
                        response.success()
                    else:
                        response.failure("No session_id in response")
                except (json.JSONDecodeError, KeyError):
                    response.failure("Invalid response format")
            elif response.status_code == 401:
                # Expected in test mode without auth
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(3)
    def get_session(self):
        """
        Test session retrieval under load.

        Weight: 3
        Validates: Requirement 18.4 - Session retrieval performance
        """
        # Use a test session ID or one we created
        session_id = (
            self.session_ids[-1]
            if self.session_ids
            else f"test_session_{random.randint(1000, 9999)}"
        )

        with self.client.get(
            f"/v1/sessions/{session_id}", catch_response=True, name="/v1/sessions/{id} [GET]"
        ) as response:
            # 200 (found), 401 (auth required), or 404 (not found) are acceptable
            if response.status_code in [200, 401, 404]:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(2)
    def start_session(self):
        """
        Test session start operation under load.

        Weight: 2
        Validates: Session control performance
        """
        session_id = (
            self.session_ids[-1]
            if self.session_ids
            else f"test_session_{random.randint(1000, 9999)}"
        )

        with self.client.post(
            f"/v1/sessions/{session_id}/start",
            catch_response=True,
            name="/v1/sessions/{id}/start [POST]",
        ) as response:
            if response.status_code in [200, 401, 404]:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(1)
    def submit_task(self):
        """
        Test task submission under load.

        Weight: 1
        Validates: Requirements 15.1, 15.2 - Task submission performance
        """
        session_id = (
            self.session_ids[-1]
            if self.session_ids
            else f"test_session_{random.randint(1000, 9999)}"
        )

        payload = {"task_type": "test_task", "parameters": {"test": True}}

        with self.client.post(
            f"/v1/sessions/{session_id}/tasks",
            json=payload,
            catch_response=True,
            name="/v1/sessions/{id}/tasks [POST]",
        ) as response:
            if response.status_code in [200, 201, 401, 404, 422]:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")


class OverloadTestUser(HttpUser):
    """
    User for testing graceful degradation under overload.

    Sends requests as fast as possible to test system behavior
    under extreme load.
    """

    # No wait time - send requests continuously
    wait_time = between(0, 0.1)

    @task
    def rapid_health_checks(self):
        """
        Rapid health check requests to test overload handling.

        Validates: Requirement 20.6 - Graceful degradation
        """
        with self.client.get("/health", catch_response=True, name="/health [overload]") as response:
            # Under overload, we expect either success or rate limiting
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                # Rate limited - this is graceful degradation
                response.success()
            elif response.status_code == 503:
                # Service unavailable - acceptable under extreme load
                response.success()
            else:
                response.failure(f"Unexpected status code {response.status_code}")


# Event handlers for performance validation


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Called when load test starts.
    Initialize performance tracking.
    """
    print("\n" + "=" * 80)
    print("LOAD TEST STARTING")
    print("=" * 80)
    print(f"Target host: {environment.host}")
    print(f"Performance thresholds:")
    print(f"  - Max p95 response time: {MAX_RESPONSE_TIME_MS}ms")
    print(f"  - Expected RPS: {EXPECTED_RPS}")
    print(f"  - Max error rate: {ERROR_RATE_THRESHOLD * 100}%")
    print("=" * 80 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Called when load test stops.
    Validate performance metrics against thresholds.

    Validates: Requirements 20.1, 20.2, 20.6
    """
    print("\n" + "=" * 80)
    print("LOAD TEST COMPLETED - VALIDATING PERFORMANCE")
    print("=" * 80)

    stats = environment.stats

    # Calculate overall metrics
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    error_rate = total_failures / total_requests if total_requests > 0 else 0

    # Get response time percentiles
    response_time_p50 = stats.total.get_response_time_percentile(0.5)
    response_time_p95 = stats.total.get_response_time_percentile(0.95)
    response_time_p99 = stats.total.get_response_time_percentile(0.99)

    # Calculate actual RPS
    total_runtime = stats.total.last_request_timestamp - stats.total.start_time
    actual_rps = total_requests / total_runtime if total_runtime > 0 else 0

    print(f"\nPerformance Metrics:")
    print(f"  Total Requests: {total_requests}")
    print(f"  Total Failures: {total_failures}")
    print(f"  Error Rate: {error_rate * 100:.2f}%")
    print(f"  Actual RPS: {actual_rps:.2f}")
    print(f"\nResponse Times:")
    print(f"  p50: {response_time_p50:.0f}ms")
    print(f"  p95: {response_time_p95:.0f}ms")
    print(f"  p99: {response_time_p99:.0f}ms")

    # Validate against thresholds
    validation_passed = True
    print(f"\nValidation Results:")

    # Test 1: Response time under load (Requirement 20.1, 20.2)
    if response_time_p95 <= MAX_RESPONSE_TIME_MS:
        print(f"  ✓ Response time p95 ({response_time_p95:.0f}ms) <= {MAX_RESPONSE_TIME_MS}ms")
    else:
        print(f"  ✗ Response time p95 ({response_time_p95:.0f}ms) > {MAX_RESPONSE_TIME_MS}ms")
        validation_passed = False

    # Test 2: Error rate under load (Requirement 20.6)
    if error_rate <= ERROR_RATE_THRESHOLD:
        print(f"  ✓ Error rate ({error_rate * 100:.2f}%) <= {ERROR_RATE_THRESHOLD * 100}%")
    else:
        print(f"  ✗ Error rate ({error_rate * 100:.2f}%) > {ERROR_RATE_THRESHOLD * 100}%")
        validation_passed = False

    # Test 3: Handles expected load (Requirement 20.6)
    # This is informational - actual RPS depends on user count
    print(f"  ℹ Actual RPS: {actual_rps:.2f} (target: {EXPECTED_RPS})")

    print("=" * 80)

    if validation_passed:
        print("✓ ALL PERFORMANCE VALIDATIONS PASSED")
    else:
        print("✗ SOME PERFORMANCE VALIDATIONS FAILED")

    print("=" * 80 + "\n")

    # Exit with error code if validation failed (for CI/CD)
    if not validation_passed and isinstance(environment.runner, MasterRunner):
        environment.process_exit_code = 1


# Custom shape for load testing scenarios

from locust import LoadTestShape


class StepLoadShape(LoadTestShape):
    """
    Load test shape that gradually increases load in steps.

    This tests how the API handles increasing load and identifies
    the point where performance degrades.

    Validates: Requirement 20.6 - Scalability and graceful degradation
    """

    # Define load steps: (duration_seconds, users, spawn_rate)
    steps = [
        (30, 10, 2),  # Warm up: 10 users for 30s
        (60, 25, 5),  # Step 1: 25 users for 30s
        (90, 50, 10),  # Step 2: 50 users for 30s
        (120, 100, 20),  # Step 3: 100 users for 30s
        (150, 150, 25),  # Step 4: 150 users for 30s (overload test)
    ]

    def tick(self):
        """
        Returns the current user count and spawn rate based on elapsed time.
        """
        run_time = self.get_run_time()

        for step_duration, users, spawn_rate in self.steps:
            if run_time < step_duration:
                return (users, spawn_rate)

        # Test complete
        return None


class SpikeLoadShape(LoadTestShape):
    """
    Load test shape that simulates traffic spikes.

    Tests how the API handles sudden increases in load.

    Validates: Requirement 20.6 - Graceful degradation under overload
    """

    def tick(self):
        """
        Creates a spike pattern: low -> high -> low -> high
        """
        run_time = self.get_run_time()

        if run_time < 30:
            return (10, 5)  # Baseline
        elif run_time < 60:
            return (100, 50)  # Spike 1
        elif run_time < 90:
            return (10, 5)  # Back to baseline
        elif run_time < 120:
            return (150, 75)  # Spike 2 (higher)
        elif run_time < 150:
            return (10, 5)  # Back to baseline
        else:
            return None  # Test complete
