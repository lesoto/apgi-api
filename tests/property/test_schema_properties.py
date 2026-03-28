"""
Property-based tests for Pydantic schema models.

Feature: test-coverage-100
Tests universal properties of schema serialization and deserialization.
"""

from hypothesis import given, strategies as st, settings
import pytest
import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))

from app.models.schemas import (
    # User schemas
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
    # Session schemas
    SessionCreateRequest,
    SessionResponse,
    SessionTemplateCreateRequest,
    SessionTemplateResponse,
    # Task schemas
    TaskSubmitRequest,
    TaskStatusResponse,
    TaskDependencyCreateRequest,
    # Webhook schemas
    WebhookDeliveryResponse,
    WebhookRetryResponse,
)


# ============================================================================
# Hypothesis Strategies for Schema Models
# ============================================================================


def user_create_request_strategy():
    """Generate valid UserCreateRequest instances."""
    # Username: 3-50 chars, alphanumeric with underscores or dashes
    username_strategy = st.text(
        min_size=3,
        max_size=50,
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    )

    # Password: must have uppercase, lowercase, digit, special char, no weak patterns, no sequential
    def is_valid_password(p):
        # Check basic requirements
        if not (
            any(c.isupper() for c in p)
            and any(c.islower() for c in p)
            and any(c.isdigit() for c in p)
            and any(c in "!@#$%^&*()" for c in p)
        ):
            return False

        # Check weak passwords
        weak_passwords = [
            "password",
            "12345678",
            "qwerty",
            "abc123",
            "password123",
            "admin",
            "root",
            "user",
            "guest",
            "test",
            "123456789",
            "password1",
            "admin123",
            "root123",
            "user123",
        ]
        if p.lower() in weak_passwords:
            return False

        # Check for repeated characters (more than 3 in a row)
        if any(p[i] == p[i + 1] == p[i + 2] == p[i + 3] for i in range(len(p) - 3)):
            return False

        # Check for sequential characters
        sequential_patterns = [
            "012",
            "123",
            "234",
            "345",
            "456",
            "567",
            "678",
            "789",
            "abc",
            "bcd",
            "cde",
            "def",
            "efg",
            "fgh",
            "ghi",
            "hij",
            "ijk",
            "jkl",
            "klm",
            "mno",
            "nop",
            "opq",
            "pqr",
            "qrs",
            "rst",
            "stu",
            "tuv",
            "uvw",
            "vwx",
            "wxy",
            "xyz",
        ]
        p_lower = p.lower()
        if any(pattern in p_lower for pattern in sequential_patterns):
            return False

        return True

    password_strategy = st.text(
        min_size=8,
        max_size=128,
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()",
    ).filter(is_valid_password)

    return st.builds(
        UserCreateRequest,
        username=username_strategy,
        email=st.emails().filter(
            lambda e: (
                all(
                    c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._%+-@"
                    for c in e
                )
                and "@" in e
                and "." in e.split("@")[1]
                and len(e.split(".")[-1]) >= 2
                and all(c.isalpha() for c in e.split(".")[-1])
            )
        ),
        password=password_strategy,
    )


def user_response_strategy():
    """Generate valid UserResponse instances."""
    return st.builds(
        UserResponse,
        id=st.uuids().map(str),
        username=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd", "Pc"),
                blacklist_characters="\x00",
            ),
        ),
        email=st.emails(),
        created_at=st.datetimes(timezones=st.none()),
        updated_at=st.datetimes(timezones=st.none()),
    )


def user_update_request_strategy():
    """Generate valid UserUpdateRequest instances."""
    return st.builds(
        UserUpdateRequest,
        username=st.one_of(
            st.none(),
            st.text(
                min_size=1,
                max_size=50,
                alphabet=st.characters(
                    whitelist_categories=("Lu", "Ll", "Nd", "Pc"),
                    blacklist_characters="\x00",
                ),
            ),
        ),
        email=st.one_of(st.none(), st.emails()),
    )


