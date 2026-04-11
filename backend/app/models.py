"""
SQLAlchemy Core table definitions.

We use Core (not ORM) deliberately — every query is explicit SQL,
no auto-flush or identity-map magic. Schema changes go through Alembic
migrations, never through metadata.create_all().
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

metadata = sa.MetaData()

# PostgreSQL ENUMs — defined explicitly so Alembic can manage them
task_status_enum = ENUM("todo", "in_progress", "done", name="task_status", create_type=False)
task_priority_enum = ENUM("low", "medium", "high", name="task_priority", create_type=False)

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("email", sa.String(255), nullable=False, unique=True),
    sa.Column("password_hash", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)

projects = sa.Table(
    "projects",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)

tasks = sa.Table(
    "tasks",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("title", sa.String(500), nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("status", task_status_enum, nullable=False, server_default="todo"),
    sa.Column("priority", task_priority_enum, nullable=False, server_default="medium"),
    sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    sa.Column("assignee_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("due_date", sa.Date, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
)
