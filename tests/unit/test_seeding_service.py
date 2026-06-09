"""
Unit tests for DatabaseSeedingService.

Tests seed and rollback paths using a MagicMock DB session.
Requirements: 2.7
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.seeding_service import DatabaseSeedingService


@pytest.fixture
def seeding_service() -> DatabaseSeedingService:
    return DatabaseSeedingService()


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    # Default: no existing records (unique-check queries return None)
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.delete.return_value = 0
    return db


def _patch_db(mock_db: MagicMock) -> Any:
    """Return a context-manager patch for get_db_context."""
    p = patch("app.services.seeding_service.get_db_context")
    return p


# ---------------------------------------------------------------------------
# seed_users
# ---------------------------------------------------------------------------


class TestSeedUsers:
    def test_seed_users_with_admin(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        with (
            patch("app.services.seeding_service.get_db_context") as mock_ctx,
            patch("app.services.seeding_service.AuthManager.hash_password", return_value="hashed"),
        ):
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_users(count=3, include_admin=True)

        assert "admin_user" in ids
        assert len(ids) == 4  # 3 regular + 1 admin
        assert mock_db.add.call_count == 4
        mock_db.commit.assert_called_once()

    def test_seed_users_without_admin(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        with (
            patch("app.services.seeding_service.get_db_context") as mock_ctx,
            patch("app.services.seeding_service.AuthManager.hash_password", return_value="hashed"),
        ):
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_users(count=2, include_admin=False)

        assert "admin_user" not in ids
        assert len(ids) == 2
        assert mock_db.add.call_count == 2

    def test_seed_users_zero_count(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        with (
            patch("app.services.seeding_service.get_db_context") as mock_ctx,
            patch("app.services.seeding_service.AuthManager.hash_password", return_value="hashed"),
        ):
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_users(count=0, include_admin=False)

        assert ids == []
        mock_db.add.assert_not_called()

    def test_seed_users_ids_format(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        with (
            patch("app.services.seeding_service.get_db_context") as mock_ctx,
            patch("app.services.seeding_service.AuthManager.hash_password", return_value="hashed"),
        ):
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_users(count=3, include_admin=False)

        assert all(id_.startswith("user_") for id_ in ids)

    def test_seed_users_username_collision(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        """Test username collision handling (lines 63-64)."""
        with (
            patch("app.services.seeding_service.get_db_context") as mock_ctx,
            patch("app.services.seeding_service.AuthManager.hash_password", return_value="hashed"),
        ):
            # Simulate username collision - first query returns existing user, second returns None
            mock_user = MagicMock()
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                mock_user,
                None,
                None,
            ]
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_users(count=1, include_admin=False)

        assert len(ids) == 1
        # Should have called query at least twice due to collision
        assert mock_db.query.return_value.filter.return_value.first.call_count >= 2

    def test_seed_users_email_collision(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        """Test email collision handling (lines 65-66)."""
        with (
            patch("app.services.seeding_service.get_db_context") as mock_ctx,
            patch("app.services.seeding_service.AuthManager.hash_password", return_value="hashed"),
        ):
            # Simulate email collision - first query returns existing user for email, second returns None
            mock_user = MagicMock()
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                None,
                mock_user,
                None,
            ]
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_users(count=1, include_admin=False)

        assert len(ids) == 1
        # Should have called query at least twice due to collision
        assert mock_db.query.return_value.filter.return_value.first.call_count >= 2


# ---------------------------------------------------------------------------
# seed_session_templates
# ---------------------------------------------------------------------------


class TestSeedSessionTemplates:
    def test_seed_templates_basic(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        user_ids = ["user_001", "user_002"]
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_session_templates(user_ids, count=3)

        assert len(ids) == 3
        assert all(tid.startswith("template_") for tid in ids)
        assert mock_db.add.call_count == 3
        mock_db.commit.assert_called_once()

    def test_seed_templates_count_capped_by_configs(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        """count > number of template configs should be capped."""
        user_ids = ["user_001"]
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_session_templates(user_ids, count=100)

        # Only 5 template configs exist
        assert len(ids) == 5

    def test_seed_templates_zero_count(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_session_templates(["user_001"], count=0)

        assert ids == []
        mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# seed_sessions
# ---------------------------------------------------------------------------


class TestSeedSessions:
    def test_seed_sessions_basic(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        user_ids = ["user_001", "user_002"]
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_sessions(user_ids, count=4)

        assert len(ids) == 4
        assert all(sid.startswith("session_") for sid in ids)
        assert mock_db.add.call_count == 4
        mock_db.commit.assert_called_once()

    def test_seed_sessions_with_templates(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        user_ids = ["user_001"]
        template_ids = ["template_001", "template_002"]
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_sessions(user_ids, template_ids, count=3)

        assert len(ids) == 3

    def test_seed_sessions_without_templates(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        user_ids = ["user_001"]
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_sessions(user_ids, template_ids=None, count=2)

        assert len(ids) == 2

    def test_seed_sessions_returns_ids(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_sessions(["user_001"], count=5)

        assert ids == [f"session_{i:03d}" for i in range(5)]


# ---------------------------------------------------------------------------
# seed_tasks
# ---------------------------------------------------------------------------


class TestSeedTasks:
    def test_seed_tasks_basic(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        session_ids = ["session_001", "session_002"]
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_tasks(session_ids, count=5)

        assert len(ids) == 5
        assert all(tid.startswith("task_") for tid in ids)
        assert mock_db.add.call_count == 5
        mock_db.commit.assert_called_once()

    def test_seed_tasks_zero_count(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            ids = seeding_service.seed_tasks(["session_001"], count=0)

        assert ids == []


# ---------------------------------------------------------------------------
# seed_task_dependencies
# ---------------------------------------------------------------------------


class TestSeedTaskDependencies:
    def test_seed_dependencies_basic(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        task_ids = ["task_001", "task_002", "task_003"]
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            dep_ids = seeding_service.seed_task_dependencies(task_ids, count=2)

        assert isinstance(dep_ids, list)
        mock_db.commit.assert_called_once()

    def test_seed_dependencies_skips_duplicates(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        """When a dependency already exists, it should be skipped."""
        task_ids = ["task_001", "task_002"]
        # Simulate existing dependency
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            dep_ids = seeding_service.seed_task_dependencies(task_ids, count=5)

        # No new dependencies added since all are "existing"
        mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# clear_all_data
# ---------------------------------------------------------------------------


class TestClearAllData:
    def test_clear_all_data_returns_counts(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        mock_db.query.return_value.delete.return_value = 3
        mock_db.query.return_value.filter.return_value.delete.return_value = 5
        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = seeding_service.clear_all_data()

        assert isinstance(result, dict)
        assert "users" in result
        assert "sessions" in result
        assert "tasks" in result
        assert "task_dependencies" in result
        assert "session_templates" in result
        mock_db.commit.assert_called_once()

    def test_clear_all_data_calls_delete_in_order(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        """Verify FK-safe deletion order: dependencies first, then tasks, sessions, etc."""
        call_order: list[str] = []

        def track_delete() -> int:
            call_order.append("delete")
            return 0

        mock_db.query.return_value.delete.side_effect = track_delete
        mock_db.query.return_value.filter.return_value.delete.side_effect = track_delete

        with patch("app.services.seeding_service.get_db_context") as mock_ctx:
            mock_ctx.return_value.__enter__.return_value = mock_db
            seeding_service.clear_all_data()

        # 5 delete calls: task_dependencies, tasks, sessions, session_templates, users
        assert len(call_order) == 5


# ---------------------------------------------------------------------------
# seed_all
# ---------------------------------------------------------------------------


class TestSeedAll:
    def test_seed_all_returns_summary(
        self, seeding_service: DatabaseSeedingService, mock_db: MagicMock
    ) -> None:
        with (
            patch("app.services.seeding_service.get_db_context") as mock_ctx,
            patch("app.services.seeding_service.AuthManager.hash_password", return_value="hashed"),
        ):
            mock_ctx.return_value.__enter__.return_value = mock_db
            result = seeding_service.seed_all(
                user_count=2, template_count=2, session_count=3, task_count=4
            )

        assert "users_created" in result
        assert "templates_created" in result
        assert "sessions_created" in result
        assert "tasks_created" in result
        assert "dependencies_created" in result
        assert result["users_created"] == 3  # 2 regular + 1 admin
        assert result["templates_created"] == 2
        assert result["sessions_created"] == 3
        assert result["tasks_created"] == 4


# ---------------------------------------------------------------------------
# _generate_task_parameters
# ---------------------------------------------------------------------------


class TestGenerateTaskParameters:
    @pytest.mark.parametrize(
        "task_type,expected_keys",
        [
            (
                "attentional_blink",
                ["stream_length", "target_position", "distractor_count", "stimulus_duration_ms"],
            ),
            ("working_memory", ["n_back_level", "sequence_length", "stimulus_types"]),
            ("decision_making", ["deck_count", "trials_per_block", "feedback_delay_ms"]),
            ("visual_search", ["target_type", "set_size", "target_present"]),
            ("emotion_recognition", ["emotion", "intensity", "presentation_time_ms"]),
            ("unknown_type", ["custom_parameter"]),
        ],
    )
    def test_generate_parameters(
        self, seeding_service: DatabaseSeedingService, task_type: str, expected_keys: list[str]
    ) -> None:
        params = seeding_service._generate_task_parameters(task_type)
        assert isinstance(params, dict)
        for key in expected_keys:
            assert key in params


# ---------------------------------------------------------------------------
# _generate_task_result
# ---------------------------------------------------------------------------


class TestGenerateTaskResult:
    @pytest.mark.parametrize(
        "task_type,expected_keys",
        [
            ("attentional_blink", ["accuracy", "reaction_time_ms", "blink_effect_detected"]),
            ("working_memory", ["accuracy", "false_positives", "false_negatives"]),
            ("decision_making", ["total_score", "good_deck_preference", "learning_rate"]),
            ("visual_search", ["search_time_ms", "accuracy", "slope_coefficient"]),
            ("emotion_recognition", ["accuracy", "reaction_time_ms", "confidence_rating"]),
            ("unknown_type", ["result_value"]),
        ],
    )
    def test_generate_result(
        self, seeding_service: DatabaseSeedingService, task_type: str, expected_keys: list[str]
    ) -> None:
        result = seeding_service._generate_task_result(task_type)
        assert isinstance(result, dict)
        for key in expected_keys:
            assert key in result
