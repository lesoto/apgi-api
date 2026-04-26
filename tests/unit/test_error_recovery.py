"""
Unit tests for error recovery service.

Tests circuit breaker, retry service, and error recovery functionality.
Validates Requirements 8.1, 8.2, 8.3.
"""

import asyncio
import time

import pytest

from app.services.error_recovery import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    ErrorRecoveryService,
    RetryConfig,
    RetryService,
    get_error_recovery_service,
)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initial_state(self) -> None:
        """Test circuit breaker starts in closed state."""
        cb = CircuitBreaker(service_name="test_service")
        assert cb.state == CircuitState.CLOSED
        assert cb.stats.total_requests == 0

    def test_circuit_breaker_with_custom_logger(self) -> None:
        """Test circuit breaker with custom logger."""
        from app.middleware.logging import StructuredLogger

        custom_logger = StructuredLogger("custom")
        cb = CircuitBreaker(service_name="test_service", logger=custom_logger)
        assert cb.logger == custom_logger

    @pytest.mark.asyncio
    async def test_call_success(self) -> None:
        """Test successful call through circuit breaker."""
        cb = CircuitBreaker(service_name="test_service")

        async def dummy_func() -> str:
            return "success"

        result = await cb.call(dummy_func)
        assert result == "success"
        assert cb.stats.successful_requests == 1
        assert cb.stats.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_call_failure(self) -> None:
        """Test failed call through circuit breaker."""
        cb = CircuitBreaker(service_name="test_service")

        async def dummy_func() -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await cb.call(dummy_func)

        assert cb.stats.failed_requests == 1
        assert cb.stats.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self) -> None:
        """Test circuit breaker opens after failure threshold."""
        cb = CircuitBreaker(service_name="test_service", failure_threshold=2)

        async def failing_func() -> None:
            raise ValueError("test error")

        # First failure
        with pytest.raises(ValueError):
            await cb.call(failing_func)

        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Third call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(failing_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self) -> None:
        """Test circuit breaker recovery in half-open state."""
        cb = CircuitBreaker(service_name="test_service", failure_threshold=2, recovery_timeout=0.1)

        async def failing_func() -> None:
            raise ValueError("test error")

        async def success_func() -> str:
            return "success"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Next call should transition to half-open and succeed
        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]

    def test_should_attempt_reset(self) -> None:
        """Test reset timing logic."""
        cb = CircuitBreaker(service_name="test_service", recovery_timeout=1.0)

        # No previous failure
        assert cb._should_attempt_reset()

        # Recent failure
        cb.stats.last_failure_time = time.time()
        assert not cb._should_attempt_reset()

        # After timeout
        cb.stats.last_failure_time = time.time() - 2.0
        assert cb._should_attempt_reset()

    def test_get_stats(self) -> None:
        """Test getting circuit breaker statistics."""
        cb = CircuitBreaker(service_name="test_service")

        stats = cb.get_stats()
        assert stats["service_name"] == "test_service"
        assert stats["state"] == "closed"
        assert stats["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_back_to_open(self) -> None:
        """Test circuit breaker goes back to open after failure in half-open state."""
        cb = CircuitBreaker(service_name="test_service", failure_threshold=2, recovery_timeout=0.1)

        async def failing_func() -> None:
            raise ValueError("test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Wait and attempt reset with failure
        await asyncio.sleep(0.2)

        with pytest.raises(ValueError):
            await cb.call(failing_func)

        assert cb.state == CircuitState.OPEN


class TestRetryService:
    """Test retry service functionality."""

    @pytest.fixture
    def retry_service(self) -> RetryService:
        """Create retry service instance."""
        return RetryService()

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_first_try(self, retry_service: RetryService) -> None:
        """Test successful execution on first try."""

        async def success_func() -> str:
            return "success"

        config = RetryConfig(max_attempts=3)
        result = await retry_service.execute_with_retry(success_func, config)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_retry(
        self, retry_service: RetryService
    ) -> None:
        """Test successful execution after retries."""
        call_count = 0

        async def intermittent_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"

        config = RetryConfig(max_attempts=3)
        result = await retry_service.execute_with_retry(intermittent_func, config)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_exhaust_retries(self, retry_service: RetryService) -> None:
        """Test execution fails after exhausting retries."""

        async def failing_func() -> None:
            raise ValueError("persistent error")

        config = RetryConfig(max_attempts=2)

        with pytest.raises(ValueError, match="persistent error"):
            await retry_service.execute_with_retry(failing_func, config)

    def test_calculate_delay_no_jitter(self, retry_service: RetryService) -> None:
        """Test delay calculation without jitter."""
        config = RetryConfig(base_delay=1.0, backoff_factor=2.0, jitter=False)

        assert retry_service._calculate_delay(0, config) == 1.0
        assert retry_service._calculate_delay(1, config) == 2.0
        assert retry_service._calculate_delay(2, config) == 4.0

    def test_calculate_delay_with_jitter(self, retry_service: RetryService) -> None:
        """Test delay calculation with jitter."""
        config = RetryConfig(base_delay=1.0, backoff_factor=2.0, jitter=True)

        delay = retry_service._calculate_delay(0, config)
        assert 1.0 <= delay <= 1.25

    def test_calculate_delay_max_delay(self, retry_service: RetryService) -> None:
        """Test delay calculation respects max delay."""
        config = RetryConfig(base_delay=10.0, max_delay=20.0, backoff_factor=10.0, jitter=False)

        delay = retry_service._calculate_delay(5, config)
        assert delay == 20.0

    @pytest.mark.asyncio
    async def test_execute_with_retry_non_retryable_exception(
        self, retry_service: RetryService
    ) -> None:
        """Test execution fails immediately on non-retryable exception."""
        config = RetryConfig(max_attempts=3, retryable_exceptions=(ValueError,))

        async def failing_func() -> None:
            raise KeyError("non-retryable error")

        with pytest.raises(KeyError, match="non-retryable error"):
            await retry_service.execute_with_retry(failing_func, config)

    @pytest.mark.asyncio
    async def test_execute_with_retry_custom_exception_list(
        self, retry_service: RetryService
    ) -> None:
        """Test execution with custom exception list."""
        config = RetryConfig(max_attempts=3, retryable_exceptions=(ValueError, KeyError))

        call_count = 0

        async def intermittent_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("temporary error")
            return "success"

        result = await retry_service.execute_with_retry(intermittent_func, config)

        assert result == "success"
        assert call_count == 2


class TestErrorRecoveryService:
    """Test error recovery service functionality."""

    @pytest.fixture
    def error_recovery_service(self) -> ErrorRecoveryService:
        """Create error recovery service instance."""
        return ErrorRecoveryService()

    def test_register_service(self, error_recovery_service: ErrorRecoveryService) -> None:
        """Test service registration."""
        error_recovery_service.register_service("test_service")

        assert "test_service" in error_recovery_service.services
        config = error_recovery_service.services["test_service"]
        assert config.service_name == "test_service"
        assert config.circuit_breaker is not None
        assert config.retry_config is not None

    def test_register_service_with_custom_config(
        self, error_recovery_service: ErrorRecoveryService
    ) -> None:
        """Test service registration with custom config."""
        retry_config = RetryConfig(max_attempts=5)
        circuit_breaker = CircuitBreaker(service_name="test_service", failure_threshold=10)

        error_recovery_service.register_service(
            "test_service", retry_config=retry_config, circuit_breaker=circuit_breaker
        )

        config = error_recovery_service.services["test_service"]
        assert config.retry_config.max_attempts == 5
        assert config.circuit_breaker is not None
        assert config.circuit_breaker.failure_threshold == 10

    @pytest.mark.asyncio
    async def test_call_external_service_unregistered(
        self, error_recovery_service: ErrorRecoveryService
    ) -> None:
        """Test calling unregistered service logs warning and proceeds."""

        async def dummy_func() -> str:
            return "success"

        result = await error_recovery_service.call_external_service("unknown_service", dummy_func)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_call_external_service_no_circuit_breaker(
        self, error_recovery_service: ErrorRecoveryService
    ) -> None:
        """Test calling service with no circuit breaker raises error."""
        error_recovery_service.register_service("test_service")

        # Manually remove circuit breaker
        service_config = error_recovery_service.services["test_service"]
        service_config.circuit_breaker = None

        async def dummy_func() -> str:
            return "success"

        with pytest.raises(ValueError, match="Circuit breaker not configured"):
            await error_recovery_service.call_external_service("test_service", dummy_func)

    @pytest.mark.asyncio
    async def test_call_external_service_registered_success(
        self, error_recovery_service: ErrorRecoveryService
    ) -> None:
        """Test successful call to registered service."""
        error_recovery_service.register_service("test_service")

        async def dummy_func() -> str:
            return "success"

        result = await error_recovery_service.call_external_service("test_service", dummy_func)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_call_external_service_registered_failure(
        self, error_recovery_service: ErrorRecoveryService
    ) -> None:
        """Test failed call to registered service."""
        error_recovery_service.register_service("test_service")

        async def failing_func() -> None:
            raise ValueError("service error")

        with pytest.raises(ValueError, match="service error"):
            await error_recovery_service.call_external_service("test_service", failing_func)

    def test_get_service_stats(self, error_recovery_service: ErrorRecoveryService) -> None:
        """Test getting service statistics."""
        error_recovery_service.register_service("test_service")

        stats = error_recovery_service.get_service_stats("test_service")

        assert stats is not None
        assert stats["service_name"] == "test_service"
        assert "circuit_breaker" in stats
        assert "retry_config" in stats

    def test_get_service_stats_unknown_service(
        self, error_recovery_service: ErrorRecoveryService
    ) -> None:
        """Test getting stats for unknown service."""
        stats = error_recovery_service.get_service_stats("unknown_service")

        assert stats is None

    def test_get_service_stats_with_circuit_breaker_data(
        self, error_recovery_service: ErrorRecoveryService
    ) -> None:
        """Test getting stats includes circuit breaker data."""
        error_recovery_service.register_service("test_service")

        # Simulate some activity
        async def dummy_func() -> str:
            return "success"

        async def failing_func() -> None:
            raise ValueError("test error")

        # Execute some calls to populate stats
        import asyncio

        asyncio.run(error_recovery_service.call_external_service("test_service", dummy_func))

        try:
            asyncio.run(error_recovery_service.call_external_service("test_service", failing_func))
        except ValueError:
            pass

        stats = error_recovery_service.get_service_stats("test_service")

        assert stats is not None
        assert stats["service_name"] == "test_service"
        assert stats["circuit_breaker"]["total_requests"] > 0

    def test_get_service_stats_no_circuit_breaker(
        self, error_recovery_service: ErrorRecoveryService
    ) -> None:
        """Test getting stats returns None when circuit breaker not configured."""
        error_recovery_service.register_service("test_service")

        # Manually remove circuit breaker
        service_config = error_recovery_service.services["test_service"]
        service_config.circuit_breaker = None

        stats = error_recovery_service.get_service_stats("test_service")

        assert stats is None

    def test_get_all_stats(self, error_recovery_service: ErrorRecoveryService) -> None:
        """Test getting all service statistics."""
        error_recovery_service.register_service("service1")
        error_recovery_service.register_service("service2")

        stats = error_recovery_service.get_all_stats()

        assert "service1" in stats
        assert "service2" in stats

    def test_reset_circuit_breaker(self, error_recovery_service: ErrorRecoveryService) -> None:
        """Test manual circuit breaker reset."""
        error_recovery_service.register_service("test_service")

        # Simulate open circuit
        cb = error_recovery_service.services["test_service"].circuit_breaker
        assert cb is not None
        cb.state = CircuitState.OPEN
        cb.stats.consecutive_failures = 5

        error_recovery_service.reset_circuit_breaker("test_service")

        assert cb.state == CircuitState.CLOSED
        assert cb.stats.consecutive_failures == 0
        assert cb.stats.state_changes == 1

    def test_reset_circuit_breaker_no_circuit_breaker(
        self, error_recovery_service: ErrorRecoveryService
    ) -> None:
        """Test reset raises error when circuit breaker not configured."""
        error_recovery_service.register_service("test_service")

        # Manually remove circuit breaker
        service_config = error_recovery_service.services["test_service"]
        service_config.circuit_breaker = None

        with pytest.raises(ValueError, match="Circuit breaker not configured"):
            error_recovery_service.reset_circuit_breaker("test_service")

    def test_reset_circuit_breaker_unknown_service(
        self, error_recovery_service: ErrorRecoveryService
    ) -> None:
        """Test reset for unknown service does nothing (no error)."""
        # Should not raise an error for unknown service
        error_recovery_service.reset_circuit_breaker("unknown_service")


def test_get_error_recovery_service() -> None:
    """Test getting global error recovery service instance."""
    service = get_error_recovery_service()
    assert isinstance(service, ErrorRecoveryService)


class TestCircuitBreakerOpenError:
    """Test circuit breaker open error."""

    def test_circuit_breaker_open_error(self) -> None:
        """Test circuit breaker open error creation."""
        error = CircuitBreakerOpenError("Circuit is open")
        assert str(error) == "Circuit is open"
