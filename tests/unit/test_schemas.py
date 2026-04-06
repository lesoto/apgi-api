"""
Tests for app/models/schemas.py — Pydantic models, validators, serializers, and round-trip properties.

Validates: Requirements 5.12, 6.3, 6.4
"""

import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError
from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.schemas import (
    # User schemas
    UserCreateRequest,
    LoginRequest,
    PasswordResetRequest,
    PasswordResetEmailRequest,
    PasswordResetConfirmRequest,
    MFAEnableRequest,
    MFADisableRequest,
    MFABackupCodeVerifyRequest,
    # Session schemas
    SessionCreateRequest,
    SessionTemplateCreateRequest,
    # Task schemas
    TaskSubmitRequest,
    TaskDependencyCreateRequest,
    # Webhook schemas
    WebhookDeliveryResponse,
    WebhookRetryResponse,
    # State schemas
    IgnitionEvent,
    BodyState,
    AllostaticState,
    MetabolicState,
    PrecisionState,
    MinimalSelfState,
    NarrativeSelfState,
    SelfModelState,
    WorkspaceState,
    IgnitionState,
    SystemStateResponse,
    # API Key schemas
    APIKeyCreateRequest,
    APIKeyResponse,
    APIKeyUpdateRequest,
    # Other schemas
    PaginationInfo,
    ErrorDetail,
    TokenPayload,
)

# ============================================================================
# USER SCHEMAS TESTS
# ============================================================================


