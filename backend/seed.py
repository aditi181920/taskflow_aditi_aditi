"""
Seed script — creates test data for immediate login and exploration.

Idempotent: skips if the seed user already exists, so it's safe
to run on every container start.

Test credentials:
  Email:    test@example.com
  Password: password123
"""

import logging
import os
import sys

from passlib.context import CryptContext
from sqlalchemy import create_engine, text

logging.getLogger("passlib").setLevel(logging.ERROR)

DATABASE_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://taskflow:taskflow_dev@db:5432/taskflow",
)
BCRYPT_COST = int(os.environ.get("BCRYPT_COST", "12"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_COST)


def seed():
    engine = create_engine(DATABASE_URL_SYNC)
    with engine.connect() as conn:
        # Check if seed user already exists
        result = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": "test@example.com"})
        if result.first():
            print("Seed data already exists, skipping.")
            return

        password_hash = pwd_context.hash("password123")

        # Create test user
        user_row = conn.execute(
            text("""
                INSERT INTO users (name, email, password_hash)
                VALUES (:name, :email, :password_hash)
                RETURNING id
            """),
            {"name": "Test User", "email": "test@example.com", "password_hash": password_hash},
        )
        user_id = user_row.scalar()

        # Create test project
        project_row = conn.execute(
            text("""
                INSERT INTO projects (name, description, owner_id)
                VALUES (:name, :description, :owner_id)
                RETURNING id
            """),
            {"name": "Website Redesign", "description": "Q2 redesign project", "owner_id": user_id},
        )
        project_id = project_row.scalar()

        # Create 3 tasks with different statuses
        tasks_data = [
            {
                "title": "Design homepage",
                "description": "Create mockups for the new homepage layout",
                "status": "todo",
                "priority": "high",
                "project_id": project_id,
                "assignee_id": user_id,
                "created_by": user_id,
            },
            {
                "title": "Implement authentication",
                "description": "Set up JWT-based auth flow",
                "status": "in_progress",
                "priority": "medium",
                "project_id": project_id,
                "assignee_id": None,
                "created_by": user_id,
            },
            {
                "title": "Write API tests",
                "description": "Integration tests for all endpoints",
                "status": "done",
                "priority": "low",
                "project_id": project_id,
                "assignee_id": user_id,
                "created_by": user_id,
            },
        ]

        for t in tasks_data:
            conn.execute(
                text("""
                    INSERT INTO tasks (title, description, status, priority, project_id, assignee_id, created_by)
                    VALUES (:title, :description, :status, :priority, :project_id, :assignee_id, :created_by)
                """),
                t,
            )

        conn.commit()
        print(f"Seed data created: user={user_id}, project={project_id}, 3 tasks")


if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        print(f"Seed failed: {e}", file=sys.stderr)
        sys.exit(1)
