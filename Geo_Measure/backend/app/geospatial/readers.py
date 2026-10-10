"""Read KML and Shapefile datasets into GeoDataFrames via GeoPandas/Pyogrio (GDAL).

Every reader returns a GeoDataFrame with a fresh ``RangeIndex`` (the
deterministic, zero-based ``feature_index``), the ``geometry`` column, and the
reserved columns from :mod:`app.geospatial.models`:

* ``__source_layer``      - KML folder / Shapefile layer name;
* ``__source_feature_id`` - an identifier from the source when it is reliable;
* ``__properties``        - the feature's attributes, already JSON-safe.

The frame's ``crs`` is exactly what GDAL reported (possibly ``None``); applying
format rules such as "KML is WGS 84" is :mod:`app.geospatial.crs`'s job.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
from pyogrio.errors import DataLayerError, DataSourceError

from app.exceptions import DatasetReadError, EmptyDatasetError
from app.geospatial.archive import extract_shapefile_bundle
from app.geospatial.models import (
    PROPERTIES_COLUMN,
    SOURCE_FEATURE_ID_COLUMN,
    SOURCE_LAYER_COLUMN,
)
from app.geospatial.serializers import serialize_properties
from app.geospatial.validators import FileValidator

logger = logging.getLogger(__name__)

# LIBKML exposes KML styling/rendering state as fields. They describe how
# Google Earth draws a placemark, not the feature's data, so they are dropped.
KML_RENDERING_FIELDS = frozenset(
    {"altitudeMode", "tessellate", "extrude", "visibility", "drawOrder", "icon", "snippet"}
)
KML_ID_FIELD = "id"

_READ_ERRORS = (DataSourceError, DataLayerError, RuntimeError, ValueError)


def read_kml(path: Path) -> gpd.GeoDataFrame:
    """Read every layer (KML folder) of a KML document, in document order.

    ``source_feature_id`` is the Placemark ``id`` attribute when present; KML
    has no other stable identifier (GDAL FIDs are per layer and synthetic).
    """
    try:
        layers = pyogrio.list_layers(path)
    except _READ_ERRORS as exc:
        raise DatasetReadError("The KML document could not be read.") from exc

    frames = [
        _read_kml_layer(path, layer_index, str(layer_name))
        for layer_index, (layer_name, _geometry_type) in enumerate(layers)
    ]
    frames = [frame for frame in frames if len(frame)]
    if not frames:
        raise EmptyDatasetError("The KML document contains no placemarks.")
    return _concat(frames)


def read_shapefile_zip(
    path: Path, destination: Path, *, validator: FileValidator
) -> gpd.GeoDataFrame:
    """Safely extract the single Shapefile in ``path`` into ``destination`` and read it.

    The archive is inspected first (paths, required ``.shp``/``.shx``/``.dbf``,
    exactly one dataset); only the matching components are extracted, so the
    ``.prj`` used is the one belonging to that ``.shp``. A missing ``.prj``
    yields ``crs=None``. ``source_feature_id`` is the Shapefile record number
    (GDAL FID), which is stable for a given file.
    """
    bundle = validator.inspect_shapefile_archive(path)
    components = extract_shapefile_bundle(
        path, bundle, destination, max_extracted_bytes=validator.max_extracted_bytes
    )
    shp_path = components[".shp"]
    try:
        frame = pyogrio.read_dataframe(shp_path, fid_as_index=True)
    except _READ_ERRORS as exc:
        raise DatasetReadError("The Shapefile could not be read.") from exc

    if frame.empty:
        raise EmptyDatasetError("The Shapefile contains no features.")

    logger.info(
        "dataset.read",
        extra={"format": "shapefile", "features": len(frame), "has_prj": bundle.has_prj},
    )
    return _with_reader_columns(
        frame,
        layer_name=bundle.stem,
        feature_ids=[str(fid) for fid in frame.index],
        attributes=frame.drop(columns=frame.geometry.name),
    )


def _read_kml_layer(path: Path, layer_index: int, layer_name: str) -> gpd.GeoDataFrame:
    try:
        frame = pyogrio.read_dataframe(path, layer=layer_index)
    except _READ_ERRORS as exc:
        raise DatasetReadError(
            f"KML folder '{layer_name}' could not be read.", details={"layer": layer_name}
        ) from exc
    if frame.empty:
        return frame

    attributes = frame.drop(columns=frame.geometry.name)
    feature_ids: list[str | None] = [None] * len(frame)
    if KML_ID_FIELD in attributes.columns:
        feature_ids = [_clean_id(value) for value in attributes[KML_ID_FIELD]]
        attributes = attributes.drop(columns=KML_ID_FIELD)

    attributes = attributes.drop(
        columns=[c for c in attributes.columns if c in KML_RENDERING_FIELDS]
    )
    # LIBKML adds the union of all ExtendedData fields of the layer; a column that
    # is empty for every placemark carries no information.
    attributes = attributes.dropna(axis="columns", how="all")

    logger.info(
        "dataset.read",
        extra={"format": "kml", "layer": layer_name, "features": len(frame)},
    )
    return _with_reader_columns(
        frame, layer_name=layer_name, feature_ids=feature_ids, attributes=attributes
    )


def _with_reader_columns(
    frame: gpd.GeoDataFrame,
    *,
    layer_name: str,
    feature_ids: list[str | None],
    attributes: pd.DataFrame,
) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            SOURCE_LAYER_COLUMN: [layer_name] * len(frame),
            SOURCE_FEATURE_ID_COLUMN: feature_ids,
            PROPERTIES_COLUMN: serialize_properties(attributes.to_dict("records")),
        },
        geometry=frame.geometry.to_numpy(),
        crs=frame.crs,
    )


def _concat(frames: list[gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
    """Concatenate layers in order; layers in another CRS are reprojected to the first."""
    target = next((frame.crs for frame in frames if frame.crs is not None), None)
    aligned = [
        frame.to_crs(target) if target is not None and frame.crs not in (None, target) else frame
        for frame in frames
    ]
    combined = pd.concat(aligned, ignore_index=True)
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=target)


def _clean_id(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text[:255] or None
