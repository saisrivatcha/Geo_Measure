import { ChevronLeft, ChevronRight } from "lucide-react";
import { useId } from "react";

import { Button } from "@/components/ui/Button";
import { formatInteger } from "@/utils/format";

import styles from "./Pagination.module.css";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  pageSizeOptions?: number[];
  itemLabel?: string;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
}

export function Pagination({
  page,
  pageSize,
  total,
  pageSizeOptions = [25, 50, 100],
  itemLabel = "rows",
  onPageChange,
  onPageSizeChange,
}: PaginationProps) {
  const sizeId = useId();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <nav className={styles.pagination} aria-label="Pagination">
      <p aria-live="polite">
        {formatInteger(first)}–{formatInteger(last)} of {formatInteger(total)} {itemLabel}
      </p>
      <div className={styles.controls}>
        {onPageSizeChange && (
          <div className={styles.pageSize}>
            <label htmlFor={sizeId}>Rows per page</label>
            <select
              id={sizeId}
              value={pageSize}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
            >
              {pageSizeOptions.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </div>
        )}
        <span>
          Page {page} of {totalPages}
        </span>
        <div className={styles.buttons}>
          <Button
            size="sm"
            icon={ChevronLeft}
            iconOnly
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            Previous page
          </Button>
          <Button
            size="sm"
            icon={ChevronRight}
            iconOnly
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            Next page
          </Button>
        </div>
      </div>
    </nav>
  );
}
