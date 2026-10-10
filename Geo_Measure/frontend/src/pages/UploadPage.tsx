import { X } from "lucide-react";

import { DefinitionList } from "@/components/data/PropertyTable";
import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { SelectedFile, UploadProgress } from "@/components/upload/UploadProgress";
import { UploadFailure, UploadSuccess } from "@/components/upload/UploadResult";
import { useServiceInfo } from "@/hooks/queries";
import { useUploadFlow } from "@/hooks/useUploadFlow";
import { formatBytes, formatInteger } from "@/utils/format";

import styles from "./UploadPage.module.css";

const DEFAULT_EXTENSIONS = [".kml", ".zip"];

export function UploadPage() {
  const { state, select, start, reset, cancel } = useUploadFlow();
  const info = useServiceInfo();
  const limits = {
    maxBytes: info.data?.upload.max_upload_bytes ?? null,
    allowedExtensions: info.data?.upload.allowed_extensions ?? DEFAULT_EXTENSIONS,
  };
  const busy = state.phase === "uploading" || state.phase === "processing" || state.phase === "preparing";

  return (
    <PageContainer>
      <PageHeader
        title="Upload dataset"
        description="Upload a KML file or ZIP archive containing an ESRI Shapefile."
        breadcrumb={[{ label: "Overview", to: "/" }, { label: "Files", to: "/files" }, { label: "Upload" }]}
      />

      <div className={styles.layout}>
        <Card>
          {state.phase === "idle" && <FileDropzone limits={limits} onSelect={select} />}

          {state.phase === "selected" && state.file && (
            <div className={styles.selected}>
              <SelectedFile
                file={state.file}
                actions={
                  <Button variant="ghost" size="sm" icon={X} iconOnly onClick={reset}>
                    Remove {state.file.name}
                  </Button>
                }
              />
              <p className={styles.hint}>
                The file is processed as soon as you start: features are read, the coordinate system is resolved and
                every polygon and line is measured.
              </p>
              <div className={styles.actions}>
                <Button variant="primary" onClick={() => void start()}>
                  Process dataset
                </Button>
                <Button variant="ghost" onClick={reset}>
                  Choose a different file
                </Button>
              </div>
            </div>
          )}

          {busy && state.file && (
            <div className={styles.selected} aria-busy="true">
              <SelectedFile file={state.file} />
              <UploadProgress phase={state.phase} progress={state.progress} />
              {state.phase === "uploading" && (
                <div className={styles.actions}>
                  <Button variant="ghost" onClick={cancel}>
                    Cancel upload
                  </Button>
                </div>
              )}
            </div>
          )}

          {state.phase === "completed" && state.result && <UploadSuccess result={state.result} onReset={reset} />}
          {state.phase === "failed" && state.error && <UploadFailure error={state.error} onReset={reset} />}
        </Card>

        <aside className={styles.aside} aria-label="Upload requirements">
          <h2 className={styles.asideTitle}>Requirements</h2>
          <DefinitionList
            items={[
              {
                label: "Maximum size",
                value: info.data ? formatBytes(info.data.upload.max_upload_bytes) : info.isError ? "Unknown" : "…",
              },
              { label: "KML", value: "One .kml document. KMZ archives need to be extracted first." },
              {
                label: "Shapefile",
                value: "One .zip with exactly one dataset: .shp, .shx and .dbf, plus .prj for its coordinate system.",
              },
              {
                label: "Map preview",
                value: info.data
                  ? `Up to ${formatInteger(info.data.geojson_preview_max_features)} features are drawn on the map.`
                  : "…",
              },
            ]}
          />
          <p className={styles.note}>
            Without a .prj file a Shapefile is still read, but polygons and lines are not measured: their coordinates
            could be in any unit.
          </p>
        </aside>
      </div>
    </PageContainer>
  );
}
