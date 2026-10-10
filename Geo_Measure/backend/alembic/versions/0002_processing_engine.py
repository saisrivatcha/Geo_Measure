"""Processing engine: feature identity, geometry validity, display geometry, statuses.

Also replaces the measurement_status enum (SUCCESS/SKIPPED/FAILED) with the
finer-grained statuses of the measurement engine, mapping existing rows.

Revision ID: c4156ea4edb4
Revises: 32bb670329b2
Create Date: 2026-10-08 07:06:18.474649+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4156ea4edb4"
down_revision: str | None = "32bb670329b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_STATUSES = (
    "COMPLETED",
    "NOT_REQUIRED",
    "NOT_SUPPORTED",
    "NO_GEOMETRY",
    "INVALID_GEOMETRY",
    "CRS_UNAVAILABLE",
    "FAILED",
)
OLD_STATUSES = ("SUCCESS", "SKIPPED", "FAILED")
OLD_CHECK = op.f("ck_feature_measurements_value_present_iff_success")
NEW_CHECK = op.f("ck_feature_measurements_value_present_iff_completed")


def _swap_status_enum(values: tuple[str, ...], mapping_sql: str) -> None:
    """Replace the measurement_status type, converting rows with ``mapping_sql``."""
    op.execute("ALTER TYPE measurement_status RENAME TO measurement_status_old")
    postgresql.ENUM(*values, name="measurement_status").create(op.get_bind())
    op.execute(
        "ALTER TABLE feature_measurements ALTER COLUMN measurement_status "
        f"TYPE measurement_status USING ({mapping_sql})::measurement_status"
    )
    op.execute("DROP TYPE measurement_status_old")


def upgrade() -> None:
    op.drop_constraint(OLD_CHECK, "feature_measurements", type_="check")
    _swap_status_enum(
        NEW_STATUSES,
        "CASE measurement_status::text WHEN 'SUCCESS' THEN 'COMPLETED' "
        "WHEN 'SKIPPED' THEN 'NOT_REQUIRED' ELSE measurement_status::text END",
    )
    op.create_check_constraint(
        NEW_CHECK,
        "feature_measurements",
        "(measurement_status = 'COMPLETED') = (measurement_value IS NOT NULL)",
    )
    op.add_column(
        "feature_measurements",
        sa.Column(
            "source_feature_id",
            sa.String(length=255),
            nullable=True,
            comment="Identifier from the source (Shapefile FID, KML Placemark id).",
        ),
    )
    op.add_column(
        "feature_measurements",
        sa.Column(
            "source_layer",
            sa.String(length=255),
            nullable=True,
            comment="Source layer (KML folder / Shapefile name).",
        ),
    )
    op.add_column(
        "feature_measurements",
        sa.Column(
            "display_geometry_geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "feature_measurements",
        sa.Column(
            "geometry_valid",
            sa.Boolean(),
            nullable=True,
            comment="OGC validity of the source geometry; NULL when not evaluated.",
        ),
    )
    op.add_column(
        "feature_measurements",
        sa.Column(
            "geometry_repaired", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.alter_column(
        "feature_measurements",
        "feature_index",
        existing_type=sa.INTEGER(),
        comment="Zero-based position in the dataset; deterministic per upload.",
        existing_nullable=False,
    )
    op.alter_column(
        "feature_measurements",
        "source_crs",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "feature_measurements",
        "measurement_crs",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "feature_measurements",
        "measurement_value",
        existing_type=sa.DOUBLE_PRECISION(precision=53),
        comment="Full-precision SI value: square metres or metres.",
        existing_nullable=True,
    )
    op.alter_column(
        "feature_measurements",
        "measurement_unit",
        existing_type=sa.VARCHAR(length=16),
        type_=sa.String(length=32),
        existing_nullable=True,
    )
    op.add_column(
        "files",
        sa.Column(
            "source_crs_assumed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="True when source_crs comes from format rules (KML = WGS 84), not the file.",
        ),
    )
    op.alter_column(
        "files",
        "source_crs",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Text(),
        comment="CRS of the source data, e.g. EPSG:4326; NULL when unknown.",
        existing_nullable=True,
    )
    op.alter_column(
        "files",
        "measurement_crs",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Text(),
        comment="Projected CRS used for measurements; NULL if nothing was measured.",
        existing_nullable=True,
    )


def downgrade() -> None:
    op.drop_constraint(NEW_CHECK, "feature_measurements", type_="check")
    _swap_status_enum(
        OLD_STATUSES,
        "CASE measurement_status::text WHEN 'COMPLETED' THEN 'SUCCESS' "
        "WHEN 'FAILED' THEN 'FAILED' ELSE 'SKIPPED' END",
    )
    op.create_check_constraint(
        OLD_CHECK,
        "feature_measurements",
        "(measurement_status = 'SUCCESS') = (measurement_value IS NOT NULL)",
    )
    op.alter_column(
        "files",
        "measurement_crs",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=255),
        postgresql_using="left(measurement_crs, 255)",
        comment=None,
        existing_comment="Projected CRS used for measurements; NULL if nothing was measured.",
        existing_nullable=True,
    )
    op.alter_column(
        "files",
        "source_crs",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=255),
        postgresql_using="left(source_crs, 255)",
        comment=None,
        existing_comment="CRS of the source data, e.g. EPSG:4326; NULL when unknown.",
        existing_nullable=True,
    )
    op.drop_column("files", "source_crs_assumed")
    op.alter_column(
        "feature_measurements",
        "measurement_unit",
        existing_type=sa.String(length=32),
        type_=sa.VARCHAR(length=16),
        existing_nullable=True,
    )
    op.alter_column(
        "feature_measurements",
        "measurement_value",
        existing_type=sa.DOUBLE_PRECISION(precision=53),
        comment=None,
        existing_comment="Full-precision SI value: square metres or metres.",
        existing_nullable=True,
    )
    op.alter_column(
        "feature_measurements",
        "measurement_crs",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=255),
        postgresql_using="left(measurement_crs, 255)",
        existing_nullable=True,
    )
    op.alter_column(
        "feature_measurements",
        "source_crs",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=255),
        postgresql_using="left(source_crs, 255)",
        existing_nullable=True,
    )
    op.alter_column(
        "feature_measurements",
        "feature_index",
        existing_type=sa.INTEGER(),
        comment=None,
        existing_comment="Zero-based position in the dataset; deterministic per upload.",
        existing_nullable=False,
    )
    op.drop_column("feature_measurements", "geometry_repaired")
    op.drop_column("feature_measurements", "geometry_valid")
    op.drop_column("feature_measurements", "display_geometry_geojson")
    op.drop_column("feature_measurements", "source_layer")
    op.drop_column("feature_measurements", "source_feature_id")
