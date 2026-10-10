import { CircleCheck, CircleX, Map as MapIcon, Ruler, Upload } from "lucide-react";
import { useEffect, useRef } from "react";

import { DefinitionList } from "@/components/data/PropertyTable";
import { Button, ButtonLink } from "@/components/ui/Button";
import type { ApiError } from "@/services/api";
import type { FileProcessingResult } from "@/types/api";
import { formatInteger } from "@/utils/format";

import styles from "./UploadResult.module.css";

function crsText(code: string | null, name: string | null, fallback: string): string {
  if (!code) return fallback;
  return name ? `${code} (${name})` : code;
}

export function UploadSuccess({ result, onReset }: { result: FileProcessingResult; onReset: () => void }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => headingRef.current?.focus(), []);
  const { file, summary } = result;

  return (
    <div className={styles.result}>
      <div className={styles.heading}>
        <CircleCheck size={22} className={styles.success} aria-hidden="true" />
        <h2 ref={headingRef} tabIndex={-1}>
          Dataset processed successfully.
        </h2>
      </div>
      <DefinitionList
        items={[
          { label: "File", value: file.filename },
          {
            label: "Features",
            value: `${formatInteger(file.feature_count)} (${formatInteger(summary.measured_features)} measured)`,
          },
          {
            label: "Source CRS",
            value: crsText(file.source_crs, file.source_crs_name, "Not defined in the dataset"),
          },
          {
            label: "Measurement CRS",
            value: crsText(file.measurement_crs, file.measurement_crs_name, "None: nothing was measured"),
          },
        ]}
      />
      <div className={styles.actions}>
        <ButtonLink to={`/files/${file.id}`} variant="primary" icon={MapIcon}>
          View file
        </ButtonLink>
        <ButtonLink to={`/files/${file.id}/measurements`} icon={Ruler}>
          View measurements
        </ButtonLink>
        <Button variant="ghost" icon={Upload} onClick={onReset}>
          Upload another
        </Button>
      </div>
    </div>
  );
}

export function UploadFailure({ error, onReset }: { error: ApiError; onReset: () => void }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => headingRef.current?.focus(), []);
  const fileId = typeof error.details.file_id === "string" ? error.details.file_id : null;

  return (
    <div className={styles.result} role="alert">
      <div className={styles.heading}>
        <CircleX size={22} className={styles.danger} aria-hidden="true" />
        <h2 ref={headingRef} tabIndex={-1}>
          Could not process dataset.
        </h2>
      </div>
      <p className={styles.message}>{error.message}</p>
      <p className={styles.code}>Error code {error.code}</p>
      <div className={styles.actions}>
        <Button variant="primary" icon={Upload} onClick={onReset}>
          Try another file
        </Button>
        {fileId && <ButtonLink to={`/files/${fileId}`}>View failed upload</ButtonLink>}
      </div>
    </div>
  );
}
