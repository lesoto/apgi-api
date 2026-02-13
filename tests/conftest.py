"""
Shared test fixtures and configuration for standalone API tests.

This module provides common fixtures used across unit, property-based,
and integration tests for the standalone API.
"""

import pytest
from hypothesis import settings, HealthCheck

# Configure Hypothesis profiles for property-based testing
settings.register_profile(
    "ci", max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)

settings.register_profile(
    "dev", max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)

settings.register_profile(
    "thorough", max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)

# Load the appropriate profile (default to 'dev' for faster local testing)
# Use 'ci' profile in CI environment for full 100 iterations
settings.load_profile("dev")
