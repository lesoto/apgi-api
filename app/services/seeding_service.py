"""
Database Seeding Service

Service for populating the database with realistic test data for development and testing.
"""

import logging
import random
from datetime import timedelta, datetime
from typing import Dict, List, Any, Optional, cast
from faker import Faker

from app.database.connection import get_db_context
from app.database.models import User, Session, SessionTemplate, Task, TaskDependency
from app.services.auth_manager import AuthManager

logger = logging.getLogger(__name__)


class DatabaseSeedingService:
    """Service for seeding the database with test data."""

    def __init__(self) -> None:
        """Initialize the seeding service."""
        self.faker = Faker()
        self.faker.seed_instance(42)  # For reproducible data

    def seed_users(self, count: int = 10, include_admin: bool = True) -> List[str]:
        """
        Seed the database with test users.

        Args:
            count: Number of users to create
            include_admin: Whether to include an admin user

        Returns:
            List of created user IDs
        """
        user_ids = []

        with get_db_context() as db:
            # Create admin user if requested
            if include_admin:
                admin_user = User(
                    user_id="admin_user",
                    username="admin",
                    email="admin@apgi-system.local",
                    password_hash=AuthManager.hash_password("admin123!"),
                    roles=["admin", "researcher", "user"],
                )
                db.add(admin_user)
                user_ids.append("admin_user")
                logger.info("Created admin user")

            # Create regular users
            for i in range(count):
                user_id = f"user_{i:03d}"
                username = self.faker.user_name()
                email = self.faker.email()

                # Ensure unique username and email
                while db.query(User).filter(User.username == username).first():
                    username = self.faker.user_name()
                while db.query(User).filter(User.email == email).first():
                    email = self.faker.email()

                user = User(
                    user_id=user_id,
                    username=username,
                    email=email,
                    password_hash=AuthManager.hash_password("password123!"),
                    roles=["user", "researcher"] if random.random() < 0.3 else ["user"],
                    last_login=(
                        self.faker.date_time_between(start_date="-30d", end_date="now")
                        if random.random() < 0.7
                        else None
                    ),
                )
                db.add(user)
                user_ids.append(user_id)

            db.commit()
            logger.info(f"Created {len(user_ids)} test users")

        return user_ids

    def seed_session_templates(self, user_ids: List[str], count: int = 5) -> List[str]:
        """
        Seed the database with session templates.

        Args:
            user_ids: List of user IDs to assign templates to
            count: Number of templates to create

        Returns:
            List of created template IDs
        """
        template_ids = []
        template_configs = [
            {
                "name": "Basic Attention Task",
                "description": "Standard attentional blink experiment configuration",
                "config_path": "config/basic_attention.yaml",
                "custom_config": {
                    "experiment_type": "attentional_blink",
                    "stimulus_duration": 100,
                    "inter_stimulus_interval": 200,
                },
                "default_description": "Basic attention task for testing attentional mechanisms",
                "tags": ["attention", "experiment", "basic"],
            },
            {
                "name": "Working Memory Test",
                "description": "N-back task for working memory assessment",
                "config_path": "config/working_memory.yaml",
                "custom_config": {
                    "experiment_type": "working_memory",
                    "n_back_level": 2,
                    "trial_count": 50,
                },
                "default_description": "Working memory assessment using n-back paradigm",
                "tags": ["memory", "working_memory", "cognitive"],
            },
            {
                "name": "Decision Making Study",
                "description": "Iowa Gambling Task for decision making under uncertainty",
                "config_path": "config/decision_making.yaml",
                "custom_config": {
                    "experiment_type": "decision_making",
                    "deck_count": 4,
                    "trial_limit": 100,
                },
                "default_description": "Decision making study with risk and reward assessment",
                "tags": ["decision_making", "risk", "reward"],
            },
            {
                "name": "Visual Search Task",
                "description": "Feature search vs. conjunction search paradigms",
                "config_path": "config/visual_search.yaml",
                "custom_config": {
                    "experiment_type": "visual_search",
                    "target_type": "conjunction",
                    "distractor_count": 15,
                },
                "default_description": "Visual search task examining search efficiency",
                "tags": ["vision", "search", "perception"],
            },
            {
                "name": "Emotion Recognition",
                "description": "Facial emotion recognition with varying intensities",
                "config_path": "config/emotion_recognition.yaml",
                "custom_config": {
                    "experiment_type": "emotion_recognition",
                    "emotions": ["happy", "sad", "angry", "fear", "surprise"],
                    "intensity_levels": [0.3, 0.6, 0.9],
                },
                "default_description": "Emotion recognition task with facial expressions",
                "tags": ["emotion", "face", "recognition"],
            },
        ]

        with get_db_context() as db:
            for i in range(min(count, len(template_configs))):
                config = template_configs[i]
                template_id = f"template_{i:03d}"
                user_id = random.choice(user_ids)

                template = SessionTemplate(
                    template_id=template_id,
                    user_id=user_id,
                    name=config["name"],
                    description=config["description"],
                    config_path=config["config_path"],
                    custom_config=config["custom_config"],
                    default_description=config["default_description"],
                    tags=config["tags"],
                    is_public=random.random() < 0.4,  # 40% chance of being public
                )
                db.add(template)
                template_ids.append(template_id)

            db.commit()
            logger.info(f"Created {len(template_ids)} session templates")

        return template_ids

    def seed_sessions(
        self, user_ids: List[str], template_ids: Optional[List[str]] = None, count: int = 20
    ) -> List[str]:
        """
        Seed the database with test sessions.

        Args:
            user_ids: List of user IDs
            template_ids: Optional list of template IDs
            count: Number of sessions to create

        Returns:
            List of created session IDs
        """
        session_ids = []
        session_states = ["created", "running", "paused", "stopped", "completed", "error"]

        with get_db_context() as db:
            for i in range(count):
                session_id = f"session_{i:03d}"
                user_id = random.choice(user_ids)

                # Sometimes use a template
                template_id = (
                    random.choice(template_ids) if template_ids and random.random() < 0.6 else None
                )

                # Generate session config
                if template_id:
                    # Use template-based config
                    config = {
                        "config_path": f"config/template_{template_id}.yaml",
                        "custom_config": {
                            "session_id": session_id,
                            "user_id": user_id,
                            "trial_count": random.randint(10, 100),
                        },
                        "description": f"Session created from template {template_id}",
                    }
                else:
                    # Use custom config
                    config = {
                        "config_path": "config/custom_session.yaml",
                        "custom_config": {
                            "experiment_type": random.choice(
                                ["attention", "memory", "decision", "vision"]
                            ),
                            "trial_count": random.randint(20, 200),
                            "duration_minutes": random.randint(5, 60),
                        },
                        "description": self.faker.sentence(),
                    }

                # Random state with bias toward completed
                state = random.choices(session_states, weights=[0.1, 0.1, 0.1, 0.1, 0.5, 0.1])[0]

                # Generate created_at datetime
                created_at_dt = self.faker.date_time_between(start_date="-90d", end_date="-1d")
                session = Session(
                    session_id=session_id,
                    user_id=user_id,
                    template_id=template_id,
                    config=config,
                    state=state,
                    description=config["description"],
                    tags=random.sample(
                        ["experiment", "test", "development", "research"], random.randint(1, 3)
                    ),
                    created_at=created_at_dt,
                )

                # Set updated_at based on state
                if state in ["running", "paused"]:
                    session.updated_at = self.faker.date_time_between(  # type: ignore
                        start_date=created_at_dt, end_date=created_at_dt + timedelta(minutes=30)
                    )
                elif state in ["stopped", "completed", "error"]:
                    session.updated_at = self.faker.date_time_between(  # type: ignore
                        start_date=created_at_dt, end_date=created_at_dt + timedelta(minutes=240)
                    )

                db.add(session)
                session_ids.append(session_id)

            db.commit()
            logger.info(f"Created {len(session_ids)} test sessions")
            return session_ids

    def seed_tasks(self, session_ids: List[str], count: int = 50) -> List[str]:
        """
        Seed the database with test tasks.

        Args:
            session_ids: List of session IDs to assign tasks to
            count: Number of tasks to create

        Returns:
            List of created task IDs
        """
        task_ids = []
        task_types = [
            "attentional_blink",
            "working_memory",
            "decision_making",
            "visual_search",
            "emotion_recognition",
        ]
        task_statuses = ["pending", "running", "completed", "failed"]

        with get_db_context() as db:
            for i in range(count):
                task_id = f"task_{i:03d}"
                session_id = random.choice(session_ids)

                task_type = random.choice(task_types)
                status = random.choices(task_statuses, weights=[0.2, 0.2, 0.5, 0.1])[0]

                # Generate parameters based on task type
                parameters = self._generate_task_parameters(task_type)

                task = Task(
                    task_id=task_id,
                    session_id=session_id,
                    task_type=task_type,
                    parameters=parameters,
                    status=status,
                    priority=random.randint(1, 10),
                    progress=random.randint(0, 100) if status in ["running", "completed"] else None,
                    result_data=(
                        self._generate_task_result(task_type) if status == "completed" else None
                    ),
                    error_message=self.faker.sentence() if status == "failed" else None,
                    created_at=self.faker.date_time_between(start_date="-30d", end_date="-1d"),
                )

                # Set timing based on status
                created_at_dt = cast(datetime, task.created_at)
                if status == "running":
                    start_dt = created_at_dt
                    end_dt = created_at_dt + timedelta(seconds=300)
                    dt = self.faker.date_time_between(start_date=start_dt, end_date=end_dt)
                    task.started_at = dt  # type: ignore[assignment]
                elif status in ["completed", "failed"]:
                    start_dt = created_at_dt
                    end_dt = created_at_dt + timedelta(seconds=300)
                    started_at_dt = self.faker.date_time_between(
                        start_date=start_dt, end_date=end_dt
                    )
                    task.started_at = started_at_dt  # type: ignore[assignment]
                    start_dt2 = started_at_dt
                    end_dt2 = started_at_dt + timedelta(minutes=30)
                    completed_dt = self.faker.date_time_between(
                        start_date=start_dt2, end_date=end_dt2
                    )
                    task.completed_at = completed_dt  # type: ignore[assignment]

                db.add(task)
                task_ids.append(task_id)

            db.commit()
            logger.info(f"Created {len(task_ids)} test tasks")

        return task_ids

    def seed_task_dependencies(self, task_ids: List[str], count: int = 15) -> List[int]:
        """
        Seed the database with task dependencies.

        Args:
            task_ids: List of task IDs to create dependencies between
            count: Number of dependencies to create

        Returns:
            List of created dependency IDs
        """
        dependency_ids = []

        with get_db_context() as db:
            for i in range(min(count, len(task_ids) - 1)):
                # Select two different tasks
                dependent_task = random.choice(task_ids)
                prerequisite_task = random.choice([t for t in task_ids if t != dependent_task])

                # Check if dependency already exists
                existing = (
                    db.query(TaskDependency)
                    .filter(
                        TaskDependency.dependent_task_id == dependent_task,
                        TaskDependency.prerequisite_task_id == prerequisite_task,
                    )
                    .first()
                )

                if not existing:
                    dependency = TaskDependency(
                        dependent_task_id=dependent_task,
                        prerequisite_task_id=prerequisite_task,
                        dependency_type=random.choice(["completion", "success"]),
                    )
                    db.add(dependency)
                    dependency_ids.append(i)

            db.commit()
            logger.info(f"Created {len(dependency_ids)} task dependencies")

        return dependency_ids

    def _generate_task_parameters(self, task_type: str) -> Dict[str, Any]:
        """Generate realistic parameters for a task type."""
        if task_type == "attentional_blink":
            return {
                "stream_length": random.randint(10, 20),
                "target_position": random.randint(3, 8),
                "distractor_count": random.randint(1, 3),
                "stimulus_duration_ms": random.randint(50, 150),
            }
        elif task_type == "working_memory":
            return {
                "n_back_level": random.randint(1, 3),
                "sequence_length": random.randint(20, 50),
                "stimulus_types": random.choice(["letters", "numbers", "shapes"]),
            }
        elif task_type == "decision_making":
            return {
                "deck_count": 4,
                "trials_per_block": random.randint(20, 40),
                "feedback_delay_ms": random.randint(500, 2000),
            }
        elif task_type == "visual_search":
            return {
                "target_type": random.choice(["feature", "conjunction"]),
                "set_size": random.choice([8, 16, 32]),
                "target_present": random.choice([True, False]),
            }
        elif task_type == "emotion_recognition":
            return {
                "emotion": random.choice(["happy", "sad", "angry", "fear"]),
                "intensity": random.choice([0.3, 0.6, 0.9]),
                "presentation_time_ms": random.randint(500, 2000),
            }
        else:
            return {"custom_parameter": random.randint(1, 100)}

    def _generate_task_result(self, task_type: str) -> Dict[str, Any]:
        """Generate realistic results for a completed task."""
        if task_type == "attentional_blink":
            return {
                "accuracy": random.uniform(0.6, 0.95),
                "reaction_time_ms": random.randint(300, 800),
                "blink_effect_detected": random.choice([True, False]),
            }
        elif task_type == "working_memory":
            return {
                "accuracy": random.uniform(0.7, 0.98),
                "false_positives": random.randint(0, 5),
                "false_negatives": random.randint(0, 3),
            }
        elif task_type == "decision_making":
            return {
                "total_score": random.randint(-500, 2000),
                "good_deck_preference": random.uniform(0.4, 0.9),
                "learning_rate": random.uniform(0.1, 0.8),
            }
        elif task_type == "visual_search":
            return {
                "search_time_ms": random.randint(200, 2000),
                "accuracy": random.uniform(0.8, 1.0),
                "slope_coefficient": random.uniform(10, 50),
            }
        elif task_type == "emotion_recognition":
            return {
                "accuracy": random.uniform(0.7, 0.95),
                "reaction_time_ms": random.randint(400, 1200),
                "confidence_rating": random.uniform(0.5, 1.0),
            }
        else:
            return {"result_value": random.randint(10, 100)}

    def clear_all_data(self) -> Dict[str, int]:
        """
            Clear all seeded test data from the database.

        Returns:
            Dictionary with counts of deleted records
        """
        deleted_counts = {}

        with get_db_context() as db:
            # Delete in order to respect foreign keys
            deleted_counts["task_dependencies"] = db.query(TaskDependency).delete()
            deleted_counts["tasks"] = db.query(Task).filter(Task.task_id.like("task_%")).delete()
            deleted_counts["sessions"] = (
                db.query(Session).filter(Session.session_id.like("session_%")).delete()
            )
            deleted_counts["session_templates"] = (
                db.query(SessionTemplate)
                .filter(SessionTemplate.template_id.like("template_%"))
                .delete()
            )
            deleted_counts["users"] = db.query(User).filter(User.user_id.like("user_%")).delete()

            db.commit()

        logger.info(f"Cleared test data: {deleted_counts}")
        return deleted_counts

    def seed_all(
        self,
        user_count: int = 10,
        template_count: int = 5,
        session_count: int = 20,
        task_count: int = 50,
    ) -> Dict[str, Any]:
        """
        Seed the database with a complete set of test data.

        Args:
            user_count: Number of users to create
            template_count: Number of templates to create
            session_count: Number of sessions to create
            task_count: Number of tasks to create

        Returns:
            Dictionary with summary of created data
        """
        logger.info("Starting complete database seeding")

        # Seed users
        user_ids = self.seed_users(user_count)

        # Seed templates
        template_ids = self.seed_session_templates(user_ids, template_count)

        # Seed sessions
        session_ids = self.seed_sessions(user_ids, template_ids, session_count)

        # Seed tasks
        task_ids = self.seed_tasks(session_ids, task_count)

        # Seed dependencies
        dependency_count = self.seed_task_dependencies(task_ids, min(15, len(task_ids) // 3))

        result = {
            "users_created": len(user_ids),
            "templates_created": len(template_ids),
            "sessions_created": len(session_ids),
            "tasks_created": len(task_ids),
            "dependencies_created": dependency_count,
            "user_ids": user_ids[:5],  # Show first 5 for reference
            "template_ids": template_ids,
            "session_ids": session_ids[:5],
            "task_ids": task_ids[:5],
        }

        logger.info(f"Database seeding completed: {result}")
        return result
