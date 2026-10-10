import { Check, Circle, FileArchive, FileText, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

import type { UploadPhase } from "@/hooks/useUploadFlow";
import { formatBytes } from "@/utils/format";

import styles from "./UploadProgress.module.css";

/** What the server does inside the single upload request (backend processor order). */
const SERVER_STEPS = [
  "Validating dataset",
  "Reading geospatial features",
  "Resolving coordinate system",
  "Calculating measurements",
] as const;

type StepState = "pending" | "active" | "done";

function StepIcon({ state }: { state: StepState }) {
  if (state === "done") return <Check size={16} className={styles.check} aria-hidden="true" />;
  if (state === "active") return <LoaderCircle size={16} className={styles.spin} aria-hidden="true" />;
  return <Circle size={10} aria-hidden="true" />;
}

function Step({ label, state }: { label: string; state: StepState }) {
  const className = [styles.step, state === "active" ? styles.active : "", state === "done" ? styles.done : ""].join(" ");
  return (
    <li className={className}>
      <span className={styles.stepIcon}>
        <StepIcon state={state} />
      </span>
      <span>
        {label}
        {state === "active" ? "…" : ""}
        <span className="visually-hidden">{state === "done" ? " (done)" : state === "active" ? " (in progress)" : ""}</span>
      </span>
    </li>
  );
}

export function SelectedFile({ file, actions }: { file: File; actions?: ReactNode }) {
  const isZip = file.name.toLowerCase().endsWith(".zip");
  const Icon = isZip ? FileArchive : FileText;
  return (
    <div className={styles.file}>
      <span className={styles.fileIcon} aria-hidden="true">
        <Icon size={18} />
      </span>
      <span className={styles.fileText}>
        <span className={styles.fileName}>{file.name}</span>
        <span className={styles.fileMeta}>
          {isZip ? "ZIP archive (Shapefile)" : "KML document"}, {formatBytes(file.size)}
        </span>
      </span>
      {actions}
    </div>
  );
}

interface UploadProgressProps {
  phase: UploadPhase;
  progress: number | null;
}

/**
 * Progress tied to the request lifecycle: real byte progress while uploading;
 * then an indeterminate state while the server processes the dataset (the API
 * reports no intermediate steps, so the server steps share one indicator).
 */
export function UploadProgress({ phase, progress }: UploadProgressProps) {
  const uploadState: StepState = phase === "uploading" ? "active" : "done";
  const serverState: StepState = phase === "uploading" ? "pending" : phase === "processing" ? "active" : "done";
  const previewState: StepState = phase === "preparing" ? "active" : phase === "completed" ? "done" : "pending";
  const percent = progress === null ? null : Math.round(progress * 100);

  return (
    <div className={styles.panel} aria-live="polite">
      <ol className={styles.steps}>
        <Step label="Uploading file" state={uploadState} />
        {phase === "uploading" && percent !== null && (
          <li aria-hidden="true">
            <div className={styles.bar}>
              <div className={styles.barFill} style={{ width: `${percent}%` }} />
            </div>
          </li>
        )}
        <li>
          <div className={`${styles.serverGroup} ${serverState === "active" ? styles.serverGroupActive : ""}`}>
            <ol className={styles.steps}>
              {SERVER_STEPS.map((label) => (
                <Step key={label} label={label} state={serverState} />
              ))}
            </ol>
            {serverState === "active" && (
              <p className={styles.serverNote}>
                The server runs these steps in a single request; large datasets can take a little while.
              </p>
            )}
          </div>
        </li>
        <Step label="Preparing map preview" state={previewState} />
      </ol>
    </div>
  );
}