def session_create_request_strategy():
    """Generate valid SessionCreateRequest instances."""
    # config_path must end with .yaml or .yml
    config_path_strategy = (
        st.text(
            min_size=5,
            max_size=200,
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-/",
        )
        .filter(lambda p: ".." not in p and not p.startswith("/"))
        .map(lambda p: p + ".yaml" if not p.endswith((".yaml", ".yml")) else p)
    )

    # Use a composite strategy that ensures at least one field is provided
    @st.composite
    def session_create_request_composite(draw):
        choice = draw(st.integers(min_value=0, max_value=1))
        template_id = draw(st.uuids().map(str))
        config_path = draw(config_path_strategy)
        description = draw(st.one_of(st.none(), st.text(max_size=500)))

        if choice == 0:
            # template_id only
            return SessionCreateRequest(
                template_id=template_id,
                config_path=None,
                custom_config=None,
                description=description,
            )
        else:
            # config_path only
            return SessionCreateRequest(
                template_id=None,
                config_path=config_path,
                custom_config=None,
                description=description,
            )

    return session_create_request_composite()


def session_response_strategy():
    """Generate valid SessionResponse instances."""
    return st.builds(
        SessionResponse,
        session_id=st.uuids().map(str),
        status=st.sampled_from(["created", "running", "paused", "stopped"]),
        created_at=st.datetimes(timezones=st.none()),
        updated_at=st.datetimes(timezones=st.none()),
        config=st.just({}),
        description=st.one_of(st.none(), st.text(max_size=500)),
    )


def session_template_create_request_strategy():
    """Generate valid SessionTemplateCreateRequest instances."""
    # config_path must end with .yaml or .yml
    config_path_strategy = (
        st.text(
            min_size=5,
            max_size=200,
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-/",
        )
        .filter(lambda p: ".." not in p and not p.startswith("/"))
        .map(lambda p: p + ".yaml" if not p.endswith((".yaml", ".yml")) else p)
    )

    # Use a composite strategy that ensures at least one field is provided
    @st.composite
    def session_template_create_request_composite(draw):
        choice = draw(st.integers(min_value=0, max_value=0))  # Only config_path for now
        name = draw(
            st.text(
                min_size=1,
                max_size=100,
                alphabet=st.characters(
                    whitelist_categories=("Lu", "Ll", "Nd", "Pc", "Zs"),
                    blacklist_characters="\x00",
                ),
            )
        )
        config_path = draw(config_path_strategy)
        tags = draw(
            st.lists(
                st.text(
                    min_size=1,
                    max_size=50,
                    alphabet=st.characters(
                        whitelist_categories=("Lu", "Ll", "Nd", "Pc"),
                        blacklist_characters="\x00",
                    ),
                ),
                max_size=10,
            )
        )

        # Always use config_path to satisfy the validator
        return SessionTemplateCreateRequest(
            name=name,
            config_path=config_path,
            custom_config=None,
            description=None,
            default_description=None,
            tags=tags,
            is_public=False,
        )

    return session_template_create_request_composite()


def session_template_response_strategy():
    """Generate valid SessionTemplateResponse instances."""
    return st.builds(
        SessionTemplateResponse,
        id=st.uuids().map(str),
        name=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd", "Pc", "Zs"),
                blacklist_characters="\x00",
            ),
        ),
        config_path=st.text(
            min_size=1,
            max_size=255,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd", "Pc", "Po"),
                blacklist_characters="\x00",
            ),
        ),
        tags=st.lists(
            st.text(
                min_size=1,
                max_size=50,
                alphabet=st.characters(
                    whitelist_categories=("Lu", "Ll", "Nd", "Pc"),
                    blacklist_characters="\x00",
                ),
            ),
            max_size=10,
        ),
        created_at=st.datetimes(timezones=st.none()),
        updated_at=st.datetimes(timezones=st.none()),
    )


def task_submit_request_strategy():
    """Generate valid TaskSubmitRequest instances."""
    return st.builds(
        TaskSubmitRequest,
        task_type=st.sampled_from(["analysis", "export", "import"]),
        parameters=st.just({}),
        webhook_url=st.one_of(st.none(), st.just("https://example.com/webhook")),
    )


def task_status_response_strategy():
    """Generate valid TaskStatusResponse instances."""
    return st.builds(
        TaskStatusResponse,
        task_id=st.uuids().map(str),
        status=st.sampled_from(["pending", "running", "completed", "failed"]),
        progress=st.integers(min_value=0, max_value=100),
        created_at=st.datetimes(timezones=st.none()),
        updated_at=st.datetimes(timezones=st.none()),
    )


def task_dependency_create_request_strategy():
    """Generate valid TaskDependencyCreateRequest instances."""
    return st.builds(
        TaskDependencyCreateRequest,
        prerequisite_task_id=st.uuids().map(str),
        dependency_type=st.sampled_from(["completion", "success", "failure"]),
    )


