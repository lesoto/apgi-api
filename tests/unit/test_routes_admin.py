"""
Tests for admin routes.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.models import AuditLog
from app.routes.admin import (
    AuditLogListResponse,
    AuditLogResponse,
    PaginationInfo,
    query_audit_logs,
)


class TestAdminRoutes:
    """Test admin management endpoints."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def mock_current_user(self):
        """Mock current user."""
        from app.services.authorization import TokenPayload

        return TokenPayload(
            user_id="user-1",
            username="admin",
            roles=["admin"],
            permissions=["user_admin"],
            exp=1234567890,
        )

    @pytest.fixture
    def sample_audit_log(self):
        """Sample audit log for testing."""
        return AuditLog(
            audit_id="audit-1",
            user_id="user-1",
            action="login",
            resource_type="user",
            resource_id="user-1",
            timestamp=datetime.now(timezone.utc),
            details={"ip": "127.0.0.1"},
            ip_address="127.0.0.1",
            user_agent="test-agent",
            status="success",
        )

    @pytest.mark.asyncio
    @patch("app.routes.admin.require_permission")
    @patch("app.routes.admin.get_current_user")
    async def test_query_audit_logs_no_filters(
        self, mock_get_user, mock_require_perm, mock_db, sample_audit_log, mock_current_user
    ):
        """Test querying audit logs without filters."""
        mock_get_user.return_value = mock_current_user
        mock_require_perm.return_value = None

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.all.return_value = [sample_audit_log]

        response = await query_audit_logs(
            user_id=None,
            action=None,
            resource_type=None,
            status_filter=None,
            page=1,
            per_page=20,
            db=mock_db,
            current_user=mock_current_user,
        )

        assert isinstance(response, AuditLogListResponse)
        assert len(response.logs) == 1
        assert response.pagination.page == 1
        assert response.pagination.per_page == 20
        assert response.pagination.total == 1

    @pytest.mark.asyncio
    @patch("app.routes.admin.require_permission")
    @patch("app.routes.admin.get_current_user")
    async def test_query_audit_logs_with_user_filter(
        self, mock_get_user, mock_require_perm, mock_db, sample_audit_log, mock_current_user
    ):
        """Test querying audit logs with user filter."""
        mock_get_user.return_value = mock_current_user
        mock_require_perm.return_value = None

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.all.return_value = [sample_audit_log]

        response = await query_audit_logs(
            user_id="user-1",
            action=None,
            resource_type=None,
            status_filter=None,
            page=1,
            per_page=20,
            db=mock_db,
            current_user=mock_current_user,
        )

        assert len(response.logs) == 1
        assert response.logs[0].user_id == "user-1"

    @pytest.mark.asyncio
    @patch("app.routes.admin.require_permission")
    @patch("app.routes.admin.get_current_user")
    async def test_query_audit_logs_with_action_filter(
        self, mock_get_user, mock_require_perm, mock_db, sample_audit_log, mock_current_user
    ):
        """Test querying audit logs with action filter."""
        mock_get_user.return_value = mock_current_user
        mock_require_perm.return_value = None

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.all.return_value = [sample_audit_log]

        response = await query_audit_logs(
            user_id=None,
            action="login",
            resource_type=None,
            status_filter=None,
            page=1,
            per_page=20,
            db=mock_db,
            current_user=mock_current_user,
        )

        assert len(response.logs) == 1
        assert response.logs[0].action == "login"

    @pytest.mark.asyncio
    @patch("app.routes.admin.require_permission")
    @patch("app.routes.admin.get_current_user")
    async def test_query_audit_logs_with_status_filter(
        self, mock_get_user, mock_require_perm, mock_db, sample_audit_log, mock_current_user
    ):
        """Test querying audit logs with status filter."""
        mock_get_user.return_value = mock_current_user
        mock_require_perm.return_value = None

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.all.return_value = [sample_audit_log]

        response = await query_audit_logs(
            user_id=None,
            action=None,
            resource_type=None,
            status_filter="success",
            page=1,
            per_page=20,
            db=mock_db,
            current_user=mock_current_user,
        )

        assert len(response.logs) == 1
        assert response.logs[0].status == "success"

    @pytest.mark.asyncio
    @patch("app.routes.admin.require_permission")
    @patch("app.routes.admin.get_current_user")
    async def test_query_audit_logs_pagination(
        self, mock_get_user, mock_require_perm, mock_db, sample_audit_log, mock_current_user
    ):
        """Test querying audit logs with pagination."""
        mock_get_user.return_value = mock_current_user
        mock_require_perm.return_value = None

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 50
        mock_query.all.return_value = [sample_audit_log]

        response = await query_audit_logs(
            user_id=None,
            action=None,
            resource_type=None,
            status_filter=None,
            page=2,
            per_page=10,
            db=mock_db,
            current_user=mock_current_user,
        )

        assert response.pagination.page == 2
        assert response.pagination.per_page == 10
        assert response.pagination.total == 50

    @pytest.mark.asyncio
    @patch("app.routes.admin.require_permission")
    @patch("app.routes.admin.get_current_user")
    async def test_query_audit_logs_exception(
        self, mock_get_user, mock_require_perm, mock_db, mock_current_user
    ):
        """Test querying audit logs handles exceptions."""
        mock_get_user.return_value = mock_current_user
        mock_require_perm.return_value = None

        mock_db.query.side_effect = Exception("Database error")

        with pytest.raises(HTTPException) as exc_info:
            await query_audit_logs(
                user_id=None,
                action=None,
                resource_type=None,
                status_filter=None,
                page=1,
                per_page=20,
                db=mock_db,
                current_user=mock_current_user,
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_audit_log_response_model(self):
        """Test AuditLogResponse model."""
        log = AuditLogResponse(
            audit_id="audit-1",
            user_id="user-1",
            action="login",
            resource_type="user",
            resource_id="user-1",
            timestamp=datetime.now(timezone.utc),
            details={"ip": "127.0.0.1"},
            ip_address="127.0.0.1",
            user_agent="test-agent",
            status="success",
        )
        assert log.audit_id == "audit-1"
        assert log.action == "login"

    def test_pagination_info_model(self):
        """Test PaginationInfo model."""
        pagination = PaginationInfo(page=1, per_page=20, total=100)
        assert pagination.page == 1
        assert pagination.per_page == 20
        assert pagination.total == 100
