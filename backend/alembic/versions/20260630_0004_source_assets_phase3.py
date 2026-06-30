"""add source assets for phase 3 surfaces

Revision ID: 20260630_0004
Revises: 20260629_0003
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260630_0004"
down_revision = "20260629_0003"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    if not _has_table("source_assets"):
        op.create_table(
            "source_assets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("knowledge_base_id", sa.Integer(), sa.ForeignKey("knowledge_bases.id"), nullable=True),
            sa.Column("asset_type", sa.String(length=40), nullable=False),
            sa.Column("filename", sa.String(length=500), nullable=False),
            sa.Column("mime_type", sa.String(length=200), nullable=True),
            sa.Column("byte_size", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("storage_path", sa.String(length=1000), nullable=True),
            sa.Column("parse_status", sa.String(length=40), nullable=False, server_default="pending"),
            sa.Column("parse_error", sa.Text(), nullable=True),
            sa.Column("embedding_status", sa.String(length=40), nullable=False, server_default="pending"),
            sa.Column("embedding_error", sa.Text(), nullable=True),
            sa.Column("index_status", sa.String(length=40), nullable=False, server_default="pending"),
            sa.Column("index_error", sa.Text(), nullable=True),
            sa.Column("graph_status", sa.String(length=40), nullable=False, server_default="pending"),
            sa.Column("graph_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )

    _create_index_if_missing("source_assets", "ix_source_assets_source_id", ["source_id"])
    _create_index_if_missing("source_assets", "ix_source_assets_user_id", ["user_id"])
    _create_index_if_missing("source_assets", "ix_source_assets_knowledge_base_id", ["knowledge_base_id"])
    _create_index_if_missing("source_assets", "ix_source_assets_asset_type", ["asset_type"])
    _create_index_if_missing("source_assets", "ix_source_assets_parse_status", ["parse_status"])
    _create_index_if_missing("source_assets", "ix_source_assets_embedding_status", ["embedding_status"])
    _create_index_if_missing("source_assets", "ix_source_assets_index_status", ["index_status"])
    _create_index_if_missing("source_assets", "ix_source_assets_graph_status", ["graph_status"])


def downgrade() -> None:
    if _has_table("source_assets"):
        op.drop_table("source_assets")
