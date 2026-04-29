"""
Additional tests for error_recovery.py to achieve 100% coverage.

Covers edge cases and missed branches.
"""

import asyncio
import time

import pytest

from app.services.error_recovery import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    ErrorRecoveryService,
    ExternalServiceConfig,
    RetryConfig,
    RetryService,
    get_error_recovery_service,
)


class TestRetryServiceAdditional:
    """Additional tests for RetryService to cover missed branches."""

    @pytest.mark.asyncio
    async def test_execute_with_retry_all_attempts_fail(self) -> None:
        """Test retry when all attempts fail - covers line 236 (last attempt logging)."""
        service = RetryService()
        config = RetryConfig(max_attempts=2, base_delay=0.01, jitter=False)

        async def failing_func() -> None:
            raise ValueError("always fails")

        with pytest.raises(ValueError, match="always fails"):
            await service.execute_with_retry(failing_func, config)

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_failure(self) -> None:
        """Test retry when function succeeds after initial failure."""
        service = RetryService()
        config = RetryConfig(max_attempts=3, base_delay=0.01, jitter=False)

        call_count = 0

        async def sometimes_fails() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail first time")
            return "success"

        result = await service.execute_with_retry(sometimes_fails, config)
        assert result == "success"
        assert call_count == 2

    def test_calculate_delay_without_jitter(self) -> None:
        """Test delay calculation without jitter."""
        service = RetryService()
        config = RetryConfig(base_delay=1.0, max_delay=10.0, backoff_factor=2.0, jitter=False)

        delay = service._calculate_delay(0, config)
        assert delay == 1.0

        delay = service._calculate_delay(1, config)
        assert delay == 2.0

    def test_calculate_delay_with_jitter(self) -> None:
        """Test delay calculation with jitter adds randomness."""
        service = RetryService()
        config = RetryConfig(base_delay=1.0, max_delay=10.0, backoff_factor=2.0, jitter=True)

        # With jitter, delay should be >= base delay
        delay = service._calculate_delay(0, config)
        assert delay >= 1.0
        assert delay < 1.5  # 1.0 + 25% jitter

    def test_calculate_delay_max_delay_cap(self) -> None:
        """Test delay is capped at max_delay."""
        service = RetryService()
        config = RetryConfig(base_delay=1.0, max_delay=5.0, backoff_factor=10.0, jitter=False)

        # attempt 1 would be 1.0 * 10^1 = 10.0, but capped at 5.0
        delay = service._calculate_delay(1, config)
        assert delay == 5.0


