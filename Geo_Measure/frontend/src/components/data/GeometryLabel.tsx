import { FAMILY_COLORS, geometryFamily, type GeometryFamily } from "@/utils/geometry";

import styles from "./GeometryLabel.module.css";

/** The legend mark for a geometry family: filled square, stroke, or dot. */
export function GeometryGlyph({ family, size = 12 }: { family: GeometryFamily; size?: number }) {
  const color = FAMILY_COLORS[family];
  return (
    <svg className={styles.glyph} width={size} height={size} viewBox="0 0 12 12" aria-hidden="true">
      {family === "polygon" && (
        <rect x="1" y="1" width="10" height="10" rx="1.5" fill={color} fillOpacity="0.25" stroke={color} strokeWidth="1.5" />
      )}
      {family === "line" && <path d="M1 10 L5 4 L8 7 L11 2" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />}
      {family === "point" && <circle cx="6" cy="6" r="4" fill={color} />}
      {family === "other" && <rect x="2" y="2" width="8" height="8" fill="none" stroke={color} strokeWidth="1.5" strokeDasharray="2 1.5" />}
    </svg>
  );
}

export function GeometryLabel({ geometryType }: { geometryType: string | null }) {
  return (
    <span className={styles.label}>
      <GeometryGlyph family={geometryFamily(geometryType)} />
      {geometryType ?? "No geometry"}
    </span>
  );
}
