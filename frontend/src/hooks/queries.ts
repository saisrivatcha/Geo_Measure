/** TanStack Query hooks over src/services/api.ts. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import {
  getFeature,
  getFile,
  getFiles,
  getGeoJSON,
  getHealth,
  getMeasurements,
  getServiceInfo,
  getStats,
} from "@/services/api";
import { queryKeys } from "@/services/queryKeys";
import type { FileListParams, MeasurementParams } from "@/types/api";

const HEALTH_INTERVAL_MS = 30_000;
/** While a file is PENDING/PROCESSING (e.g. uploaded from another tab), poll it. */
const IN_PROGRESS_INTERVAL_MS = 3_000;

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => getHealth(signal),
    refetchInterval: HEALTH_INTERVAL_MS,
    retry: false,
  });
}

export function useServiceInfo() {
  return useQuery({
    queryKey: queryKeys.serviceInfo,
    queryFn: ({ signal }) => getServiceInfo(signal),
    staleTime: 5 * 60_000,
  });
}

export function useStats() {
  return useQuery({ queryKey: queryKeys.stats, queryFn: ({ signal }) => getStats(signal) });
}

export function useFiles(params: FileListParams) {
  return useQuery({
    queryKey: queryKeys.files.list(params),
    queryFn: ({ signal }) => getFiles(params, signal),
    placeholderData: keepPreviousData,
  });
}

export function useFile(id: string) {
  return useQuery({
    queryKey: queryKeys.files.detail(id),
    queryFn: ({ signal }) => getFile(id, signal),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "PENDING" || status === "PROCESSING" ? IN_PROGRESS_INTERVAL_MS : false;
    },
  });
}

export function useMeasurements(id: string, params: MeasurementParams, enabled = true) {
  return useQuery({
    queryKey: queryKeys.files.measurements(id, params),
    queryFn: ({ signal }) => getMeasurements(id, params, signal),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useGeoJSON(id: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.files.geojson(id),
    queryFn: ({ signal }) => getGeoJSON(id, signal),
    enabled,
    staleTime: Infinity, // results of a COMPLETED file never change
  });
}

export function useFeature(id: string, featureIndex: number | null) {
  return useQuery({
    queryKey: queryKeys.files.feature(id, featureIndex ?? -1),
    queryFn: ({ signal }) => getFeature(id, featureIndex as number, signal),
    enabled: featureIndex !== null,
    staleTime: Infinity,
  });
}
