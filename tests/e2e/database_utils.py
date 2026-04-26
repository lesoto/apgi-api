"""
Database State Testing Utilities

Utilities for testing database state and managing test data in E2E tests.
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.connection import get_db_context
from app.database.models import Session as SessionModel
from app.database.models import SessionTemplate, Task, TaskDependency, User

logger = logging.getLogger(__name__)


class DatabaseStateTester:
    """Utilities for testing database state in E2E tests."""

    @staticmethod
    def get_table_row_count(table_name: str) -> int:
        """Get the number of rows in a table."""
        with get_db_context() as db:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            return result.scalar()  # type: ignore[return-value]

    @staticmethod
    def get_user_count() -> int:
        """Get total number of users."""
        with get_db_context() as db:
            return db.query(User).count()

    @staticmethod
    def get_session_count(user_id: Optional[str] = None) -> int:
        """Get number of sessions, optionally filtered by user."""
        with get_db_context() as db:
            query = db.query(SessionModel)
            if user_id:
                query = query.filter(SessionModel.user_id == user_id)
            return query.count()

    @staticmethod
    def get_task_count(session_id: Optional[str] = None) -> int:
        """Get number of tasks, optionally filtered by session."""
        with get_db_context() as db:
            query = db.query(Task)
            if session_id:
                query = query.filter(Task.session_id == session_id)
            return query.count()

    @staticmethod
    def get_template_count(user_id: Optional[str] = None) -> int:
        """Get number of templates, optionally filtered by user."""
        with get_db_context() as db:
            query = db.query(SessionTemplate)
            if user_id:
                query = query.filter(SessionTemplate.user_id == user_id)
            return query.count()

    @staticmethod
    def verify_user_exists(user_id: str) -> bool:
        """Verify that a user exists."""
        with get_db_context() as db:
            return db.query(User).filter(User.user_id == user_id).first() is not None

    @staticmethod
    def verify_session_exists(session_id: str) -> bool:
        """Verify that a session exists."""
        with get_db_context() as db:
            return (
                db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
                is not None
            )

    @staticmethod
    def verify_task_exists(task_id: str) -> bool:
        """Verify that a task exists."""
        with get_db_context() as db:
            return db.query(Task).filter(Task.task_id == task_id).first() is not None

    @staticmethod
    def get_session_state(session_id: str) -> Optional[str]:
        """Get the current state of a session."""
        with get_db_context() as db:
            session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
            return session.state if session else None

    @staticmethod
    def get_task_state(task_id: str) -> Optional[str]:
        """Get the current state of a task."""
        with get_db_context() as db:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            return task.status if task else None

    @staticmethod
    def get_user_sessions(user_id: str) -> List[Dict[str, Any]]:
        """Get all sessions for a user."""
        with get_db_context() as db:
            sessions = db.query(SessionModel).filter(SessionModel.user_id == user_id).all()
            return [
                {
                    "session_id": s.session_id,
                    "state": s.state,
                    "created_at": s.created_at.isoformat(),
                    "description": s.description,
                }
                for s in sessions
            ]

    @staticmethod
    def get_session_tasks(session_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a session."""
        with get_db_context() as db:
            tasks = db.query(Task).filter(Task.session_id == session_id).all()
            return [
                {
                    "task_id": t.task_id,
                    "task_type": t.task_type,
                    "status": t.status,
                    "created_at": t.created_at.isoformat(),
                    "priority": t.priority,
                }
                for t in tasks
            ]

    @staticmethod
    def verify_data_integrity() -> Dict[str, Any]:
        """Verify data integrity across related tables."""
        issues = []

        with get_db_context() as db:
            # Check for sessions without valid users
            orphaned_sessions = (
                db.query(SessionModel)
                .filter(~SessionModel.user_id.in_(db.query(User.user_id)))
                .count()
            )
            if orphaned_sessions > 0:
                issues.append(f"Found {orphaned_sessions} sessions with invalid user_id")

            # Check for tasks without valid sessions
            orphaned_tasks = (
                db.query(Task)
                .filter(~Task.session_id.in_(db.query(SessionModel.session_id)))
                .count()
            )
            if orphaned_tasks > 0:
                issues.append(f"Found {orphaned_tasks} tasks with invalid session_id")

            # Check for task dependencies with invalid tasks
            invalid_deps = (
                db.query(TaskDependency)
                .filter(
                    (~TaskDependency.dependent_task_id.in_(db.query(Task.task_id)))
                    | (~TaskDependency.prerequisite_task_id.in_(db.query(Task.task_id)))
                )
                .count()
            )
            if invalid_deps > 0:
                issues.append(
                    f"Found {invalid_deps} task dependencies with invalid task references"
                )

            # Check for sessions without valid templates (if template_id is set)
            invalid_template_refs = (
                db.query(SessionModel)
                .filter(
                    SessionModel.template_id.isnot(None),
                    ~SessionModel.template_id.in_(db.query(SessionTemplate.template_id)),
                )
                .count()
            )
            if invalid_template_refs > 0:
                issues.append(f"Found {invalid_template_refs} sessions with invalid template_id")

        return {
            "integrity_check_passed": len(issues) == 0,
            "issues": issues,
        }


