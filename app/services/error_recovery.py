"""
Error Recovery Service

Provides exponential backoff retry logic and circuit breaker patterns
for external service calls and operations.
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

from app.middleware.logging import StructuredLogger


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: int = 0


@dataclass
class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls.

    Prevents cascading failures by temporarily stopping requests to a failing service.
    """

    service_name: str
    failure_threshold: int = 5  # Open after this many consecutive failures
    recovery_timeout: float = 60.0  # Seconds to wait before trying again
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures
    success_threshold: int = 3  # Successes needed to close circuit in half-open state

    # Internal state
    state: CircuitState = CircuitState.CLOSED
    stats: CircuitBreakerStats = field(default_factory=CircuitBreakerStats)
    logger: Optional[StructuredLogger] = None

    def __post_init__(self):
        if self.logger is None:
            self.logger = StructuredLogger(f"circuit_breaker.{self.service_name}")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: The function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from the function call
        """
        self.stats.total_requests += 1

        if self.state == CircuitState.OPEN:
            if not self._should_attempt_reset():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN for {self.service_name}. "
                    f"Will retry after {self.recovery_timeout}s"
                )
            self.state = CircuitState.HALF_OPEN
            self.stats.state_changes += 1
            self.logger.info(
                "Circuit breaker transitioning to HALF_OPEN",
                service=self.service_name,
                consecutive_failures=self.stats.consecutive_failures,
            )

        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt a reset."""
        if self.stats.last_failure_time is None:
            return True
        return time.time() - self.stats.last_failure_time >= self.recovery_timeout

    def _record_success(self):
        """Record a successful call."""
        self.stats.successful_requests += 1
        self.stats.consecutive_failures = 0
        self.stats.last_success_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.stats.state_changes += 1
            self.state = CircuitState.CLOSED
            self.logger.info(
                "Circuit breaker CLOSED after successful call", service=self.service_name
            )

    def _record_failure(self):
        """Record a failed call."""
        self.stats.failed_requests += 1
        self.stats.consecutive_failures += 1
        self.stats.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.stats.state_changes += 1
            self.logger.warning(
                "Circuit breaker OPEN after failure in HALF_OPEN state", service=self.service_name
            )
        elif (
            self.state == CircuitState.CLOSED
            and self.stats.consecutive_failures >= self.failure_threshold
        ):
            self.state = CircuitState.OPEN
            self.stats.state_changes += 1
            self.logger.warning(
                "Circuit breaker OPEN after reaching failure threshold",
                service=self.service_name,
                consecutive_failures=self.stats.consecutive_failures,
                threshold=self.failure_threshold,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "service_name": self.service_name,
            "state": self.state.value,
            "total_requests": self.stats.total_requests,
            "successful_requests": self.stats.successful_requests,
            "failed_requests": self.stats.failed_requests,
            "consecutive_failures": self.stats.consecutive_failures,
            "failure_rate": (
                self.stats.failed_requests / self.stats.total_requests
                if self.stats.total_requests > 0
                else 0
            ),
            "last_failure_time": self.stats.last_failure_time,
            "last_success_time": self.stats.last_success_time,
            "state_changes": self.stats.state_changes,
        }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay between retries
    backoff_factor: float = 2.0  # Exponential backoff multiplier
    jitter: bool = True  # Add random jitter to delay
    retryable_exceptions: tuple = (Exception,)  # Exceptions to retry on


