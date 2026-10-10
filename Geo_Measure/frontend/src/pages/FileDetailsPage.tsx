import { ArrowLeft, Ruler } from "lucide-react";
import { useParams } from "react-router-dom";

import { GeometryBreakdown } from "@/components/data/GeometryBreakdown";
import { DefinitionList } from "@/components/data/PropertyTable";
import { StatCard, StatStrip } from "@/components/data/StatCard";
import { StatusBadge } from "@/components/data/StatusBadge";
import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { DatasetMap } from "@/components/map/DatasetMap";
import { ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { MapSkeleton, Skeleton, Spinner } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState, NotFoundState } from "@/components/ui/States";
import { NotMeasuredList } from "@/features/dashboard/MeasurementOverview";
import { CRSPanel } from "@/features/file-details/CRSPanel";
import styles from "@/features/file-details/FileDetails.module.css";
import { useFile, useGeoJSON, useMeasurements } from "@/hooks/queries";
import { ApiError } from "@/services/api";
import type { FileRecord } from "@/types/api";
import { FILE_TYPE_LABELS, formatBytes, formatDateTime, formatInteger } from "@/utils/format";

function mapNote(total: number, returned: number, withoutGeometry: number): string | null {
  const notes: string[] = [];
  if (returned < total) notes.push(`Showing the first ${formatInteger(returned)} of ${formatInteger(total)} features.`);
  if (withoutGeometry > 0) notes.push(`${formatInteger(withoutGeometry)} without a mappable geometry.`);
  return notes.length ? notes.join(" ") : null;
}

function DatasetMapCard({ file }: { file: FileRecord }) {
  const geojson = useGeoJSON(file.id);
  return (
    <Card title="Map" description="Geometries reprojected to WGS 84 for display. Select a feature for details." flush className={styles.mapCard}>
      <div className={styles.mapBody}>
        {geojson.isPending && <MapSkeleton />}
        {geojson.isError && (
          <ErrorState title="Unable to load the map preview." error={geojson.error} onRetry={() => geojson.refetch()} />
        )}
        {geojson.data && (
          <DatasetMap
            features={geojson.data.features}
            fileId={file.id}
            height={520}
            note={mapNote(
              geojson.data.metadata.total_features,
              geojson.data.metadata.returned_features,
              geojson.data.metadata.features_without_geometry,
            )}
            emptyMessage={
              file.source_crs
                ? "No feature in this dataset has a geometry to draw."
                : "This dataset has no coordinate reference system, so its features cannot be placed on a map."
            }
          />
        )}
      </div>
    </Card>
  );
}

function BreakdownCard({ fileId }: { fileId: string }) {
  const measurements = useMeasurements(fileId, { page: 1, page_size: 1 });
  return (
    <Card title="Feature breakdown">
      {measurements.isPending && <Skeleton height={140} />}
      {measurements.isError && (
        <ErrorState title="Unable to load the breakdown." error={measurements.error} onRetry={() => measurements.refetch()} />
      )}
      {measurements.data && (
        <>
          <GeometryBreakdown summary={measurements.data.summary} />
          <h3 className={styles.subTitle}>Not measured</h3>
          <NotMeasuredList summary={measurements.data.summary} />
        </>
      )}
    </Card>
  );
}

function DatasetInfoCard({ file }: { file: FileRecord }) {
  return (
    <Card title="Dataset information">
      <DefinitionList
        items={[
          { label: "File name", value: file.filename },
          { label: "Format", value: file.file_type === "KML" ? "KML document" : "ESRI Shapefile (ZIP)" },
          { label: "Size", value: formatBytes(file.file_size_bytes) },
          { label: "Uploaded", value: formatDateTime(file.created_at) },
          {
            label: file.status === "FAILED" ? "Failed at" : "Processed",
            value: formatDateTime(file.completed_at),
          },
          { label: "File ID", value: <span className={styles.id}>{file.id}</span> },
        ]}
      />
    </Card>
  );
}

