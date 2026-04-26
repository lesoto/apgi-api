"""
Unit tests for SLO monitoring and compliance checking.
Requirements: 4.7, 5.1
"""

from unittest.mock import patch

from app.middleware.slo import (
    API_SLOS,
    SLO,
    SLOMonitor,
    get_slo_for_request,
)


class TestSLODataclass:
    """Test SLO dataclass creation and properties."""

    def test_slo_creation(self) -> None:
        """Test creating SLO instance with all fields."""
        slo = SLO(
            name="Test SLO",
            target_p50=0.1,
            target_p95=0.25,
            target_p99=0.5,
            error_budget=0.99,
            description="Test description",
        )

        assert slo.name == "Test SLO"
        assert slo.target_p50 == 0.1
        assert slo.target_p95 == 0.25
        assert slo.target_p99 == 0.5
        assert slo.error_budget == 0.99
        assert slo.description == "Test description"

    def test_slo_default_values(self) -> None:
        """Test SLO with various error budget values."""
        slo = SLO(
            name="High Availability",
            target_p50=0.05,
            target_p95=0.1,
            target_p99=0.2,
            error_budget=0.999,
            description="Critical service",
        )

        assert slo.error_budget == 0.999


class TestAPISLOs:
    """Test predefined API SLOs."""

    def test_auth_slo_defined(self) -> None:
        """Authentication SLO is defined."""
        assert "auth" in API_SLOS
        slo = API_SLOS["auth"]
        assert slo.name == "Authentication"
        assert slo.target_p50 == 0.1
        assert slo.target_p95 == 0.25
        assert slo.target_p99 == 0.5
        assert slo.error_budget == 0.999

    def test_task_submission_slo_defined(self) -> None:
        """Task submission SLO is defined."""
        assert "task_submission" in API_SLOS
        slo = API_SLOS["task_submission"]
        assert slo.name == "Task Submission"
        assert slo.target_p50 == 0.05
        assert slo.target_p95 == 0.15
        assert slo.target_p99 == 0.3
        assert slo.error_budget == 0.995

    def test_data_read_slo_defined(self) -> None:
        """Data read SLO is defined."""
        assert "data_read" in API_SLOS
        slo = API_SLOS["data_read"]
        assert slo.name == "Data Retrieval"
        assert slo.target_p50 == 0.02
        assert slo.target_p95 == 0.1
        assert slo.target_p99 == 0.25
        assert slo.error_budget == 0.999

    def test_global_default_slo_defined(self) -> None:
        """Global default SLO is defined."""
        assert "global_default" in API_SLOS
        slo = API_SLOS["global_default"]
        assert slo.name == "Global API Latency"
        assert slo.target_p50 == 0.15
        assert slo.target_p95 == 0.5
        assert slo.target_p99 == 1.0
        assert slo.error_budget == 0.99


class TestGetSLOForRequest:
    """Test SLO mapping for different request types."""

    def test_get_slo_for_auth_endpoint(self) -> None:
        """Auth endpoints map to auth SLO."""
        slo = get_slo_for_request("/v1/auth/login", "POST")
        assert slo.name == "Authentication"

    def test_get_slo_for_task_submission(self) -> None:
        """POST to tasks endpoint maps to task_submission SLO."""
        slo = get_slo_for_request("/v1/tasks", "POST")
        assert slo.name == "Task Submission"

    def test_get_slo_for_data_read(self) -> None:
        """GET requests map to data_read SLO."""
        slo = get_slo_for_request("/v1/sessions", "GET")
        assert slo.name == "Data Retrieval"

    def test_get_slo_for_global_default(self) -> None:
        """Other requests map to global_default SLO."""
        slo = get_slo_for_request("/v1/users", "DELETE")
        assert slo.name == "Global API Latency"

    def test_get_slo_nested_auth_path(self) -> None:
        """Nested auth paths map to auth SLO."""
        slo = get_slo_for_request("/v1/auth/refresh", "POST")
        assert slo.name == "Authentication"

    def test_get_slo_nested_tasks_path(self) -> None:
        """Nested tasks POSTs map to task_submission SLO."""
        slo = get_slo_for_request("/v1/sessions/123/tasks", "POST")
        assert slo.name == "Task Submission"


