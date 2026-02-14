"""
User Management Service

Handles user CRUD operations and user-related business logic.
"""

from typing import Optional
from sqlalchemy.orm import Session


class UserManagementService:
    """Service for managing users."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db


def get_user_management_service(db: Session) -> UserManagementService:
    """Get user management service instance."""
    return UserManagementService(db)
