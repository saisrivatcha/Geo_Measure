"""Measurement engine correctness.

Reference values come from closed-form geometry in metric CRSs, and from
pyproj's ellipsoidal (geodesic) calculations on WGS 84 for lon/lat inputs -
the ground truth any projected measurement must agree with.
"""

from __future__ import annotations

import math

import geopandas as gpd
import pytest
import shapely
from pyproj import CRS, Geod
from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from app.db.models import MeasurementStatus, MeasurementType, MeasurementUnit
from app.geospatial.measurements import MeasurementEngine
from app.geospatial.models import CRSStrategy
from tests.factories import square

GEOD = Geod(ellps="WGS84")
# ~1.1 km x 1.1 km parcel near Hyderabad, India.
HYDERABAD_PARCEL = square(78.4800, 17.3800, 0.01)


def measure(geometries: list, crs: object) -> tuple:
    frame = gpd.GeoDataFrame(geometry=geometries, crs=crs)
    outcome = MeasurementEngine().measure(frame)
    return outcome.results, outcome.measurement_crs


def geodesic_area(polygon: Polygon) -> float:
    area, _ = GEOD.geometry_area_perimeter(polygon)
    return abs(area)


# ---- the critical guarantee -----------------------------------------------------


def test_geographic_polygon_is_not_measured_in_degrees() -> None:
    """A WGS 84 polygon must be projected before its area is computed.

    Its planar area in degrees is 0.0001 "square degrees"; the true area is
    about 1.18 km². A degree-based implementation would return the former (or
    a value off by orders of magnitude); this one must return square metres
    computed in a projected CRS that differs from the source CRS.
    """
    (result,), measurement_crs = measure([HYDERABAD_PARCEL], "EPSG:4326")

    assert measurement_crs is not None
    assert measurement_crs.crs.is_projected
    assert measurement_crs.label != "EPSG:4326"
    assert result.status is MeasurementStatus.COMPLETED
    assert result.measurement_type is MeasurementType.AREA
    assert result.unit is MeasurementUnit.SQUARE_METERS

    degree_area = HYDERABAD_PARCEL.area
    assert degree_area == pytest.approx(1e-4)
    assert result.value > 1_000_000 * degree_area  # nowhere near degree units
    assert result.value == pytest.approx(geodesic_area(HYDERABAD_PARCEL), rel=1e-3)


def test_utm_zone_follows_the_data_not_a_constant() -> None:
    _, hyderabad = measure([HYDERABAD_PARCEL], "EPSG:4326")
    _, new_york = measure([square(-74.00, 40.70, 0.01)], "EPSG:4326")
    _, nairobi = measure([square(36.80, -1.30, 0.01)], "EPSG:4326")

    assert hyderabad.label == "EPSG:32644"
    assert new_york.label == "EPSG:32618"
    assert nairobi.label == "EPSG:32737"  # southern hemisphere
    assert {hyderabad.strategy, new_york.strategy, nairobi.strategy} == {CRSStrategy.UTM_ZONE}


@pytest.mark.parametrize(
    "polygon",
    [
        square(-0.1300, 51.5000, 0.02),  # London
        square(151.2000, -33.8700, 0.02),  # Sydney
        square(-70.6500, -33.4500, 0.02),  # Santiago
        square(18.0000, 69.6000, 0.05),  # Tromsø, high latitude
        Polygon([(72.0, 20.0), (74.5, 20.0), (74.5, 21.0), (72.0, 21.0)]),  # spans 2 UTM zones
    ],
)
def test_area_matches_geodesic_reference_worldwide(polygon: Polygon) -> None:
    (result,), _ = measure([polygon], "EPSG:4326")
    assert result.value == pytest.approx(geodesic_area(polygon), rel=2e-3)


def test_line_length_matches_geodesic_reference() -> None:
    line = LineString([(78.40, 17.30), (78.45, 17.36), (78.52, 17.40)])
    (result,), measurement_crs = measure([line], "EPSG:4326")

    assert result.measurement_type is MeasurementType.LENGTH
    assert result.unit is MeasurementUnit.METERS
    assert measurement_crs.label != "EPSG:4326"
    assert result.value == pytest.approx(GEOD.geometry_length(line), rel=1e-3)


# ---- known values in metric CRSs --------------------------------------------------


