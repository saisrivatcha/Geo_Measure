import "leaflet/dist/leaflet.css";

import L, { type LatLngExpression, type PathOptions } from "leaflet";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { GeoJSON, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";

import type { GeoJSONFeature } from "@/types/api";
import { FAMILY_COLORS, geometryFamily, type GeometryFamily } from "@/utils/geometry";

import styles from "./DatasetMap.module.css";
import { FeaturePopup } from "./FeaturePopup";
import { MapControls } from "./MapControls";

const FAMILIES: GeometryFamily[] = ["polygon", "line", "point", "other"];
const OSM_TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

type MappableFeature = GeoJSONFeature & { geometry: GeoJSON.Geometry };

function styleFor(family: GeometryFamily, selected: boolean): PathOptions {
  const color = FAMILY_COLORS[family];
  return {
    color,
    weight: selected ? 4 : family === "line" ? 2.5 : 1.5,
    opacity: 1,
    fillColor: color,
    fillOpacity: family === "polygon" ? (selected ? 0.38 : 0.18) : 0.85,
  };
}

function boundsOf(features: MappableFeature[]): L.LatLngBounds | null {
  if (features.length === 0) return null;
  const bounds = L.geoJSON({ type: "FeatureCollection", features } as GeoJSON.FeatureCollection).getBounds();
  return bounds.isValid() ? bounds : null;
}

function FitBounds({ bounds, version }: { bounds: L.LatLngBounds | null; version: number }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [32, 32], maxZoom: 17 });
  }, [map, bounds, version]);
  return null;
}

interface DatasetMapProps {
  features: GeoJSONFeature[];
  fileId?: string;
  /** Feature to emphasise (e.g. the row opened in the measurements table). */
  selectedIndex?: number | null;
  height?: number;
  showLayerControls?: boolean;
  /** Short note about what the map omits (truncation, missing CRS...). */
  note?: string | null;
  /** Message shown over the map when no feature can be drawn. */
  emptyMessage?: string;
}

/**
 * Leaflet map on OpenStreetMap tiles, one layer per geometry family so they can
 * be toggled. Features arrive in EPSG:4326 from the API's GeoJSON endpoint.
 */
export function DatasetMap({
  features,
  fileId,
  selectedIndex = null,
  height = 480,
  showLayerControls = true,
  note,
  emptyMessage = "No feature in this dataset can be placed on a map.",
}: DatasetMapProps) {
  const [hidden, setHidden] = useState<Set<GeometryFamily>>(new Set());
  const [popup, setPopup] = useState<{ feature: GeoJSONFeature; latlng: LatLngExpression } | null>(null);
  const [fitVersion, setFitVersion] = useState(0);

  const mappable = useMemo(
    () => features.filter((feature): feature is MappableFeature => feature.geometry !== null),
    [features],
  );
  const byFamily = useMemo(() => {
    const groups: Record<GeometryFamily, MappableFeature[]> = { polygon: [], line: [], point: [], other: [] };
    for (const feature of mappable) groups[geometryFamily(feature.geomeasure.geometry_type)].push(feature);
    return groups;
  }, [mappable]);
  const bounds = useMemo(() => boundsOf(mappable), [mappable]);
  const presentFamilies = FAMILIES.filter((family) => byFamily[family].length > 0);

  const toggle = (family: GeometryFamily) =>
    setHidden((current) => {
      const next = new Set(current);
      if (next.has(family)) next.delete(family);
      else next.add(family);
      return next;
    });

  return (
    <div className={styles.frame} style={{ "--map-height": `${height}px` } as CSSProperties}>
      <MapContainer
        className={styles.map}
        center={[20, 0]}
        zoom={2}
        scrollWheelZoom
        worldCopyJump
        aria-label="Dataset map"
      >
        <TileLayer url={OSM_TILES} attribution={OSM_ATTRIBUTION} maxZoom={19} />
        <FitBounds bounds={bounds} version={fitVersion} />
        {presentFamilies
          .filter((family) => !hidden.has(family))
          .map((family) => (
            <GeoJSON
              key={`${family}-${selectedIndex ?? "none"}-${byFamily[family].length}`}
              data={{ type: "FeatureCollection", features: byFamily[family] } as GeoJSON.FeatureCollection}
              style={(feature) => styleFor(family, (feature as GeoJSONFeature | undefined)?.id === selectedIndex)}
              pointToLayer={(feature, latlng) =>
                L.circleMarker(latlng, {
                  ...styleFor(family, (feature as GeoJSONFeature).id === selectedIndex),
                  radius: (feature as GeoJSONFeature).id === selectedIndex ? 8 : 5,
                  color: "#ffffff",
                  weight: 1.5,
                  fillColor: FAMILY_COLORS[family],
                })
              }
              eventHandlers={{
                click: (event) => {
                  const layer = event.propagatedFrom as L.Layer & { feature?: GeoJSONFeature };
                  if (layer.feature) setPopup({ feature: layer.feature, latlng: event.latlng });
                },
              }}
            />
          ))}
        {popup && (
          <Popup position={popup.latlng} eventHandlers={{ remove: () => setPopup(null) }}>
            <FeaturePopup feature={popup.feature} fileId={fileId} />
          </Popup>
        )}
      </MapContainer>

      {showLayerControls && presentFamilies.length > 0 && (
        <MapControls
          families={presentFamilies}
          counts={Object.fromEntries(presentFamilies.map((f) => [f, byFamily[f].length])) as Record<GeometryFamily, number>}
          hidden={hidden}
          onToggle={toggle}
          onFit={() => setFitVersion((v) => v + 1)}
        />
      )}

      {note && mappable.length > 0 && <p className={styles.note}>{note}</p>}
      {mappable.length === 0 && <div className={styles.empty}>{emptyMessage}</div>}
    </div>
  );
}
