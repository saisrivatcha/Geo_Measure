"""Fail fast if the geospatial native stack is unusable.

Run at image build time so a broken GDAL/PROJ/GEOS install never ships.
"""

from __future__ import annotations

import sys

import pyogrio
import pyproj
import shapely

REQUIRED_DRIVERS = ("ESRI Shapefile", "KML", "LIBKML", "GeoJSON")


def main() -> int:
    drivers = pyogrio.list_drivers()
    missing = [name for name in REQUIRED_DRIVERS if name not in drivers]

    # Exercise PROJ's database (needs proj.db) and GEOS with a real operation.
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True)
    x, _ = transformer.transform(78.4867, 17.3850)
    area = shapely.box(0, 0, 2, 3).area

    print(f"GDAL {pyogrio.__gdal_version_string__}")
    print(f"PROJ {pyproj.proj_version_str}")
    print(f"GEOS {shapely.geos_version_string}")
    if missing:
        print(f"Missing OGR drivers: {missing}", file=sys.stderr)
        return 1
    if not (100_000 < x < 900_000) or area != 6:
        print("PROJ/GEOS sanity check failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
