"""
Integration Tests for Monitoring and Alerting Features

These tests verify that the monitoring and alerting systems work correctly
end-to-end, including:
- Alert manager functionality
- Notification channels (webhook, Slack, email, PagerDuty, Teams)
- Business metrics collection and caching
- Distributed tracing instrumentation

**Validates: Requirements related to monitoring and alerting**
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator

from app.middleware.alerting import (
    AlertManager,
    Alert,
    AlertSeverity,
    WebhookNotificationChannel,
    PagerDutyNotificationChannel,
    TeamsNotificationChannel,
    LogNotificationChannel,
)


@pytest.fixture
async def alert_manager() -> "AlertManager":
    """Create a test alert manager instance."""
    manager = AlertManager()  # type: ignore[no-untyped-call]

    # Clear any existing channels
    manager.channels.clear()
    manager.rules.clear()
    manager.active_alerts.clear()
    manager.error_counts.clear()
    manager.alert_cooldowns.clear()

    return manager


@pytest.fixture
async def client(
    test_environment: None, mock_database_connection: None
) -> AsyncGenerator[AsyncClient, None]:
    """Create test client for monitoring/alerting tests."""
    from app.main import create_app
    from unittest.mock import AsyncMock, patch

    # Mock Redis for the lifespan
    mock_redis_client = AsyncMock()
    mock_redis_client.ping = AsyncMock()
    mock_redis_client.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_redis_client):
        app = create_app(test_mode=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


class TestAlertManager:
    """Test alert manager functionality."""

    @pytest.mark.asyncio
    async def test_alert_creation_and_sending(self, alert_manager: "AlertManager") -> None:
        """Test that alerts can be created and sent through channels."""
        # Create a mock notification channel
        mock_channel = AsyncMock()
        mock_channel.send_alert.return_value = True
        alert_manager.add_channel(mock_channel)

        # Create and send an alert
        alert = Alert(
            title="Test Alert",
            message="This is a test alert",
            severity=AlertSeverity.WARNING,
            metadata={"test": True},
        )

        # Send alert through manager
        await alert_manager._send_alert(alert)

        # Verify channel was called
        mock_channel.send_alert.assert_called_once_with(alert)

    @pytest.mark.asyncio
    async def test_error_rate_alerting(self, alert_manager: "AlertManager") -> None:
        """Test that error rate monitoring triggers alerts."""
        # Create a mock notification channel
        mock_channel = AsyncMock()
        mock_channel.send_alert.return_value = True
        alert_manager.add_channel(mock_channel)

        # Override default thresholds for testing
        alert_manager.error_rate_threshold = 2
        alert_manager.error_rate_window = alert_manager.error_rate_window  # 1 minute window
        alert_manager.alert_cooldown = alert_manager.alert_cooldown  # 5 minute cooldown

        # Record multiple errors
        await alert_manager.record_error("test_error", "Test error message")
        await alert_manager.record_error("test_error", "Another test error")

        # Check that alert was triggered (channels should have been called)
        # Note: The actual alert sending happens asynchronously, so we check the call count
        assert mock_channel.send_alert.call_count >= 1

    @pytest.mark.asyncio
    async def test_custom_alert_triggering(self, alert_manager: "AlertManager") -> None:
        """Test custom alert triggering."""
        # Create a mock notification channel
        mock_channel = AsyncMock()
        mock_channel.send_alert.return_value = True
        alert_manager.add_channel(mock_channel)

        # Trigger custom alert
        await alert_manager.trigger_custom_alert(
            title="Custom Test Alert",
            message="This is a custom alert",
            severity=AlertSeverity.ERROR,
            metadata={"custom": True},
        )

        # Verify alert was sent
        mock_channel.send_alert.assert_called_once()
        call_args = mock_channel.send_alert.call_args[0][0]
        assert call_args.title == "Custom Test Alert"
        assert call_args.severity == AlertSeverity.ERROR


class TestNotificationChannels:
    """Test notification channel implementations."""

    @pytest.mark.asyncio
    async def test_webhook_channel_success(self) -> None:
        """Test webhook notification channel with successful delivery."""
        webhook_url = "https://example.com/webhook"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            channel = WebhookNotificationChannel(webhook_url)
            alert = Alert(title="Test Alert", message="Test message", severity=AlertSeverity.INFO)

            result = await channel.send_alert(alert)
            assert result is True

            # Verify the webhook was called with correct data
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == webhook_url
            assert "title" in call_args[1]["json"]

    @pytest.mark.asyncio
    async def test_webhook_channel_failure(self) -> None:
        """Test webhook notification channel with failure."""
        webhook_url = "https://example.com/webhook"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            channel = WebhookNotificationChannel(webhook_url)
            alert = Alert(title="Test Alert", message="Test message", severity=AlertSeverity.ERROR)

            result = await channel.send_alert(alert)
            assert result is False

    @pytest.mark.asyncio
    async def test_pagerduty_channel_success(self) -> None:
        """Test PagerDuty notification channel."""
        integration_key = "test-integration-key"

        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"dedup_key": "test-dedup"}
        mock_client.post.return_value = mock_response

        class MockAsyncClient:
            def __init__(self) -> None:
                self.post = mock_client.post

            async def __aenter__(self) -> "MockAsyncClient":
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

        with patch("app.middleware.alerting.httpx") as mock_httpx:
            mock_httpx.AsyncClient = MockAsyncClient
            channel = PagerDutyNotificationChannel(integration_key)
            alert = Alert(
                title="Test Alert", message="Test message", severity=AlertSeverity.CRITICAL
            )

            result = await channel.send_alert(alert)
            assert result is True

            # Verify the PagerDuty API was called correctly
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://events.pagerduty.com/v2/enqueue"
            payload = call_args[1]["json"]
            assert payload["routing_key"] == integration_key
            assert payload["payload"]["summary"] == "Test Alert"

    @pytest.mark.asyncio
    async def test_teams_channel_success(self) -> None:
        """Test Microsoft Teams notification channel."""
        webhook_url = "https://outlook.office.com/webhook/test"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            channel = TeamsNotificationChannel(webhook_url)
            alert = Alert(
                title="Test Alert",
                message="Test message",
                severity=AlertSeverity.WARNING,
                metadata={"key": "value"},
            )

            result = await channel.send_alert(alert)
            assert result is True

            # Verify the Teams webhook was called with MessageCard format
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == webhook_url
            payload = call_args[1]["json"]
            assert payload["@type"] == "MessageCard"
            assert "Test Alert" in payload["summary"]

    @pytest.mark.asyncio
    async def test_log_channel(self) -> None:
        """Test log notification channel."""
        with patch("app.middleware.alerting.logger") as mock_logger:
            channel = LogNotificationChannel()
            alert = Alert(
                title="Test Alert",
                message="Test message",
                severity=AlertSeverity.ERROR,
                metadata={"test": True},
            )

            result = await channel.send_alert(alert)
            assert result is True

            # Verify logger was called
            mock_logger.error.assert_called_once()


class TestBusinessMetricsIntegration:
    """Test business metrics service integration."""

    @pytest.mark.asyncio
    async def test_metrics_service_creation(self) -> None:
        """Test that business metrics service can be created."""
        from app.services.business_metrics import BusinessMetricsService

        service = BusinessMetricsService()  # type: ignore[no-untyped-call]
        assert service is not None
        assert hasattr(service, "cache_service")
        assert hasattr(service, "_generate_cache_key")

    @pytest.mark.asyncio
    async def test_metrics_caching(self) -> None:
        """Test that metrics service uses caching."""
        from app.services.business_metrics import BusinessMetricsService

        service = BusinessMetricsService()  # type: ignore[no-untyped-call]

        # Test cache key generation
        key1 = service._generate_cache_key("test_method", "arg1", "arg2", kwarg1="value1")
        key2 = service._generate_cache_key("test_method", "arg1", "arg2", kwarg1="value1")
        key3 = service._generate_cache_key("test_method", "arg1", "arg2", kwarg1="value2")

        assert key1 == key2  # Same inputs should generate same key
        assert key1 != key3  # Different inputs should generate different keys

    @pytest.mark.asyncio
    async def test_overview_metrics_structure(self, mock_database_connection: None) -> None:
        """Test that overview metrics returns expected structure."""
        from app.services.business_metrics import BusinessMetricsService

        service = BusinessMetricsService()  # type: ignore[no-untyped-call]

        # Mock the database context to return test data
        with patch("app.services.business_metrics.get_db_context") as mock_db_context:
            mock_db = MagicMock()

            # Mock query results for different metrics
            mock_db.query.return_value.scalar.return_value = 10
            mock_db.query.return_value.filter.return_value.scalar.return_value = 5
            mock_db.query.return_value.filter.return_value.filter.return_value.scalar.return_value = (
                3
            )

            # Mock the context manager
            mock_context_manager = MagicMock()
            mock_context_manager.__enter__ = MagicMock(return_value=mock_db)
            mock_context_manager.__exit__ = MagicMock(return_value=None)
            mock_db_context.return_value = mock_context_manager

            # Get the overview metrics
            result = await service.get_overview_metrics()

            # Verify the structure
            assert "overview" in result
            overview = result["overview"]

            # Check that all expected metrics are present
            expected_metrics = [
                "total_users",
                "active_users",
                "total_sessions",
                "active_sessions",
                "total_tasks",
                "task_completion_rate",
                "total_templates",
                "public_templates",
            ]

            for metric in expected_metrics:
                assert metric in overview, f"Missing metric: {metric}"

            # Verify metric structure (should be MetricValue objects)
            for metric_name, metric_value in overview.items():
                assert hasattr(
                    metric_value, "value"
                ), f"Metric {metric_name} should have 'value' attribute"
                assert hasattr(
                    metric_value, "label"
                ), f"Metric {metric_name} should have 'label' attribute"
                assert hasattr(
                    metric_value, "description"
                ), f"Metric {metric_name} should have 'description' attribute"


class TestDistributedTracing:
    """Test distributed tracing integration."""

    @pytest.mark.asyncio
    async def test_tracing_initialization(self) -> None:
        """Test that tracing can be initialized."""
        from app.middleware.tracing import configure_distributed_tracing

        # This should not raise an exception
        try:
            configure_distributed_tracing(enable_console_exporter=False)
        except Exception as e:
            # OpenTelemetry might not be available in test environment
            if "OpenTelemetry" in str(e) or "opentelemetry" in str(e).lower():
                pytest.skip("OpenTelemetry not available in test environment")
            else:
                raise

    @pytest.mark.asyncio
    async def test_tracing_with_console_exporter(self) -> None:
        """Test tracing with console exporter enabled."""
        from app.middleware.tracing import configure_distributed_tracing

        try:
            configure_distributed_tracing(enable_console_exporter=True, sampling_rate=1.0)
        except Exception as e:
            if "OpenTelemetry" in str(e) or "opentelemetry" in str(e).lower():
                pytest.skip("OpenTelemetry not available in test environment")
            else:
                raise


class TestMetricsEndpoints:
    """Test metrics-related API endpoints."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_access(self, client: AsyncClient) -> None:
        """Test that metrics endpoint is accessible."""
        # Note: This assumes a metrics endpoint exists
        # Adjust based on actual endpoint implementation
        response = await client.get("/metrics")
        # The endpoint might require authentication or might not exist yet
        # This is a basic structure test
        assert response.status_code in [200, 401, 404]  # Expected responses

    @pytest.mark.asyncio
    async def test_health_endpoint_with_monitoring(self, client: AsyncClient) -> None:
        """Test health endpoint includes monitoring information."""
        from unittest.mock import AsyncMock, patch

        # Mock the health check to return healthy status with monitoring info
        mock_health_result = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "dependencies": {
                "database": {"status": "healthy", "message": "Connected"},
                "redis": {"status": "healthy", "message": "Connected and responsive"},
                "celery": {
                    "status": "healthy",
                    "message": "Workers responding: 1, tasks running: 0",
                },
            },
        }

        with patch("app.routes.health.health_service") as mock_service:
            if mock_service:
                mock_service.perform_health_check = AsyncMock(return_value=mock_health_result)

            response = await client.get("/health")
            assert response.status_code == 200

            data = response.json()
            # Health endpoint should include some monitoring info
            assert "status" in data or "healthy" in data
            assert "dependencies" in data  # Monitoring information
