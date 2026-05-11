/**
 * UnifiedZoneLayer — Bold, readable agronomic region rendering
 *
 * Visual language: Clear analytical zones over dimmed basemap.
 *   - Colors are earth tones with sufficient contrast
 *   - Default edges are crisp white-neutral for readability
 *   - Trust zones remain visually distinct (cool gray, dashed)
 *   - Confidence scales opacity, not visibility
 *   - Selection isolation: chosen zone prominent, rest recedes
 *   - Motion is weighted and deliberate
 *
 * Opacity model:
 *   Default:  fill ~0.14, edge ~0.31, width 1.5px
 *   Hover:    fill ~0.25, edge ~0.71, width 2.5px
 *   Selected: fill ~0.35, edge ~0.90, width 3.5px
 *   Non-selected during inspection: fill ~0.05, edge ~0.08
 */

import { GeoJsonLayer } from "@deck.gl/layers";
import { PathStyleExtension } from "@deck.gl/extensions";
import { DeckZoneFeature } from "./zoneUtils";

// ── Zone family material system ──────────────────────────────────────────────
// Colors are deliberately muted — earth tones, not screen colors.
// Inspired by topographic map washes and satellite false-color conventions.

type ZoneMaterial = {
  fill: [number, number, number];
  edge: [number, number, number];
  halo: [number, number, number];
  fillMul: number;
  edgeMul: number;
  haloMul: number;
};

function getZoneMaterial(zoneType: string, zoneFamily: string): ZoneMaterial {
  const t = zoneType.toLowerCase();

  // Trust/uncertainty — cool gray-lavender, sparse and quiet
  if (zoneFamily === "trust") {
    return {
      fill: [160, 155, 195],   // brighter slate-lavender
      edge: [200, 190, 230],   // bright violet
      halo: [140, 135, 180],   // cool gray
      fillMul: 0.60, edgeMul: 0.70, haloMul: 0.50,
    };
  }

  // Disease / Pathogen — bright rust for visibility
  if (t.includes("disease") || t.includes("pest") || t.includes("pathogen")) {
    return {
      fill: [255, 140, 100],   // bright rust-orange
      edge: [255, 160, 120],   // warm orange
      halo: [220, 120, 80],    // rust
      fillMul: 0.90, edgeMul: 1.0, haloMul: 0.80,
    };
  }

  // Nutrient — bright ochre/gold
  if (t.includes("nutrient") || t.includes("nitrogen") || t.includes("fertiliz")) {
    return {
      fill: [230, 190, 90],    // bright gold
      edge: [245, 210, 110],   // warm gold
      halo: [200, 170, 80],    // ochre
      fillMul: 0.85, edgeMul: 1.0, haloMul: 0.80,
    };
  }

  // Water stress — bright cyan-teal for visibility through multiply blend
  if (t.includes("water") || t.includes("dry") || t.includes("moisture") || t.includes("irrigat")) {
    return {
      fill: [100, 200, 240],   // bright cyan
      edge: [140, 220, 255],   // vivid sky blue
      halo: [80, 180, 220],    // teal
      fillMul: 0.85, edgeMul: 1.0, haloMul: 0.85,
    };
  }

  // Composite risk — bright amber
  if (t.includes("composite") || t.includes("risk") || t.includes("alert")) {
    return {
      fill: [240, 160, 80],    // bright amber
      edge: [255, 180, 100],   // warm amber
      halo: [210, 140, 60],    // deep amber
      fillMul: 0.90, edgeMul: 1.0, haloMul: 0.85,
    };
  }

  // Action zones — bright emerald
  if (zoneFamily === "action") {
    return {
      fill: [100, 200, 130],   // bright emerald
      edge: [130, 230, 160],   // vivid green
      halo: [80, 180, 110],    // green
      fillMul: 0.80, edgeMul: 0.90, haloMul: 0.80,
    };
  }

  // Default diagnostic — bright warm clay
  return {
    fill: [240, 140, 110],   // bright coral
    edge: [255, 165, 130],   // warm coral
    halo: [210, 120, 90],    // deep coral
    fillMul: 0.90, edgeMul: 1.0, haloMul: 0.85,
  };
}

// ── Confidence multiplier ────────────────────────────────────────────────────
// V2.1: tighter scaling — low-confidence zones should almost vanish
function confidenceScale(confidence: number): { fillScale: number; edgeScale: number; widthScale: number } {
  if (confidence >= 0.7) return { fillScale: 1.0, edgeScale: 1.0, widthScale: 1.0 };
  if (confidence >= 0.5) return { fillScale: 0.72, edgeScale: 0.75, widthScale: 0.85 };
  if (confidence >= 0.3) return { fillScale: 0.42, edgeScale: 0.48, widthScale: 0.65 };
  return { fillScale: 0.25, edgeScale: 0.30, widthScale: 0.50 };
}

