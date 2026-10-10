import { LoaderCircle } from "lucide-react";
import type { CSSProperties } from "react";

import styles from "./Skeleton.module.css";

interface SkeletonProps {
  width?: CSSProperties["width"];
  height?: CSSProperties["height"];
  className?: string;
}

/** A placeholder block with the shape of the content that is loading. */
export function Skeleton({ width = "100%", height = 14, className }: SkeletonProps) {
  return (
    <span className={`${styles.skeleton} ${className ?? ""}`} style={{ width, height }} aria-hidden="true" />
  );
}

export function Spinner({ label = "Loading", size = 18 }: { label?: string; size?: number }) {
  return (
    <span role="status" aria-live="polite">
      <LoaderCircle size={size} className={styles.spinner} aria-hidden="true" />
      <span className="visually-hidden">{label}</span>
    </span>
  );
}

interface TableSkeletonProps {
  rows?: number;
  columns?: number;
  label?: string;
}

export function TableSkeleton({ rows = 6, columns = 6, label = "Loading table" }: TableSkeletonProps) {
  const template = { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` };
  return (
    <div className={styles.table} role="status" aria-label={label}>
      <div className={`${styles.tableRow} ${styles.tableHead}`} style={template}>
        {Array.from({ length: columns }, (_, column) => (
          <Skeleton key={column} width="60%" height={10} />
        ))}
      </div>
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className={styles.tableRow} style={template}>
          {Array.from({ length: columns }, (_, column) => (
            <Skeleton key={column} width={column === 0 ? "85%" : `${50 + ((row + column) % 4) * 10}%`} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function MapSkeleton({ label = "Loading map" }: { label?: string }) {
  return (
    <div className={styles.map} role="status" aria-label={label}>
      <div className={styles.mapGrid} aria-hidden="true" />
      <span className={styles.mapLabel}>
        <LoaderCircle size={14} className={styles.spinner} aria-hidden="true" />
        Loading geometries
      </span>
    </div>
  );
}