class TestSLOMonitor:
    """Test SLOMonitor class."""

    def test_monitor_init_default_slos(self) -> None:
        """Monitor initializes with default SLOs."""
        monitor = SLOMonitor()
        assert "auth" in monitor.slos
        assert "task_submission" in monitor.slos
        assert "data_read" in monitor.slos
        assert "global_default" in monitor.slos

    def test_monitor_init_custom_slos(self) -> None:
        """Monitor can initialize with custom SLOs."""
        custom_slos = {
            "custom": SLO(
                name="Custom",
                target_p50=0.1,
                target_p95=0.2,
                target_p99=0.3,
                error_budget=0.95,
                description="Custom SLO",
            )
        }
        monitor = SLOMonitor(slo_config=custom_slos)
        assert "custom" in monitor.slos
        assert monitor.slos["custom"].name == "Custom"

    def test_check_compliance_p99_violation(self) -> None:
        """Log warning when P99 target violated."""
        monitor = SLOMonitor()

        with patch("app.middleware.slo.logger") as mock_logger:
            # Auth SLO target_p99 is 0.5s, 1.0s exceeds it
            monitor.check_compliance("auth", 1.0)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "SLO P99 VIOLATION" in call_args
            assert "Authentication" in call_args

    def test_check_compliance_p95_warning(self) -> None:
        """Log info when P95 target exceeded but P99 OK."""
        monitor = SLOMonitor()

        with patch("app.middleware.slo.logger") as mock_logger:
            # Auth SLO: p95=0.25s, p99=0.5s; 0.3s is between them
            monitor.check_compliance("auth", 0.3)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "SLO P95 Warning" in call_args

    def test_check_compliance_within_targets(self) -> None:
        """No logging when within all targets."""
        monitor = SLOMonitor()

        with patch("app.middleware.slo.logger") as mock_logger:
            # Auth SLO p50=0.1s, 0.05s is well within target
            monitor.check_compliance("auth", 0.05)

            mock_logger.warning.assert_not_called()
            mock_logger.info.assert_not_called()

    def test_check_compliance_unknown_slo(self) -> None:
        """Use global_default for unknown SLO names."""
        monitor = SLOMonitor()

        with patch("app.middleware.slo.logger") as mock_logger:
            # Unknown SLO name falls back to global_default
            monitor.check_compliance("unknown_slo", 2.0)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "Global API Latency" in call_args

    def test_check_compliance_edge_case_exactly_p95(self) -> None:
        """Test edge case at exactly P95 threshold."""
        monitor = SLOMonitor()

        with patch("app.middleware.slo.logger") as mock_logger:
            # Auth SLO p95=0.25s, exactly 0.25s triggers P95 warning
            monitor.check_compliance("auth", 0.25)

            # Should log P95 warning (duration > p95, not >=)
            mock_logger.info.assert_not_called()

    def test_check_compliance_edge_case_exactly_p99(self) -> None:
        """Test edge case at exactly P99 threshold."""
        monitor = SLOMonitor()

        with patch("app.middleware.slo.logger") as mock_logger:
            # Auth SLO p99=0.5s, exactly 0.5s does not trigger violation
            monitor.check_compliance("auth", 0.5)

            # Should not log (duration > p99 triggers violation)
            mock_logger.warning.assert_not_called()

    def test_check_compliance_different_slos(self) -> None:
        """Check compliance for different SLO types."""
        monitor = SLOMonitor()

        with patch("app.middleware.slo.logger") as mock_logger:
            # Task submission has stricter targets
            # p50=0.05, p95=0.15, p99=0.3
            monitor.check_compliance("task_submission", 0.4)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "Task Submission" in call_args

    def test_check_compliance_data_read_fast(self) -> None:
        """Data read SLO is very strict."""
        monitor = SLOMonitor()

        with patch("app.middleware.slo.logger") as mock_logger:
            # Data read p99=0.25s
            monitor.check_compliance("data_read", 0.3)

            mock_logger.warning.assert_called_once()
