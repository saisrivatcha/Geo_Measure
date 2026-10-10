/**
 * Types mirroring the FastAPI response schemas (backend/app/schemas).
 * Keep these in step with the backend; field names are the wire format.
 */

export type FileType = "KML" | "SHAPEFILE";
export type FileStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
export type MeasurementType = "AREA" | "LENGTH";
export type MeasurementStatus =
  | "COMPLETED"
  | "NOT_REQUIRED"
  | "NOT_SUPPORTED"
  | "NO_GEOMETRY"
  | "INVALID_GEOMETRY"
  | "CRS_UNAVAILABLE"
  | "FAILED";

export type FileSortField = "created_at" | "filename" | "file_size_bytes" | "feature_count" | "status";
export type SortOrder = "asc" | "desc";

/** JSON value as produced by the backend property serializer. */
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type Properties = Record<string, JsonValue>;

export interface FileRecord {
  id: string;
  filename: string;
  file_type: FileType;
  status: FileStatus;
  file_size_bytes: number;
  feature_count: number | null;
  source_crs: string | null;
  source_crs_name: string | null;
  source_crs_assumed: boolean;
  measurement_crs: string | null;
  measurement_crs_name: string | null;
  processing_error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface PaginationResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export type FileList = PaginationResponse<FileRecord>;

export interface Measurement {
  type: MeasurementType;
  /** Full-precision SI value: square metres (AREA) or metres (LENGTH). */
  value: number;
  unit: "square_meters" | "meters" | string;
  area_square_km: number | null;
  area_hectares: number | null;
  length_km: number | null;
  display: string;
}

export interface FeatureMeasurement {
  feature_index: number;
  source_feature_id: string | null;
  source_layer: string | null;
  geometry_type: string | null;
  geometry_valid: boolean | null;
  geometry_repaired: boolean;
  measurement: Measurement | null;
  measurement_status: MeasurementStatus;
  measurement_error: string | null;
  source_crs: string | null;
  measurement_crs: string | null;
  properties: Properties;
}

export interface FeatureDetail extends FeatureMeasurement {
  display_geometry: GeoJSON.Geometry | null;
  geometry: GeoJSON.Geometry | null;
}

export interface MeasurementSummary {
  total_features: number;
  measured_features: number;
  not_required_features: number;
  unsupported_features: number;
  invalid_features: number;
  no_geometry_features: number;
  crs_unavailable_features: number;
  failed_features: number;
  polygon_count: number;
  line_count: number;
  measured_polygon_count: number;
  measured_line_count: number;
  point_count: number;
  other_count: number;
  total_area_square_meters: number;
  total_length_meters: number;
}

export interface MeasurementsPage {
  file_id: string;
  source_crs: string | null;
  measurement_crs: string | null;
  summary: MeasurementSummary;
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  features: FeatureMeasurement[];
}

export interface FileLinks {
  self: string;
  measurements: string;
  geojson: string;
}

export interface FileProcessingResult {
  file: FileRecord;
  summary: MeasurementSummary;
  links: FileLinks;
}

export interface GeoJSONFeatureMeasurement {
  feature_index: number;
  geometry_type: string | null;
  measurement_status: MeasurementStatus;
  measurement_type: MeasurementType | null;
  measurement_value: number | null;
  measurement_unit: string | null;
}

export interface GeoJSONFeature {
  type: "Feature";
  id: number;
  geometry: GeoJSON.Geometry | null;
  properties: Properties;
  /** Foreign member: the feature's measurement. */
  geomeasure: GeoJSONFeatureMeasurement;
}

export interface GeoJSONPreviewMetadata {
  total_features: number;
  returned_features: number;
  truncated: boolean;
  display_crs: string;
  source_crs: string | null;
  measurement_crs: string | null;
  features_without_geometry: number;
}

export interface GeoJSONFeatureCollection {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
  metadata: GeoJSONPreviewMetadata;
}

export interface FileCounts {
  total: number;
  completed: number;
  in_progress: number;
  failed: number;
}

export interface WorkspaceStats {
  files: FileCounts;
  features: MeasurementSummary;
}

export interface ServiceInfo {
  name: string;
  version: string;
  environment: string;
  upload: {
    max_upload_size_mb: number;
    max_upload_bytes: number;
    allowed_extensions: string[];
  };
  measurement: {
    area_unit: string;
    length_unit: string;
    max_linear_distortion: number;
    crs_strategy: string[];
  };
  geojson_preview_max_features: number;
}

export interface HealthStatus {
  status: "ok";
  database?: "ok";
}

/** The backend's error envelope. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export interface FileListParams {
  page?: number;
  page_size?: number;
  sort?: FileSortField;
  order?: SortOrder;
  status?: FileStatus;
  file_type?: FileType;
  q?: string;
}

export interface MeasurementParams {
  page?: number;
  page_size?: number;
}
