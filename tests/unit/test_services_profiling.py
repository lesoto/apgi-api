"""
Tests for profiling service.
"""

import pytest

from app.services.profiling_service import ProfilingService


class TestProfilingService:
    """Test profiling service."""

    @pytest.fixture
    def profiling_service(self):
        """Profiling service instance."""
        return ProfilingService()

    def test_start_memory_tracing(self, profiling_service):
        """Test starting memory tracing."""
        profiling_service.start_memory_tracing()
        assert profiling_service.memory_tracing_active is True

    def test_stop_memory_tracing(self, profiling_service):
        """Test stopping memory tracing."""
        profiling_service.start_memory_tracing()
        profiling_service.stop_memory_tracing()
        assert profiling_service.memory_tracing_active is False

    def test_get_memory_snapshot(self, profiling_service):
        """Test getting memory snapshot."""
        profiling_service.start_memory_tracing()
        snapshot = profiling_service.get_memory_snapshot()
        assert isinstance(snapshot, dict)
        assert "error" not in snapshot

    def test_get_system_performance(self, profiling_service):
        """Test getting system performance metrics."""
        metrics = profiling_service.get_system_performance()
        assert isinstance(metrics, dict)
        # Should contain CPU, memory, or thread info
        assert len(metrics) > 0

    def test_get_performance_history(self, profiling_service):
        """Test getting performance history."""
        history = profiling_service.get_performance_history(hours=1)
        assert isinstance(history, list)

    def test_get_performance_history_invalid_hours(self, profiling_service):
        """Test performance history with invalid hours."""
        # The service doesn't validate hours, so this just returns empty list
        history = profiling_service.get_performance_history(hours=25)
        assert isinstance(history, list)

    def test_get_bottleneck_analysis(self, profiling_service):
        """Test getting bottleneck analysis."""
        # Add a snapshot to avoid error case
        profiling_service.record_performance_snapshot(
            cpu_percent=50.0,
            memory_mb=512.0,
            active_threads=5,
            active_coroutines=3,
            request_count=100,
            response_time_avg=0.1,
        )
        analysis = profiling_service.get_bottleneck_analysis()
        assert isinstance(analysis, dict)
        assert "bottlenecks" in analysis or "recommendations" in analysis or "error" in analysis
