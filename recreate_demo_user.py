#!/usr/bin/env python3
"""
Script to recreate demo user with admin privileges
"""

import sys
import os

# Add app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from app.database.connection import get_db_context
from app.database.models import User
from app.services.auth_manager import AuthManager


def recreate_demo_user():
    """Recreate demo user with admin privileges"""
    with get_db_context() as db:
        # Delete existing user if it exists
        existing_user = db.query(User).filter(User.username == "user@example.com").first()
        if existing_user:
            db.delete(existing_user)
            db.commit()
            print("Deleted existing demo user")

        # Create demo user with admin privileges
        demo_user = User(
            user_id="demo_user",
            username="user@example.com",
            email="user@example.com",
            password_hash=AuthManager.hash_password("SecurePassword123"),
            roles=["admin", "user"],
        )

        db.add(demo_user)
        db.commit()

        print("Demo user created successfully with admin privileges!")
        print("Username: user@example.com")
        print("Password: SecurePassword123")


if __name__ == "__main__":
    recreate_demo_user()
