import { LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

import styles from "./Badge.module.css";

export type BadgeTone = "neutral" | "success" | "progress" | "danger" | "info";

interface BadgeProps {
  tone?: BadgeTone;
  /** Leading marker: a dot, a spinner for work in progress, or nothing. */
  marker?: "dot" | "spinner" | "none";
  title?: string;
  children: ReactNode;
}

export function Badge({ tone = "neutral", marker = "dot", title, children }: BadgeProps) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`} title={title}>
      {marker === "dot" && <span className={styles.dot} aria-hidden="true" />}
      {marker === "spinner" && <LoaderCircle size={12} className={styles.spin} aria-hidden="true" />}
      {children}
    </span>
  );
}
