"""Coordinate reference system handling.

Two decisions live here and nowhere else:

1. **Source CRS** (:func:`resolve_source_crs`). The CRS reported by GDAL is
   used as-is. The single exception is KML: OGC KML 2.2 defines coordinates as
   WGS 84 longitude/latitude, so a KML layer with no CRS is assigned EPSG:4326
   and flagged ``assumed=True``. A Shapefile without ``.prj`` gets *no* CRS -
   its coordinates could be in any unit, and guessing would invent numbers.

2. **Measurement CRS** (:func:`select_measurement_crs`). Area and length are
   never computed on longitude/latitude degrees. Candidates are tried in order
   and the first whose scale distortion across the dataset's extent is within
   :data:`MAX_LINEAR_DISTORTION` wins:

   a. the source CRS, if it is projected with a linear unit convertible to metres;
   b. the WGS 84 UTM zone containing the centre of the dataset;
   c. a Transverse Mercator centred on the dataset (fixes datasets straddling
      a UTM zone boundary);
   d. otherwise a Lambert Azimuthal Equal-Area centred on the dataset. Areas
      stay exact at any extent; lengths on continent-scale datasets carry the
      reported distortion.

   Distortion is measured with PROJ's Tissot indicatrix (``Proj.get_factors``)
   at nine points across the extent, so an unsuitable projected source - Web
   Mercator, plate carrée, a UTM zone far from the data - is detected from the
   projection's actual behaviour rather than from a hard-coded list.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from pyproj import CRS, Proj, Transformer
from pyproj.exceptions import CRSError

from app.db.models.enums import FileType
from app.geospatial.models import CRSStrategy, MeasurementCRS, SourceCRS

logger = logging.getLogger(__name__)

WGS84 = CRS.from_epsg(4326)
DISPLAY_CRS = WGS84
DISPLAY_CRS_LABEL = "EPSG:4326"

# KML 2.2 (OGC 07-147r2, section 6.2): coordinates are WGS 84 lon/lat/alt.
KML_IMPLIED_CRS = WGS84

# 0.1 %: the scale error of a UTM zone at its edge near the equator. A
# 1 km line is off by at most 1 m; areas by at most ~0.2 %.
MAX_LINEAR_DISTORTION = 1e-3

UTM_MIN_LATITUDE = -80.0
UTM_MAX_LATITUDE = 84.0


@dataclass(frozen=True, slots=True)
class GeographicExtent:
    """Lon/lat extent. ``east`` may exceed 180 when the data crosses the antimeridian."""

    west: float
    south: float
    east: float
    north: float

    @property
    def center_lon(self) -> float:
        return float(_normalize_lon((self.west + self.east) / 2))

    @property
    def center_lat(self) -> float:
        return (self.south + self.north) / 2

    def sample_points(self) -> tuple[np.ndarray, np.ndarray]:
        """A 3x3 grid over the extent (corners, edge midpoints, centre)."""
        lons, lats = np.meshgrid(
            np.linspace(self.west, self.east, 3),
            np.clip(np.linspace(self.south, self.north, 3), -89.9, 89.9),
        )
        return _normalize_lon(lons.ravel()), lats.ravel()


# ---- labels -------------------------------------------------------------------


def crs_label(crs: CRS) -> str:
    """Short identifier for storage and display: ``EPSG:32644`` when an authority
    code matches confidently, otherwise a PROJ string."""
    authority = crs.to_authority(min_confidence=70)
    if authority:
        return f"{authority[0]}:{authority[1]}"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # "may lose information"
        try:
            return crs.to_proj4()
        except CRSError:
            return crs.name


@lru_cache(maxsize=512)
def describe_crs(label: str | None) -> str | None:
    """Human-readable name for a stored CRS label, e.g. ``WGS 84 / UTM zone 43N``.

    Dataset-centred CRSs built by :func:`select_measurement_crs` have no
    registered name, so they are described by their projection method.
    """
    if not label:
        return None
    try:
        crs = CRS.from_user_input(label)
    except CRSError:
        return None
    if crs.name and crs.name.lower() != "unknown":
        return crs.name
    operation = crs.coordinate_operation
    if operation is not None:
        return f"{operation.method_name} (centred on dataset, WGS 84)"
    return None


def is_display_crs(crs: CRS) -> bool:
    return crs.equals(DISPLAY_CRS, ignore_axis_order=True)


# ---- source CRS -----------------------------------------------------------------


def resolve_source_crs(crs: CRS | None, file_type: FileType) -> SourceCRS:
    if crs is not None:
        return SourceCRS(crs=crs, label=crs_label(crs), assumed=False)
    if file_type is FileType.KML:
        logger.info("crs.assumed", extra={"crs": "EPSG:4326", "reason": "KML 2.2 mandates WGS 84"})
        return SourceCRS(crs=KML_IMPLIED_CRS, label=crs_label(KML_IMPLIED_CRS), assumed=True)
    return SourceCRS(crs=None, label=None, assumed=False)


def is_measurable_crs(crs: CRS) -> bool:
    horizontal = _horizontal(crs)
    return horizontal.is_geographic or horizontal.is_projected


# ---- measurement CRS ------------------------------------------------------------


def select_measurement_crs(source: CRS, bounds: np.ndarray) -> MeasurementCRS | None:
    """Choose a metric CRS for the geometries whose per-feature ``bounds``
    (n x 4, in ``source`` coordinates) are given. ``None`` if there is no extent."""
    horizontal = _horizontal(source)
    extent = geographic_extent(horizontal, bounds)
    if extent is None:
        return None

    for candidate in _candidates(horizontal, extent):
        if candidate.max_linear_distortion <= MAX_LINEAR_DISTORTION:
            _log_choice(candidate, extent)
            return candidate

    fallback = _measurement_crs(_local_equal_area(extent), CRSStrategy.LOCAL_EQUAL_AREA, extent)
    logger.warning(
        "crs.measurement_wide_extent",
        extra={
            "measurement_crs": fallback.label,
            "max_linear_distortion": fallback.max_linear_distortion,
            "note": "areas exact (equal-area); lengths carry the reported distortion",
        },
    )
    return fallback


def geographic_extent(crs: CRS, bounds: np.ndarray) -> GeographicExtent | None:
    """Lon/lat extent of per-feature ``bounds`` given in ``crs``."""
    bounds = np.asarray(bounds, dtype=float).reshape(-1, 4)
    bounds = bounds[np.isfinite(bounds).all(axis=1)]
    if not len(bounds):
        return None

    if crs.is_geographic:
        return _extent_from_lonlat_bounds(bounds)

    transformer = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
    west, south, east, north = transformer.transform_bounds(
        bounds[:, 0].min(),
        bounds[:, 1].min(),
        bounds[:, 2].max(),
        bounds[:, 3].max(),
        densify_pts=21,
    )
    if not np.isfinite([west, south, east, north]).all():
        return None
    if east < west:  # crosses the antimeridian
        east += 360.0
    return GeographicExtent(west, south, east, north)


def _extent_from_lonlat_bounds(bounds: np.ndarray) -> GeographicExtent:
    """Smallest longitude span, considering that data may cross the antimeridian.

    Features lying entirely west of 0 deg are shifted by +360 deg; if that yields a
    narrower span (e.g. a Fiji dataset at +179 / -179) the shifted frame is used.
    """
    minx, miny, maxx, maxy = bounds.T
    south, north = float(miny.min()), float(maxy.max())
    west, east = float(minx.min()), float(maxx.max())

    shift = np.where(maxx < 0, 360.0, 0.0)
    shifted_west, shifted_east = float((minx + shift).min()), float((maxx + shift).max())
    if shifted_east - shifted_west < east - west:
        west, east = shifted_west, shifted_east
    return GeographicExtent(west, south, east, north)


def _candidates(source: CRS, extent: GeographicExtent) -> list[MeasurementCRS]:
    candidates: list[MeasurementCRS] = []
    if source.is_projected and _metres_per_unit(source) is not None:
        candidates.append(_measurement_crs(source, CRSStrategy.SOURCE_PROJECTED, extent))

    utm = utm_crs_for(extent.center_lon, extent.center_lat)
    if utm is not None:
        candidates.append(_measurement_crs(utm, CRSStrategy.UTM_ZONE, extent))

    candidates.append(
        _measurement_crs(
            _local_transverse_mercator(extent), CRSStrategy.LOCAL_TRANSVERSE_MERCATOR, extent
        )
    )
    return candidates


def utm_crs_for(lon: float, lat: float) -> CRS | None:
    """WGS 84 UTM zone (EPSG:326xx north / 327xx south) containing the point."""
    if not UTM_MIN_LATITUDE <= lat <= UTM_MAX_LATITUDE:
        return None
    zone = int((_normalize_lon(lon) + 180.0) // 6.0) % 60 + 1
    return CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)


def _local_transverse_mercator(extent: GeographicExtent) -> CRS:
    return CRS.from_proj4(
        f"+proj=tmerc +lat_0=0 +lon_0={extent.center_lon:.6f} +k=1 +x_0=0 +y_0=0 "
        "+datum=WGS84 +units=m +no_defs +type=crs"
    )


def _local_equal_area(extent: GeographicExtent) -> CRS:
    return CRS.from_proj4(
        f"+proj=laea +lat_0={extent.center_lat:.6f} +lon_0={extent.center_lon:.6f} "
        "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs"
    )


def _measurement_crs(crs: CRS, strategy: CRSStrategy, extent: GeographicExtent) -> MeasurementCRS:
    return MeasurementCRS(
        crs=crs,
        label=crs_label(crs),
        strategy=strategy,
        metres_per_unit=_metres_per_unit(crs) or 1.0,
        max_linear_distortion=max_linear_distortion(crs, extent),
    )


def max_linear_distortion(crs: CRS, extent: GeographicExtent) -> float:
    """Largest relative scale error (Tissot semi-axes) over the extent; inf if
    any sample point is outside the projection's domain."""
    lons, lats = extent.sample_points()
    try:
        factors = Proj(crs).get_factors(lons, lats, errcheck=False)
    except (CRSError, RuntimeError):
        return float("inf")
    semi_axes = np.concatenate(
        [np.asarray(factors.tissot_semimajor), np.asarray(factors.tissot_semiminor)]
    )
    if not np.isfinite(semi_axes).all():
        return float("inf")
    return float(np.abs(semi_axes - 1.0).max())


def _metres_per_unit(crs: CRS) -> float | None:
    axes = crs.axis_info
    if not axes:
        return None
    factor = axes[0].unit_conversion_factor
    if not factor or axes[0].unit_name in ("degree", "radian", "grad"):
        return None
    return float(factor)


def _horizontal(crs: CRS) -> CRS:
    """Drop any vertical component of a compound CRS."""
    return crs.to_2d() if crs.is_compound else crs


def _normalize_lon[T: (float, np.ndarray)](lon: T) -> T:
    return (lon + 180.0) % 360.0 - 180.0


def _log_choice(choice: MeasurementCRS, extent: GeographicExtent) -> None:
    logger.info(
        "crs.measurement_selected",
        extra={
            "measurement_crs": choice.label,
            "strategy": choice.strategy.value,
            "max_linear_distortion": round(choice.max_linear_distortion, 6),
            "extent": [round(v, 6) for v in (extent.west, extent.south, extent.east, extent.north)],
        },
    )
