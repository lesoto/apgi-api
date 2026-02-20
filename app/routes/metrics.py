"""
Metrics Routes

Endpoints for exposing Prometheus metrics and business dashboard metrics.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from typing import Optional

from app.middleware.metrics import get_metrics_response
from app.services.business_metrics import BusinessMetricsService
from app.services.authorization import require_permission, Permission
from app.services.profiling_service import ProfilingService
from app.services.cache_service import get_cache_service

router = APIRouter(prefix="/v1", tags=["Metrics"])

# Business metrics service instance
_business_metrics_service: Optional[BusinessMetricsService] = None

# Profiling service instance
_profiling_service: Optional[ProfilingService] = None


def get_business_metrics_service() -> BusinessMetricsService:
    """Get BusinessMetricsService dependency."""
    global _business_metrics_service
    if _business_metrics_service is None:
        _business_metrics_service = BusinessMetricsService()
    return _business_metrics_service


def get_profiling_service() -> ProfilingService:
    """Get ProfilingService dependency."""
    global _profiling_service
    if _profiling_service is None:
        _profiling_service = ProfilingService()
    return _profiling_service


@router.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.

    Returns:
        Prometheus metrics
    """
    return get_metrics_response()


@router.get(
    "/dashboard/overview",
    summary="Get dashboard overview metrics",
    description="Retrieve high-level overview metrics for the business dashboard",
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_dashboard_overview(
    service: BusinessMetricsService = Depends(get_business_metrics_service),
):
    """
    Get dashboard overview metrics.

    Returns:
        Overview metrics for dashboard display
    """
    try:
        return service.get_overview_metrics()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard overview: {str(e)}",
        )


@router.get(
    "/dashboard/sessions",
    summary="Get session metrics",
    description="Retrieve session-related metrics for the business dashboard",
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_dashboard_sessions(
    days: int = 30, service: BusinessMetricsService = Depends(get_business_metrics_service)
):
    """
    Get session metrics for dashboard.

    Args:
        days: Number of days to look back for metrics

    Returns:
        Session metrics for dashboard display
    """
    try:
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Days must be between 1 and 365"
            )
        return service.get_session_metrics(days)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session metrics: {str(e)}",
        )


@router.get(
    "/dashboard/tasks",
    summary="Get task metrics",
    description="Retrieve task-related metrics for the business dashboard",
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_dashboard_tasks(
    days: int = 30, service: BusinessMetricsService = Depends(get_business_metrics_service)
):
    """
    Get task metrics for dashboard.

    Args:
        days: Number of days to look back for metrics

    Returns:
        Task metrics for dashboard display
    """
    try:
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Days must be between 1 and 365"
            )
        return service.get_task_metrics(days)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task metrics: {str(e)}",
        )


@router.get(
    "/dashboard/users",
    summary="Get user metrics",
    description="Retrieve user-related metrics for the business dashboard",
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_dashboard_users(
    days: int = 30, service: BusinessMetricsService = Depends(get_business_metrics_service)
):
    """
    Get user metrics for dashboard.

    Args:
        days: Number of days to look back for metrics

    Returns:
        User metrics for dashboard display
    """
    try:
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Days must be between 1 and 365"
            )
        return service.get_user_metrics(days)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user metrics: {str(e)}",
        )


@router.get(
    "/dashboard/templates",
    summary="Get template metrics",
    description="Retrieve template-related metrics for the business dashboard",
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_dashboard_templates(
    days: int = 30, service: BusinessMetricsService = Depends(get_business_metrics_service)
):
    """
    Get template metrics for dashboard.

    Args:
        days: Number of days to look back for metrics

    Returns:
        Template metrics for dashboard display
    """
    try:
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Days must be between 1 and 365"
            )
        return service.get_template_metrics(days)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template metrics: {str(e)}",
        )