def test_known_polygon_area_in_projected_crs() -> None:
    rectangle = Polygon(
        [(500_000, 1_900_000), (500_100, 1_900_000), (500_100, 1_900_050), (500_000, 1_900_050)]
    )
    (result,), measurement_crs = measure([rectangle], "EPSG:32644")

    assert measurement_crs.label == "EPSG:32644"
    assert measurement_crs.strategy is CRSStrategy.SOURCE_PROJECTED
    assert result.value == pytest.approx(5_000.0, abs=1e-6)


def test_polygon_with_hole() -> None:
    outer = [(500_000, 1_900_000), (500_100, 1_900_000), (500_100, 1_900_100), (500_000, 1_900_100)]
    hole = [(500_040, 1_900_040), (500_060, 1_900_040), (500_060, 1_900_060), (500_040, 1_900_060)]
    (result,), _ = measure([Polygon(outer, [hole])], "EPSG:32644")
    assert result.value == pytest.approx(10_000 - 400)


def test_known_line_length_in_projected_crs() -> None:
    line = LineString([(500_000, 1_900_000), (500_300, 1_900_400)])  # 3-4-5 triangle
    (result,), _ = measure([line], "EPSG:32644")
    assert result.value == pytest.approx(500.0)


def test_multipolygon_area_is_sum_of_parts() -> None:
    parts = [square(500_000, 1_900_000, 100), square(501_000, 1_900_000, 20)]
    (result,), _ = measure([MultiPolygon(parts)], "EPSG:32644")
    assert result.measurement_type is MeasurementType.AREA
    assert result.value == pytest.approx(10_000 + 400)


def test_multilinestring_length_is_sum_of_parts() -> None:
    lines = MultiLineString(
        [[(500_000, 1_900_000), (500_100, 1_900_000)], [(500_000, 1_901_000), (500_000, 1_901_250)]]
    )
    (result,), _ = measure([lines], "EPSG:32644")
    assert result.measurement_type is MeasurementType.LENGTH
    assert result.value == pytest.approx(350.0)


def test_linear_ring_is_measured_as_a_line() -> None:
    ring = LinearRing([(500_000, 1_900_000), (500_100, 1_900_000), (500_100, 1_900_100)])
    (result,), _ = measure([ring], "EPSG:32644")
    assert result.measurement_type is MeasurementType.LENGTH
    assert result.value == pytest.approx(200 + 100 * 2**0.5)


def test_us_survey_feet_are_converted_to_square_meters() -> None:
    # 1000 ft x 1000 ft in California zone 5 (US survey feet).
    plot = square(6_480_000, 1_840_000, 1_000)
    (result,), measurement_crs = measure([plot], "EPSG:2229")

    metres_per_us_foot = 1200 / 3937
    assert measurement_crs.label == "EPSG:2229"
    assert measurement_crs.metres_per_unit == pytest.approx(metres_per_us_foot)
    assert result.unit is MeasurementUnit.SQUARE_METERS
    assert result.value == pytest.approx((1_000 * metres_per_us_foot) ** 2)


def test_distorted_projected_source_is_reprojected() -> None:
    """Web Mercator inflates areas by ~9 % at 17 deg N; it must not be used."""
    web_mercator = gpd.GeoSeries([HYDERABAD_PARCEL], crs=4326).to_crs(3857).iloc[0]
    (result,), measurement_crs = measure([web_mercator], "EPSG:3857")

    assert measurement_crs.label == "EPSG:32644"
    # Mercator's areal scale is sec²(latitude): about 1.10 here.
    assert web_mercator.area / result.value == pytest.approx(
        1 / math.cos(math.radians(17.385)) ** 2, rel=0.01
    )
    assert result.value == pytest.approx(geodesic_area(HYDERABAD_PARCEL), rel=1e-3)


# ---- statuses for non-measurable features --------------------------------------------


def test_points_need_no_measurement() -> None:
    results, measurement_crs = measure(
        [Point(78.4, 17.3), MultiPoint([(78, 17), (79, 18)])], "EPSG:4326"
    )
    assert [r.status for r in results] == [MeasurementStatus.NOT_REQUIRED] * 2
    assert all(r.value is None and r.unit is None and r.measurement_type is None for r in results)
    assert measurement_crs is None  # nothing was measured