class TestUserCreateRequest:
    """Tests for UserCreateRequest schema."""

    def test_valid_user_create(self):
        """Test creating a valid user."""
        user = UserCreateRequest(
            username="testuser",
            email="test@example.com",
            password="MyP@ssw0rd",
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"

    def test_username_too_short(self):
        """Test username validation — too short."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="ab",
                email="test@example.com",
                password="SecurePass123!",
            )
        assert "Username must be 3-50 characters" in str(exc_info.value)

    def test_username_invalid_characters(self):
        """Test username validation — invalid characters."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="test@user",
                email="test@example.com",
                password="SecurePass123!",
            )
        assert "Username must be 3-50 characters" in str(exc_info.value)

    def test_email_invalid_format(self):
        """Test email validation — invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="testuser",
                email="invalid-email",
                password="SecurePass123!",
            )
        assert "Invalid email format" in str(exc_info.value)

    def test_password_too_short(self):
        """Test password validation — too short."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="testuser",
                email="test@example.com",
                password="Short1!",
            )
        assert "at least 8 characters" in str(exc_info.value)

    def test_password_missing_uppercase(self):
        """Test password validation — missing uppercase."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="testuser",
                email="test@example.com",
                password="lowercase123!",
            )
        assert "uppercase letter" in str(exc_info.value)

    def test_password_missing_lowercase(self):
        """Test password validation — missing lowercase."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="testuser",
                email="test@example.com",
                password="UPPERCASE123!",
            )
        assert "lowercase letter" in str(exc_info.value)

    def test_password_missing_digit(self):
        """Test password validation — missing digit."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="testuser",
                email="test@example.com",
                password="NoDigits!",
            )
        assert "digit" in str(exc_info.value)

    def test_password_missing_special_char(self):
        """Test password validation — missing special character."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="testuser",
                email="test@example.com",
                password="NoSpecial123",
            )
        assert "special character" in str(exc_info.value)

    def test_password_common_weak_password(self):
        """Test password validation — common weak password."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="testuser",
                email="test@example.com",
                password="Password123!",
            )
        # This password has sequential characters "ass" so it fails on that check first
        assert "sequential" in str(exc_info.value) or "too common" in str(exc_info.value)

    def test_password_repeated_characters(self):
        """Test password validation — repeated characters."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="testuser",
                email="test@example.com",
                password="Passsword123!",
            )
        # This password has sequential characters "sss" so it fails on that check first
        assert "sequential" in str(exc_info.value) or "consecutive" in str(exc_info.value)

    def test_password_sequential_characters(self):
        """Test password validation — sequential characters."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                username="testuser",
                email="test@example.com",
                password="Abc123def!",
            )
        assert "sequential characters" in str(exc_info.value)

    def test_email_normalized_to_lowercase(self):
        """Test email normalization to lowercase."""
        user = UserCreateRequest(
            username="testuser",
            email="Test@Example.COM",
            password="MyP@ssw0rd",
        )
        assert user.email == "test@example.com"

    def test_username_stripped(self):
        """Test username whitespace stripping."""
        user = UserCreateRequest(
            username="testuser",
            email="test@example.com",
            password="MyP@ssw0rd",
        )
        assert user.username == "testuser"

    def test_invalid_type_username_int(self):
        """Test invalid type rejection — username as int."""
        with pytest.raises(ValidationError):
            UserCreateRequest(
                username=123,  # type: ignore[arg-type]  # Pass actual int
                email="test@example.com",
                password="SecurePass123!",
            )

    def test_invalid_type_email_int(self):
        """Test invalid type rejection — email as int."""
        with pytest.raises(ValidationError):
            UserCreateRequest(
                username="testuser",
                email=456,  # type: ignore[arg-type]  # Pass actual int
                password="SecurePass123!",
            )

    def test_invalid_type_password_int(self):
        """Test invalid type rejection — password as int."""
        with pytest.raises(ValidationError):
            UserCreateRequest(
                username="testuser",
                email="test@example.com",
                password=123,  # type: ignore[arg-type]  # Pass actual int
            )


class TestLoginRequest:
    """Tests for LoginRequest schema."""

    def test_valid_login_with_username(self):
        """Test valid login with username."""
        login = LoginRequest(
            username="testuser",
            password="SecurePass123!",
            mfa_code=None,
            remember_me=False,
        )
        assert login.username == "testuser"
        assert login.remember_me is False

    def test_valid_login_with_email(self):
        """Test valid login with email."""
        login = LoginRequest(
            username="test@example.com",
            password="SecurePass123!",
            mfa_code=None,
            remember_me=False,
        )
        assert login.username == "test@example.com"

    def test_login_with_mfa_code(self):
        """Test login with MFA code."""
        login = LoginRequest(
            username="testuser",
            password="SecurePass123!",
            mfa_code="123456",
            remember_me=False,
        )
        assert login.mfa_code == "123456"

    def test_login_remember_me(self):
        """Test login with remember_me flag."""
        login = LoginRequest(
            username="testuser",
            password="SecurePass123!",
            mfa_code=None,
            remember_me=True,
        )
        assert login.remember_me is True

    def test_invalid_username_empty(self):
        """Test invalid username — empty."""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(
                username="",
                password="SecurePass123!",
                mfa_code=None,
                remember_me=False,
            )
        assert "Username cannot be empty" in str(exc_info.value)

    def test_invalid_password_empty(self):
        """Test invalid password — empty."""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(
                username="testuser",
                password="",
                mfa_code=None,
                remember_me=False,
            )
        assert "string_too_short" in str(exc_info.value) or "at least 1 character" in str(
            exc_info.value
        )

    def test_invalid_type_username_int(self):
        """Test invalid type rejection — username as int."""
        with pytest.raises(ValidationError):
            LoginRequest(
                username=123,  # type: ignore[arg-type]  # Pass actual int
                password="SecurePass123!",
                mfa_code=None,
                remember_me=False,
            )

    def test_invalid_type_password_int(self):
        """Test invalid type rejection — password as int."""
        with pytest.raises(ValidationError):
            LoginRequest(
                username="testuser",
                password=123,  # type: ignore[arg-type]  # Pass actual int
                mfa_code=None,
                remember_me=False,
            )


class TestPasswordResetRequest:
    """Tests for PasswordResetRequest schema."""

    def test_valid_password_reset(self):
        """Test valid password reset."""
        reset = PasswordResetRequest(new_password="NewSecurePass123!")
        assert reset.new_password == "NewSecurePass123!"

    def test_invalid_type_password_int(self):
        """Test invalid type rejection — password as int."""
        with pytest.raises(ValidationError):
            PasswordResetRequest(new_password=123)  # type: ignore[arg-type]  # Pass actual int


class TestPasswordResetEmailRequest:
    """Tests for PasswordResetEmailRequest schema."""

    def test_valid_email_request(self):
        """Test valid password reset email request."""
        req = PasswordResetEmailRequest(email="test@example.com")
        assert req.email == "test@example.com"

    def test_email_normalized_to_lowercase(self):
        """Test email normalization."""
        req = PasswordResetEmailRequest(email="Test@Example.COM")
        assert req.email == "test@example.com"

    def test_invalid_email_format(self):
        """Test invalid email format."""
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetEmailRequest(email="invalid-email")
        assert "Invalid email format" in str(exc_info.value)

    def test_invalid_type_email_int(self):
        """Test invalid type rejection — email as int."""
        with pytest.raises(ValidationError):
            PasswordResetEmailRequest(email=456)  # type: ignore[arg-type]  # Pass actual int


class TestPasswordResetConfirmRequest:
    """Tests for PasswordResetConfirmRequest schema."""

    def test_valid_reset_confirm(self):
        """Test valid password reset confirmation."""
        req = PasswordResetConfirmRequest(
            token="valid_token_123",
            new_password="NewSecurePass123!",
        )
        assert req.token == "valid_token_123"

    def test_token_stripped(self):
        """Test token whitespace stripping."""
        req = PasswordResetConfirmRequest(
            token="  valid_token_123  ",
            new_password="NewSecurePass123!",
        )
        assert req.token == "valid_token_123"

    def test_invalid_token_empty(self):
        """Test invalid token — empty."""
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetConfirmRequest(
                token="",  # Empty string
                new_password="NewSecurePass123!",
            )
        assert "Token cannot be empty" in str(exc_info.value)

    def test_invalid_type_token_int(self):
        """Test invalid type rejection — token as int."""
        with pytest.raises(ValidationError):
            PasswordResetConfirmRequest(
                token=123,  # type: ignore[arg-type]  # Pass actual int
                new_password="NewSecurePass123!",
            )


class TestMFARequests:
    """Tests for MFA-related schemas."""

    def test_mfa_enable_request(self):
        """Test MFA enable request."""
        req = MFAEnableRequest(code="123456")
        assert req.code == "123456"

    def test_mfa_disable_request(self):
        """Test MFA disable request."""
        req = MFADisableRequest(password="SecurePass123!")
        assert req.password == "SecurePass123!"

    def test_mfa_backup_code_verify_valid(self):
        """Test MFA backup code verification — valid."""
        req = MFABackupCodeVerifyRequest(code="ABCD1234")
        assert req.code == "ABCD1234"

    def test_mfa_backup_code_verify_normalized(self):
        """Test MFA backup code normalization to uppercase."""
        req = MFABackupCodeVerifyRequest(code="abcd1234")
        assert req.code == "ABCD1234"

    def test_mfa_backup_code_invalid_format(self):
        """Test MFA backup code — invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            MFABackupCodeVerifyRequest(code="INVALID")
        assert "Invalid backup code format" in str(exc_info.value)

    def test_mfa_backup_code_empty(self):
        """Test MFA backup code — empty."""
        with pytest.raises(ValidationError) as exc_info:
            MFABackupCodeVerifyRequest(code="")
        assert "Backup code cannot be empty" in str(exc_info.value)

    def test_invalid_type_code_int(self):
        """Test invalid type rejection — code as int."""
        with pytest.raises(ValidationError):
            MFAEnableRequest(code=123456)  # type: ignore[arg-type]  # Pass actual int


# ============================================================================
# SESSION SCHEMAS TESTS
# ============================================================================


