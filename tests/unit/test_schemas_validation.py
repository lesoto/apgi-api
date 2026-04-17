"""
Comprehensive Schema Validation Tests
Achieves 100% coverage for schema validators and edge cases.
"""

# mypy: disable-error-code="attr-defined"

import pytest
from datetime import datetime, timezone, timedelta

from app.models.schemas import (
    TokenPayload,
    CustomConfig,
    SessionTemplateCreateRequest,
    SessionTemplateUpdateRequest,
    SessionTemplateResponse,
    SessionTemplateListResponse,
    SessionCreateRequest,
    PaginationInfo,
)

# ============================================================================
# TokenPayload Tests
# ============================================================================


class TestTokenPayload:
    """Test TokenPayload model."""

    def test_token_payload_to_dict_full(self) -> None:
        """Test to_dict with all fields including optional ones."""
        payload = TokenPayload(
            user_id="user-123",
            username="testuser",
            roles=["admin", "user"],
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            token_type="access",
            jti="unique-id-123",
            permissions=["read", "write"],
        )

        data = payload.to_dict()

        assert data["user_id"] == "user-123"
        assert data["username"] == "testuser"
        assert data["roles"] == ["admin", "user"]
        assert data["token_type"] == "access"
        assert data["jti"] == "unique-id-123"
        assert data["permissions"] == ["read", "write"]
        assert "exp" in data
        assert isinstance(data["exp"], int)

    def test_token_payload_to_dict_minimal(self) -> None:
        """Test to_dict with minimal fields (no optional)."""
        payload = TokenPayload(
            user_id="user-123",
            username="testuser",
            roles=["user"],
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        data = payload.to_dict()

        assert data["user_id"] == "user-123"
        assert data["token_type"] == "access"  # Default
        assert "jti" not in data
        assert "permissions" not in data

    def test_token_payload_from_dict_full(self) -> None:
        """Test from_dict with all fields."""
        exp_time = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        data = {
            "user_id": "user-123",
            "username": "testuser",
            "roles": ["admin"],
            "exp": exp_time,
            "token_type": "refresh",
            "jti": "unique-id",
            "permissions": ["read"],
        }

        payload = TokenPayload.from_dict(data)

        assert payload.user_id == "user-123"
        assert payload.username == "testuser"
        assert payload.roles == ["admin"]
        assert payload.token_type == "refresh"
        assert payload.jti == "unique-id"
        assert payload.permissions == ["read"]

    def test_token_payload_from_dict_minimal(self) -> None:
        """Test from_dict with minimal fields."""
        exp_time = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        data = {
            "user_id": "user-123",
            "username": "testuser",
            "roles": ["user"],
            "exp": exp_time,
        }

        payload = TokenPayload.from_dict(data)

        assert payload.token_type == "access"  # Default
        assert payload.jti is None
        assert payload.permissions is None


# ============================================================================
# CustomConfig Tests
# ============================================================================


class TestCustomConfig:
    """Test CustomConfig validation."""

    def test_custom_config_valid_simple(self) -> None:
        """Test valid simple config."""
        config = CustomConfig(config={"param1": "value1", "param2": 123})
        data = config.model_dump()
        assert data["param1"] == "value1"
        assert data["param2"] == 123

    def test_custom_config_valid_nested(self) -> None:
        """Test valid nested config."""
        config = CustomConfig(
            config={
                "nested": {"key1": "value1", "key2": {"deep": "value"}},
                "list_field": [1, 2, 3],
            },
        )
        data = config.model_dump()
        assert data["nested"]["key1"] == "value1"
        assert data["nested"]["key2"]["deep"] == "value"

    def test_custom_config_nesting_too_deep(self) -> None:
        """Test config nesting depth limit (max 5 levels)."""
        with pytest.raises(ValueError) as exc_info:
            CustomConfig(
                config={
                    "level1": {"level2": {"level3": {"level4": {"level5": {"level6": "too deep"}}}}}
                }
            )
        assert "nesting too deep" in str(exc_info.value).lower()

    def test_custom_config_empty_key(self) -> None:
        """Test config with empty key."""
        with pytest.raises(ValueError) as exc_info:
            CustomConfig(config={"": "value"})
        assert "non-empty string" in str(exc_info.value).lower()

    def test_custom_config_whitespace_key(self) -> None:
        """Test config with whitespace-only key."""
        with pytest.raises(ValueError) as exc_info:
            CustomConfig(config={"   ": "value"})
        assert "non-empty string" in str(exc_info.value).lower()

    def test_custom_config_dangerous_key_database_url(self) -> None:
        """Test config with forbidden key 'database_url'."""
        with pytest.raises(ValueError) as exc_info:
            CustomConfig(config={"database_url": "postgres://..."})
        assert "not allowed" in str(exc_info.value).lower()

    def test_custom_config_dangerous_key_secret_key(self) -> None:
        """Test config with forbidden key 'secret_key'."""
        with pytest.raises(ValueError) as exc_info:
            CustomConfig(config={"secret_key": "super-secret"})
        assert "not allowed" in str(exc_info.value).lower()

    def test_custom_config_dangerous_key_password(self) -> None:
        """Test config with forbidden key 'password'."""
        with pytest.raises(ValueError) as exc_info:
            CustomConfig(config={"password": "secret123"})
        assert "not allowed" in str(exc_info.value).lower()

    def test_custom_config_dangerous_key_token(self) -> None:
        """Test config with forbidden key 'token'."""
        with pytest.raises(ValueError) as exc_info:
            CustomConfig(config={"token": "jwt-token"})
        assert "not allowed" in str(exc_info.value).lower()

    def test_custom_config_dangerous_key_case_insensitive(self) -> None:
        """Test config with forbidden key (case insensitive)."""
        with pytest.raises(ValueError) as exc_info:
            CustomConfig(config={"DATABASE_URL": "postgres://..."})
        assert "not allowed" in str(exc_info.value).lower()

    def test_custom_config_invalid_value_type(self) -> None:
        """Test config with invalid value type."""
        with pytest.raises(ValueError) as exc_info:
            CustomConfig(config={"param": set([1, 2, 3])})
        assert "must be a string, number, boolean, null" in str(exc_info.value).lower()

    def test_custom_config_valid_none_value(self) -> None:
        """Test config with None value."""
        config = CustomConfig(config={"param": None})
        data = config.model_dump()
        assert data["param"] is None

    def test_custom_config_valid_bool_value(self) -> None:
        """Test config with boolean value."""
        config = CustomConfig(config={"enabled": True, "disabled": False})
        data = config.model_dump()
        assert data["enabled"] is True
        assert data["disabled"] is False

    def test_custom_config_valid_float_value(self) -> None:
        """Test config with float value."""
        config = CustomConfig(config={"threshold": 0.5})
        data = config.model_dump()
        assert data["threshold"] == 0.5


# ============================================================================
# SessionTemplateCreateRequest Tests
# ============================================================================


class TestSessionTemplateCreateRequest:
    """Test SessionTemplateCreateRequest validation."""

    def test_valid_minimal_request(self) -> None:
        """Test valid request with minimal fields."""
        request = SessionTemplateCreateRequest(
            name="Test Template",
            config_path="config/test.yaml",
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
        )
        assert request.name == "Test Template"
        assert request.config_path == "config/test.yaml"

    def test_valid_full_request(self) -> None:
        """Test valid request with all fields."""
        request = SessionTemplateCreateRequest(
            name="Test Template",
            description="A test template",
            config_path="config/test.yaml",
            custom_config={"key": "value"},
            default_description="Default desc",
            tags=["tag1", "tag2"],
            is_public=True,
        )
        assert request.name == "Test Template"
        assert request.description == "A test template"

    # Name validation tests
    def test_name_empty_string(self) -> None:
        """Test empty name validation."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="",
                config_path="config/test.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert "cannot be empty" in str(exc_info.value).lower()

    def test_name_whitespace_only(self) -> None:
        """Test whitespace-only name validation."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="   ",
                config_path="config/test.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert "cannot be empty" in str(exc_info.value).lower()

    def test_name_too_long(self) -> None:
        """Test name length limit (100 chars)."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="a" * 101,
                config_path="config/test.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert "too long" in str(exc_info.value).lower()

    def test_name_exactly_max_length(self) -> None:
        """Test name at exact max length (100 chars)."""
        request = SessionTemplateCreateRequest(
            name="a" * 100,
            config_path="config/test.yaml",
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
        )
        assert len(request.name) == 100

    def test_name_strips_whitespace(self) -> None:
        """Test that name has whitespace stripped."""
        request = SessionTemplateCreateRequest(
            name="  Test Template  ",
            config_path="config/test.yaml",
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
        )
        assert request.name == "Test Template"

    # Config path validation tests
    def test_config_path_none(self) -> None:
        """Test None config_path (allowed when custom_config provided)."""
        request = SessionTemplateCreateRequest(
            name="Test",
            description=None,
            config_path=None,
            custom_config={"key": "value"},
            default_description=None,
            is_public=False,
        )
        assert request.config_path is None

    def test_config_path_empty_string(self) -> None:
        """Test empty config_path validation."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                config_path="",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert "non-empty string" in str(exc_info.value).lower()

    def test_config_path_whitespace_only(self) -> None:
        """Test whitespace-only config_path validation."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                config_path="   ",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert "non-empty string" in str(exc_info.value).lower()

    def test_config_path_directory_traversal_dotdot(self) -> None:
        """Test config_path with .. directory traversal."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                config_path="../etc/passwd.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert "directory traversal" in str(exc_info.value).lower()

    def test_config_path_invalid_extension(self) -> None:
        """Test config_path without yaml extension."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                config_path="config/test.json",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert ".yaml or .yml" in str(exc_info.value).lower()

    def test_config_path_too_long(self) -> None:
        """Test config_path length limit (255 chars)."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                config_path="a" * 256 + ".yaml",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert "too long" in str(exc_info.value).lower()

    def test_config_path_strips_whitespace(self) -> None:
        """Test that config_path has whitespace stripped."""
        request = SessionTemplateCreateRequest(
            name="Test",
            config_path="  config/test.yaml  ",
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
        )
        assert request.config_path == "config/test.yaml"

    # Custom config validation tests
    def test_custom_config_none(self) -> None:
        """Test None custom_config (allowed when config_path provided)."""
        request = SessionTemplateCreateRequest(
            name="Test",
            config_path="config/test.yaml",
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
        )
        assert request.custom_config is None

    def test_custom_config_not_dict(self) -> None:
        """Test custom_config that is not a dict."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                description=None,
                config_path=None,
                custom_config="not a dict",  # type: ignore[arg-type]
                default_description=None,
                is_public=False,
            )
        assert "input should be a valid dictionary" in str(exc_info.value).lower()

    def test_custom_config_empty_key(self) -> None:
        """Test custom_config with empty key."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                description=None,
                config_path=None,
                custom_config={"": "value"},
                default_description=None,
                is_public=False,
            )
        assert "non-empty string" in str(exc_info.value).lower()

    def test_custom_config_dangerous_key(self) -> None:
        """Test custom_config with dangerous key."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                description=None,
                config_path=None,
                custom_config={"password": "secret"},
                default_description=None,
                is_public=False,
            )
        assert "not allowed" in str(exc_info.value).lower()

    # Tags validation tests
    def test_tags_none(self) -> None:
        """Test None tags defaults to empty list."""
        request = SessionTemplateCreateRequest(
            name="Test",
            config_path="config/test.yaml",
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
            tags=None,
        )
        assert request.tags == []

    def test_tags_not_list(self) -> None:
        """Test tags that is not a list."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                config_path="config/test.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
                tags="not a list",  # type: ignore[arg-type]
            )
        assert "input should be a valid list" in str(exc_info.value).lower()

    def test_tags_non_string_element(self) -> None:
        """Test tags with non-string element."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                config_path="config/test.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
                tags=["valid", 123],  # type: ignore[list-item]
            )
        assert "input should be a valid string" in str(exc_info.value).lower()

    def test_tags_empty_string_element(self) -> None:
        """Test tags with empty string element."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                config_path="config/test.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
                tags=["valid", ""],
            )
        assert "non-whitespace characters" in str(exc_info.value).lower()

    def test_tags_whitespace_only_element(self) -> None:
        """Test tags with whitespace-only element."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                config_path="config/test.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
                tags=["valid", "   "],
            )
        assert "non-whitespace characters" in str(exc_info.value).lower()

    def test_tags_too_long_element(self) -> None:
        """Test tags with element exceeding 50 chars."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                config_path="config/test.yaml",
                description=None,
                custom_config=None,
                default_description=None,
                is_public=False,
                tags=["valid", "a" * 51],
            )
        assert "too long" in str(exc_info.value).lower()

    def test_tags_strips_whitespace(self) -> None:
        """Test that tags have whitespace stripped."""
        request = SessionTemplateCreateRequest(
            name="Test",
            config_path="config/test.yaml",
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
            tags=["  tag1  ", "  tag2  "],
        )
        assert request.tags == ["tag1", "tag2"]

    def test_tags_exactly_max_length(self) -> None:
        """Test tags at exactly max length (50 chars)."""
        request = SessionTemplateCreateRequest(
            name="Test",
            config_path="config/test.yaml",
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
            tags=["a" * 50],
        )
        assert len(request.tags[0]) == 50  # type: ignore[index]

    # Model validator tests
    def test_config_consistency_neither_provided(self) -> None:
        """Test that either config_path or custom_config must be provided."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateCreateRequest(
                name="Test",
                description=None,
                config_path=None,
                custom_config=None,
                default_description=None,
                is_public=False,
            )
        assert "either config_path or custom_config" in str(exc_info.value).lower()

    def test_config_consistency_both_provided(self) -> None:
        """Test that both config_path and custom_config can be provided."""
        request = SessionTemplateCreateRequest(
            name="Test",
            config_path="config/test.yaml",
            custom_config={"key": "value"},
            description=None,
            default_description=None,
            is_public=False,
        )
        assert request.config_path == "config/test.yaml"
        assert request.custom_config == {"key": "value"}

    def test_config_consistency_only_config_path(self) -> None:
        """Test with only config_path provided."""
        request = SessionTemplateCreateRequest(
            name="Test",
            config_path="config/test.yaml",
            description=None,
            custom_config=None,
            default_description=None,
            is_public=False,
        )
        assert request.config_path == "config/test.yaml"

    def test_config_consistency_only_custom_config(self) -> None:
        """Test with only custom_config provided."""
        request = SessionTemplateCreateRequest(
            name="Test",
            description=None,
            config_path=None,
            custom_config={"key": "value"},
            default_description=None,
            is_public=False,
        )
        assert request.custom_config == {"key": "value"}


# ============================================================================
# SessionTemplateUpdateRequest Tests
# ============================================================================


class TestSessionTemplateUpdateRequest:
    """Test SessionTemplateUpdateRequest validation."""

    def test_valid_minimal_update(self) -> None:
        """Test valid update with minimal fields."""
        request = SessionTemplateUpdateRequest(
            name="Updated Name",
            description=None,
            config_path=None,
            custom_config=None,
            default_description=None,
            tags=None,
            is_public=None,
        )
        assert request.name == "Updated Name"

    def test_valid_full_update(self) -> None:
        """Test valid update with all fields."""
        request = SessionTemplateUpdateRequest(
            name="Updated",
            description="Updated desc",
            config_path="config/updated.yaml",
            custom_config={"updated": True},
            default_description="New default",
            tags=["updated"],
            is_public=False,
        )
        assert request.name == "Updated"

    # Name validation (nullable)
    def test_name_none_allowed(self) -> None:
        """Test that None name is allowed."""
        request = SessionTemplateUpdateRequest(
            name=None,
            description=None,
            config_path=None,
            custom_config=None,
            default_description=None,
            tags=None,
            is_public=None,
        )
        assert request.name is None

    def test_name_empty_string_not_allowed(self) -> None:
        """Test empty name validation in update."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateUpdateRequest(
                name="",
                description=None,
                config_path=None,
                custom_config=None,
                default_description=None,
                tags=None,
                is_public=None,
            )
        assert "cannot be empty" in str(exc_info.value).lower()

    def test_name_whitespace_only_not_allowed(self) -> None:
        """Test whitespace-only name validation in update."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateUpdateRequest(
                name="   ",
                description=None,
                config_path=None,
                custom_config=None,
                default_description=None,
                tags=None,
                is_public=None,
            )
        assert "cannot be empty" in str(exc_info.value).lower()

    def test_name_too_long_in_update(self) -> None:
        """Test name length limit in update (100 chars)."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateUpdateRequest(
                name="a" * 101,
                description=None,
                config_path=None,
                custom_config=None,
                default_description=None,
                tags=None,
                is_public=None,
            )
        assert "too long" in str(exc_info.value).lower()

    def test_name_strips_whitespace_in_update(self) -> None:
        """Test that name has whitespace stripped in update."""
        request = SessionTemplateUpdateRequest(
            name="  Updated  ",
            description=None,
            config_path=None,
            custom_config=None,
            default_description=None,
            tags=None,
            is_public=None,
        )
        assert request.name == "Updated"

    # Config path validation (nullable in update)
    def test_config_path_none_allowed(self) -> None:
        """Test that None config_path is allowed in update."""
        request = SessionTemplateUpdateRequest(
            name=None,
            description=None,
            config_path=None,
            custom_config=None,
            default_description=None,
            tags=None,
            is_public=None,
        )
        assert request.config_path is None

    def test_config_path_empty_string_not_allowed(self) -> None:
        """Test empty config_path validation in update."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateUpdateRequest(
                name=None,
                description=None,
                config_path="",
                custom_config=None,
                default_description=None,
                tags=None,
                is_public=None,
            )
        assert "non-empty string" in str(exc_info.value).lower()

    def test_config_path_directory_traversal_not_allowed(self) -> None:
        """Test directory traversal in update config_path."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateUpdateRequest(
                name=None,
                description=None,
                config_path="../../etc/passwd.yaml",
                custom_config=None,
                default_description=None,
                tags=None,
                is_public=None,
            )
        assert "directory traversal" in str(exc_info.value).lower()

    def test_config_path_absolute_not_allowed(self) -> None:
        """Test absolute path in update config_path."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateUpdateRequest(
                name=None,
                description=None,
                config_path="/etc/passwd.yaml",
                custom_config=None,
                default_description=None,
                tags=None,
                is_public=None,
            )
        assert "absolute paths not allowed" in str(exc_info.value).lower()

    def test_config_path_percent_encoded_traversal(self) -> None:
        """Test percent-encoded directory traversal."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateUpdateRequest(
                name=None,
                description=None,
                config_path="%2e%2e/config.yaml",
                custom_config=None,
                default_description=None,
                tags=None,
                is_public=None,
            )
        assert "directory traversal" in str(exc_info.value).lower()

    def test_config_path_url_encoded_traversal(self) -> None:
        """Test URL-encoded directory traversal."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateUpdateRequest(
                name=None,
                description=None,
                config_path="..%2fconfig.yaml",
                custom_config=None,
                default_description=None,
                tags=None,
                is_public=None,
            )
        assert "directory traversal" in str(exc_info.value).lower()

    # Custom config validation (nullable in update)
    def test_custom_config_none_allowed(self) -> None:
        """Test that None custom_config is allowed in update."""
        request = SessionTemplateUpdateRequest(
            name=None,
            description=None,
            config_path=None,
            custom_config=None,
            default_description=None,
            tags=None,
            is_public=None,
        )
        assert request.custom_config is None

    def test_custom_config_not_dict(self) -> None:
        """Test custom_config that is not a dict in update."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateUpdateRequest(
                name=None,
                description=None,
                config_path=None,
                custom_config="string",  # type: ignore[arg-type]
                default_description=None,
                tags=None,
                is_public=None,
            )
        assert "input should be a valid dictionary" in str(exc_info.value).lower()

    # Tags validation (nullable in update)
    def test_tags_none_allowed(self) -> None:
        """Test that None tags is allowed in update."""
        request = SessionTemplateUpdateRequest(
            name=None,
            description=None,
            config_path=None,
            custom_config=None,
            default_description=None,
            tags=None,
            is_public=None,
        )
        assert request.tags is None

    def test_tags_not_list(self) -> None:
        """Test tags that is not a list in update."""
        with pytest.raises(ValueError) as exc_info:
            SessionTemplateUpdateRequest(
                name=None,
                description=None,
                config_path=None,
                custom_config=None,
                default_description=None,
                tags="tag1,tag2",  # type: ignore[arg-type]
                is_public=None,
            )
        assert "input should be a valid list" in str(exc_info.value).lower()


