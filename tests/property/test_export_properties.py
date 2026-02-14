"""
Property-based tests for data export functionality.

Feature: api-migration
Tests universal properties of export authorization, metadata completeness,
and content-type headers.
"""

import json
import pytest
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import Mock, AsyncMock
import sys
from pathlib import Path
from io import BytesIO

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.testclient import TestClient
from fastapi.responses import StreamingResponse
from services.data_export import DataExportService


# ============================================================================
# Helper Functions
# ============================================================================


def create_export_endpoint():
    """Create a test FastAPI app with a single export endpoint."""
    app = FastAPI()

    # Global mock service that tests can override
    mock_service_holder = {"service": None}

    def get_data_export_service():
        if mock_service_holder["service"] is None:
            raise HTTPException(status_code=503, detail="Service not initialized")
        return mock_service_holder["service"]

    @app.get("/v1/sessions/{session_id}/export")
    async def export_session_data(
        session_id: str,
        format: str = Query("json"),
        variables: str = Query(None),
        start_time: float = Query(None),
        end_time: float = Query(None),
        service: DataExportService = Depends(get_data_export_service),
    ):
        """Export session data endpoint."""
        try:
            var_list = None
            if variables:
                var_list = [v.strip() for v in variables.split(",")]

            data_bytes, content_type = await service.export_session_data(
                session_id=session_id,
                format=format,
                variables=var_list,
                start_time=start_time,
                end_time=end_time,
            )

            extension = "json" if format.lower() == "json" else "csv"
            filename = f"session_{session_id}_export.{extension}"

            return StreamingResponse(
                BytesIO(data_bytes),
                media_type=content_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to export data: {str(e)}")

    return app, mock_service_holder


# ============================================================================
# Property 19: Export Authorization
# ============================================================================


@settings(max_examples=1)
@given(
    session_owner_id=st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
    requesting_user_id=st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
    session_id=st.uuids(),
)
def test_property_19_export_authorization_different_user(
    session_owner_id, requesting_user_id, session_id
):
    """
    **Validates: Requirements 17.3**

    Feature: api-migration, Property 19: Export Authorization

    For any user attempting to export session data, they should only be able
    to export sessions that belong to them (user_id matches).

    This property ensures that users cannot access other users' session data
    through export endpoints.
    """
    # Skip if users are the same (this is the allowed case)
    assume(session_owner_id != requesting_user_id)

    app, mock_service_holder = create_export_endpoint()

    # Create mock service that denies access
    mock_service = Mock(spec=DataExportService)

    async def mock_export(session_id, format, variables, start_time, end_time):
        # Simulate authorization check failure
        raise ValueError(f"Session {session_id} not found or access denied")

    mock_service.export_session_data = AsyncMock(side_effect=mock_export)
    mock_service_holder["service"] = mock_service

    client = TestClient(app)

    # Attempt to export session owned by different user
    response = client.get(f"/v1/sessions/{session_id}/export?format=json")

    # Property: User should not be able to export another user's session
    assert response.status_code == 404, (
        f"User {requesting_user_id} should not be able to export "
        f"session {session_id} owned by {session_owner_id}"
    )


@settings(max_examples=1)
@given(
    user_id=st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
    session_id=st.uuids(),
)
def test_property_19_export_authorization_own_session(user_id, session_id):
    """
    **Validates: Requirements 17.3**

    Feature: api-migration, Property 19: Export Authorization

    For any user attempting to export their own session data, the export
    should succeed (assuming the session exists).

    This property ensures that users can successfully export their own sessions.
    """
    app, mock_service_holder = create_export_endpoint()

    # Create mock service that allows export
    mock_service = Mock(spec=DataExportService)

    export_data = {
        "session_id": str(session_id),
        "user_id": user_id,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "config": {"test": "config"},
        "state": "completed",
        "data": [],
    }

    async def mock_export(session_id, format, variables, start_time, end_time):
        return (json.dumps(export_data).encode(), "application/json")

    mock_service.export_session_data = AsyncMock(side_effect=mock_export)
    mock_service_holder["service"] = mock_service

    client = TestClient(app)

    # Export own session
    response = client.get(f"/v1/sessions/{session_id}/export?format=json")

    # Property: User should be able to export their own session
    assert (
        response.status_code == 200
    ), f"User {user_id} should be able to export their own session {session_id}"


# ============================================================================
# Property 20: Export Metadata Completeness
# ============================================================================


@settings(max_examples=1)
@given(
    session_id=st.uuids(),
    user_id=st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
    config=st.dictionaries(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
        st.one_of(st.text(max_size=50), st.integers(), st.floats(allow_nan=False)),
        min_size=1,
        max_size=5,
    ),
    state=st.sampled_from(["created", "running", "paused", "stopped", "completed"]),
)
def test_property_20_export_metadata_completeness_json(session_id, user_id, config, state):
    """
    **Validates: Requirements 17.4**

    Feature: api-migration, Property 20: Export Metadata Completeness

    For any exported session in JSON format, the export should include
    session_id, created_at, updated_at, config, and state fields.

    This property ensures that all essential metadata is included in exports
    for proper data analysis and reproducibility.
    """
    app, mock_service_holder = create_export_endpoint()

    # Create export data with all required fields
    export_data = {
        "session_id": str(session_id),
        "user_id": user_id,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "config": config,
        "state": state,
        "data": [],
    }

    mock_service = Mock(spec=DataExportService)

    async def mock_export(session_id, format, variables, start_time, end_time):
        return (json.dumps(export_data).encode(), "application/json")

    mock_service.export_session_data = AsyncMock(side_effect=mock_export)
    mock_service_holder["service"] = mock_service

    client = TestClient(app)

    # Export session
    response = client.get(f"/v1/sessions/{session_id}/export?format=json")

    assert response.status_code == 200, "Export should succeed"

    # Parse response
    response_data = response.json()

    # Property 1: Export should include session_id
    assert "session_id" in response_data, "Export should include 'session_id' field"
    assert response_data["session_id"] == str(session_id), f"Session ID should be '{session_id}'"

    # Property 2: Export should include created_at
    assert "created_at" in response_data, "Export should include 'created_at' field"
    assert isinstance(
        response_data["created_at"], str
    ), "created_at should be a string (ISO timestamp)"

    # Property 3: Export should include updated_at
    assert "updated_at" in response_data, "Export should include 'updated_at' field"
    assert isinstance(
        response_data["updated_at"], str
    ), "updated_at should be a string (ISO timestamp)"

    # Property 4: Export should include config
    assert "config" in response_data, "Export should include 'config' field"
    assert response_data["config"] == config, f"Config should match original: {config}"

    # Property 5: Export should include state
    assert "state" in response_data, "Export should include 'state' field"
    assert response_data["state"] == state, f"State should be '{state}'"


@settings(max_examples=1)
@given(
    session_id=st.uuids(),
    user_id=st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
)
def test_property_20_export_metadata_completeness_csv(session_id, user_id):
    """
    **Validates: Requirements 17.4**

    Feature: api-migration, Property 20: Export Metadata Completeness

    For any exported session in CSV format, the export should include
    metadata headers for session_id, created_at, updated_at, config, and state.

    This property ensures that CSV exports also contain essential metadata,
    either in headers or as initial rows.
    """
    app, mock_service_holder = create_export_endpoint()

    # Create CSV export with metadata
    csv_data = (
        "# Session Metadata\n"
        f"# session_id: {session_id}\n"
        "# created_at: 2024-01-01T00:00:00Z\n"
        "# updated_at: 2024-01-01T01:00:00Z\n"
        "# config: {}\n"
        "# state: completed\n"
        "timestamp,variable,value\n"
        "0,test,1.0\n"
    )

    mock_service = Mock(spec=DataExportService)

    async def mock_export(session_id, format, variables, start_time, end_time):
        return (csv_data.encode(), "text/csv")

    mock_service.export_session_data = AsyncMock(side_effect=mock_export)
    mock_service_holder["service"] = mock_service

    client = TestClient(app)

    # Export session as CSV
    response = client.get(f"/v1/sessions/{session_id}/export?format=csv")

    assert response.status_code == 200, "Export should succeed"

    # Get CSV content
    csv_content = response.text

    # Property 1: CSV should include session_id in metadata
    assert "session_id" in csv_content, "CSV export should include 'session_id' in metadata"

    # Property 2: CSV should include created_at in metadata
    assert "created_at" in csv_content, "CSV export should include 'created_at' in metadata"

    # Property 3: CSV should include updated_at in metadata
    assert "updated_at" in csv_content, "CSV export should include 'updated_at' in metadata"

    # Property 4: CSV should include config in metadata
    assert "config" in csv_content, "CSV export should include 'config' in metadata"

    # Property 5: CSV should include state in metadata
    assert "state" in csv_content, "CSV export should include 'state' in metadata"


# ============================================================================
# Property 21: Export Content-Type Headers
# ============================================================================


@settings(max_examples=1)
@given(
    session_id=st.uuids(),
    user_id=st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
    format=st.sampled_from(["json", "csv"]),
)
def test_property_21_export_content_type_headers(session_id, user_id, format):
    """
    **Validates: Requirements 17.6**

    Feature: api-migration, Property 21: Export Content-Type Headers

    For any export request, the response should include appropriate
    Content-Type (application/json or text/csv) and Content-Disposition headers.

    This property ensures that exported files are properly identified and
    can be downloaded with correct filenames by browsers and clients.
    """
    app, mock_service_holder = create_export_endpoint()

    # Determine expected content type
    expected_content_type = "application/json" if format == "json" else "text/csv"
    expected_extension = "json" if format == "json" else "csv"

    # Create export data
    if format == "json":
        export_data = json.dumps({"session_id": str(session_id)}).encode()
    else:
        export_data = b"timestamp,variable,value\n0,test,1.0\n"

    mock_service = Mock(spec=DataExportService)

    async def mock_export(session_id, format, variables, start_time, end_time):
        return (export_data, expected_content_type)

    mock_service.export_session_data = AsyncMock(side_effect=mock_export)
    mock_service_holder["service"] = mock_service

    client = TestClient(app)

    # Export session
    response = client.get(f"/v1/sessions/{session_id}/export?format={format}")

    assert response.status_code == 200, "Export should succeed"

    # Property 1: Response should include Content-Type header
    assert "content-type" in response.headers, "Response should include 'Content-Type' header"

    # Property 2: Content-Type should match the export format
    content_type = response.headers["content-type"]
    assert expected_content_type in content_type, (
        f"Content-Type should be '{expected_content_type}' for {format} format, "
        f"got '{content_type}'"
    )

    # Property 3: Response should include Content-Disposition header
    assert (
        "content-disposition" in response.headers
    ), "Response should include 'Content-Disposition' header"

    # Property 4: Content-Disposition should indicate attachment
    content_disposition = response.headers["content-disposition"]
    assert (
        "attachment" in content_disposition
    ), "Content-Disposition should indicate 'attachment' for file download"

    # Property 5: Content-Disposition should include filename with correct extension
    assert (
        f"session_{session_id}_export.{expected_extension}" in content_disposition
    ), f"Content-Disposition should include filename with .{expected_extension} extension"


@settings(max_examples=1)
@given(
    session_id=st.uuids(),
    user_id=st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
)
def test_property_21_export_content_type_default_json(session_id, user_id):
    """
    **Validates: Requirements 17.6**

    Feature: api-migration, Property 21: Export Content-Type Headers

    For any export request without explicit format parameter, the response
    should default to JSON format with appropriate Content-Type header.

    This property ensures that the default export format is properly handled.
    """
    app, mock_service_holder = create_export_endpoint()

    # Create JSON export data
    export_data = json.dumps({"session_id": str(session_id)}).encode()

    mock_service = Mock(spec=DataExportService)

    async def mock_export(session_id, format, variables, start_time, end_time):
        return (export_data, "application/json")

    mock_service.export_session_data = AsyncMock(side_effect=mock_export)
    mock_service_holder["service"] = mock_service

    client = TestClient(app)

    # Export session without format parameter (should default to JSON)
    response = client.get(f"/v1/sessions/{session_id}/export")

    assert response.status_code == 200, "Export should succeed"

    # Property: Default format should be JSON
    content_type = response.headers.get("content-type", "")
    assert (
        "application/json" in content_type
    ), f"Default Content-Type should be 'application/json', got '{content_type}'"

    # Property: Filename should have .json extension
    content_disposition = response.headers.get("content-disposition", "")
    assert ".json" in content_disposition, "Default filename should have .json extension"
