"""Conversion of attribute values and geometries into strict JSON.

PostgreSQL ``JSONB`` and RFC 8259 reject NaN/Infinity, numpy scalars, pandas
timestamps, bytes, decimals and so on. Every value that leaves the geospatial
package goes through :func:`to_jsonable` or :func:`geometry_to_geojson`.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import math
import uuid
from collections.abc import Iterable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]


def to_jsonable(value: Any) -> JSONValue:
    """Convert one attribute value into a JSON-compatible value.

    Missing values (None, NaN, NaT, pd.NA) and non-finite floats become ``null``;
    temporal values become ISO 8601 strings; numpy scalars become Python scalars;
    bytes become base64; anything unrecognised falls back to ``str()``.
    """
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, bool | np.bool_):
        return bool(value)
    if isinstance(value, int | np.integer):
        return int(value)
    if isinstance(value, float | np.floating):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else None
    if isinstance(value, str):
        return value
    if isinstance(value, pd.Timestamp | dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, np.datetime64):
        return None if np.isnat(value) else pd.Timestamp(value).isoformat()
    if isinstance(value, pd.Timedelta | dt.timedelta):
        return value.total_seconds()
    if isinstance(value, bytes | bytearray | memoryview):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return [to_jsonable(item) for item in value.tolist()]
    if isinstance(value, list | tuple | set | frozenset):
        return [to_jsonable(item) for item in value]
    if isinstance(value, BaseGeometry):
        return geometry_to_geojson(value)
    return str(value)


def serialize_properties(records: Iterable[Mapping[Any, Any]]) -> list[dict[str, JSONValue]]:
    """Serialise attribute rows (e.g. ``frame.to_dict("records")``)."""
    return [{str(key): to_jsonable(value) for key, value in row.items()} for row in records]


def geometry_to_geojson(geometry: BaseGeometry | None) -> dict[str, Any] | None:
    """GeoJSON geometry dict, or ``None`` for null, empty or non-finite geometries.

    ``LinearRing`` has no GeoJSON equivalent and is emitted as a closed
    ``LineString``.
    """
    if geometry is None or geometry.is_empty:
        return None
    if not np.isfinite(shapely.bounds(geometry)).all():
        return None
    if geometry.geom_type == "LinearRing":
        geometry = shapely.LineString(geometry.coords)
    return _listify(mapping(geometry))


def _listify(value: Any) -> Any:
    """Shapely's mapping uses tuples; JSON (and equality in tests) prefers lists."""
    if isinstance(value, dict):
        return {key: _listify(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_listify(item) for item in value]
    return value


def write_feature_collection(
    path: Path, features: Iterable[Mapping[str, Any]], metadata: Mapping[str, Any]
) -> None:
    """Stream a FeatureCollection to ``path`` one feature at a time.

    Avoids building the whole document in memory for large datasets.
    """
    with path.open("w", encoding="utf-8") as handle:
        handle.write('{"type": "FeatureCollection", "metadata": ')
        handle.write(json.dumps(metadata, allow_nan=False))
        handle.write(', "features": [')
        for position, feature in enumerate(features):
            if position:
                handle.write(",")
            handle.write("\n")
            handle.write(json.dumps(feature, allow_nan=False))
        handle.write("\n]}\n")
