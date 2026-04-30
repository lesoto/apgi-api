"""
Coverage tests for app/services/task_execution/
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.models import Task, TaskStatus
from app.services.task_execution.dependency_manager import DependencyManager
from app.services.task_execution.task_executor import TaskExecutor


@pytest.fixture
def mock_db():
    db = MagicMock()
    # Mock the context manager __enter__ to return the db mock
    db.__enter__.return_value = db
    return db


@pytest.mark.asyncio
async def test_task_executor_list_available_tasks():
    executor = TaskExecutor()
    with patch.object(executor.strategy_registry, "get_all") as mock_get_all:
        mock_strategy = MagicMock()
        mock_strategy.get_task_info.return_value = {"id": "test_task"}
        mock_get_all.return_value = [mock_strategy]

        result = await executor.list_available_tasks()
        assert result["tasks"] == [{"id": "test_task"}]


@pytest.mark.asyncio
async def test_task_executor_submit_task_success():
    executor = TaskExecutor()
    user_id = "user-1"
    session_id = "sess-1"
    task_type = "iowa_gambling"
    params = {"p": 1}

    mock_session = MagicMock()
    mock_session.session_id = session_id
    mock_session.user_id = user_id

    with (
        patch("app.services.task_execution.task_executor.get_db_context") as mock_db_ctx,
        patch.object(executor.task_submitter, "submit_task", new_callable=AsyncMock) as mock_submit,
        patch.object(executor.dependency_manager, "has_cycle", return_value=False),
        patch.object(executor.dependency_manager, "can_start_task", return_value=True),
        patch.object(
            executor.task_submitter, "start_task_immediately", new_callable=AsyncMock
        ) as mock_start,
    ):

        mock_db = mock_db_ctx.return_value.__enter__.return_value
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        mock_submit.return_value = "task-1"

        task_id = await executor.submit_task(session_id, task_type, params, user_id)
        assert task_id == "task-1"
        assert mock_start.called


@pytest.mark.asyncio
async def test_task_executor_submit_task_invalid_type():
    executor = TaskExecutor()
    with pytest.raises(ValueError, match="Invalid task type"):
        await executor.submit_task("s", "invalid", {}, "u")


@pytest.mark.asyncio
async def test_task_executor_submit_task_invalid_priority():
    executor = TaskExecutor()
    with pytest.raises(ValueError, match="Priority must be between"):
        await executor.submit_task("s", "iowa_gambling", {}, "u", priority=11)


@pytest.mark.asyncio
async def test_task_executor_submit_task_session_not_found():
    executor = TaskExecutor()
    with patch("app.services.task_execution.task_executor.get_db_context") as mock_db_ctx:
        mock_db = mock_db_ctx.return_value.__enter__.return_value
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="Session .* not found"):
            await executor.submit_task("s", "iowa_gambling", {}, "u")


@pytest.mark.asyncio
async def test_task_executor_submit_task_cycle_detected():
    executor = TaskExecutor()
    with (
        patch("app.services.task_execution.task_executor.get_db_context") as mock_db_ctx,
        patch.object(
            executor.task_submitter, "submit_task", new_callable=AsyncMock, return_value="task-1"
        ),
        patch.object(executor.dependency_manager, "has_cycle", return_value=True),
    ):

        mock_db = mock_db_ctx.return_value.__enter__.return_value
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            MagicMock()
        )
        mock_task = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_task

        with pytest.raises(ValueError, match="Task dependency cycle detected"):
            await executor.submit_task("s", "iowa_gambling", {}, "u")
        assert mock_db.delete.called


@pytest.mark.asyncio
async def test_task_executor_get_task_status_success():
    executor = TaskExecutor()
    with (
        patch("app.services.task_execution.task_executor.get_db_context") as mock_db_ctx,
        patch("app.services.task_execution.task_executor.AsyncResult") as mock_async_res_cls,
    ):

        mock_db = mock_db_ctx.return_value.__enter__.return_value
        mock_task = MagicMock()
        mock_task.status = "completed"
        mock_task.result_data = {"res": 1}
        mock_task.error_message = None
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task
        )

        mock_async_res = mock_async_res_cls.return_value
        mock_async_res.state = "SUCCESS"

        status = await executor.get_task_status("t1", "u1")
        assert status["status"] == "completed"
        assert status["result"] == {"res": 1}


@pytest.mark.asyncio
async def test_dependency_manager_can_start_task_no_deps(mock_db):
    dm = DependencyManager()
    with patch(
        "app.services.task_execution.dependency_manager.get_db_context", return_value=mock_db
    ):
        mock_db.query.return_value.filter.return_value.all.return_value = []
        assert dm.can_start_task("t1") is True


@pytest.mark.asyncio
async def test_dependency_manager_can_start_task_with_deps_satisfied(mock_db):
    dm = DependencyManager()
    with patch(
        "app.services.task_execution.dependency_manager.get_db_context", return_value=mock_db
    ):
        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "p1"
        mock_dep.dependency_type = "completion"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        mock_prereq = MagicMock()
        mock_prereq.status = TaskStatus.COMPLETED.value
        # Mock query sequence: first for dependencies, second for prerequisite
        mock_db.query.return_value.filter.return_value.first.return_value = mock_prereq

        assert dm.can_start_task("t1") is True


@pytest.mark.asyncio
async def test_dependency_manager_has_cycle_direct(mock_db):
    dm = DependencyManager()
    with patch(
        "app.services.task_execution.dependency_manager.get_db_context", return_value=mock_db
    ):
        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "t1"  # Cycle to self
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        assert dm.has_cycle("t1") is True


@pytest.mark.asyncio
async def test_dependency_manager_full_chain(mock_db):
    dm = DependencyManager()
    with patch(
        "app.services.task_execution.dependency_manager.get_db_context", return_value=mock_db
    ):
        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "p1"
        mock_db.query.return_value.filter.return_value.all.side_effect = [[mock_dep], []]

        chain = dm.get_dependency_chain("t1")
        assert chain == ["p1"]


@pytest.mark.asyncio
async def test_dependency_manager_get_dependent_tasks(mock_db):
    dm = DependencyManager()
    with patch(
        "app.services.task_execution.dependency_manager.get_db_context", return_value=mock_db
    ):
        mock_dep = MagicMock()
        mock_dep.dependent_task_id = "d1"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        dependents = dm.get_dependent_tasks("p1")
        assert dependents == ["d1"]


@pytest.mark.asyncio
async def test_dependency_manager_validate_new_dependency_cycle(mock_db):
    dm = DependencyManager()
    with patch.object(dm, "get_dependency_chain", return_value=["d1", "p1"]):
        with pytest.raises(ValueError, match="would create a cycle"):
            dm.validate_new_dependency("d1", "p1")


@pytest.mark.asyncio
async def test_dependency_manager_get_ready_tasks(mock_db):
    dm = DependencyManager()
    with patch(
        "app.services.task_execution.dependency_manager.get_db_context", return_value=mock_db
    ):
        mock_task = MagicMock(spec=Task)
        mock_task.task_id = "t1"
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_task
        ]

        with patch.object(dm, "can_start_task", return_value=True):
            ready = dm.get_ready_tasks("s1")
            assert len(ready) == 1
            assert ready[0].task_id == "t1"


@pytest.mark.asyncio
async def test_task_executor_check_and_start_pending_tasks():
    executor = TaskExecutor()
    mock_task = MagicMock()
    mock_task.task_type = "iowa_gambling"
    mock_task.session_id = "s1"
    mock_task.task_id = "t1"
    mock_task.parameters = {}

    with (
        patch.object(executor.dependency_manager, "get_ready_tasks", return_value=[mock_task]),
        patch("app.services.task_execution.task_executor.celery_app") as mock_celery,
        patch("app.services.task_execution.task_executor.get_db_context"),
    ):

        await executor.check_and_start_pending_tasks("s1")
        assert mock_celery.send_task.called


@pytest.mark.asyncio
async def test_task_executor_cancel_task():
    executor = TaskExecutor()
    with (
        patch("app.services.task_execution.task_executor.get_db_context") as mock_db_ctx,
        patch("app.services.task_execution.task_executor.celery_app") as mock_celery,
    ):

        mock_db = mock_db_ctx.return_value.__enter__.return_value
        mock_task = MagicMock()
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task
        )

        result = await executor.cancel_task("t1", "u1")
        assert result["status"] == "cancelled"
        assert mock_celery.control.revoke.called
        assert mock_db.commit.called


@pytest.mark.asyncio
async def test_task_executor_retry_task():
    executor = TaskExecutor()
    with patch.object(executor.task_submitter, "retry_task", new_callable=AsyncMock) as mock_retry:
        result = await executor.retry_task("t1", "s1", "iowa_gambling", {})
        assert result["status"] == "retrying"
        assert mock_retry.called


@pytest.mark.asyncio
async def test_task_strategies_validation():
    from app.services.task_execution.task_strategies import (
        IowaGamblingStrategy,
        MaskingParadigmStrategy,
    )

    igs = IowaGamblingStrategy()
    params = {"num_trials": 50}
    validated = igs.validate_parameters(params)
    assert validated["num_trials"] == 50
    assert validated["initial_balance"] == 2000  # default

    mps = MaskingParadigmStrategy()
    with pytest.raises(ValueError, match="soas must be a list"):
        mps.validate_parameters({"soas": "not a list"})


@pytest.mark.asyncio
async def test_async_retry_with_backoff_success():
    from app.services.task_execution.task_submitter import async_retry_with_backoff

    mock_func = AsyncMock(side_effect=[Exception("fail"), "success"])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await async_retry_with_backoff(mock_func, max_retries=2, base_delay=0.1)
        assert result == "success"
        assert mock_func.call_count == 2


@pytest.mark.asyncio
async def test_async_retry_with_backoff_failure():
    from app.services.task_execution.task_submitter import async_retry_with_backoff

    mock_func = AsyncMock(side_effect=Exception("permanent fail"))

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(Exception, match="permanent fail"):
            await async_retry_with_backoff(mock_func, max_retries=1)
        assert mock_func.call_count == 2


@pytest.mark.asyncio
async def test_dependency_manager_dependency_types(mock_db):
    dm = DependencyManager()
    with patch(
        "app.services.task_execution.dependency_manager.get_db_context", return_value=mock_db
    ):
        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "p1"
        mock_dep.dependency_type = "failure"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]

        mock_prereq = MagicMock()
        mock_prereq.status = TaskStatus.FAILED.value
        mock_db.query.return_value.filter.return_value.first.return_value = mock_prereq

        assert dm.can_start_task("t1") is True


@pytest.mark.asyncio
async def test_dependency_manager_errors(mock_db):
    dm = DependencyManager()
    with patch(
        "app.services.task_execution.dependency_manager.get_db_context",
        side_effect=Exception("DB Error"),
    ):
        assert dm.can_start_task("t1") is False
        assert dm.has_cycle("t1") is True
        assert dm.get_dependency_chain("t1") == []
        assert dm.get_dependent_tasks("t1") == []


@pytest.mark.asyncio
async def test_task_executor_get_task_status_failure_and_timeout():
    executor = TaskExecutor()
    with (
        patch("app.services.task_execution.task_executor.get_db_context") as mock_db_ctx,
        patch("app.services.task_execution.task_executor.AsyncResult") as mock_async_res_cls,
        patch("app.config.settings") as mock_settings,
    ):

        mock_db = mock_db_ctx.return_value.__enter__.return_value
        mock_task = MagicMock()
        mock_task.status = "running"
        mock_task.started_at = datetime.now(timezone.utc).replace(year=2000)  # Old
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            mock_task
        )

        mock_async_res = mock_async_res_cls.return_value
        mock_async_res.state = "FAILURE"
        mock_async_res.result = "worker error"

        mock_settings.task_timeout_seconds = 60

        status = await executor.get_task_status("t1", "u1")
        assert status["status"] == TaskStatus.FAILED.value
        assert mock_db.commit.called


@pytest.mark.asyncio
async def test_task_executor_check_and_start_errors():
    executor = TaskExecutor()
    mock_task = MagicMock()
    mock_task.task_type = "iowa_gambling"
    mock_task.session_id = "s1"

    with (
        patch.object(executor.dependency_manager, "get_ready_tasks", return_value=[mock_task]),
        patch("app.services.task_execution.task_executor.celery_app") as mock_celery,
        patch("app.services.task_execution.task_executor.get_db_context"),
    ):

        mock_celery.send_task.side_effect = Exception("Celery Down")
        await executor.check_and_start_pending_tasks("s1")
        assert mock_task.status == TaskStatus.FAILED.value


@pytest.mark.asyncio
async def test_task_submitter_methods(mock_db):
    from app.services.task_execution.task_submitter import TaskSubmitter

    ts = TaskSubmitter()

    with patch("app.services.task_execution.task_submitter.get_db_context", return_value=mock_db):
        ts.create_task_record("t1", "s1", "iowa_gambling", {}, 5, None)
        assert mock_db.add.called

        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        ts.mark_task_failed("t1", "error")
        assert mock_db.commit.called

    with patch.object(ts.strategy_registry, "get") as mock_get:
        mock_get.return_value = None
        with pytest.raises(ValueError, match="No strategy found"):
            ts.validate_parameters("unknown", {})


@pytest.mark.asyncio
async def test_task_executor_more_edge_cases():
    executor = TaskExecutor()
    with patch("app.services.task_execution.task_executor.get_db_context") as mock_db_ctx:
        mock_db = mock_db_ctx.return_value.__enter__.return_value
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )

        with pytest.raises(ValueError, match="Task .* not found"):
            await executor.get_task_status("t1", "u1")

        with pytest.raises(ValueError, match="Task .* not found"):
            await executor.cancel_task("t1", "u1")


@pytest.mark.asyncio
async def test_task_executor_get_task_status_started():
    executor = TaskExecutor()
    with (
        patch("app.services.task_execution.task_executor.get_db_context"),
        patch("app.services.task_execution.task_executor.AsyncResult") as mock_async_res_cls,
    ):

        mock_async_res = mock_async_res_cls.return_value
        mock_async_res.state = "STARTED"
        mock_async_res.info = {"progress": 50}

        status = await executor.get_task_status("t1", "u1")
        assert status["info"] == {"progress": 50}


@pytest.mark.asyncio
async def test_task_submitter_validation_errors():
    from app.services.task_execution.task_submitter import TaskSubmitter

    ts = TaskSubmitter()

    with pytest.raises(ValueError, match="Invalid task type"):
        ts.validate_task_type("invalid")

    with pytest.raises(ValueError, match="Priority must be between"):
        ts.validate_priority(0)


@pytest.mark.asyncio
async def test_task_submitter_submit_to_celery_errors():
    from app.services.task_execution.task_submitter import TaskSubmitter

    ts = TaskSubmitter()

    with pytest.raises(ValueError, match="No Celery task mapping"):
        await ts.submit_to_celery("t1", "unknown", "s1", {})


@pytest.mark.asyncio
async def test_task_submitter_full_flows(mock_db):
    from app.services.task_execution.task_submitter import TaskSubmitter

    ts = TaskSubmitter()

    with (
        patch("app.services.task_execution.task_submitter.get_db_context", return_value=mock_db),
        patch("app.services.task_execution.task_submitter.uuid.uuid4", return_value="uuid-1"),
    ):

        task_id = await ts.submit_task("s1", "iowa_gambling", {"num_trials": 10}, "u1")
        assert task_id == "uuid-1"

    with patch.object(ts, "submit_to_celery", new_callable=AsyncMock) as mock_sub:
        await ts.start_task_immediately("t1", "iowa_gambling", "s1", {})
        assert mock_sub.called

    with (
        patch.object(ts, "submit_to_celery", new_callable=AsyncMock) as mock_sub,
        patch("app.services.task_execution.task_submitter.get_db_context", return_value=mock_db),
    ):
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        await ts.retry_task("t1", "iowa_gambling", "s1", {})
        assert mock_sub.called


@pytest.mark.asyncio
async def test_task_submitter_start_task_immediately_failure(mock_db):
    from app.services.task_execution.task_submitter import TaskSubmitter

    ts = TaskSubmitter()
    with (
        patch.object(ts, "submit_to_celery", side_effect=Exception("Celery Error")),
        patch.object(ts, "mark_task_failed") as mock_mark,
    ):
        with pytest.raises(Exception, match="Celery Error"):
            await ts.start_task_immediately("t1", "iowa_gambling", "s1", {})
        assert mock_mark.called


@pytest.mark.asyncio
async def test_task_submitter_retry_task_missing(mock_db):
    from app.services.task_execution.task_submitter import TaskSubmitter

    ts = TaskSubmitter()
    with (
        patch("app.services.task_execution.task_submitter.get_db_context", return_value=mock_db),
        patch.object(ts, "submit_to_celery", new_callable=AsyncMock) as mock_sub,
    ):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        await ts.retry_task("t1", "iowa_gambling", "s1", {})
        assert mock_sub.called


@pytest.mark.asyncio
async def test_task_strategies_detailed():
    from app.services.task_execution.task_strategies import (
        AttentionalBlinkStrategy,
        BinocularRivalryStrategy,
        ChangeBlindnessStrategy,
        IowaGamblingStrategy,
        MaskingParadigmStrategy,
        TaskStrategyRegistry,
    )

    # Iowa Gambling
    igs = IowaGamblingStrategy()
    with pytest.raises(ValueError, match="num_trials must be a positive integer"):
        igs.validate_parameters({"num_trials": 0})
    with pytest.raises(ValueError, match="Invalid deck_selection_strategy"):
        igs.validate_parameters({"deck_selection_strategy": "cheating"})

    # Masking Paradigm
    mps = MaskingParadigmStrategy()
    with pytest.raises(ValueError, match="soas must contain only numbers"):
        mps.validate_parameters({"soas": ["a"]})

    # Attentional Blink
    abs = AttentionalBlinkStrategy()
    with pytest.raises(ValueError, match="lags must be a list"):
        abs.validate_parameters({"lags": 1})
    with pytest.raises(ValueError, match="lags must contain only integers"):
        abs.validate_parameters({"lags": [1.5]})

    # Change Blindness
    cbs = ChangeBlindnessStrategy()
    with pytest.raises(ValueError, match="image_size must be a list of two integers"):
        cbs.validate_parameters({"image_size": [1]})
    with pytest.raises(ValueError, match="image_size values must be positive integers"):
        cbs.validate_parameters({"image_size": [0, 0]})

    # Binocular Rivalry
    brs = BinocularRivalryStrategy()
    with pytest.raises(ValueError, match="pattern_size must be a list of two integers"):
        brs.validate_parameters({"pattern_size": [1]})
    with pytest.raises(ValueError, match="pattern_size values must be positive integers"):
        brs.validate_parameters({"pattern_size": [-1, -1]})

    # Registry
    reg = TaskStrategyRegistry()
    with pytest.raises(ValueError, match="already registered"):
        reg.register(IowaGamblingStrategy())

    # Info
    info = igs.get_task_info()
    assert info["task_type"] == "iowa_gambling"
    assert "num_trials" in info["parameters"]

    # Singleton check
    from app.services.task_execution.task_strategies import get_task_strategy_registry

    reg1 = get_task_strategy_registry()
    reg2 = get_task_strategy_registry()
    assert reg1 is reg2


@pytest.mark.asyncio
async def test_dependency_manager_more_errors(mock_db):
    dm = DependencyManager()
    with patch(
        "app.services.task_execution.dependency_manager.get_db_context", return_value=mock_db
    ):
        # Prerequisite missing
        mock_dep = MagicMock()
        mock_dep.prerequisite_task_id = "p1"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dep]
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert dm.can_start_task("t1") is False


@pytest.mark.asyncio
async def test_task_executor_retry_error():
    executor = TaskExecutor()
    with patch.object(executor.task_submitter, "retry_task", side_effect=Exception("Retry Fail")):
        with pytest.raises(Exception, match="Retry Fail"):
            await executor.retry_task("t1", "s1", "iowa_gambling", {})


@pytest.mark.asyncio
async def test_task_executor_mapping_error():
    executor = TaskExecutor()
    mock_task = MagicMock()
    mock_task.task_type = "unknown"
    with patch.object(executor.dependency_manager, "get_ready_tasks", return_value=[mock_task]):
        await executor.check_and_start_pending_tasks("s1")  # Should just log error
