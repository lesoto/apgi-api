"""
Metrics Routes

Endpoints for exposing Prometheus metrics.
"""

from fastapi import APIRouter

from app.middleware.metrics import get_metrics_response

router = APIRouter(prefix="/v1", tags=["Metrics"])


@router.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.

    Returns:
        Prometheus metrics
    """
    return get_metrics_response()
