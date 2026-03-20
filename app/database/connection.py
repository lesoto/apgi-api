"""
Database Connection Management

SQLAlchemy engine and session configuration.
"""

import logging
import secrets
import string
import uuid
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database.models import Base, User

logger = logging.getLogger(__name__)


# Create SQLAlchemy engine with connection pooling
if settings.database_url.startswith("sqlite"):
    # SQLite-specific configuration
    engine = create_engine(
        settings.database_url,
        echo=False,  # Set to True for SQL query logging
        connect_args={"check_same_thread": False},  # SQLite specific
    )
else:
    # PostgreSQL configuration with connection pooling optimized for horizontal scaling
    engine = create_engine(
        settings.database_url,
        echo=False,  # Set to True for SQL query logging
        pool_pre_ping=True,  # Verify connections before using
        pool_size=settings.pool_size,  # Configurable pool size
        max_overflow=settings.max_overflow,  # Configurable overflow
        pool_timeout=settings.pool_timeout,  # Configurable timeout
        pool_recycle=settings.pool_recycle,  # Configurable recycle
        echo_pool=False,  # Disable pool logging in production
    )


# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def generate_secure_password(length: int = 32) -> str:
    """
    Generate a secure random password.

    Args:
        length: Length of the password to generate

    Returns:
        Secure random password string
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    return password


def generate_secure_username(prefix: str = "user") -> str:
    """
    Generate a secure random username.

    Args:
        prefix: Prefix for the username

    Returns:
        Secure random username string
    """
    random_suffix = secrets.token_hex(8)
    return f"{prefix}_{random_suffix}"


def init_db():
    """
    Initialize database by creating all tables and default user.

    This should be called during application startup.
    """
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # Create default user if it doesn't exist
        create_default_user()

    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


def create_default_user():
    """
    Create a default user for session management with secure random credentials.

    This ensures that the foreign key constraint for sessions
    can be satisfied when creating sessions without explicit user management.
    """
    db = SessionLocal()
    try:
        # Check if any default user already exists (users with username starting with "default_")
        from sqlalchemy import select

        stmt = select(User).where(User.username.like("default_%"))
        result = db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.info(f"Default user already exists: {existing_user.username}")
            return

        # Generate secure credentials
        secure_username = generate_secure_username("default")
        secure_password = generate_secure_password()

        # Write credentials to secure temporary file with proper cleanup
        import pathlib
        import tempfile

        # Use NamedTemporaryFile with delete=True for automatic cleanup
        # Use mode='w+' to write text and keep file open for logging
        with tempfile.NamedTemporaryFile(
            mode="w+",
            prefix="apgi_default_user_",
            suffix=".txt",
            delete=True,
            encoding="utf-8",
        ) as temp_file:
            secrets_content = f"""Generated default user credentials - STORE SECURELY
Username: {secure_username}
Password: {secure_password}
NOTE: These credentials allow full system access - change immediately
"""
            temp_file.write(secrets_content)
            temp_file.flush()

            # Get the file path before it's deleted
            secrets_file_path = pathlib.Path(temp_file.name)
            secrets_file_path.chmod(0o600)

            logger.warning(
                f"Default user created: {secure_username} - credentials written to temporary file: {secrets_file_path}"
                f" (File will be automatically cleaned up when closed)"
            )

        # Import here to avoid circular import
        from app.services.auth_manager import AuthManager

        # Create default user with proper UUID
        user_id = str(uuid.uuid4())
        default_user = User(
            user_id=user_id,
            username=secure_username,
            email=f"{secure_username}@apgi-system.local",
            password_hash=AuthManager.hash_password(secure_password),
            roles=["user", "session_manager"],
        )

        db.add(default_user)
        db.commit()
        logger.info(f"Default user created with secure credentials: {secure_username}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create default user: {e}")
        raise
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.

    Yields:
        Session: SQLAlchemy database session

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: Session = Depends(get_db)):
            # Use db session
            pass
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database session.

    Yields:
        Session: SQLAlchemy database session

    Usage:
        with get_db_context() as db:
            # Use db session
            pass
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def close_db():
    """
    Close database connections.

    This should be called during application shutdown.
    """
    try:
        engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


def get_pool_status() -> dict:
    """
    Get database connection pool status for monitoring.

    Returns:
        Dictionary with pool status information
    """
    pool = engine.pool

    status = {
        "pool_size": getattr(pool, "size", 0),
        "checked_in": getattr(pool, "checkedin", 0),
        "checked_out": getattr(pool, "checkedout", 0),
        "overflow": getattr(pool, "overflow", 0),
        "invalid": getattr(pool, "invalid", 0),
        "timeout": getattr(pool, "timeout", 0),
    }

    # Calculate utilization
    total_connections = status["checked_in"] + status["checked_out"]
    max_connections = status["pool_size"] + status["overflow"]
    utilization = total_connections / max_connections if max_connections > 0 else 0

    status["utilization"] = utilization
    status["available_connections"] = max_connections - total_connections

    # Log warnings if pool is under stress
    if utilization > 0.8:
        logger.warning(
            f"Database connection pool under high load: {utilization:.1%} utilized "
            f"({total_connections}/{max_connections} connections)"
        )
    elif status["checked_out"] >= status["pool_size"] + status["overflow"]:
        logger.error(
            f"Database connection pool exhausted: {status['checked_out']} connections checked out, "
            f"pool_size={status['pool_size']}, overflow={status['overflow']}"
        )

    return status


def log_pool_status():
    """
    Log current database connection pool status.
    """
    status = get_pool_status()
    logger.info(
        f"DB Pool Status: size={status['pool_size']}, checked_out={status['checked_out']}, "
        f"checked_in={status['checked_in']}, overflow={status['overflow']}, "
        f"utilization={status['utilization']:.1%}"
    )
