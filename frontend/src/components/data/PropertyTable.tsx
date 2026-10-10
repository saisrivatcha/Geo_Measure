import type { ReactNode } from "react";

import type { JsonValue, Properties } from "@/types/api";

import styles from "./PropertyTable.module.css";

function renderValue(value: JsonValue): ReactNode {
  if (value === null) return <span className={styles.null}>null</span>;
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

interface PropertyTableProps {
  properties: Properties;
  /** Show only the first N keys (e.g. in map popups). */
  limit?: number;
  emptyText?: string;
}

/** Feature attributes as a key/value list, rendered from the API's JSON values. */
export function PropertyTable({ properties, limit, emptyText = "No attributes." }: PropertyTableProps) {
  const entries = Object.entries(properties);
  if (entries.length === 0) return <p className={styles.empty}>{emptyText}</p>;
  const shown = limit ? entries.slice(0, limit) : entries;

  return (
    <>
      <dl className={styles.list}>
        {shown.map(([key, value]) => (
          <div key={key} style={{ display: "contents" }}>
            <dt>{key}</dt>
            <dd>{renderValue(value)}</dd>
          </div>
        ))}
      </dl>
      {limit && entries.length > limit && (
        <p className={styles.empty}>
          {entries.length - limit} more attribute{entries.length - limit === 1 ? "" : "s"}
        </p>
      )}
    </>
  );
}

/** Generic definition list for metadata (label/value pairs). */
export function DefinitionList({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className={styles.list}>
      {items.map((item) => (
        <div key={item.label} style={{ display: "contents" }}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
