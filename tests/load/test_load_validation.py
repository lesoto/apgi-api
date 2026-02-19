"""
Pytest-based Load Test Validation

These tests can be run as part of the pytest suite to validate
performance characteristics. They use concurrent requests to simulate
load and measure response times.

**Validates: Requirements 20.1, 20.2, 20.6**

Usage:
    pytest tests/load/test_load_validation.py -v
    pytest tests/load/test_load_validation.py -v -k test_response_time
"""

import asyncio
import time
import statistics
import pytest
from httpx import AsyncClient, ASGITransport
from typing import List, Tuple

# Performance thresholds
MAX_RESPONSE_TIME_P95_MS = 1500  # p95 should be under 1.5 seconds (includes middleware overhead)
MAX_RESPONSE_TIME_P99_MS = 2500  # p99 should be under 2.5 seconds
CONCURRENT_REQUESTS = 50  # Number of concurrent requests for load tests
OVERLOAD_REQUESTS = 200  # Number of requests for overload test
MAX_ERROR_RATE = 0.05  # Maximum 5% error rate


@pytest.fixture
async def client():
    """Create test client for load tests."""
    from app.main import create_app

    app = create_app(test_mode=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def make_request(client: AsyncClient, endpoint: str) -> Tuple[int, float]:
    """
    Make a single request and measure response time.

    Args:
        client: HTTP client
        endpoint: Endpoint to request

    Returns:
        Tuple of (status_code, response_time_ms)
    """
    start_time = time.perf_counter()
    try:
        response = await client.get(endpoint)
        end_time = time.perf_counter()
        response_time_ms = (end_time - start_time) * 1000
        return (response.status_code, response_time_ms)
    except Exception as e:
        end_time = time.perf_counter()
        response_time_ms = (end_time - start_time) * 1000
        return (500, response_time_ms)


async def make_concurrent_requests(
    client: AsyncClient, endpoint: str, count: int
) -> List[Tuple[int, float]]:
    """
    Make multiple concurrent requests to an endpoint.

    Args:
        client: HTTP client
        endpoint: Endpoint to request
        count: Number of concurrent requests

    Returns:
        List of (status_code, response_time_ms) tuples
    """
    tasks = [make_request(client, endpoint) for _ in range(count)]
    results = await asyncio.gather(*tasks)
    return results


def calculate_percentile(values: List[float], percentile: float) -> float:
    """
    Calculate percentile from a list of values.

    Args:
        values: List of numeric values
        percentile: Percentile to calculate (0.0 to 1.0)

    Returns:
        Percentile value
    """
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int(len(sorted_values) * percentile)
    return sorted_values[min(index, len(sorted_values) - 1)]


class TestAPIHandlesExpectedLoad:
    """
    Test that API handles expected load (requests per second).

    Validates: Requirement 20.6 - API supports horizontal scaling
    """

    @pytest.mark.asyncio
    async def test_health_endpoint_handles_concurrent_requests(self, client):
        """
        Test that health endpoint handles concurrent requests successfully.

        Validates: Requirement 20.6 - Handle expected load
        """
        # Make concurrent requests
        results = await make_concurrent_requests(client, "/health", CONCURRENT_REQUESTS)

        # Extract status codes and response times
        status_codes = [status for status, _ in results]
        response_times = [rt for _, rt in results]

        # Calculate success rate
        successful_requests = sum(1 for status in status_codes if status == 200)
        success_rate = successful_requests / len(status_codes)

        # Validate that most requests succeeded
        assert success_rate >= (1 - MAX_ERROR_RATE), (
            f"Success rate {success_rate:.2%} is below threshold " f"{(1 - MAX_ERROR_RATE):.2%}"
        )

        # Log statistics
        print(f"\nConcurrent Requests: {CONCURRENT_REQUESTS}")
        print(f"Successful: {successful_requests}/{len(status_codes)}")
        print(f"Success Rate: {success_rate:.2%}")
        print(f"Mean Response Time: {statistics.mean(response_times):.2f}ms")

    @pytest.mark.asyncio
    async def test_readiness_endpoint_handles_concurrent_requests(self, client):
        """
        Test that readiness endpoint handles concurrent requests.

        Validates: Requirement 20.6 - Handle expected load
        """
        results = await make_concurrent_requests(client, "/v1/health/ready", CONCURRENT_REQUESTS)

        status_codes = [status for status, _ in results]

        # Readiness can return 200 or 503, both are acceptable
        acceptable_responses = sum(1 for status in status_codes if status in [200, 503])
        success_rate = acceptable_responses / len(status_codes)

        assert success_rate >= (
            1 - MAX_ERROR_RATE
        ), f"Acceptable response rate {success_rate:.2%} is below threshold"

    @pytest.mark.asyncio
    async def test_api_info_endpoint_handles_concurrent_requests(self, client):
        """
        Test that API info endpoint handles concurrent requests.

        Validates: Requirement 20.6 - Handle expected load
        """
        results = await make_concurrent_requests(client, "/", CONCURRENT_REQUESTS)

        status_codes = [status for status, _ in results]
        successful_requests = sum(1 for status in status_codes if status == 200)
        success_rate = successful_requests / len(status_codes)

        assert success_rate >= (
            1 - MAX_ERROR_RATE
        ), f"Success rate {success_rate:.2%} is below threshold"


class TestResponseTimesUnderLoad:
    """
    Test that response times remain acceptable under load.

    Validates: Requirements 20.1, 20.2 - Performance and scalability
    """

    @pytest.mark.asyncio
    async def test_health_endpoint_response_time_under_load(self, client):
        """
        Test that health endpoint response times are acceptable under load.

        Validates: Requirement 20.1, 20.2 - Response time under load
        """
        # Make concurrent requests
        results = await make_concurrent_requests(client, "/health", CONCURRENT_REQUESTS)

        # Extract response times
        response_times = [rt for _, rt in results]

        # Calculate percentiles
        p50 = calculate_percentile(response_times, 0.50)
        p95 = calculate_percentile(response_times, 0.95)
        p99 = calculate_percentile(response_times, 0.99)

        # Log statistics
        print(f"\nResponse Time Statistics (n={len(response_times)}):")
        print(f"  Min: {min(response_times):.2f}ms")
        print(f"  Mean: {statistics.mean(response_times):.2f}ms")
        print(f"  Median (p50): {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")
        print(f"  Max: {max(response_times):.2f}ms")

        # Validate response times
        assert p95 <= MAX_RESPONSE_TIME_P95_MS, (
            f"p95 response time {p95:.2f}ms exceeds threshold " f"{MAX_RESPONSE_TIME_P95_MS}ms"
        )

        assert p99 <= MAX_RESPONSE_TIME_P99_MS, (
            f"p99 response time {p99:.2f}ms exceeds threshold " f"{MAX_RESPONSE_TIME_P99_MS}ms"
        )

    @pytest.mark.asyncio
    async def test_readiness_endpoint_response_time_under_load(self, client):
        """
        Test that readiness endpoint response times are acceptable.

        Validates: Requirement 20.1, 20.2 - Response time under load
        """
        results = await make_concurrent_requests(client, "/v1/health/ready", CONCURRENT_REQUESTS)

        response_times = [rt for _, rt in results]

        p95 = calculate_percentile(response_times, 0.95)
        p99 = calculate_percentile(response_times, 0.99)

        print(f"\nReadiness Check Response Times:")
        print(f"  Mean: {statistics.mean(response_times):.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        # Readiness checks may be slower due to dependency checks
        # Allow 2x the normal threshold
        assert p95 <= MAX_RESPONSE_TIME_P95_MS * 2, (
            f"p95 response time {p95:.2f}ms exceeds threshold " f"{MAX_RESPONSE_TIME_P95_MS * 2}ms"
        )

    @pytest.mark.asyncio
    async def test_api_info_endpoint_response_time_under_load(self, client):
        """
        Test that API info endpoint response times are acceptable.

        Validates: Requirement 20.1, 20.2 - Response time under load
        """
        results = await make_concurrent_requests(client, "/", CONCURRENT_REQUESTS)

        response_times = [rt for _, rt in results]

        p95 = calculate_percentile(response_times, 0.95)
        p99 = calculate_percentile(response_times, 0.99)

        print(f"\nAPI Info Response Times:")
        print(f"  Mean: {statistics.mean(response_times):.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        assert p95 <= MAX_RESPONSE_TIME_P95_MS, (
            f"p95 response time {p95:.2f}ms exceeds threshold " f"{MAX_RESPONSE_TIME_P95_MS}ms"
        )


class TestGracefulDegradationUnderOverload:
    """
    Test that API degrades gracefully under overload conditions.

    Validates: Requirement 20.6 - Graceful degradation under overload
    """

    @pytest.mark.asyncio
    async def test_health_endpoint_graceful_degradation(self, client):
        """
        Test that health endpoint degrades gracefully under extreme load.

        Under overload, the API should either:
        - Continue serving requests successfully
        - Return 429 (rate limited)
        - Return 503 (service unavailable)

        It should NOT crash or hang indefinitely.

        Validates: Requirement 20.6 - Graceful degradation
        """
        # Send many concurrent requests to simulate overload
        results = await make_concurrent_requests(client, "/health", OVERLOAD_REQUESTS)

        status_codes = [status for status, _ in results]
        response_times = [rt for _, rt in results]

        # Count response types
        success_count = sum(1 for status in status_codes if status == 200)
        rate_limited_count = sum(1 for status in status_codes if status == 429)
        unavailable_count = sum(1 for status in status_codes if status == 503)
        error_count = sum(1 for status in status_codes if status not in [200, 429, 503])

        # Calculate rates
        total = len(status_codes)
        success_rate = success_count / total
        graceful_degradation_rate = (success_count + rate_limited_count + unavailable_count) / total

        print(f"\nOverload Test Results (n={total}):")
        print(f"  Successful (200): {success_count} ({success_count/total:.1%})")
        print(f"  Rate Limited (429): {rate_limited_count} ({rate_limited_count/total:.1%})")
        print(f"  Unavailable (503): {unavailable_count} ({unavailable_count/total:.1%})")
        print(f"  Errors (other): {error_count} ({error_count/total:.1%})")
        print(f"  Graceful Degradation Rate: {graceful_degradation_rate:.1%}")

        # Validate graceful degradation
        # Under overload, we expect mostly successful responses or graceful errors
        assert graceful_degradation_rate >= 0.90, (
            f"Graceful degradation rate {graceful_degradation_rate:.1%} is too low. "
            f"API should handle overload with 200, 429, or 503 responses."
        )

        # Validate that response times are still reasonable
        # Even under overload, responses shouldn't hang indefinitely
        max_response_time = max(response_times)
        assert max_response_time <= 10000, (  # 10 seconds max
            f"Maximum response time {max_response_time:.2f}ms is too high. "
            f"API should fail fast under overload, not hang."
        )

    @pytest.mark.asyncio
    async def test_multiple_endpoints_under_load(self, client):
        """
        Test that multiple endpoints can handle concurrent load.

        Validates: Requirement 20.6 - System-wide performance under load
        """
        # Test multiple endpoints concurrently
        endpoints = [
            "/health",
            "/v1/health/ready",
            "/v1/health/live",
            "/",
            "/v1/version",
        ]

        # Make requests to all endpoints concurrently
        all_tasks = []
        for endpoint in endpoints:
            tasks = [make_request(client, endpoint) for _ in range(20)]
            all_tasks.extend(tasks)

        results = await asyncio.gather(*all_tasks)

        status_codes = [status for status, _ in results]
        response_times = [rt for _, rt in results]

        # Calculate success rate (200, 429, 503 are acceptable)
        acceptable_responses = sum(1 for status in status_codes if status in [200, 429, 503])
        success_rate = acceptable_responses / len(status_codes)

        print(f"\nMulti-Endpoint Load Test (n={len(results)}):")
        print(f"  Endpoints tested: {len(endpoints)}")
        print(f"  Total requests: {len(results)}")
        print(f"  Acceptable responses: {acceptable_responses}")
        print(f"  Success rate: {success_rate:.1%}")
        print(f"  Mean response time: {statistics.mean(response_times):.2f}ms")

        assert success_rate >= 0.90, f"Success rate {success_rate:.1%} is too low under mixed load"

    @pytest.mark.asyncio
    async def test_sustained_load(self, client):
        """
        Test that API can handle sustained load over time.

        Validates: Requirement 20.6 - Sustained performance
        """
        # Run multiple rounds of requests to simulate sustained load
        rounds = 5
        requests_per_round = 20

        all_response_times = []
        all_status_codes = []

        for round_num in range(rounds):
            results = await make_concurrent_requests(client, "/health", requests_per_round)

            status_codes = [status for status, _ in results]
            response_times = [rt for _, rt in results]

            all_status_codes.extend(status_codes)
            all_response_times.extend(response_times)

            # Small delay between rounds
            await asyncio.sleep(0.1)

        # Calculate overall statistics
        success_count = sum(1 for status in all_status_codes if status == 200)
        success_rate = success_count / len(all_status_codes)

        p95 = calculate_percentile(all_response_times, 0.95)

        print(f"\nSustained Load Test:")
        print(f"  Rounds: {rounds}")
        print(f"  Total requests: {len(all_status_codes)}")
        print(f"  Success rate: {success_rate:.1%}")
        print(f"  Mean response time: {statistics.mean(all_response_times):.2f}ms")
        print(f"  p95 response time: {p95:.2f}ms")

        # Validate sustained performance
        assert success_rate >= (
            1 - MAX_ERROR_RATE
        ), f"Success rate {success_rate:.1%} degraded under sustained load"

        assert (
            p95 <= MAX_RESPONSE_TIME_P95_MS
        ), f"p95 response time {p95:.2f}ms degraded under sustained load"
