from __future__ import annotations

import numpy as np
import pytest
from pyproj import CRS, Transformer

from app.db.models import FileType
from app.geospatial.crs import (
    MAX_LINEAR_DISTORTION,
    crs_label,
    geographic_extent,
    resolve_source_crs,
    select_measurement_crs,
    utm_crs_for,
)
from app.geospatial.models import CRSStrategy


def bounds(*boxes: tuple[float, float, float, float]) -> np.ndarray:
    return np.array(boxes, dtype=float)


# ---- source CRS --------------------------------------------------------------------


def test_reported_crs_is_used_as_is() -> None:
    source = resolve_source_crs(CRS.from_epsg(32643), FileType.SHAPEFILE)
    assert source.label == "EPSG:32643"
    assert source.assumed is False


def test_kml_without_crs_is_wgs84_by_specification() -> None:
    source = resolve_source_crs(None, FileType.KML)
    assert source.label == "EPSG:4326"
    assert source.assumed is True


def test_shapefile_without_prj_has_no_crs() -> None:
    source = resolve_source_crs(None, FileType.SHAPEFILE)
    assert source.crs is None
    assert source.label is None
    assert source.assumed is False


def test_crs_label_prefers_authority_code_and_falls_back_to_proj() -> None:
    assert crs_label(CRS.from_wkt(CRS.from_epsg(4326).to_wkt())) == "EPSG:4326"
    custom = CRS.from_proj4("+proj=tmerc +lat_0=0 +lon_0=73 +k=1 +datum=WGS84 +units=m +type=crs")
    assert crs_label(custom).startswith("+proj=tmerc")


# ---- measurement CRS -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("lon", "lat", "expected"),
    [(78.4, 17.4, 32644), (77.9, 17.4, 32643), (-74.0, 40.7, 32618), (36.8, -1.3, 32737)],
)
def test_utm_zone_for_point(lon: float, lat: float, expected: int) -> None:
    assert utm_crs_for(lon, lat).to_epsg() == expected


def test_utm_is_undefined_near_the_poles() -> None:
    assert utm_crs_for(10.0, 86.0) is None
    assert utm_crs_for(10.0, -82.0) is None


def test_geographic_source_gets_local_utm() -> None:
    choice = select_measurement_crs(CRS.from_epsg(4326), bounds((78.40, 17.30, 78.45, 17.35)))
    assert choice.label == "EPSG:32644"
    assert choice.strategy is CRSStrategy.UTM_ZONE
    assert choice.max_linear_distortion <= MAX_LINEAR_DISTORTION


def test_dataset_straddling_zones_gets_centred_transverse_mercator() -> None:
    choice = select_measurement_crs(CRS.from_epsg(4326), bounds((71.5, 20.0, 74.5, 21.0)))
    assert choice.strategy is CRSStrategy.LOCAL_TRANSVERSE_MERCATOR
    assert "+lon_0=73" in choice.label
    assert choice.max_linear_distortion <= MAX_LINEAR_DISTORTION


def test_continental_dataset_falls_back_to_equal_area() -> None:
    choice = select_measurement_crs(CRS.from_epsg(4326), bounds((68.0, 8.0, 97.0, 35.0)))
    assert choice.strategy is CRSStrategy.LOCAL_EQUAL_AREA
    assert choice.label.startswith("+proj=laea")


def test_antimeridian_dataset_is_centred_correctly() -> None:
    fiji = bounds((179.5, -17.0, 179.9, -16.0), (-179.9, -17.0, -179.5, -16.0))
    extent = geographic_extent(CRS.from_epsg(4326), fiji)
    assert extent.east - extent.west == pytest.approx(1.0)  # not 359.4 degrees
    choice = select_measurement_crs(CRS.from_epsg(4326), fiji)
    assert choice.max_linear_distortion <= MAX_LINEAR_DISTORTION


@pytest.mark.parametrize(
    ("epsg", "box"),
    [
        (32644, (200_000, 1_880_000, 210_000, 1_890_000)),  # UTM in metres
        (27700, (400_000, 300_000, 410_000, 310_000)),  # British National Grid
        (2229, (6_480_000, 1_840_000, 6_490_000, 1_850_000)),  # US survey feet
    ],
)
def test_suitable_projected_source_is_used_directly(epsg: int, box: tuple) -> None:
    choice = select_measurement_crs(CRS.from_epsg(epsg), bounds(box))
    assert choice.label == f"EPSG:{epsg}"
    assert choice.strategy is CRSStrategy.SOURCE_PROJECTED


@pytest.mark.parametrize("epsg", [3857, 4087])  # Web Mercator, World Equidistant Cylindrical
def test_distorting_projected_source_is_replaced(epsg: int) -> None:
    source = CRS.from_epsg(epsg)
    x0, y0 = Transformer.from_crs(4326, source, always_xy=True).transform(78.40, 17.30)
    x1, y1 = Transformer.from_crs(4326, source, always_xy=True).transform(78.45, 17.35)
    choice = select_measurement_crs(source, bounds((x0, y0, x1, y1)))
    assert choice.label == "EPSG:32644"
    assert choice.strategy is CRSStrategy.UTM_ZONE


def test_utm_zone_far_from_the_data_is_replaced() -> None:
    """Data stored in zone 43 but located 9 deg east of its central meridian."""
    to_zone43 = Transformer.from_crs(4326, 32643, always_xy=True)
    x0, y0 = to_zone43.transform(84.0, 20.0)
    x1, y1 = to_zone43.transform(84.1, 20.1)
    choice = select_measurement_crs(CRS.from_epsg(32643), bounds((x0, y0, x1, y1)))
    assert choice.label == "EPSG:32645"


def test_no_extent_means_no_measurement_crs() -> None:
    assert select_measurement_crs(CRS.from_epsg(4326), np.empty((0, 4))) is None
