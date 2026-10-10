import { ArrowRight, Info } from "lucide-react";

import type { FileRecord } from "@/types/api";

import styles from "./CRSPanel.module.css";

function explanation(file: FileRecord): string {
  if (!file.source_crs) {
    return "The dataset does not define a coordinate reference system (for a Shapefile, the .prj file is missing). Polygons and lines were not measured, because metric values would be guesses.";
  }
  if (!file.measurement_crs) {
    return "Nothing in this dataset needed measuring, so no measurement CRS was chosen.";
  }
  if (file.measurement_crs === file.source_crs) {
    return "The source data is already in a projected coordinate system in linear units with low distortion over this dataset, so areas and lengths were calculated directly in it.";
  }
  return "Measurements are calculated in a projected coordinate system to avoid using latitude/longitude degrees for area and distance calculations. The projection was chosen for this dataset's location.";
}

function SystemBlock({ role, code, name }: { role: string; code: string | null; name: string | null }) {
  return (
    <div className={styles.system}>
      <dt className={styles.role}>{role}</dt>
      <dd style={{ margin: 0 }}>
        {code ? (
          <>
            <p className={styles.code}>{code}</p>
            {name && <p className={styles.name}>{name}</p>}
          </>
        ) : (
          <p className={`${styles.code} ${styles.missing}`}>Not available</p>
        )}
      </dd>
    </div>
  );
}

/** Source and measurement CRS exactly as reported by the API, with why they differ. */
export function CRSPanel({ file }: { file: FileRecord }) {
  return (
    <section className={styles.panel} aria-labelledby="crs-panel-title">
      <div className={styles.neatline}>
        <span className={styles.ticks} aria-hidden="true" />
        <h2 className={styles.title} id="crs-panel-title">
          Coordinate reference systems
        </h2>
        <dl className={styles.systems}>
          <SystemBlock role="Source CRS" code={file.source_crs} name={file.source_crs_name} />
          <ArrowRight size={18} className={styles.arrow} aria-hidden="true" />
          <SystemBlock role="Measurement CRS" code={file.measurement_crs} name={file.measurement_crs_name} />
        </dl>
        {file.source_crs_assumed && (
          <p className={styles.assumed}>
            Not stated in the file: KML coordinates are WGS 84 longitude/latitude by specification.
          </p>
        )}
        <p className={styles.note}>
          <Info size={14} aria-hidden="true" />
          {explanation(file)}
        </p>
      </div>
    </section>
  );
}
