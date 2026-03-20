"""
Unit tests for profiling service.
"""

import pytest
from unittest.mock import Mock
from app.services.profiling_service import ProfilingService


class TestProfilingService:
    """Test profiling service."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def service(self):
        """Create profiling service instance."""
        return ProfilingService()

    def test_collect_performance_data(self, service):
        """Test performance data collection."""
        data = service.collect_performance_data("endpoint123")

        assert data is not None
        assert "endpoint_id" in data
        assert "timestamp" in data

    def test_profiling_aggregation_logic(self, service):
        """Test profiling aggregation logic."""
        data_points = [
            {"endpoint_id": "endpoint1", "duration": 100},
            {"endpoint_id": "endpoint1", "duration": 150},
            {"endpoint_id": "endpoint2", "duration": 200},
        ]

        aggregated = service.aggregate_profiling_data(data_points)

        assert aggregated["endpoint1"]["avg_duration"] == 125
        assert aggregated["endpoint2"]["avg_duration"] == 200

    def test_report_generation(self, service):
        """Test profiling report generation."""
        data = {
            "endpoint1": {"avg_duration": 125, "max_duration": 200, "min_duration": 50},
            "endpoint2": {"avg_duration": 200, "max_duration": 300, "min_duration": 100},
        }

        report = service.generate_profiling_report(data)

        assert report is not None
        assert "endpoints" in report

    def test_profiling_overhead_measurement(self, service):
        """Test profiling overhead measurement."""
        overhead = service.measure_profiling_overhead()

        assert overhead >= 0
        assert overhead < 1  # Should be less than 1 second

    def test_sampling_strategies(self, service):
        """Test different sampling strategies."""
        strategies = ["random", "systematic", "stratified"]

        for strategy in strategies:
            sample = service.apply_sampling_strategy(strategy, 1000, 100)
            assert len(sample) == 100

    def test_profiling_data_collection(self, service):
        """Test performance data collection."""
        endpoint_id = "test_endpoint"
        duration = 150

        data = service.collect_endpoint_data(endpoint_id, duration)

        assert data["endpoint_id"] == endpoint_id
        assert data["duration"] == duration

    def test_profiling_data_storage(self, service):
        """Test profiling data storage."""
        data = {"endpoint_id": "endpoint123", "duration": 150}

        service.store_profiling_data(data)

        # Should not raise any errors

    def test_profiling_data_retrieval(self, service):
        """Test profiling data retrieval."""
        endpoint_id = "endpoint123"

        data = service.retrieve_profiling_data(endpoint_id)

        assert data is not None

    def test_profiling_data_cleanup(self, service):
        """Test profiling data cleanup."""
        days_old = 30

        service.cleanup_old_profiling_data(days_old)

        # Should not raise any errors

    def test_profiling_statistics(self, service):
        """Test profiling statistics calculation."""
        data = [100, 150, 200, 175, 125]

        stats = service.calculate_statistics(data)

        assert "mean" in stats
        assert "median" in stats
        assert "std_dev" in stats

    def test_profiling_percentiles(self, service):
        """Test profiling percentiles calculation."""
        data = [100, 150, 200, 175, 125]

        percentiles = service.calculate_percentiles(data, [50, 90, 95, 99])

        assert 50 in percentiles
        assert 90 in percentiles

    def test_profiling_outlier_detection(self, service):
        """Test profiling outlier detection."""
        data = [100, 105, 110, 95, 1000]

        outliers = service.detect_outliers(data)

        assert 1000 in outliers

    def test_profiling_trend_analysis(self, service):
        """Test profiling trend analysis."""
        data = [
            {"timestamp": "2024-01-01", "avg_duration": 100},
            {"timestamp": "2024-01-02", "avg_duration": 105},
            {"timestamp": "2024-01-03", "avg_duration": 110},
        ]

        trend = service.analyze_trend(data)

        assert trend["direction"] in ["increasing", "decreasing", "stable"]

    def test_profiling_comparison(self, service):
        """Test profiling comparison between endpoints."""
        data1 = [100, 105, 110, 95, 100]
        data2 = [150, 155, 160, 145, 150]

        comparison = service.compare_profiling_data(data1, data2)

        assert "difference" in comparison
        assert "percent_change" in comparison

    def test_profiling_alerting(self, service):
        """Test profiling alerting for slow endpoints."""
        data = {"endpoint_id": "endpoint123", "avg_duration": 5000}

        alert = service.check_profiling_alerts(data, threshold=1000)

        assert alert["is_alert"] is True

    def test_profiling_optimization_suggestions(self, service):
        """Test profiling optimization suggestions."""
        data = {"endpoint_id": "endpoint123", "avg_duration": 500}

        suggestions = service.get_optimization_suggestions(data)

        assert len(suggestions) > 0

    def test_profiling_export(self, service):
        """Test profiling data export."""
        data = {"endpoint123": {"avg_duration": 150}}

        exported = service.export_profiling_data(data, "json")

        assert exported is not None

    def test_profiling_import(self, service):
        """Test profiling data import."""
        data = {"endpoint123": {"avg_duration": 150}}

        service.import_profiling_data(data)

        # Should not raise any errors

    def test_profiling_aggregation_by_time(self, service):
        """Test profiling aggregation by time period."""
        data = [
            {"timestamp": "2024-01-01T00:00:00", "duration": 100},
            {"timestamp": "2024-01-01T01:00:00", "duration": 105},
            {"timestamp": "2024-01-02T00:00:00", "duration": 110},
        ]

        aggregated = service.aggregate_by_time_period(data, "hourly")

        assert len(aggregated) > 0

    def test_profiling_aggregation_by_endpoint(self, service):
        """Test profiling aggregation by endpoint."""
        data = [
            {"endpoint_id": "endpoint1", "duration": 100},
            {"endpoint_id": "endpoint1", "duration": 150},
            {"endpoint_id": "endpoint2", "duration": 200},
        ]

        aggregated = service.aggregate_by_endpoint(data)

        assert "endpoint1" in aggregated
        assert "endpoint2" in aggregated

    def test_profiling_real_time_monitoring(self, service):
        """Test real-time profiling monitoring."""
        endpoint_id = "endpoint123"

        metrics = service.get_real_time_metrics(endpoint_id)

        assert metrics is not None

    def test_profiling_memory_tracking(self, service):
        """Test memory usage tracking."""
        data = service.track_memory_usage()

        assert "memory_mb" in data
        assert "timestamp" in data

    def test_profiling_cpu_tracking(self, service):
        """Test CPU usage tracking."""
        data = service.track_cpu_usage()

        assert "cpu_percent" in data
        assert "timestamp" in data

    def test_profiling_io_tracking(self, service):
        """Test I/O tracking."""
        data = service.track_io_operations()

        assert "read_count" in data
        assert "write_count" in data

    def test_profiling_database_queries(self, service):
        """Test database query profiling."""
        query = "SELECT * FROM users WHERE id = 123"

        data = service.profile_database_query(query)

        assert data is not None
        assert "duration" in data

    def test_profiling_cache_performance(self, service):
        """Test cache performance profiling."""
        data = service.profile_cache_performance()

        assert "hit_rate" in data
        assert "miss_rate" in data

    def test_profiling_network_latency(self, service):
        """Test network latency profiling."""
        url = "https://api.example.com/endpoint"

        latency = service.measure_network_latency(url)

        assert latency >= 0

    def test_profiling_concurrent_requests(self, service):
        """Test concurrent request profiling."""
        data = service.profile_concurrent_requests(10)

        assert data is not None
        assert "avg_duration" in data

    def test_profiling_error_tracking(self, service):
        """Test error tracking in profiling."""
        error_data = {"endpoint_id": "endpoint123", "error": "Timeout", "timestamp": "2024-01-01"}

        service.track_profiling_error(error_data)

        # Should not raise any errors

    def test_profiling_error_analysis(self, service):
        """Test error analysis in profiling."""
        endpoint_id = "endpoint123"

        analysis = service.analyze_profiling_errors(endpoint_id)

        assert analysis is not None

    def test_profiling_custom_metrics(self, service):
        """Test custom metrics collection."""
        metrics = {"custom_metric1": 100, "custom_metric2": 200}

        service.collect_custom_metrics(metrics)

        # Should not raise any errors

    def test_profiling_dashboard_data(self, service):
        """Test dashboard data preparation."""
        data = service.prepare_dashboard_data()

        assert data is not None
        assert "endpoints" in data
        assert "overall_stats" in data

    def test_profiling_anomaly_detection(self, service):
        """Test anomaly detection in profiling data."""
        data = [100, 105, 110, 95, 1000]

        anomalies = service.detect_profiling_anomalies(data)

        assert len(anomalies) > 0

    def test_profiling_capacity_planning(self, service):
        """Test capacity planning based on profiling."""
        data = {"avg_duration": 150, "max_duration": 500}

        capacity = service.calculate_capacity_requirements(data)

        assert capacity is not None

    def test_profiling_cost_analysis(self, service):
        """Test cost analysis based on profiling."""
        data = {"cpu_hours": 10, "memory_gb": 5}

        cost = service.calculate_resource_cost(data)

        assert cost is not None

    def test_profiling_sla_compliance(self, service):
        """Test SLA compliance checking."""
        sla_threshold = 1000
        actual_duration = 1500

        is_compliant = service.check_sla_compliance(actual_duration, sla_threshold)

        assert is_compliant is False

    def test_profiling_recommendations(self, service):
        """Test profiling recommendations."""
        data = {"endpoint_id": "endpoint123", "avg_duration": 500}

        recommendations = service.get_profiling_recommendations(data)

        assert len(recommendations) > 0

    def test_profiling_automation(self, service):
        """Test automated profiling actions."""
        endpoint_id = "endpoint123"

        service.automate_profiling_actions(endpoint_id)

        # Should not raise any errors

    def test_profiling_integration(self, service):
        """Test profiling integration with monitoring."""
        data = service.integrate_with_monitoring()

        assert data is not None

    def test_profiling_health_check(self, service):
        """Test profiling service health check."""
        is_healthy = service.health_check()

        assert is_healthy is True

    def test_profiling_configuration(self, service):
        """Test profiling configuration management."""
        config = {"enabled": True, "sample_rate": 0.1}

        service.update_configuration(config)

        # Should not raise any errors

    def test_profiling_backup(self, service):
        """Test profiling data backup."""
        service.backup_profiling_data()

        # Should not raise any errors

    def test_profiling_restore(self, service):
        """Test profiling data restore."""
        service.restore_profiling_data("backup_2024-01-01.json")

        # Should not raise any errors

    def test_profiling_cleanup_old_data(self, service):
        """Test cleanup of old profiling data."""
        days_old = 30

        service.cleanup_old_profiling_data(days_old)

        # Should not raise any errors

    def test_profiling_archive(self, service):
        """Test profiling data archiving."""
        service.archive_profiling_data()

        # Should not raise any errors

    def test_profiling_retention_policy(self, service):
        """Test profiling data retention policy."""
        policy = {"days": 30, "archive": True}

        service.apply_retention_policy(policy)

        # Should not raise any errors


# ---------------------------------------------------------------------------
# Tests merged from test_profiling_service_simple.py
# ---------------------------------------------------------------------------
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from app.services.profiling_service import (
    PerformanceSnapshot,
    ProfilingResult,
)


class TestProfilingServiceCore:
    """Core unit tests for ProfilingService (merged from test_profiling_service_simple.py)."""

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
            cpu_percent=50.0,
            memory_mb=512.0,
            active_threads=5,
            active_coroutines=3,
            request_count=100,
            response_time_avg=0.1,
        )

        assert len(mock_service.snapshots) == 1
        assert mock_service.snapshots[0].cpu_percent == 50.0
        assert mock_service.snapshots[0].memory_mb == 512.0
        assert mock_service.snapshots[0].response_time_avg == 0.1

    def test_record_performance_snapshot_max_snapshots(self, mock_service):
        """Test recording performance snapshot when max reached."""
        mock_service.max_snapshots = 2

        # Add max snapshots
        mock_service.record_performance_snapshot(50.0, 512.0, 5, 3, 100, 0.1)
        mock_service.record_performance_snapshot(60.0, 614.0, 6, 4, 120, 0.2)

        # Add one more - should remove the oldest
        mock_service.record_performance_snapshot(70.0, 716.0, 7, 5, 140, 0.3)

        assert len(mock_service.snapshots) == 2
        assert mock_service.snapshots[0].cpu_percent == 60.0  # Second snapshot
        assert mock_service.snapshots[1].cpu_percent == 70.0  # Third snapshot

    def test_get_performance_history_empty(self, mock_service):
        """Test getting performance history when no snapshots."""
        result = mock_service.get_performance_history(hours=1)

        assert result == []

    def test_get_performance_history_success(self, mock_service):
        """Test successful performance history retrieval."""
        now = datetime.now(timezone.utc)
        mock_service.snapshots = [
            PerformanceSnapshot(
                timestamp=now - timedelta(hours=2),
                cpu_percent=50.0,
                memory_mb=512.0,
                active_threads=5,
                active_coroutines=3,
                request_count=100,
                response_time_avg=0.1,
            ),
            PerformanceSnapshot(
                timestamp=now - timedelta(minutes=30),
                cpu_percent=60.0,
                memory_mb=614.0,
                active_threads=6,
                active_coroutines=4,
                request_count=120,
                response_time_avg=0.2,
            ),
            PerformanceSnapshot(
                timestamp=now,
                cpu_percent=70.0,
                memory_mb=716.0,
                active_threads=7,
                active_coroutines=5,
                request_count=140,
                response_time_avg=0.3,
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
                active_threads=5,
                active_coroutines=3,
                request_count=100,
                response_time_avg=0.1,
            ),
            PerformanceSnapshot(
                timestamp=now - timedelta(hours=1),
                cpu_percent=60.0,
                memory_mb=614.0,
                active_threads=6,
                active_coroutines=4,
                request_count=120,
                response_time_avg=0.2,
            ),
        ]

        result = mock_service.get_performance_history(hours=1)

        assert len(result) == 1
        assert result[0]["timestamp"] == (now - timedelta(hours=1)).isoformat()

    def test_get_bottleneck_analysis_empty(self, mock_service):
        """Test bottleneck analysis when no snapshots available."""
        result = mock_service.get_bottleneck_analysis()

        assert result["error"] == "No performance snapshots available"

    def test_get_bottleneck_analysis_success(self, mock_service):
        """Test successful bottleneck analysis."""
        now = datetime.now(timezone.utc)
        mock_service.snapshots = [
            PerformanceSnapshot(
                timestamp=now - timedelta(minutes=10),
                cpu_percent=80.0,
                memory_mb=1024.0,
                active_threads=8,
                active_coroutines=6,
                request_count=200,
                response_time_avg=1.0,
            ),
            PerformanceSnapshot(
                timestamp=now - timedelta(minutes=5),
                cpu_percent=90.0,
                memory_mb=1536.0,
                active_threads=9,
                active_coroutines=7,
                request_count=250,
                response_time_avg=2.0,
            ),
            PerformanceSnapshot(
                timestamp=now,
                cpu_percent=85.0,
                memory_mb=1280.0,
                active_threads=8,
                active_coroutines=6,
                request_count=225,
                response_time_avg=1.5,
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
            timestamp=timestamp,
            cpu_percent=50.0,
            memory_mb=512.0,
            active_threads=5,
            active_coroutines=3,
            request_count=100,
            response_time_avg=0.1,
        )

        assert snapshot.timestamp == timestamp
        assert snapshot.cpu_percent == 50.0
        assert snapshot.memory_mb == 512.0
        assert snapshot.response_time_avg == 0.1

    def test_profiling_result_dataclass(self):
        """Test ProfilingResult dataclass."""
        function_stats = [{"function": "test_function", "calls": 5, "time": 0.1}]
        result = ProfilingResult(
            function_stats=function_stats,
            total_calls=5,
            total_time=0.5,
            memory_peak=1024,
            duration=0.5,
        )

        assert result.function_stats == function_stats
        assert result.total_calls == 5
        assert result.total_time == 0.5
        assert result.memory_peak == 1024
        assert result.duration == 0.5

    def test_edge_case_max_snapshots_zero(self, mock_service):
        """Test edge case with max_snapshots set to zero."""
        mock_service.max_snapshots = 0

        # Add a snapshot - should immediately remove it
        mock_service.record_performance_snapshot(50.0, 512.0, 5, 3, 100, 0.1)

        assert len(mock_service.snapshots) == 0

    def test_edge_case_negative_hours(self, mock_service):
        """Test edge case with negative hours parameter."""
        # Add some snapshots
        mock_service.record_performance_snapshot(50.0, 512.0, 5, 3, 100, 0.1)

        result = mock_service.get_performance_history(hours=-1)

        # Should return all snapshots since cutoff is in the past
        assert len(result) == 1
