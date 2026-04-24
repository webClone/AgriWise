/**
 * ZoneGlowLayer — Subtle dual-layer halo for calm zone edges
 *
 * Creates soft, atmospheric depth around zone boundaries.
 * Halos are desaturated earth tones — barely perceptible, never glowing.
 *
 * Visual philosophy: "felt, not seen" — the halo makes the zone
 * feel inferred and spatial, not outlined and drawn.
 *
 * Only renders for hovered + selected zones.
 */

import { GeoJsonLayer } from "@deck.gl/layers";
import { DeckZoneFeature } from "./zoneUtils";

// Halo colors — desaturated, shifted from edge color toward neutral
function getHaloColor(zoneType: string, zoneFamily: string): [number, number, number] {
  const t = zoneType.toLowerCase();
  if (zoneFamily === "trust") return [105, 100, 130];     // cool gray
  if (t.includes("disease") || t.includes("pest")) return [130, 80, 115];     // muted plum
  if (t.includes("nutrient") || t.includes("nitrogen")) return [155, 130, 65]; // dark ochre
  if (t.includes("water") || t.includes("dry") || t.includes("moisture")) return [55, 105, 130]; // deep slate
  if (t.includes("composite") || t.includes("risk")) return [150, 95, 50];    // burnt sienna
  if (zoneFamily === "action") return [65, 120, 80];      // forest
  return [140, 80, 65];                                    // clay
}

/**
 * Returns an array of GeoJsonLayers for the halo effect.
 * Both are non-pickable (purely visual).
 */
export function getZoneGlowLayers({
  id = "zone-glow",
  featureCollection,
  visible = true,
}: {
  id?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  featureCollection: any;
  visible?: boolean;
}): (GeoJsonLayer | null)[] {
  if (!visible || !featureCollection) return [];

  const glowFeatures = featureCollection.features.filter(
    (f: DeckZoneFeature) => f.properties.isSelected || f.properties.isHovered
  );
  if (glowFeatures.length === 0) return [];

  const glowData = { ...featureCollection, features: glowFeatures };

  // ── Inner glow: visible feathered edge for presence ─────────────────────
  const innerGlow = new GeoJsonLayer({
    id: `${id}-inner`,
    data: glowData,
    pickable: false,
    stroked: true,
    filled: true,
    extruded: false,
    lineWidthScale: 1,
    lineWidthMinPixels: 3,
    lineJointRounded: true,
    lineCapRounded: true,

    // V2.1: softer fill — atmospheric presence, not bright wash
    getFillColor: (f: unknown) => {
      const feat = f as DeckZoneFeature;
      const { zoneType, zoneFamily, isSelected } = feat.properties;
      const rgb = getHaloColor(zoneType, zoneFamily);
      const confMod = feat.properties.confidence < 0.5 ? 0.40 : 1.0;
      const alpha = Math.round((isSelected ? 25 : 8) * confMod);
      return [...rgb, alpha] as [number, number, number, number];
    },

    // V2.1: softer feathered edge
    getLineColor: (f: unknown) => {
      const feat = f as DeckZoneFeature;
      const { zoneType, zoneFamily, isSelected } = feat.properties;
      const rgb = getHaloColor(zoneType, zoneFamily);
      const alpha = isSelected ? 48 : 20;
      return [...rgb, alpha] as [number, number, number, number];
    },

    getLineWidth: (f: unknown) => {
      const feat = f as DeckZoneFeature;
      return feat.properties.isSelected ? 5 : 3;
    },

    transitions: {
      getFillColor: { duration: 280, easing: (t: number) => 1 - Math.pow(1 - t, 2) },
      getLineColor: { duration: 260, easing: (t: number) => 1 - Math.pow(1 - t, 2) },
    },
  });

  // ── Outer halo: wide atmospheric presence ────────────────────────────────
  const outerHalo = new GeoJsonLayer({
    id: `${id}-outer`,
    data: glowData,
    pickable: false,
    stroked: true,
    filled: false,
    extruded: false,
    lineWidthScale: 1,
    lineWidthMinPixels: 8,
    lineJointRounded: true,
    lineCapRounded: true,

    // V2.1: wider but much fainter — true atmospheric halo
    getLineColor: (f: unknown) => {
      const feat = f as DeckZoneFeature;
      const { zoneType, zoneFamily, isSelected } = feat.properties;
      const rgb = getHaloColor(zoneType, zoneFamily);
      const confMod = feat.properties.confidence < 0.5 ? 0.40 : 1.0;
      const alpha = Math.round((isSelected ? 28 : 10) * confMod);
      return [...rgb, alpha] as [number, number, number, number];
    },

    getLineWidth: (f: unknown) => {
      const feat = f as DeckZoneFeature;
      return feat.properties.isSelected ? 12 : 6;
    },

    transitions: {
      getLineColor: { duration: 300, easing: (t: number) => 1 - Math.pow(1 - t, 2) },
      getLineWidth: { duration: 300, easing: (t: number) => 1 - Math.pow(1 - t, 2) },
    },
  });

  return [outerHalo, innerGlow];
}