# ============================================================================
# SessionCreateRequest Tests
# ============================================================================


class TestSessionCreateRequest:
    """Test SessionCreateRequest validation."""

    def test_valid_minimal_request(self) -> None:
        """Test valid minimal request."""
        request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path=None,
            custom_config=None,
            description=None,
        )
        assert request.template_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_valid_full_request(self) -> None:
        """Test valid request with all fields."""
        request = SessionCreateRequest(
            template_id="550e8400-e29b-41d4-a716-446655440000",
            config_path="config/test.yaml",
            custom_config={"key": "value"},
            description="Test session",
        )
        assert request.description == "Test session"

    def test_all_optional_none(self) -> None:
        """Test request with all fields None - should require at least one config source."""
        with pytest.raises(ValueError) as exc_info:
            SessionCreateRequest(
                template_id=None,
                config_path=None,
                custom_config=None,
                description=None,
            )
        assert "must be provided" in str(exc_info.value).lower()

    # Template ID validation
    def test_template_id_none_allowed(self) -> None:
        """Test None template_id with config_path provided."""
        request = SessionCreateRequest(
            template_id=None,
            config_path="config/test.yaml",
            custom_config=None,
            description=None,
        )
        assert request.template_id is None
        assert request.config_path == "config/test.yaml"

    def test_template_id_empty_string(self) -> None:
        """Test empty template_id."""
        with pytest.raises(ValueError) as exc_info:
            SessionCreateRequest(
                template_id="",
                config_path="config/test.yaml",
                custom_config=None,
                description=None,
            )
        assert "non-empty string" in str(exc_info.value).lower()

    def test_template_id_whitespace_only(self) -> None:
        """Test whitespace-only template_id."""
        with pytest.raises(ValueError) as exc_info:
            SessionCreateRequest(
                template_id="   ",
                config_path=None,
                custom_config=None,
                description=None,
            )
        assert "non-empty string" in str(exc_info.value).lower()

    def test_template_id_invalid_format(self) -> None:
        """Test invalid UUID format."""
        with pytest.raises(ValueError) as exc_info:
            SessionCreateRequest(
                template_id="not-a-uuid",
                config_path=None,
                custom_config=None,
                description=None,
            )
        assert "invalid template id format" in str(exc_info.value).lower()

    def test_template_id_invalid_uuid_pattern(self) -> None:
        """Test UUID-like but invalid pattern."""
        with pytest.raises(ValueError) as exc_info:
            SessionCreateRequest(
                template_id="550e8400-e29b-41d4-a716-44665544000",  # Too short
                config_path=None,
                custom_config=None,
                description=None,
            )
        assert "invalid template id format" in str(exc_info.value).lower()

    def test_template_id_valid_uuid_uppercase(self) -> None:
        """Test valid UUID in uppercase."""
        request = SessionCreateRequest(
            template_id="550E8400-E29B-41D4-A716-446655440000",
            config_path="config/test.yaml",
            custom_config=None,
            description=None,
        )
        assert request.template_id == "550E8400-E29B-41D4-A716-446655440000"

    def test_template_id_strips_whitespace(self) -> None:
        """Test that template_id has whitespace stripped."""
        request = SessionCreateRequest(
            template_id="  550e8400-e29b-41d4-a716-446655440000  ",
            config_path="config/test.yaml",
            custom_config=None,
            description=None,
        )
        assert request.template_id == "550e8400-e29b-41d4-a716-446655440000"

    # Config path validation
    def test_config_path_absolute_not_allowed(self) -> None:
        """Test absolute path rejection."""
        with pytest.raises(ValueError) as exc_info:
            SessionCreateRequest(
                template_id=None,
                config_path="/absolute/path.yaml",
                custom_config=None,
                description=None,
            )
        assert "absolute paths not allowed" in str(exc_info.value).lower()

    # Custom config validation
    def test_custom_config_dangerous_keys(self) -> None:
        """Test custom_config with dangerous keys."""
        with pytest.raises(ValueError) as exc_info:
            SessionCreateRequest(
                template_id=None,
                config_path=None,
                custom_config={"secret_key": "value"},
                description=None,
            )
        assert "not allowed" in str(exc_info.value).lower()


