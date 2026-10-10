"""Model, constraint and migration tests against PostgreSQL."""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    FeatureMeasurement,
    File,
    FileStatus,
    FileType,
    MeasurementStatus,
    MeasurementType,
)
from app.repositories.feature_measurement_repository import FeatureMeasurementRepository

pytestmark = pytest.mark.db


def _file(**overrides: object) -> File:
    values: dict[str, object] = {
        "filename": "parcels.zip",
        "file_type": FileType.SHAPEFILE,
        "stored_path": "x/original/parcels.zip",
        "file_size_bytes": 2048,
    }
    values.update(overrides)
    return File(**values)


def _measurement(index: int, **overrides: object) -> FeatureMeasurement:
    values: dict[str, object] = {
        "feature_index": index,
        "geometry_type": "Polygon",
        "geometry_geojson": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        "properties": {"name": f"parcel-{index}"},
        "source_crs": "EPSG:4326",
        "measurement_crs": "EPSG:32644",
        "measurement_type": MeasurementType.AREA,
        "measurement_value": 1234.5,
        "measurement_unit": "square_meters",
        "measurement_status": MeasurementStatus.COMPLETED,
    }
    values.update(overrides)
    return FeatureMeasurement(**values)


def test_migrations_match_models(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


@pytest.mark.parametrize(
    ("type_name", "enum_cls"),
    [
        ("file_type", FileType),
        ("file_status", FileStatus),
        ("measurement_type", MeasurementType),
        ("measurement_status", MeasurementStatus),
    ],
)
def test_postgres_enums_match_python_enums(
    migrated_engine: Engine, type_name: str, enum_cls: type
) -> None:
    """compare_metadata does not diff ENUM members, so check them explicitly."""
    with migrated_engine.connect() as connection:
        values = connection.execute(
            text(f"SELECT unnest(enum_range(NULL::{type_name}))::text")
        ).scalars()
        assert list(values) == [member.value for member in enum_cls]


def test_expected_indexes_exist(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    file_indexes = {ix["name"] for ix in inspector.get_indexes("files")}
    feature_uniques = {
        uq["name"]: uq["column_names"]
        for uq in inspector.get_unique_constraints("feature_measurements")
    }

    assert "ix_files_created_at" in file_indexes
    assert feature_uniques["uq_feature_measurements_file_id_feature_index"] == [
        "file_id",
        "feature_index",
    ]


def test_create_file_with_defaults(db_session: Session) -> None:
    file = _file()
    db_session.add(file)
    db_session.flush()
    db_session.refresh(file)

    assert file.id is not None
    assert file.status is FileStatus.PENDING
    assert file.created_at is not None
    assert file.completed_at is None
    assert file.source_crs is None


def test_file_feature_relationship_round_trip(db_session: Session) -> None:
    file = _file(status=FileStatus.COMPLETED, feature_count=2)
    file.features = [
        _measurement(1),
        _measurement(
            0,
            geometry_type="Point",
            measurement_type=None,
            measurement_value=None,
            measurement_unit=None,
            measurement_status=MeasurementStatus.NOT_REQUIRED,
        ),
    ]
    db_session.add(file)
    db_session.commit()
    db_session.expire_all()

    loaded = db_session.get(File, file.id)
    assert loaded is not None
    assert [f.feature_index for f in loaded.features] == [0, 1]
    assert loaded.features[1].properties == {"name": "parcel-1"}
    assert loaded.features[1].geometry_geojson["type"] == "Polygon"
    assert loaded.features[0].measurement_status is MeasurementStatus.NOT_REQUIRED


def test_deleting_file_cascades_to_features(db_session: Session) -> None:
    file = _file()
    file.features = [_measurement(0), _measurement(1)]
    db_session.add(file)
    db_session.flush()

    db_session.delete(file)
    db_session.flush()

    assert db_session.scalars(select(FeatureMeasurement)).all() == []


def test_feature_index_is_unique_per_file(db_session: Session) -> None:
    file = _file()
    file.features = [_measurement(0), _measurement(0)]
    db_session.add(file)
    with pytest.raises(IntegrityError, match="uq_feature_measurements_file_id_feature_index"):
        db_session.flush()


def test_measurement_value_requires_completed_status(db_session: Session) -> None:
    file = _file()
    file.features = [_measurement(0, measurement_status=MeasurementStatus.FAILED)]
    db_session.add(file)
    with pytest.raises(IntegrityError, match="value_present_iff_completed"):
        db_session.flush()


def test_new_feature_columns_round_trip(db_session: Session) -> None:
    file = _file()
    file.features = [
        _measurement(
            0,
            source_feature_id="pm-1",
            source_layer="Parcels",
            geometry_valid=False,
            geometry_repaired=True,
            display_geometry_geojson={"type": "Point", "coordinates": [78.0, 17.0]},
        )
    ]
    db_session.add(file)
    db_session.flush()
    db_session.expire_all()

    feature = db_session.scalars(select(FeatureMeasurement)).one()
    assert (feature.source_feature_id, feature.source_layer) == ("pm-1", "Parcels")
    assert feature.geometry_valid is False
    assert feature.geometry_repaired is True
    assert feature.display_geometry_geojson == {"type": "Point", "coordinates": [78.0, 17.0]}


def test_file_size_cannot_be_negative(db_session: Session) -> None:
    db_session.add(_file(file_size_bytes=-1))
    with pytest.raises(IntegrityError, match="file_size_non_negative"):
        db_session.flush()


def test_bulk_insert_batches_within_one_transaction(db_session: Session) -> None:
    file = _file()
    db_session.add(file)
    db_session.flush()
    rows = (
        {
            "file_id": file.id,
            "feature_index": index,
            "measurement_status": MeasurementStatus.NOT_REQUIRED,
            "geometry_type": "Point",
        }
        for index in range(2_345)
    )

    inserted = FeatureMeasurementRepository(db_session).bulk_insert(rows, batch_size=1_000)

    assert inserted == 2_345
    count = db_session.scalar(
        select(func.count())
        .select_from(FeatureMeasurement)
        .where(FeatureMeasurement.file_id == file.id)
    )
    assert count == 2_345
