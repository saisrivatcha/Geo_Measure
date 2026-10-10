"""Builders for test inputs: ZIP archives (including hostile ones) and datasets."""

from __future__ import annotations

import zipfile
from collections.abc import Mapping
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

VALID_KML = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Site A</name>
      <Point><coordinates>78.4867,17.3850,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""


def write_zip(path: Path, members: Mapping[str, bytes]) -> Path:
    """Write ``members`` verbatim; names are not sanitised (so hostile names work)."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(zipfile.ZipInfo(name), payload)
    return path


def write_symlink_zip(path: Path, link_name: str, target: str) -> Path:
    info = zipfile.ZipInfo(link_name)
    info.external_attr = 0o120777 << 16  # S_IFLNK | rwxrwxrwx
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, target)
    return path


def shapefile_members(
    stem: str = "parcels", prefix: str = "", *, with_prj: bool = True
) -> dict[str, bytes]:
    """Placeholder component bytes for central-directory tests (not readable by GDAL)."""
    extensions = [".shp", ".shx", ".dbf"] + ([".prj"] if with_prj else [])
    return {f"{prefix}{stem}{ext}": b"x" for ext in extensions}


def build_real_shapefile_zip(
    workdir: Path,
    *,
    stem: str = "parcels",
    with_prj: bool = True,
    extra: Mapping[str, bytes] | None = None,
) -> Path:
    """A genuine single-polygon Shapefile written by GDAL, zipped."""
    source_dir = workdir / f"{stem}_src"
    source_dir.mkdir()
    frame = gpd.GeoDataFrame(
        {"name": ["parcel"]},
        geometry=[Polygon([(78.0, 17.0), (78.01, 17.0), (78.01, 17.01), (78.0, 17.01)])],
        crs="EPSG:4326",
    )
    frame.to_file(source_dir / f"{stem}.shp", engine="pyogrio")

    members: dict[str, bytes] = {}
    for component in sorted(source_dir.iterdir()):
        if component.suffix == ".prj" and not with_prj:
            continue
        members[component.name] = component.read_bytes()
    members.update(extra or {})
    return write_zip(workdir / f"{stem}.zip", members)


# ---- KML -----------------------------------------------------------------------

KML_NS = "http://www.opengis.net/kml/2.2"


def kml_document(*folders: tuple[str, list[str]]) -> bytes:
    """A KML document with one ``<Folder>`` per ``(name, placemarks)`` pair."""
    body = "".join(
        f"<Folder><name>{name}</name>{''.join(placemarks)}</Folder>" for name, placemarks in folders
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="{KML_NS}"><Document>'
        f"<name>test</name>{body}</Document></kml>"
    ).encode()


def _coords(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x},{y},0" for x, y in points)


def kml_placemark(
    name: str,
    geometry_xml: str,
    *,
    placemark_id: str | None = None,
    data: Mapping[str, str] | None = None,
) -> str:
    id_attr = f' id="{placemark_id}"' if placemark_id else ""
    extended = ""
    if data:
        items = "".join(f'<Data name="{k}"><value>{v}</value></Data>' for k, v in data.items())
        extended = f"<ExtendedData>{items}</ExtendedData>"
    return f"<Placemark{id_attr}><name>{name}</name>{extended}{geometry_xml}</Placemark>"


def kml_polygon(ring: list[tuple[float, float]]) -> str:
    return (
        "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
        f"{_coords(ring)}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
    )


def kml_line(points: list[tuple[float, float]]) -> str:
    return f"<LineString><coordinates>{_coords(points)}</coordinates></LineString>"


def kml_point(x: float, y: float) -> str:
    return f"<Point><coordinates>{x},{y},0</coordinates></Point>"


def kml_multigeometry(*parts: str) -> str:
    return f"<MultiGeometry>{''.join(parts)}</MultiGeometry>"


# ---- Shapefiles ----------------------------------------------------------------


def write_shapefile_zip(
    workdir: Path,
    frame: gpd.GeoDataFrame,
    *,
    stem: str = "dataset",
    with_prj: bool = True,
    omit: tuple[str, ...] = (),
) -> Path:
    """Write ``frame`` as a real Shapefile with GDAL and zip its components."""
    source_dir = workdir / f"{stem}_src"
    source_dir.mkdir()
    frame.to_file(source_dir / f"{stem}.shp", engine="pyogrio")
    skipped = set(omit) | (set() if with_prj else {".prj"})
    members = {
        component.name: component.read_bytes()
        for component in sorted(source_dir.iterdir())
        if component.suffix.lower() not in skipped
    }
    return write_zip(workdir / f"{stem}.zip", members)


def square(x0: float, y0: float, size: float) -> Polygon:
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size)])
