import type { ChapterKeyframe } from "../SpatialStage/SpatialKeyframes";
import { CAMERAS } from "../SpatialStage/SpatialKeyframes";

/* ═══ AgriWise R2 Pass 3 — Home Timeline ═══════════════════════
   Static keyframe timeline configuration for the homepage.
   
   Each chapter ID corresponds to a DOM element with:
     data-r2-chapter="hero"
     data-r2-chapter="scale"
     etc.
   
   The SpatialEngine discovers these elements, measures their
   scroll bounds, and applies the matching keyframe timeline.
   
   No React context needed. Pure static data.
   ═══════════════════════════════════════════════════════════════ */

export const HOME_TIMELINE: Record<string, ChapterKeyframe[]> = {
  hero: [
    {
      at: 0.0,
      camera: CAMERAS.field,
      layerOpacities: {
        "demo-optical": 0.85,
        "field-polygon": 0.9,
      },
      hud: {
        scaleLabel: "FIELD SCALE",
        contextLabel: "Direct + derived evidence",
        authorityLabel: "Illustrative demonstration",
      },
    },
    {
      at: 1.0,
      camera: CAMERAS.field,
      layerOpacities: {
        "demo-optical": 0.85,
        "field-polygon": 0.9,
        "sentinel-derived": 0.3,
      },
      hud: {
        scaleLabel: "FIELD SCALE",
        contextLabel: "Direct + derived evidence",
        authorityLabel: "Illustrative demonstration",
      },
    },
  ],

  scale: [
    {
      at: 0.0,
      camera: CAMERAS.field,
      layerOpacities: {
        "demo-optical": 0.85,
        "field-polygon": 0.9,
        "sentinel-derived": 0.6,
        "sar-geometry": 0.7,
        "iot-sensor": 0.9,
        "field-annotations": 1.0,
      },
      hud: {
        scaleLabel: "FIELD SCALE",
        contextLabel: "Multimodal evidence convergence",
        authorityLabel: "Illustrative demonstration",
      },
    },
    {
      at: 0.25,
      camera: CAMERAS.evidence,
      layerOpacities: {
        "demo-optical": 0.7,
        "field-polygon": 0.8,
        "sentinel-derived": 0.8,
        "sar-geometry": 0.9,
        "iot-sensor": 1.0,
        "field-annotations": 1.0,
      },
      hud: {
        scaleLabel: "EVIDENCE SCALE",
        contextLabel: "Heterogeneous source fusion",
        authorityLabel: "Illustrative demonstration",
      },
    },
    {
      at: 0.50,
      camera: CAMERAS.farm,
      layerOpacities: {
        "demo-optical": 0.3,
        "field-polygon": 0.4,
        "farm-boundaries": 0.9,
        "iot-sensor": 0.4,
        "farm-annotations": 1.0,
      },
      hud: {
        scaleLabel: "FARM SCALE",
        contextLabel: "Multi-parcel operational context",
        authorityLabel: "Illustrative product view",
      },
    },
    {
      at: 0.72,
      camera: CAMERAS.portfolio,
      layerOpacities: {
        "farm-boundaries": 0.5,
        "portfolio-centroids": 1.0,
      },
      hud: {
        scaleLabel: "PORTFOLIO SCALE",
        contextLabel: "Aggregated agricultural risk context",
        authorityLabel: "Illustrative product view",
      },
    },
    {
      at: 0.88,
      camera: CAMERAS.agriculturalRegions,
      layerOpacities: {
        "agricultural-regions": 0.8,
        "national-boundary": 0.3,
        "national-annotations": 0.8,
      },
      hud: {
        scaleLabel: "REGIONAL SCALE",
        contextLabel: "Agricultural production regions",
        authorityLabel: "Illustrative national scenario",
      },
    },
    {
      at: 1.0,
      camera: CAMERAS.nationalAlgeria,
      layerOpacities: {
        "agricultural-regions": 0.6,
        "national-boundary": 0.85,
        "national-annotations": 1.0,
      },
      hud: {
        scaleLabel: "NATIONAL SCALE",
        contextLabel: "Illustrative sovereign intelligence",
        authorityLabel: "Illustrative national scenario",
      },
    },
  ],

  // Remaining chapters use single-keyframe static scenes for now.
  // They will be expanded in Pass 4.
  evidence: [
    {
      at: 0.0,
      camera: CAMERAS.evidence,
      layerOpacities: {
        "demo-optical": 0.7,
        "field-polygon": 0.8,
        "sentinel-derived": 0.7,
        "sar-geometry": 0.8,
        "iot-sensor": 1.0,
        "field-annotations": 1.0,
      },
      hud: {
        scaleLabel: "EVIDENCE SCALE",
        contextLabel: "Heterogeneous source fusion",
        authorityLabel: "Illustrative demonstration",
      },
    },
  ],

  "agribrain-organism": [
    {
      at: 0.0,
      camera: CAMERAS.evidence,
      layerOpacities: {
        "demo-optical": 0.5,
        "field-polygon": 0.8,
        "sentinel-derived": 0.5,
      },
      hud: {
        scaleLabel: "FIELD SCALE",
        contextLabel: "AgriBrain canonical concepts",
        authorityLabel: "Illustrative demonstration",
      },
    },
  ],

  "asmae-microscope": [
    {
      at: 0.0,
      camera: CAMERAS.field,
      layerOpacities: {
        "demo-optical": 0.6,
        "field-polygon": 0.9,
        "sentinel-derived": 0.8,
      },
      hud: {
        scaleLabel: "FIELD SCALE",
        contextLabel: "ASMAE sub-grid reconstruction",
        authorityLabel: "Illustrative scientific run",
      },
    },
  ],

  worldline: [
    {
      at: 0.0,
      camera: CAMERAS.field,
      layerOpacities: {
        "demo-optical": 0.7,
        "field-polygon": 0.9,
      },
      hud: {
        scaleLabel: "FIELD SCALE",
        contextLabel: "Temporal parcel memory",
        authorityLabel: "Illustrative demonstration",
      },
    },
  ],

  "command-center": [
    {
      at: 0.0,
      camera: CAMERAS.farm,
      layerOpacities: {
        "field-polygon": 0.5,
        "farm-boundaries": 0.8,
      },
      hud: {
        scaleLabel: "MULTI-SCALE",
        contextLabel: "Stakeholder operational projection",
        authorityLabel: "Illustrative product view",
      },
    },
  ],

  institutional: [
    {
      at: 0.0,
      camera: CAMERAS.portfolio,
      layerOpacities: {
        "farm-boundaries": 0.5,
        "portfolio-centroids": 1.0,
      },
      hud: {
        scaleLabel: "PORTFOLIO SCALE",
        contextLabel: "Credit and insurance risk context",
        authorityLabel: "Illustrative product view",
      },
    },
  ],

  sovereign: [
    {
      at: 0.0,
      camera: CAMERAS.nationalAlgeria,
      layerOpacities: {
        "agricultural-regions": 0.7,
        "national-boundary": 0.8,
        "national-annotations": 1.0,
      },
      hud: {
        scaleLabel: "NATIONAL SCALE",
        contextLabel: "Illustrative sovereign intelligence",
        authorityLabel: "Illustrative national scenario",
      },
    },
  ],

  infrastructure: [
    {
      at: 0.0,
      camera: CAMERAS.farm,
      layerOpacities: {
        "field-polygon": 0.4,
        "farm-boundaries": 0.6,
      },
      hud: {
        scaleLabel: "SYSTEMS SCALE",
        contextLabel: "Interoperable data infrastructure",
        authorityLabel: "Illustrative product view",
      },
    },
  ],
};
