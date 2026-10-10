import type { CSSProperties, KeyboardEvent, ReactNode } from "react";

import { TableSkeleton } from "@/components/ui/Skeleton";

import styles from "./DataTable.module.css";

export interface Column<Row> {
  key: string;
  header: ReactNode;
  cell: (row: Row) => ReactNode;
  align?: "start" | "end";
  nowrap?: boolean;
  width?: string;
}

interface DataTableProps<Row> {
  caption: string;
  columns: Column<Row>[];
  rows: Row[] | undefined;
  getRowKey: (row: Row) => string | number;
  /** Rows become keyboard-focusable and activate on click / Enter. */
  onRowClick?: (row: Row) => void;
  rowLabel?: (row: Row) => string;
  isSelected?: (row: Row) => boolean;
  isLoading?: boolean;
  /** True while a new page loads over existing rows. */
  isFetching?: boolean;
  empty?: ReactNode;
  skeletonRows?: number;
  maxHeight?: string;
}

/**
 * Accessible data table with a sticky header and horizontal scrolling on narrow
 * screens. It renders only the rows it is given; paging happens on the server.
 */
export function DataTable<Row>({
  caption,
  columns,
  rows,
  getRowKey,
  onRowClick,
  rowLabel,
  isSelected,
  isLoading = false,
  isFetching = false,
  empty,
  skeletonRows = 6,
  maxHeight,
}: DataTableProps<Row>) {
  if (isLoading && !rows) {
    return <TableSkeleton rows={skeletonRows} columns={Math.min(columns.length, 7)} label={`Loading ${caption}`} />;
  }
  if (rows && rows.length === 0 && empty) return <>{empty}</>;

  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, row: Row) => {
    if (event.target !== event.currentTarget) return; // let nested links/buttons work
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onRowClick?.(row);
    }
  };

  return (
    <div
      className={`${styles.wrapper} ${isFetching ? styles.fetching : ""}`}
      style={maxHeight ? ({ "--table-max-height": maxHeight } as CSSProperties) : undefined}
      aria-busy={isFetching || undefined}
    >
      <table className={styles.table}>
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={column.align === "end" ? styles.end : undefined}
                style={column.width ? { width: column.width } : undefined}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows?.map((row) => {
            const selected = isSelected?.(row) ?? false;
            const classNames = [onRowClick ? styles.clickable : "", selected ? styles.selected : ""]
              .filter(Boolean)
              .join(" ");
            return (
              <tr
                key={getRowKey(row)}
                className={classNames || undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={onRowClick ? (event) => onKeyDown(event, row) : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                aria-label={onRowClick && rowLabel ? rowLabel(row) : undefined}
                aria-current={selected ? "true" : undefined}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={
                      [column.align === "end" ? styles.end : "", column.nowrap ? styles.nowrap : ""]
                        .filter(Boolean)
                        .join(" ") || undefined
                    }
                  >
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
