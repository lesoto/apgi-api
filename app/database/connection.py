"""
Database Connection Management

SQLAlchemy engine and session configuration.
"""

import logging
import secrets
import string
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database.models import Base, User

logger = logging.getLogger(__name__)


# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,
    max_overflow=20,
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

        # Log credentials securely (in production, this should go to a secure secrets manager)
        logger.warning(
            f"Generated default user credentials - STORE SECURELY. "
            f"Username: {secure_username}, Password: {secure_password}. "
            f"NOTE: These credentials allow full system access - change immediately"
        )

        # Import here to avoid circular import
        from app.services.auth_manager import AuthManager

        # Create default user
        default_user = User(
            user_id=secure_username,
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
