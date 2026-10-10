import { DefinitionList } from "@/components/data/PropertyTable";
import { ApiStatus } from "@/components/layout/ApiStatus";
import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useServiceInfo } from "@/hooks/queries";
import { API_BASE_URL } from "@/services/api";
import { formatBytes, formatInteger, unitSymbol } from "@/utils/format";

import styles from "./SettingsPage.module.css";

const TECHNOLOGY = [
  "FastAPI, SQLAlchemy and PostgreSQL",
  "GeoPandas, Shapely, PyProj and GDAL (via Pyogrio)",
  "React, TypeScript, TanStack Query and Vite",
  "Leaflet with OpenStreetMap tiles",
];

/**
 * Read-only view of how this deployment is configured. Values come from
 * GET /api/meta; they are changed through the backend's environment variables.
 */
export function SettingsPage() {
  const info = useServiceInfo();
  const endpoint = API_BASE_URL ? `${API_BASE_URL}/api` : `${window.location.origin}/api (same origin)`;

  return (
    <PageContainer>
      <PageHeader
        title="Settings"
        description="How this GeoMeasure deployment is configured. Values are set through the backend's environment."
        breadcrumb={[{ label: "Overview", to: "/" }, { label: "Settings" }]}
      />

      {info.isError && (
        <Card>
          <ErrorState title="Unable to load the service configuration." error={info.error} onRetry={() => info.refetch()} />
        </Card>
      )}

      <div className={styles.grid}>
        <Card title="Application">
          <DefinitionList
            items={[
              { label: "API endpoint", value: <span className={styles.wrap}>{endpoint}</span> },
              { label: "API status", value: <ApiStatus /> },
              { label: "Environment", value: info.data?.environment ?? <Skeleton width={90} /> },
              {
                label: "Upload limit",
                value: info.data ? formatBytes(info.data.upload.max_upload_bytes) : <Skeleton width={70} />,
              },
              {
                label: "Accepted files",
                value: info.data ? info.data.upload.allowed_extensions.join(", ") : <Skeleton width={90} />,
              },
              {
                label: "Map preview",
                value: info.data
                  ? `First ${formatInteger(info.data.geojson_preview_max_features)} features per file`
                  : <Skeleton width={160} />,
              },
            ]}
          />
        </Card>

        <Card title="Measurement behaviour">
          <DefinitionList
            items={[
              {
                label: "Area unit",
                value: info.data ? `Square metres (${unitSymbol(info.data.measurement.area_unit)})` : <Skeleton width={120} />,
              },
              {
                label: "Length unit",
                value: info.data ? `Metres (${unitSymbol(info.data.measurement.length_unit)})` : <Skeleton width={90} />,
              },
              {
                label: "Distortion limit",
                value: info.data
                  ? `${(info.data.measurement.max_linear_distortion * 100).toLocaleString()} % scale error`
                  : <Skeleton width={110} />,
              },
            ]}
          />
          <h3 className={styles.subTitle}>Projected CRS strategy</h3>
          <p className={styles.text}>
            Areas and lengths are never calculated in degrees. For each dataset the first of these that keeps scale
            error within the limit across its extent is used:
          </p>
          {info.data ? (
            <ol className={styles.strategy}>
              {info.data.measurement.crs_strategy.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          ) : (
            <Skeleton height={72} />
          )}
          <p className={styles.text}>
            Datasets without a CRS are not measured. A KML file without one is read as WGS 84, as the KML
            specification requires.
          </p>
        </Card>

        <Card title="About">
          <DefinitionList
            items={[
              { label: "Product", value: "GeoMeasure: geospatial measurement, without the manual work." },
              { label: "Web client", value: `Version ${__APP_VERSION__}` },
              { label: "API", value: info.data ? `Version ${info.data.version}` : <Skeleton width={80} /> },
              {
                label: "Technology",
                value: (
                  <ul className={styles.list}>
                    {TECHNOLOGY.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ),
              },
            ]}
          />
        </Card>
      </div>
    </PageContainer>
  );
}
