"""
Tests for app/services/task_executor.py to address 0% coverage.
"""

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

# Reload module to ensure coverage tracking
if "app.services.task_executor" in sys.modules:
    importlib.reload(sys.modules["app.services.task_executor"])

from app.services.task_executor import TaskExecutor, async_retry_with_backoff


class TestAsyncRetryWithBackoff:
    """Test async_retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        """Test function succeeds on first attempt."""
        mock_func = MagicMock(return_value="success")

        async def async_func():
            return mock_func()

        result = await async_retry_with_backoff(async_func, max_retries=0)
        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        """Test retry after failure then success."""
        mock_func = MagicMock(side_effect=[Exception("fail"), "success"])

        async def async_func():
            return mock_func()

        result = await async_retry_with_backoff(async_func, max_retries=1, base_delay=0.001)
        assert result == "success"
        assert mock_func.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_fail(self):
        """Test when all retries fail."""
        mock_func = MagicMock(side_effect=Exception("always fails"))

        async def async_func():
            return mock_func()

        with pytest.raises(Exception, match="always fails"):
            await async_retry_with_backoff(async_func, max_retries=2, base_delay=0.001)

        assert mock_func.call_count == 3  # Initial + 2 retries


class TestTaskExecutor:
    """Test TaskExecutor class."""

    def test_init(self):
        """Test TaskExecutor initialization."""
        executor = TaskExecutor()
        assert executor is not None
        assert "iowa_gambling" in executor.TASK_MAP
        assert "masking_paradigm" in executor.TASK_MAP

    def test_allowed_task_types(self):
        """Test allowed task types list."""
        executor = TaskExecutor()
        assert "iowa_gambling" in executor.ALLOWED_TASK_TYPES
        assert "attentional_blink" in executor.ALLOWED_TASK_TYPES

    def test_task_info(self):
        """Test task metadata."""
        executor = TaskExecutor()
        info = executor.TASK_INFO.get("iowa_gambling")
        assert info is not None
        assert "name" in info
        assert "description" in info

    @pytest.mark.asyncio
    @patch("app.services.task_executor.get_db_context")
    async def test_submit_task_invalid_type(self, mock_get_db):
        """Test submitting a task with invalid type raises error."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        executor = TaskExecutor()
        with pytest.raises(ValueError, match="Invalid task type"):
            await executor.submit_task(
                session_id="session-123",
                task_type="invalid_task",
                parameters={},
                user_id="user-123",
            )

    @pytest.mark.asyncio
    @patch("app.services.task_executor.get_db_context")
    async def test_submit_task_invalid_priority(self, mock_get_db):
        """Test submitting a task with invalid priority raises error."""
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        executor = TaskExecutor()
        with pytest.raises(ValueError, match="Priority must be between"):
            await executor.submit_task(
                session_id="session-123",
                task_type="iowa_gambling",
                parameters={},
                user_id="user-123",
                priority=15,  # Invalid priority
            )
