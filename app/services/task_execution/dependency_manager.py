"""
Dependency Manager Module

Handles task dependency graph management including cycle detection,
prerequisite checking, and dependency-based task scheduling.
"""

import logging
from typing import Dict, List, Optional, Set

from app.database.connection import get_db_context
from app.database.models import Task, TaskDependency, TaskStatus

logger = logging.getLogger(__name__)


class DependencyManager:
    """
    Manages task dependencies and scheduling logic.

    Provides methods for:
    - Cycle detection in dependency graphs
    - Checking if prerequisites are satisfied
    - Managing task dependency relationships
    """

    def __init__(self) -> None:
        """Initialize the dependency manager."""
        self._cycle_check_cache: Dict[str, bool] = {}

    def can_start_task(self, task_id: str) -> bool:
        """
        Check if a task can be started based on its dependencies.

        Args:
            task_id: Task identifier

        Returns:
            True if all dependencies are satisfied, False otherwise
        """
        try:
            with get_db_context() as db:
                # Get all dependencies for this task
                dependencies = (
                    db.query(TaskDependency)
                    .filter(TaskDependency.dependent_task_id == task_id)
                    .all()
                )

                for dep in dependencies:
                    prerequisite_task = (
                        db.query(Task).filter(Task.task_id == dep.prerequisite_task_id).first()
                    )

                    if not prerequisite_task:
                        logger.error(
                            f"Prerequisite task {dep.prerequisite_task_id} not found for task {task_id}"
                        )
                        return False

                    # Check if prerequisite is completed (or failed for failure dependencies)
                    if dep.dependency_type == "completion":
                        if prerequisite_task.status != TaskStatus.COMPLETED.value:
                            return False
                    elif dep.dependency_type == "success":
                        if prerequisite_task.status != TaskStatus.COMPLETED.value:
                            return False
                    elif dep.dependency_type == "failure":
                        if prerequisite_task.status != TaskStatus.FAILED.value:
                            return False

                return True
        except Exception as e:
            logger.error(f"Error checking if task {task_id} can start: {e}")
            return False

    def has_cycle(
        self,
        task_id: str,
        visited: Optional[Set[str]] = None,
        rec_stack: Optional[Set[str]] = None,
    ) -> bool:
        """
        Detect cycles in task dependency graph using DFS.

        Args:
            task_id: Task identifier to check
            visited: Set of visited tasks
            rec_stack: Recursion stack for cycle detection

        Returns:
            True if cycle detected, False otherwise
        """
        try:
            if visited is None:
                visited = set()
            if rec_stack is None:
                rec_stack = set()

            visited.add(task_id)
            rec_stack.add(task_id)

            with get_db_context() as db:
                dependencies = (
                    db.query(TaskDependency)
                    .filter(TaskDependency.dependent_task_id == task_id)
                    .all()
                )

                for dep in dependencies:
                    prereq_id = str(dep.prerequisite_task_id)
                    if prereq_id not in visited:
                        if self.has_cycle(prereq_id, visited, rec_stack):
                            return True
                    elif prereq_id in rec_stack:
                        return True

            rec_stack.remove(task_id)
            return False
        except Exception as e:
            logger.error(f"Error checking for cycle at task {task_id}: {e}")
            return True

    def get_dependency_chain(self, task_id: str) -> List[str]:
        """
        Get the full dependency chain for a task.

        Args:
            task_id: Task identifier

        Returns:
            List of prerequisite task IDs in dependency order
        """
        chain: List[str] = []
        visited: Set[str] = set()

        def traverse(current_task_id: str) -> None:
            if current_task_id in visited:
                return
            visited.add(current_task_id)

            try:
                with get_db_context() as db:
                    dependencies = (
                        db.query(TaskDependency)
                        .filter(TaskDependency.dependent_task_id == current_task_id)
                        .all()
                    )

                    for dep in dependencies:
                        prereq_id = str(dep.prerequisite_task_id)
                        traverse(prereq_id)
                        if prereq_id not in chain:
                            chain.append(prereq_id)
            except Exception as e:
                logger.error(f"Error traversing dependency chain for task {current_task_id}: {e}")

        try:
            traverse(task_id)
        except Exception as e:
            logger.error(f"Error getting dependency chain for task {task_id}: {e}")
            return []

        return chain

    def get_dependent_tasks(self, task_id: str) -> List[str]:
        """
        Get all tasks that depend on the given task.

        Args:
            task_id: Task identifier

        Returns:
            List of dependent task IDs
        """
        try:
            with get_db_context() as db:
                dependents = (
                    db.query(TaskDependency)
                    .filter(TaskDependency.prerequisite_task_id == task_id)
                    .all()
                )
                return [str(dep.dependent_task_id) for dep in dependents]
        except Exception as e:
            logger.error(f"Error getting dependent tasks for task {task_id}: {e}")
            return []

    def validate_new_dependency(self, dependent_task_id: str, prerequisite_task_id: str) -> bool:
        """
        Validate that adding a new dependency wouldn't create a cycle.

        Args:
            dependent_task_id: Task that would depend on the prerequisite
            prerequisite_task_id: Task that must complete first

        Returns:
            True if the dependency is valid (no cycle)

        Raises:
            ValueError: If the dependency would create a cycle
        """
        try:
            # Check if prerequisite would create a cycle
            # by checking if dependent is in prerequisite's chain
            chain = self.get_dependency_chain(prerequisite_task_id)
            if dependent_task_id in chain:
                raise ValueError(
                    f"Adding dependency from {dependent_task_id} to {prerequisite_task_id} "
                    f"would create a cycle"
                )

            return True
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Error validating dependency from {dependent_task_id} to {prerequisite_task_id}: {e}"
            )
            raise ValueError(f"Failed to validate dependency: {e}")

    def get_ready_tasks(self, session_id: str) -> List[Task]:
        """
        Get all pending tasks in a session that can now be started.

        Args:
            session_id: Session identifier

        Returns:
            List of tasks ready to start (ordered by priority)
        """
        try:
            with get_db_context() as db:
                pending_tasks = (
                    db.query(Task)
                    .filter(Task.session_id == session_id, Task.status == TaskStatus.PENDING.value)
                    .order_by(Task.priority)
                    .all()
                )

                ready_tasks = []
                for task in pending_tasks:
                    try:
                        if self.can_start_task(str(task.task_id)):
                            ready_tasks.append(task)
                    except Exception as e:
                        logger.error(f"Error checking if task {task.task_id} can start: {e}")
                        continue

                return ready_tasks
        except Exception as e:
            logger.error(f"Error getting ready tasks for session {session_id}: {e}")
            return []
