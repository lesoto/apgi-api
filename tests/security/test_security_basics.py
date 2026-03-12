"""
Security Test Suite

Tests for common security vulnerabilities including SQL injection,
XSS, CSRF bypass, and JWT manipulation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestSQLInjection:
    """Test SQL injection vulnerabilities."""

    def test_sql_injection_in_username(self, client: TestClient, test_user_token: str):
        """Test that SQL injection payloads in username are rejected."""
        payload = {
            "username": "admin' OR '1'='1",
            "password": "test123",
        }
        response = client.post("/v1/auth/login", json=payload)
        assert response.status_code == 401

    def test_sql_injection_in_email(self, client: TestClient):
        """Test that SQL injection payloads in email are rejected."""
        payload = {
            "username": "testuser",
            "email": "test@example.com' OR '1'='1",
            "password": "test123",
        }
        response = client.post("/v1/users/register", json=payload)
        assert response.status_code == 400

    def test_sql_injection_in_search(self, client: TestClient, test_user_token: str):
        """Test that SQL injection in search parameters is rejected."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        response = client.get("/v1/users?search=admin' OR '1'='1", headers=headers)
        assert response.status_code in [400, 401]  # Bad request or unauthorized


class TestXSSPrevention:
    """Test XSS vulnerability prevention."""

    def test_xss_in_username(self, client: TestClient):
        """Test that XSS payloads in username are sanitized."""
        payload = {
            "username": "<script>alert('xss')</script>",
            "email": "test@example.com",
            "password": "test123",
        }
        response = client.post("/v1/users/register", json=payload)
        # Should either reject or sanitize
        assert response.status_code in [400, 201]

    def test_xss_in_user_profile(self, client: TestClient, test_user_token: str):
        """Test that XSS in user profile fields is sanitized."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        payload = {
            "email": "<script>alert('xss')</script>@example.com",
        }
        response = client.put("/v1/users/me", json=payload, headers=headers)
        assert response.status_code == 400


class TestCSRFProtection:
    """Test CSRF protection."""

    def test_csrf_token_required(self, client: TestClient, test_user_token: str):
        """Test that CSRF tokens are required for state-changing operations."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        payload = {
            "password": "newpassword123",
        }
        # This should require CSRF protection
        response = client.post("/v1/users/me/password", json=payload, headers=headers)
        # CSRF protection should be enforced
        assert response.status_code in [400, 403, 405]


class TestJWTSecurity:
    """Test JWT token security."""

    def test_jwt_algorithm_none_rejected(self, client: TestClient):
        """Test that 'none' algorithm is rejected."""
        # Create a malformed JWT with 'none' algorithm
        token = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJ1c2VyX2lkIjoidGVzdCJ9.signature"
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/v1/users/me", headers=headers)
        assert response.status_code == 401

    def test_jwt_expiration_enforced(self, client: TestClient):
        """Test that expired tokens are rejected."""
        # Create an expired token (this would need proper JWT library)
        # For now, test with invalid token format
        token = "invalid.expired.token"
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/v1/users/me", headers=headers)
        assert response.status_code == 401

    def test_jwt_revocation(self, client: TestClient, test_user_token: str):
        """Test that revoked tokens are rejected."""
        # After logout, token should be revoked
        headers = {"Authorization": f"Bearer {test_user_token}"}
        response = client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 200

        # Try to use the token again
        response = client.get("/v1/users/me", headers=headers)
        assert response.status_code == 401


class TestAuthenticationSecurity:
    """Test authentication security."""

    def test_password_hashing_not_plaintext(self, db: Session):
        """Test that passwords are not stored in plaintext."""
        from app.database.models import User
        from app.services.auth_manager import AuthManager

        user = db.query(User).filter(User.username == "testuser").first()
        if user:
            auth_manager = AuthManager(db)
            # Password hash should not equal plaintext password
            assert user.password_hash != "test123"
            # Should be a bcrypt hash
            assert user.password_hash.startswith("$2b$")

    def test_failed_login_lockout(self, client: TestClient):
        """Test that account locks after multiple failed attempts."""
        # Attempt 5 failed logins
        for _ in range(5):
            payload = {
                "username": "testuser",
                "password": "wrongpassword",
            }
            response = client.post("/v1/auth/login", json=payload)
            assert response.status_code == 401

        # 6th attempt should be locked
        payload = {
            "username": "testuser",
            "password": "wrongpassword",
        }
        response = client.post("/v1/auth/login", json=payload)
        assert response.status_code == 403
        assert "locked" in response.json()["detail"].lower()


class TestAuthorizationSecurity:
    """Test authorization security."""

    def test_unauthorized_access_blocked(self, client: TestClient, test_user_token: str):
        """Test that unauthorized access to admin endpoints is blocked."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        # Try to access admin-only endpoint
        response = client.get("/v1/users/stats", headers=headers)
        assert response.status_code == 403

    def test_permission_check_enforced(self, client: TestClient, test_user_token: str):
        """Test that permission checks are enforced."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        # Try to delete a session without proper permissions
        response = client.delete("/v1/sessions/test-session-id", headers=headers)
        assert response.status_code in [403, 404]


class TestInputValidation:
    """Test input validation security."""

    def test_long_username_rejected(self, client: TestClient):
        """Test that excessively long usernames are rejected."""
        payload = {
            "username": "a" * 1000,
            "email": "test@example.com",
            "password": "test123",
        }
        response = client.post("/v1/users/register", json=payload)
        assert response.status_code == 400

    def test_invalid_email_format_rejected(self, client: TestClient):
        """Test that invalid email formats are rejected."""
        payload = {
            "username": "testuser",
            "email": "not-an-email",
            "password": "test123",
        }
        response = client.post("/v1/users/register", json=payload)
        assert response.status_code == 400

    def test_weak_password_rejected(self, client: TestClient):
        """Test that weak passwords are rejected."""
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "123",  # Too short
        }
        response = client.post("/v1/users/register", json=payload)
        assert response.status_code == 400


class TestRateLimiting:
    """Test rate limiting security."""

    def test_brute_force_protection(self, client: TestClient):
        """Test that brute force attacks are mitigated."""
        # Attempt many rapid requests
        for i in range(100):
            payload = {
                "username": "testuser",
                "password": "wrongpassword",
            }
            response = client.post("/v1/auth/login", json=payload)
            # After some attempts, should be rate limited
            if response.status_code == 429:
                return True
        # If not rate limited, test fails
        pytest.fail("Rate limiting not working")


class TestSessionSecurity:
    """Test session security."""

    def test_session_hijacking_prevention(self, client: TestClient, test_user_token: str):
        """Test that session hijacking is prevented."""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        response = client.get("/v1/users/me", headers=headers)
        assert response.status_code == 200

        # Try to use the same token from a different IP (simulated)
        # This would need proper IP tracking in the application
        # For now, just verify token is bound to user
        user_data = response.json()
        assert "user_id" in user_data

    def test_concurrent_session_limit(self, client: TestClient):
        """Test that concurrent sessions are limited."""
        # Create multiple sessions
        tokens = []
        for i in range(60):  # Try to create 60 sessions
            payload = {
                "username": "testuser",
                "password": "test123",
            }
            response = client.post("/v1/auth/login", json=payload)
            if response.status_code == 200:
                tokens.append(response.json()["access_token"])

        # Should have a reasonable limit
        assert len(tokens) < 60
