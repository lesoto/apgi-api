"""
Unit tests for app/routes/export.py

Covers all endpoints:
  GET /v1/sessions/{session_id}/export     - export session data (CSV/JSON)
  GET /v1/sessions/{session_id}/summary    - get summary statistics
  GET /v1/sessions/{session_id}/timeseries - get time series data
  GET /v1/sessions/{session_id}/events     - get event analysis

Also covers:
  - get_data_export_service() 503 when not initialized
  - init_export_routes() initialization
  - All 4xx/5xx error paths per endpoint
"""

import io
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Generator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.models.schemas import TokenPayload

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

ADMIN_USER = TokenPayload(
    user_id="user123",
    username="testuser",
    roles=["admin"],
    exp=datetime.now(timezone.utc) + timedelta(hours=1),
    token_type="access",
    permissions=[],
)


@pytest.fixture(autouse=True)
def _patch_trigger_webhook() -> Generator[None, None, None]:
    """Patch trigger_webhook_on_completion to prevent RuntimeWarning from unawaited coroutine."""

    async def noop_webhook(*args: Any, **kwargs: Any) -> None:
        pass

    with patch("app.tasks.experimental_tasks.trigger_webhook_on_completion", new=noop_webhook):
        yield


@asynccontextmanager
async def noop_lifespan(app: object) -> AsyncGenerator[None, None]:
    yield


