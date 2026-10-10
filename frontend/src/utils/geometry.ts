/** Geometry families and their topographic colours (see tokens.css). */
export type GeometryFamily = "polygon" | "line" | "point" | "other";

const FAMILIES: Record<string, GeometryFamily> = {
  Polygon: "polygon",
  MultiPolygon: "polygon",
  LineString: "line",
  MultiLineString: "line",
  LinearRing: "line",
  Point: "point",
  MultiPoint: "point",
};

export function geometryFamily(geometryType: string | null | undefined): GeometryFamily {
  return (geometryType && FAMILIES[geometryType]) || "other";
}

export const FAMILY_LABELS: Record<GeometryFamily, string> = {
  polygon: "Polygons",
  line: "Lines",
  point: "Points",
  other: "Other types",
};

/** Concrete colours for Leaflet, which cannot read CSS variables. */
export const FAMILY_COLORS: Record<GeometryFamily, string> = {
  polygon: "#3b76a8",
  line: "#a0612a",
  point: "#3c7a4e",
  other: "#7a8592",
};
