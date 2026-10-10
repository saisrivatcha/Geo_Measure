from __future__ import annotations

import datetime as dt
import json
import uuid
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LinearRing, Point, Polygon

from app.geospatial.serializers import (
    geometry_to_geojson,
    serialize_properties,
    to_jsonable,
    write_feature_collection,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("text", "text"),
        (True, True),
        (np.bool_(False), False),
        (np.int64(42), 42),
        (np.int8(-3), -3),
        (np.float32(1.5), 1.5),
        (np.float64("nan"), None),
        (float("inf"), None),
        (pd.NA, None),
        (pd.NaT, None),
        (np.datetime64("NaT", "ns"), None),
        (np.datetime64("2024-03-01T10:00:00", "s"), "2024-03-01T10:00:00"),
        (pd.Timestamp("2024-03-01T10:00:00", tz="UTC"), "2024-03-01T10:00:00+00:00"),
        (dt.date(2024, 3, 1), "2024-03-01"),
        (dt.time(9, 30), "09:30:00"),
        (pd.Timedelta(minutes=2), 120.0),
        (Decimal("12.50"), 12.5),
        (b"\x00\xff", "AP8="),
        (uuid.UUID(int=1), "00000000-0000-0000-0000-000000000001"),
        ({"a": np.int16(1), 2: [np.float64(0.5), None]}, {"a": 1, "2": [0.5, None]}),
        (np.array([1, 2]), [1, 2]),
    ],
)
def test_to_jsonable(value: object, expected: object) -> None:
    result = to_jsonable(value)
    assert result == expected
    json.dumps(result, allow_nan=False)  # strictly valid JSON


def test_serialize_properties_handles_a_dataframe_row() -> None:
    frame = pd.DataFrame(
        {
            "count": pd.array([1, None], dtype="Int64"),
            "when": pd.to_datetime(["2024-01-01", None]),
            "ratio": [0.25, np.nan],
        }
    )
    rows = serialize_properties(frame.to_dict("records"))
    assert rows == [
        {"count": 1, "when": "2024-01-01T00:00:00", "ratio": 0.25},
        {"count": None, "when": None, "ratio": None},
    ]


def test_geometry_to_geojson() -> None:
    assert geometry_to_geojson(Point(1.5, 2.5)) == {"type": "Point", "coordinates": [1.5, 2.5]}
    polygon = geometry_to_geojson(Polygon([(0, 0), (1, 0), (1, 1)]))
    assert polygon["coordinates"] == [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]]


def test_linear_ring_becomes_closed_linestring() -> None:
    ring = geometry_to_geojson(LinearRing([(0, 0), (1, 0), (1, 1)]))
    assert ring["type"] == "LineString"
    assert ring["coordinates"][0] == ring["coordinates"][-1]


@pytest.mark.parametrize("geometry", [None, Polygon(), Point(float("inf"), 0)])
def test_unrepresentable_geometries_become_null(geometry: object) -> None:
    assert geometry_to_geojson(geometry) is None


def test_write_feature_collection_streams_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "out.geojson"
    features = ({"type": "Feature", "id": i, "geometry": None, "properties": {}} for i in range(3))
    write_feature_collection(path, features, {"total_features": 3})

    document = json.loads(path.read_text())
    assert document["type"] == "FeatureCollection"
    assert [f["id"] for f in document["features"]] == [0, 1, 2]
    assert document["metadata"] == {"total_features": 3}
