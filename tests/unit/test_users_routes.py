"""
Unit tests for app/routes/users.py
"""
import pytest
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.models.schemas import TokenPayload

FAKE_USER = TokenPayload(
    user_id="user-123",
    username="testuser",
    roles=["admin"],
    exp=datetime.now(timezone.utc) + timedelta(hours=1),
    token_type="access",
    permissions=[],
)

FAKE_VIEWER = TokenPayload(
    user_id="user-456",
    username="viewer",
    roles=["viewer"],
    exp=datetime.now(timezone.utc) + timedelta(hours=1),
    token_type="access",
    permissions=[],
)


@asynccontextmanager
async def noop_lifespan(app):
    yield


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def client(db):
    from app.main import create_app
    from app.database.connection import get_db
    from app.services.authorization import get_current_user

    app = create_app(test_mode=True)
    app.router.lifespan_context = noop_lifespan
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def viewer_client(db):
    from app.main import create_app
    from app.database.connection import get_db
    from app.services.authorization import get_current_user

    app = create_app(test_mode=True)
    app.router.lifespan_context = noop_lifespan
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: FAKE_VIEWER
    return TestClient(app, raise_server_exceptions=False)


# ── POST /v1/users/register ──────────────────────────────────────────────────

def test_register_user_happy_path(client, db):
    mock_user = MagicMock()
    mock_user.user_id = "user-123"
    mock_user.username = "newuser"
    mock_user.email = "new@example.com"
    mock_user.created_at = datetime.now(timezone.utc)

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.create_user.return_value = mock_user
        resp = client.post(
            "/v1/users/register",
            json={"username": "newuser", "email": "new@example.com", "password": "Password1"},
        )
    assert resp.status_code == 201


def test_register_user_value_error(client, db):
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.create_user.side_effect = ValueError("Username taken")
        resp = client.post(
            "/v1/users/register",
            json={"username": "newuser", "email": "new@example.com", "password": "Password1"},
        )
    assert resp.status_code == 400


def test_register_user_exception(client, db):
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.create_user.side_effect = Exception("DB error")
        resp = client.post(
            "/v1/users/register",
            json={"username": "newuser", "email": "new@example.com", "password": "Password1"},
        )
    assert resp.status_code == 500


# ── GET /v1/users/verify-email ───────────────────────────────────────────────

def test_verify_email_valid_token(client, db):
    mock_user = MagicMock()
    mock_user.user_id = "user-123"
    db.query.return_value.filter.return_value.first.return_value = mock_user
    resp = client.get("/v1/users/verify-email?token=valid-token")
    assert resp.status_code == 200


def test_verify_email_invalid_token(client, db):
    db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/v1/users/verify-email?token=bad-token")
    assert resp.status_code == 400


# ── POST /v1/users/create-default ───────────────────────────────────────────

def test_create_default_user_happy_path(client, db):
    mock_user = MagicMock()
    mock_user.user_id = "admin-1"
    mock_user.username = "admin"
    mock_user.email = "admin@example.com"
    mock_user.created_at = datetime.now(timezone.utc)

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.create_default_user.return_value = mock_user
        resp = client.post("/v1/users/create-default")
    assert resp.status_code == 201


# ── GET /v1/users/ ───────────────────────────────────────────────────────────

def test_list_users_happy_path(client, db):
    mock_user = MagicMock()
    mock_user.user_id = "user-123"
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"
    mock_user.roles = ["admin"]
    mock_user.is_active = True
    mock_user.created_at = datetime.now(timezone.utc)
    mock_user.updated_at = datetime.now(timezone.utc)
    mock_user.last_login = None

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.list_users.return_value = [mock_user]
        mock_svc.return_value.get_user_stats.return_value = {
            "total_users": 1, "active_users": 1, "inactive_users": 0,
            "role_counts": {}, "total_sessions": 0, "active_sessions": 0,
        }
        resp = client.get("/v1/users/")
    assert resp.status_code == 200


def test_list_users_page_less_than_1(client, db):
    resp = client.get("/v1/users/?page=0")
    assert resp.status_code == 400


def test_list_users_per_page_too_large(client, db):
    resp = client.get("/v1/users/?per_page=200")
    assert resp.status_code == 400


# ── GET /v1/users/me ─────────────────────────────────────────────────────────

def test_get_me_happy_path(client, db):
    mock_user = MagicMock()
    mock_user.user_id = "user-123"
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"
    mock_user.roles = ["admin"]
    mock_user.is_active = True
    mock_user.created_at = datetime.now(timezone.utc)
    mock_user.updated_at = datetime.now(timezone.utc)
    mock_user.last_login = None

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.get_user.return_value = mock_user
        resp = client.get("/v1/users/me")
    assert resp.status_code == 200


def test_get_me_not_found(client, db):
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.get_user.return_value = None
        resp = client.get("/v1/users/me")
    assert resp.status_code == 404


