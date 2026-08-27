import { WebMercatorViewport } from "@deck.gl/core";
import type {
  CameraIntent,
  CameraViewState,
  ChapterKeyframe,
  HudState,
  LayerId,
  ResolvedRenderState,
} from "./SpatialKeyframes";

/* ═══ AgriWise R2 Pass 3 — RenderStateSolver ═══════════════════
   Pure function: given chapter + progress + keyframes, outputs
   a fully resolved render state with interpolated camera,
   layer opacities, HUD, and active layer set.
   
   Called inside requestAnimationFrame. Never inside React render.
   ═══════════════════════════════════════════════════════════════ */

const ALL_LAYER_IDS: LayerId[] = [
  "demo-optical",
  "field-polygon",
  "sentinel-derived",
  "sar-geometry",
  "iot-sensor",
  "farm-boundaries",
  "portfolio-centroids",
  "agricultural-regions",
  "national-boundary",
  "field-annotations",
  "farm-annotations",
  "national-annotations",
];

/* ── Camera Intent Resolution ──────────────────────────────── */

function resolveCameraIntent(
  intent: CameraIntent,
  viewportWidth: number,
  viewportHeight: number,
): CameraViewState {
  if (intent.type === "fixed") {
    return intent.view;
  }

  // Geometry-driven camera via fitBounds
  const [[west, south], [east, north]] = intent.bounds;
  try {
    const vp = new WebMercatorViewport({
      width: Math.max(viewportWidth, 100),
      height: Math.max(viewportHeight, 100),
    }).fitBounds(
      [
        [west, south],
        [east, north],
      ],
      {
        padding: intent.padding,
      },
    );
    return {
      longitude: vp.longitude,
      latitude: vp.latitude,
      zoom: vp.zoom,
      pitch: intent.pitch ?? 0,
      bearing: intent.bearing ?? 0,
    };
  } catch {
    // Fallback if fitBounds fails
    return {
      longitude: (west + east) / 2,
      latitude: (south + north) / 2,
      zoom: 5,
      pitch: intent.pitch ?? 0,
      bearing: intent.bearing ?? 0,
    };
  }
}

/* ── Numeric lerp ──────────────────────────────────────────── */

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function lerpCamera(a: CameraViewState, b: CameraViewState, t: number): CameraViewState {
  return {
    longitude: lerp(a.longitude, b.longitude, t),
    latitude: lerp(a.latitude, b.latitude, t),
    zoom: lerp(a.zoom, b.zoom, t),
    pitch: lerp(a.pitch, b.pitch, t),
    bearing: lerp(a.bearing, b.bearing, t),
  };
}

/* ── Main Solver ───────────────────────────────────────────── */

export function solveRenderState(
  chapterId: string,
  chapterProgress: number,
  keyframes: ChapterKeyframe[],
  viewportWidth: number,
  viewportHeight: number,
): ResolvedRenderState {
  // Clamp
  const progress = Math.max(0, Math.min(1, chapterProgress));

  // Single-keyframe chapter
  if (keyframes.length === 1) {
    const kf = keyframes[0];
    const camera = resolveCameraIntent(kf.camera, viewportWidth, viewportHeight);
    const opacities: Record<LayerId, number> = {} as Record<LayerId, number>;
    const activeLayers = new Set<LayerId>();

    for (const id of ALL_LAYER_IDS) {
      const val = kf.layerOpacities[id] ?? 0;
      opacities[id] = val;
      if (val > 0) activeLayers.add(id);
    }

    return {
      camera,
      layerOpacities: opacities,
      activeLayers,
      hud: kf.hud,
      chapterId,
      chapterProgress: progress,
      bracketLabel: kf.hud.scaleLabel,
      blendT: 0,
    };
  }

  // Find bracketing keyframes
  let kfA = keyframes[0];
  let kfB = keyframes[keyframes.length - 1];
  let localT = 0;

  for (let i = 0; i < keyframes.length - 1; i++) {
    if (progress >= keyframes[i].at && progress <= keyframes[i + 1].at) {
      kfA = keyframes[i];
      kfB = keyframes[i + 1];
      const range = kfB.at - kfA.at;
      localT = range > 0 ? (progress - kfA.at) / range : 0;
      break;
    }
  }

  // Handle progress beyond last keyframe
  if (progress >= keyframes[keyframes.length - 1].at) {
    kfA = keyframes[keyframes.length - 1];
    kfB = kfA;
    localT = 0;
  }

  // Resolve camera intents to concrete CameraViewState, then lerp
  const camA = resolveCameraIntent(kfA.camera, viewportWidth, viewportHeight);
  const camB = resolveCameraIntent(kfB.camera, viewportWidth, viewportHeight);
  const camera = lerpCamera(camA, camB, localT);

  // Lerp layer opacities — compute union of both keyframes' layers
  const opacities: Record<LayerId, number> = {} as Record<LayerId, number>;
  const activeLayers = new Set<LayerId>();

  for (const id of ALL_LAYER_IDS) {
    const aVal = kfA.layerOpacities[id] ?? 0;
    const bVal = kfB.layerOpacities[id] ?? 0;

    // Only include in active set if either keyframe uses this layer
    if (aVal > 0 || bVal > 0) {
      activeLayers.add(id);
      opacities[id] = lerp(aVal, bVal, localT);
    } else {
      opacities[id] = 0;
    }
  }

  // HUD: snap at midpoint (not lerp text)
  const hud: HudState = localT < 0.5 ? kfA.hud : kfB.hud;

  return {
    camera,
    layerOpacities: opacities,
    activeLayers,
    hud,
    chapterId,
    chapterProgress: progress,
    bracketLabel: `${kfA.hud.scaleLabel} → ${kfB.hud.scaleLabel}`,
    blendT: localT,
  };
}
