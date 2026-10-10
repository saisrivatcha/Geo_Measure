import { Badge, type BadgeTone } from "@/components/ui/Badge";
import type { FileStatus, MeasurementStatus } from "@/types/api";
import {
  FILE_STATUS_LABELS,
  MEASUREMENT_STATUS_HINTS,
  MEASUREMENT_STATUS_LABELS,
} from "@/utils/format";

const FILE_TONES: Record<FileStatus, BadgeTone> = {
  PENDING: "progress",
  PROCESSING: "progress",
  COMPLETED: "success",
  FAILED: "danger",
};

export function StatusBadge({ status }: { status: FileStatus }) {
  const working = status === "PENDING" || status === "PROCESSING";
  return (
    <Badge tone={FILE_TONES[status]} marker={working ? "spinner" : "dot"}>
      {FILE_STATUS_LABELS[status]}
    </Badge>
  );
}

const MEASUREMENT_TONES: Record<MeasurementStatus, BadgeTone> = {
  COMPLETED: "success",
  NOT_REQUIRED: "neutral",
  NOT_SUPPORTED: "neutral",
  NO_GEOMETRY: "neutral",
  INVALID_GEOMETRY: "danger",
  CRS_UNAVAILABLE: "progress",
  FAILED: "danger",
};

export function MeasurementStatusBadge({ status }: { status: MeasurementStatus }) {
  return (
    <Badge tone={MEASUREMENT_TONES[status]} title={MEASUREMENT_STATUS_HINTS[status]}>
      {MEASUREMENT_STATUS_LABELS[status]}
    </Badge>
  );
}