function crsHint(name: string | null, assumed = false): string | undefined {
  if (assumed) return "Implied by the KML format";
  return name ?? undefined;
}

export function FileDetailsPage() {
  const { id = "" } = useParams();
  const file = useFile(id);

  if (file.isPending) {
    return (
      <PageContainer>
        <PageHeader
          title={<Skeleton width={260} height={24} />}
          documentTitle="File"
          breadcrumb={[{ label: "Files", to: "/files" }, { label: "Loading" }]}
        />
        <div className={styles.stack}>
          <Skeleton height={92} />
          <MapSkeleton />
        </div>
      </PageContainer>
    );
  }

  if (file.isError) {
    const notFound = file.error instanceof ApiError && file.error.isNotFound;
    const back = (
      <ButtonLink to="/files" icon={ArrowLeft}>
        Back to Files
      </ButtonLink>
    );
    return (
      <PageContainer>
        <PageHeader title="File" breadcrumb={[{ label: "Files", to: "/files" }, { label: "Unavailable" }]} />
        <Card>
          {notFound ? (
            <NotFoundState
              title="This file does not exist."
              description="It may have been removed, or the link is incorrect."
              actions={back}
            />
          ) : (
            <ErrorState
              title="Unable to load this dataset."
              description="The dataset may have been removed or the API is unavailable."
              error={file.error}
              onRetry={() => file.refetch()}
              actions={back}
            />
          )}
        </Card>
      </PageContainer>
    );
  }

  const record = file.data;
  const completed = record.status === "COMPLETED";

  return (
    <PageContainer>
      <PageHeader
        title={record.filename}
        meta={<StatusBadge status={record.status} />}
        breadcrumb={[
          { label: "Files", to: "/files" },
          { label: record.filename },
        ]}
        actions={
          <>
            {completed && (
              <ButtonLink to={`/files/${record.id}/measurements`} variant="primary" icon={Ruler}>
                Measurements
              </ButtonLink>
            )}
            <ButtonLink to="/files" icon={ArrowLeft}>
              Back to Files
            </ButtonLink>
          </>
        }
      />

      <div className={styles.stack}>
        <StatStrip label="File summary">
          <StatCard
            label="Features"
            value={formatInteger(record.feature_count)}
            hint={completed ? undefined : "Not processed"}
          />
          <StatCard
            label="Source CRS"
            value={completed ? (record.source_crs ?? "Not defined") : "–"}
            hint={completed ? crsHint(record.source_crs_name, record.source_crs_assumed) : "Not processed"}
            compact
          />
          <StatCard
            label="Measurement CRS"
            value={completed ? (record.measurement_crs ?? "None") : "–"}
            hint={completed ? (record.measurement_crs_name ?? undefined) : "Not processed"}
            compact
          />
          <StatCard
            label="Dataset type"
            value={FILE_TYPE_LABELS[record.file_type]}
            hint={formatBytes(record.file_size_bytes)}
            compact
          />
        </StatStrip>

        {record.status === "FAILED" && (
          <Card>
            <ErrorState
              title="Processing failed."
              description={record.processing_error ?? "The dataset could not be processed."}
              actions={
                <ButtonLink to="/files/upload" variant="primary">
                  Upload a corrected file
                </ButtonLink>
              }
            />
          </Card>
        )}

        {(record.status === "PENDING" || record.status === "PROCESSING") && (
          <Card>
            <EmptyState
              title="This dataset is still being processed."
              description="This page updates automatically when processing finishes."
              actions={<Spinner label="Processing" />}
            />
          </Card>
        )}

        <div className={styles.grid}>
          {completed && <DatasetMapCard file={record} />}
          <div className={styles.side}>
            {completed && <CRSPanel file={record} />}
            <DatasetInfoCard file={record} />
            {completed && <BreakdownCard fileId={record.id} />}
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
