"""
Data Lifecycle Management Service

Manages data retention, deletion workflows, and PII handling requirements.
Implements GDPR/CCPA compliant data lifecycle controls.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from enum import Enum as PythonEnum

from sqlalchemy import and_, or_

from app.database.connection import get_db_context
from app.database.models import (
    User,
    Session,
    Task,
    SessionData,
    AuditLog,
    RefreshToken,
    APIKey,
    WebhookDelivery,
)

logger = logging.getLogger(__name__)


class RetentionCategory(PythonEnum):
    """Data retention categories for lifecycle management."""

    SHORT_TERM = "short_term"  # 30 days
    STANDARD = "standard"  # 1 year
    LONG_TERM = "long_term"  # 7 years (compliance)
    PERMANENT = "permanent"  # Never delete


class DataClassification(PythonEnum):
    """Data classification levels for PII handling."""

    PUBLIC = "public"  # No restrictions
    INTERNAL = "internal"  # Business data
    CONFIDENTIAL = "confidential"  # Sensitive business data
    RESTRICTED = "restricted"  # PII/PHI


# Retention periods in days
RETENTION_PERIODS = {
    RetentionCategory.SHORT_TERM: 30,
    RetentionCategory.STANDARD: 365,
    RetentionCategory.LONG_TERM: 2555,  # 7 years
    RetentionCategory.PERMANENT: None,
}

# Data classification for each model
DATA_CLASSIFICATIONS: Dict[str, DataClassification] = {
    "users": DataClassification.RESTRICTED,
    "sessions": DataClassification.CONFIDENTIAL,
    "tasks": DataClassification.INTERNAL,
    "session_data": DataClassification.CONFIDENTIAL,
    "audit_logs": DataClassification.CONFIDENTIAL,
    "refresh_tokens": DataClassification.RESTRICTED,
    "api_keys": DataClassification.RESTRICTED,
    "webhook_deliveries": DataClassification.INTERNAL,
}

# Retention policies by data type
RETENTION_POLICIES: Dict[str, RetentionCategory] = {
    "users": RetentionCategory.LONG_TERM,  # Until account deletion
    "sessions": RetentionCategory.STANDARD,
    "tasks": RetentionCategory.STANDARD,
    "session_data": RetentionCategory.SHORT_TERM,
    "audit_logs": RetentionCategory.LONG_TERM,
    "refresh_tokens": RetentionCategory.SHORT_TERM,
    "api_keys": RetentionCategory.SHORT_TERM,  # Until expiration
    "webhook_deliveries": RetentionCategory.SHORT_TERM,
}

# PII fields by model
PII_FIELDS: Dict[str, Set[str]] = {
    "users": {"username", "email", "password_hash", "mfa_secret", "mfa_backup_codes"},
    "sessions": {"config", "full_state"},  # May contain PII
    "session_data": {"data"},  # May contain PII
    "audit_logs": {"ip_address", "user_agent"},
    "refresh_tokens": {"token_hash", "token_sha256"},
    "api_keys": {"key_hash"},
    "webhook_deliveries": {"payload"},  # May contain PII
}


class DataLifecycleManager:
    """
    Manages data lifecycle operations including retention, deletion, and PII handling.

    Implements:
    - Retention schedule enforcement
    - Data deletion workflows
    - PII detection and handling
    - Audit trail for data operations
    """

    def __init__(self) -> None:
        """Initialize the data lifecycle manager."""
        self._retention_policies = RETENTION_POLICIES.copy()
        self._pii_fields = PII_FIELDS.copy()

    def get_retention_policy(self, data_type: str) -> RetentionCategory:
        """
        Get the retention policy for a data type.

        Args:
            data_type: The type of data (table name)

        Returns:
            Retention category for the data type
        """
        return self._retention_policies.get(data_type, RetentionCategory.STANDARD)

    def get_retention_days(self, data_type: str) -> Optional[int]:
        """
        Get the retention period in days for a data type.

        Args:
            data_type: The type of data

        Returns:
            Number of days, or None for permanent retention
        """
        category = self.get_retention_policy(data_type)
        return RETENTION_PERIODS[category]

    def get_data_classification(self, data_type: str) -> DataClassification:
        """
        Get the classification level for a data type.

        Args:
            data_type: The type of data

        Returns:
            Data classification level
        """
        return DATA_CLASSIFICATIONS.get(data_type, DataClassification.INTERNAL)

    def get_pii_fields(self, data_type: str) -> Set[str]:
        """
        Get the PII fields for a data type.

        Args:
            data_type: The type of data

        Returns:
            Set of field names containing PII
        """
        return self._pii_fields.get(data_type, set())

    def is_pii_field(self, data_type: str, field_name: str) -> bool:
        """
        Check if a field contains PII.

        Args:
            data_type: The type of data
            field_name: The field name to check

        Returns:
            True if the field contains PII
        """
        return field_name in self.get_pii_fields(data_type)

    def calculate_expiry_date(
        self, data_type: str, created_at: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Calculate the expiry date for data based on retention policy.

        Args:
            data_type: The type of data
            created_at: When the data was created (defaults to now)

        Returns:
            Expiry datetime, or None if permanent retention
        """
        retention_days = self.get_retention_days(data_type)
        if retention_days is None:
            return None

        if created_at is None:
            created_at = datetime.now(timezone.utc)

        return created_at + timedelta(days=retention_days)

    def find_expired_data(self, data_type: str, batch_size: int = 1000) -> List[Any]:
        """
        Find data that has exceeded its retention period.

        Args:
            data_type: The type of data to check
            batch_size: Maximum number of records to return

        Returns:
            List of expired records
        """
        retention_days = self.get_retention_days(data_type)
        if retention_days is None:
            return []

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        with get_db_context() as db:
            if data_type == "session_data":
                return (
                    db.query(SessionData)
                    .filter(SessionData.created_at < cutoff_date)
                    .limit(batch_size)
                    .all()
                )
            elif data_type == "tasks":
                return (
                    db.query(Task)
                    .filter(
                        and_(
                            Task.completed_at < cutoff_date,
                            Task.status.in_(["completed", "failed", "cancelled"]),
                        )
                    )
                    .limit(batch_size)
                    .all()
                )
            elif data_type == "sessions":
                return (
                    db.query(Session)
                    .filter(
                        and_(
                            Session.updated_at < cutoff_date,
                            Session.state.in_(["stopped", "error"]),
                        )
                    )
                    .limit(batch_size)
                    .all()
                )
            elif data_type == "audit_logs":
                return (
                    db.query(AuditLog)
                    .filter(AuditLog.timestamp < cutoff_date)
                    .limit(batch_size)
                    .all()
                )
            elif data_type == "refresh_tokens":
                return (
                    db.query(RefreshToken)
                    .filter(
                        or_(
                            RefreshToken.expires_at < datetime.now(timezone.utc),
                            RefreshToken.revoked is True,
                        )
                    )
                    .limit(batch_size)
                    .all()
                )
            elif data_type == "api_keys":
                return (
                    db.query(APIKey)
                    .filter(
                        or_(
                            APIKey.expires_at < datetime.now(timezone.utc),
                            not APIKey.is_active,
                        )
                    )
                    .limit(batch_size)
                    .all()
                )
            elif data_type == "webhook_deliveries":
                return (
                    db.query(WebhookDelivery)
                    .filter(
                        and_(
                            WebhookDelivery.status.in_(["delivered", "failed"]),
                            WebhookDelivery.created_at < cutoff_date,
                        )
                    )
                    .limit(batch_size)
                    .all()
                )
            else:
                return []

    def delete_expired_data(
        self, data_type: str, dry_run: bool = False, batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Delete data that has exceeded its retention period.

        Args:
            data_type: The type of data to delete
            dry_run: If True, only count records without deleting
            batch_size: Maximum number of records to process

        Returns:
            Dict with deletion summary
        """
        expired_records = self.find_expired_data(data_type, batch_size)
        count = len(expired_records)

        if dry_run:
            return {
                "data_type": data_type,
                "would_delete": count,
                "dry_run": True,
            }

        deleted_count = 0
        with get_db_context() as db:
            for record in expired_records:
                try:
                    db.delete(record)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete record: {e}")

            if deleted_count > 0:
                db.commit()
                logger.info(f"Deleted {deleted_count} expired {data_type} records")

        return {
            "data_type": data_type,
            "deleted": deleted_count,
            "dry_run": False,
        }

    def delete_user_data(self, user_id: str, reason: str = "user_request") -> Dict[str, Any]:
        """
        Delete all data associated with a user (GDPR/CCPA right to deletion).

        Args:
            user_id: The user ID to delete
            reason: Reason for deletion (for audit log)

        Returns:
            Dict with deletion summary
        """
        deletion_summary: Dict[str, int] = {}

        with get_db_context() as db:
            # Get user's sessions
            sessions = db.query(Session).filter(Session.user_id == user_id).all()
            session_ids = [s.session_id for s in sessions]

            # Delete session data
            if session_ids:
                session_data_count = (
                    db.query(SessionData)
                    .filter(SessionData.session_id.in_(session_ids))
                    .delete(synchronize_session=False)
                )
                deletion_summary["session_data"] = session_data_count

            # Delete tasks
            if session_ids:
                tasks_count = (
                    db.query(Task)
                    .filter(Task.session_id.in_(session_ids))
                    .delete(synchronize_session=False)
                )
                deletion_summary["tasks"] = tasks_count

            # Delete sessions
            sessions_count = (
                db.query(Session)
                .filter(Session.user_id == user_id)
                .delete(synchronize_session=False)
            )
            deletion_summary["sessions"] = sessions_count

            # Delete refresh tokens
            tokens_count = (
                db.query(RefreshToken)
                .filter(RefreshToken.user_id == user_id)
                .delete(synchronize_session=False)
            )
            deletion_summary["refresh_tokens"] = tokens_count

            # Delete API keys
            api_keys_count = (
                db.query(APIKey).filter(APIKey.user_id == user_id).delete(synchronize_session=False)
            )
            deletion_summary["api_keys"] = api_keys_count

            # Soft delete user (keep record with anonymized data)
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                user.is_deleted = True
                user.is_active = False
                user.username = f"deleted_{user_id[:8]}"
                user.email = f"deleted_{user_id[:8]}@deleted.local"
                user.password_hash = "deleted"
                user.mfa_secret = None
                user.mfa_backup_codes = None
                deletion_summary["user_soft_deleted"] = 1

            db.commit()

        # Log the deletion
        logger.info(f"User data deletion completed for {user_id}: {deletion_summary}")

        return {
            "user_id": user_id,
            "reason": reason,
            "deleted_counts": deletion_summary,
        }

    def anonymize_pii(self, data_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize PII fields in data.

        Args:
            data_type: The type of data
            data: The data dict containing potential PII

        Returns:
            Data dict with PII anonymized
        """
        pii_fields = self.get_pii_fields(data_type)
        result = dict(data)

        for field in pii_fields:
            if field in result:
                # Replace with anonymized placeholder
                result[field] = "[REDACTED]"

        return result

    def get_data_retention_report(self) -> Dict[str, Any]:
        """
        Generate a report of data retention status.

        Returns:
            Dict with retention statistics
        """
        report: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_types": {},
        }

        with get_db_context() as db:
            for data_type in self._retention_policies.keys():
                retention_days = self.get_retention_days(data_type)
                classification = self.get_data_classification(data_type)

                # Count total records
                if data_type == "session_data":
                    total = db.query(SessionData).count()
                elif data_type == "tasks":
                    total = db.query(Task).count()
                elif data_type == "sessions":
                    total = db.query(Session).count()
                elif data_type == "audit_logs":
                    total = db.query(AuditLog).count()
                elif data_type == "refresh_tokens":
                    total = db.query(RefreshToken).count()
                elif data_type == "api_keys":
                    total = db.query(APIKey).count()
                elif data_type == "webhook_deliveries":
                    total = db.query(WebhookDelivery).count()
                else:
                    total = 0

                # Count expired records
                expired = len(self.find_expired_data(data_type, batch_size=10000))

                report["data_types"][data_type] = {
                    "total_records": total,
                    "expired_records": expired,
                    "retention_days": retention_days,
                    "retention_category": self.get_retention_policy(data_type).value,
                    "classification": classification.value,
                    "pii_fields": list(self.get_pii_fields(data_type)),
                }

        return report

    def enforce_all_retention_policies(self, dry_run: bool = True) -> List[Dict[str, Any]]:
        """
        Enforce retention policies for all data types.

        Args:
            dry_run: If True, only simulate deletions

        Returns:
            List of deletion summaries
        """
        results = []

        for data_type in self._retention_policies.keys():
            result = self.delete_expired_data(data_type, dry_run=dry_run)
            results.append(result)

        return results


# Global instance
data_lifecycle_manager = DataLifecycleManager()
