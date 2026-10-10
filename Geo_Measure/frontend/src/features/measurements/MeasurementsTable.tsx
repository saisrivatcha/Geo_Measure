import type { ReactNode } from "react";

import { DataTable, type Column } from "@/components/data/DataTable";
import { GeometryLabel } from "@/components/data/GeometryLabel";
import { MeasurementStatusBadge } from "@/components/data/StatusBadge";
import type { FeatureMeasurement } from "@/types/api";
import { formatDecimal, formatExact, unitSymbol } from "@/utils/format";

import styles from "./Measurements.module.css";

/** The formatted value keeps the API's full precision in its tooltip. */
function MeasurementValue({ feature }: { feature: FeatureMeasurement }) {
  if (!feature.measurement) return <span className={styles.muted}>–</span>;
  const { value } = feature.measurement;
  return (
    <data value={String(value)} title={formatExact(value)}>
      {formatDecimal(value)}
    </data>
  );
}

const COLUMNS: Column<FeatureMeasurement>[] = [
  { key: "index", header: "Index", align: "end", width: "72px", cell: (f) => f.feature_index },
  { key: "geometry", header: "Geometry", cell: (f) => <GeometryLabel geometryType={f.geometry_type} /> },
  { key: "measurement", header: "Measurement", align: "end", nowrap: true, cell: (f) => <MeasurementValue feature={f} /> },
  {
    key: "unit",
    header: "Unit",
    cell: (f) => (f.measurement ? unitSymbol(f.measurement.unit) : <span className={styles.muted}>–</span>),
  },
  { key: "source", header: "Source CRS", nowrap: true, cell: (f) => f.source_crs ?? <span className={styles.muted}>None</span> },
  {
    key: "measurementCrs",
    header: "Measurement CRS",
    nowrap: true,
    cell: (f) => f.measurement_crs ?? <span className={styles.muted}>None</span>,
  },
  { key: "status", header: "Status", cell: (f) => <MeasurementStatusBadge status={f.measurement_status} /> },
];

interface MeasurementsTableProps {
  features: FeatureMeasurement[] | undefined;
  /** Shown when the requested page has no rows (e.g. a page past the end). */
  empty?: ReactNode;
  isLoading: boolean;
  isFetching: boolean;
  selectedIndex: number | null;
  onSelect: (feature: FeatureMeasurement) => void;
}

export function MeasurementsTable({
  features,
  empty,
  isLoading,
  isFetching,
  selectedIndex,
  onSelect,
}: MeasurementsTableProps) {
  return (
    <DataTable
      caption="Feature measurements"
      columns={COLUMNS}
      rows={features}
      getRowKey={(f) => f.feature_index}
      onRowClick={onSelect}
      rowLabel={(f) => `Feature ${f.feature_index}, ${f.geometry_type ?? "no geometry"}: open details`}
      isSelected={(f) => f.feature_index === selectedIndex}
      isLoading={isLoading}
      isFetching={isFetching}
      empty={empty}
      skeletonRows={10}
      maxHeight="calc(100vh - 220px)"
    />
  );
}
