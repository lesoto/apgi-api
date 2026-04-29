"""
Tests for business metrics service.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.business_metrics import BusinessMetricsService


class TestBusinessMetricsService:
    """Test business metrics service."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        from sqlalchemy.orm import Session

        return MagicMock(spec=Session)

    @pytest.fixture
    def metrics_service(self, mock_db):
        """Business metrics service instance."""
        return BusinessMetricsService()

    @pytest.mark.asyncio
    async def test_get_overview_metrics(self, metrics_service):
        """Test getting overview metrics."""
        with patch("app.services.business_metrics.get_db_context") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            # Mock scalar() to return integers for count queries
            mock_db.query.return_value.scalar.side_effect = [100, 50, 200, 75, 150, 120, 30, 15]

            metrics = await metrics_service.get_overview_metrics()

            assert isinstance(metrics, dict)
            assert "overview" in metrics

    def test_get_session_metrics(self, metrics_service):
        """Test getting session metrics."""
        with patch("app.services.business_metrics.get_db_context") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            # Build query chain: query().filter().group_by().all()
            # and query().filter().scalar()
            mock_final_query1 = MagicMock()
            mock_final_query1.all.return_value = [("active", 30), ("completed", 20)]

            mock_filter1 = MagicMock()
            mock_filter1.group_by.return_value = mock_final_query1

            mock_query_builder1 = MagicMock()
            mock_query_builder1.filter.return_value = mock_filter1

            # For scalar queries
            mock_final_query2 = MagicMock()
            mock_final_query2.scalar.return_value = 50  # template_usage

            mock_filter2 = MagicMock()
            mock_filter2.scalar.return_value = 50

            mock_query_builder2 = MagicMock()
            mock_query_builder2.filter.return_value = mock_filter2

            mock_final_query3 = MagicMock()
            mock_final_query3.scalar.return_value = 100  # total_recent_sessions

            mock_filter3 = MagicMock()
            mock_filter3.scalar.return_value = 100

            mock_query_builder3 = MagicMock()
            mock_query_builder3.filter.return_value = mock_filter3

            mock_final_query4 = MagicMock()
            mock_final_query4.all.return_value = []  # daily_sessions

            mock_filter4 = MagicMock()
            mock_filter4.group_by.return_value = mock_final_query4
            mock_filter4.order_by.return_value = mock_final_query4

            mock_query_builder4 = MagicMock()
            mock_query_builder4.filter.return_value = mock_filter4

            # Setup side_effect for db.query() calls
            mock_db.query.side_effect = [
                mock_query_builder1,  # status_counts
                mock_query_builder2,  # template_usage
                mock_query_builder3,  # total_recent_sessions
                mock_query_builder4,  # daily_sessions
            ]

            metrics = metrics_service.get_session_metrics(days=30)

            assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_get_task_metrics(self, metrics_service):
        """Test getting task metrics."""
        with patch("app.services.business_metrics.get_db_context") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = [(50, 45, 5)]

            metrics = metrics_service.get_task_metrics(days=30)

            assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_get_user_metrics(self, metrics_service):
        """Test getting user metrics."""
        with patch("app.services.business_metrics.get_db_context") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = [(100, 80, 20)]

            metrics = metrics_service.get_user_metrics(days=30)

            assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_get_template_metrics(self, metrics_service):
        """Test getting template metrics."""
        with patch("app.services.business_metrics.get_db_context") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = [(10, 5, 3)]

            metrics = metrics_service.get_template_metrics(days=30)

            assert isinstance(metrics, dict)

    @pytest.mark.asyncio
    async def test_get_dashboard_data(self, metrics_service):
        """Test getting complete dashboard data."""
        with (
            patch.object(
                metrics_service, "get_overview_metrics", new_callable=AsyncMock
            ) as mock_overview,
            patch.object(metrics_service, "get_session_metrics") as mock_sessions,
            patch.object(metrics_service, "get_task_metrics") as mock_tasks,
            patch.object(metrics_service, "get_user_metrics") as mock_users,
            patch.object(metrics_service, "get_template_metrics") as mock_templates,
        ):
            mock_overview.return_value = {"overview": {"total_users": 100}}
            mock_sessions.return_value = {"sessions": 10}
            mock_tasks.return_value = {"tasks": 5}
            mock_users.return_value = {"users": 20}
            mock_templates.return_value = {"templates": 3}

            dashboard = await metrics_service.get_dashboard_data(days=30)

            assert isinstance(dashboard, dict)
            assert "overview" in dashboard
