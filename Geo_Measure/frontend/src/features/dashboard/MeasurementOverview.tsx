import { GeometryBreakdown } from "@/components/data/GeometryBreakdown";
import type { MeasurementSummary } from "@/types/api";
import { formatInteger } from "@/utils/format";

import styles from "./Dashboard.module.css";

/** Why features were not measured, listed only when there are any. */
export function NotMeasuredList({ summary }: { summary: MeasurementSummary }) {
  const reasons = [
    { label: "Points (no measurement needed)", count: summary.not_required_features },
    { label: "Unsupported geometry types", count: summary.unsupported_features },
    { label: "Invalid geometry, not repairable", count: summary.invalid_features },
    { label: "No coordinate system in dataset", count: summary.crs_unavailable_features },
    { label: "Features without geometry", count: summary.no_geometry_features },
    { label: "Measurement failed", count: summary.failed_features },
  ].filter((reason) => reason.count > 0);

  if (reasons.length === 0) {
    return <p className={styles.muted}>Every feature with a measurable geometry was measured.</p>;
  }
  return (
    <ul className={styles.reasonList}>
      {reasons.map((reason) => (
        <li key={reason.label}>
          <span>{reason.label}</span>
          <span className={styles.reasonCount}>{formatInteger(reason.count)}</span>
        </li>
      ))}
    </ul>
  );
}

export function MeasurementOverview({ summary }: { summary: MeasurementSummary }) {
  return (
    <div className={styles.overviewGrid}>
      <div>
        <h3 className={styles.subTitle}>By geometry</h3>
        <GeometryBreakdown summary={summary} />
      </div>
      <div>
        <h3 className={styles.subTitle}>Not measured</h3>
        <NotMeasuredList summary={summary} />
      </div>
    </div>
  );
}