def webhook_delivery_response_strategy():
    """Generate valid WebhookDeliveryResponse instances."""
    return st.builds(
        WebhookDeliveryResponse,
        id=st.uuids().map(str),
        webhook_id=st.uuids().map(str),
        status=st.sampled_from(["pending", "delivered", "failed"]),
        response_status=st.one_of(st.none(), st.integers(min_value=100, max_value=599)),
        created_at=st.datetimes(timezones=st.none()),
        updated_at=st.datetimes(timezones=st.none()),
    )


def webhook_retry_response_strategy():
    """Generate valid WebhookRetryResponse instances."""
    return st.builds(
        WebhookRetryResponse,
        id=st.uuids().map(str),
        webhook_id=st.uuids().map(str),
        status=st.sampled_from(["pending", "delivered", "failed"]),
        retry_count=st.integers(min_value=0, max_value=10),
        created_at=st.datetimes(timezones=st.none()),
        updated_at=st.datetimes(timezones=st.none()),
    )


# ============================================================================
# Property 1: Schema dict round-trip
# ============================================================================
# Feature: test-coverage-100, Property 1


@pytest.mark.property
@settings(max_examples=50)
@given(user_create_request_strategy())
def test_property_1_user_create_request_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid UserCreateRequest instance, calling
    `UserCreateRequest.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = UserCreateRequest.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for UserCreateRequest: " f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(user_response_strategy())
def test_property_1_user_response_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid UserResponse instance, calling
    `UserResponse.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = UserResponse.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for UserResponse: " f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(user_update_request_strategy())
def test_property_1_user_update_request_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid UserUpdateRequest instance, calling
    `UserUpdateRequest.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = UserUpdateRequest.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for UserUpdateRequest: " f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(session_create_request_strategy())
def test_property_1_session_create_request_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid SessionCreateRequest instance, calling
    `SessionCreateRequest.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = SessionCreateRequest.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for SessionCreateRequest: " f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(session_response_strategy())
def test_property_1_session_response_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid SessionResponse instance, calling
    `SessionResponse.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = SessionResponse.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for SessionResponse: " f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(session_template_create_request_strategy())
def test_property_1_session_template_create_request_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid SessionTemplateCreateRequest instance, calling
    `SessionTemplateCreateRequest.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = SessionTemplateCreateRequest.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for SessionTemplateCreateRequest: "
        f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(session_template_response_strategy())
def test_property_1_session_template_response_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid SessionTemplateResponse instance, calling
    `SessionTemplateResponse.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = SessionTemplateResponse.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for SessionTemplateResponse: "
        f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(task_submit_request_strategy())
def test_property_1_task_submit_request_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid TaskSubmitRequest instance, calling
    `TaskSubmitRequest.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = TaskSubmitRequest.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for TaskSubmitRequest: " f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(task_status_response_strategy())
def test_property_1_task_status_response_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid TaskStatusResponse instance, calling
    `TaskStatusResponse.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = TaskStatusResponse.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for TaskStatusResponse: " f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(task_dependency_create_request_strategy())
def test_property_1_task_dependency_create_request_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid TaskDependencyCreateRequest instance, calling
    `TaskDependencyCreateRequest.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = TaskDependencyCreateRequest.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for TaskDependencyCreateRequest: "
        f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(webhook_delivery_response_strategy())
def test_property_1_webhook_delivery_response_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid WebhookDeliveryResponse instance, calling
    `WebhookDeliveryResponse.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = WebhookDeliveryResponse.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for WebhookDeliveryResponse: "
        f"original={instance}, restored={restored}"
    )


@pytest.mark.property
@settings(max_examples=50)
@given(webhook_retry_response_strategy())
def test_property_1_webhook_retry_response_dict_round_trip(instance):
    """
    **Validates: Requirements 6.1, 12.1**

    Feature: test-coverage-100, Property 1: Schema dict round-trip

    For any valid WebhookRetryResponse instance, calling
    `WebhookRetryResponse.model_validate(instance.model_dump())` produces an object
    equal to the original instance.
    """
    dumped = instance.model_dump()
    restored = WebhookRetryResponse.model_validate(dumped)
    assert restored == instance, (
        f"Round-trip failed for WebhookRetryResponse: " f"original={instance}, restored={restored}"
    )