# ── GET /v1/users/stats ──────────────────────────────────────────────────────

def test_get_user_stats_happy_path(client, db):
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.get_user_stats.return_value = {
            "total_users": 10, "active_users": 8, "inactive_users": 2,
            "role_counts": {"admin": 1, "viewer": 9},
            "total_sessions": 5, "active_sessions": 2,
        }
        resp = client.get("/v1/users/stats")
    assert resp.status_code == 200


# ── GET /v1/users/{user_id} ──────────────────────────────────────────────────

def test_get_user_happy_path(client, db):
    mock_user = MagicMock()
    mock_user.user_id = "user-123"
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"
    mock_user.roles = ["admin"]
    mock_user.is_active = True
    mock_user.created_at = datetime.now(timezone.utc)
    mock_user.updated_at = datetime.now(timezone.utc)
    mock_user.last_login = None

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.get_user.return_value = mock_user
        resp = client.get("/v1/users/user-123")
    assert resp.status_code == 200


def test_get_user_not_found(client, db):
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.get_user.return_value = None
        resp = client.get("/v1/users/nonexistent")
    assert resp.status_code == 404


# ── PATCH /v1/users/{user_id} ────────────────────────────────────────────────

def test_patch_user_own_user(client, db):
    mock_user = MagicMock()
    mock_user.user_id = "user-123"
    mock_user.username = "testuser"
    mock_user.email = "updated@example.com"
    mock_user.roles = ["admin"]
    mock_user.is_active = True
    mock_user.created_at = datetime.now(timezone.utc)
    mock_user.updated_at = datetime.now(timezone.utc)
    mock_user.last_login = None

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.update_user.return_value = mock_user
        resp = client.patch("/v1/users/user-123", json={"email": "updated@example.com"})
    assert resp.status_code == 200


def test_patch_user_forbidden(viewer_client, db):
    resp = viewer_client.patch("/v1/users/other-user", json={"email": "x@x.com"})
    assert resp.status_code == 403


def test_patch_user_not_found(client, db):
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.update_user.side_effect = ValueError("not found")
        resp = client.patch("/v1/users/user-123", json={"email": "x@x.com"})
    assert resp.status_code == 404


# ── PUT /v1/users/{user_id} ──────────────────────────────────────────────────

def test_put_user_own_user(client, db):
    mock_user = MagicMock()
    mock_user.user_id = "user-123"
    mock_user.username = "testuser"
    mock_user.email = "updated@example.com"
    mock_user.roles = ["admin"]
    mock_user.is_active = True
    mock_user.created_at = datetime.now(timezone.utc)
    mock_user.updated_at = datetime.now(timezone.utc)
    mock_user.last_login = None

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.update_user.return_value = mock_user
        resp = client.put("/v1/users/user-123", json={"email": "updated@example.com"})
    assert resp.status_code == 200


def test_put_user_forbidden(viewer_client, db):
    resp = viewer_client.put("/v1/users/other-user", json={"email": "x@x.com"})
    assert resp.status_code == 403


# ── POST /v1/users/reset-password ────────────────────────────────────────────

def test_reset_password_happy_path(client, db):
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.request_password_reset.return_value = None
        resp = client.post("/v1/users/reset-password", json={"email": "test@example.com"})
    assert resp.status_code == 200


def test_reset_password_user_not_found_still_200(client, db):
    from app.exceptions import UserNotFoundError
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.request_password_reset.side_effect = UserNotFoundError("user-123")
        resp = client.post("/v1/users/reset-password", json={"email": "missing@example.com"})
    assert resp.status_code == 200


# ── POST /v1/users/reset-password/confirm ────────────────────────────────────

def test_confirm_password_reset_happy_path(client, db):
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.confirm_password_reset.return_value = None
        resp = client.post(
            "/v1/users/reset-password/confirm",
            json={"token": "valid-token", "new_password": "NewPass1!"},
        )
    assert resp.status_code == 200


def test_confirm_password_reset_validation_error(client, db):
    from app.exceptions import ValidationError
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.confirm_password_reset.side_effect = ValidationError("bad token")
        resp = client.post(
            "/v1/users/reset-password/confirm",
            json={"token": "bad-token", "new_password": "NewPass1!"},
        )
    assert resp.status_code == 400


# ── POST /v1/users/{user_id}/reset-password ──────────────────────────────────

def test_reset_user_password_own_user(client, db):
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.reset_password.return_value = "newpass"
        resp = client.post(
            "/v1/users/user-123/reset-password",
            json={"new_password": "NewPass1!"},
        )
    assert resp.status_code == 200


def test_reset_user_password_forbidden(viewer_client, db):
    resp = viewer_client.post(
        "/v1/users/other-user/reset-password",
        json={"new_password": "NewPass1!"},
    )
    assert resp.status_code == 403


