import { SearchField, SelectField } from "@/components/ui/Field";
import type { FileSortField, FileStatus, FileType, SortOrder } from "@/types/api";

import styles from "./FileFilters.module.css";

export const SORT_OPTIONS: { value: string; label: string; sort: FileSortField; order: SortOrder }[] = [
  { value: "newest", label: "Newest first", sort: "created_at", order: "desc" },
  { value: "oldest", label: "Oldest first", sort: "created_at", order: "asc" },
  { value: "name", label: "Name (A–Z)", sort: "filename", order: "asc" },
  { value: "features", label: "Most features", sort: "feature_count", order: "desc" },
  { value: "size", label: "Largest file", sort: "file_size_bytes", order: "desc" },
];

export interface FileFilterValues {
  q: string;
  type: FileType | "";
  status: FileStatus | "";
  sort: string;
}

interface FileFiltersProps {
  values: FileFilterValues;
  onChange: (values: Partial<FileFilterValues>) => void;
}

export function FileFilters({ values, onChange }: FileFiltersProps) {
  return (
    <div className={styles.toolbar} role="search" aria-label="Filter files">
      <SearchField
        className={styles.search}
        label="Search files"
        hideLabel
        placeholder="Search by file name"
        value={values.q}
        onChange={(event) => onChange({ q: event.target.value })}
      />
      <SelectField
        label="Type"
        hideLabel
        value={values.type}
        onChange={(event) => onChange({ type: event.target.value as FileType | "" })}
        options={[
          { value: "", label: "All types" },
          { value: "KML", label: "KML" },
          { value: "SHAPEFILE", label: "Shapefile" },
        ]}
      />
      <SelectField
        label="Status"
        hideLabel
        value={values.status}
        onChange={(event) => onChange({ status: event.target.value as FileStatus | "" })}
        options={[
          { value: "", label: "All statuses" },
          { value: "COMPLETED", label: "Completed" },
          { value: "PROCESSING", label: "Processing" },
          { value: "PENDING", label: "Pending" },
          { value: "FAILED", label: "Failed" },
        ]}
      />
      <SelectField
        label="Sort"
        hideLabel
        value={values.sort}
        onChange={(event) => onChange({ sort: event.target.value })}
        options={SORT_OPTIONS.map(({ value, label }) => ({ value, label }))}
      />
    </div>
  );
}
