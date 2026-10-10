"""Realistic payloads (taken from a processed KML survey) used as OpenAPI examples."""

from __future__ import annotations

from typing import Any

FILE_ID = "f34b4f73-692e-4689-9da5-a868eaa51356"

FILE: dict[str, Any] = {
    "id": FILE_ID,
    "filename": "shamshabad_field_survey.kml",
    "file_type": "KML",
    "status": "COMPLETED",
    "file_size_bytes": 10240,
    "feature_count": 27,
    "source_crs": "EPSG:4326",
    "source_crs_name": "WGS 84",
    "source_crs_assumed": False,
    "measurement_crs": "EPSG:32644",
    "measurement_crs_name": "WGS 84 / UTM zone 44N",
    "processing_error": None,
    "created_at": "2026-10-08T07:38:36.104924Z",
    "completed_at": "2026-10-08T07:38:36.351795Z",
}

SUMMARY: dict[str, Any] = {
    "total_features": 27,
    "measured_features": 21,
    "not_required_features": 6,
    "unsupported_features": 0,
    "invalid_features": 0,
    "no_geometry_features": 0,
    "crs_unavailable_features": 0,
    "failed_features": 0,
    "polygon_count": 18,
    "line_count": 3,
    "measured_polygon_count": 18,
    "measured_line_count": 3,
    "point_count": 6,
    "other_count": 0,
    "total_area_square_meters": 2138213.0911,
    "total_length_meters": 8143.6087,
}

FEATURE: dict[str, Any] = {
    "feature_index": 0,
    "source_feature_id": "plot-101",
    "source_layer": "Parcels",
    "geometry_type": "Polygon",
    "geometry_valid": True,
    "geometry_repaired": False,
    "measurement": {
        "type": "AREA",
        "value": 118707.5412,
        "unit": "square_meters",
        "area_square_km": 0.1187075412,
        "area_hectares": 11.87075412,
        "length_km": None,
        "display": "11.87 ha",
    },
    "measurement_status": "COMPLETED",
    "measurement_error": None,
    "source_crs": "EPSG:4326",
    "measurement_crs": "EPSG:32644",
    "properties": {
        "Name": "Plot 101",
        "owner": "Reddy",
        "survey_no": "330",
        "land_use": "Agricultural",
    },
}

POINT_FEATURE: dict[str, Any] = {
    **FEATURE,
    "feature_index": 21,
    "source_feature_id": None,
    "source_layer": "Borewells",
    "geometry_type": "Point",
    "geometry_valid": None,
    "measurement": None,
    "measurement_status": "NOT_REQUIRED",
    "properties": {"Name": "Borewell 1", "depth_m": "60"},
}

GEOJSON_FEATURE: dict[str, Any] = {
    "type": "Feature",
    "id": 0,
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [78.4, 17.24, 0.0],
                [78.4032, 17.2402, 0.0],
                [78.4034, 17.2431, 0.0],
                [78.4001, 17.2433, 0.0],
                [78.4, 17.24, 0.0],
            ]
        ],
    },
    "properties": FEATURE["properties"],
    "geomeasure": {
        "feature_index": 0,
        "geometry_type": "Polygon",
        "measurement_status": "COMPLETED",
        "measurement_type": "AREA",
        "measurement_value": 118707.5412,
        "measurement_unit": "square_meters",
    },
}
