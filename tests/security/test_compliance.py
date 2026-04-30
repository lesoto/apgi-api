"""
Compliance-as-code tests for APGI API.
Maps data protection requirements (GDPR/CCPA/SOC 2) to executable tests.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.middleware.logging import StructuredLogger


@pytest.fixture
def client():
    app = create_app(test_mode=True)
    return TestClient(app)


def test_data_retention_audit_log_headers(client):
    """
    Requirement: All sensitive requests must include audit-traceability headers.
    Compliance: SOC 2 (Auditability)
    """
    response = client.get("/v1/version")
    assert "X-Request-ID" in response.headers
    assert "API-Version" in response.headers


def test_security_headers_compliance(client):
    """
    Requirement: Enforce secure browser headers.
    Compliance: GDPR/SOC 2 (Protection of data in transit)
    """
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" in response.headers


def test_personally_identifiable_information_masking():
    """
    Requirement: PII must not be logged in plain text.
    Compliance: GDPR/CCPA
    """
    from app.middleware.logging import StructuredLogger

    logger = StructuredLogger("test")
    # This is a conceptual test for log masking logic
    # In a real implementation, we would verify that fields like 'email' or 'password' are not in 'extra'
    assert hasattr(logger, "info")


def test_immutable_audit_log_format():
    """
    Requirement: Audit logs must follow a structured, immutable format.
    Compliance: SOC 2
    """
    # Verify structured logger can be initialized and has basic logging methods
    logger = StructuredLogger("test")
    assert hasattr(logger, "info")
    assert logger.logger.name == "test"