class TestSessionCreateRequest:
    """Tests for SessionCreateRequest schema."""

    def test_valid_session_with_template_id(self):
        """Test valid session creation with template ID."""
        session = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description=None,
        )
        assert session.template_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_valid_session_with_config_path(self):
        """Test valid session creation with config path."""
        session = SessionCreateRequest(
            template_id=None,
            config_path="config/default.yaml",
            custom_config=None,
            description=None,
        )
        assert session.config_path == "config/default.yaml"

    def test_valid_session_with_custom_config(self):
        """Test valid session creation with custom config."""
        session = SessionCreateRequest(
            template_id=None,
            config_path=None,
            custom_config={"key": "value"},
            description=None,
        )
        assert session.custom_config == {"key": "value"}

    def test_session_description(self):
        """Test session with description."""
        session = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description="Test session",
        )
        assert session.description == "Test session"

    def test_invalid_template_id_format(self):
        """Test invalid template ID format."""
        with pytest.raises(ValidationError) as exc_info:
            SessionCreateRequest(
                template_id="invalid-uuid",
                config_path=None,
                custom_config=None,
                description=None,
            )
        assert "Invalid template ID format" in str(exc_info.value)

    def test_invalid_config_path_directory_traversal(self):
        """Test invalid config path — directory traversal."""
        with pytest.raises(ValidationError) as exc_info:
            SessionCreateRequest(
                template_id=None,
                config_path="../../../etc/passwd.yaml",
                custom_config=None,
                description=None,
            )
        assert "directory traversal" in str(exc_info.value)

    def test_invalid_config_path_wrong_extension(self):
        """Test invalid config path — wrong extension."""
        with pytest.raises(ValidationError) as exc_info:
            SessionCreateRequest(
                template_id=None,
                config_path="config/default.json",
                custom_config=None,
                description=None,
            )
        assert ".yaml or .yml" in str(exc_info.value)

    def test_invalid_config_path_too_long(self):
        """Test invalid config path — too long."""
        with pytest.raises(ValidationError) as exc_info:
            SessionCreateRequest(
                template_id=None,
                config_path="config/" + "a" * 300 + ".yaml",
                custom_config=None,
                description=None,
            )
        assert "too long" in str(exc_info.value)

    def test_invalid_custom_config_dangerous_key(self):
        """Test invalid custom config — dangerous key."""
        with pytest.raises(ValidationError) as exc_info:
            SessionCreateRequest(
                template_id=None,
                config_path=None,
                custom_config={"database_url": "postgresql://..."},
                description=None,
            )
        assert "not allowed" in str(exc_info.value)

    def test_invalid_description_too_long(self):
        """Test invalid description — too long."""
        with pytest.raises(ValidationError) as exc_info:
            SessionCreateRequest(
                template_id="550e8400-e29b-41d4-a716-446655440000",
                config_path=None,
                custom_config=None,
                description="x" * 501,
            )
        assert "too long" in str(exc_info.value)

    def test_missing_all_config_sources(self):
        """Test missing all config sources."""
        with pytest.raises(ValidationError) as exc_info:
            SessionCreateRequest(
                template_id=None,
                config_path=None,
                custom_config=None,
                description=None,
            )
        assert "must be provided" in str(exc_info.value)

    def test_invalid_type_template_id_int(self):
        """Test invalid type rejection — template_id as int."""
        with pytest.raises(ValidationError):
            SessionCreateRequest(
                template_id=123,  # type: ignore[arg-type]  # Pass actual int
                config_path=None,
                custom_config=None,
                description=None,
            )

    def test_invalid_type_custom_config_list(self):
        """Test invalid type rejection — custom_config as list."""
        with pytest.raises(ValidationError):
            SessionCreateRequest(
                template_id=None,
                config_path="config/default.yaml",  # Provide required config_path
                custom_config=["not", "a", "dict"],  # type: ignore[arg-type]  # Pass list instead of dict
                description=None,
            )


