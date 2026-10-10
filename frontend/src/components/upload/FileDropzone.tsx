import { TriangleAlert, Upload } from "lucide-react";
import { useId, useRef, useState, type DragEvent } from "react";

import { Button } from "@/components/ui/Button";
import { formatBytes } from "@/utils/format";

import styles from "./FileDropzone.module.css";

export interface DropzoneLimits {
  maxBytes: number | null;
  allowedExtensions: string[];
}

export function validateSelection(file: File, limits: DropzoneLimits): string | null {
  const name = file.name.toLowerCase();
  if (name.endsWith(".kmz")) return "KMZ files are not supported. Extract the .kml from the KMZ and upload that.";
  const extension = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";
  if (!limits.allowedExtensions.includes(extension)) {
    return `${file.name} is not a supported file. Choose a .kml file or a .zip containing a Shapefile.`;
  }
  if (file.size === 0) return `${file.name} is empty.`;
  if (limits.maxBytes !== null && file.size > limits.maxBytes) {
    return `${file.name} is ${formatBytes(file.size)}; the limit is ${formatBytes(limits.maxBytes)}.`;
  }
  return null;
}

interface FileDropzoneProps {
  limits: DropzoneLimits;
  onSelect: (file: File) => void;
  disabled?: boolean;
}

/**
 * Drop target plus a real "Choose file" button, so the uploader works with a
 * keyboard and screen reader as well as drag and drop. Files are only
 * selected here; uploading needs an explicit action.
 */
export function FileDropzone({ limits, onSelect, disabled = false }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titleId = useId();
  const hintId = useId();

  const accept = (files: FileList | null) => {
    if (disabled || !files || files.length === 0) return;
    if (files.length > 1) {
      setError("Choose one file at a time.");
      return;
    }
    const file = files[0] as File;
    const problem = validateSelection(file, limits);
    setError(problem);
    if (!problem) onSelect(file);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    accept(event.dataTransfer.files);
  };

  return (
    <div
      className={[styles.dropzone, dragging ? styles.dragging : "", disabled ? styles.disabled : ""].join(" ")}
      role="group"
      aria-labelledby={titleId}
      aria-describedby={hintId}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      data-testid="dropzone"
    >
      <span className={styles.icon} aria-hidden="true">
        <Upload size={20} />
      </span>
      <p className={styles.title} id={titleId}>
        Drag and drop your file here
      </p>
      <span className={styles.or}>or</span>
      <Button variant="secondary" onClick={() => inputRef.current?.click()} disabled={disabled}>
        Choose file
      </Button>
      <input
        ref={inputRef}
        className={styles.input}
        type="file"
        accept={limits.allowedExtensions.join(",")}
        aria-label="Dataset file"
        onChange={(event) => {
          accept(event.target.files);
          event.target.value = "";
        }}
        tabIndex={-1}
      />
      <ul className={styles.formats} id={hintId}>
        <li>
          <strong>KML</strong> document (.kml)
        </li>
        <li>
          <strong>ZIP</strong> with one Shapefile (.shp, .shx, .dbf; .prj recommended)
        </li>
        <li>{limits.maxBytes !== null ? `Up to ${formatBytes(limits.maxBytes)}` : "Checking size limit"}</li>
      </ul>
      {error && (
        <p className={styles.error} role="alert">
          <TriangleAlert size={16} aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}
