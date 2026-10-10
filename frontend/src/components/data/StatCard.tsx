import type { CSSProperties, ReactNode } from "react";

import { Skeleton } from "@/components/ui/Skeleton";

import styles from "./StatCard.module.css";

interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  /** Text values (CRS codes, types) use a smaller size than counts. */
  compact?: boolean;
  isLoading?: boolean;
}

export function StatCard({ label, value, hint, compact = false, isLoading = false }: StatCardProps) {
  return (
    <div className={styles.stat}>
      <dt className={styles.label}>{label}</dt>
      <dd className={`${styles.value} ${compact ? styles.valueSmall : ""}`} style={{ margin: 0 }}>
        {isLoading ? <Skeleton width="55%" height={compact ? 18 : 26} /> : value}
      </dd>
      {hint && !isLoading && <dd className={styles.hint} style={{ margin: 0 }}>{hint}</dd>}
    </div>
  );
}

export function StatStrip({ children, columns = 4, label }: { children: ReactNode; columns?: number; label: string }) {
  return (
    <dl className={styles.strip} style={{ "--stat-columns": columns } as CSSProperties} aria-label={label}>
      {children}
    </dl>
  );
}
