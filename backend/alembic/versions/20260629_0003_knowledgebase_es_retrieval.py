"""add knowledge base and indexing storage

Revision ID: 20260629_0003
Revises: 20260629_0002
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260629_0003"
down_revision = "20260629_0002"
branch_labels = None
depends_on = None

DEFAULT_KNOWLEDGE_BASE_NAME = "默认知识库"


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if not _has_table(table_name) or _has_index(table_name, index_name):
        return
    if all(_has_column(table_name, column) for column in columns):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_present(batch, table_name: str, index_name: str) -> None:
    if _has_index(table_name, index_name):
        batch.drop_index(index_name)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if _has_column(table_name, column.name):
        return
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(column)


def _add_fk_column_if_missing(
    table_name: str,
    column_name: str,
    referred_table: str,
    *,
    index: bool = True,
) -> None:
    if _has_column(table_name, column_name):
        return
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(sa.Column(column_name, sa.Integer(), nullable=True))
        if index:
            batch.create_index(f"ix_{table_name}_{column_name}", [column_name])
        batch.create_foreign_key(f"fk_{table_name}_{column_name}_{referred_table}", referred_table, [column_name], ["id"])


def _create_knowledge_bases_table() -> None:
    if _has_table("knowledge_bases"):
        return
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_knowledge_bases_user_name"),
    )
    op.create_index("ix_knowledge_bases_user_id", "knowledge_bases", ["user_id"])
    op.create_index("ix_knowledge_bases_status", "knowledge_bases", ["status"])
    op.create_index("ix_knowledge_bases_is_default", "knowledge_bases", ["is_default"])


def _create_indexing_runs_table() -> None:
    if _has_table("indexing_runs"):
        return
    op.create_table(
        "indexing_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("knowledge_base_id", sa.Integer(), sa.ForeignKey("knowledge_bases.id"), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("ingestion_jobs.id"), nullable=True),
        sa.Column("run_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
        sa.Column("embedding_provider_profile_id", sa.Integer(), sa.ForeignKey("llm_provider_profiles.id"), nullable=True),
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("chunks_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("chunks_embedded", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("chunks_indexed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_indexing_runs_user_id", "indexing_runs", ["user_id"])
    op.create_index("ix_indexing_runs_knowledge_base_id", "indexing_runs", ["knowledge_base_id"])
    op.create_index("ix_indexing_runs_source_id", "indexing_runs", ["source_id"])
    op.create_index("ix_indexing_runs_job_id", "indexing_runs", ["job_id"])
    op.create_index("ix_indexing_runs_run_type", "indexing_runs", ["run_type"])
    op.create_index("ix_indexing_runs_status", "indexing_runs", ["status"])


def _add_source_chunk_columns() -> None:
    if not _has_table("source_chunks"):
        return
    _add_fk_column_if_missing("source_chunks", "user_id", "users")
    _add_fk_column_if_missing("source_chunks", "knowledge_base_id", "knowledge_bases")
    _add_column_if_missing("source_chunks", sa.Column("content_hash", sa.String(length=64), nullable=True))
    _add_column_if_missing("source_chunks", sa.Column("token_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    _add_column_if_missing("source_chunks", sa.Column("embedding_status", sa.String(length=40), nullable=False, server_default="pending"))
    _add_fk_column_if_missing("source_chunks", "embedding_provider_profile_id", "llm_provider_profiles", index=False)
    _add_column_if_missing("source_chunks", sa.Column("embedding_model", sa.String(length=200), nullable=True))
    _add_column_if_missing("source_chunks", sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
    _add_column_if_missing("source_chunks", sa.Column("embedding_error", sa.Text(), nullable=True))
    _add_column_if_missing("source_chunks", sa.Column("embedded_at", sa.DateTime(), nullable=True))
    _add_column_if_missing("source_chunks", sa.Column("index_status", sa.String(length=40), nullable=False, server_default="pending"))
    _add_column_if_missing("source_chunks", sa.Column("index_error", sa.Text(), nullable=True))
    _add_column_if_missing("source_chunks", sa.Column("indexed_at", sa.DateTime(), nullable=True))
    _add_column_if_missing("source_chunks", sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))
    _create_index_if_missing("source_chunks", "ix_source_chunks_content_hash", ["content_hash"])
    _create_index_if_missing("source_chunks", "ix_source_chunks_embedding_status", ["embedding_status"])
    _create_index_if_missing("source_chunks", "ix_source_chunks_index_status", ["index_status"])


def _add_provider_columns() -> None:
    if not _has_table("llm_provider_profiles"):
        return
    _add_column_if_missing("llm_provider_profiles", sa.Column("supports_chat", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    _add_column_if_missing("llm_provider_profiles", sa.Column("supports_embedding", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    _add_column_if_missing("llm_provider_profiles", sa.Column("embedding_model", sa.String(length=200), nullable=True))
    _add_column_if_missing("llm_provider_profiles", sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
    _add_column_if_missing("llm_provider_profiles", sa.Column("embedding_status", sa.String(length=40), nullable=False, server_default="untested"))
    _add_column_if_missing("llm_provider_profiles", sa.Column("embedding_last_error", sa.Text(), nullable=True))
    _add_column_if_missing("llm_provider_profiles", sa.Column("embedding_last_checked_at", sa.DateTime(), nullable=True))


def _ensure_default_knowledge_bases() -> None:
    if not _has_table("users") or not _has_table("knowledge_bases"):
        return
    connection = op.get_bind()
    user_ids = [int(row[0]) for row in connection.execute(sa.text("SELECT id FROM users")).all()]
    for user_id in user_ids:
        default_id = connection.execute(
            sa.text(
                "SELECT id FROM knowledge_bases "
                "WHERE user_id = :user_id AND is_default = :is_default "
                "ORDER BY id ASC LIMIT 1"
            ),
            {"user_id": user_id, "is_default": True},
        ).scalar()
        if default_id is not None:
            continue

        named_id = connection.execute(
            sa.text(
                "SELECT id FROM knowledge_bases "
                "WHERE user_id = :user_id AND name = :name "
                "ORDER BY id ASC LIMIT 1"
            ),
            {"user_id": user_id, "name": DEFAULT_KNOWLEDGE_BASE_NAME},
        ).scalar()
        if named_id is not None:
            connection.execute(
                sa.text(
                    "UPDATE knowledge_bases "
                    "SET status = 'active', is_default = :is_default, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = :knowledge_base_id"
                ),
                {"knowledge_base_id": int(named_id), "is_default": True},
            )
            continue

        connection.execute(
            sa.text(
                "INSERT INTO knowledge_bases (user_id, name, description, status, is_default, created_at, updated_at) "
                "VALUES (:user_id, :name, NULL, 'active', :is_default, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"user_id": user_id, "name": DEFAULT_KNOWLEDGE_BASE_NAME, "is_default": True},
        )


def _backfill_scopes() -> None:
    connection = op.get_bind()
    if _has_column("sources", "knowledge_base_id"):
        connection.execute(
            sa.text(
                "UPDATE sources "
                "SET knowledge_base_id = ("
                "  SELECT kb.id FROM knowledge_bases kb "
                "  WHERE kb.user_id = sources.user_id AND kb.is_default = :is_default "
                "  ORDER BY kb.id ASC LIMIT 1"
                ") "
                "WHERE knowledge_base_id IS NULL"
            ),
            {"is_default": True},
        )

    if _has_column("ingestion_jobs", "knowledge_base_id"):
        connection.execute(
            sa.text(
                "UPDATE ingestion_jobs "
                "SET knowledge_base_id = ("
                "  SELECT s.knowledge_base_id FROM sources s "
                "  WHERE s.id = ingestion_jobs.source_id"
                ") "
                "WHERE knowledge_base_id IS NULL AND source_id IS NOT NULL"
            )
        )
        connection.execute(
            sa.text(
                "UPDATE ingestion_jobs "
                "SET knowledge_base_id = ("
                "  SELECT kb.id FROM knowledge_bases kb "
                "  WHERE kb.user_id = ingestion_jobs.user_id AND kb.is_default = :is_default "
                "  ORDER BY kb.id ASC LIMIT 1"
                ") "
                "WHERE knowledge_base_id IS NULL"
            ),
            {"is_default": True},
        )

    if _has_column("source_chunks", "user_id") and _has_column("source_chunks", "knowledge_base_id"):
        connection.execute(
            sa.text(
                "UPDATE source_chunks "
                "SET user_id = COALESCE(user_id, ("
                "  SELECT s.user_id FROM sources s WHERE s.id = source_chunks.source_id"
                ")), "
                "knowledge_base_id = COALESCE(knowledge_base_id, ("
                "  SELECT s.knowledge_base_id FROM sources s WHERE s.id = source_chunks.source_id"
                ")) "
                "WHERE user_id IS NULL OR knowledge_base_id IS NULL"
            )
        )


def upgrade() -> None:
    _create_knowledge_bases_table()
    _create_index_if_missing("knowledge_bases", "ix_knowledge_bases_user_id", ["user_id"])
    _create_index_if_missing("knowledge_bases", "ix_knowledge_bases_status", ["status"])
    _create_index_if_missing("knowledge_bases", "ix_knowledge_bases_is_default", ["is_default"])

    if _has_table("sources"):
        _add_fk_column_if_missing("sources", "knowledge_base_id", "knowledge_bases")
    if _has_table("ingestion_jobs"):
        _add_fk_column_if_missing("ingestion_jobs", "knowledge_base_id", "knowledge_bases")
    _add_source_chunk_columns()
    _add_provider_columns()
    _create_indexing_runs_table()
    _create_index_if_missing("indexing_runs", "ix_indexing_runs_user_id", ["user_id"])
    _create_index_if_missing("indexing_runs", "ix_indexing_runs_knowledge_base_id", ["knowledge_base_id"])
    _create_index_if_missing("indexing_runs", "ix_indexing_runs_source_id", ["source_id"])
    _create_index_if_missing("indexing_runs", "ix_indexing_runs_job_id", ["job_id"])
    _create_index_if_missing("indexing_runs", "ix_indexing_runs_run_type", ["run_type"])
    _create_index_if_missing("indexing_runs", "ix_indexing_runs_status", ["status"])

    _ensure_default_knowledge_bases()
    _backfill_scopes()


def downgrade() -> None:
    if _has_table("indexing_runs"):
        op.drop_table("indexing_runs")

    if _has_table("llm_provider_profiles"):
        with op.batch_alter_table("llm_provider_profiles") as batch:
            for column_name in (
                "embedding_last_checked_at",
                "embedding_last_error",
                "embedding_status",
                "embedding_dimensions",
                "embedding_model",
                "supports_embedding",
                "supports_chat",
            ):
                if _has_column("llm_provider_profiles", column_name):
                    batch.drop_column(column_name)

    if _has_table("source_chunks"):
        with op.batch_alter_table("source_chunks") as batch:
            _drop_index_if_present(batch, "source_chunks", "ix_source_chunks_content_hash")
            _drop_index_if_present(batch, "source_chunks", "ix_source_chunks_embedding_status")
            _drop_index_if_present(batch, "source_chunks", "ix_source_chunks_index_status")
            _drop_index_if_present(batch, "source_chunks", "ix_source_chunks_user_id")
            _drop_index_if_present(batch, "source_chunks", "ix_source_chunks_knowledge_base_id")
            for column_name in (
                "updated_at",
                "indexed_at",
                "index_error",
                "index_status",
                "embedded_at",
                "embedding_error",
                "embedding_dimensions",
                "embedding_model",
                "embedding_provider_profile_id",
                "embedding_status",
                "token_count",
                "content_hash",
                "knowledge_base_id",
                "user_id",
            ):
                if _has_column("source_chunks", column_name):
                    batch.drop_column(column_name)

    if _has_table("ingestion_jobs"):
        with op.batch_alter_table("ingestion_jobs") as batch:
            _drop_index_if_present(batch, "ingestion_jobs", "ix_ingestion_jobs_knowledge_base_id")
            if _has_column("ingestion_jobs", "knowledge_base_id"):
                batch.drop_column("knowledge_base_id")

    if _has_table("sources"):
        with op.batch_alter_table("sources") as batch:
            _drop_index_if_present(batch, "sources", "ix_sources_knowledge_base_id")
            if _has_column("sources", "knowledge_base_id"):
                batch.drop_column("knowledge_base_id")

    if _has_table("knowledge_bases"):
        op.drop_table("knowledge_bases")
