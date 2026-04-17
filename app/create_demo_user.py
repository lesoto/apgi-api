#!/usr/bin/env python3

import sys

# Add /app to Python path for proper imports
sys.path.insert(0, "/app")

from app.database.connection import SessionLocal
from app.database.models import User
from app.services.auth_manager import AuthManager


def create_demo_user() -> None:
    db = SessionLocal()
    try:
        # Check if user exists
        existing = db.query(User).filter(User.email == "user@example.com").first()
        if existing:
            if "admin" not in existing.roles or "user" not in existing.roles:
                existing.roles = ["user", "admin"]
                db.commit()
                print("Demo user updated with user and admin roles")
            else:
                print("Demo user already has user and admin roles")
            return

        # Create user
        auth_manager = AuthManager(db)
        user = User(
            user_id="demo_user_123",
            username="user@example.com",
            email="user@example.com",
            password_hash=auth_manager.hash_password("SecurePassword123"),
            roles=["user", "admin"],
        )
        db.add(user)
        db.commit()
        print("Demo user created")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_demo_user()
