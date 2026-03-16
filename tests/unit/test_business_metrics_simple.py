"""Simple unit tests for business metrics service to achieve basic coverage.

Focuses on testing service methods and error paths without complex dependencies.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.services.business_metrics import (
    BusinessMetricsService,
    MetricValue,
    TimeSeriesPoint,
)


class TestBusinessMetricsService:
    """Test business metrics service."""

    @pytest.fixture
    def mock_service(self):
        """Mock business metrics service."""
        return BusinessMetricsService()

    def test_business_metrics_service_initialization(self, mock_service):
        """Test business metrics service initialization."""
        assert mock_service.cache_ttl == 900
        assert mock_service.cache_service is not None

    def test_generate_cache_key(self, mock_service):
        """Test cache key generation."""
        key = mock_service._generate_cache_key("test_method", "arg1", "arg2", param="value")

        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hash length

    def test_generate_cache_key_empty(self, mock_service):
        """Test cache key generation with no args."""
        key = mock_service._generate_cache_key("test_method")

        assert isinstance(key, str)
        assert len(key) == 32

    @pytest.mark.asyncio
    async def test_get_cached_or_compute_cache_hit(self, mock_service):
        """Test getting from cache when cache hit."""
        cache_key = "test_key"
        expected_result = {"data": "test"}

        with patch.object(mock_service.cache_service, "get", return_value=expected_result):
            result = await mock_service._get_cached_or_compute(cache_key, lambda: {"data": "new"})

            assert result == expected_result

    @pytest.mark.asyncio
    async def test_get_cached_or_compute_cache_miss(self, mock_service):
        """Test computing when cache miss."""
        cache_key = "test_key"
        expected_result = {"data": "test"}

        with patch.object(mock_service.cache_service, "get", return_value=None), patch.object(
            mock_service.cache_service, "set"
        ) as mock_set:

            def compute_func():
                return expected_result

            result = await mock_service._get_cached_or_compute(cache_key, compute_func)

            assert result == expected_result
            mock_set.assert_called_once_with(cache_key, expected_result, ttl=mock_service.cache_ttl)

    @pytest.mark.asyncio
    async def test_get_overview_metrics(self, mock_service):
        """Test getting overview metrics."""
        with patch.object(mock_service, "_get_cached_or_compute") as mock_cached:
            mock_cached.return_value = {
                "total_users": 100,
                "active_sessions": 50,
                "total_tasks": 200,
                "completed_tasks": 150,
            }

            result = await mock_service.get_overview_metrics()

            assert result["total_users"] == 100
            assert result["active_sessions"] == 50
            assert result["total_tasks"] == 200
            assert result["completed_tasks"] == 150

    def test_get_session_metrics(self, mock_service):
        """Test getting session metrics."""
        with patch("app.services.business_metrics.get_db_context") as mock_db_context:
            mock_db = Mock(spec=Session)
            mock_db_context.return_value.__enter__.return_value = mock_db
            mock_db_context.return_value.__exit__.return_value = None

            # Mock database queries
            mock_db.query.return_value.filter.return_value.count.return_value.scalar.return_value = (
                100
            )
            mock_db.query.return_value.filter.return_value.count.return_value.distinct.return_value.count.return_value.scalar.return_value = (
                50
            )

            result = mock_service.get_session_metrics(days=30)

            assert "total_sessions" in result
            assert "active_sessions" in result
            assert "session_timeline" in result

    def test_get_task_metrics(self, mock_service):
        """Test getting task metrics."""
        with patch("app.services.business_metrics.get_db_context") as mock_db_context:
            mock_db = Mock(spec=Session)
            mock_db_context.return_value.__enter__.return_value = mock_db
            mock_db_context.return_value.__exit__.return_value = None

            # Mock database queries
            mock_db.query.return_value.filter.return_value.count.return_value.scalar.return_value = (
                200
            )
            mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value.scalar.return_value = (
                150
            )

            result = mock_service.get_task_metrics(days=30)

            assert "total_tasks" in result
            assert "completed_tasks" in result
            assert "task_timeline" in result

    def test_get_user_metrics(self, mock_service):
        """Test getting user metrics."""
        with patch("app.services.business_metrics.get_db_context") as mock_db_context:
            mock_db = Mock(spec=Session)
            mock_db_context.return_value.__enter__.return_value = mock_db
            mock_db_context.return_value.__exit__.return_value = None

            # Mock database queries
            mock_db.query.return_value.filter.return_value.count.return_value.scalar.return_value = (
                100
            )
            mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value.scalar.return_value = (
                80
            )

            result = mock_service.get_user_metrics(days=30)

            assert "total_users" in result
            assert "active_users" in result
            assert "users_by_role" in result

    def test_get_template_metrics(self, mock_service):
        """Test getting template metrics."""
        with patch("app.services.business_metrics.get_db_context") as mock_db_context:
            mock_db = Mock(spec=Session)
            mock_db_context.return_value.__enter__.return_value = mock_db
            mock_db_context.return_value.__exit__.return_value = None

            # Mock database queries
            mock_db.query.return_value.filter.return_value.count.return_value.scalar.return_value = (
                50
            )
            mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value.scalar.return_value = (
                30
            )

            result = mock_service.get_template_metrics(days=30)

            assert "total_templates" in result
            assert "active_templates" in result
            assert "template_usage" in result

    def test_get_dashboard_data(self, mock_service):
        """Test getting complete dashboard data."""
        with patch.object(mock_service, "get_overview_metrics") as mock_overview, patch.object(
            mock_service, "get_session_metrics"
        ) as mock_sessions, patch.object(
            mock_service, "get_task_metrics"
        ) as mock_tasks, patch.object(
            mock_service, "get_user_metrics"
        ) as mock_users, patch.object(
            mock_service, "get_template_metrics"
        ) as mock_templates:
            mock_overview.return_value = {"total_users": 100}
            mock_sessions.return_value = {"total_sessions": 50}
            mock_tasks.return_value = {"total_tasks": 200}
            mock_users.return_value = {"active_users": 80}
            mock_templates.return_value = {"total_templates": 30}

            result = mock_service.get_dashboard_data(days=30)

            assert result["overview"] == {"total_users": 100}
            assert result["sessions"] == {"total_sessions": 50}
            assert result["tasks"] == {"total_tasks": 200}
            assert result["users"] == {"active_users": 80}
            assert result["templates"] == {"total_templates": 30}
            assert result["generated_at"] is not None

    def test_get_session_metrics_default_days(self, mock_service):
        """Test session metrics with default days."""
        with patch("app.services.business_metrics.get_db_context") as mock_db_context:
            mock_db = Mock(spec=Session)
            mock_db_context.return_value.__enter__.return_value = mock_db
            mock_db_context.return_value.__exit__.return_value = None

            mock_db.query.return_value.filter.return_value.count.return_value.scalar.return_value = (
                100
            )

            result = mock_service.get_session_metrics()  # No days parameter

            assert "total_sessions" in result

    def test_get_task_metrics_default_days(self, mock_service):
        """Test task metrics with default days."""
        with patch("app.services.business_metrics.get_db_context") as mock_db_context:
            mock_db = Mock(spec=Session)
            mock_db_context.return_value.__enter__.return_value = mock_db
            mock_db_context.return_value.__exit__.return_value = None

            mock_db.query.return_value.filter.return_value.count.return_value.scalar.return_value = (
                200
            )

            result = mock_service.get_task_metrics()  # No days parameter

            assert "total_tasks" in result

    def test_get_user_metrics_default_days(self, mock_service):
        """Test user metrics with default days."""
        with patch("app.services.business_metrics.get_db_context") as mock_db_context:
            mock_db = Mock(spec=Session)
            mock_db_context.return_value.__enter__.return_value = mock_db
            mock_db_context.return_value.__exit__.return_value = None

            mock_db.query.return_value.filter.return_value.count.return_value.scalar.return_value = (
                100
            )

            result = mock_service.get_user_metrics()  # No days parameter

            assert "total_users" in result

    def test_get_template_metrics_default_days(self, mock_service):
        """Test template metrics with default days."""
        with patch("app.services.business_metrics.get_db_context") as mock_db_context:
            mock_db = Mock(spec=Session)
            mock_db_context.return_value.__enter__.return_value = mock_db
            mock_db_context.return_value.__exit__.return_value = None

            mock_db.query.return_value.filter.return_value.count.return_value.scalar.return_value = (
                50
            )

            result = mock_service.get_template_metrics()  # No days parameter

            assert "total_templates" in result

    def test_get_dashboard_data_default_days(self, mock_service):
        """Test dashboard data with default days."""
        with patch.object(mock_service, "get_overview_metrics"), patch.object(
            mock_service, "get_session_metrics"
        ), patch.object(mock_service, "get_task_metrics"), patch.object(
            mock_service, "get_user_metrics"
        ), patch.object(
            mock_service, "get_template_metrics"
        ):
            result = mock_service.get_dashboard_data()  # No days parameter

            assert "overview" in result
            assert "sessions" in result
            assert "tasks" in result
            assert "users" in result
            assert "templates" in result

    def test_metric_value_dataclass(self):
        """Test MetricValue dataclass."""
        metric = MetricValue(
            value=100, label="test_metric", description="A test metric", unit="count"
        )

        assert metric.value == 100
        assert metric.label == "test_metric"
        assert metric.description == "A test metric"
        assert metric.unit == "count"

    def test_time_series_point_dataclass(self):
        """Test TimeSeriesPoint dataclass."""
        timestamp = datetime.now(timezone.utc)
        point = TimeSeriesPoint(timestamp=timestamp, value=42.5, label="test_point")

        assert point.timestamp == timestamp
        assert point.value == 42.5
        assert point.label == "test_point"

    def test_time_series_point_dataclass_no_label(self):
        """Test TimeSeriesPoint dataclass without label."""
        timestamp = datetime.now(timezone.utc)
        point = TimeSeriesPoint(timestamp=timestamp, value=42.5)

        assert point.timestamp == timestamp
        assert point.value == 42.5
        assert point.label is None

    def test_get_cached_or_compute_exception(self, mock_service):
        """Test handling exception in compute function."""
        cache_key = "test_key"

        def failing_func():
            raise Exception("Test error")

        with pytest.raises(Exception) as exc_info:
            # This should be async, but we're testing the sync version
            import asyncio

            asyncio.run(mock_service._get_cached_or_compute(cache_key, failing_func))

            assert "Test error" in str(exc_info.value)

    def test_get_cached_or_compute_cache_set_exception(self, mock_service):
        """Test handling exception when setting cache."""
        cache_key = "test_key"
        expected_result = {"data": "test"}

        with patch.object(mock_service.cache_service, "get", return_value=None), patch.object(
            mock_service.cache_service, "set", side_effect=Exception("Cache error")
        ):

            def compute_func():
                return expected_result

            # Should still return the computed result even if caching fails
            import asyncio

            result = asyncio.run(mock_service._get_cached_or_compute(cache_key, compute_func))

            assert result == expected_result
