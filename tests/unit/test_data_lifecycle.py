"""
Unit tests for DataLifecycleManager covering retention policies, PII handling, and data deletion.
Requirements: 4.7, 5.1
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.services.data_lifecycle import (
    DATA_CLASSIFICATIONS,
    PII_FIELDS,
    RETENTION_PERIODS,
    RETENTION_POLICIES,
    DataClassification,
    DataLifecycleManager,
    RetentionCategory,
    data_lifecycle_manager,
)


class TestRetentionCategory:
    """Test RetentionCategory enum."""

    def test_retention_category_values(self) -> None:
        """RetentionCategory has correct values."""
        assert RetentionCategory.SHORT_TERM.value == "short_term"
        assert RetentionCategory.STANDARD.value == "standard"
        assert RetentionCategory.LONG_TERM.value == "long_term"
        assert RetentionCategory.PERMANENT.value == "permanent"


class TestDataClassification:
    """TestDataClassification enum."""

    def test_data_classification_values(self) -> None:
        """DataClassification has correct values."""
        assert DataClassification.PUBLIC.value == "public"
        assert DataClassification.INTERNAL.value == "internal"
        assert DataClassification.CONFIDENTIAL.value == "confidential"
        assert DataClassification.RESTRICTED.value == "restricted"


class TestRetentionPeriods:
    """Test retention period definitions."""

    def test_retention_periods_defined(self) -> None:
        """All retention categories have periods defined."""
        assert RetentionCategory.SHORT_TERM in RETENTION_PERIODS
        assert RetentionCategory.STANDARD in RETENTION_PERIODS
        assert RetentionCategory.LONG_TERM in RETENTION_PERIODS
        assert RetentionCategory.PERMANENT in RETENTION_PERIODS

    def test_retention_period_values(self) -> None:
        """Retention periods have correct values."""
        assert RETENTION_PERIODS[RetentionCategory.SHORT_TERM] == 30
        assert RETENTION_PERIODS[RetentionCategory.STANDARD] == 365
        assert RETENTION_PERIODS[RetentionCategory.LONG_TERM] == 2555
        assert RETENTION_PERIODS[RetentionCategory.PERMANENT] is None


class TestDataClassifications:
    """Test data classification definitions."""

    def test_data_classifications_defined(self) -> None:
        """All data types have classifications."""
        assert "users" in DATA_CLASSIFICATIONS
        assert "sessions" in DATA_CLASSIFICATIONS
        assert "tasks" in DATA_CLASSIFICATIONS

    def test_users_classification_restricted(self) -> None:
        """Users data is restricted."""
        assert DATA_CLASSIFICATIONS["users"] == DataClassification.RESTRICTED

    def test_sessions_classification_confidential(self) -> None:
        """Sessions data is confidential."""
        assert DATA_CLASSIFICATIONS["sessions"] == DataClassification.CONFIDENTIAL


class TestRetentionPolicies:
    """Test retention policy definitions."""

    def test_retention_policies_defined(self) -> None:
        """All data types have retention policies."""
        assert "users" in RETENTION_POLICIES
        assert "sessions" in RETENTION_POLICIES
        assert "tasks" in RETENTION_POLICIES

    def test_users_retention_long_term(self) -> None:
        """Users have long-term retention."""
        assert RETENTION_POLICIES["users"] == RetentionCategory.LONG_TERM

    def test_session_data_retention_short_term(self) -> None:
        """Session data has short-term retention."""
        assert RETENTION_POLICIES["session_data"] == RetentionCategory.SHORT_TERM


class TestPIIFields:
    """Test PII field definitions."""

    def test_pii_fields_defined(self) -> None:
        """All data types have PII field definitions."""
        assert "users" in PII_FIELDS
        assert "sessions" in PII_FIELDS
        assert "audit_logs" in PII_FIELDS

    def test_users_pii_fields(self) -> None:
        """Users have expected PII fields."""
        assert "username" in PII_FIELDS["users"]
        assert "email" in PII_FIELDS["users"]
        assert "password_hash" in PII_FIELDS["users"]


class TestDataLifecycleManagerInit:
    """Test DataLifecycleManager initialization."""

    def test_manager_initialization(self) -> None:
        """Manager initializes with default policies."""
        manager = DataLifecycleManager()
        assert "users" in manager._retention_policies
        assert "users" in manager._pii_fields


class TestGetRetentionPolicy:
    """Test retention policy retrieval."""

    def test_get_retention_policy_known_type(self) -> None:
        """Get policy for known data type."""
        manager = DataLifecycleManager()
        policy = manager.get_retention_policy("users")
        assert policy == RetentionCategory.LONG_TERM

    def test_get_retention_policy_unknown_type(self) -> None:
        """Return standard policy for unknown type."""
        manager = DataLifecycleManager()
        policy = manager.get_retention_policy("unknown")
        assert policy == RetentionCategory.STANDARD


class TestGetRetentionDays:
    """Test retention period retrieval."""

    def test_get_retention_days_short_term(self) -> None:
        """Get days for short-term retention."""
        manager = DataLifecycleManager()
        days = manager.get_retention_days("session_data")
        assert days == 30

    def test_get_retention_days_long_term(self) -> None:
        """Get days for long-term retention."""
        manager = DataLifecycleManager()
        days = manager.get_retention_days("users")
        assert days == 2555


class TestDataClassificationRetrieval:
    """Test data classification retrieval."""

    def test_get_data_classification_known_type(self) -> None:
        """Get classification for known data type."""
        manager = DataLifecycleManager()
        classification = manager.get_data_classification("users")
        assert classification == DataClassification.RESTRICTED

    def test_get_data_classification_unknown_type(self) -> None:
        """Return internal for unknown type."""
        manager = DataLifecycleManager()
        classification = manager.get_data_classification("unknown")
        assert classification == DataClassification.INTERNAL


class TestGetPIIFields:
    """Test PII field retrieval."""

    def test_get_pii_fields_known_type(self) -> None:
        """Get PII fields for known data type."""
        manager = DataLifecycleManager()
        fields = manager.get_pii_fields("users")
        assert "username" in fields
        assert "email" in fields

    def test_get_pii_fields_unknown_type(self) -> None:
        """Return empty set for unknown type."""
        manager = DataLifecycleManager()
        fields = manager.get_pii_fields("unknown")
        assert len(fields) == 0


class TestIsPIIField:
    """Test PII field checking."""

    def test_is_pii_field_true(self) -> None:
        """Identify PII field correctly."""
        manager = DataLifecycleManager()
        assert manager.is_pii_field("users", "username") is True

    def test_is_pii_field_false(self) -> None:
        """Non-PII field returns False."""
        manager = DataLifecycleManager()
        assert manager.is_pii_field("users", "created_at") is False


class TestCalculateExpiryDate:
    """Test expiry date calculation."""

    def test_calculate_expiry_date_short_term(self) -> None:
        """Calculate expiry for short-term retention."""
        manager = DataLifecycleManager()
        created = datetime(2024, 1, 1, tzinfo=timezone.utc)
        expiry = manager.calculate_expiry_date("session_data", created)
        expected = created + timedelta(days=30)
        assert expiry == expected

    def test_calculate_expiry_date_long_term(self) -> None:
        """Calculate expiry for long-term retention."""
        manager = DataLifecycleManager()
        created = datetime(2024, 1, 1, tzinfo=timezone.utc)
        expiry = manager.calculate_expiry_date("users", created)
        expected = created + timedelta(days=2555)
        assert expiry == expected

    def test_calculate_expiry_date_default_now(self) -> None:
        """Use current time when created_at not provided."""
        manager = DataLifecycleManager()
        expiry = manager.calculate_expiry_date("session_data")
        assert expiry is not None
        assert expiry > datetime.now(timezone.utc)


class TestFindExpiredData:
    """Test finding expired data."""

    @patch("app.services.data_lifecycle.get_db_context")
    def test_find_expired_data_permanent_retention(self, mock_db_context: MagicMock) -> None:
        """Return empty list for permanent retention."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        expired = manager.find_expired_data("users")
        assert expired == []

    @patch("app.services.data_lifecycle.get_db_context")
    def test_find_expired_data_unknown_type(self, mock_db_context: MagicMock) -> None:
        """Return empty list for unknown type."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        expired = manager.find_expired_data("unknown")
        assert expired == []


class TestDeleteExpiredData:
    """Test deleting expired data."""

    @patch("app.services.data_lifecycle.get_db_context")
    def test_delete_expired_data_dry_run(self, mock_db_context: MagicMock) -> None:
        """Dry run only counts records."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        result = manager.delete_expired_data("session_data", dry_run=True)
        assert result["dry_run"] is True
        assert "would_delete" in result

    @patch("app.services.data_lifecycle.get_db_context")
    def test_delete_expired_data_actual_delete(self, mock_db_context: MagicMock) -> None:
        """Actual delete performs deletion."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        result = manager.delete_expired_data("session_data", dry_run=False)
        assert result["dry_run"] is False
        assert "deleted" in result


class TestDeleteUserData:
    """Test user data deletion (GDPR/CCPA)."""

    @patch("app.services.data_lifecycle.get_db_context")
    def test_delete_user_data_structure(self, mock_db_context: MagicMock) -> None:
        """Delete user data returns proper structure."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        result = manager.delete_user_data("user123", "test")
        assert "user_id" in result
        assert "reason" in result
        assert "deleted_counts" in result

    @patch("app.services.data_lifecycle.get_db_context")
    def test_delete_user_data_empty_session_ids(self, mock_db_context: MagicMock) -> None:
        """Handle empty session_ids gracefully."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        result = manager.delete_user_data("user123", "test")
        assert "user_id" in result
        assert "deleted_counts" in result

    @patch("app.services.data_lifecycle.get_db_context")
    def test_delete_user_data_user_not_found(self, mock_db_context: MagicMock) -> None:
        """Handle user not found gracefully."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        result = manager.delete_user_data("nonexistent", "test")
        assert "user_id" in result
        assert "deleted_counts" in result

    @patch("app.services.data_lifecycle.get_db_context")
    def test_delete_user_data_exception_handling(self, mock_db_context: MagicMock) -> None:
        """Handle database exceptions gracefully."""
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("Database error")
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        result = manager.delete_user_data("user123", "test")
        assert "user_id" in result
        assert "deleted_counts" in result
        # Error is logged but not added to return dict


