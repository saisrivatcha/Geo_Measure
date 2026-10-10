import { Link } from "react-router-dom";

import { GeometryLabel } from "@/components/data/GeometryLabel";
import { PropertyTable } from "@/components/data/PropertyTable";
import type { GeoJSONFeature } from "@/types/api";
import { MEASUREMENT_STATUS_LABELS, formatMeasurement } from "@/utils/format";

import styles from "./FeaturePopup.module.css";

const POPUP_PROPERTY_LIMIT = 4;

export function FeaturePopup({ feature, fileId }: { feature: GeoJSONFeature; fileId?: string }) {
  const m = feature.geomeasure;
  const measured = m.measurement_status === "COMPLETED" && m.measurement_value !== null && m.measurement_unit;

  return (
    <div className={styles.popup}>
      <div className={styles.header}>
        <span className={styles.index}>Feature {m.feature_index}</span>
        <span className={styles.type}>
          <GeometryLabel geometryType={m.geometry_type} />
        </span>
      </div>
      <div className={styles.measurement}>
        <span className={styles.measurementLabel}>
          {m.measurement_type === "AREA" ? "Area" : m.measurement_type === "LENGTH" ? "Length" : "Measurement"}
        </span>
        <span className={styles.measurementValue}>
          {measured
            ? formatMeasurement(m.measurement_value as number, m.measurement_unit as string)
            : MEASUREMENT_STATUS_LABELS[m.measurement_status]}
        </span>
      </div>
      <PropertyTable properties={feature.properties} limit={POPUP_PROPERTY_LIMIT} />
      {fileId && (
        <Link className={styles.link} to={`/files/${fileId}/measurements?feature=${m.feature_index}`}>
          Open in measurements
        </Link>
      )}
    </div>
  );
}
