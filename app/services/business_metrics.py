"""
Business Metrics Dashboard Service

Service for collecting and aggregating business metrics for operational insights.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, cast

from sqlalchemy import and_, func, or_

from app.database.connection import get_db_context
from app.database.models import Session as SessionModel
from app.database.models import SessionTemplate, Task, User
from app.services.cache_service import get_cache_service

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """Represents a single metric value with metadata."""

    value: Any
    label: str
    description: str
    unit: Optional[str] = None
    change_percentage: Optional[float] = None


@dataclass
class TimeSeriesPoint:
    """Represents a point in a time series."""

    timestamp: datetime
    value: float
    label: Optional[str] = None


class BusinessMetricsService:
    """Service for collecting business metrics for dashboard display."""

    def __init__(self) -> None:
        """Initialize the metrics service."""
        self.cache_service = get_cache_service()
        self.cache_ttl = 900  # 15 minutes for metrics cache

    def _generate_cache_key(self, method_name: str, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key for a method call."""
        key_data = f"{method_name}:{args}:{sorted(kwargs.items())}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    async def _get_cached_or_compute(
        self, cache_key: str, compute_func: Callable[[], Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get from cache or compute and cache the result."""
        if self.cache_service:
            cached_result = await self.cache_service.get_query_result(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cast(Dict[str, Any], cached_result)

        # Compute the result
        result = compute_func()

        # Cache the result
        if self.cache_service:
            await self.cache_service.set_query_result(cache_key, result, self.cache_ttl)
            logger.debug(f"Cached result for {cache_key}")

        return result

    async def get_overview_metrics(self) -> Dict[str, Any]:
        """
        Get high-level overview metrics for the dashboard.

        Returns:
            Dictionary with overview metrics
        """
        cache_key = self._generate_cache_key("overview_metrics")

        def _compute_overview_metrics() -> Dict[str, Any]:
            with get_db_context() as db:
                # Total users
                total_users = db.query(func.count(User.user_id)).scalar()

                # Active users (users who logged in within last 30 days)
                thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                active_users = (
                    db.query(func.count(User.user_id))
                    .filter(User.last_login >= thirty_days_ago)
                    .scalar()
                )

                # Total sessions
                total_sessions = db.query(func.count(SessionModel.session_id)).scalar()

                # Active sessions (created or updated in last 24 hours)
                twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
                active_sessions = (
                    db.query(func.count(SessionModel.session_id))
                    .filter(
                        or_(
                            SessionModel.created_at >= twenty_four_hours_ago,
                            SessionModel.updated_at >= twenty_four_hours_ago,
                        )
                    )
                    .scalar()
                )

                # Total tasks
                total_tasks = db.query(func.count(Task.task_id)).scalar()

                # Completed tasks
                completed_tasks = (
                    db.query(func.count(Task.task_id)).filter(Task.status == "completed").scalar()
                )

                # Total templates
                total_templates = db.query(func.count(SessionTemplate.template_id)).scalar()

                # Public templates
                public_templates = (
                    db.query(func.count(SessionTemplate.template_id))
                    .filter(SessionTemplate.is_public)
                    .scalar()
                )

                # Calculate rates
                task_completion_rate = (
                    (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
                )
                template_public_rate = (
                    (public_templates / total_templates * 100) if total_templates > 0 else 0
                )

                return {
                    "overview": {
                        "total_users": MetricValue(
                            value=total_users,
                            label="Total Users",
                            description="Total number of registered users",
                        ),
                        "active_users": MetricValue(
                            value=active_users,
                            label="Active Users (30d)",
                            description="Users who logged in within the last 30 days",
                        ),
                        "total_sessions": MetricValue(
                            value=total_sessions,
                            label="Total Sessions",
                            description="Total number of simulation sessions created",
                        ),
                        "active_sessions": MetricValue(
                            value=active_sessions,
                            label="Active Sessions (24h)",
                            description="Sessions created or updated in the last 24 hours",
                        ),
                        "total_tasks": MetricValue(
                            value=total_tasks,
                            label="Total Tasks",
                            description="Total number of experimental tasks",
                        ),
                        "task_completion_rate": MetricValue(
                            value=round(task_completion_rate, 1),
                            label="Task Completion Rate",
                            description="Percentage of tasks completed successfully",
                            unit="%",
                        ),
                        "total_templates": MetricValue(
                            value=total_templates,
                            label="Session Templates",
                            description="Total number of reusable session templates",
                        ),
                        "public_templates": MetricValue(
                            value=public_templates,
                            label="Public Templates",
                            description="Number of publicly available templates",
                        ),
                    }
                }

        return await self._get_cached_or_compute(cache_key, _compute_overview_metrics)

    def get_session_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get session-related metrics.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with session metrics
        """
        with get_db_context() as db:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Sessions by status
            status_counts = (
                db.query(SessionModel.state, func.count(SessionModel.session_id))
                .filter(SessionModel.created_at >= start_date)
                .group_by(SessionModel.state)
                .all()
            )

            # Sessions by template usage
            template_usage = (
                db.query(func.count(SessionModel.session_id))
                .filter(
                    and_(
                        SessionModel.created_at >= start_date, SessionModel.template_id.isnot(None)
                    )
                )
                .scalar()
            )

            total_recent_sessions = (
                db.query(func.count(SessionModel.session_id))
                .filter(SessionModel.created_at >= start_date)
                .scalar()
            )

            template_usage_rate = (
                (template_usage / total_recent_sessions * 100) if total_recent_sessions > 0 else 0
            )

            # Sessions over time (daily)
            daily_sessions = (
                db.query(func.date(SessionModel.created_at), func.count(SessionModel.session_id))
                .filter(SessionModel.created_at >= start_date)
                .group_by(func.date(SessionModel.created_at))
                .order_by(func.date(SessionModel.created_at))
                .all()
            )

            session_timeline = [
                TimeSeriesPoint(
                    timestamp=datetime.combine(date, datetime.min.time()),
                    value=count,
                    label=f"{count} sessions",
                )
                for date, count in daily_sessions
            ]

            return {
                "session_status_distribution": {status: count for status, count in status_counts},
                "template_usage_rate": MetricValue(
                    value=round(template_usage_rate, 1),
                    label="Template Usage Rate",
                    description="Percentage of sessions created from templates",
                    unit="%",
                ),
                "session_timeline": session_timeline,
            }

    def get_task_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get task-related metrics.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with task metrics
        """
        with get_db_context() as db:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Tasks by status
            status_counts = (
                db.query(Task.status, func.count(Task.task_id))
                .filter(Task.created_at >= start_date)
                .group_by(Task.status)
                .all()
            )

            # Tasks by type
            type_counts = (
                db.query(Task.task_type, func.count(Task.task_id))
                .filter(Task.created_at >= start_date)
                .group_by(Task.task_type)
                .all()
            )

            # Average task duration by type
            avg_durations = (
                db.query(
                    Task.task_type,
                    func.avg(func.extract("epoch", Task.completed_at - Task.started_at)),
                )
                .filter(
                    and_(
                        Task.created_at >= start_date,
                        Task.started_at.isnot(None),
                        Task.completed_at.isnot(None),
                        Task.status == "completed",
                    )
                )
                .group_by(Task.task_type)
                .all()
            )

            # Tasks over time (daily)
            daily_tasks = (
                db.query(func.date(Task.created_at), func.count(Task.task_id))
                .filter(Task.created_at >= start_date)
                .group_by(func.date(Task.created_at))
                .order_by(func.date(Task.created_at))
                .all()
            )

            task_timeline = [
                TimeSeriesPoint(
                    timestamp=datetime.combine(date, datetime.min.time()),
                    value=count,
                    label=f"{count} tasks",
                )
                for date, count in daily_tasks
            ]

            return {
                "task_status_distribution": {status: count for status, count in status_counts},
                "task_type_distribution": {task_type: count for task_type, count in type_counts},
                "average_durations": {task_type: duration for task_type, duration in avg_durations},
                "task_timeline": task_timeline,
            }

    def get_user_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get user-related metrics.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with user metrics
        """
        with get_db_context() as db:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # User registrations over time
            daily_registrations = (
                db.query(func.date(User.created_at), func.count(User.user_id))
                .filter(User.created_at >= start_date)
                .group_by(func.date(User.created_at))
                .order_by(func.date(User.created_at))
                .all()
            )

            # User logins over time (approximated by last_login updates)
            daily_logins = (
                db.query(func.date(User.last_login), func.count(User.user_id))
                .filter(and_(User.last_login >= start_date, User.last_login.isnot(None)))
                .group_by(func.date(User.last_login))
                .order_by(func.date(User.last_login))
                .all()
            )

            # Users by role
            role_counts = (
                db.query(func.unnest(User.roles), func.count(User.user_id))
                .group_by(func.unnest(User.roles))
                .all()
            )

            registration_timeline = [
                TimeSeriesPoint(
                    timestamp=datetime.combine(date, datetime.min.time()),
                    value=count,
                    label=f"{count} registrations",
                )
                for date, count in daily_registrations
            ]

            login_timeline = [
                TimeSeriesPoint(
                    timestamp=datetime.combine(date, datetime.min.time()),
                    value=count,
                    label=f"{count} logins",
                )
                for date, count in daily_logins
            ]

            return {
                "user_registrations_timeline": registration_timeline,
                "user_logins_timeline": login_timeline,
                "users_by_role": {role: count for role, count in role_counts},
            }

    def get_template_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get template-related metrics.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with template metrics
        """
        with get_db_context() as db:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Template usage (sessions created from templates)
            template_usage = (
                db.query(SessionTemplate.name, func.count(SessionModel.session_id))
                .join(SessionModel, SessionTemplate.template_id == SessionModel.template_id)
                .filter(SessionModel.created_at >= start_date)
                .group_by(SessionTemplate.template_id, SessionTemplate.name)
                .order_by(func.count(SessionModel.session_id).desc())
                .limit(10)
                .all()
            )

            # Templates by user
            templates_by_user = (
                db.query(User.username, func.count(SessionTemplate.template_id))
                .join(SessionTemplate, User.user_id == SessionTemplate.user_id)
                .group_by(User.user_id, User.username)
                .order_by(func.count(SessionTemplate.template_id).desc())
                .limit(10)
                .all()
            )

            return {
                "most_used_templates": [
                    {"name": name, "usage_count": count} for name, count in template_usage
                ],
                "templates_by_user": [
                    {"username": username, "template_count": count}
                    for username, count in templates_by_user
                ],
            }

    async def get_dashboard_data(self, days: int = 30) -> Dict[str, Any]:
        """
        Get complete dashboard data combining all metrics.

        Args:
            days: Number of days to look back for time-based metrics

        Returns:
            Complete dashboard data dictionary
        """
        overview = await self.get_overview_metrics()
        return {
            "overview": overview,
            "sessions": self.get_session_metrics(days),
            "tasks": self.get_task_metrics(days),
            "users": self.get_user_metrics(days),
            "templates": self.get_template_metrics(days),
            "generated_at": datetime.now(timezone.utc),
            "time_range_days": days,
        }