@router.get(
    "/dashboard",
    summary="Get complete dashboard data",
    description="Retrieve complete business metrics dashboard data",
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_complete_dashboard(
    days: int = 30, service: BusinessMetricsService = Depends(get_business_metrics_service)
):
    """
    Get complete dashboard data.

    Args:
        days: Number of days to look back for metrics

    Returns:
        Complete dashboard data with all metrics
    """
    try:
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Days must be between 1 and 365"
            )

        # Check cache first
        cache_service = get_cache_service()
        if cache_service:
            cache_key = f"dashboard:{days}"
            cached_data = await cache_service.get_api_response("/dashboard", cache_key)
            if cached_data:
                return cached_data

        # Compute dashboard data
        dashboard_data = service.get_dashboard_data(days)

        # Cache the result for 15 minutes (900 seconds)
        if cache_service:
            await cache_service.set_api_response("/dashboard", cache_key, dashboard_data, 900)

        return dashboard_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard data: {str(e)}",
        )


@router.get(
    "/dashboard/html",
    summary="Dashboard HTML Interface",
    description="Real-time API analytics dashboard interface",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_dashboard_html(
    days: int = 30, service: BusinessMetricsService = Depends(get_business_metrics_service)
):
    """
    Get HTML dashboard interface for API analytics.

    Args:
        days: Number of days to look back for metrics

    Returns:
        HTML dashboard page
    """
    try:
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Days must be between 1 and 365"
            )

        # Get dashboard data
        dashboard_data = service.get_dashboard_data(days)

        # Create simple HTML dashboard
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>APGI API Analytics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .dashboard {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .metric-card {{ background: white; padding: 20px; margin: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: inline-block; width: 300px; vertical-align: top; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #3498db; }}
        .metric-label {{ color: #7f8c8d; margin-top: 5px; }}
        .chart-container {{ background: white; height: 300px; margin-top: 10px; }}
        .grid {{ display: flex; flex-wrap: wrap; }}
        .section {{ background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .section h2 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>APGI API Analytics Dashboard</h1>
            <p>Real-time API usage and performance metrics</p>
            <p>Showing data for the last {days} days</p>
        </div>

        <div class="section">
            <h2>Overview</h2>
            <div class="grid">
                <div class="metric-card">
                    <div class="metric-value">{dashboard_data.get('overview', {}).get('total_requests', 0)}</div>
                    <div class="metric-label">Total Requests</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{dashboard_data.get('overview', {}).get('active_users', 0)}</div>
                    <div class="metric-label">Active Users</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{dashboard_data.get('overview', {}).get('avg_response_time', 0):.2f}ms</div>
                    <div class="metric-label">Avg Response Time</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{dashboard_data.get('overview', {}).get('error_rate', 0):.2f}%</div>
                    <div class="metric-label">Error Rate</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Performance Trends</h2>
            <div class="chart-container">
                <canvas id="performanceChart"></canvas>
            </div>
            <p>Response time trends and throughput metrics over the last {days} days.</p>
        </div>

        <div class="section">
            <h2>API Usage by Endpoint</h2>
            <div class="chart-container">
                <canvas id="endpointChart"></canvas>
            </div>
            <p>Most frequently used API endpoints and their usage patterns.</p>
        </div>

        <div class="section">
            <h2>System Health</h2>
            <div class="grid">
                <div class="metric-card">
                    <div class="metric-value">{dashboard_data.get('system', {}).get('uptime_hours', 0):.1f}h</div>
                    <div class="metric-label">System Uptime</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{dashboard_data.get('system', {}).get('cpu_usage', 0):.1f}%</div>
                    <div class="metric-label">CPU Usage</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{dashboard_data.get('system', {}).get('memory_usage', 0):.1f}%</div>
                    <div class="metric-label">Memory Usage</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Dashboard data
        const dashboardData = {dashboard_data};

        // Performance Trends Chart
        const performanceCtx = document.getElementById('performanceChart').getContext('2d');
        const performanceChart = new Chart(performanceCtx, {{
            type: 'line',
            data: {{
                labels: dashboardData.trends ? dashboardData.trends.dates : [],
                datasets: [{{
                    label: 'Response Time (ms)',
                    data: dashboardData.trends ? dashboardData.trends.response_times : [],
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1
                }}, {{
                    label: 'Requests per Hour',
                    data: dashboardData.trends ? dashboardData.trends.requests : [],
                    borderColor: 'rgb(255, 99, 132)',
                    tension: 0.1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false
            }}
        }});

        // Endpoint Usage Chart
        const endpointCtx = document.getElementById('endpointChart').getContext('2d');
        const endpointChart = new Chart(endpointCtx, {{
            type: 'bar',
            data: {{
                labels: dashboardData.endpoints ? dashboardData.endpoints.labels : [],
                datasets: [{{
                    label: 'Request Count',
                    data: dashboardData.endpoints ? dashboardData.endpoints.counts : [],
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgb(54, 162, 235)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

        return HTMLResponse(content=html_content)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate dashboard: {str(e)}",
        )


@router.post(
    "/profiling/memory/start",
    summary="Start memory tracing",
    description="Start collecting detailed memory usage information",
    dependencies=[Depends(require_permission(Permission.SYSTEM_ADMIN))],
)
async def start_memory_tracing(service: ProfilingService = Depends(get_profiling_service)):
    """
    Start memory tracing for performance analysis.

    Returns:
        Status message
    """
    try:
        service.start_memory_tracing()
        return {"message": "Memory tracing started successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start memory tracing: {str(e)}",
        )


@router.post(
    "/profiling/memory/stop",
    summary="Stop memory tracing",
    description="Stop collecting detailed memory usage information",
    dependencies=[Depends(require_permission(Permission.SYSTEM_ADMIN))],
)
async def stop_memory_tracing(service: ProfilingService = Depends(get_profiling_service)):
    """
    Stop memory tracing.

    Returns:
        Status message
    """
    try:
        service.stop_memory_tracing()
        return {"message": "Memory tracing stopped successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop memory tracing: {str(e)}",
        )


@router.get(
    "/profiling/memory",
    summary="Get memory usage snapshot",
    description="Retrieve current memory usage and allocation details",
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_memory_snapshot(service: ProfilingService = Depends(get_profiling_service)):
    """
    Get current memory usage snapshot.

    Returns:
        Memory usage statistics
    """
    try:
        return service.get_memory_snapshot()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get memory snapshot: {str(e)}",
        )


@router.get(
    "/profiling/system",
    summary="Get system performance metrics",
    description="Retrieve current system performance metrics (CPU, memory, threads)",
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_system_performance(service: ProfilingService = Depends(get_profiling_service)):
    """
    Get current system performance metrics.

    Returns:
        System performance data
    """
    try:
        return service.get_system_performance()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system performance: {str(e)}",
        )


@router.get(
    "/profiling/history",
    summary="Get performance history",
    description="Retrieve historical performance metrics for analysis",
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_performance_history(
    hours: int = 1, service: ProfilingService = Depends(get_profiling_service)
):
    """
    Get performance history for the specified time period.

    Args:
        hours: Number of hours to look back

    Returns:
        Historical performance data
    """
    try:
        if hours < 1 or hours > 24:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Hours must be between 1 and 24"
            )
        return service.get_performance_history(hours)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance history: {str(e)}",
        )


@router.get(
    "/profiling/analysis",
    summary="Get bottleneck analysis",
    description="Analyze performance data to identify bottlenecks and recommendations",
    dependencies=[Depends(require_permission(Permission.DATA_READ))],
)
async def get_bottleneck_analysis(service: ProfilingService = Depends(get_profiling_service)):
    """
    Get performance bottleneck analysis.

    Returns:
        Bottleneck analysis and recommendations
    """
    try:
        return service.get_bottleneck_analysis()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bottleneck analysis: {str(e)}",
        )