def test_geometry_collection_is_not_supported() -> None:
    collection = GeometryCollection([Point(78.4, 17.3), LineString([(78.4, 17.3), (78.5, 17.4)])])
    (result,), _ = measure([collection], "EPSG:4326")
    assert result.status is MeasurementStatus.NOT_SUPPORTED
    assert result.value is None


def test_null_and_empty_geometries() -> None:
    results, _ = measure([None, Polygon()], "EPSG:4326")
    assert [r.status for r in results] == [MeasurementStatus.NO_GEOMETRY] * 2


def test_self_intersecting_polygon_is_repaired_before_measuring() -> None:
    # Bow-tie: two 50 m x 100 m triangles. Its naive (signed) area is 0.
    bowtie = Polygon(
        [(500_000, 1_900_000), (500_100, 1_900_100), (500_100, 1_900_000), (500_000, 1_900_100)]
    )
    assert not bowtie.is_valid
    assert bowtie.area == 0

    (result,), _ = measure([bowtie], "EPSG:32644")

    assert result.status is MeasurementStatus.COMPLETED
    assert result.geometry_valid is False
    assert result.geometry_repaired is True
    assert result.value == pytest.approx(5_000.0)


def test_unrepairable_geometry_does_not_stop_other_features() -> None:
    collapsed = Polygon([(500_000, 1_900_000), (500_100, 1_900_000), (500_200, 1_900_000)])
    degenerate_line = shapely.from_wkt("LINESTRING (500000 1900000, 500000 1900000)")
    good = square(500_000, 1_900_000, 10)

    bad_polygon, bad_line, ok = measure([collapsed, degenerate_line, good], "EPSG:32644")[0]

    assert bad_polygon.status is MeasurementStatus.INVALID_GEOMETRY
    assert bad_polygon.value is None
    assert bad_polygon.geometry_valid is False
    assert "could not be repaired" in bad_polygon.error
    assert bad_line.status is MeasurementStatus.INVALID_GEOMETRY
    assert ok.status is MeasurementStatus.COMPLETED
    assert ok.geometry_valid is True and ok.geometry_repaired is False
    assert ok.value == pytest.approx(100.0)


def test_missing_crs_is_never_measured() -> None:
    results, measurement_crs = measure(
        [square(500_000, 1_900_000, 100), LineString([(0, 0), (1, 1)]), Point(0, 0)], None
    )
    assert measurement_crs is None
    assert [r.status for r in results] == [
        MeasurementStatus.CRS_UNAVAILABLE,
        MeasurementStatus.CRS_UNAVAILABLE,
        MeasurementStatus.NOT_REQUIRED,
    ]
    assert all(r.value is None for r in results)


def test_coordinates_outside_geographic_range_fail_without_affecting_others() -> None:
    # Projected metres mislabelled as EPSG:4326 - a classic broken .prj.
    mislabelled = square(500_000, 1_900_000, 100)
    results, measurement_crs = measure([mislabelled, HYDERABAD_PARCEL], "EPSG:4326")

    assert results[0].status is MeasurementStatus.FAILED
    assert "outside the valid" in results[0].error
    assert results[1].status is MeasurementStatus.COMPLETED
    assert measurement_crs.label == "EPSG:32644"  # extent ignores the bad feature


def test_results_stay_aligned_with_input_order() -> None:
    geometries = [
        Point(78.48, 17.38),
        HYDERABAD_PARCEL,
        None,
        LineString([(78.48, 17.38), (78.49, 17.39)]),
        GeometryCollection([Point(78.48, 17.38)]),
    ]
    results, _ = measure(geometries, "EPSG:4326")
    assert [r.status for r in results] == [
        MeasurementStatus.NOT_REQUIRED,
        MeasurementStatus.COMPLETED,
        MeasurementStatus.NO_GEOMETRY,
        MeasurementStatus.COMPLETED,
        MeasurementStatus.NOT_SUPPORTED,
    ]
    assert results[1].measurement_type is MeasurementType.AREA
    assert results[3].measurement_type is MeasurementType.LENGTH


def test_engine_works_with_non_wgs84_geographic_crs() -> None:
    # NAD83 (EPSG:4269) lon/lat over Denver.
    parcel = square(-104.99, 39.74, 0.01)
    (result,), measurement_crs = measure([parcel], CRS.from_epsg(4269))
    assert measurement_crs.label == "EPSG:32613"
    assert result.value == pytest.approx(geodesic_area(parcel), rel=1e-3)
