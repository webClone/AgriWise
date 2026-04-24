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
      fill: [130, 125, 155],   // slate-lavender
      edge: [145, 135, 175],   // muted violet
      halo: [115, 110, 148],   // deep cool gray
      fillMul: 0.50, edgeMul: 0.55, haloMul: 0.40,
    };
  }

  // Disease / Pathogen — muted rust/ochre, NOT magenta/purple
  if (t.includes("disease") || t.includes("pest") || t.includes("pathogen")) {
    return {
      fill: [195, 105, 80],    // muted rust
      edge: [205, 115, 90],    // warm terracotta
      halo: [175, 95, 70],     // deep rust
      fillMul: 0.80, edgeMul: 0.85, haloMul: 0.70,
    };
  }

  // Nutrient — warm ochre/sandstone, not bright yellow
  if (t.includes("nutrient") || t.includes("nitrogen") || t.includes("fertiliz")) {
    return {
      fill: [185, 150, 75],    // warm ochre
      edge: [195, 165, 90],    // sandstone
      halo: [165, 135, 70],    // muted clay
      fillMul: 0.70, edgeMul: 0.85, haloMul: 0.70,
    };
  }

  // Water stress — slate-blue teal, not bright cyan
  if (t.includes("water") || t.includes("dry") || t.includes("moisture") || t.includes("irrigat")) {
    return {
      fill: [70, 130, 155],    // slate teal
      edge: [85, 148, 170],    // muted steel-blue
      halo: [60, 115, 140],    // deep slate
      fillMul: 0.75, edgeMul: 0.85, haloMul: 0.75,
    };
  }

  // Composite risk — warm terracotta, not bright amber
  if (t.includes("composite") || t.includes("risk") || t.includes("alert")) {
    return {
      fill: [185, 115, 65],    // terracotta
      edge: [195, 130, 75],    // warm clay
      halo: [165, 100, 55],    // deep rust
      fillMul: 0.80, edgeMul: 0.90, haloMul: 0.80,
    };
  }

  // Action zones — sage/muted green, not neon emerald
  if (zoneFamily === "action") {
    return {
      fill: [85, 145, 100],    // sage
      edge: [100, 160, 115],   // muted green
      halo: [75, 130, 90],     // forest
      fillMul: 0.70, edgeMul: 0.80, haloMul: 0.70,
    };
  }

  // Default diagnostic — warm clay-red, not bright red
  return {
    fill: [175, 95, 80],     // warm clay
    edge: [190, 110, 95],    // terracotta-rose
    halo: [155, 85, 70],     // deep clay
    fillMul: 0.80, edgeMul: 0.90, haloMul: 0.75,
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

      // V2.3: zones must be visible in observe mode — "are there zones here or not?"
      let baseAlpha: number;
      if (isSelected) {
        baseAlpha = 70;   // ~0.27 — present and clear
      } else if (isHovered) {
        baseAlpha = 55;   // ~0.22 — confirmation lift
      } else {
        baseAlpha = 38;   // ~0.15 — visible tint, readable at a glance
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
        baseAlpha = 155;   // ~0.60 — firm and clear
      } else if (isHovered) {
        baseAlpha = 100;   // ~0.39 — soft confirmation
      } else {
        baseAlpha = 55;    // ~0.22 — readable contour even in observe mode
      }

      const alpha = Math.round(baseAlpha * mat.edgeMul * conf.edgeScale);
      return [...edgeRgb, alpha] as [number, number, number, number];
    },

    // ── Line width — V2.1: thinner, more like terrain boundaries ──────────────
    getLineWidth: (f: unknown) => {
      const feat = f as DeckZoneFeature;
      const { isSelected, isHovered, confidence } = feat.properties;
      const conf = confidenceScale(confidence);

      if (isSelected) return 2.5 * conf.widthScale;
      if (isHovered) return 2.0 * conf.widthScale;
      return 1.0 * conf.widthScale;
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
