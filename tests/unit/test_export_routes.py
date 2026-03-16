"""
Unit tests for export routes.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi import HTTPException, status
from io import BytesIO
from datetime import datetime, timezone


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.execute = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def mock_current_user():
    """Mock current user."""
    user = Mock()
    user.user_id = "user123"
    user.email = "test@example.com"
    user.roles = ["user"]
    return user


@pytest.fixture
def mock_session():
    """Mock session."""
    session = MagicMock()
    session.session_id = "session123"
    session.user_id = "user123"
    session.status = "completed"
    session.created_at = datetime.now(timezone.utc)
    session.updated_at = datetime.now(timezone.utc)
    return session


@pytest.fixture
def mock_data_export_service():
    """Mock data export service."""
    service = MagicMock()
    service.export_session_data.return_value = BytesIO(b"test data")
    service.export_summary_statistics.return_value = BytesIO(b"stats data")
    service.export_event_analysis.return_value = BytesIO(b"event data")
    return service


class TestExportRoutes:
    """Test export routes."""

    @patch("app.routes.export.get_data_export_service")
    @patch("app.routes.export.get_db_context")
    @patch("app.routes.export.get_current_user")
    @patch("app.routes.export.require_permission")
    async def test_export_session_data_csv(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_get_service,
        mock_db,
        mock_current_user,
        mock_session,
        mock_data_export_service,
    ):
        """Test successful session data export to CSV."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_service.return_value = mock_data_export_service
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_session

        from app.routes.export import export_session_data

        result = await export_session_data(
            "session123", format="csv", current_user=mock_current_user
        )

        assert result.media_type == "text/csv"
        assert "attachment" in result.headers.get("content-disposition", "")

    @patch("app.routes.export.get_data_export_service")
    @patch("app.routes.export.get_db_context")
    @patch("app.routes.export.get_current_user")
    @patch("app.routes.export.require_permission")
    async def test_export_session_data_json(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_get_service,
        mock_db,
        mock_current_user,
        mock_session,
        mock_data_export_service,
    ):
        """Test successful session data export to JSON."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_service.return_value = mock_data_export_service
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_session

        from app.routes.export import export_session_data

        result = await export_session_data(
            "session123", format="json", current_user=mock_current_user
        )

        assert result.media_type == "application/json"
        assert "attachment" in result.headers.get("content-disposition", "")

    @patch("app.routes.export.get_data_export_service")
    @patch("app.routes.export.get_db_context")
    @patch("app.routes.export.get_current_user")
    @patch("app.routes.export.require_permission")
    async def test_export_session_data_invalid_format(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_get_service,
        mock_current_user,
    ):
        """Test session data export with invalid format."""
        mock_get_user.return_value = mock_current_user

        from app.routes.export import export_session_data

        with pytest.raises(HTTPException) as exc_info:
            await export_session_data(
                "session123", format="invalid", current_user=mock_current_user
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.routes.export.get_data_export_service")
    @patch("app.routes.export.get_db_context")
    @patch("app.routes.export.get_current_user")
    @patch("app.routes.export.require_permission")
    async def test_export_session_data_not_found(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_get_service,
        mock_db,
        mock_current_user,
    ):
        """Test exporting non-existent session."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        from app.routes.export import export_session_data

        with pytest.raises(HTTPException) as exc_info:
            await export_session_data("nonexistent", format="csv", current_user=mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.routes.export.get_data_export_service")
    @patch("app.routes.export.get_db_context")
    @patch("app.routes.export.get_current_user")
    @patch("app.routes.export.require_permission")
    async def test_export_summary_statistics(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_get_service,
        mock_db,
        mock_current_user,
        mock_session,
        mock_data_export_service,
    ):
        """Test successful summary statistics export."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_service.return_value = mock_data_export_service
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_session

        from app.routes.export import get_summary_statistics

        result = await get_summary_statistics("session123", current_user=mock_current_user)

        assert result is not None
        mock_data_export_service.export_summary_statistics.assert_called_once()

    @patch("app.routes.export.get_data_export_service")
    @patch("app.routes.export.get_db_context")
    @patch("app.routes.export.get_current_user")
    @patch("app.routes.export.require_permission")
    async def test_export_event_analysis(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_get_service,
        mock_db,
        mock_current_user,
        mock_session,
        mock_data_export_service,
    ):
        """Test successful event analysis export."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_service.return_value = mock_data_export_service
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_session

        from app.routes.export import get_event_analysis

        result = await get_event_analysis("session123", current_user=mock_current_user)

        assert result is not None
        mock_data_export_service.export_event_analysis.assert_called_once()

    @patch("app.routes.export.get_data_export_service")
    @patch("app.routes.export.get_db_context")
    @patch("app.routes.export.get_current_user")
    @patch("app.routes.export.require_permission")
    async def test_export_access_denied(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_get_service,
        mock_db,
        mock_current_user,
        mock_session,
    ):
        """Test export with access denied."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_session.user_id = "other_user"
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_session

        from app.routes.export import export_session_data

        with pytest.raises(HTTPException) as exc_info:
            await export_session_data("session123", format="csv", current_user=mock_current_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @patch("app.routes.export.get_data_export_service")
    @patch("app.routes.export.get_db_context")
    @patch("app.routes.export.get_current_user")
    @patch("app.routes.export.require_permission")
    async def test_export_service_error(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_get_service,
        mock_db,
        mock_current_user,
        mock_session,
    ):
        """Test export with service error."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_session

        mock_service = MagicMock()
        mock_service.export_session_data.side_effect = Exception("Export failed")
        mock_get_service.return_value = mock_service

        from app.routes.export import export_session_data

        with pytest.raises(HTTPException) as exc_info:
            await export_session_data("session123", format="csv", current_user=mock_current_user)

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_get_data_export_service_initialization(self):
        """Test data export service initialization."""
        from app.routes.export import get_data_export_service

        service = get_data_export_service()
        assert service is not None

    @patch("app.routes.export.get_data_export_service")
    @patch("app.routes.export.get_db_context")
    @patch("app.routes.export.get_current_user")
    @patch("app.routes.export.require_permission")
    async def test_export_large_dataset(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_get_service,
        mock_db,
        mock_current_user,
        mock_session,
        mock_data_export_service,
    ):
        """Test export with large dataset."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_service.return_value = mock_data_export_service
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_session

        large_data = b"x" * (10 * 1024 * 1024)  # 10MB
        mock_data_export_service.export_session_data.return_value = BytesIO(large_data)

        from app.routes.export import export_session_data

        result = await export_session_data(
            "session123", format="csv", current_user=mock_current_user
        )

        assert result.media_type == "text/csv"

    @patch("app.routes.export.get_data_export_service")
    @patch("app.routes.export.get_db_context")
    @patch("app.routes.export.get_current_user")
    @patch("app.routes.export.require_permission")
    async def test_export_with_filters(
        self,
        mock_require_permission,
        mock_get_user,
        mock_get_db,
        mock_get_service,
        mock_db,
        mock_current_user,
        mock_session,
        mock_data_export_service,
    ):
        """Test export with date filters."""
        mock_get_user.return_value = mock_current_user
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_service.return_value = mock_data_export_service
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_session

        from app.routes.export import export_session_data

        result = await export_session_data(
            "session123",
            format="csv",
            start_time=1704067200000.0,  # 2024-01-01 in ms
            end_time=1735689599000.0,  # 2024-12-31 in ms
            db=mock_db,
            service=mock_data_export_service,
            current_user=mock_current_user,
        )

        assert result.media_type == "text/csv"
        mock_data_export_service.export_session_data.assert_called_once()
