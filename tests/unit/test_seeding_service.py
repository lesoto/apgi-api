"""
Unit tests for database seeding service.

Tests seeding functionality for users, sessions, templates, tasks, and dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.seeding_service import DatabaseSeedingService


@pytest.fixture
def seeding_service():
    """Create DatabaseSeedingService instance."""
    return DatabaseSeedingService()


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.delete.return_value = 0
    return session


class TestDatabaseSeedingService:
    """Test DatabaseSeedingService functionality."""

    def test_seed_users_with_admin(self, seeding_service, mock_db_session):
        """Test seeding users including admin user."""
        with patch("app.services.seeding_service.get_db_context") as mock_get_db, patch(
            "app.services.seeding_service.AuthManager.hash_password", return_value="hashed_password"
        ):
            mock_get_db.return_value.__enter__.return_value = mock_db_session

            user_ids = seeding_service.seed_users(count=3, include_admin=True)

            assert len(user_ids) == 4  # 3 regular users + 1 admin
            assert "admin_user" in user_ids
            assert mock_db_session.add.call_count == 4
            assert mock_db_session.commit.called

    def test_seed_users_without_admin(self, seeding_service, mock_db_session):
        """Test seeding users without admin user."""
        with patch("app.services.seeding_service.get_db_context") as mock_get_db, patch(
            "app.services.seeding_service.AuthManager.hash_password", return_value="hashed_password"
        ):
            mock_get_db.return_value.__enter__.return_value = mock_db_session

            user_ids = seeding_service.seed_users(count=2, include_admin=False)

            assert len(user_ids) == 2
            assert "admin_user" not in user_ids
            assert mock_db_session.add.call_count == 2

    def test_seed_session_templates(self, seeding_service, mock_db_session):
        """Test seeding session templates."""
        user_ids = ["user_001", "user_002"]

        with patch("app.services.seeding_service.get_db_context") as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = mock_db_session

            template_ids = seeding_service.seed_session_templates(user_ids, count=2)

            assert len(template_ids) == 2
            assert all(tid.startswith("template_") for tid in template_ids)
            assert mock_db_session.add.call_count == 2
            assert mock_db_session.commit.called

    def test_seed_sessions(self, seeding_service, mock_db_session):
        """Test seeding sessions."""
        user_ids = ["user_001", "user_002"]
        template_ids = ["template_001", "template_002"]

        with patch("app.services.seeding_service.get_db_context") as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = mock_db_session

            session_ids = seeding_service.seed_sessions(user_ids, template_ids, count=3)

            assert len(session_ids) == 3
            assert all(sid.startswith("session_") for sid in session_ids)
            assert mock_db_session.add.call_count == 3
            assert mock_db_session.commit.called

    def test_seed_tasks(self, seeding_service, mock_db_session):
        """Test seeding tasks."""
        session_ids = ["session_001", "session_002"]

        with patch("app.services.seeding_service.get_db_context") as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = mock_db_session

            task_ids = seeding_service.seed_tasks(session_ids, count=4)

            assert len(task_ids) == 4
            assert all(tid.startswith("task_") for tid in task_ids)
            assert mock_db_session.add.call_count == 4
            assert mock_db_session.commit.called

    def test_seed_task_dependencies(self, seeding_service, mock_db_session):
        """Test seeding task dependencies."""
        task_ids = ["task_001", "task_002", "task_003"]

        with patch("app.services.seeding_service.get_db_context") as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = mock_db_session

            dependency_ids = seeding_service.seed_task_dependencies(task_ids, count=2)

            # Should create dependencies (may be less than requested if duplicates)
            assert isinstance(dependency_ids, list)
            assert mock_db_session.commit.called

    def test_clear_all_data(self, seeding_service, mock_db_session):
        """Test clearing all seeded data."""
        with patch("app.services.seeding_service.get_db_context") as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = mock_db_session

            result = seeding_service.clear_all_data()

            assert isinstance(result, dict)
            assert "users" in result
            assert "sessions" in result
            assert "tasks" in result
            assert "task_dependencies" in result
            assert "session_templates" in result
            assert mock_db_session.commit.called

    def test_seed_all(self, seeding_service, mock_db_session):
        """Test complete seeding workflow."""
        with patch("app.services.seeding_service.get_db_context") as mock_get_db, patch(
            "app.services.seeding_service.AuthManager.hash_password", return_value="hashed_password"
        ):
            mock_get_db.return_value.__enter__.return_value = mock_db_session

            result = seeding_service.seed_all(
                user_count=2, template_count=1, session_count=2, task_count=3
            )

            assert isinstance(result, dict)
            assert "users_created" in result
            assert "templates_created" in result
            assert "sessions_created" in result
            assert "tasks_created" in result
            assert "dependencies_created" in result
            assert result["users_created"] == 3  # 2 regular + 1 admin

    def test_generate_task_parameters_attentional_blink(self, seeding_service):
        """Test parameter generation for attentional blink tasks."""
        params = seeding_service._generate_task_parameters("attentional_blink")

        assert isinstance(params, dict)
        assert "stream_length" in params
        assert "target_position" in params
        assert "distractor_count" in params
        assert "stimulus_duration_ms" in params

    def test_generate_task_parameters_working_memory(self, seeding_service):
        """Test parameter generation for working memory tasks."""
        params = seeding_service._generate_task_parameters("working_memory")

        assert isinstance(params, dict)
        assert "n_back_level" in params
        assert "sequence_length" in params
        assert "stimulus_types" in params

    def test_generate_task_parameters_unknown_type(self, seeding_service):
        """Test parameter generation for unknown task types."""
        params = seeding_service._generate_task_parameters("unknown_type")

        assert isinstance(params, dict)
        assert "custom_parameter" in params

    def test_generate_task_result_attentional_blink(self, seeding_service):
        """Test result generation for attentional blink tasks."""
        result = seeding_service._generate_task_result("attentional_blink")

        assert isinstance(result, dict)
        assert "accuracy" in result
        assert "reaction_time_ms" in result
        assert "blink_effect_detected" in result

    def test_generate_task_result_unknown_type(self, seeding_service):
        """Test result generation for unknown task types."""
        result = seeding_service._generate_task_result("unknown_type")

        assert isinstance(result, dict)
        assert "result_value" in result
