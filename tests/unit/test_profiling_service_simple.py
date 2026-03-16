"""Simple unit tests for profiling service to achieve basic coverage.

Focuses on testing service methods and error paths without complex dependencies.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta

from app.services.profiling_service import (
    ProfilingService,
    PerformanceSnapshot,
    ProfilingResult,
)


class TestProfilingService:
    """Test profiling service."""

    @pytest.fixture
    def mock_service(self):
        """Mock profiling service."""
        return ProfilingService()

    def test_profiling_service_initialization(self, mock_service):
        """Test profiling service initialization."""
        assert mock_service.snapshots == []
        assert mock_service.max_snapshots == 1000
        assert mock_service.is_tracing_memory is False
        assert mock_service.memory_trace_started is False

    def test_start_memory_tracing_success(self, mock_service):
        """Test successful memory tracing start."""
        with patch("app.services.profiling_service.tracemalloc.start") as mock_start:
            mock_service.start_memory_tracing()

            assert mock_service.is_tracing_memory is True
            mock_start.assert_called_once()

    def test_start_memory_tracing_already_started(self, mock_service):
        """Test memory tracing start when already started."""
        mock_service.is_tracing_memory = True

        # Should not start again
        mock_service.start_memory_tracing()

        assert mock_service.is_tracing_memory is True

    def test_stop_memory_tracing_success(self, mock_service):
        """Test successful memory tracing stop."""
        mock_service.is_tracing_memory = True
        mock_service.memory_trace_started = True

        with patch("app.services.profiling_service.tracemalloc.stop") as mock_stop:
            mock_service.stop_memory_tracing()

            assert mock_service.is_tracing_memory is False
            mock_stop.assert_called_once()

    def test_stop_memory_tracing_not_started(self, mock_service):
        """Test memory tracing stop when not started."""
        mock_service.is_tracing_memory = False

        # Should not stop
        mock_service.stop_memory_tracing()

        assert mock_service.is_tracing_memory is False

    def test_get_memory_snapshot_not_started(self, mock_service):
        """Test getting memory snapshot when tracing not started."""
        result = mock_service.get_memory_snapshot()

        assert result["error"] == "Memory tracing not started"

    def test_get_memory_snapshot_success(self, mock_service):
        """Test successful memory snapshot retrieval."""
        mock_service.memory_trace_started = True

        with patch(
            "app.services.profiling_service.tracemalloc.get_traced_memory"
        ) as mock_get_memory:
            mock_get_memory.return_value = {
                "filename": "test.py",
                "lineno": 10,
                "size": 1024,
                "traceback": [],
            }

            result = mock_service.get_memory_snapshot()

            assert "filename" in result
            assert result["size"] == 1024

    def test_get_memory_snapshot_failure(self, mock_service):
        """Test memory snapshot retrieval failure."""
        mock_service.memory_trace_started = True

        with patch(
            "app.services.profiling_service.tracemalloc.get_traced_memory",
            side_effect=Exception("Memory error"),
        ):
            result = mock_service.get_memory_snapshot()

            assert "error" in result
            assert "Memory error" in result["error"]

    def test_record_performance_snapshot(self, mock_service):
        """Test recording performance snapshot."""
        mock_service.record_performance_snapshot(
            cpu_percent=50.0, memory_mb=512.0, response_time=0.1
        )

        assert len(mock_service.snapshots) == 1
        assert mock_service.snapshots[0].cpu_percent == 50.0
        assert mock_service.snapshots[0].memory_mb == 512.0
        assert mock_service.snapshots[0].response_time == 0.1

    def test_record_performance_snapshot_max_snapshots(self, mock_service):
        """Test recording performance snapshot when max reached."""
        mock_service.max_snapshots = 2

        # Add max snapshots
        mock_service.record_performance_snapshot(50.0, 512.0, 0.1)
        mock_service.record_performance_snapshot(60.0, 614.0, 0.2)

        # Add one more - should remove the oldest
        mock_service.record_performance_snapshot(70.0, 716.0, 0.3)

        assert len(mock_service.snapshots) == 2
        assert mock_service.snapshots[0].cpu_percent == 60.0  # Second snapshot
        assert mock_service.snapshots[1].cpu_percent == 70.0  # Third snapshot

    def test_get_performance_history_empty(self, mock_service):
        """Test getting performance history when no snapshots."""
        result = mock_service.get_performance_history(hours=1)

        assert result == []

    def test_get_performance_history_success(self, mock_service):
        """Test successful performance history retrieval."""
        # Add some snapshots
        now = datetime.now(timezone.utc)
        mock_service.snapshots = [
            PerformanceSnapshot(
                timestamp=now - timedelta(hours=2),
                cpu_percent=50.0,
                memory_mb=512.0,
                response_time=0.1,
            ),
            PerformanceSnapshot(
                timestamp=now - timedelta(minutes=30),
                cpu_percent=60.0,
                memory_mb=614.0,
                response_time=0.2,
            ),
            PerformanceSnapshot(
                timestamp=now, cpu_percent=70.0, memory_mb=716.0, response_time=0.3
            ),
        ]

        result = mock_service.get_performance_history(hours=1)

        assert len(result) == 2  # Only last hour
        assert result[0]["timestamp"] == (now - timedelta(minutes=30)).isoformat()
        assert result[1]["timestamp"] == now.isoformat()

    def test_get_performance_history_different_hours(self, mock_service):
        """Test performance history with different time periods."""
        now = datetime.now(timezone.utc)
        mock_service.snapshots = [
            PerformanceSnapshot(
                timestamp=now - timedelta(hours=2),
                cpu_percent=50.0,
                memory_mb=512.0,
                response_time=0.1,
            ),
            PerformanceSnapshot(
                timestamp=now - timedelta(hours=1),
                cpu_percent=60.0,
                memory_mb=614.0,
                response_time=0.2,
            ),
        ]

        result = mock_service.get_performance_history(hours=1)

        assert len(result) == 1
        assert result[0]["timestamp"] == (now - timedelta(hours=1)).isoformat()

    def test_profile_function_context_manager(self, mock_service):
        """Test profile function context manager."""
        with patch("app.services.profiling_service.cProfile") as mock_profile:
            mock_profile.return_value = Mock()
            mock_profile.return_value.get_stats.return_value = "test stats"
            mock_profile.return_value.total_calls = 5
            mock_profile.return_value.duration = 0.5

            with mock_service.profile_function() as profiler:
                pass

            assert mock_profile.return_value.enable.assert_called_once()
            assert mock_profile.return_value.disable.assert_called_once()

    def test_profile_function_with_sort_by(self, mock_service):
        """Test profile function with different sort options."""
        with patch("app.services.profiling_service.cProfile") as mock_profile:
            mock_profile.return_value = Mock()
            mock_profile.return_value.get_stats.return_value = "test stats"

            with mock_service.profile_function(sort_by="cumulative", lines=10) as profiler:
                pass

            assert mock_profile.return_value.sort_stats.assert_called_once_with("cumulative")

    def test_profile_function_with_lines(self, mock_service):
        """Test profile function with custom lines."""
        with patch("app.services.profiling_service.cProfile") as mock_profile:
            mock_profile.return_value = Mock()
            mock_profile.return_value.get_stats.return_value = "test stats"

            with mock_service.profile_function(lines=50) as profiler:
                pass

            assert mock_profile.return_value.print_stats.assert_called_once()

    def test_parse_profile_stats(self, mock_service):
        """Test parsing profile stats output."""
        stats_output = """
         ncalls  tottime  cumtime
             1    0.001    0.001  test_function
             5    0.002    0.003  another_function
        """

        result = mock_service._parse_profile_stats(stats_output)

        assert len(result) == 2
        assert result[0]["ncalls"] == 1
        assert result[0]["tottime"] == 0.001
        assert result[0]["cumtime"] == 0.001
        assert result[0]["filename"] == "test_function"
        assert result[1]["ncalls"] == 5
        assert result[1]["tottime"] == 0.002
        assert result[1]["cumtime"] == 0.003

    def test_parse_profile_stats_empty(self, mock_service):
        """Test parsing empty profile stats."""
        result = mock_service._parse_profile_stats("")

        assert result == []

    def test_get_system_performance_success(self, mock_service):
        """Test successful system performance retrieval."""
        with patch("app.services.profiling_service.psutil") as mock_psutil:
            mock_psutil.cpu_percent.return_value = 50.0
            mock_psutil.virtual_memory.return_value = 1024 * 1024 * 1024  # 1GB
            mock_psutil.disk_usage.return_value = Mock()
            mock_psutil.disk_usage.used = 500 * 1024 * 1024  # 500MB
            mock_psutil.disk_usage.free = 500 * 1024 * 1024  # 500MB

            result = mock_service.get_system_performance()

            assert result["cpu_percent"] == 50.0
            assert result["memory_mb"] == 1024.0
            assert result["disk_used_mb"] == 500.0
            assert result["disk_free_mb"] == 500.0

    def test_get_system_performance_failure(self, mock_service):
        """Test system performance retrieval failure."""
        with patch("app.services.profiling_service.psutil", side_effect=Exception("PSUtil error")):
            result = mock_service.get_system_performance()

            assert "error" in result
            assert "PSUtil error" in result["error"]

    def test_get_bottleneck_analysis_empty(self, mock_service):
        """Test bottleneck analysis when no snapshots available."""
        result = mock_service.get_bottleneck_analysis()

        assert result["error"] == "No performance snapshots available"

    def test_get_bottleneck_analysis_success(self, mock_service):
        """Test successful bottleneck analysis."""
        # Add some snapshots with varying performance
        now = datetime.now(timezone.utc)
        mock_service.snapshots = [
            PerformanceSnapshot(
                timestamp=now - timedelta(minutes=10),
                cpu_percent=80.0,
                memory_mb=1024.0,
                response_time=1.0,
            ),
            PerformanceSnapshot(
                timestamp=now - timedelta(minutes=5),
                cpu_percent=90.0,
                memory_mb=1536.0,
                response_time=2.0,
            ),
            PerformanceSnapshot(
                timestamp=now, cpu_percent=85.0, memory_mb=1280.0, response_time=1.5
            ),
        ]

        result = mock_service.get_bottleneck_analysis()

        assert "analysis" in result
        assert "avg_cpu" in result
        assert "avg_memory" in result
        assert "avg_response_time" in result
        assert result["avg_cpu"] == 85.0
        assert result["avg_memory"] == 1280.0
        assert result["avg_response_time"] == 1.5

    def test_performance_snapshot_dataclass(self):
        """Test PerformanceSnapshot dataclass."""
        timestamp = datetime.now(timezone.utc)
        snapshot = PerformanceSnapshot(
            timestamp=timestamp, cpu_percent=50.0, memory_mb=512.0, response_time=0.1
        )

        assert snapshot.timestamp == timestamp
        assert snapshot.cpu_percent == 50.0
        assert snapshot.memory_mb == 512.0
        assert snapshot.response_time == 0.1

    def test_profiling_result_dataclass(self):
        """Test ProfilingResult dataclass."""
        function_stats = [{"function": "test_function", "calls": 5, "time": 0.1}]
        result = ProfilingResult(function_stats=function_stats, duration=0.5, memory_usage=1024)

        assert result.function_stats == function_stats
        assert result.duration == 0.5
        assert result.memory_usage == 1024

    def test_edge_case_max_snapshots_zero(self, mock_service):
        """Test edge case with max_snapshots set to zero."""
        mock_service.max_snapshots = 0

        # Add a snapshot - should immediately remove it
        mock_service.record_performance_snapshot(50.0, 512.0, 0.1)

        assert len(mock_service.snapshots) == 0

    def test_edge_case_negative_hours(self, mock_service):
        """Test edge case with negative hours parameter."""
        # Add some snapshots
        mock_service.record_performance_snapshot(50.0, 512.0, 0.1)

        result = mock_service.get_performance_history(hours=-1)

        # Should return all snapshots since cutoff is in the past
        assert len(result) == 1
