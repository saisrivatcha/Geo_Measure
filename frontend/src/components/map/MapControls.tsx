import { Maximize2 } from "lucide-react";
import { useId } from "react";

import { GeometryGlyph } from "@/components/data/GeometryLabel";
import { Button } from "@/components/ui/Button";
import { formatInteger } from "@/utils/format";
import { FAMILY_LABELS, type GeometryFamily } from "@/utils/geometry";

import styles from "./DatasetMap.module.css";

interface MapControlsProps {
  families: GeometryFamily[];
  counts: Record<GeometryFamily, number>;
  hidden: Set<GeometryFamily>;
  onToggle: (family: GeometryFamily) => void;
  onFit: () => void;
}

/** Legend that doubles as layer visibility toggles, plus "fit to data". */
export function MapControls({ families, counts, hidden, onToggle, onFit }: MapControlsProps) {
  const titleId = useId();
  return (
    <div className={styles.controls} role="group" aria-labelledby={titleId}>
      <p className={styles.legendTitle} id={titleId}>
        Layers
      </p>
      {families.map((family) => (
        <label key={family} className={styles.layer}>
          <input type="checkbox" checked={!hidden.has(family)} onChange={() => onToggle(family)} />
          <GeometryGlyph family={family} />
          {FAMILY_LABELS[family]}
          <span className={styles.count}>{formatInteger(counts[family])}</span>
        </label>
      ))}
      <Button size="sm" variant="ghost" icon={Maximize2} className={styles.fit} onClick={onFit}>
        Fit to data
      </Button>
    </div>
  );
}