// ── Layer factory ────────────────────────────────────────────────────────────

export function getUnifiedZoneLayer({
  id = "unified-zones",
  featureCollection,
  visible = true,
  detailMode = "farmer",
  isInspecting = false,
  onHover,
  onClick,
}: {
  id?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  featureCollection: any;
  visible?: boolean;
  detailMode?: "farmer" | "expert";
  isInspecting?: boolean;
  onHover?: (info: { object?: DeckZoneFeature }) => void;
  onClick?: (info: { object?: DeckZoneFeature }) => void;
}) {
  if (!visible || !featureCollection) return null;
  if (featureCollection.features.length === 0) return null;

  const hasTrustZones = featureCollection.features.some(
    (f: DeckZoneFeature) => f.properties.zoneFamily === "trust"
  );

  return new GeoJsonLayer({
    id,
    data: featureCollection,
    pickable: true,
    stroked: true,
    filled: true,
    extruded: false,
    lineWidthScale: 1,
    lineWidthMinPixels: 0.5,
    lineJointRounded: true,
    lineCapRounded: true,

    // Dashed outlines for trust/uncertainty zones
    ...(hasTrustZones ? {
      extensions: [new PathStyleExtension({ dash: true })],
      getDashArray: (f: unknown) => {
        const feat = f as DeckZoneFeature;
        return feat.properties.zoneFamily === "trust" ? [6, 5] : [0, 0];
      },
      dashJustified: true,
    } : {}),

    // ── Fill — readable analytical wash ─────────────────────────────────────
    getFillColor: (f: unknown) => {
      const feat = f as DeckZoneFeature;
      const { zoneType, zoneFamily, isSelected, isHovered, confidence } = feat.properties;
      const mat = getZoneMaterial(zoneType, zoneFamily);
      const conf = confidenceScale(confidence);

      // During inspection: non-selected zones vanish completely to spotlight the selection
      if (isInspecting && !isSelected && !isHovered) {
        return [...mat.fill, 0] as [number, number, number, number];
      }

      // V3: zones render in their own normal-blend canvas — moderate opacity
      let baseAlpha: number;
      if (isSelected) {
        baseAlpha = 90;   // ~0.35 — bold and clear
      } else if (isHovered) {
        baseAlpha = 70;   // ~0.27 — confirmation lift
      } else {
        baseAlpha = 45;   // ~0.18 — visible tint, non-obtrusive
      }

      const alpha = Math.round(baseAlpha * mat.fillMul * conf.fillScale);
      return [...mat.fill, alpha] as [number, number, number, number];
    },

    // ── Edge — V2.1: zone-colored edges (not white) feel like condition boundaries ──
    getLineColor: (f: unknown) => {
      const feat = f as DeckZoneFeature;
      const { zoneType, zoneFamily, isSelected, isHovered, confidence } = feat.properties;
      const mat = getZoneMaterial(zoneType, zoneFamily);
      const conf = confidenceScale(confidence);

      // During inspection: non-selected zone edges vanish completely
      if (isInspecting && !isSelected && !isHovered) {
        return [...mat.edge, 0] as [number, number, number, number];
      }

      // V2.1: ALL zones use their material edge color — no more white outlines.
      // White edges scream "software selection tool". Colored edges feel like
      // natural condition boundaries inferred from the land.
      const edgeRgb = mat.edge;

      let baseAlpha: number;
      if (isSelected) {
        baseAlpha = 200;   // ~0.78 — crisp and bold
      } else if (isHovered) {
        baseAlpha = 160;   // ~0.63 — strong confirmation
      } else {
        baseAlpha = 120;   // ~0.47 — clearly visible edge
      }

      const alpha = Math.round(baseAlpha * mat.edgeMul * conf.edgeScale);
      return [...edgeRgb, alpha] as [number, number, number, number];
    },

    // ── Line width — V2.1: thinner, more like terrain boundaries ──────────────
    getLineWidth: (f: unknown) => {
      const feat = f as DeckZoneFeature;
      const { isSelected, isHovered, confidence } = feat.properties;
      const conf = confidenceScale(confidence);

      if (isSelected) return 3.5 * conf.widthScale;
      if (isHovered) return 3.0 * conf.widthScale;
      return 2.0 * conf.widthScale;
    },

    onHover,
    onClick,

    // Weighted, deliberate motion — ease-out with longer settle
    transitions: {
      getLineColor: { duration: 220, easing: (t: number) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2 },  // ease-in-out quad
      getLineWidth: { duration: 220, easing: (t: number) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2 },
      getFillColor: { duration: 320, easing: (t: number) => 1 - Math.pow(1 - t, 3) },   // fill blooms slowly after edge
    },

    opacity: 1.0,

    updateTriggers: {
      getFillColor: [detailMode, isInspecting],
      getLineColor: [detailMode, isInspecting],
      getLineWidth: [detailMode],
    },
  });
}
