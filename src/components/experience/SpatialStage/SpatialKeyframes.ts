/* ═══ AgriWise R2 Pass 3 — Spatial Keyframes & Camera Intent ════
   Type system for the continuous interpolation engine.
   
   CameraIntent replaces fixed CameraViewState for keyframes:
   - "fixed": hard-coded camera coordinates
   - "bounds": geometry-driven camera via fitBounds

   LayerId identifies Deck.gl layers.
   HudState drives the scene-controlled bottom HUD.
   ═══════════════════════════════════════════════════════════════ */

/* ── Camera ────────────────────────────────────────────────── */

export interface CameraViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

export interface ResponsivePadding {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

export type CameraIntent =
  | {
      type: "fixed";
      view: CameraViewState;
    }
  | {
      type: "bounds";
      bounds: [[number, number], [number, number]]; // [[west, south], [east, north]]
      padding: ResponsivePadding;
      pitch?: number;
      bearing?: number;
    };

/* ── Layers ────────────────────────────────────────────────── */

export type LayerId =
  | "stage-raster"
  | "demo-optical"
  | "field-polygon"
  | "sentinel-derived"
  | "sar-geometry"
  | "iot-sensor"
  | "farm-boundaries"
  | "portfolio-centroids"
  | "agricultural-regions"
  | "national-boundary"
  | "active-lineage"
  | "field-annotations"
  | "farm-annotations"
  | "national-annotations";

/* ── HUD ───────────────────────────────────────────────────── */

export interface HudState {
  scaleLabel: string;
  contextLabel: string;
  authorityLabel: string;
}

/* ── Keyframe ──────────────────────────────────────────────── */

export interface ChapterKeyframe {
  at: number; // 0.0 → 1.0 within chapter
  camera: CameraIntent;
  layerOpacities: Partial<Record<LayerId, number>>;
  hud: HudState;
}

/* ── Resolved Render State ─────────────────────────────────── */

export interface ResolvedRenderState {
  camera: CameraViewState;
  layerOpacities: Record<LayerId, number>;
  /** Which layers are needed (union of bracketing keyframes) */
  activeLayers: Set<LayerId>;
  hud: HudState;
  chapterId: string;
  chapterProgress: number;
  bracketLabel: string; // e.g. "field → farm" for debug
  blendT: number; // 0.0 → 1.0 within bracket
}

/* ── Canonical Camera Presets ──────────────────────────────── */

export const CAMERAS = {
  field: {
    type: "fixed" as const,
    view: { longitude: 3.015, latitude: 36.502, zoom: 15.5, pitch: 45, bearing: -15 },
  },
  evidence: {
    type: "fixed" as const,
    view: { longitude: 3.015, latitude: 36.502, zoom: 15.2, pitch: 30, bearing: 15 },
  },
  farm: {
    type: "fixed" as const,
    view: { longitude: 3.025, latitude: 36.510, zoom: 13.2, pitch: 25, bearing: 0 },
  },
  portfolio: {
    type: "fixed" as const,
    view: { longitude: 3.05, latitude: 36.52, zoom: 10.8, pitch: 12, bearing: 0 },
  },
  agriculturalRegions: {
    type: "bounds" as const,
    bounds: [[0.0, 34.0], [8.5, 37.5]] as [[number, number], [number, number]],
    padding: { top: 60, bottom: 80, left: 60, right: 60 },
    pitch: 0,
    bearing: 0,
  },
  nationalAlgeria: {
    type: "bounds" as const,
    bounds: [[-2.0, 19.0], [12.0, 37.5]] as [[number, number], [number, number]],
    padding: { top: 40, bottom: 80, left: 40, right: 40 },
    pitch: 0,
    bearing: 0,
  },
} satisfies Record<string, CameraIntent>;