def make_mock_db(session: Optional[MagicMock] = None) -> MagicMock:
    """Return a mock db whose query().filter().first() returns `session`."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = session
    return db


def make_mock_session(session_id: str = "session123", user_id: str = "user123") -> MagicMock:
    session = MagicMock()
    session.session_id = session_id
    session.user_id = user_id
    return session


def make_mock_service() -> MagicMock:
    svc = MagicMock()
    svc.export_session_data = AsyncMock(return_value=(b"col1,col2\n1,2", "text/csv"))
    svc.generate_summary_stats = AsyncMock(
        return_value={
            "mean": 1.0,
            "std": 0.5,
            "min": 0.1,
            "max": 2.0,
        }
    )
    svc.export_time_series = AsyncMock(
        return_value={
            "session_id": "session123",
            "variables": ["var1"],
            "data": [],
            "num_points": 0,
            "next_cursor": None,
        }
    )
    svc.get_event_analysis = AsyncMock(
        return_value={
            "session_id": "session123",
            "event_type": "ignition",
            "total_events": 5,
        }
    )
    return svc


def make_client(
    mock_db: Optional[MagicMock] = None,
    mock_service: Optional[MagicMock] = None,
    user: Optional[TokenPayload] = None,
) -> tuple[TestClient, object]:
    """Create a TestClient with dependency overrides."""
    from app.database.connection import get_db
    from app.main import create_app
    from app.routes.export import get_data_export_service
    from app.services.authorization import get_current_user

    if mock_db is None:
        mock_db = make_mock_db()
    if mock_service is None:
        mock_service = make_mock_service()
    if user is None:
        user = ADMIN_USER

    app = create_app(test_mode=True)
    app.router.lifespan_context = noop_lifespan

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_data_export_service] = lambda: mock_service
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app, raise_server_exceptions=False)
    return client, app


# ---------------------------------------------------------------------------
# Tests: get_data_export_service factory
# ---------------------------------------------------------------------------


class TestGetDataExportService:
    def test_raises_503_when_not_initialized(self) -> None:
        """get_data_export_service raises HTTP 503 when _data_export_service is None."""
        import app.routes.export as export_module
        from app.routes.export import get_data_export_service

        original = export_module._data_export_service
        export_module._data_export_service = None
        try:
            with pytest.raises(HTTPException) as exc_info:
                get_data_export_service()
            assert exc_info.value.status_code == 503
        finally:
            export_module._data_export_service = original

    def test_returns_service_when_initialized(self) -> None:
        """get_data_export_service returns the service when initialized."""
        import app.routes.export as export_module
        from app.routes.export import get_data_export_service

        mock_svc = MagicMock()
        original = export_module._data_export_service
        export_module._data_export_service = mock_svc
        try:
            result = get_data_export_service()
            assert result is mock_svc
        finally:
            export_module._data_export_service = original


# ---------------------------------------------------------------------------
# Tests: init_export_routes
# ---------------------------------------------------------------------------


class TestInitExportRoutes:
    def test_init_export_routes_sets_service(self) -> None:
        """init_export_routes initializes the DataExportService singleton."""
        import app.routes.export as export_module
        from app.routes.export import init_export_routes

        mock_session_manager = MagicMock()
        original = export_module._data_export_service
        export_module._data_export_service = None

        with patch("app.routes.export.DataExportService") as MockDES:
            mock_instance = MagicMock()
            MockDES.return_value = mock_instance
            init_export_routes(mock_session_manager)
            MockDES.assert_called_once_with(mock_session_manager)
            assert export_module._data_export_service is mock_instance

        export_module._data_export_service = original


# ---------------------------------------------------------------------------
# Tests: export_session_data  GET /v1/sessions/{session_id}/export
# ---------------------------------------------------------------------------


class TestExportSessionData:
    def test_export_csv_success(self) -> None:
        """Happy path: CSV export returns 200 with text/csv content type."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)
        mock_svc = make_mock_service()
        mock_svc.export_session_data = AsyncMock(return_value=(b"col1,col2\n1,2", "text/csv"))

        client, _ = make_client(mock_db=mock_db, mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/export?format=csv")

        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]

    def test_export_json_success(self) -> None:
        """Happy path: JSON export returns 200 with application/json content type."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)
        mock_svc = make_mock_service()
        mock_svc.export_session_data = AsyncMock(return_value=(b'{"data": []}', "application/json"))

        client, _ = make_client(mock_db=mock_db, mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/export?format=json")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_export_invalid_format_returns_400(self) -> None:
        """Invalid format parameter returns HTTP 400."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)

        client, _ = make_client(mock_db=mock_db)
        response = client.get("/v1/sessions/session123/export?format=xml")

        assert response.status_code == 400

    def test_export_session_not_found_returns_404(self) -> None:
        """Session not found returns HTTP 404."""
        mock_db = make_mock_db(session=None)

        client, _ = make_client(mock_db=mock_db)
        response = client.get("/v1/sessions/nonexistent/export?format=csv")

        assert response.status_code == 404

    def test_export_service_error_returns_500(self) -> None:
        """Service exception returns HTTP 500."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)
        mock_svc = make_mock_service()
        mock_svc.export_session_data = AsyncMock(side_effect=RuntimeError("export failed"))

        client, _ = make_client(mock_db=mock_db, mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/export?format=csv")

        assert response.status_code == 500

    def test_export_value_error_exceeds_maximum_returns_413(self) -> None:
        """ValueError with 'exceeds maximum' returns HTTP 413."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)
        mock_svc = make_mock_service()
        mock_svc.export_session_data = AsyncMock(
            side_effect=ValueError("Data size exceeds maximum allowed limit")
        )

        client, _ = make_client(mock_db=mock_db, mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/export?format=csv")

        assert response.status_code == 413

    def test_export_value_error_other_returns_404(self) -> None:
        """ValueError without 'exceeds maximum' returns HTTP 404."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)
        mock_svc = make_mock_service()
        mock_svc.export_session_data = AsyncMock(side_effect=ValueError("Session not found"))

        client, _ = make_client(mock_db=mock_db, mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/export?format=csv")

        assert response.status_code == 404

    def test_export_with_valid_variables(self) -> None:
        """Export with valid variable names succeeds."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)
        mock_svc = make_mock_service()
        mock_svc.export_session_data = AsyncMock(return_value=(b"data", "text/csv"))

        client, _ = make_client(mock_db=mock_db, mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/export?format=csv&variables=var1,var2")

        assert response.status_code == 200

    def test_export_with_invalid_variable_name_returns_400(self) -> None:
        """Export with invalid variable name returns HTTP 400."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)

        client, _ = make_client(mock_db=mock_db)
        response = client.get(
            "/v1/sessions/session123/export?format=csv&variables=valid,inv%40lid%21"
        )

        assert response.status_code == 400

    def test_export_with_empty_variable_name_returns_400(self) -> None:
        """Export with empty variable name (e.g. trailing comma) returns HTTP 400."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)

        client, _ = make_client(mock_db=mock_db)
        # Use a space as the second variable which won't match the regex after strip
        response = client.get("/v1/sessions/session123/export?format=csv&variables=var1,%20")

        assert response.status_code == 400

    def test_export_with_time_filters(self) -> None:
        """Export with start_time and end_time filters succeeds."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)
        mock_svc = make_mock_service()
        mock_svc.export_session_data = AsyncMock(return_value=(b"data", "text/csv"))

        client, _ = make_client(mock_db=mock_db, mock_service=mock_svc)
        response = client.get(
            "/v1/sessions/session123/export?format=csv&start_time=0&end_time=1000"
        )

        assert response.status_code == 200
        mock_svc.export_session_data.assert_called_once()

    def test_export_default_format_is_json(self) -> None:
        """Default format (no format param) is json."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)
        mock_svc = make_mock_service()
        mock_svc.export_session_data = AsyncMock(return_value=(b'{"data":[]}', "application/json"))

        client, _ = make_client(mock_db=mock_db, mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/export")

        assert response.status_code == 200

    def test_export_with_bytesio_response(self) -> None:
        """Service returning BytesIO object is handled correctly."""
        mock_session = make_mock_session()
        mock_db = make_mock_db(session=mock_session)
        mock_svc = make_mock_service()
        mock_svc.export_session_data = AsyncMock(return_value=(io.BytesIO(b"csv,data"), "text/csv"))

        client, _ = make_client(mock_db=mock_db, mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/export?format=csv")

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: get_summary_statistics  GET /v1/sessions/{session_id}/summary
# ---------------------------------------------------------------------------


class TestGetSummaryStatistics:
    def test_summary_success(self) -> None:
        """Happy path: returns 200 with summary statistics."""
        mock_svc = make_mock_service()

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/summary")

        assert response.status_code == 200
        mock_svc.generate_summary_stats.assert_called_once_with("session123", "user123")

    def test_summary_value_error_returns_404(self) -> None:
        """ValueError from service returns HTTP 404."""
        mock_svc = make_mock_service()
        mock_svc.generate_summary_stats = AsyncMock(side_effect=ValueError("Session not found"))

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/summary")

        assert response.status_code == 404

    def test_summary_generic_exception_returns_500(self) -> None:
        """Generic exception from service returns HTTP 500."""
        mock_svc = make_mock_service()
        mock_svc.generate_summary_stats = AsyncMock(side_effect=RuntimeError("db connection lost"))

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/summary")

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# Tests: get_time_series_data  GET /v1/sessions/{session_id}/timeseries
# ---------------------------------------------------------------------------


class TestGetTimeSeriesData:
    def test_timeseries_success(self) -> None:
        """Happy path: returns 200 with time series data."""
        mock_svc = make_mock_service()

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/timeseries?variables=var1,var2")

        assert response.status_code == 200
        mock_svc.export_time_series.assert_called_once()

    def test_timeseries_invalid_variable_returns_400(self) -> None:
        """Invalid variable name returns HTTP 400."""
        client, _ = make_client()
        response = client.get("/v1/sessions/session123/timeseries?variables=valid,inv%40lid")

        assert response.status_code == 400

    def test_timeseries_empty_variable_returns_400(self) -> None:
        """Empty variable name (space after comma) returns HTTP 400."""
        client, _ = make_client()
        response = client.get("/v1/sessions/session123/timeseries?variables=var1,%20")

        assert response.status_code == 400

    def test_timeseries_value_error_returns_404(self) -> None:
        """ValueError from service returns HTTP 404."""
        mock_svc = make_mock_service()
        mock_svc.export_time_series = AsyncMock(side_effect=ValueError("Session not found"))

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/timeseries?variables=var1")

        assert response.status_code == 404

    def test_timeseries_generic_exception_returns_500(self) -> None:
        """Generic exception from service returns HTTP 500."""
        mock_svc = make_mock_service()
        mock_svc.export_time_series = AsyncMock(side_effect=RuntimeError("unexpected error"))

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/timeseries?variables=var1")

        assert response.status_code == 500

    def test_timeseries_with_optional_params(self) -> None:
        """Time series with downsample, limit, cursor, and time filters succeeds."""
        mock_svc = make_mock_service()

        client, _ = make_client(mock_service=mock_svc)
        response = client.get(
            "/v1/sessions/session123/timeseries"
            "?variables=var1&start_time=0&end_time=1000&downsample=2&limit=100&cursor=abc"
        )

        assert response.status_code == 200
        mock_svc.export_time_series.assert_called_once()

    def test_timeseries_missing_variables_returns_422(self) -> None:
        """Missing required variables parameter returns HTTP 422."""
        client, _ = make_client()
        response = client.get("/v1/sessions/session123/timeseries")

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: get_event_analysis  GET /v1/sessions/{session_id}/events
# ---------------------------------------------------------------------------


class TestGetEventAnalysis:
    def test_event_analysis_ignition_success(self) -> None:
        """Happy path: ignition event analysis returns 200."""
        mock_svc = make_mock_service()

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/events?event_type=ignition")

        assert response.status_code == 200
        mock_svc.get_event_analysis.assert_called_once_with(
            session_id="session123", event_type="ignition", user_id="user123"
        )

    def test_event_analysis_metabolism_success(self) -> None:
        """metabolism event type returns 200."""
        mock_svc = make_mock_service()
        mock_svc.get_event_analysis = AsyncMock(
            return_value={
                "session_id": "session123",
                "event_type": "metabolism",
                "total_events": 3,
            }
        )

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/events?event_type=metabolism")

        assert response.status_code == 200

    def test_event_analysis_allostatic_load_success(self) -> None:
        """allostatic_load event type returns 200."""
        mock_svc = make_mock_service()
        mock_svc.get_event_analysis = AsyncMock(
            return_value={
                "session_id": "session123",
                "event_type": "allostatic_load",
                "total_events": 2,
            }
        )

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/events?event_type=allostatic_load")

        assert response.status_code == 200

    def test_event_analysis_invalid_event_type_returns_400(self) -> None:
        """Invalid event_type returns HTTP 400."""
        client, _ = make_client()
        response = client.get("/v1/sessions/session123/events?event_type=unknown_type")

        assert response.status_code == 400

    def test_event_analysis_value_error_returns_404(self) -> None:
        """ValueError from service returns HTTP 404."""
        mock_svc = make_mock_service()
        mock_svc.get_event_analysis = AsyncMock(side_effect=ValueError("Session not found"))

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/events?event_type=ignition")

        assert response.status_code == 404

    def test_event_analysis_generic_exception_returns_500(self) -> None:
        """Generic exception from service returns HTTP 500."""
        mock_svc = make_mock_service()
        mock_svc.get_event_analysis = AsyncMock(side_effect=RuntimeError("unexpected error"))

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/events?event_type=ignition")

        assert response.status_code == 500

    def test_event_analysis_http_exception_re_raised(self) -> None:
        """HTTPException from service is re-raised unchanged."""
        mock_svc = make_mock_service()
        mock_svc.get_event_analysis = AsyncMock(
            side_effect=HTTPException(status_code=403, detail="Forbidden")
        )

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/events?event_type=ignition")

        assert response.status_code == 403

    def test_event_analysis_default_event_type_is_ignition(self) -> None:
        """Default event_type (no param) is 'ignition'."""
        mock_svc = make_mock_service()

        client, _ = make_client(mock_service=mock_svc)
        response = client.get("/v1/sessions/session123/events")

        assert response.status_code == 200
        mock_svc.get_event_analysis.assert_called_once_with(
            session_id="session123", event_type="ignition", user_id="user123"
        )
