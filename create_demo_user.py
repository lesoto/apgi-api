#!/usr/bin/env python3
"""
Simple script to create a demo user for the API demo
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from app.database.connection import get_db_context
from app.database.models import User
from app.services.auth_manager import AuthManager


def create_demo_user():
    """Create a demo user for testing"""

    with get_db_context() as db:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == "user@example.com").first()
        if existing_user:
            print("Demo user already exists")
            return

        # Create demo user
        demo_user = User(
            user_id="demo_user",
            username="user@example.com",
            email="user@example.com",
            password_hash=AuthManager.hash_password("SecurePassword123"),
            roles=["admin", "user"],
        )

        db.add(demo_user)
        db.commit()

        print("Demo user created successfully!")
        print("Username: user@example.com")
        print("Password: SecurePassword123")


if __name__ == "__main__":
    create_demo_user()