class TestDataManager:
    """Manager for test data setup and cleanup in E2E tests."""

    def __init__(self) -> None:
        self.created_users: list[str] = []
        self.created_sessions: list[str] = []
        self.created_tasks: list[str] = []
        self.created_templates: list[str] = []

    def track_user(self, user_id: str) -> None:
        """Track a created user for cleanup."""
        self.created_users.append(user_id)

    def track_session(self, session_id: str) -> None:
        """Track a created session for cleanup."""
        self.created_sessions.append(session_id)

    def track_task(self, task_id: str) -> None:
        """Track a created task for cleanup."""
        self.created_tasks.append(task_id)

    def track_template(self, template_id: str) -> None:
        """Track a created template for cleanup."""
        self.created_templates.append(template_id)

    def cleanup_tracked_data(self) -> None:
        """Clean up all tracked test data."""
        logger.info("Cleaning up tracked test data...")

        with get_db_context() as db:
            try:
                # Delete in reverse order of dependencies
                if self.created_tasks:
                    db.query(Task).filter(Task.task_id.in_(self.created_tasks)).delete()
                    logger.info(f"Deleted {len(self.created_tasks)} test tasks")

                if self.created_sessions:
                    db.query(SessionModel).filter(
                        SessionModel.session_id.in_(self.created_sessions)
                    ).delete()
                    logger.info(f"Deleted {len(self.created_sessions)} test sessions")

                if self.created_templates:
                    db.query(SessionTemplate).filter(
                        SessionTemplate.template_id.in_(self.created_templates)
                    ).delete()
                    logger.info(f"Deleted {len(self.created_templates)} test templates")

                if self.created_users:
                    db.query(User).filter(User.user_id.in_(self.created_users)).delete()
                    logger.info(f"Deleted {len(self.created_users)} test users")

                db.commit()

                # Clear tracking lists
                self.created_users.clear()
                self.created_sessions.clear()
                self.created_tasks.clear()
                self.created_templates.clear()

            except Exception as e:
                db.rollback()
                logger.error(f"Error during test data cleanup: {e}")
                raise

    @contextmanager
    def test_data_scope(self) -> Generator["TestDataManager", None, None]:
        """Context manager for automatic test data cleanup."""
        try:
            yield self
        finally:
            self.cleanup_tracked_data()

    def create_test_user(self, db: Session, user_data: Optional[Dict[str, Any]] = None) -> str:
        """Create a test user and track it for cleanup."""
        from app.services.auth_manager import AuthManager

        if not user_data:
            from faker import Faker

            faker = Faker()
            user_data = {
                "user_id": f"test_user_{faker.uuid4()[:8]}",
                "username": faker.user_name(),
                "email": faker.email(),
                "password_hash": AuthManager.hash_password("TestPass123!"),
                "roles": ["user"],
            }

        user = User(**user_data)
        db.add(user)
        db.commit()

        self.track_user(user.user_id)  # type: ignore[arg-type]
        return user.user_id  # type: ignore[return-value]

    def create_test_session(
        self, db: Session, user_id: str, session_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a test session and track it for cleanup."""
        import uuid

        if not session_data:
            session_data = {
                "session_id": str(uuid.uuid4()),
                "user_id": user_id,
                "config": {"test": True},
                "state": "created",
                "description": "Test session",
            }

        session = SessionModel(**session_data)
        db.add(session)
        db.commit()

        self.track_session(session.session_id)  # type: ignore[arg-type]
        return session.session_id  # type: ignore[return-value]

    def create_test_task(
        self, db: Session, session_id: str, task_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a test task and track it for cleanup."""
        import uuid

        if not task_data:
            task_data = {
                "task_id": str(uuid.uuid4()),
                "session_id": session_id,
                "task_type": "test_task",
                "parameters": {},
                "status": "pending",
                "priority": 5,
            }

        task = Task(**task_data)
        db.add(task)
        db.commit()

        self.track_task(task.task_id)  # type: ignore[arg-type]
        return task.task_id  # type: ignore[return-value]


# Global instances for use in tests
database_state_tester = DatabaseStateTester()
test_data_manager = TestDataManager()


# Pytest fixtures
import pytest


@pytest.fixture
def db_state_tester() -> DatabaseStateTester:
    """Fixture providing database state testing utilities."""
    return database_state_tester


@pytest.fixture
def test_data_mgr() -> TestDataManager:
    """Fixture providing test data management utilities."""
    return test_data_manager


@pytest.fixture(autouse=True)
def cleanup_test_data() -> Generator[None, None, None]:
    """Auto-cleanup fixture for test data."""
    yield
    # Cleanup happens in the TestDataManager context manager
    # This ensures cleanup even if tests fail
