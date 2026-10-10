"""Create files and feature_measurements tables.

Revision ID: 32bb670329b2
Revises:
Create Date: 2026-10-08 06:50:19.762593+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "32bb670329b2"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.Enum("KML", "SHAPEFILE", name="file_type"), nullable=False),
        sa.Column(
            "stored_path",
            sa.String(length=1024),
            nullable=False,
            comment="Path of the original upload, relative to STORAGE_DIR.",
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="file_status"),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("feature_count", sa.Integer(), nullable=True),
        sa.Column("source_crs", sa.String(length=255), nullable=True),
        sa.Column("measurement_crs", sa.String(length=255), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "feature_count IS NULL OR feature_count >= 0",
            name=op.f("ck_files_feature_count_non_negative"),
        ),
        sa.CheckConstraint("file_size_bytes >= 0", name=op.f("ck_files_file_size_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_files")),
    )
    op.create_index(op.f("ix_files_created_at"), "files", ["created_at"], unique=False)
    op.create_index(op.f("ix_files_status"), "files", ["status"], unique=False)
    op.create_table(
        "feature_measurements",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("feature_index", sa.Integer(), nullable=False),
        sa.Column(
            "geometry_type",
            sa.String(length=32),
            nullable=True,
            comment="OGC type name, e.g. Polygon; NULL for a null geometry.",
        ),
        sa.Column("geometry_geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_crs", sa.String(length=255), nullable=True),
        sa.Column("measurement_crs", sa.String(length=255), nullable=True),
        sa.Column(
            "measurement_type",
            sa.Enum("LENGTH", "AREA", name="measurement_type"),
            nullable=True,
        ),
        sa.Column("measurement_value", sa.Double(), nullable=True),
        sa.Column("measurement_unit", sa.String(length=16), nullable=True),
        sa.Column(
            "measurement_status",
            sa.Enum("SUCCESS", "SKIPPED", "FAILED", name="measurement_status"),
            nullable=False,
        ),
        sa.Column("measurement_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(measurement_status = 'SUCCESS') = (measurement_value IS NOT NULL)",
            name=op.f("ck_feature_measurements_value_present_iff_success"),
        ),
        sa.CheckConstraint(
            "feature_index >= 0",
            name=op.f("ck_feature_measurements_feature_index_non_negative"),
        ),
        sa.CheckConstraint(
            "measurement_value IS NULL OR measurement_value >= 0",
            name=op.f("ck_feature_measurements_measurement_value_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
            name=op.f("fk_feature_measurements_file_id_files"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feature_measurements")),
        sa.UniqueConstraint(
            "file_id",
            "feature_index",
            name=op.f("uq_feature_measurements_file_id_feature_index"),
        ),
    )


def downgrade() -> None:
    op.drop_table("feature_measurements")
    op.drop_index(op.f("ix_files_status"), table_name="files")
    op.drop_index(op.f("ix_files_created_at"), table_name="files")
    op.drop_table("files")
    for enum_name in ("measurement_status", "measurement_type", "file_status", "file_type"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