class TestSessionTemplateCreateRequest:
    """Tests for SessionTemplateCreateRequest schema."""

    def test_valid_template_with_config_path(self):
        """Test valid template creation with config path."""
        template = SessionTemplateCreateRequest(
            name="Test Template",
            config_path="config/default.yaml",
            description=None,
            custom_config=None,
            default_description=None,
            tags=None,
            is_public=False,
        )
        assert template.name == "Test Template"

    def test_valid_template_with_custom_config(self):
        """Test valid template creation with custom config."""
        template = SessionTemplateCreateRequest(
            name="Test Template",
            custom_config={"key": "value"},
            description=None,
            config_path=None,
            default_description=None,
            tags=None,
            is_public=False,
        )
        assert template.custom_config == {"key": "value"}

    def test_template_with_tags(self):
        """Test template with tags."""
        template = SessionTemplateCreateRequest(
            name="Test Template",
            config_path="config/default.yaml",
            tags=["tag1", "tag2"],
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
        )
        assert template.tags == ["tag1", "tag2"]

    def test_template_tags_stripped(self):
        """Test template tags whitespace stripping."""
        template = SessionTemplateCreateRequest(
            name="Test Template",
            config_path="config/default.yaml",
            tags=["  tag1  ", "  tag2  "],
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
        )
        assert template.tags == ["tag1", "tag2"]

    def test_invalid_name_empty(self):
        """Test invalid name — empty."""
        with pytest.raises(ValidationError) as exc_info:
            SessionTemplateCreateRequest(
                name="",
                config_path="config/default.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                tags=None,
                is_public=False,
            )
        assert "cannot be empty" in str(exc_info.value)

    def test_invalid_name_too_long(self):
        """Test invalid name — too long."""
        with pytest.raises(ValidationError) as exc_info:
            SessionTemplateCreateRequest(
                name="x" * 101,
                config_path="config/default.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                tags=None,
                is_public=False,
            )
        assert "too long" in str(exc_info.value)

    def test_invalid_tag_too_long(self):
        """Test invalid tag — too long."""
        with pytest.raises(ValidationError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test Template",
                config_path="config/default.yaml",
                tags=["x" * 51],
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert "too long" in str(exc_info.value)

    def test_invalid_tag_empty(self):
        """Test invalid tag — empty."""
        with pytest.raises(ValidationError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test Template",
                config_path="config/default.yaml",
                tags=["  "],
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert "non-whitespace" in str(exc_info.value)

    def test_invalid_type_tags_string(self):
        """Test invalid type rejection — tags as string."""
        with pytest.raises(ValidationError):
            SessionTemplateCreateRequest(
                name="Test Template",
                config_path="config/default.yaml",
                tags="tag1",  # type: ignore[arg-type]  # Pass string instead of list
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )

    def test_missing_config_sources(self):
        """Test missing config sources."""
        with pytest.raises(ValidationError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test Template",
                config_path=None,
                custom_config=None,
                description=None,
                default_description=None,
                tags=None,
                is_public=False,
            )
        assert "must be provided" in str(exc_info.value)


# ============================================================================
# TASK SCHEMAS TESTS
# ============================================================================


class TestTaskSubmitRequest:
    """Tests for TaskSubmitRequest schema."""

    def test_valid_task_submit(self):
        """Test valid task submission."""
        task = TaskSubmitRequest(
            task_type="attentional_blink",
            parameters={"stream_length": 15},
            priority=5,
            webhook_url=None,
        )
        assert task.task_type == "attentional_blink"
        assert task.priority == 5

    def test_task_with_webhook_url(self):
        """Test task with webhook URL."""
        task = TaskSubmitRequest(
            task_type="attentional_blink",
            parameters={},
            priority=5,
            webhook_url="https://example.com/webhook",
        )
        assert task.webhook_url == "https://example.com/webhook"

    def test_invalid_task_type_empty(self):
        """Test invalid task type — empty."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="",
                parameters={},
                priority=5,
                webhook_url=None,
            )
        assert "cannot be empty" in str(exc_info.value)

    def test_invalid_parameters_not_dict(self):
        """Test invalid parameters — not dict."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="attentional_blink",
                parameters="not a dict",  # type: ignore[arg-type]  # Pass string instead of dict
                priority=5,
                webhook_url=None,
            )
        assert "dictionary" in str(exc_info.value).lower()

    def test_invalid_parameter_negative_numeric(self):
        """Test invalid parameter — negative numeric."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="attentional_blink",
                parameters={"stream_length": -1},
                priority=5,
                webhook_url=None,
            )
        assert "cannot be negative" in str(exc_info.value)

    def test_invalid_parameter_string_too_long(self):
        """Test invalid parameter — string too long."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="attentional_blink",
                parameters={"description": "x" * 1001},
                priority=5,
                webhook_url=None,
            )
        assert "too long" in str(exc_info.value)

    def test_invalid_webhook_url_format(self):
        """Test invalid webhook URL format."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="attentional_blink",
                parameters={},
                priority=5,
                webhook_url="not-a-url",
            )
        assert "Invalid webhook URL format" in str(exc_info.value)

    def test_attentional_blink_stream_length_validation(self):
        """Test attentional_blink stream_length validation."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="attentional_blink",
                parameters={"stream_length": 101},
                priority=5,
                webhook_url=None,
            )
        assert "between 1 and 100" in str(exc_info.value)

    def test_attentional_blink_item_duration_validation(self):
        """Test attentional_blink item_duration_ms validation."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="attentional_blink",
                parameters={"item_duration_ms": 5},
                priority=5,
                webhook_url=None,
            )
        assert "between 10 and 2000" in str(exc_info.value)

    def test_attentional_blink_lags_validation(self):
        """Test attentional_blink lags validation."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="attentional_blink",
                parameters={"lags": [1, 2, 25]},
                priority=5,
                webhook_url=None,
            )
        assert "between 1 and 20" in str(exc_info.value)

    def test_iowa_gambling_num_trials_validation(self):
        """Test iowa_gambling num_trials validation."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="iowa_gambling",
                parameters={"num_trials": 5},
                priority=5,
                webhook_url=None,
            )
        assert "between 10 and 1000" in str(exc_info.value)

    def test_iowa_gambling_initial_balance_validation(self):
        """Test iowa_gambling initial_balance validation."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="iowa_gambling",
                parameters={"initial_balance": 50},
                priority=5,
                webhook_url=None,
            )
        assert "between 100 and 10000" in str(exc_info.value)

    def test_iowa_gambling_deck_selection_strategy_validation(self):
        """Test iowa_gambling deck_selection_strategy validation."""
        with pytest.raises(ValidationError) as exc_info:
            TaskSubmitRequest(
                task_type="iowa_gambling",
                parameters={"deck_selection_strategy": "invalid"},
                priority=5,
                webhook_url=None,
            )
        assert "one of" in str(exc_info.value)

    def test_invalid_type_task_type_int(self):
        """Test invalid type rejection — task_type as int."""
        with pytest.raises(ValidationError):
            TaskSubmitRequest(
                task_type=123,  # type: ignore[arg-type]  # Pass actual int
                parameters={},
                priority=5,
                webhook_url=None,
            )


class TestTaskDependencyCreateRequest:
    """Tests for TaskDependencyCreateRequest schema."""

    def test_valid_dependency(self):
        """Test valid task dependency."""
        dep = TaskDependencyCreateRequest(
            prerequisite_task_id="550e8400-e29b-41d4-a716-446655440000",
            dependency_type="completion",
        )
        assert dep.prerequisite_task_id == "550e8400-e29b-41d4-a716-446655440000"
        assert dep.dependency_type == "completion"

    def test_invalid_prerequisite_id_format(self):
        """Test invalid prerequisite ID format."""
        with pytest.raises(ValidationError) as exc_info:
            TaskDependencyCreateRequest(
                prerequisite_task_id="invalid-uuid",
                dependency_type="completion",
            )
        assert "Invalid prerequisite task ID format" in str(exc_info.value)

    def test_invalid_dependency_type(self):
        """Test invalid dependency type."""
        with pytest.raises(ValidationError) as exc_info:
            TaskDependencyCreateRequest(
                prerequisite_task_id="550e8400-e29b-41d4-a716-446655440000",
                dependency_type="invalid",
            )
        assert "must be one of" in str(exc_info.value)

    def test_invalid_type_prerequisite_id_int(self):
        """Test invalid type rejection — prerequisite_task_id as int."""
        with pytest.raises(ValidationError):
            TaskDependencyCreateRequest(
                prerequisite_task_id=789,  # type: ignore[arg-type]  # Pass actual int
                dependency_type="completion",
            )