# ============================================================================
# Response Models Tests
# ============================================================================


class TestSessionTemplateResponse:
    """Test SessionTemplateResponse model."""

    def test_response_creation(self) -> None:
        """Test creating a response."""
        now = datetime.now(timezone.utc)
        response = SessionTemplateResponse(
            template_id="tmpl-123",
            user_id="user-123",
            name="Test Template",
            description="Description",
            config_path="config/test.yaml",
            custom_config={"key": "value"},
            default_description="Default",
            tags=["tag1"],
            is_public=False,
            created_at=now,
            updated_at=now,
        )
        assert response.template_id == "tmpl-123"
        assert response.user_id == "user-123"

    def test_response_optional_defaults(self) -> None:
        """Test response with optional fields as None."""
        now = datetime.now(timezone.utc)
        response = SessionTemplateResponse(
            template_id="tmpl-123",
            user_id="user-123",
            name="Test",
            description=None,
            config_path=None,
            custom_config=None,
            default_description=None,
            is_public=True,
            created_at=now,
            updated_at=now,
        )
        assert response.description is None
        assert response.config_path is None
        assert response.custom_config is None
        assert response.default_description is None


class TestSessionTemplateListResponse:
    """Test SessionTemplateListResponse model."""

    def test_list_response_creation(self) -> None:
        """Test creating a list response."""
        now = datetime.now(timezone.utc)
        templates = [
            SessionTemplateResponse(
                template_id="tmpl-1",
                user_id="user-1",
                name="Template 1",
                description=None,
                config_path=None,
                custom_config=None,
                default_description=None,
                is_public=False,
                created_at=now,
                updated_at=now,
            ),
        ]
        pagination = PaginationInfo(page=1, per_page=10, total=1)

        response = SessionTemplateListResponse(
            templates=templates,
            pagination=pagination,
        )
        assert len(response.templates) == 1
        assert response.pagination.page == 1


class TestPaginationInfo:
    """Test PaginationInfo model."""

    def test_pagination_creation(self) -> None:
        """Test creating pagination info."""
        pagination = PaginationInfo(page=2, per_page=20, total=100)
        assert pagination.page == 2
        assert pagination.per_page == 20
        assert pagination.total == 100
