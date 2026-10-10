import type { MeasurementSummary } from "@/types/api";
import { formatArea, formatInteger, formatLength } from "@/utils/format";
import { FAMILY_COLORS, type GeometryFamily } from "@/utils/geometry";

import styles from "./GeometryBreakdown.module.css";
import { GeometryGlyph } from "./GeometryLabel";

interface Row {
  family: GeometryFamily;
  label: string;
  count: number;
  /** Features with a value, or a word when the family is never measured. */
  measured: string;
  total: string;
}

function rowsFor(summary: MeasurementSummary): Row[] {
  return [
    {
      family: "polygon",
      label: "Polygons",
      count: summary.polygon_count,
      measured: formatInteger(summary.measured_polygon_count),
      total: summary.measured_polygon_count ? formatArea(summary.total_area_square_meters) : "–",
    },
    {
      family: "line",
      label: "Lines",
      count: summary.line_count,
      measured: formatInteger(summary.measured_line_count),
      total: summary.measured_line_count ? formatLength(summary.total_length_meters) : "–",
    },
    { family: "point", label: "Points", count: summary.point_count, measured: "Not required", total: "–" },
    {
      family: "other",
      label: "Other types",
      count: summary.other_count,
      measured: summary.other_count ? "Not supported" : "–",
      total: "–",
    },
  ];
}

/**
 * Feature composition by geometry family: one proportional bar plus exact
 * counts, how many of each were measured, and the measured total.
 */
export function GeometryBreakdown({ summary }: { summary: MeasurementSummary }) {
  const rows = rowsFor(summary);
  // Features with a null geometry belong to no type, so the bar is scaled to
  // the typed features only.
  const total = rows.reduce((sum, row) => sum + row.count, 0);

  return (
    <div>
      <div className={styles.bar} role="img" aria-label={rows.map((r) => `${r.label}: ${r.count}`).join(", ")}>
        {total > 0 &&
          rows
            .filter((row) => row.count > 0)
            .map((row) => (
              <span
                key={row.family}
                className={styles.segment}
                style={{ width: `${(row.count / total) * 100}%`, background: FAMILY_COLORS[row.family] }}
              />
            ))}
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Geometry</th>
            <th scope="col">Count</th>
            <th scope="col">Measured</th>
            <th scope="col">Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.family}>
              <td>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                  <GeometryGlyph family={row.family} />
                  {row.label}
                </span>
              </td>
              <td className={row.count ? undefined : styles.muted}>{formatInteger(row.count)}</td>
              <td className={row.count ? undefined : styles.muted}>{row.count ? row.measured : "–"}</td>
              <td className={row.count ? undefined : styles.muted}>{row.total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