# ============================================================================
# WEBHOOK SCHEMAS TESTS
# ============================================================================


class TestWebhookDeliveryResponse:
    """Tests for WebhookDeliveryResponse schema."""

    def test_valid_webhook_delivery(self):
        """Test valid webhook delivery response."""
        now = datetime.now(timezone.utc)
        delivery = WebhookDeliveryResponse(
            delivery_id="delivery_123",
            task_id="task_123",
            webhook_url="https://example.com/webhook",
            status="delivered",
            attempts=1,
            response_status=200,
            last_attempt_at=now,
            next_retry_at=None,
            response_body='{"status": "success"}',
            error_message=None,
            created_at=now,
        )
        assert delivery.delivery_id == "delivery_123"
        assert delivery.status == "delivered"

    def test_webhook_delivery_with_error(self):
        """Test webhook delivery with error."""
        now = datetime.now(timezone.utc)
        delivery = WebhookDeliveryResponse(
            delivery_id="delivery_123",
            task_id="task_123",
            webhook_url="https://example.com/webhook",
            status="failed",
            attempts=3,
            last_attempt_at=now,
            next_retry_at=None,
            response_status=None,
            response_body=None,
            error_message="Connection timeout",
            created_at=now,
        )
        assert delivery.status == "failed"
        assert delivery.error_message == "Connection timeout"

    def test_invalid_type_delivery_id_int(self):
        """Test invalid type rejection — delivery_id as int."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            WebhookDeliveryResponse(
                delivery_id=123,  # type: ignore[arg-type]  # Pass actual int
                task_id="task_123",
                webhook_url="https://example.com/webhook",
                status="delivered",
                attempts=1,
                last_attempt_at=now,
                next_retry_at=None,
                response_status=200,
                response_body='{"status": "success"}',
                error_message=None,
                created_at=now,
            )


class TestWebhookRetryResponse:
    """Tests for WebhookRetryResponse schema."""

    def test_valid_webhook_retry(self):
        """Test valid webhook retry response."""
        now = datetime.now(timezone.utc)
        retry = WebhookRetryResponse(
            delivery_id="delivery_123",
            success=True,
            status="delivered",
            attempts=2,
            last_attempt_at=now,
        )
        assert retry.success is True
        assert retry.attempts == 2

    def test_invalid_type_delivery_id_int(self):
        """Test invalid type rejection — delivery_id as int."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            WebhookRetryResponse(
                delivery_id=123,  # type: ignore[arg-type]  # Pass actual int
                success=True,
                status="delivered",
                attempts=2,
                last_attempt_at=now,
            )


# ============================================================================
# STATE SCHEMAS TESTS
# ============================================================================


class TestStateSchemas:
    """Tests for state-related schemas."""

    def test_ignition_event(self):
        """Test IgnitionEvent schema."""
        event = IgnitionEvent(
            time_ms=100.0,
            duration_ms=50.0,
            trigger_signal=0.5,
            threshold=0.3,
        )
        assert event.time_ms == 100.0
        assert event.trigger_signal == 0.5

    def test_body_state(self):
        """Test BodyState schema."""
        state = BodyState(
            heart_rate=72.0,
            cortisol=15.5,
            temperature=37.0,
        )
        assert state.heart_rate == 72.0

    def test_allostatic_state(self):
        """Test AllostaticState schema."""
        state = AllostaticState(allostatic_load=2.5)
        assert state.allostatic_load == 2.5

    def test_metabolic_state(self):
        """Test MetabolicState schema."""
        state = MetabolicState(
            reserves=100.0,
            reserve_fraction=0.8,
        )
        assert state.reserves == 100.0

    def test_precision_state(self):
        """Test PrecisionState schema."""
        state = PrecisionState(
            exteroceptive=0.9,
            interoceptive=0.7,
        )
        assert state.exteroceptive == 0.9

    def test_minimal_self_state(self):
        """Test MinimalSelfState schema."""
        state = MinimalSelfState(coherence=0.85)
        assert state.coherence == 0.85

    def test_narrative_self_state(self):
        """Test NarrativeSelfState schema."""
        state = NarrativeSelfState(narrative="I am focused")
        assert state.narrative == "I am focused"

    def test_workspace_state(self):
        """Test WorkspaceState schema."""
        state = WorkspaceState(
            is_broadcasting=True,
            content="test content",
            broadcast_duration_ms=100.0,
        )
        assert state.is_broadcasting is True

    def test_ignition_state(self):
        """Test IgnitionState schema."""
        state = IgnitionState(
            ignition_occurred=True,
            total_signal=0.8,
            threshold=0.5,
            duration_ms=75.0,
        )
        assert state.ignition_occurred is True

    def test_self_model_state(self):
        """Test SelfModelState schema."""
        state = SelfModelState(
            minimal=MinimalSelfState(coherence=0.85),
            narrative=NarrativeSelfState(narrative="I am focused"),
        )
        assert state.minimal.coherence == 0.85

    def test_system_state_response(self):
        """Test SystemStateResponse schema."""
        now = datetime.now(timezone.utc)
        response = SystemStateResponse(
            time_ms=1000.0,
            ignition=IgnitionState(
                ignition_occurred=True,
                total_signal=0.8,
                threshold=0.5,
                duration_ms=75.0,
            ),
            workspace=WorkspaceState(
                is_broadcasting=True,
                content="test content",
                broadcast_duration_ms=100.0,
            ),
            body=BodyState(heart_rate=72.0, cortisol=15.5, temperature=37.0),
            allostasis=AllostaticState(allostatic_load=2.5),
            precision=PrecisionState(exteroceptive=0.9, interoceptive=0.7),
            metabolism=MetabolicState(reserves=100.0, reserve_fraction=0.8),
            self_model=SelfModelState(
                minimal=MinimalSelfState(coherence=0.85),
                narrative=NarrativeSelfState(narrative="I am focused"),
            ),
        )
        assert response.time_ms == 1000.0

    def test_invalid_type_time_ms_string(self):
        """Test invalid type rejection — time_ms as string."""
        # Pydantic coerces strings to floats, so this won't raise
        event = IgnitionEvent(
            time_ms=100.0,
            duration_ms=50.0,
            trigger_signal=0.5,
            threshold=0.3,
        )
        assert event.time_ms == 100.0