def test_reset_user_password_not_found(client, db):
    from app.exceptions import UserNotFoundError
    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.reset_password.side_effect = UserNotFoundError("user-123")
        resp = client.post(
            "/v1/users/user-123/reset-password",
            json={"new_password": "NewPass1!"},
        )
    assert resp.status_code == 404


# ── POST /v1/users/mfa/enroll ────────────────────────────────────────────────

def test_mfa_enroll_happy_path(client, db):
    mock_user = MagicMock()
    mock_user.mfa_secret = None
    mock_user.mfa_backup_codes = None
    mock_user.mfa_enabled = False

    with patch("app.routes.users.get_user_management_service") as mock_svc, \
         patch("app.routes.users.AuthManager") as mock_auth:
        mock_svc.return_value.get_user.return_value = mock_user
        mock_auth.return_value.generate_mfa_secret.return_value = "JBSWY3DPEHPK3PXP"
        mock_auth.return_value.get_mfa_qr_url.return_value = "otpauth://totp/..."
        resp = client.post("/v1/users/mfa/enroll")
    assert resp.status_code == 200


# ── POST /v1/users/mfa/enable ────────────────────────────────────────────────

def test_mfa_enable_happy_path(client, db):
    mock_user = MagicMock()
    mock_user.mfa_secret = "JBSWY3DPEHPK3PXP"
    mock_user.mfa_enabled = False

    with patch("app.routes.users.get_user_management_service") as mock_svc, \
         patch("app.routes.users.AuthManager") as mock_auth:
        mock_svc.return_value.get_user.return_value = mock_user
        mock_auth.return_value.verify_mfa_code.return_value = True
        resp = client.post("/v1/users/mfa/enable", json={"code": "123456"})
    assert resp.status_code == 200


def test_mfa_enable_no_secret(client, db):
    mock_user = MagicMock()
    mock_user.mfa_secret = None

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.get_user.return_value = mock_user
        resp = client.post("/v1/users/mfa/enable", json={"code": "123456"})
    assert resp.status_code == 400


def test_mfa_enable_invalid_code(client, db):
    mock_user = MagicMock()
    mock_user.mfa_secret = "JBSWY3DPEHPK3PXP"

    with patch("app.routes.users.get_user_management_service") as mock_svc, \
         patch("app.routes.users.AuthManager") as mock_auth:
        mock_svc.return_value.get_user.return_value = mock_user
        mock_auth.return_value.verify_mfa_code.return_value = False
        resp = client.post("/v1/users/mfa/enable", json={"code": "000000"})
    assert resp.status_code == 400


# ── POST /v1/users/mfa/disable ───────────────────────────────────────────────

def test_mfa_disable_happy_path(client, db):
    mock_user = MagicMock()
    mock_user.mfa_enabled = True
    mock_user.password_hash = "hashed"

    with patch("app.routes.users.get_user_management_service") as mock_svc, \
         patch("app.routes.users.AuthManager") as mock_auth:
        mock_svc.return_value.get_user.return_value = mock_user
        mock_auth.return_value.verify_password.return_value = True
        resp = client.post("/v1/users/mfa/disable", json={"password": "Password1"})
    assert resp.status_code == 200


def test_mfa_disable_not_enabled(client, db):
    mock_user = MagicMock()
    mock_user.mfa_enabled = False

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.get_user.return_value = mock_user
        resp = client.post("/v1/users/mfa/disable", json={"password": "Password1"})
    assert resp.status_code == 400


def test_mfa_disable_wrong_password(client, db):
    mock_user = MagicMock()
    mock_user.mfa_enabled = True
    mock_user.password_hash = "hashed"

    with patch("app.routes.users.get_user_management_service") as mock_svc, \
         patch("app.routes.users.AuthManager") as mock_auth:
        mock_svc.return_value.get_user.return_value = mock_user
        mock_auth.return_value.verify_password.return_value = False
        resp = client.post("/v1/users/mfa/disable", json={"password": "wrongpass"})
    assert resp.status_code == 400


# ── POST /v1/users/mfa/backup-code/verify ────────────────────────────────────

def test_mfa_backup_code_verify_happy_path(client, db):
    import hashlib
    code = "ABCDEF1234567890"
    hashed = hashlib.sha256(code.encode()).hexdigest()

    mock_user = MagicMock()
    mock_user.mfa_enabled = True
    mock_user.mfa_backup_codes = [hashed]

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.get_user.return_value = mock_user
        resp = client.post("/v1/users/mfa/backup-code/verify", json={"code": code})
    assert resp.status_code == 200


def test_mfa_backup_code_verify_not_enabled(client, db):
    mock_user = MagicMock()
    mock_user.mfa_enabled = False

    with patch("app.routes.users.get_user_management_service") as mock_svc:
        mock_svc.return_value.get_user.return_value = mock_user
        resp = client.post("/v1/users/mfa/backup-code/verify", json={"code": "ABCDEF1234567890"})
    assert resp.status_code == 400
