"""add auth users and user-scoped records

Revision ID: 20260629_0002
Revises: 20260618_0001
Create Date: 2026-06-29
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets

from alembic import op
import sqlalchemy as sa

revision = "20260629_0002"
down_revision = "20260618_0001"
branch_labels = None
depends_on = None


OWNED_TABLES = (
    "sources",
    "ingestion_jobs",
    "conversations",
    "memory_candidates",
    "memories",
    "memory_relations",
    "tags",
    "tag_assignments",
    "tag_suggestions",
    "favorites",
    "llm_provider_profiles",
    "agent_profiles",
    "agent_tool_logs",
    "reranker_profiles",
)


def _hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(16)
    iterations = 260_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    encoded = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${iterations}${salt}${encoded}"


def _bootstrap_user_id() -> int:
    connection = op.get_bind()
    email = os.environ.get("LUMEN_BOOTSTRAP_USER_EMAIL", "admin@example.com").strip().lower()
    password = os.environ.get("LUMEN_BOOTSTRAP_USER_PASSWORD", "admin-password")
    existing = connection.execute(sa.text("SELECT id FROM users WHERE email = :email"), {"email": email}).scalar()
    if existing is not None:
        return int(existing)
    connection.execute(
        sa.text(
            "INSERT INTO users (email, password_hash, is_admin, created_at, updated_at) "
            "VALUES (:email, :password_hash, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"email": email, "password_hash": _hash_password(password)},
    )
    return int(connection.execute(sa.text("SELECT id FROM users WHERE email = :email"), {"email": email}).scalar_one())


def _add_user_column(table_name: str) -> None:
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch.create_index(f"ix_{table_name}_user_id", ["user_id"])
        batch.create_foreign_key(f"fk_{table_name}_user_id_users", "users", ["user_id"], ["id"])


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _drop_user_column(table_name: str) -> None:
    with op.batch_alter_table(table_name) as batch:
        batch.drop_constraint(f"fk_{table_name}_user_id_users", type_="foreignkey")
        batch.drop_index(f"ix_{table_name}_user_id")
        batch.drop_column("user_id")


def upgrade() -> None:
    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("password_hash", sa.Text(), nullable=False),
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("email"),
        )
        op.create_index("ix_users_email", "users", ["email"])

    added_user_scope: set[str] = set()
    for table_name in OWNED_TABLES:
        if not _has_column(table_name, "user_id"):
            _add_user_column(table_name)
            added_user_scope.add(table_name)

    if "tags" in added_user_scope:
        with op.batch_alter_table("tags") as batch:
            batch.drop_constraint("uq_tags_normalized_name", type_="unique")
            batch.create_unique_constraint("uq_tags_normalized_name", ["user_id", "normalized_name"])
    if "tag_assignments" in added_user_scope:
        with op.batch_alter_table("tag_assignments") as batch:
            batch.drop_constraint("uq_tag_assignment_target", type_="unique")
            batch.create_unique_constraint("uq_tag_assignment_target", ["user_id", "tag_id", "target_type", "target_id"])
    if "favorites" in added_user_scope:
        with op.batch_alter_table("favorites") as batch:
            batch.drop_constraint("uq_favorite_target", type_="unique")
            batch.create_unique_constraint("uq_favorite_target", ["user_id", "target_type", "target_id"])
    if "memory_relations" in added_user_scope:
        with op.batch_alter_table("memory_relations") as batch:
            batch.drop_constraint("uq_memory_relation_pair_type", type_="unique")
            batch.create_unique_constraint(
                "uq_memory_relation_pair_type",
                ["user_id", "source_memory_id", "target_memory_id", "relation_type"],
            )

    user_id = _bootstrap_user_id()
    connection = op.get_bind()
    for table_name in OWNED_TABLES:
        connection.execute(sa.text(f"UPDATE {table_name} SET user_id = :user_id WHERE user_id IS NULL"), {"user_id": user_id})


def downgrade() -> None:
    with op.batch_alter_table("memory_relations") as batch:
        batch.drop_constraint("uq_memory_relation_pair_type", type_="unique")
        batch.create_unique_constraint("uq_memory_relation_pair_type", ["source_memory_id", "target_memory_id", "relation_type"])
    with op.batch_alter_table("favorites") as batch:
        batch.drop_constraint("uq_favorite_target", type_="unique")
        batch.create_unique_constraint("uq_favorite_target", ["target_type", "target_id"])
    with op.batch_alter_table("tag_assignments") as batch:
        batch.drop_constraint("uq_tag_assignment_target", type_="unique")
        batch.create_unique_constraint("uq_tag_assignment_target", ["tag_id", "target_type", "target_id"])
    with op.batch_alter_table("tags") as batch:
        batch.drop_constraint("uq_tags_normalized_name", type_="unique")
        batch.create_unique_constraint("uq_tags_normalized_name", ["normalized_name"])

    for table_name in reversed(OWNED_TABLES):
        _drop_user_column(table_name)

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
