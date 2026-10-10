import { DatasetMap } from "@/components/map/DatasetMap";
import { DefinitionList, PropertyTable } from "@/components/data/PropertyTable";
import { GeometryLabel } from "@/components/data/GeometryLabel";
import { MeasurementStatusBadge } from "@/components/data/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { Drawer } from "@/components/ui/Overlay";
import { MapSkeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useFeature } from "@/hooks/queries";
import type { FeatureMeasurement, GeoJSONFeature } from "@/types/api";
import {
  MEASUREMENT_STATUS_HINTS,
  formatDecimal,
  formatExact,
  formatInteger,
  unitSymbol,
} from "@/utils/format";

import styles from "./Measurements.module.css";

function MeasurementFigure({ feature }: { feature: FeatureMeasurement }) {
  const m = feature.measurement;
  if (!m) {
    return (
      <div className={styles.reason}>
        <MeasurementStatusBadge status={feature.measurement_status} />
        <p style={{ marginTop: 8 }}>{feature.measurement_error ?? MEASUREMENT_STATUS_HINTS[feature.measurement_status]}</p>
      </div>
    );
  }
  const derived =
    m.type === "AREA"
      ? `${formatDecimal(m.area_hectares ?? 0)} ha, ${formatDecimal(m.area_square_km ?? 0)} km²`
      : `${formatDecimal(m.length_km ?? 0)} km`;
  return (
    <div className={styles.figure}>
      <p className={styles.figureLabel}>{m.type === "AREA" ? "Area" : "Length"}</p>
      <p className={styles.figureValue}>
        {formatDecimal(m.value)} {unitSymbol(m.unit)}
      </p>
      <p className={styles.figureExtra}>{derived}</p>
      <p className={styles.figureExtra}>
        Exact value: <data value={String(m.value)}>{formatExact(m.value)}</data> {unitSymbol(m.unit)}
      </p>
    </div>
  );
}

function FeatureLocation({ fileId, feature }: { fileId: string; feature: FeatureMeasurement }) {
  const detail = useFeature(fileId, feature.feature_index);
  if (detail.isPending) return <MapSkeleton label="Loading feature geometry" />;
  if (detail.isError) return <ErrorState title="Unable to load the geometry." error={detail.error} onRetry={() => detail.refetch()} />;

  const asFeature: GeoJSONFeature = {
    type: "Feature",
    id: feature.feature_index,
    geometry: detail.data.display_geometry,
    properties: detail.data.properties,
    geomeasure: {
      feature_index: feature.feature_index,
      geometry_type: feature.geometry_type,
      measurement_status: feature.measurement_status,
      measurement_type: feature.measurement?.type ?? null,
      measurement_value: feature.measurement?.value ?? null,
      measurement_unit: feature.measurement?.unit ?? null,
    },
  };
  return (
    <DatasetMap
      features={[asFeature]}
      selectedIndex={feature.feature_index}
      height={240}
      showLayerControls={false}
      emptyMessage={
        feature.geometry_type
          ? "This geometry cannot be placed on a map because the dataset has no CRS."
          : "This feature has no geometry."
      }
    />
  );
}

interface FeatureDetailPanelProps {
  fileId: string;
  feature: FeatureMeasurement | null;
  onClose: () => void;
}

/** Side panel for one feature: measurement, CRS, validity, location and attributes. */
export function FeatureDetailPanel({ fileId, feature, onClose }: FeatureDetailPanelProps) {
  return (
    <Drawer
      open={feature !== null}
      onClose={onClose}
      title={feature ? `Feature ${formatInteger(feature.feature_index)}` : ""}
      subtitle={feature ? <GeometryLabel geometryType={feature.geometry_type} /> : undefined}
    >
      {feature && (
        <>
          <section className={styles.section} aria-label="Measurement">
            <MeasurementFigure feature={feature} />
            {(feature.geometry_repaired || feature.geometry_valid === false) && (
              <div className={styles.flags}>
                {feature.geometry_valid === false && <Badge tone="progress">Invalid source geometry</Badge>}
                {feature.geometry_repaired && <Badge tone="info">Repaired before measuring</Badge>}
              </div>
            )}
          </section>

          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Location</h3>
            <div className={styles.mapBox}>
              <FeatureLocation fileId={fileId} feature={feature} />
            </div>
          </section>

          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Details</h3>
            <DefinitionList
              items={[
                { label: "Feature index", value: feature.feature_index },
                { label: "Source ID", value: feature.source_feature_id ?? "–" },
                { label: "Layer", value: feature.source_layer ?? "–" },
                { label: "Geometry type", value: feature.geometry_type ?? "None" },
                { label: "Status", value: <MeasurementStatusBadge status={feature.measurement_status} /> },
                { label: "Source CRS", value: feature.source_crs ?? "Not defined" },
                { label: "Measurement CRS", value: feature.measurement_crs ?? "None" },
                {
                  label: "Valid geometry",
                  value: feature.geometry_valid === null ? "Not checked" : feature.geometry_valid ? "Yes" : "No",
                },
              ]}
            />
          </section>

          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Properties</h3>
            <PropertyTable properties={feature.properties} emptyText="This feature has no attributes." />
          </section>
        </>
      )}
    </Drawer>
  );
}
