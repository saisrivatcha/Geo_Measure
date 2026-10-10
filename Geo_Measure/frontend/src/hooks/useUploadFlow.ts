/**
 * State machine for the upload page, driven by the real request:
 *
 *   idle -> selected -> uploading (request body in flight, real byte progress)
 *        -> processing (body sent; server validates, reads, measures - one request)
 *        -> preparing  (response received; map preview GeoJSON is being fetched)
 *        -> completed | failed
 */
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, getGeoJSON, uploadFile } from "@/services/api";
import { queryKeys } from "@/services/queryKeys";
import type { FileProcessingResult } from "@/types/api";

export type UploadPhase = "idle" | "selected" | "uploading" | "processing" | "preparing" | "completed" | "failed";

export interface UploadState {
  phase: UploadPhase;
  file: File | null;
  /** Fraction of the request body sent, when the browser reports it. */
  progress: number | null;
  result: FileProcessingResult | null;
  error: ApiError | null;
}

const INITIAL: UploadState = { phase: "idle", file: null, progress: null, result: null, error: null };

export function useUploadFlow() {
  const queryClient = useQueryClient();
  const [state, setState] = useState<UploadState>(INITIAL);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const select = useCallback((file: File) => {
    setState({ ...INITIAL, phase: "selected", file });
  }, []);

  const reset = useCallback(() => {
    controllerRef.current?.abort();
    setState(INITIAL);
  }, []);

  const start = useCallback(async () => {
    const file = state.file;
    if (!file) return;
    const controller = new AbortController();
    controllerRef.current = controller;
    setState((s) => ({ ...s, phase: "uploading", progress: 0, error: null }));

    try {
      const result = await uploadFile(file, {
        signal: controller.signal,
        onUploadProgress: (progress) => setState((s) => (s.phase === "uploading" ? { ...s, progress } : s)),
        onPhaseChange: (phase) =>
          setState((s) => (phase === "processing" && s.phase === "uploading" ? { ...s, phase: "processing" } : s)),
      });

      void queryClient.invalidateQueries({ queryKey: queryKeys.files.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.stats });
      queryClient.setQueryData(queryKeys.files.detail(result.file.id), result.file);

      setState((s) => ({ ...s, phase: "preparing", result }));
      await queryClient
        .prefetchQuery({
          queryKey: queryKeys.files.geojson(result.file.id),
          queryFn: ({ signal }) => getGeoJSON(result.file.id, signal),
          staleTime: Infinity,
        })
        .catch(() => undefined); // the details page retries; the upload itself succeeded
      setState((s) => ({ ...s, phase: "completed" }));
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      const apiError =
        error instanceof ApiError ? error : new ApiError(0, "UNKNOWN", "The upload failed unexpectedly.");
      if (apiError.details.file_id) void queryClient.invalidateQueries({ queryKey: queryKeys.files.all });
      setState((s) => ({ ...s, phase: "failed", error: apiError }));
    } finally {
      controllerRef.current = null;
    }
  }, [state.file, queryClient]);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    setState((s) => ({ ...s, phase: "selected", progress: null }));
  }, []);

  return { state, select, start, reset, cancel };
}
