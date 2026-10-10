import type {
  FeatureMeasurement,
  FileList,
  FileProcessingResult,
  FileRecord,
  GeoJSONFeature,
  GeoJSONFeatureCollection,
  HealthStatus,
  MeasurementsPage,
  MeasurementSummary,
  ServiceInfo,
  WorkspaceStats,
} from "@/types/api";

export const healthOk: HealthStatus = { status: "ok", database: "ok" };

export function fileRecord(overrides: Partial<FileRecord> = {}): FileRecord {
  return {
    id: "3d3e7d3a-0000-4000-8000-000000000001",
    filename: "survey.kml",
    file_type: "KML",
    status: "COMPLETED",
    file_size_bytes: 182_304,
    feature_count: 120,
    source_crs: "EPSG:4326",
    source_crs_name: "WGS 84",
    source_crs_assumed: false,
    measurement_crs: "EPSG:32643",
    measurement_crs_name: "WGS 84 / UTM zone 43N",
    processing_error: null,
    created_at: "2026-10-08T06:00:00Z",
    completed_at: "2026-10-08T06:00:02Z",
    ...overrides,
  };
}

export function fileList(items: FileRecord[] = [fileRecord()], overrides: Partial<FileList> = {}): FileList {
  return { items, page: 1, page_size: 20, total: items.length, total_pages: items.length ? 1 : 0, ...overrides };
}

export const summary: MeasurementSummary = {
  total_features: 120,
  measured_features: 100,
  not_required_features: 15,
  unsupported_features: 3,
  invalid_features: 2,
  no_geometry_features: 0,
  crs_unavailable_features: 0,
  failed_features: 0,
  polygon_count: 70,
  line_count: 30,
  measured_polygon_count: 68,
  measured_line_count: 30,
  point_count: 15,
  other_count: 5,
  total_area_square_meters: 1_523_482.731,
  total_length_meters: 28_411.921,
};

export const stats: WorkspaceStats = {
  files: { total: 5, completed: 4, in_progress: 0, failed: 1 },
  features: summary,
};

export const serviceInfo: ServiceInfo = {
  name: "GeoMeasure",
  version: "0.3.0",
  environment: "test",
  upload: { max_upload_size_mb: 50, max_upload_bytes: 52_428_800, allowed_extensions: [".kml", ".zip"] },
  measurement: {
    area_unit: "square_meters",
    length_unit: "meters",
    max_linear_distortion: 0.001,
    crs_strategy: ["Source CRS", "UTM zone", "Local Transverse Mercator", "Local equal-area"],
  },
  geojson_preview_max_features: 5000,
};

export function processingResult(file: Partial<FileRecord> = {}): FileProcessingResult {
  const record = fileRecord(file);
  return {
    file: record,
    summary,
    links: {
      self: `/api/files/${record.id}/`,
      measurements: `/api/files/${record.id}/measurements/`,
      geojson: `/api/files/${record.id}/geojson`,
    },
  };
}

export function feature(overrides: Partial<FeatureMeasurement> = {}): FeatureMeasurement {
  return {
    feature_index: 0,
    source_feature_id: "0",
    source_layer: "parcels",
    geometry_type: "Polygon",
    geometry_valid: true,
    geometry_repaired: false,
    measurement: {
      type: "AREA",
      value: 15234.82731,
      unit: "square_meters",
      area_square_km: 0.01523482731,
      area_hectares: 1.523482731,
      length_km: null,
      display: "1.52 ha",
    },
    measurement_status: "COMPLETED",
    measurement_error: null,
    source_crs: "EPSG:4326",
    measurement_crs: "EPSG:32643",
    properties: { name: "Plot 1" },
    ...overrides,
  };
}


export function measurementsPage(
  features: FeatureMeasurement[],
  { page = 1, pageSize = 50, total = features.length }: { page?: number; pageSize?: number; total?: number } = {},
): MeasurementsPage {
  return {
    file_id: fileRecord().id,
    source_crs: "EPSG:4326",
    measurement_crs: "EPSG:32643",
    summary: { ...summary, total_features: total },
    page,
    page_size: pageSize,
    total,
    total_pages: Math.ceil(total / pageSize),
    features,
  };
}

export function geojsonCollection(): GeoJSONFeatureCollection {
  const polygon: GeoJSONFeature = {
    type: "Feature",
    id: 0,
    geometry: {
      type: "Polygon",
      coordinates: [[[78.48, 17.38], [78.49, 17.38], [78.49, 17.39], [78.48, 17.39], [78.48, 17.38]]],
    },
    properties: { Name: "Parcel 1" },
    geomeasure: {
      feature_index: 0,
      geometry_type: "Polygon",
      measurement_status: "COMPLETED",
      measurement_type: "AREA",
      measurement_value: 1177219.37,
      measurement_unit: "square_meters",
    },
  };
  const line: GeoJSONFeature = {
    ...polygon,
    id: 1,
    geometry: { type: "LineString", coordinates: [[78.48, 17.38], [78.5, 17.4]] },
    geomeasure: { ...polygon.geomeasure, feature_index: 1, geometry_type: "LineString", measurement_type: "LENGTH", measurement_value: 3070.05, measurement_unit: "meters" },
  };
  const point: GeoJSONFeature = {
    ...polygon,
    id: 2,
    geometry: { type: "Point", coordinates: [78.485, 17.385] },
    geomeasure: { ...polygon.geomeasure, feature_index: 2, geometry_type: "Point", measurement_status: "NOT_REQUIRED", measurement_type: null, measurement_value: null, measurement_unit: null },
  };
  return {
    type: "FeatureCollection",
    features: [polygon, line, point],
    metadata: {
      total_features: 3,
      returned_features: 3,
      truncated: false,
      display_crs: "EPSG:4326",
      source_crs: "EPSG:4326",
      measurement_crs: "EPSG:32643",
      features_without_geometry: 0,
    },
  };
}
