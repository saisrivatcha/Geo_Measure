/**
 * Display formatting. These functions only produce strings for the screen; the
 * full-precision numbers from the API are kept untouched in data objects.
 */
import type { FileStatus, FileType, MeasurementStatus } from "@/types/api";

const twoDecimals = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const integer = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const full = new Intl.NumberFormat(undefined, { maximumFractionDigits: 10 });

export function formatInteger(value: number | null | undefined): string {
  return value === null || value === undefined ? "–" : integer.format(value);
}

/** 15234.82731 -> "15,234.83" */
export function formatDecimal(value: number): string {
  return twoDecimals.format(value);
}

/** Full precision for detail views and tooltips. */
export function formatExact(value: number): string {
  return full.format(value);
}

const UNIT_SYMBOLS: Record<string, string> = {
  square_meters: "m²",
  meters: "m",
};

export function unitSymbol(unit: string | null | undefined): string {
  if (!unit) return "";
  return UNIT_SYMBOLS[unit] ?? unit;
}

/** 15234.82731, "square_meters" -> "15,234.83 m²" */
export function formatMeasurement(value: number, unit: string): string {
  return `${formatDecimal(value)} ${unitSymbol(unit)}`;
}

/** Large totals read better in km/km²; small ones stay in m/m². */
export function formatArea(squareMeters: number): string {
  if (squareMeters >= 1_000_000) return `${formatDecimal(squareMeters / 1_000_000)} km²`;
  if (squareMeters >= 10_000) return `${formatDecimal(squareMeters / 10_000)} ha`;
  return `${formatDecimal(squareMeters)} m²`;
}

export function formatLength(meters: number): string {
  if (meters >= 1_000) return `${formatDecimal(meters / 1_000)} km`;
  return `${formatDecimal(meters)} m`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`;
}

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "–" : dateTime.format(date);
}

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const RELATIVE_STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["second", 60],
  ["minute", 60],
  ["hour", 24],
  ["day", 7],
  ["week", 4.35],
  ["month", 12],
  ["year", Number.POSITIVE_INFINITY],
];

export function formatRelative(iso: string, now: Date = new Date()): string {
  let delta = (new Date(iso).getTime() - now.getTime()) / 1000;
  for (const [unit, size] of RELATIVE_STEPS) {
    if (Math.abs(delta) < size) return relative.format(Math.round(delta), unit);
    delta /= size;
  }
  return formatDateTime(iso);
}

export const FILE_TYPE_LABELS: Record<FileType, string> = {
  KML: "KML",
  SHAPEFILE: "Shapefile",
};

export const FILE_STATUS_LABELS: Record<FileStatus, string> = {
  PENDING: "Pending",
  PROCESSING: "Processing",
  COMPLETED: "Completed",
  FAILED: "Failed",
};

export const MEASUREMENT_STATUS_LABELS: Record<MeasurementStatus, string> = {
  COMPLETED: "Completed",
  NOT_REQUIRED: "Not required",
  NOT_SUPPORTED: "Not supported",
  NO_GEOMETRY: "No geometry",
  INVALID_GEOMETRY: "Invalid geometry",
  CRS_UNAVAILABLE: "CRS unavailable",
  FAILED: "Failed",
};

export const MEASUREMENT_STATUS_HINTS: Record<MeasurementStatus, string> = {
  COMPLETED: "Measured in the projected measurement CRS.",
  NOT_REQUIRED: "Points have no length or area.",
  NOT_SUPPORTED: "Geometry collections and unknown types are not measured.",
  NO_GEOMETRY: "The feature has no geometry.",
  INVALID_GEOMETRY: "The geometry is invalid and could not be safely repaired.",
  CRS_UNAVAILABLE: "The dataset has no coordinate reference system, so metric values would be guesses.",
  FAILED: "Measurement was attempted but produced no usable value.",
};
