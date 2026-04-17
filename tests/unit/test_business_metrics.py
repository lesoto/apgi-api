"""
Unit tests for BusinessMetricsService.

Tests aggregation and reporting methods using mocked DB context and cache.
Requirements: 2.9
"""

import pytest
from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from app.services.business_metrics import (
    BusinessMetricsService,
    MetricValue,
    TimeSeriesPoint,
)


@pytest.fixture
def mock_cache() -> MagicMock:
    cache = MagicMock()
    cache.get_query_result = AsyncMock(return_value=None)
    cache.set_query_result = AsyncMock(return_value=None)
    return cache


@pytest.fixture
def service(mock_cache: MagicMock) -> BusinessMetricsService:
    with patch("app.services.business_metrics.get_cache_service", return_value=mock_cache):
        svc = BusinessMetricsService()
    return svc


def _make_mock_db() -> MagicMock:
    """Build a mock DB that returns sensible scalar/all values."""
    db = MagicMock()
    # Default scalar returns 0
    db.query.return_value.scalar.return_value = 0
    db.query.return_value.filter.return_value.scalar.return_value = 0
    db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
    db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = (
        []
    )
    db.query.return_value.group_by.return_value.all.return_value = []
    db.query.return_value.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = (
        []
    )
    db.query.return_value.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = (
        []
    )
    return db


# ---------------------------------------------------------------------------
# _generate_cache_key
# ---------------------------------------------------------------------------


class TestGenerateCacheKey:
    def test_returns_string(self, service: BusinessMetricsService) -> None:
        key = service._generate_cache_key("test_method", "arg1", kwarg1="val1")
        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hex digest

    def test_different_args_produce_different_keys(self, service: BusinessMetricsService) -> None:
        k1 = service._generate_cache_key("method", "a")
        k2 = service._generate_cache_key("method", "b")
        assert k1 != k2

    def test_same_args_produce_same_key(self, service: BusinessMetricsService) -> None:
        k1 = service._generate_cache_key("method", "a", x=1)
        k2 = service._generate_cache_key("method", "a", x=1)
        assert k1 == k2


# ---------------------------------------------------------------------------
# _get_cached_or_compute
# ---------------------------------------------------------------------------


class TestGetCachedOrCompute:
    @pytest.mark.asyncio
    async def test_returns_cached_value_when_available(
        self, service: BusinessMetricsService, mock_cache: MagicMock
    ) -> None:
        mock_cache.get_query_result.return_value = {"cached": True}
        result = await service._get_cached_or_compute("key", lambda: {"fresh": True})
        assert result == {"cached": True}

    @pytest.mark.asyncio
    async def test_computes_and_caches_when_no_cache(
        self, service: BusinessMetricsService, mock_cache: MagicMock
    ) -> None:
        mock_cache.get_query_result.return_value = None
        result = await service._get_cached_or_compute("key", lambda: {"computed": True})
        assert result == {"computed": True}
        mock_cache.set_query_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_works_without_cache_service(self) -> None:
        with patch("app.services.business_metrics.get_cache_service", return_value=None):
            svc = BusinessMetricsService()
        result = await svc._get_cached_or_compute("key", lambda: {"no_cache": True})
        assert result == {"no_cache": True}


# ---------------------------------------------------------------------------
# get_overview_metrics
# ---------------------------------------------------------------------------


class TestGetOverviewMetrics:
    @pytest.mark.asyncio
    async def test_returns_overview_dict(
        self, service: BusinessMetricsService, mock_cache: MagicMock
    ) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = await service.get_overview_metrics()

        assert "overview" in result
        overview = result["overview"]
        assert "total_users" in overview
        assert "active_users" in overview
        assert "total_sessions" in overview
        assert "active_sessions" in overview
        assert "total_tasks" in overview
        assert "task_completion_rate" in overview
        assert "total_templates" in overview
        assert "public_templates" in overview

    @pytest.mark.asyncio
    async def test_metric_values_are_metric_value_instances(
        self, service: BusinessMetricsService, mock_cache: MagicMock
    ) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = await service.get_overview_metrics()

        for key, val in result["overview"].items():
            assert isinstance(val, MetricValue), f"{key} should be MetricValue"

    @pytest.mark.asyncio
    async def test_uses_cache_on_second_call(
        self, service: BusinessMetricsService, mock_cache: MagicMock
    ) -> None:
        mock_db = _make_mock_db()
        cached_result: Dict[str, Any] = {"overview": {}}
        mock_cache.get_query_result.return_value = cached_result

        result = await service.get_overview_metrics()
        assert result == cached_result

    @pytest.mark.asyncio
    async def test_task_completion_rate_zero_when_no_tasks(
        self, service: BusinessMetricsService, mock_cache: MagicMock
    ) -> None:
        mock_db = _make_mock_db()
        # total_tasks = 0, completed_tasks = 0
        mock_db.query.return_value.scalar.return_value = 0
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = await service.get_overview_metrics()

        rate = result["overview"]["task_completion_rate"]
        assert rate.value == 0