class RetryService:
    """
    Service for implementing exponential backoff retry logic.
    """

    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger("retry_service")

    async def execute_with_retry(self, func: Callable, config: RetryConfig, *args, **kwargs) -> Any:
        """
        Execute a function with exponential backoff retry.

        Args:
            func: The function to execute
            config: Retry configuration
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The function result

        Raises:
            Exception: The last exception if all retries are exhausted
        """
        last_exception = None

        for attempt in range(config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except config.retryable_exceptions as e:
                last_exception = e

                if attempt < config.max_attempts - 1:  # Not the last attempt
                    delay = self._calculate_delay(attempt, config)
                    self.logger.warning(
                        "Function call failed, retrying",
                        attempt=attempt + 1,
                        max_attempts=config.max_attempts,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        "Function call failed after all retries",
                        attempts=config.max_attempts,
                        final_error=str(e),
                    )

        # All retries exhausted
        raise last_exception

    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for exponential backoff with optional jitter."""
        delay = min(config.base_delay * (config.backoff_factor**attempt), config.max_delay)

        if config.jitter:
            # Add random jitter (±25% of delay)
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0.1, delay)  # Minimum 100ms delay


@dataclass
class ExternalServiceConfig:
    """Configuration for external service calls."""

    service_name: str
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    circuit_breaker: Optional[CircuitBreaker] = None


class ErrorRecoveryService:
    """
    Comprehensive error recovery service combining retry logic and circuit breakers.
    """

    def __init__(self):
        self.logger = StructuredLogger("error_recovery")
        self.services: Dict[str, ExternalServiceConfig] = {}
        self.retry_service = RetryService()

    def register_service(
        self,
        service_name: str,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        """
        Register an external service for error recovery.

        Args:
            service_name: Name of the service
            retry_config: Retry configuration (default if None)
            circuit_breaker: Circuit breaker instance (created if None)
        """
        if circuit_breaker is None:
            circuit_breaker = CircuitBreaker(service_name=service_name)

        if retry_config is None:
            retry_config = RetryConfig()

        self.services[service_name] = ExternalServiceConfig(
            service_name=service_name, retry_config=retry_config, circuit_breaker=circuit_breaker
        )

        self.logger.info("Registered service for error recovery", service=service_name)

    async def call_external_service(
        self, service_name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """
        Call an external service with error recovery.

        Args:
            service_name: Name of the registered service
            func: The function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The function result

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            Exception: Any exception from the function call
        """
        if service_name not in self.services:
            self.logger.warning(
                "Service not registered for error recovery, proceeding without protection",
                service=service_name,
            )
            return await func(*args, **kwargs)

        service_config = self.services[service_name]

        # Wrap the function call with circuit breaker and retry logic
        async def protected_call():
            return await self.retry_service.execute_with_retry(
                func, service_config.retry_config, *args, **kwargs
            )

        return await service_config.circuit_breaker.call(protected_call)

    def get_service_stats(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a registered service.

        Args:
            service_name: Name of the service

        Returns:
            Service statistics or None if service not found
        """
        if service_name not in self.services:
            return None

        service_config = self.services[service_name]
        return {
            "service_name": service_name,
            "circuit_breaker": service_config.circuit_breaker.get_stats(),
            "retry_config": {
                "max_attempts": service_config.retry_config.max_attempts,
                "base_delay": service_config.retry_config.base_delay,
                "max_delay": service_config.retry_config.max_delay,
                "backoff_factor": service_config.retry_config.backoff_factor,
                "jitter": service_config.retry_config.jitter,
            },
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all registered services."""
        return {name: self.get_service_stats(name) for name in self.services.keys()}

    def reset_circuit_breaker(self, service_name: str):
        """
        Manually reset a circuit breaker to closed state.

        Args:
            service_name: Name of the service
        """
        if service_name in self.services:
            service_config = self.services[service_name]
            service_config.circuit_breaker.state = CircuitState.CLOSED
            service_config.circuit_breaker.stats.consecutive_failures = 0
            service_config.circuit_breaker.stats.state_changes += 1

            self.logger.info("Circuit breaker manually reset", service=service_name)


# Global error recovery service instance
error_recovery_service = ErrorRecoveryService()


def get_error_recovery_service() -> ErrorRecoveryService:
    """
    Get the global error recovery service instance.

    Returns:
        ErrorRecoveryService instance
    """
    return error_recovery_service