class TestAnonymizePII:
    """Test PII anonymization."""

    def test_anonymize_pii_known_type(self) -> None:
        """Anonymize PII fields in data."""
        manager = DataLifecycleManager()
        data = {"username": "john", "email": "john@example.com", "other": "value"}
        result = manager.anonymize_pii("users", data)
        assert result["username"] == "[REDACTED]"
        assert result["email"] == "[REDACTED]"
        assert result["other"] == "value"

    def test_anonymize_pii_unknown_type(self) -> None:
        """Return original data for unknown type."""
        manager = DataLifecycleManager()
        data = {"field": "value"}
        result = manager.anonymize_pii("unknown", data)
        assert result == data


class TestGetDataRetentionReport:
    """Test data retention report generation."""

    @patch("app.services.data_lifecycle.get_db_context")
    def test_get_data_retention_report_structure(self, mock_db_context: MagicMock) -> None:
        """Report has proper structure."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.count.return_value = 0

        manager = DataLifecycleManager()
        report = manager.get_data_retention_report()
        assert "generated_at" in report
        assert "data_types" in report

    @patch("app.services.data_lifecycle.get_db_context")
    def test_get_data_retention_report_exception_handling(self, mock_db_context: MagicMock) -> None:
        """Handle database exceptions gracefully."""
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("Database error")
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        report = manager.get_data_retention_report()
        # Error is added to each data_type entry, not top-level report
        assert any("error" in report["data_types"].get(dt, {}) for dt in report["data_types"])


class TestEnforceAllRetentionPolicies:
    """Test enforcing all retention policies."""

    @patch("app.services.data_lifecycle.get_db_context")
    def test_enforce_all_retention_policies_dry_run(self, mock_db_context: MagicMock) -> None:
        """Dry run enforcement."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        results = manager.enforce_all_retention_policies(dry_run=True)
        assert len(results) > 0
        assert all(r["dry_run"] is True for r in results)

    @patch("app.services.data_lifecycle.get_db_context")
    def test_enforce_all_retention_policies_actual(self, mock_db_context: MagicMock) -> None:
        """Actual enforcement."""
        mock_db = MagicMock()
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        results = manager.enforce_all_retention_policies(dry_run=False)
        assert len(results) > 0
        assert all(r["dry_run"] is False for r in results)

    @patch("app.services.data_lifecycle.get_db_context")
    def test_enforce_all_retention_policies_exception_handling(
        self, mock_db_context: MagicMock
    ) -> None:
        """Handle exceptions during policy enforcement gracefully."""
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("Database error")
        mock_db_context.return_value.__enter__.return_value = mock_db
        manager = DataLifecycleManager()
        results = manager.enforce_all_retention_policies(dry_run=True)
        assert len(results) > 0
        # Results should still be returned even if some fail
        assert any("error" in r for r in results)


class TestGlobalInstance:
    """Test global data_lifecycle_manager instance."""

    def test_global_instance_exists(self) -> None:
        """Global manager instance is created."""
        assert data_lifecycle_manager is not None
        assert isinstance(data_lifecycle_manager, DataLifecycleManager)
