import { useHealth } from "@/hooks/queries";
import { ApiError } from "@/services/api";

import styles from "./ApiStatus.module.css";

type ApiState = "checking" | "connected" | "degraded" | "unavailable";

const LABELS: Record<ApiState, string> = {
  checking: "Checking API",
  connected: "API connected",
  degraded: "Database unavailable",
  unavailable: "API unavailable",
};

const DESCRIPTIONS: Record<ApiState, string> = {
  checking: "Contacting the GeoMeasure API.",
  connected: "The API and its database are reachable.",
  degraded: "The API is running but cannot reach its database.",
  unavailable: "The GeoMeasure API cannot be reached.",
};

function useApiState(): ApiState {
  const health = useHealth();
  if (health.isSuccess) return "connected";
  if (health.isError) {
    const error = health.error;
    return error instanceof ApiError && error.status === 503 ? "degraded" : "unavailable";
  }
  return "checking";
}

/** Live readiness of the API, from GET /api/health/ready (re-checked every 30 s). */
export function ApiStatus({ compact = false }: { compact?: boolean }) {
  const state = useApiState();
  return (
    <span
      className={`${styles.status} ${styles[state]}`}
      role="status"
      aria-live="polite"
      title={DESCRIPTIONS[state]}
    >
      <span className={styles.dot} aria-hidden="true" />
      <span className={compact ? "visually-hidden" : undefined}>{LABELS[state]}</span>
    </span>
  );
}