class TestCircuitBreakerAdditional:
    """Additional tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_record_success_in_half_open(self) -> None:
        """Test recording success in half-open state transitions to closed."""
        cb = CircuitBreaker(service_name="test", failure_threshold=2, recovery_timeout=0.01)

        # Force to open state
        cb.state = CircuitState.OPEN
        cb.stats.consecutive_failures = 2
        cb.stats.last_failure_time = time.time()

        # Wait for recovery timeout
        await asyncio.sleep(0.02)

        # This should transition to half_open then to closed on success
        async def success_func() -> str:
            return "success"

        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_record_failure_in_half_open(self) -> None:
        """Test recording failure in half-open state returns to open."""
        cb = CircuitBreaker(service_name="test", failure_threshold=2, recovery_timeout=0.01)

        # Force to half-open state
        cb.state = CircuitState.HALF_OPEN

        async def fail_func() -> None:
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await cb.call(fail_func)

        assert cb.state == CircuitState.OPEN

    def test_should_attempt_reset_no_failure_time(self) -> None:
        """Test should_attempt_reset when last_failure_time is None."""
        cb = CircuitBreaker(service_name="test", recovery_timeout=60.0)
        cb.stats.last_failure_time = None

        # Should return True when no failure time recorded
        assert cb._should_attempt_reset() is True

    def test_should_attempt_reset_not_enough_time(self) -> None:
        """Test should_attempt_reset when not enough time has passed."""
        cb = CircuitBreaker(service_name="test", recovery_timeout=60.0)
        cb.stats.last_failure_time = time.time()  # Just now

        # Should return False when not enough time passed
        assert cb._should_attempt_reset() is False

    def test_should_attempt_reset_enough_time(self) -> None:
        """Test should_attempt_reset when enough time has passed."""
        cb = CircuitBreaker(service_name="test", recovery_timeout=0.01)
        cb.stats.last_failure_time = time.time() - 0.02  # 20ms ago

        # Should return True when enough time passed
        assert cb._should_attempt_reset() is True

    def test_get_stats_with_zero_requests(self) -> None:
        """Test get_stats when no requests made (covers division by zero protection)."""
        cb = CircuitBreaker(service_name="test")
        stats = cb.get_stats()

        assert stats["failure_rate"] == 0
        assert stats["total_requests"] == 0

    def test_get_stats_with_requests(self) -> None:
        """Test get_stats calculates failure rate correctly."""
        cb = CircuitBreaker(service_name="test")
        cb.stats.total_requests = 10
        cb.stats.failed_requests = 3

        stats = cb.get_stats()
        assert stats["failure_rate"] == 0.3


class TestErrorRecoveryServiceAdditional:
    """Additional tests for ErrorRecoveryService."""

    @pytest.mark.asyncio
    async def test_call_unregistered_service(self) -> None:
        """Test calling unregistered service proceeds without protection."""
        service = ErrorRecoveryService()

        async def test_func() -> str:
            return "result"

        # Should work even for unregistered service
        result = await service.call_external_service("unregistered", test_func)
        assert result == "result"

    @pytest.mark.asyncio
    async def test_call_registered_service_with_circuit_breaker_none(self) -> None:
        """Test calling service with None circuit breaker raises ValueError."""
        service = ErrorRecoveryService()

        # Register service but manually set circuit_breaker to None
        config = ExternalServiceConfig(
            service_name="test", retry_config=RetryConfig(), circuit_breaker=None
        )
        service.services["test"] = config

        async def test_func() -> str:
            return "result"

        with pytest.raises(ValueError, match="Circuit breaker not configured"):
            await service.call_external_service("test", test_func)

    def test_get_service_stats_not_found(self) -> None:
        """Test get_service_stats returns None for unknown service."""
        service = ErrorRecoveryService()
        assert service.get_service_stats("unknown") is None

    def test_get_service_stats_no_circuit_breaker(self) -> None:
        """Test get_service_stats returns None when circuit breaker is None."""
        service = ErrorRecoveryService()
        config = ExternalServiceConfig(
            service_name="test", retry_config=RetryConfig(), circuit_breaker=None
        )
        service.services["test"] = config

        assert service.get_service_stats("test") is None

    def test_get_service_stats_success(self) -> None:
        """Test get_service_stats returns stats for valid service."""
        service = ErrorRecoveryService()
        cb = CircuitBreaker(service_name="test")

        service.register_service("test", circuit_breaker=cb)
        stats = service.get_service_stats("test")

        assert stats is not None
        assert stats["service_name"] == "test"
        assert "circuit_breaker" in stats
        assert "retry_config" in stats
        assert stats["retry_config"]["max_attempts"] == 3
        assert stats["retry_config"]["base_delay"] == 1.0
        assert stats["retry_config"]["max_delay"] == 60.0
        assert stats["retry_config"]["backoff_factor"] == 2.0
        assert stats["retry_config"]["jitter"] is True

    def test_get_all_stats(self) -> None:
        """Test get_all_stats returns stats for all services."""
        service = ErrorRecoveryService()

        service.register_service("service1")
        service.register_service("service2")

        all_stats = service.get_all_stats()
        assert "service1" in all_stats
        assert "service2" in all_stats

    def test_reset_circuit_breaker_success(self) -> None:
        """Test reset_circuit_breaker resets to closed state."""
        service = ErrorRecoveryService()
        cb = CircuitBreaker(service_name="test")

        # Open the circuit
        cb.state = CircuitState.OPEN
        cb.stats.consecutive_failures = 5

        service.register_service("test", circuit_breaker=cb)

        # Reset it
        service.reset_circuit_breaker("test")

        assert cb.state == CircuitState.CLOSED
        assert cb.stats.consecutive_failures == 0
        assert cb.stats.state_changes == 1

    def test_reset_circuit_breaker_no_circuit_breaker(self) -> None:
        """Test reset_circuit_breaker raises error when no circuit breaker configured."""
        service = ErrorRecoveryService()

        config = ExternalServiceConfig(
            service_name="test", retry_config=RetryConfig(), circuit_breaker=None
        )
        service.services["test"] = config

        with pytest.raises(ValueError, match="Circuit breaker not configured"):
            service.reset_circuit_breaker("test")

    def test_register_service_with_defaults(self) -> None:
        """Test register_service creates default circuit breaker and retry config."""
        service = ErrorRecoveryService()

        service.register_service("new_service")

        assert "new_service" in service.services
        config = service.services["new_service"]
        assert config.circuit_breaker is not None
        assert config.retry_config is not None

    def test_get_error_recovery_service_singleton(self) -> None:
        """Test get_error_recovery_service returns singleton instance."""
        service1 = get_error_recovery_service()
        service2 = get_error_recovery_service()
        assert service1 is service2


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError exception."""

    def test_exception_message(self) -> None:
        """Test exception can be raised with message."""
        with pytest.raises(CircuitBreakerOpenError, match="Circuit breaker is OPEN"):
            raise CircuitBreakerOpenError("Circuit breaker is OPEN for service")

    def test_exception_inheritance(self) -> None:
        """Test exception inherits from Exception."""
        err = CircuitBreakerOpenError("test")
        assert isinstance(err, Exception)