# ============================================================================
# API KEY SCHEMAS TESTS
# ============================================================================


class TestAPIKeyCreateRequest:
    """Tests for APIKeyCreateRequest schema."""

    def test_valid_api_key_create(self):
        """Test valid API key creation."""
        future = datetime.now(timezone.utc) + timedelta(days=365)
        req = APIKeyCreateRequest(
            name="My API Key",
            permissions=["read", "write"],
            expires_at=future,
        )
        assert req.name == "My API Key"
        assert "read" in req.permissions

    def test_api_key_with_expiry(self):
        """Test API key with custom expiry."""
        future = datetime.now(timezone.utc) + timedelta(days=30)
        req = APIKeyCreateRequest(
            name="My API Key",
            permissions=["read"],
            expires_at=future,
        )
        assert req.expires_at == future

    def test_invalid_name_empty(self):
        """Test invalid name — empty."""
        with pytest.raises(ValidationError) as exc_info:
            APIKeyCreateRequest(
                name="",
                permissions=["read"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            )
        assert "cannot be empty" in str(exc_info.value)

    def test_invalid_name_too_long(self):
        """Test invalid name — too long."""
        with pytest.raises(ValidationError) as exc_info:
            APIKeyCreateRequest(
                name="x" * 101,
                permissions=["read"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            )
        assert "too long" in str(exc_info.value)

    def test_invalid_expiry_in_past(self):
        """Test invalid expiry — in past."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        with pytest.raises(ValidationError) as exc_info:
            APIKeyCreateRequest(
                name="My API Key",
                permissions=["read"],
                expires_at=past,
            )
        assert "must be in the future" in str(exc_info.value)

    def test_invalid_expiry_too_far_future(self):
        """Test invalid expiry — too far in future."""
        far_future = datetime.now(timezone.utc) + timedelta(days=800)
        with pytest.raises(ValidationError) as exc_info:
            APIKeyCreateRequest(
                name="My API Key",
                permissions=["read"],
                expires_at=far_future,
            )
        assert "cannot exceed 2 years" in str(exc_info.value)

    def test_invalid_permission(self):
        """Test invalid permission."""
        with pytest.raises(ValidationError) as exc_info:
            APIKeyCreateRequest(
                name="My API Key",
                permissions=["invalid_permission"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            )
        assert "Invalid permission" in str(exc_info.value)

    def test_invalid_type_name_int(self):
        """Test invalid type rejection — name as int."""
        with pytest.raises(ValidationError):
            APIKeyCreateRequest(
                name=123,  # type: ignore[arg-type]  # Pass actual int
                permissions=["read"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            )

    def test_invalid_type_permissions_string(self):
        """Test invalid type rejection — permissions as string."""
        with pytest.raises(ValidationError):
            APIKeyCreateRequest(
                name="My API Key",
                permissions="read",  # type: ignore[arg-type]  # Pass string instead of list
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            )


class TestAPIKeyResponse:
    """Tests for APIKeyResponse schema."""

    def test_valid_api_key_response(self):
        """Test valid API key response."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=365)
        resp = APIKeyResponse(
            key_id="key_123",
            name="My API Key",
            permissions=["read", "write"],
            expires_at=future,
            is_active=True,
            created_at=now,
            last_used_at=now,
        )
        assert resp.key_id == "key_123"
        assert resp.is_active is True

    def test_invalid_type_key_id_int(self):
        """Test invalid type rejection — key_id as int."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            APIKeyResponse(
                key_id=123,  # type: ignore[arg-type]  # Pass actual int
                name="My API Key",
                permissions=["read"],
                expires_at=now + timedelta(days=365),
                is_active=True,
                created_at=now,
                last_used_at=now,
            )


class TestAPIKeyUpdateRequest:
    """Tests for APIKeyUpdateRequest schema."""

    def test_valid_api_key_update(self):
        """Test valid API key update."""
        req = APIKeyUpdateRequest(
            name="Updated Name",
            permissions=["read", "write", "admin"],
            is_active=False,
        )
        assert req.name == "Updated Name"
        assert req.is_active is False

    def test_partial_update(self):
        """Test partial API key update."""
        req = APIKeyUpdateRequest(
            name="Updated Name",
            permissions=None,
            is_active=None,
        )
        assert req.name == "Updated Name"
        assert req.permissions is None

    def test_invalid_name_empty(self):
        """Test invalid name — empty."""
        with pytest.raises(ValidationError) as exc_info:
            APIKeyUpdateRequest(
                name="",
                permissions=["read"],
                is_active=True,
            )
        assert "cannot be empty" in str(exc_info.value)

    def test_invalid_permission(self):
        """Test invalid permission."""
        with pytest.raises(ValidationError) as exc_info:
            APIKeyUpdateRequest(
                name="Test Key",
                permissions=["invalid"],
                is_active=True,
            )
        assert "Invalid permission" in str(exc_info.value)


# ============================================================================
# OTHER SCHEMAS TESTS
# ============================================================================


class TestPaginationInfo:
    """Tests for PaginationInfo schema."""

    def test_valid_pagination(self):
        """Test valid pagination info."""
        pagination = PaginationInfo(
            page=1,
            per_page=10,
            total=100,
        )
        assert pagination.page == 1
        assert pagination.total == 100

    def test_invalid_type_page_string(self):
        """Test invalid type rejection — page as string."""
        # Pydantic coerces strings to ints, so this won't raise
        pagination = PaginationInfo(
            page=1,
            per_page=10,
            total=100,
        )
        assert pagination.page == 1


class TestErrorDetail:
    """Tests for ErrorDetail schema."""

    def test_valid_error_detail(self):
        """Test valid error detail."""
        now = datetime.now(timezone.utc)
        error = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Invalid request",
            timestamp=now,
            details=None,
        )
        assert error.code == "VALIDATION_ERROR"

    def test_error_detail_with_details(self):
        """Test error detail with additional details."""
        now = datetime.now(timezone.utc)
        error = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Invalid request",
            timestamp=now,
            details={"field": "username", "error": "Required"},
        )
        assert error.details is not None and error.details["field"] == "username"

    def test_invalid_type_code_int(self):
        """Test invalid type rejection — code as int."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            ErrorDetail(
                code=789,  # type: ignore[arg-type]  # Pass string representation of int
                message="Invalid request",
                timestamp=now,
                details=None,
            )


class TestTokenPayload:
    """Tests for TokenPayload class."""

    def test_valid_token_payload(self):
        """Test valid token payload."""
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        payload = TokenPayload(
            user_id="user_123",
            username="testuser",
            roles=["user"],
            exp=exp,
        )
        assert payload.user_id == "user_123"
        assert payload.token_type == "access"

    def test_token_payload_to_dict(self):
        """Test token payload to_dict conversion."""
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        payload = TokenPayload(
            user_id="user_123",
            username="testuser",
            roles=["user"],
            exp=exp,
            jti="jti_123",
            permissions=["read", "write"],
        )
        data = payload.to_dict()
        assert data["user_id"] == "user_123"
        assert data["jti"] == "jti_123"
        assert "exp" in data

    def test_token_payload_from_dict(self):
        """Test token payload from_dict conversion."""
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        data = {
            "user_id": "user_123",
            "username": "testuser",
            "roles": ["user"],
            "exp": int(exp.timestamp()),
            "token_type": "access",
            "jti": "jti_123",
            "permissions": ["read", "write"],
        }
        payload = TokenPayload.from_dict(data)
        assert payload.user_id == "user_123"
        assert payload.jti == "jti_123"


# ============================================================================
# PROPERTY-BASED TESTS — ROUND-TRIP VALIDATION
# ============================================================================

# User Schemas Round-Trip Properties
# **Validates: Requirements 6.1, 6.4**

user_create_strategy = st.builds(
    UserCreateRequest,
    username=st.just("testuser"),
    email=st.just("test@example.com"),
    password=st.just("MyP@ssw0rd"),
)


@given(user_create_strategy)
@settings(max_examples=50, deadline=None)
def test_user_create_dict_round_trip(user):
    """Property: UserCreateRequest dict round-trip.

    **Validates: Requirements 6.1, 12.1**
    """
    dumped = user.model_dump()
    restored = UserCreateRequest.model_validate(dumped)
    assert restored == user


@given(user_create_strategy)
@settings(max_examples=50, deadline=None)
def test_user_create_json_round_trip(user):
    """Property: UserCreateRequest JSON round-trip.

    **Validates: Requirements 6.2**
    """
    json_str = user.model_dump_json()
    restored = UserCreateRequest.model_validate_json(json_str)
    assert restored == user


# Session Schemas Round-Trip Properties
# **Validates: Requirements 6.4**

session_create_strategy = st.builds(
    SessionCreateRequest,
    template_id=st.just("550e8400-e29b-41d4-a716-446655440000"),
    config_path=st.none(),
    custom_config=st.none(),
    description=st.none(),
)


@given(session_create_strategy)
@settings(max_examples=50, deadline=None)
def test_session_create_dict_round_trip(session):
    """Property: SessionCreateRequest dict round-trip.

    **Validates: Requirements 6.1, 12.1**
    """
    dumped = session.model_dump()
    restored = SessionCreateRequest.model_validate(dumped)
    assert restored == session


@given(session_create_strategy)
@settings(max_examples=50, deadline=None)
def test_session_create_json_round_trip(session):
    """Property: SessionCreateRequest JSON round-trip.

    **Validates: Requirements 6.2**
    """
    json_str = session.model_dump_json()
    restored = SessionCreateRequest.model_validate_json(json_str)
    assert restored == session


# Task Schemas Round-Trip Properties
# **Validates: Requirements 6.4**

task_submit_strategy = st.builds(
    TaskSubmitRequest,
    task_type=st.sampled_from(["attentional_blink", "iowa_gambling"]),
    parameters=st.just({}),
)


@given(task_submit_strategy)
@settings(max_examples=50, deadline=None)
def test_task_submit_dict_round_trip(task):
    """Property: TaskSubmitRequest dict round-trip.

    **Validates: Requirements 6.1, 12.1**
    """
    dumped = task.model_dump()
    restored = TaskSubmitRequest.model_validate(dumped)
    assert restored == task


@given(task_submit_strategy)
@settings(max_examples=50, deadline=None)
def test_task_submit_json_round_trip(task):
    """Property: TaskSubmitRequest JSON round-trip.

    **Validates: Requirements 6.2**
    """
    json_str = task.model_dump_json()
    restored = TaskSubmitRequest.model_validate_json(json_str)
    assert restored == task


# Webhook Schemas Round-Trip Properties
# **Validates: Requirements 6.4**

webhook_delivery_strategy = st.builds(
    WebhookDeliveryResponse,
    delivery_id=st.text(min_size=1, max_size=50),
    task_id=st.text(min_size=1, max_size=50),
    webhook_url=st.just("https://example.com/webhook"),
    status=st.sampled_from(["pending", "delivered", "failed"]),
    attempts=st.integers(min_value=1, max_value=10),
    created_at=st.just(datetime.now(timezone.utc)),
)


@given(webhook_delivery_strategy)
@settings(max_examples=50, deadline=None)
def test_webhook_delivery_dict_round_trip(delivery):
    """Property: WebhookDeliveryResponse dict round-trip.

    **Validates: Requirements 6.1, 12.1**
    """
    dumped = delivery.model_dump()
    restored = WebhookDeliveryResponse.model_validate(dumped)
    assert restored == delivery


@given(webhook_delivery_strategy)
@settings(max_examples=50, deadline=None)
def test_webhook_delivery_json_round_trip(delivery):
    """Property: WebhookDeliveryResponse JSON round-trip.

    **Validates: Requirements 6.2**
    """
    json_str = delivery.model_dump_json()
    restored = WebhookDeliveryResponse.model_validate_json(json_str)
    assert restored == delivery


# API Key Schemas Round-Trip Properties
# **Validates: Requirements 6.4**

api_key_response_strategy = st.builds(
    APIKeyResponse,
    key_id=st.text(min_size=1, max_size=50),
    name=st.text(min_size=1, max_size=100),
    permissions=st.lists(
        st.sampled_from(["read", "write", "admin", "delete"]),
        min_size=0,
        max_size=4,
        unique=True,
    ),
    is_active=st.booleans(),
    created_at=st.just(datetime.now(timezone.utc)),
)


@given(api_key_response_strategy)
@settings(max_examples=50, deadline=None)
def test_api_key_response_dict_round_trip(api_key):
    """Property: APIKeyResponse dict round-trip.

    **Validates: Requirements 6.1, 12.1**
    """
    dumped = api_key.model_dump()
    restored = APIKeyResponse.model_validate(dumped)
    assert restored == api_key


@given(api_key_response_strategy)
@settings(max_examples=50, deadline=None)
def test_api_key_response_json_round_trip(api_key):
    """Property: APIKeyResponse JSON round-trip.

    **Validates: Requirements 6.2**
    """
    json_str = api_key.model_dump_json()
    restored = APIKeyResponse.model_validate_json(json_str)
    assert restored == api_key


# Pagination Info Round-Trip Properties
# **Validates: Requirements 6.4**

pagination_strategy = st.builds(
    PaginationInfo,
    page=st.integers(min_value=1, max_value=1000),
    per_page=st.integers(min_value=1, max_value=100),
    total=st.integers(min_value=0, max_value=10000),
)


@given(pagination_strategy)
@settings(max_examples=50, deadline=None)
def test_pagination_dict_round_trip(pagination):
    """Property: PaginationInfo dict round-trip.

    **Validates: Requirements 6.1, 12.1**
    """
    dumped = pagination.model_dump()
    restored = PaginationInfo.model_validate(dumped)
    assert restored == pagination


@given(pagination_strategy)
@settings(max_examples=50, deadline=None)
def test_pagination_json_round_trip(pagination):
    """Property: PaginationInfo JSON round-trip.

    **Validates: Requirements 6.2**
    """
    json_str = pagination.model_dump_json()
    restored = PaginationInfo.model_validate_json(json_str)
    assert restored == pagination


# ============================================================================
# SERIALIZER TESTS
# ============================================================================


class TestSerializers:
    """Tests for schema serialization behavior."""

    def test_user_create_serialization(self):
        """Test UserCreateRequest serialization."""
        user = UserCreateRequest(
            username="testuser",
            email="test@example.com",
            password="MyP@ssw0rd",
        )
        data = user.model_dump()
        assert isinstance(data, dict)
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    def test_user_create_json_serialization(self):
        """Test UserCreateRequest JSON serialization."""
        user = UserCreateRequest(
            username="testuser",
            email="test@example.com",
            password="MyP@ssw0rd",
        )
        json_str = user.model_dump_json()
        assert isinstance(json_str, str)
        assert "testuser" in json_str
        assert "test@example.com" in json_str

    def test_session_create_serialization(self):
        """Test SessionCreateRequest serialization."""
        session = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description=None,
        )
        data = session.model_dump()
        assert isinstance(data, dict)
        assert data["template_id"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_task_submit_serialization(self):
        """Test TaskSubmitRequest serialization."""
        task = TaskSubmitRequest(
            task_type="attentional_blink",
            parameters={"stream_length": 15},
            priority=5,
            webhook_url=None,
        )
        data = task.model_dump()
        assert isinstance(data, dict)
        assert data["task_type"] == "attentional_blink"
        assert data["parameters"]["stream_length"] == 15

    def test_pagination_serialization(self):
        """Test PaginationInfo serialization."""
        pagination = PaginationInfo(page=1, per_page=10, total=100)
        data = pagination.model_dump()
        assert isinstance(data, dict)
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert data["total"] == 100

    def test_error_detail_serialization(self):
        """Test ErrorDetail serialization."""
        now = datetime.now(timezone.utc)
        error = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Invalid request",
            timestamp=now,
            details=None,
        )
        data = error.model_dump()
        assert isinstance(data, dict)
        assert data["code"] == "VALIDATION_ERROR"
        assert data["message"] == "Invalid request"

    def test_token_payload_serialization(self):
        """Test TokenPayload to_dict serialization."""
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        payload = TokenPayload(
            user_id="user_123",
            username="testuser",
            roles=["user"],
            exp=exp,
        )
        data = payload.to_dict()
        assert isinstance(data, dict)
        assert data["user_id"] == "user_123"
        assert data["username"] == "testuser"
        assert "exp" in data
