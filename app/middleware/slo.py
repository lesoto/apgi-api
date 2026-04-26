"""
SLO Definition and Monitoring

Defines Service Level Objectives (SLOs) for the APGI API and provides
monitoring utilities to track compliance.
"""

import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger(__name__)


@dataclass
class SLO:
    """Service Level Objective definition."""

    name: str
    target_p50: float  # seconds
    target_p95: float  # seconds
    target_p99: float  # seconds
    error_budget: float  # percentage (0.0 to 1.0)
    description: str


# Define core API SLOs
API_SLOS = {
    "auth": SLO(
        name="Authentication",
        target_p50=0.1,
        target_p95=0.25,
        target_p99=0.5,
        error_budget=0.999,
        description="JWT token generation and verification",
    ),
    "task_submission": SLO(
        name="Task Submission",
        target_p50=0.05,
        target_p95=0.15,
        target_p99=0.3,
        error_budget=0.995,
        description="Async task submission to Celery",
    ),
    "data_read": SLO(
        name="Data Retrieval",
        target_p50=0.02,
        target_p95=0.1,
        target_p99=0.25,
        error_budget=0.999,
        description="GET requests for session/task data",
    ),
    "global_default": SLO(
        name="Global API Latency",
        target_p50=0.15,
        target_p95=0.5,
        target_p99=1.0,
        error_budget=0.99,
        description="Default fallback SLO",
    ),
}


def get_slo_for_request(path: str, method: str) -> SLO:
    """Map request to appropriate SLO."""
    if path.startswith("/v1/auth"):
        return API_SLOS["auth"]
    if "/tasks" in path and method == "POST":
        return API_SLOS["task_submission"]
    if method == "GET":
        return API_SLOS["data_read"]
    return API_SLOS["global_default"]


class SLOMonitor:
    """Monitor SLO compliance and log violations."""

    def __init__(self, slo_config: Dict[str, SLO] = API_SLOS):
        self.slos = slo_config

    def check_compliance(self, slo_name: str, duration: float) -> None:
        """Track request duration against SLO targets."""
        slo = self.slos.get(slo_name, self.slos["global_default"])

        # Simple logging for now; in production, this would increment Prometheus metrics
        if duration > slo.target_p99:
            logger.warning(
                f"SLO P99 VIOLATION: {slo.name} took {duration:.3f}s (target {slo.target_p99}s)"
            )
        elif duration > slo.target_p95:
            logger.info(
                f"SLO P95 Warning: {slo.name} took {duration:.3f}s (target {slo.target_p95}s)"
            )
