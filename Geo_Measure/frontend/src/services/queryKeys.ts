import type { FileListParams, MeasurementParams } from "@/types/api";

/** Centralised TanStack Query keys so invalidation stays consistent. */
export const queryKeys = {
  health: ["health"] as const,
  serviceInfo: ["service-info"] as const,
  stats: ["stats"] as const,
  files: {
    all: ["files"] as const,
    list: (params: FileListParams) => ["files", "list", params] as const,
    detail: (id: string) => ["files", "detail", id] as const,
    measurements: (id: string, params: MeasurementParams) =>
      ["files", "measurements", id, params] as const,
    geojson: (id: string) => ["files", "geojson", id] as const,
    feature: (id: string, index: number) => ["files", "feature", id, index] as const,
  },
};
