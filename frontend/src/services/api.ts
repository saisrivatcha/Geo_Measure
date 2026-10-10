/**
 * Typed client for the GeoMeasure FastAPI backend.
 *
 * Components never call fetch directly: they use these functions through the
 * TanStack Query hooks in src/hooks. Every non-2xx response is turned into an
 * {@link ApiError} carrying the backend's error envelope.
 */
import type {
  ApiErrorBody,
  FeatureDetail,
  FileList,
  FileListParams,
  FileProcessingResult,
  FileRecord,
  GeoJSONFeatureCollection,
  HealthStatus,
  MeasurementParams,
  MeasurementsPage,
  ServiceInfo,
  WorkspaceStats,
} from "@/types/api";

/** API origin; empty string means same origin (Vite proxy in dev, nginx in Docker). */
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

const NETWORK_ERROR_MESSAGE = "The GeoMeasure API could not be reached.";

function isErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const error = (value as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}

export function toApiError(status: number, body: unknown): ApiError {
  if (isErrorBody(body)) {
    return new ApiError(status, body.error.code, body.error.message, body.error.details ?? {});
  }
  return new ApiError(status, "HTTP_ERROR", `The API responded with status ${status}.`);
}

function queryString(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "NETWORK_ERROR", NETWORK_ERROR_MESSAGE);
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw toApiError(response.status, body);
  return body as T;
}

// ---- reads -------------------------------------------------------------------------

/** Readiness check: the API is up and can reach its database. */
export function getHealth(signal?: AbortSignal): Promise<HealthStatus> {
  return request<HealthStatus>("/api/health/ready", { signal });
}

export function getServiceInfo(signal?: AbortSignal): Promise<ServiceInfo> {
  return request<ServiceInfo>("/api/meta", { signal });
}

export function getStats(signal?: AbortSignal): Promise<WorkspaceStats> {
  return request<WorkspaceStats>("/api/stats", { signal });
}

export function getFiles(params: FileListParams = {}, signal?: AbortSignal): Promise<FileList> {
  return request<FileList>(`/api/files/${queryString(params)}`, { signal });
}

export function getFile(id: string, signal?: AbortSignal): Promise<FileRecord> {
  return request<FileRecord>(`/api/files/${encodeURIComponent(id)}/`, { signal });
}

export function getMeasurements(
  id: string,
  params: MeasurementParams = {},
  signal?: AbortSignal,
): Promise<MeasurementsPage> {
  return request<MeasurementsPage>(
    `/api/files/${encodeURIComponent(id)}/measurements/${queryString(params)}`,
    { signal },
  );
}

export function getFeature(id: string, featureIndex: number, signal?: AbortSignal): Promise<FeatureDetail> {
  return request<FeatureDetail>(`/api/files/${encodeURIComponent(id)}/features/${featureIndex}`, {
    signal,
  });
}

export function getGeoJSON(id: string, signal?: AbortSignal): Promise<GeoJSONFeatureCollection> {
  return request<GeoJSONFeatureCollection>(`/api/files/${encodeURIComponent(id)}/geojson`, { signal });
}

// ---- upload --------------------------------------------------------------------------

export type UploadPhase = "uploading" | "processing";

export interface UploadOptions {
  /** Real byte progress of the request body (0-1), when the browser reports it. */
  onUploadProgress?: (fraction: number) => void;
  /** Called with "processing" once every byte has been sent and the server is working. */
  onPhaseChange?: (phase: UploadPhase) => void;
  signal?: AbortSignal;
}

/**
 * Upload and process a dataset. Uses XMLHttpRequest because fetch cannot report
 * upload progress. Processing is synchronous on the server, so the request
 * resolves only when the dataset has been fully processed (or failed).
 */
export function uploadFile(file: File, options: UploadOptions = {}): Promise<FileProcessingResult> {
  const { onUploadProgress, onPhaseChange, signal } = options;

  return new Promise<FileProcessingResult>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", apiUrl("/api/files/"));
    xhr.setRequestHeader("Accept", "application/json");
    xhr.responseType = "text";

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onUploadProgress?.(event.loaded / event.total);
    };
    xhr.upload.onload = () => onPhaseChange?.("processing");

    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as FileProcessingResult);
      else reject(toApiError(xhr.status, body));
    };
    xhr.onerror = () => reject(new ApiError(0, "NETWORK_ERROR", NETWORK_ERROR_MESSAGE));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));

    if (signal) {
      if (signal.aborted) {
        reject(new DOMException("Upload cancelled", "AbortError"));
        return;
      }
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }

    const form = new FormData();
    form.append("file", file, file.name);
    onPhaseChange?.("uploading");
    xhr.send(form);
  });
}
