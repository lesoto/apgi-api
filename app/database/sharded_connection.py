"""
Sharding-Aware Database Connection Management

Enhanced database connection management with support for database sharding.
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings
from app.services.sharding_service import sharding_service

logger = logging.getLogger(__name__)


class ShardedDatabaseManager:
    """Database manager that supports sharding across multiple database instances."""

    def __init__(self) -> None:
        self.engines: Dict[str, Any] = {}
        self.session_factories: Dict[str, sessionmaker[Session]] = {}

        # Initialize engines for all configured shards
        self._initialize_shard_engines()

    def _initialize_shard_engines(self) -> None:
        """Initialize database engines for all shards."""
        shard_configs = sharding_service.get_all_shards()

        for shard_info in shard_configs:
            shard_id = shard_info.shard_id
            database_url = shard_info.database_url

            # Configure engine based on database type
            if database_url.startswith("sqlite"):
                engine = create_engine(
                    database_url,
                    echo=False,
                    connect_args={"check_same_thread": False},
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                )
            else:
                # PostgreSQL configuration optimized for sharding
                engine = create_engine(
                    database_url,
                    echo=False,
                    pool_pre_ping=True,
                    pool_size=15,  # Smaller pool per shard
                    max_overflow=20,
                    pool_timeout=30,
                    pool_recycle=3600,
                    poolclass=QueuePool,
                )

            self.engines[shard_id] = engine
            self.session_factories[shard_id] = sessionmaker(
                autocommit=False, autoflush=False, bind=engine
            )

            logger.info(f"Initialized database engine for shard {shard_id}: {database_url}")

    def get_shard_for_user(self, user_id: str) -> str:
        """Get shard ID for a user."""
        return sharding_service.get_shard_for_user(user_id)

    def get_engine_for_shard(self, shard_id: str) -> Optional[Any]:
        """Get SQLAlchemy engine for a specific shard."""
        return self.engines.get(shard_id)

    def get_session_for_user(self, user_id: str) -> Session:
        """
        Get a database session for the appropriate shard.

        Args:
            user_id: User identifier

        Returns:
            SQLAlchemy session for the appropriate shard
        """
        shard_id = self.get_shard_for_user(user_id)
        session_factory = self.session_factories.get(shard_id)

        if not session_factory:
            raise ValueError(f"No session factory available for shard {shard_id}")

        return session_factory()

    def get_session_for_shard(self, shard_id: str) -> Session:
        """
        Get a database session for a specific shard.

        Args:
            shard_id: Shard identifier

        Returns:
            SQLAlchemy session for the shard
        """
        session_factory = self.session_factories.get(shard_id)

        if not session_factory:
            raise ValueError(f"No session factory available for shard {shard_id}")

        return session_factory()

    @contextmanager
    def get_user_session(self, user_id: str) -> Generator[Session, None, None]:
        """
        Context manager for user-specific database sessions.

        Args:
            user_id: User identifier

        Yields:
            Database session for the user's shard
        """
        session = self.get_session_for_user(user_id)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def get_shard_session(self, shard_id: str) -> Generator[Session, None, None]:
        """
        Context manager for shard-specific database sessions.

        Args:
            shard_id: Shard identifier

        Yields:
            Database session for the shard
        """
        session = self.get_session_for_shard(shard_id)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def execute_cross_shard_query(self, query_func: Any, *args: Any, **kwargs: Any) -> list[Any]:
        """
        Execute a query that needs to run across all shards.

        This is useful for queries that don't have a specific user context,
        like global statistics or admin operations.

        Args:
            query_func: Function that takes a session and returns query results
            *args: Additional arguments for query_func
            **kwargs: Additional keyword arguments for query_func

        Returns:
            Combined results from all shards
        """
        all_results = []

        for shard_id in self.engines.keys():
            with self.get_shard_session(shard_id) as session:
                try:
                    results = query_func(session, *args, **kwargs)
                    if results:
                        all_results.extend(results)
                except Exception as e:
                    logger.error(f"Error executing query on shard {shard_id}: {e}")
                    # Continue with other shards rather than failing completely

        return all_results

    def get_shard_stats(self) -> Dict[str, Any]:
        """Get statistics about all shards."""
        stats = {"total_shards": len(self.engines), "shards": {}}

        for shard_id, engine in self.engines.items():
            try:
                # Get basic connection pool stats
                pool = engine.pool
                pool_info: Dict[str, Any] = getattr(pool, "_pool", {})
                stats["shards"][shard_id] = {  # type: ignore[index]
                    "pool_size": getattr(pool, "size", 0),
                    "checked_in": getattr(pool_info, "get", lambda x: 0)("checkedin"),
                    "checked_out": getattr(pool_info, "get", lambda x: 0)("checkedout"),
                    "overflow": getattr(pool, "_overflow", 0),
                    "invalid": getattr(pool, "_invalid", 0),
                }
            except Exception as e:  # pragma: no cover
                logger.error(f"Error getting stats for shard {shard_id}: {e}")
                stats["shards"][shard_id] = {"error": str(e)}  # type: ignore[index]

        return stats

    def close_all_connections(self) -> None:
        """Close all database connections across all shards."""
        for shard_id, engine in self.engines.items():
            try:
                engine.dispose()
                logger.info(f"Closed connections for shard {shard_id}")
            except Exception as e:
                logger.error(f"Error closing connections for shard {shard_id}: {e}")


# Global sharded database manager instance
sharded_db_manager: Optional[ShardedDatabaseManager] = None
if settings.database_shards_enabled:  # pragma: no cover
    sharded_db_manager = ShardedDatabaseManager()
    logger.info("Sharded database manager initialized")
else:
    logger.info("Database sharding disabled, using single database instance")
