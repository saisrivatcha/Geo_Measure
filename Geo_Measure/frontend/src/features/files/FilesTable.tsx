import { Map as MapIcon, Ruler } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { DataTable, type Column } from "@/components/data/DataTable";
import { StatusBadge } from "@/components/data/StatusBadge";
import { ButtonLink } from "@/components/ui/Button";
import type { FileRecord } from "@/types/api";
import { FILE_TYPE_LABELS, formatDateTime, formatInteger, formatRelative } from "@/utils/format";

import styles from "./FilesTable.module.css";

type ColumnKey = "file" | "type" | "features" | "sourceCrs" | "measurementCrs" | "crs" | "status" | "uploaded" | "actions";

const COLUMNS: Record<ColumnKey, Column<FileRecord>> = {
  file: {
    key: "file",
    header: "File",
    cell: (file) => (
      <span className={styles.fileCell}>
        <span className={styles.fileName}>{file.filename}</span>
      </span>
    ),
  },
  type: { key: "type", header: "Type", nowrap: true, cell: (file) => FILE_TYPE_LABELS[file.file_type] },
  features: {
    key: "features",
    header: "Features",
    align: "end",
    cell: (file) => formatInteger(file.feature_count),
  },
  sourceCrs: {
    key: "sourceCrs",
    header: "Source CRS",
    nowrap: true,
    cell: (file) => <CrsCell code={file.source_crs} name={file.source_crs_name} />,
  },
  measurementCrs: {
    key: "measurementCrs",
    header: "Measurement CRS",
    nowrap: true,
    cell: (file) => <CrsCell code={file.measurement_crs} name={file.measurement_crs_name} />,
  },
  crs: {
    key: "crs",
    header: "CRS",
    nowrap: true,
    cell: (file) => <CrsCell code={file.source_crs} name={file.source_crs_name} />,
  },
  status: { key: "status", header: "Status", cell: (file) => <StatusBadge status={file.status} /> },
  uploaded: {
    key: "uploaded",
    header: "Uploaded",
    nowrap: true,
    cell: (file) => <time dateTime={file.created_at} title={formatDateTime(file.created_at)}>{formatRelative(file.created_at)}</time>,
  },
  actions: {
    key: "actions",
    header: <span className="visually-hidden">Actions</span>,
    align: "end",
    nowrap: true,
    cell: (file) => (
      <span className={styles.actions} onClick={(event) => event.stopPropagation()}>
        <ButtonLink to={`/files/${file.id}`} size="sm" variant="ghost" icon={MapIcon} aria-label={`View ${file.filename}`}>
          View
        </ButtonLink>
        {file.status === "COMPLETED" && (
          <ButtonLink
            to={`/files/${file.id}/measurements`}
            size="sm"
            variant="ghost"
            icon={Ruler}
            aria-label={`Measurements for ${file.filename}`}
          >
            Measurements
          </ButtonLink>
        )}
      </span>
    ),
  },
};

function CrsCell({ code, name }: { code: string | null; name: string | null }) {
  if (!code) return <span className={styles.muted}>None</span>;
  const short = code.length > 24 ? `${code.slice(0, 22)}…` : code;
  return <span title={name ? `${code}: ${name}` : code}>{short}</span>;
}

interface FilesTableProps {
  files: FileRecord[] | undefined;
  columns: ColumnKey[];
  isLoading: boolean;
  isFetching?: boolean;
  empty?: ReactNode;
  caption: string;
  skeletonRows?: number;
}

/** Files with clickable rows (open the file) and explicit actions. */
export function FilesTable({ files, columns, isLoading, isFetching, empty, caption, skeletonRows }: FilesTableProps) {
  const navigate = useNavigate();
  return (
    <DataTable
      caption={caption}
      columns={columns.map((key) => COLUMNS[key])}
      rows={files}
      getRowKey={(file) => file.id}
      onRowClick={(file) => navigate(`/files/${file.id}`)}
      rowLabel={(file) => `Open ${file.filename}`}
      isLoading={isLoading}
      isFetching={isFetching}
      empty={empty}
      skeletonRows={skeletonRows}
    />
  );
}
