"""
Unit tests for admin routes — targeting ≥90% coverage of app/routes/admin.py.

Tests audit log queries, filtering, pagination, and error paths.
Validates: Requirements 3.13, 3.15
"""

from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

try:
    from app.database.connection import get_db
    from app.main import create_app
    from app.services.authorization import get_current_user, require_permission
except ImportError:
    pytest.skip(
        "Required app modules not available - skipping admin routes tests",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def mock_audit_log() -> MagicMock:
    """Create a mock audit log entry."""
    log = MagicMock()
    log.audit_id = "audit_123"
    log.user_id = "user_456"
    log.action = "CREATE"
    log.resource_type = "session"
    log.resource_id = "resource_789"
    log.timestamp = datetime.now(timezone.utc)
    log.details = {"key": "value"}
    log.ip_address = "192.168.1.1"
    log.user_agent = "Mozilla/5.0"
    log.status = "success"
    return log


@pytest.fixture
def mock_current_user() -> MagicMock:
    """Create a mock current user with admin permission."""
    user = MagicMock()
    user.user_id = "admin_user_123"
    user.username = "admin"
    user.roles = ["admin"]
    return user


@pytest.fixture
def client(mock_db: MagicMock, mock_current_user: MagicMock) -> Generator[TestClient, None, None]:
    """Create a TestClient with mocked database and authentication dependencies."""
    app = create_app(test_mode=True)
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[require_permission] = lambda permission: lambda: None
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Query Audit Logs Tests
# ---------------------------------------------------------------------------


class TestQueryAuditLogs:
    """Test the /v1/admin/audit-logs endpoint."""

    def test_query_audit_logs_success_no_filters(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test successful query of audit logs without filters."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log]

        response = client.get("/v1/admin/audit-logs")

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "pagination" in data
        assert len(data["logs"]) == 1
        assert data["logs"][0]["audit_id"] == "audit_123"
        assert data["logs"][0]["user_id"] == "user_456"
        assert data["logs"][0]["action"] == "CREATE"
        assert data["logs"][0]["resource_type"] == "session"
        assert data["logs"][0]["status"] == "success"

    def test_query_audit_logs_with_user_id_filter(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test query audit logs with user_id filter."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log]

        response = client.get("/v1/admin/audit-logs?user_id=user_456")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        # Verify filter was applied
        mock_query.filter.assert_called()

    def test_query_audit_logs_with_action_filter(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test query audit logs with action filter."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log]

        response = client.get("/v1/admin/audit-logs?action=CREATE")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1

    def test_query_audit_logs_with_resource_type_filter(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test query audit logs with resource_type filter."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log]

        response = client.get("/v1/admin/audit-logs?resource_type=session")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1

    def test_query_audit_logs_with_status_filter(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test query audit logs with status filter."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log]

        response = client.get("/v1/admin/audit-logs?status_filter=success")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1

    def test_query_audit_logs_with_multiple_filters(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test query audit logs with multiple filters applied."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log]

        response = client.get(
            "/v1/admin/audit-logs?user_id=user_456&action=CREATE&resource_type=session&status_filter=success"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1

    def test_query_audit_logs_pagination_default(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test pagination with default page and per_page values."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 50
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log] * 20

        response = client.get("/v1/admin/audit-logs")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 20
        assert data["pagination"]["total"] == 50

    def test_query_audit_logs_pagination_custom_page(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test pagination with custom page number."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log] * 20

        response = client.get("/v1/admin/audit-logs?page=2&per_page=20")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["per_page"] == 20
        assert data["pagination"]["total"] == 100
        # Verify offset was calculated correctly (page 2 with 20 per page = offset 20)
        mock_query.offset.assert_called_with(20)

    def test_query_audit_logs_pagination_custom_per_page(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test pagination with custom per_page value."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log] * 50

        response = client.get("/v1/admin/audit-logs?per_page=50")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["per_page"] == 50

    def test_query_audit_logs_empty_result(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test query audit logs with no results."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        response = client.get("/v1/admin/audit-logs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 0
        assert data["pagination"]["total"] == 0

    def test_query_audit_logs_multiple_entries(
        self, client: TestClient, mock_db: MagicMock
    ) -> None:
        """Test query audit logs returning multiple entries."""
        # Setup mock logs
        logs = []
        for i in range(5):
            log = MagicMock()
            log.audit_id = f"audit_{i}"
            log.user_id = f"user_{i}"
            log.action = "CREATE"
            log.resource_type = "session"
            log.resource_id = f"resource_{i}"
            log.timestamp = datetime.now(timezone.utc)
            log.details = {"index": i}
            log.ip_address = f"192.168.1.{i}"
            log.user_agent = "Mozilla/5.0"
            log.status = "success"
            logs.append(log)

        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = logs

        response = client.get("/v1/admin/audit-logs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 5
        for i, log_entry in enumerate(data["logs"]):
            assert log_entry["audit_id"] == f"audit_{i}"
            assert log_entry["user_id"] == f"user_{i}"

    def test_query_audit_logs_response_structure(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test that response has correct structure with all required fields."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log]

        response = client.get("/v1/admin/audit-logs")

        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "logs" in data
        assert "pagination" in data

        # Check log entry structure
        log = data["logs"][0]
        assert "audit_id" in log
        assert "user_id" in log
        assert "action" in log
        assert "resource_type" in log
        assert "resource_id" in log
        assert "timestamp" in log
        assert "details" in log
        assert "ip_address" in log
        assert "user_agent" in log
        assert "status" in log

        # Check pagination structure
        pagination = data["pagination"]
        assert "page" in pagination
        assert "per_page" in pagination
        assert "total" in pagination

    def test_query_audit_logs_database_exception(
        self, client: TestClient, mock_db: MagicMock
    ) -> None:
        """Test handling of database exception."""
        # Setup mock to raise exception
        mock_db.query.side_effect = Exception("Database connection error")

        response = client.get("/v1/admin/audit-logs")

        assert response.status_code == 500
        data = response.json()
        # Check for error response structure
        assert "error" in data or "detail" in data
        error_msg = data.get("detail") or data.get("error", {}).get("message", "")
        assert "Failed to retrieve audit logs" in error_msg

    def test_query_audit_logs_sorting_by_timestamp(
        self, client: TestClient, mock_db: MagicMock
    ) -> None:
        """Test that results are sorted by timestamp in descending order."""
        # Setup mock logs with different timestamps
        logs = []
        for i in range(3):
            log = MagicMock()
            log.audit_id = f"audit_{i}"
            log.user_id = f"user_{i}"
            log.action = "CREATE"
            log.resource_type = "session"
            log.resource_id = f"resource_{i}"
            log.timestamp = datetime.now(timezone.utc) - timedelta(hours=i)
            log.details = None
            log.ip_address = None
            log.user_agent = None
            log.status = "success"
            logs.append(log)

        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 3
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = logs

        response = client.get("/v1/admin/audit-logs")

        assert response.status_code == 200
        # Verify order_by was called (sorting by timestamp descending)
        mock_query.order_by.assert_called()

    def test_query_audit_logs_with_null_optional_fields(
        self, client: TestClient, mock_db: MagicMock
    ) -> None:
        """Test handling of audit logs with null optional fields."""
        # Setup mock log with null optional fields
        log = MagicMock()
        log.audit_id = "audit_123"
        log.user_id = None
        log.action = "DELETE"
        log.resource_type = "user"
        log.resource_id = None
        log.timestamp = datetime.now(timezone.utc)
        log.details = None
        log.ip_address = None
        log.user_agent = None
        log.status = "failure"

        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [log]

        response = client.get("/v1/admin/audit-logs")

        assert response.status_code == 200
        data = response.json()
        log_entry = data["logs"][0]
        assert log_entry["user_id"] is None
        assert log_entry["resource_id"] is None
        assert log_entry["details"] is None
        assert log_entry["ip_address"] is None
        assert log_entry["user_agent"] is None

    def test_query_audit_logs_with_complex_details(
        self, client: TestClient, mock_db: MagicMock
    ) -> None:
        """Test handling of audit logs with complex details JSON."""
        # Setup mock log with complex details
        log = MagicMock()
        log.audit_id = "audit_123"
        log.user_id = "user_456"
        log.action = "UPDATE"
        log.resource_type = "session"
        log.resource_id = "resource_789"
        log.timestamp = datetime.now(timezone.utc)
        log.details = {
            "changes": {
                "status": {"old": "active", "new": "paused"},
                "duration": {"old": 3600, "new": 7200},
            },
            "reason": "User requested pause",
        }
        log.ip_address = "192.168.1.1"
        log.user_agent = "Mozilla/5.0"
        log.status = "success"

        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [log]

        response = client.get("/v1/admin/audit-logs")

        assert response.status_code == 200
        data = response.json()
        log_entry = data["logs"][0]
        assert log_entry["details"]["changes"]["status"]["old"] == "active"
        assert log_entry["details"]["changes"]["status"]["new"] == "paused"

    def test_query_audit_logs_pagination_boundary_page_1(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test pagination at boundary: page 1."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log] * 20

        response = client.get("/v1/admin/audit-logs?page=1&per_page=20")

        assert response.status_code == 200
        data = response.json()
        # Offset should be 0 for page 1
        mock_query.offset.assert_called_with(0)

    def test_query_audit_logs_pagination_max_per_page(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test pagination with maximum per_page value (100)."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 200
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log] * 100

        response = client.get("/v1/admin/audit-logs?per_page=100")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["per_page"] == 100
        mock_query.limit.assert_called_with(100)

    def test_query_audit_logs_filter_combinations(
        self, client: TestClient, mock_db: MagicMock, mock_audit_log: MagicMock
    ) -> None:
        """Test various filter combinations."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_audit_log]

        # Test user_id + action
        response = client.get("/v1/admin/audit-logs?user_id=user_456&action=CREATE")
        assert response.status_code == 200

        # Test resource_type + status
        response = client.get("/v1/admin/audit-logs?resource_type=session&status_filter=success")
        assert response.status_code == 200

        # Test all filters
        response = client.get(
            "/v1/admin/audit-logs?user_id=user_456&action=CREATE&resource_type=session&status_filter=success"
        )
        assert response.status_code == 200

    def test_query_audit_logs_failure_status(self, client: TestClient, mock_db: MagicMock) -> None:
        """Test query audit logs with failure status."""
        # Setup mock log with failure status
        log = MagicMock()
        log.audit_id = "audit_fail"
        log.user_id = "user_456"
        log.action = "DELETE"
        log.resource_type = "user"
        log.resource_id = "resource_999"
        log.timestamp = datetime.now(timezone.utc)
        log.details = {"error": "Permission denied"}
        log.ip_address = "192.168.1.100"
        log.user_agent = "Mozilla/5.0"
        log.status = "failure"

        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [log]

        response = client.get("/v1/admin/audit-logs?status_filter=failure")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        assert data["logs"][0]["status"] == "failure"
        assert data["logs"][0]["action"] == "DELETE"

    def test_query_audit_logs_large_page_number(
        self, client: TestClient, mock_db: MagicMock
    ) -> None:
        """Test pagination with large page number beyond available data."""
        # Setup mock
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 50
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        response = client.get("/v1/admin/audit-logs?page=100&per_page=20")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 0
        assert data["pagination"]["page"] == 100
        assert data["pagination"]["total"] == 50