# ---------------------------------------------------------------------------
# get_session_metrics
# ---------------------------------------------------------------------------


class TestGetSessionMetrics:
    def test_returns_session_metrics_dict(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_session_metrics(days=30)

        assert "session_status_distribution" in result
        assert "template_usage_rate" in result
        assert "session_timeline" in result

    def test_template_usage_rate_is_metric_value(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_session_metrics()

        assert isinstance(result["template_usage_rate"], MetricValue)

    def test_session_timeline_is_list(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_session_metrics()

        assert isinstance(result["session_timeline"], list)

    def test_template_usage_rate_zero_when_no_sessions(
        self, service: BusinessMetricsService
    ) -> None:
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_session_metrics()

        assert result["template_usage_rate"].value == 0


# ---------------------------------------------------------------------------
# get_task_metrics
# ---------------------------------------------------------------------------


class TestGetTaskMetrics:
    def test_returns_task_metrics_dict(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_task_metrics(days=30)

        assert "task_status_distribution" in result
        assert "task_type_distribution" in result
        assert "average_durations" in result
        assert "task_timeline" in result

    def test_task_timeline_is_list(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_task_metrics()

        assert isinstance(result["task_timeline"], list)

    def test_distributions_are_dicts(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_task_metrics()

        assert isinstance(result["task_status_distribution"], dict)
        assert isinstance(result["task_type_distribution"], dict)
        assert isinstance(result["average_durations"], dict)


# ---------------------------------------------------------------------------
# get_user_metrics
# ---------------------------------------------------------------------------


class TestGetUserMetrics:
    def test_returns_user_metrics_dict(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_user_metrics(days=30)

        assert "user_registrations_timeline" in result
        assert "user_logins_timeline" in result
        assert "users_by_role" in result

    def test_timelines_are_lists(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_user_metrics()

        assert isinstance(result["user_registrations_timeline"], list)
        assert isinstance(result["user_logins_timeline"], list)


# ---------------------------------------------------------------------------
# get_template_metrics
# ---------------------------------------------------------------------------


class TestGetTemplateMetrics:
    def test_returns_template_metrics_dict(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_template_metrics(days=30)

        assert "most_used_templates" in result
        assert "templates_by_user" in result

    def test_most_used_templates_is_list(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with patch("app.services.business_metrics.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = service.get_template_metrics()

        assert isinstance(result["most_used_templates"], list)
        assert isinstance(result["templates_by_user"], list)


# ---------------------------------------------------------------------------
# get_dashboard_data
# ---------------------------------------------------------------------------


class TestGetDashboardData:
    @pytest.mark.asyncio
    async def test_returns_all_sections(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with (
            patch("app.services.business_metrics.get_db_context") as mock_ctx,
            patch.object(service, "get_overview_metrics", new_callable=AsyncMock) as mock_overview,
        ):
            mock_ctx.return_value.__enter__.return_value = mock_db
            mock_overview.return_value = {"overview": {}}
            result = await service.get_dashboard_data(days=30)

        assert "sessions" in result
        assert "tasks" in result
        assert "users" in result
        assert "templates" in result
        assert "generated_at" in result
        assert "time_range_days" in result
        assert result["time_range_days"] == 30

    @pytest.mark.asyncio
    async def test_generated_at_is_datetime(self, service: BusinessMetricsService) -> None:
        mock_db = _make_mock_db()
        with (
            patch("app.services.business_metrics.get_db_context") as mock_ctx,
            patch.object(service, "get_overview_metrics", new_callable=AsyncMock) as mock_overview,
        ):
            mock_ctx.return_value.__enter__.return_value = mock_db
            mock_overview.return_value = {}
            result = await service.get_dashboard_data()

        assert isinstance(result["generated_at"], datetime)


# ---------------------------------------------------------------------------
# MetricValue and TimeSeriesPoint dataclasses
# ---------------------------------------------------------------------------


class TestMetricValue:
    def test_basic_creation(self) -> None:
        mv = MetricValue(value=42, label="Test", description="A test metric")
        assert mv.value == 42
        assert mv.label == "Test"
        assert mv.description == "A test metric"
        assert mv.unit is None
        assert mv.change_percentage is None

    def test_with_optional_fields(self) -> None:
        mv = MetricValue(
            value=99.5, label="Rate", description="Rate metric", unit="%", change_percentage=5.2
        )
        assert mv.unit == "%"
        assert mv.change_percentage == 5.2


class TestTimeSeriesPoint:
    def test_basic_creation(self) -> None:
        ts = TimeSeriesPoint(timestamp=datetime.now(timezone.utc), value=1.5)
        assert ts.value == 1.5
        assert ts.label is None

    def test_with_label(self) -> None:
        ts = TimeSeriesPoint(timestamp=datetime.now(timezone.utc), value=10.0, label="10 items")
        assert ts.label == "10 items"
