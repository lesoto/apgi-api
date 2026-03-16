"""
Session Manager

Manages APGI simulation sessions with Redis caching and database persistence.
"""

import asyncio
import json
import logging
import re
import uuid
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple, cast
from collections import OrderedDict

import redis.asyncio as redis
from sqlalchemy import select, func

from app.database.models import Session as SessionModel
from app.database.models import SessionState
from app.database.models import SessionTemplate
from app.models.schemas import SessionCreateRequest
from app.config import settings
from app import APGISystem  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# UUID validation pattern
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def validate_session_id(session_id: str) -> str:
    """
    Validate session ID format to prevent SQL injection.

    Args:
        session_id: Session identifier to validate

    Returns:
        Validated session ID

    Raises:
        ValueError: If session ID is not a valid UUID
    """
    if not session_id or not isinstance(session_id, str):
        raise ValueError("Session ID must be a non-empty string")

    if not UUID_PATTERN.match(session_id):
        raise ValueError(f"Invalid session ID format: {session_id}")

    return session_id


class SessionLifecycleState(str, Enum):
    """Session lifecycle states."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


# State transition table
ALLOWED_TRANSITIONS = {
    SessionLifecycleState.CREATED: [
        SessionLifecycleState.RUNNING,
        SessionLifecycleState.STOPPED,
        SessionLifecycleState.ERROR,
    ],
    SessionLifecycleState.RUNNING: [
        SessionLifecycleState.PAUSED,
        SessionLifecycleState.STOPPED,
        SessionLifecycleState.ERROR,
    ],
    SessionLifecycleState.PAUSED: [
        SessionLifecycleState.RUNNING,
        SessionLifecycleState.STOPPED,
        SessionLifecycleState.ERROR,
    ],
    SessionLifecycleState.STOPPED: [SessionLifecycleState.CREATED, SessionLifecycleState.ERROR],
    SessionLifecycleState.ERROR: [SessionLifecycleState.CREATED],
}


class SimulationSession:
    """
    Represents a single APGI simulation instance with async interface.

    Wraps APGISystem with thread-safe locking for concurrent access.
    """

    def __init__(self, session_id: str, config: Dict[str, Any]):
        """
        Initialize simulation session.

        Args:
            session_id: Unique session identifier
            config: Session configuration dictionary
        """
        self.session_id = session_id
        self.config = config
        self.state: SessionLifecycleState = SessionLifecycleState.CREATED
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

        # Thread-safe lock for concurrent access
        self.lock = asyncio.Lock()

        # Initialize APGI system
        config_path = config.get("config_path")
        self.apgi_system = APGISystem(config_path=config_path)

        # Apply custom config overrides if provided
        if "custom_config" in config and config["custom_config"]:
            self._apply_custom_config(config["custom_config"])

        # Simulation control
        self.is_running = False
        self.is_paused = False

        # Store state snapshot for pause/resume
        self._paused_state: Optional[Dict[str, Any]] = None

        logger.info(f"SimulationSession {session_id} initialized")

    def _can_transition_to(self, new_state: SessionLifecycleState) -> bool:
        """Check if transition to new_state is allowed from current state."""
        return new_state in ALLOWED_TRANSITIONS.get(self.state, [])

    def _apply_custom_config(self, custom_config: Dict[str, Any]):
        """Apply custom configuration overrides to APGI system."""

        # Deep merge custom config into system config
        def deep_merge(base: dict, override: dict):
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value

        deep_merge(self.apgi_system.config, custom_config)

        # Reinitialize subsystems with new config
        self.apgi_system._initialize_subsystems()

    def _capture_state(self) -> Dict[str, Any]:
        """Capture complete system state for pause/resume."""
        state = cast(Dict[str, Any], self.apgi_system.get_state())

        # Explicitly capture subsystem states for full restoration
        state["allostasis"] = self.apgi_system.allostasis.save_state()
        state["body"] = self.apgi_system.body.save_state()
        state["precision"] = self.apgi_system.precision.save_state()
        state["workspace"] = self.apgi_system.workspace.save_state()
        state["self_model"] = self.apgi_system.self_model.save_state()
        state["ignition"] = self.apgi_system.ignition.save_state()
        return state

    def _restore_state(self, state: Dict[str, Any]):
        """Restore system state from snapshot."""
        # Restore complete system state from snapshot
        if not state:
            logger.warning(f"Session {self.session_id} attempting to restore empty state")
            return

        # Restore basic simulation properties
        self.apgi_system.time = state.get("time", 0.0)
        self.apgi_system.history = state.get("history", {})

        # Restore subsystem states if available
        if "allostasis" in state:
            self.apgi_system.allostasis.load_state(state["allostasis"])

        if "body" in state:
            self.apgi_system.body.load_state(state["body"])

        if "precision" in state:
            self.apgi_system.precision.load_state(state["precision"])

        if "workspace" in state:
            self.apgi_system.workspace.load_state(state["workspace"])

        if "self_model" in state:
            self.apgi_system.self_model.load_state(state["self_model"])

        if "ignition" in state:
            self.apgi_system.ignition.load_state(state["ignition"])

        # Restore any other dynamic attributes from state
        for key, value in state.items():
            if (
                hasattr(self.apgi_system, key)
                and key
                not in [
                    "time",
                    "history",
                    "allostasis",
                    "body",
                    "precision",
                    "workspace",
                    "self_model",
                    "ignition",
                ]
                and key.isidentifier()
            ):
                setattr(self.apgi_system, key, value)

        logger.info(f"Session {self.session_id} full state restored")

    async def start(self) -> Dict[str, Any]:
        """
        Start simulation.

        Returns:
            Dict with status information
        """
        async with self.lock:
            if not self._can_transition_to(SessionLifecycleState.RUNNING):
                raise ValueError(f"Cannot start session in state {self.state.value}")

            if self.state == SessionLifecycleState.PAUSED:
                # Resume from paused state
                if self._paused_state:
                    self._restore_state(self._paused_state)
                    self._paused_state = None

            self.is_running = True
            self.is_paused = False
            self.state = SessionLifecycleState.RUNNING
            self.updated_at = datetime.now(timezone.utc)

            logger.info(f"Session {self.session_id} started")

            return {
                "session_id": self.session_id,
                "status": self.state.value,
                "started_at": self.updated_at.isoformat() + "Z",
            }

    async def pause(self) -> Dict[str, Any]:
        """
        Pause simulation while preserving current state.

        Returns:
            Dict with status information
        """
        async with self.lock:
            if not self._can_transition_to(SessionLifecycleState.PAUSED):
                raise ValueError(f"Cannot pause session in state {self.state.value}")

            # Capture current state
            self._paused_state = self._capture_state()

            self.is_running = False
            self.is_paused = True
            self.state = SessionLifecycleState.PAUSED
            self.updated_at = datetime.now(timezone.utc)

            logger.info(f"Session {self.session_id} paused")

            return {
                "session_id": self.session_id,
                "status": self.state.value,
                "paused_at": self.updated_at.isoformat() + "Z",
            }

    async def stop(self) -> Dict[str, Any]:
        """
        Stop simulation.

        Returns:
            Dict with status information
        """
        async with self.lock:
            if not self._can_transition_to(SessionLifecycleState.STOPPED):
                raise ValueError(f"Cannot stop session in state {self.state.value}")

            self.is_running = False
            self.is_paused = False
            self.state = SessionLifecycleState.STOPPED
            self.updated_at = datetime.now(timezone.utc)

            logger.info(f"Session {self.session_id} stopped")

            return {
                "session_id": self.session_id,
                "status": self.state.value,
                "stopped_at": self.updated_at.isoformat() + "Z",
            }

    async def reset(self) -> Dict[str, Any]:
        """
        Reset simulation to initial conditions.

        Returns:
            Dict with status information
        """
        async with self.lock:
            if not self._can_transition_to(SessionLifecycleState.CREATED):
                raise ValueError(f"Cannot reset session in state {self.state.value}")

            # Reset APGI system
            self.apgi_system.reset()

            # Clear paused state
            self._paused_state = None

            # Reset control flags
            self.is_running = False
            self.is_paused = False
            self.state = SessionLifecycleState.CREATED
            self.updated_at = datetime.now(timezone.utc)

            logger.info(f"Session {self.session_id} reset")

            return {
                "session_id": self.session_id,
                "status": self.state.value,
                "reset_at": self.updated_at.isoformat() + "Z",
            }

    async def step(self, extero_input: Any) -> Dict[str, Any]:
        """
        Execute single simulation step.

        Args:
            extero_input: Exteroceptive input for this step

        Returns:
            System state after step
        """
        async with self.lock:
            if not self.is_running:
                raise ValueError(f"Session {self.session_id} is not running")

            # Execute step in APGI system
            state = self.apgi_system.step(extero_input)
            self.updated_at = datetime.now(timezone.utc)

            # Store historical ignition data for accurate event annotation
            history = state.setdefault("history", {})
            ignition_data = state.get("ignition", {})
            ignition_signals = history.setdefault("ignition_signals", [])
            ignition_signals.append(ignition_data.get("total_signal", 0.0))
            ignition_thresholds = history.setdefault("ignition_thresholds", [])
            ignition_thresholds.append(ignition_data.get("threshold", 2.0))

            return cast(Dict[str, Any], state)

    async def get_state(self) -> Dict[str, Any]:
        """
        Get current system state.

        Returns:
            Complete system state
        """
        async with self.lock:
            state = self.apgi_system.get_state()

            # Add session metadata
            state["session_metadata"] = {
                "session_id": self.session_id,
                "state": self.state.value,
                "is_running": self.is_running,
                "is_paused": self.is_paused,
                "created_at": self.created_at.isoformat() + "Z",
                "updated_at": self.updated_at.isoformat() + "Z",
            }

            return cast(Dict[str, Any], state)

        return state


class SessionManager:
    """
    Manages APGI simulation sessions with Redis caching and database persistence.

    Handles session lifecycle, state caching, and resource cleanup.
    """

    def __init__(self, redis_client: redis.Redis, db_session_factory):
        """
        Initialize session manager.

        Args:
            redis_client: Async Redis client for caching
            db_session_factory: SQLAlchemy session factory for database access
        """
        self.redis = redis_client
        self.db_session_factory = db_session_factory

        # In-memory session cache with TTL and size limits
        self.session_cache_max_size = 1000  # Maximum number of sessions to cache
        self.session_ttl_seconds = 3600  # 1 hour TTL for cached sessions
        self.sessions: OrderedDict[
            str, Tuple[SimulationSession, float]
        ] = OrderedDict()  # (session, last_access_time)

        # Lock for session cache access
        self.cache_lock = asyncio.Lock()

        logger.info("SessionManager initialized")

    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions from cache (called within lock)."""
        current_time = time.time()
        expired_keys = []

        for session_id, (_, last_access) in self.sessions.items():
            if current_time - last_access > self.session_ttl_seconds:
                expired_keys.append(session_id)

        for key in expired_keys:
            del self.sessions[key]
            logger.debug(f"Removed expired session {key} from cache")

    async def _persist_session(self, session_id: str):
        """Persist the full session state to database."""
        if session_id not in self.sessions:
            return

        session, _ = self.sessions[session_id]

        try:
            state = await session.get_state()

            # Remove session metadata before saving
            if "session_metadata" in state:
                del state["session_metadata"]

            # Update database
            db_session = self.db_session_factory()
            try:
                stmt = select(SessionModel).where(SessionModel.session_id == session_id)
                result = db_session.execute(stmt)
                db_model = result.scalar_one_or_none()

                if db_model:
                    db_model.full_state = state
                    db_model.updated_at = datetime.now(timezone.utc)
                    db_session.commit()
                    logger.debug(f"Persisted full state for session {session_id}")
            except Exception as e:
                db_session.rollback()
                logger.error(f"Failed to persist session state for {session_id}: {e}")
            finally:
                db_session.close()

        except Exception as e:
            logger.error(f"Failed to get state for session {session_id}: {e}")

    async def _evict_oldest_sessions(self) -> None:
        """Remove oldest sessions to maintain cache size limit (called within lock)."""
        while len(self.sessions) > self.session_cache_max_size:
            oldest_key = next(iter(self.sessions))  # OrderedDict preserves insertion order

            # Persist session state before eviction
            try:
                await self._persist_session(oldest_key)
            except Exception as e:
                logger.warning(f"Failed to persist session {oldest_key} before eviction: {e}")

            del self.sessions[oldest_key]
            logger.debug(f"Evicted oldest session {oldest_key} from cache (state persisted)")

    async def create_session(
        self, request: SessionCreateRequest, user_id: str = "default_user"
    ) -> str:
        """
        Create new simulation session.

        Args:
            request: Session creation request
            user_id: User identifier

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        # Check per-user session count cap
        db_session = self.db_session_factory()
        try:
            session_count = db_session.scalar(
                select(func.count(SessionModel.session_id))
                .where(SessionModel.user_id == user_id)
                .where(SessionModel.is_deleted.is_(False))
            )
            if session_count >= settings.max_sessions_per_user:
                raise ValueError(
                    f"User {user_id} has reached the maximum number of sessions ({settings.max_sessions_per_user}). "
                    "Please delete some existing sessions before creating new ones."
                )
        finally:
            db_session.close()

        # Prepare configuration
        config = {}

        # Handle template-based session creation
        template_id = None
        if request.template_id:
            # Load template from database
            db_session = self.db_session_factory()
            try:
                stmt = select(SessionTemplate).where(
                    SessionTemplate.template_id == request.template_id
                )
                result = db_session.execute(stmt)
                template = result.scalar_one_or_none()

                if not template:
                    raise ValueError(f"Template {request.template_id} not found")

                # Check if user has access to template (public or owned by user)
                if not template.is_public and template.user_id != user_id:
                    raise ValueError(
                        f"Template {request.template_id} is not accessible to user {user_id}"
                    )

                # Use template configuration as base
                config = {
                    "config_path": template.config_path,
                    "custom_config": template.custom_config or {},
                    "description": request.description or template.default_description,
                }
                template_id = template.template_id

            finally:
                db_session.close()

        # Apply request overrides
        if request.config_path:
            config["config_path"] = request.config_path
        if request.custom_config:
            # Merge custom config with existing (request overrides template)
            existing_custom = config.get("custom_config", {})
            existing_custom.update(request.custom_config)
            config["custom_config"] = existing_custom
        if request.description and not template_id:
            config["description"] = request.description

        # Ensure we have valid configuration
        if not config.get("config_path") and not config.get("custom_config"):
            raise ValueError("Either config_path or custom_config must be provided")

        # Create simulation session
        sim_session = SimulationSession(session_id, config)

        # Atomic cache + database operation
        async with self.cache_lock:
            # Cleanup expired sessions before adding new one
            self._cleanup_expired_sessions()

            # First try to persist to database
            db_session = self.db_session_factory()
            try:
                db_model = SessionModel(
                    session_id=session_id,
                    user_id=user_id,
                    template_id=template_id,
                    config=config,
                    state=SessionState.CREATED.value,
                    description=config.get("description"),
                    tags=[],
                )
                db_session.add(db_model)
                db_session.commit()

                # Only add to cache after successful DB write
                self.sessions[session_id] = (sim_session, time.time())  # Store with timestamp
                logger.info(f"Session {session_id} created and persisted")

                if template_id:
                    logger.info(f"Session {session_id} created from template {template_id}")

            except Exception as e:
                db_session.rollback()
                logger.error(f"Failed to persist session {session_id}: {e}")
                # Don't add to cache if DB write failed
                raise
            finally:
                db_session.close()

            # Enforce cache size limit
            await self._evict_oldest_sessions()

        # Cache session metadata in Redis
        await self._cache_session_metadata(session_id, sim_session, user_id)

        return session_id

    async def get_session(
        self, session_id: str, user_id: Optional[str] = None
    ) -> SimulationSession:
        """
        Retrieve existing session.

        Args:
            session_id: Session identifier
            user_id: Optional user ID to validate ownership

        Returns:
            SimulationSession instance

        Raises:
            ValueError: If session not found, invalid session ID, or access denied
        """
        # Validate session ID format
        validate_session_id(session_id)

        # Check memory cache first
        async with self.cache_lock:
            # Cleanup expired sessions
            self._cleanup_expired_sessions()

            if session_id in self.sessions:
                session_data, last_access = self.sessions[session_id]
                # Update access time and move to end (LRU)
                self.sessions.move_to_end(session_id)
                self.sessions[session_id] = (session_data, time.time())
                return session_data

        # Check Redis cache
        cached_data = await self.redis.get(f"session:{session_id}")
        if cached_data:
            # Reconstruct session from cache
            metadata = json.loads(cached_data)

            # Validate ownership if user_id is provided
            if user_id and metadata.get("user_id") != user_id:
                # Cache hit but wrong owner - don't reveal, fall through to DB check
                logger.warning(f"Cache hit for session {session_id} but ownership mismatch")
            else:
                sim_session = SimulationSession(session_id, metadata["config"])
                sim_session.state = SessionLifecycleState(metadata["state"])
                sim_session.created_at = datetime.fromisoformat(
                    metadata["created_at"].replace("Z", "+00:00")
                )
                sim_session.updated_at = datetime.fromisoformat(
                    metadata["updated_at"].replace("Z", "+00:00")
                )

                # Add to memory cache
                async with self.cache_lock:
                    self.sessions[session_id] = (sim_session, time.time())  # Store with timestamp

                return sim_session

        # Load from database
        db_session = self.db_session_factory()
        try:
            stmt = select(SessionModel).where(SessionModel.session_id == session_id)

            # Add user_id filter if provided for ownership validation
            if user_id:
                stmt = stmt.where(SessionModel.user_id == user_id)

            stmt = stmt.where(SessionModel.is_deleted.is_(False))

            result = db_session.execute(stmt)
            db_model = result.scalar_one_or_none()

            if not db_model:
                if user_id:
                    # Don't reveal if session exists or not for security
                    raise ValueError(f"Session {session_id} not found or access denied")
                else:
                    raise ValueError(f"Session {session_id} not found")

            # Reconstruct session
            sim_session = SimulationSession(session_id, db_model.config)
            sim_session.state = SessionLifecycleState(db_model.state)
            sim_session.created_at = db_model.created_at
            sim_session.updated_at = db_model.updated_at

            # Restore full state if persisted
            if db_model.full_state:
                sim_session._restore_state(db_model.full_state)
                logger.debug(f"Restored full state for session {session_id}")

            # Add to caches
            async with self.cache_lock:
                self.sessions[session_id] = (sim_session, time.time())  # Store with timestamp

            await self._cache_session_metadata(session_id, sim_session, db_model.user_id)

            logger.info(f"Session {session_id} loaded from database")

            return sim_session
        finally:
            db_session.close()

    async def delete_session(self, session_id: str):
        """
        Clean up session resources.

        Args:
            session_id: Session identifier

        Raises:
            ValueError: If session ID is invalid
        """
        # Validate session ID format
        validate_session_id(session_id)
        # Remove from memory cache
        async with self.cache_lock:
            if session_id in self.sessions:
                del self.sessions[session_id]

        # Remove from Redis cache
        await self.redis.delete(f"session:{session_id}")

        # Delete from database
        db_session = self.db_session_factory()
        try:
            stmt = select(SessionModel).where(SessionModel.session_id == session_id)
            result = db_session.execute(stmt)
            db_model = result.scalar_one_or_none()

            if db_model:
                db_model.is_deleted = True
                db_model.updated_at = datetime.now(timezone.utc)
                db_session.commit()
                logger.info(f"Session {session_id} soft deleted from database")
        except Exception as e:
            db_session.rollback()
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise
        finally:
            db_session.close()

        logger.info(f"Session {session_id} cleaned up")

    async def update_session_state(
        self, session_id: str, new_state: SessionLifecycleState, user_id: Optional[str] = None
    ):
        """
        Update session state in database and cache atomically.

        Uses SELECT FOR UPDATE to prevent race conditions when multiple
        concurrent requests try to update the same session state.

        Args:
            session_id: Session identifier
            new_state: New session state
            user_id: Optional user ID for ownership validation

        Raises:
            ValueError: If session ID is invalid
        """
        # Validate session ID format
        validate_session_id(session_id)

        # Update database with row locking to prevent race conditions
        db_session = self.db_session_factory()
        try:
            # Use SELECT FOR UPDATE to lock the row atomically
            stmt = (
                select(SessionModel).where(SessionModel.session_id == session_id).with_for_update()
            )
            result = db_session.execute(stmt)
            db_model = result.scalar_one_or_none()

            if db_model:
                db_model.state = new_state.value
                db_model.updated_at = datetime.now(timezone.utc)
                db_session.commit()
                logger.info(f"Session {session_id} state updated to {new_state.value} atomically")
        except Exception as e:
            db_session.rollback()
            logger.error(f"Failed to update session {session_id} state: {e}")
            raise
        finally:
            db_session.close()

        # Update Redis cache
        if user_id:
            sim_session = await self.get_session(session_id, user_id)
            await self._cache_session_metadata(session_id, sim_session, user_id)

    async def _cache_session_metadata(
        self, session_id: str, sim_session: SimulationSession, user_id: str
    ):
        """Cache session metadata in Redis."""
        metadata = {
            "session_id": session_id,
            "user_id": user_id,
            "state": sim_session.state.value,
            "config": sim_session.config,
            "created_at": sim_session.created_at.isoformat() + "Z",
            "updated_at": sim_session.updated_at.isoformat() + "Z",
        }

        # Cache for 1 hour
        await self.redis.setex(f"session:{session_id}", 3600, json.dumps(metadata))

    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List sessions with pagination and filtering.

        Args:
            user_id: Optional user ID filter
            page: Page number (1-based)
            per_page: Items per page
            state: Optional state filter

        Returns:
            Dict with sessions list and total count
        """
        from sqlalchemy import func

        db_session = self.db_session_factory()
        try:
            # Build query
            stmt = select(SessionModel)
            if user_id:
                stmt = stmt.where(SessionModel.user_id == user_id)
            if state:
                stmt = stmt.where(SessionModel.state == state)

            stmt = stmt.where(SessionModel.is_deleted.is_(False))

            # Get total count
            total = (
                db_session.scalar(
                    select(func.count(SessionModel.session_id)).where(stmt.whereclause)
                )
                if stmt.whereclause is not None
                else db_session.scalar(select(func.count(SessionModel.session_id)))
            )

            # Apply pagination
            offset = (page - 1) * per_page
            stmt = stmt.offset(offset).limit(per_page)

            # Execute query
            result = db_session.execute(stmt)
            sessions = result.scalars().all()

            return {
                "sessions": sessions,
                "total": total,
            }
        finally:
            db_session.close()
