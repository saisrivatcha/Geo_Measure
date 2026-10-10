import { ArrowLeft } from "lucide-react";
import { useCallback } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { Pagination } from "@/components/data/Pagination";
import { StatCard, StatStrip } from "@/components/data/StatCard";
import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, NotFoundState } from "@/components/ui/States";
import { FeatureDetailPanel } from "@/features/measurements/FeatureDetailPanel";
import { MeasurementsTable } from "@/features/measurements/MeasurementsTable";
import { useFeature, useFile, useMeasurements } from "@/hooks/queries";
import { ApiError } from "@/services/api";
import { formatArea, formatInteger, formatLength } from "@/utils/format";

const PAGE_SIZES = [25, 50, 100, 200];

export function MeasurementsPage() {
  const { id = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const pageSize = PAGE_SIZES.includes(Number(params.get("page_size"))) ? Number(params.get("page_size")) : 50;
  const featureParam = params.get("feature");
  const selectedIndex = featureParam !== null && /^\d+$/.test(featureParam) ? Number(featureParam) : null;

  const file = useFile(id);
  const measurements = useMeasurements(id, { page, page_size: pageSize });
  // A feature linked from the map may not be on the current page: fetch it directly.
  const selectedOnPage = measurements.data?.features.find((f) => f.feature_index === selectedIndex) ?? null;
  const selectedFetched = useFeature(id, selectedOnPage ? null : selectedIndex);
  const selected = selectedOnPage ?? selectedFetched.data ?? null;

  const update = useCallback(
    (changes: Record<string, string | number | null>) =>
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          for (const [key, value] of Object.entries(changes)) {
            if (value === null) next.delete(key);
            else next.set(key, String(value));
          }
          return next;
        },
        { replace: true },
      ),
    [setParams],
  );
  const closeDetail = useCallback(() => update({ feature: null }), [update]);

  const filename = file.data?.filename ?? "File";
  const breadcrumb = [
    { label: "Files", to: "/files" },
    { label: filename, to: `/files/${id}` },
    { label: "Measurements" },
  ];
  const back = (
    <ButtonLink to={`/files/${id}`} icon={ArrowLeft}>
      Back to file
    </ButtonLink>
  );

  const error = measurements.error;
  if (measurements.isError && error instanceof ApiError && (error.status === 404 || error.status === 409)) {
    return (
      <PageContainer>
        <PageHeader title="Measurements" breadcrumb={breadcrumb} />
        <Card>
          {error.status === 404 ? (
            <NotFoundState
              title="This file does not exist."
              description="It may have been removed, or the link is incorrect."
              actions={<ButtonLink to="/files" icon={ArrowLeft}>Back to Files</ButtonLink>}
            />
          ) : (
            <EmptyState
              title="No measurements for this file."
              description={
                typeof error.details.processing_error === "string"
                  ? `Processing failed: ${error.details.processing_error}`
                  : error.message
              }
              actions={back}
            />
          )}
        </Card>
      </PageContainer>
    );
  }

  const summary = measurements.data?.summary;

  return (
    <PageContainer>
      <PageHeader
        title="Measurements"
        documentTitle={`Measurements: ${filename}`}
        description="Feature-level area and length calculations."
        breadcrumb={breadcrumb}
        actions={back}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
        <StatStrip label="Measurement summary">
          <StatCard label="Total features" value={formatInteger(summary?.total_features)} isLoading={!summary} />
          <StatCard
            label="Measured"
            value={formatInteger(summary?.measured_features)}
            hint={
              summary
                ? [
                    summary.polygon_count ? `${formatArea(summary.total_area_square_meters)} area` : null,
                    summary.line_count ? `${formatLength(summary.total_length_meters)} length` : null,
                  ]
                    .filter(Boolean)
                    .join(", ") || undefined
                : undefined
            }
            isLoading={!summary}
          />
          <StatCard
            label="Unsupported"
            value={formatInteger(summary?.unsupported_features)}
            hint="Collections and unknown types"
            isLoading={!summary}
          />
          <StatCard
            label="Invalid"
            value={formatInteger(summary?.invalid_features)}
            hint="Geometry could not be repaired"
            isLoading={!summary}
          />
        </StatStrip>

        <Card
          title="Features"
          description={
            measurements.data
              ? `Measured in ${measurements.data.measurement_crs ?? "no projected CRS"}; source data in ${measurements.data.source_crs ?? "an undefined CRS"}. Select a row for details.`
              : undefined
          }
          flush
        >
          {measurements.isError ? (
            <ErrorState
              title="Unable to load measurements."
              description="The dataset may have been removed or the API is unavailable."
              error={error}
              onRetry={() => measurements.refetch()}
              actions={back}
            />
          ) : (
            <>
              <MeasurementsTable
                features={measurements.data?.features}
                isLoading={measurements.isPending}
                isFetching={measurements.isFetching && !measurements.isPending}
                selectedIndex={selectedIndex}
                onSelect={(feature) => update({ feature: feature.feature_index })}
                empty={
                  <EmptyState
                    title="This page is empty."
                    description="The page is past the last feature of this file."
                    actions={<Button onClick={() => update({ page: null })}>Go to first page</Button>}
                  />
                }
              />
              {measurements.data && measurements.data.total > 0 && (
                <Pagination
                  page={page}
                  pageSize={pageSize}
                  total={measurements.data.total}
                  pageSizeOptions={PAGE_SIZES}
                  itemLabel="features"
                  onPageChange={(next) => update({ page: next === 1 ? null : next })}
                  onPageSizeChange={(size) => update({ page_size: size === 50 ? null : size, page: null })}
                />
              )}
            </>
          )}
        </Card>
      </div>

      <FeatureDetailPanel fileId={id} feature={selected} onClose={closeDetail} />
    </PageContainer>
  );
}
