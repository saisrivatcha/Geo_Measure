"""Orchestrates one dataset from a stored upload to per-feature results.

    validate content -> read -> resolve source CRS -> measure (validity, metric
    CRS, area/length) -> display geometry (EPSG:4326) -> JSON serialisation

The processor is pure computation over files on disk: it never touches the
database and raises :class:`app.exceptions.AppError` subclasses with
user-safe messages for anything wrong with the dataset.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry.base import BaseGeometry

from app.db.models.enums import FileType
from app.geospatial.crs import DISPLAY_CRS, is_display_crs, resolve_source_crs
from app.geospatial.measurements import MeasurementEngine
from app.geospatial.models import (
    PROPERTIES_COLUMN,
    SOURCE_FEATURE_ID_COLUMN,
    SOURCE_LAYER_COLUMN,
    ProcessedFeature,
    ProcessingResult,
    SourceCRS,
)
from app.geospatial.readers import read_kml, read_shapefile_zip
from app.geospatial.serializers import geometry_to_geojson
from app.geospatial.validators import FileValidator

logger = logging.getLogger(__name__)


class GeospatialProcessor:
    def __init__(self, validator: FileValidator, engine: MeasurementEngine | None = None) -> None:
        self.validator = validator
        self.engine = engine or MeasurementEngine()

    def process(self, path: Path, file_type: FileType, extraction_dir: Path) -> ProcessingResult:
        """Process the stored upload at ``path``.

        ``extraction_dir`` receives Shapefile components; the caller owns its
        lifecycle (it is deleted after processing).
        """
        self.validator.validate_size(path.stat().st_size)
        frame = self._read(path, file_type, extraction_dir)

        source_crs = resolve_source_crs(frame.crs, file_type)
        if source_crs.crs is not None and frame.crs is None:
            frame = frame.set_crs(source_crs.crs)
        logger.info(
            "dataset.crs_discovered",
            extra={
                "source_crs": source_crs.label,
                "assumed": source_crs.assumed,
                "features": len(frame),
            },
        )

        outcome = self.engine.measure(frame)
        display = _display_geometries(frame, source_crs)
        source_geometries = frame.geometry.to_numpy()
        # pd.concat turns None into NaN in object columns; restore None.
        feature_ids = [_none_if_missing(value) for value in frame[SOURCE_FEATURE_ID_COLUMN]]
        layers = [_none_if_missing(value) for value in frame[SOURCE_LAYER_COLUMN]]
        properties = frame[PROPERTIES_COLUMN].tolist()

        features = [
            ProcessedFeature(
                feature_index=index,
                source_feature_id=feature_ids[index],
                source_layer=layers[index],
                geometry_type=_geometry_type(geometry),
                geometry=geometry_to_geojson(geometry),
                display_geometry=geometry_to_geojson(display[index]),
                properties=properties[index],
                measurement=outcome.results[index],
            )
            for index, geometry in enumerate(source_geometries)
        ]
        return ProcessingResult(
            source_crs=source_crs, measurement_crs=outcome.measurement_crs, features=features
        )

    def _read(self, path: Path, file_type: FileType, extraction_dir: Path) -> gpd.GeoDataFrame:
        """Content validation always precedes GDAL: the KML is checked for
        well-formedness here, the ZIP's central directory inside the reader."""
        if file_type is FileType.KML:
            self.validator.validate_kml(path)
            return read_kml(path)
        return read_shapefile_zip(path, extraction_dir, validator=self.validator)


def _display_geometries(frame: gpd.GeoDataFrame, source_crs: SourceCRS) -> np.ndarray:
    """Geometries in EPSG:4326 for map rendering; all ``None`` without a CRS.

    The source geometries are left untouched; this is a separate, reprojected copy.
    """
    if source_crs.crs is None:
        return np.full(len(frame), None, dtype=object)
    if is_display_crs(source_crs.crs):
        return frame.geometry.to_numpy()
    return frame.geometry.to_crs(DISPLAY_CRS).to_numpy()


def _geometry_type(geometry: BaseGeometry | None) -> str | None:
    return None if geometry is None else geometry.geom_type


def _none_if_missing(value: object) -> str | None:
    return None if value is None or pd.isna(value) else str(value)
