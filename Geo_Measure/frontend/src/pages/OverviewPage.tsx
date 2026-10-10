import { Files, Upload } from "lucide-react";

import { StatCard, StatStrip } from "@/components/data/StatCard";
import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import styles from "@/features/dashboard/Dashboard.module.css";
import { MeasurementOverview } from "@/features/dashboard/MeasurementOverview";
import { FilesTable } from "@/features/files/FilesTable";
import { useFiles, useStats } from "@/hooks/queries";
import { formatArea, formatInteger, formatLength } from "@/utils/format";

const RECENT_FILES = 6;

function percent(part: number, whole: number): string {
  return whole ? `${Math.round((part / whole) * 100)}% of indexed features` : "No features yet";
}

export function OverviewPage() {
  const stats = useStats();
  const recent = useFiles({ page: 1, page_size: RECENT_FILES, sort: "created_at", order: "desc" });
  const files = stats.data?.files;
  const features = stats.data?.features;

  return (
    <PageContainer>
      <PageHeader
        title="Geospatial workspace"
        description="Upload, inspect and measure spatial datasets."
        breadcrumb={[{ label: "Overview" }]}
        actions={
          <>
            <ButtonLink to="/files/upload" variant="primary" icon={Upload}>
              Upload dataset
            </ButtonLink>
            <ButtonLink to="/files" icon={Files}>
              View files
            </ButtonLink>
          </>
        }
      />

      <div className={styles.stack}>
        {stats.isError ? (
          <Card>
            <ErrorState title="Unable to load workspace statistics." error={stats.error} onRetry={() => stats.refetch()} />
          </Card>
        ) : (
          <StatStrip label="Workspace statistics">
            <StatCard
              label="Files processed"
              value={formatInteger(files?.completed)}
              hint={files ? `${formatInteger(files.total)} uploaded in total` : undefined}
              isLoading={stats.isPending}
            />
            <StatCard
              label="Features indexed"
              value={formatInteger(features?.total_features)}
              hint="Across completed files"
              isLoading={stats.isPending}
            />
            <StatCard
              label="Features measured"
              value={formatInteger(features?.measured_features)}
              hint={features ? percent(features.measured_features, features.total_features) : undefined}
              isLoading={stats.isPending}
            />
            <StatCard
              label="Failed jobs"
              value={formatInteger(files?.failed)}
              hint={files && files.in_progress > 0 ? `${formatInteger(files.in_progress)} in progress` : "Uploads that could not be processed"}
              isLoading={stats.isPending}
            />
          </StatStrip>
        )}

        <Card
          title="Recent files"
          actions={
            recent.data && recent.data.total > RECENT_FILES ? (
              <ButtonLink to="/files" size="sm" variant="ghost">
                All {formatInteger(recent.data.total)} files
              </ButtonLink>
            ) : undefined
          }
          flush
        >
          {recent.isError ? (
            <ErrorState title="Unable to load recent files." error={recent.error} onRetry={() => recent.refetch()} />
          ) : (
            <FilesTable
              caption="Recent files"
              files={recent.data?.items}
              isLoading={recent.isPending}
              skeletonRows={4}
              columns={["file", "type", "features", "crs", "status", "uploaded", "actions"]}
              empty={
                <EmptyState
                  title="No geospatial files yet."
                  description="Upload a KML file or a zipped Shapefile to see its features, coordinate system and measurements."
                  actions={
                    <ButtonLink to="/files/upload" variant="primary" icon={Upload}>
                      Upload your first dataset
                    </ButtonLink>
                  }
                />
              }
            />
          )}
        </Card>

        <Card
          title="Measurement overview"
          description={
            features && features.total_features > 0
              ? `${formatArea(features.total_area_square_meters)} of polygon area and ${formatLength(features.total_length_meters)} of line length measured.`
              : "Feature types and measurement outcomes across completed files."
          }
        >
          {stats.isPending ? (
            <Skeleton height={120} />
          ) : features && features.total_features > 0 ? (
            <MeasurementOverview summary={features} />
          ) : (
            <p className={styles.muted}>Measurements appear here once a dataset has been processed.</p>
          )}
        </Card>
      </div>
    </PageContainer>
  );
}
