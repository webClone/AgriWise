import { WebMercatorViewport } from "@deck.gl/core";
import type { CameraViewState, HudState, LayerId } from "./SpatialKeyframes";
import {
  PREPARED_WORLD,
  selectPlotLineage,
  selectPreparedEntity,
  ILLUSTRATIVE_WORLD,
} from "../world/selectors";

/* ═══ AgriWise Cinematic ShotDirector — Multi-Stage Asset System ═
   Visual Scene Production & Micro-Interaction Choreography Director.
   
   Architecture:
   1. Stage Asset System (hero-field-master, farm-wide, organization-atmosphere,
      region-atmosphere, nation-atmosphere).
   2. Perspective-safe geometry camera resolver.
   3. Independent parcel perimeter progress with 60-110ms staggered graph reveal.
   4. One-shot micro-motion cues (ticks, acquisition flash, contour expansion).
   5. Deterministic illustrative density contours & administrative geography.
   ═══════════════════════════════════════════════════════════════ */

export type SpatialStage = "field" | "farm" | "organization" | "region" | "nation";

export type TimelinePosition =
  | { type: "hold"; stage: SpatialStage }
  | { type: "transition"; from: SpatialStage; to: SpatialStage; t: number }
  | { type: "evidence_dive"; t: number }
  | { type: "deferred_hold" };

export interface CornerTickState {
  vertexIndex: number;
  progress: number; // 0..1 scale-in
  opacity: number;  // 0..1 alpha
}

export interface ParcelAcquisitionState {
  id: string;
  outlineProgress: number; // 0..1 boundary stroke draw
  membershipMix: number;   // 0..1 green fill acquisition (3-5%)
  acquisitionFlash: number; // 0..1 momentary brightness pulse
  emphasis: number;        // 0..1 visual weight
}

export interface MicroMotionState {
  selectedPlotAcquisition: number; // 0..1 hero intro progress
  cornerTicks: CornerTickState[];
  parcelAcquisition: Record<string, ParcelAcquisitionState>;
  farmEnvelope: {
    drawProgress: number;  // 0..1 perimeter draw
    opacity: number;       // 0..1 subtle outer envelope (max 0.30)
    flash: number;         // 0..1 completion pulse
  };
  organizationLinks: Record<string, number>;
  organizationNodes: Record<string, number>;
  regionContours: number[];
  coastline: number;
  administrativeContext: number;
  countryBoundary: number;
}

export interface VisualChannelProfile {
  // Multi-Stage Raster Assets
  opticalField: number;
  opticalFarm: number;
  opticalOrg: number;
  opticalRegion: number;
  opticalNation: number;

  // MicroMotion Contract
  microMotion: MicroMotionState;

  // Organization Scene (Distributed Topology)
  sisterFarms: number;
  organizationLinks: number;
  organizationTopologyNodes: number;

  // Region Scene (Deterministic Density Contours)
  regionalAggregationField: number;
  contourRevealProgress: number;
  selectedRegion: number;
  peerRegions: number;

  // Nation Scene (Sovereign Reference Geography)
  countryBoundary: number;
  coastlineRevealProgress: number;
  administrativeContext: number;
}

export interface ResolvedShotState {
  camera: CameraViewState;
  channels: VisualChannelProfile;
  activeLayers: Set<LayerId>;
  layerOpacities: Record<LayerId, number>;
  
  stage: SpatialStage;
  settledStage: SpatialStage | null;
  fromStage: SpatialStage;
  toStage: SpatialStage;
  transitionT: number;

  hud: HudState;
  selectedPlotId: string;
}

/* ── Easing Utilities ──────────────────────────────────────── */

export function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export function easeInCubic(t: number): number {
  return t * t * t;
}

export function easeInOutQuad(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function lerpAngle(a: number, b: number, t: number): number {
  let diff = (b - a) % 360;
  if (diff > 180) diff -= 360;
  if (diff < -180) diff += 360;
  return a + diff * t;
}

export function phaseProgress(t: number, start: number, end: number): number {
  if (t <= start) return 0;
  if (t >= end) return 1;
  return (t - start) / (end - start);
}

/* ── Perspective-Safe Camera Resolver ──────────────────────── */

export interface ShotCameraOptions {
  bounds: [[number, number], [number, number]]; // [[west, south], [east, north]]
  viewportWidth: number;
  viewportHeight: number;
  copySide: "left" | "right" | "center";
  targetPitch: number;
  targetBearing: number;
  safetyScale?: number;
}

export function resolveShotCamera(opts: ShotCameraOptions): CameraViewState {
  const {
    bounds,
    viewportWidth,
    viewportHeight,
    copySide,
    targetPitch,
    targetBearing,
    safetyScale = 0.92,
  } = opts;

  const isMobile = viewportWidth < 768;
  const vw = Math.max(320, viewportWidth);
  const vh = Math.max(480, viewportHeight);

  let padding = { top: vh * 0.12, bottom: vh * 0.14, left: vw * 0.08, right: vw * 0.08 };
  if (!isMobile) {
    if (copySide === "left") {
      // Copy on left -> Active geometry on right
      padding = { top: vh * 0.14, bottom: vh * 0.14, left: vw * 0.44, right: vw * 0.08 };
    } else if (copySide === "right") {
      // Copy on right -> Active geometry on left
      padding = { top: vh * 0.14, bottom: vh * 0.14, left: vw * 0.08, right: vw * 0.44 };
    } else {
      padding = { top: vh * 0.14, bottom: vh * 0.16, left: vw * 0.12, right: vw * 0.12 };
    }
  }

  // 1. Top-down fitBounds baseline
  const topDown = new WebMercatorViewport({
    width: vw,
    height: vh,
  }).fitBounds(bounds, { padding });

  // 2. Pitch compensation
  const pitchAdjustment = (targetPitch / 60) * 0.38;
  let zoom = (topDown.zoom - pitchAdjustment) * safetyScale + (1 - safetyScale) * topDown.zoom;

  // 3. Construct candidate viewport
  let candidate = new WebMercatorViewport({
    width: vw,
    height: vh,
    longitude: topDown.longitude,
    latitude: topDown.latitude,
    zoom,
    pitch: targetPitch,
    bearing: targetBearing,
  });

  // 4. Containment safety test
  const corners: [number, number][] = [
    [bounds[0][0], bounds[0][1]],
    [bounds[1][0], bounds[0][1]],
    [bounds[1][0], bounds[1][1]],
    [bounds[0][0], bounds[1][1]],
  ];

  for (let i = 0; i < 4; i++) {
    const projected = candidate.project(corners[i]);
    const margin = 20;
    const isOut =
      projected[0] < margin ||
      projected[0] > vw - margin ||
      projected[1] < margin ||
      projected[1] > vh - margin;

    if (isOut) {
      zoom -= 0.15;
      candidate = new WebMercatorViewport({
        width: vw,
        height: vh,
        longitude: topDown.longitude,
        latitude: topDown.latitude,
        zoom,
        pitch: targetPitch,
        bearing: targetBearing,
      });
    }
  }

  return {
    longitude: candidate.longitude,
    latitude: candidate.latitude,
    zoom: candidate.zoom,
    pitch: targetPitch,
    bearing: targetBearing,
  };
}

/* ── Geometry-Derived Stage Cameras ────────────────────────── */

export function getStageCamera(
  stage: SpatialStage,
  viewportWidth: number,
  viewportHeight: number,
  prefersReducedMotion = false
): CameraViewState {
  const [plotId, farmId, portfolioId, regionId, countryId] = selectPlotLineage("PLOT-017");

  const prepPlot = selectPreparedEntity(plotId)!;
  const prepFarm = selectPreparedEntity(farmId)!;
  const prepPortfolio = selectPreparedEntity(portfolioId)!;
  const prepRegion = selectPreparedEntity(regionId)!;
  const prepCountry = selectPreparedEntity(countryId)!;

  switch (stage) {
    case "field":
      return resolveShotCamera({
        bounds: prepPlot.bounds,
        viewportWidth,
        viewportHeight,
        copySide: "left",
        targetPitch: 0,
        targetBearing: 0,
        safetyScale: 0.95,
      });

    case "farm":
      return resolveShotCamera({
        bounds: prepFarm.bounds,
        viewportWidth,
        viewportHeight,
        copySide: "right",
        targetPitch: 0,
        targetBearing: 0,
        safetyScale: 0.93,
      });

    case "organization":
      return resolveShotCamera({
        bounds: prepPortfolio.bounds,
        viewportWidth,
        viewportHeight,
        copySide: "left",
        targetPitch: 0,
        targetBearing: 0,
        safetyScale: 0.90,
      });

    case "region":
      return resolveShotCamera({
        bounds: prepRegion.bounds,
        viewportWidth,
        viewportHeight,
        copySide: "right",
        targetPitch: 0,
        targetBearing: 0,
        safetyScale: 0.88,
      });

    case "nation":
      return resolveShotCamera({
        bounds: prepCountry.bounds,
        viewportWidth,
        viewportHeight,
        copySide: "center",
        targetPitch: 0,
        targetBearing: 0,
        safetyScale: 0.86,
      });
  }
}

/* ── Settled Visual Profiles ───────────────────────────────── */

function createSettledMicroMotion(stage: SpatialStage): MicroMotionState {
  const farm04Plots = ["PLOT-017", "PLOT-018", "PLOT-019", "PLOT-020", "PLOT-021", "PLOT-022"];
  const parcelAcquisition: Record<string, ParcelAcquisitionState> = {};

  for (const id of farm04Plots) {
    if (stage === "field") {
      parcelAcquisition[id] = {
        id,
        outlineProgress: id === "PLOT-017" ? 1.0 : 0.0,
        membershipMix: id === "PLOT-017" ? 1.0 : 0.0,
        acquisitionFlash: 0.0,
        emphasis: id === "PLOT-017" ? 1.0 : 0.0,
      };
    } else {
      parcelAcquisition[id] = {
        id,
        outlineProgress: 1.0,
        membershipMix: 1.0,
        acquisitionFlash: 0.0,
        emphasis: id === "PLOT-017" ? 0.75 : 0.55,
      };
    }
  }

  const cornerTicks: CornerTickState[] = [0, 1, 2, 3].map((i) => ({
    vertexIndex: i,
    progress: 1.0,
    opacity: stage === "field" ? 1.0 : 0.8,
  }));

  return {
    selectedPlotAcquisition: 1.0,
    cornerTicks,
    parcelAcquisition,
    farmEnvelope: {
      drawProgress: stage === "field" ? 0.0 : 1.0,
      opacity: stage === "field" ? 0.0 : 0.30,
      flash: 0.0,
    },
    organizationLinks: {},
    organizationNodes: {},
    regionContours: stage === "region" ? [1, 1, 1, 1, 1] : [],
    coastline: stage === "nation" ? 1.0 : 0.0,
    administrativeContext: stage === "nation" ? 0.5 : 0.0,
    countryBoundary: stage === "nation" ? 1.0 : 0.0,
  };
}

export function getSettledChannels(stage: SpatialStage): VisualChannelProfile {
  return {
    opticalField: stage === "field" ? 1.0 : 0.0,
    opticalFarm: stage === "farm" ? 1.0 : 0.0,
    opticalOrg: stage === "organization" ? 0.85 : 0.0,
    opticalRegion: stage === "region" ? 0.85 : 0.0,
    opticalNation: stage === "nation" ? 0.90 : 0.0,

    microMotion: createSettledMicroMotion(stage),

    sisterFarms: stage === "organization" ? 0.8 : 0.0,
    organizationLinks: stage === "organization" ? 1.0 : 0.0,
    organizationTopologyNodes: stage === "organization" ? 1.0 : 0.0,

    regionalAggregationField: stage === "region" ? 1.0 : 0.0,
    contourRevealProgress: stage === "region" ? 1.0 : 0.0,
    selectedRegion: stage === "region" ? 1.0 : stage === "nation" ? 0.35 : 0.0,
    peerRegions: stage === "nation" ? 0.65 : 0.0,

    countryBoundary: stage === "nation" ? 1.0 : 0.0,
    coastlineRevealProgress: stage === "nation" ? 1.0 : 0.0,
    administrativeContext: stage === "nation" ? 0.5 : 0.0,
  };
}

/* ── Shot Choreography Director ────────────────────────────── */

export function directShot(
  position: TimelinePosition,
  viewportWidth: number,
  viewportHeight: number,
  prefersReducedMotion = false
): ResolvedShotState {
  const stageCameras = {
    field: getStageCamera("field", viewportWidth, viewportHeight, prefersReducedMotion),
    farm: getStageCamera("farm", viewportWidth, viewportHeight, prefersReducedMotion),
    organization: getStageCamera("organization", viewportWidth, viewportHeight, prefersReducedMotion),
    region: getStageCamera("region", viewportWidth, viewportHeight, prefersReducedMotion),
    nation: getStageCamera("nation", viewportWidth, viewportHeight, prefersReducedMotion),
  };

  // ── 1. HOLD STATE ──────────────────────────────────────────
  if (position.type === "hold") {
    const stage = position.stage;
    const channels = getSettledChannels(stage);
    const camera = stageCameras[stage];

    const hudLabels: Record<SpatialStage, { scale: string; context: string }> = {
      field: { scale: "01 · ONE FIELD", context: "One field becomes a living intelligence object." },
      farm: { scale: "02 · ITS FARM", context: "Related parcels become one operational system." },
      organization: { scale: "03 · ORGANIZATION", context: "Farms become one organizational picture." },
      region: { scale: "04 · REGIONAL SYSTEM", context: "Local systems reveal regional patterns." },
      nation: { scale: "05 · NATIONAL INTELLIGENCE", context: "Regional intelligence becomes national visibility." },
    };

    return {
      camera,
      channels,
      activeLayers: new Set(["stage-raster", "active-lineage", "farm-boundaries", "portfolio-centroids", "agricultural-regions", "national-boundary"]),
      layerOpacities: buildLayerOpacities(channels),
      stage,
      settledStage: stage,
      fromStage: stage,
      toStage: stage,
      transitionT: 1.0,
      hud: {
        scaleLabel: hudLabels[stage].scale,
        contextLabel: hudLabels[stage].context,
        authorityLabel: "Illustrative spatial demonstration",
      },
      selectedPlotId: "PLOT-017",
    };
  }

  // ── 2. TRANSITION CHOREOGRAPHY ─────────────────────────────
  if (position.type === "transition") {
    const { from, to, t } = position;

    let camera: CameraViewState = stageCameras[from];
    let channels: VisualChannelProfile = getSettledChannels(from);

    // ── Transition A: Field -> Farm (Staggered Graph-Based Reveal) ──
    if (from === "field" && to === "farm") {
      // Staggered parcel outline progress windows:
      const p18Progress = phaseProgress(t, 0.12, 0.38); // North-West
      const p19Progress = phaseProgress(t, 0.18, 0.44); // North Central
      const p20Progress = phaseProgress(t, 0.28, 0.54); // East beyond canal
      const p21Progress = phaseProgress(t, 0.36, 0.62); // South-West
      const p22Progress = phaseProgress(t, 0.44, 0.70); // South Market Garden
      
      const camProgress = phaseProgress(t, 0.15, 0.75);
      const envelopeDrawProgress = phaseProgress(t, 0.60, 0.85);
      const envelopeOpacity = lerp(0.0, 0.30, phaseProgress(t, 0.65, 0.88));
      const envelopeFlash = phaseProgress(t, 0.85, 0.96) > 0 ? Math.sin(phaseProgress(t, 0.85, 0.96) * Math.PI) * 0.3 : 0;
      const subordinationProgress = phaseProgress(t, 0.60, 1.00);

      // Camera interpolation
      const camFrom = stageCameras.field;
      const camTo = stageCameras.farm;
      const camT = easeInOutCubic(camProgress);

      camera = {
        longitude: lerp(camFrom.longitude, camTo.longitude, camT),
        latitude: lerp(camFrom.latitude, camTo.latitude, camT),
        zoom: lerp(camFrom.zoom, camTo.zoom, camT),
        pitch: lerp(camFrom.pitch, camTo.pitch, easeOutCubic(camProgress)),
        bearing: lerpAngle(camFrom.bearing, camTo.bearing, easeInOutQuad(camProgress)),
      };

      const calcFlash = (p: number) => (p > 0.80 && p < 1.0 ? Math.sin(((p - 0.80) / 0.20) * Math.PI) * 0.45 : 0);

      const parcelAcquisition: Record<string, ParcelAcquisitionState> = {
        "PLOT-017": {
          id: "PLOT-017",
          outlineProgress: 1.0,
          membershipMix: 1.0,
          acquisitionFlash: 0.0,
          emphasis: lerp(1.0, 0.75, subordinationProgress),
        },
        "PLOT-018": {
          id: "PLOT-018",
          outlineProgress: p18Progress,
          membershipMix: easeOutCubic(p18Progress),
          acquisitionFlash: calcFlash(p18Progress),
          emphasis: lerp(0.0, 0.55, p18Progress),
        },
        "PLOT-019": {
          id: "PLOT-019",
          outlineProgress: p19Progress,
          membershipMix: easeOutCubic(p19Progress),
          acquisitionFlash: calcFlash(p19Progress),
          emphasis: lerp(0.0, 0.55, p19Progress),
        },
        "PLOT-020": {
          id: "PLOT-020",
          outlineProgress: p20Progress,
          membershipMix: easeOutCubic(p20Progress),
          acquisitionFlash: calcFlash(p20Progress),
          emphasis: lerp(0.0, 0.55, p20Progress),
        },
        "PLOT-021": {
          id: "PLOT-021",
          outlineProgress: p21Progress,
          membershipMix: easeOutCubic(p21Progress),
          acquisitionFlash: calcFlash(p21Progress),
          emphasis: lerp(0.0, 0.55, p21Progress),
        },
        "PLOT-022": {
          id: "PLOT-022",
          outlineProgress: p22Progress,
          membershipMix: easeOutCubic(p22Progress),
          acquisitionFlash: calcFlash(p22Progress),
          emphasis: lerp(0.0, 0.55, p22Progress),
        },
      };

      const cornerTicks: CornerTickState[] = [0, 1, 2, 3].map((i) => ({
        vertexIndex: i,
        progress: 1.0,
        opacity: lerp(1.0, 0.8, subordinationProgress),
      }));

      channels = {
        opticalField: lerp(1.0, 0.0, easeInOutQuad(phaseProgress(t, 0.25, 0.65))),
        opticalFarm: lerp(0.0, 1.0, easeInOutQuad(phaseProgress(t, 0.15, 0.55))),
        opticalOrg: 0,
        opticalRegion: 0,
        opticalNation: 0,

        microMotion: {
          selectedPlotAcquisition: 1.0,
          cornerTicks,
          parcelAcquisition,
          farmEnvelope: {
            drawProgress: envelopeDrawProgress,
            opacity: envelopeOpacity,
            flash: envelopeFlash,
          },
          organizationLinks: {},
          organizationNodes: {},
          regionContours: [],
          coastline: 0,
          administrativeContext: 0,
          countryBoundary: 0,
        },

        sisterFarms: 0,
        organizationLinks: 0,
        organizationTopologyNodes: 0,
        regionalAggregationField: 0,
        contourRevealProgress: 0,
        selectedRegion: 0,
        peerRegions: 0,
        countryBoundary: 0,
        coastlineRevealProgress: 0,
        administrativeContext: 0,
      };
    }

    // ── Transition B: Farm -> Organization ───────────────────
    else if (from === "farm" && to === "organization") {
      const camT = easeInOutCubic(phaseProgress(t, 0.20, 0.75));
      const camFrom = stageCameras.farm;
      const camTo = stageCameras.organization;

      camera = {
        longitude: lerp(camFrom.longitude, camTo.longitude, camT),
        latitude: lerp(camFrom.latitude, camTo.latitude, camT),
        zoom: lerp(camFrom.zoom, camTo.zoom, camT),
        pitch: lerp(camFrom.pitch, camTo.pitch, camT),
        bearing: lerpAngle(camFrom.bearing, camTo.bearing, camT),
      };

      const orgLinksP = phaseProgress(t, 0.25, 0.75);
      const orgNodesP = phaseProgress(t, 0.50, 0.95);

      channels = {
        opticalField: 0,
        opticalFarm: lerp(1.0, 0.0, easeInOutQuad(phaseProgress(t, 0.15, 0.55))),
        opticalOrg: lerp(0.0, 0.85, easeInOutQuad(phaseProgress(t, 0.25, 0.75))),
        opticalRegion: 0,
        opticalNation: 0,

        microMotion: createSettledMicroMotion("farm"),
        sisterFarms: lerp(0.0, 0.8, phaseProgress(t, 0.10, 0.50)),
        organizationLinks: lerp(0.0, 1.0, orgLinksP),
        organizationTopologyNodes: lerp(0.0, 1.0, orgNodesP),
        regionalAggregationField: 0,
        contourRevealProgress: 0,
        selectedRegion: 0,
        peerRegions: 0,
        countryBoundary: 0,
        coastlineRevealProgress: 0,
        administrativeContext: 0,
      };
    }

    // ── Transition C: Organization -> Region ─────────────────
    else if (from === "organization" && to === "region") {
      const camT = easeInOutCubic(phaseProgress(t, 0.20, 0.75));
      const camFrom = stageCameras.organization;
      const camTo = stageCameras.region;

      camera = {
        longitude: lerp(camFrom.longitude, camTo.longitude, camT),
        latitude: lerp(camFrom.latitude, camTo.latitude, camT),
        zoom: lerp(camFrom.zoom, camTo.zoom, camT),
        pitch: lerp(camFrom.pitch, camTo.pitch, camT),
        bearing: 0,
      };

      const contourP = phaseProgress(t, 0.15, 0.75);
      const regionBoundaryP = phaseProgress(t, 0.50, 0.95);

      channels = {
        opticalField: 0,
        opticalFarm: 0,
        opticalOrg: lerp(0.85, 0.0, easeInCubic(phaseProgress(t, 0.10, 0.50))),
        opticalRegion: lerp(0.0, 0.85, easeInOutQuad(phaseProgress(t, 0.20, 0.65))),
        opticalNation: 0,

        microMotion: createSettledMicroMotion("farm"),
        sisterFarms: lerp(0.8, 0.0, t),
        organizationLinks: lerp(1.0, 0.0, t),
        organizationTopologyNodes: lerp(1.0, 0.0, t),
        regionalAggregationField: lerp(0.0, 1.0, contourP),
        contourRevealProgress: contourP,
        selectedRegion: lerp(0.0, 1.0, regionBoundaryP),
        peerRegions: 0,
        countryBoundary: lerp(0.0, 0.15, t),
        coastlineRevealProgress: 0,
        administrativeContext: 0,
      };
    }

    // ── Transition D: Region -> Nation ───────────────────────
    else if (from === "region" && to === "nation") {
      const zoomT = easeInCubic(phaseProgress(t, 0.25, 0.65));
      const posT = easeInOutCubic(phaseProgress(t, 0.60, 0.92));
      const camFrom = stageCameras.region;
      const camTo = stageCameras.nation;

      camera = {
        longitude: lerp(camFrom.longitude, camTo.longitude, posT),
        latitude: lerp(camFrom.latitude, camTo.latitude, posT),
        zoom: lerp(camFrom.zoom, camTo.zoom, zoomT),
        pitch: 0,
        bearing: 0,
      };

      const countryRevealP = phaseProgress(t, 0.25, 0.70);
      const coastP = phaseProgress(t, 0.20, 0.60);
      const adminRevealP = phaseProgress(t, 0.60, 0.90);
      const peerRegionsP = phaseProgress(t, 0.80, 1.00);

      channels = {
        opticalField: 0,
        opticalFarm: 0,
        opticalOrg: 0,
        opticalRegion: lerp(0.85, 0.0, easeInCubic(phaseProgress(t, 0.10, 0.50))),
        opticalNation: lerp(0.0, 0.90, easeInOutQuad(phaseProgress(t, 0.25, 0.75))),

        microMotion: createSettledMicroMotion("farm"),
        sisterFarms: 0,
        organizationLinks: 0,
        organizationTopologyNodes: 0,
        regionalAggregationField: lerp(1.0, 0.0, t),
        contourRevealProgress: lerp(1.0, 0.0, t),
        selectedRegion: lerp(1.0, 0.35, countryRevealP),
        peerRegions: lerp(0.0, 0.65, peerRegionsP),
        countryBoundary: lerp(0.15, 1.0, countryRevealP),
        coastlineRevealProgress: coastP,
        administrativeContext: lerp(0.0, 0.5, adminRevealP),
      };
    }

    const activeStage = t > 0.5 ? to : from;
    return {
      camera,
      channels,
      activeLayers: new Set(["stage-raster", "active-lineage", "farm-boundaries", "portfolio-centroids", "agricultural-regions", "national-boundary"]),
      layerOpacities: buildLayerOpacities(channels),
      stage: activeStage,
      settledStage: null,
      fromStage: from,
      toStage: to,
      transitionT: t,
      hud: {
        scaleLabel: `TRANSITION: ${from.toUpperCase()} → ${to.toUpperCase()}`,
        contextLabel: "Multi-level spatial transformation",
        authorityLabel: "Illustrative spatial demonstration",
      },
      selectedPlotId: "PLOT-017",
    };
  }

  // ── 3. EVIDENCE DIVE (Nation → Region → Farm → Field Reverse Lineage) ──
  if (position.type === "evidence_dive") {
    const t = position.t;

    // Multi-phase camera trajectory:
    // Phase 1 (0.0 -> 0.35): Nation -> Region
    // Phase 2 (0.35 -> 0.70): Region -> Farm
    // Phase 3 (0.70 -> 1.00): Farm -> Field (Evidence dock)
    let camera: CameraViewState;

    if (t < 0.35) {
      const p1 = t / 0.35;
      const camT = easeInOutCubic(p1);
      camera = {
        longitude: lerp(stageCameras.nation.longitude, stageCameras.region.longitude, camT),
        latitude: lerp(stageCameras.nation.latitude, stageCameras.region.latitude, camT),
        zoom: lerp(stageCameras.nation.zoom, stageCameras.region.zoom, camT),
        pitch: lerp(stageCameras.nation.pitch, stageCameras.region.pitch, camT),
        bearing: 0,
      };
    } else if (t < 0.70) {
      const p2 = (t - 0.35) / 0.35;
      const camT = easeInOutCubic(p2);
      camera = {
        longitude: lerp(stageCameras.region.longitude, stageCameras.farm.longitude, camT),
        latitude: lerp(stageCameras.region.latitude, stageCameras.farm.latitude, camT),
        zoom: lerp(stageCameras.region.zoom, stageCameras.farm.zoom, camT),
        pitch: lerp(stageCameras.region.pitch, stageCameras.farm.pitch, camT),
        bearing: lerpAngle(0, stageCameras.farm.bearing, camT),
      };
    } else {
      const p3 = (t - 0.70) / 0.30;
      const camT = easeInOutCubic(p3);
      camera = {
        longitude: lerp(stageCameras.farm.longitude, stageCameras.field.longitude, camT),
        latitude: lerp(stageCameras.farm.latitude, stageCameras.field.latitude, camT),
        zoom: lerp(stageCameras.farm.zoom, stageCameras.field.zoom, camT),
        pitch: lerp(stageCameras.farm.pitch, stageCameras.field.pitch, camT),
        bearing: lerpAngle(stageCameras.farm.bearing, stageCameras.field.bearing, camT),
      };
    }

    const channels: VisualChannelProfile = {
      opticalNation: lerp(0.90, 0.0, phaseProgress(t, 0.0, 0.35)),
      opticalRegion: lerp(0.0, 0.85, phaseProgress(t, 0.15, 0.40)) * (1 - phaseProgress(t, 0.45, 0.70)),
      opticalOrg: lerp(0.0, 0.80, phaseProgress(t, 0.35, 0.55)) * (1 - phaseProgress(t, 0.60, 0.75)),
      opticalFarm: lerp(0.0, 1.0, phaseProgress(t, 0.50, 0.75)) * (1 - phaseProgress(t, 0.75, 0.95)),
      opticalField: lerp(0.0, 1.0, phaseProgress(t, 0.70, 0.95)),

      microMotion: {
        selectedPlotAcquisition: 1.0,
        cornerTicks: [0, 1, 2, 3].map((i) => ({ vertexIndex: i, progress: 1.0, opacity: lerp(0.5, 1.0, phaseProgress(t, 0.70, 1.0)) })),
        parcelAcquisition: {
          "PLOT-017": { id: "PLOT-017", outlineProgress: 1.0, membershipMix: 1.0, acquisitionFlash: 0, emphasis: 1.0 },
          "PLOT-018": { id: "PLOT-018", outlineProgress: lerp(1.0, 0.0, phaseProgress(t, 0.80, 1.0)), membershipMix: 1.0, acquisitionFlash: 0, emphasis: 0.5 },
          "PLOT-019": { id: "PLOT-019", outlineProgress: lerp(1.0, 0.0, phaseProgress(t, 0.80, 1.0)), membershipMix: 1.0, acquisitionFlash: 0, emphasis: 0.5 },
          "PLOT-020": { id: "PLOT-020", outlineProgress: lerp(1.0, 0.0, phaseProgress(t, 0.80, 1.0)), membershipMix: 1.0, acquisitionFlash: 0, emphasis: 0.5 },
          "PLOT-021": { id: "PLOT-021", outlineProgress: lerp(1.0, 0.0, phaseProgress(t, 0.80, 1.0)), membershipMix: 1.0, acquisitionFlash: 0, emphasis: 0.5 },
          "PLOT-022": { id: "PLOT-022", outlineProgress: lerp(1.0, 0.0, phaseProgress(t, 0.80, 1.0)), membershipMix: 1.0, acquisitionFlash: 0, emphasis: 0.5 },
        },
        farmEnvelope: {
          drawProgress: 1.0,
          opacity: lerp(0.30, 0.0, phaseProgress(t, 0.75, 0.95)),
          flash: 0,
        },
        organizationLinks: {},
        organizationNodes: {},
        regionContours: [],
        coastline: lerp(1.0, 0.0, phaseProgress(t, 0.0, 0.35)),
        administrativeContext: lerp(0.5, 0.0, phaseProgress(t, 0.0, 0.40)),
        countryBoundary: lerp(1.0, 0.0, phaseProgress(t, 0.0, 0.35)),
      },

      sisterFarms: lerp(0.0, 0.6, phaseProgress(t, 0.30, 0.55)) * (1 - phaseProgress(t, 0.65, 0.85)),
      organizationLinks: lerp(0.0, 0.8, phaseProgress(t, 0.35, 0.60)) * (1 - phaseProgress(t, 0.65, 0.85)),
      organizationTopologyNodes: lerp(0.0, 0.8, phaseProgress(t, 0.35, 0.60)) * (1 - phaseProgress(t, 0.65, 0.85)),
      regionalAggregationField: lerp(1.0, 0.0, phaseProgress(t, 0.10, 0.45)),
      contourRevealProgress: lerp(1.0, 0.0, phaseProgress(t, 0.10, 0.45)),
      selectedRegion: lerp(0.35, 0.9, phaseProgress(t, 0.0, 0.30)) * (1 - phaseProgress(t, 0.40, 0.65)),
      peerRegions: lerp(0.65, 0.0, phaseProgress(t, 0.0, 0.30)),
      countryBoundary: lerp(1.0, 0.0, phaseProgress(t, 0.0, 0.35)),
      coastlineRevealProgress: lerp(1.0, 0.0, phaseProgress(t, 0.0, 0.30)),
      administrativeContext: lerp(0.5, 0.0, phaseProgress(t, 0.0, 0.35)),
    };

    return {
      camera,
      channels,
      activeLayers: new Set(["stage-raster", "active-lineage"]),
      layerOpacities: buildLayerOpacities(channels),
      stage: "field",
      settledStage: null,
      fromStage: "nation",
      toStage: "field",
      transitionT: t,
      hud: {
        scaleLabel: "LINEAGE DIVE · NATION → FIELD",
        contextLabel: "Tracing sovereign intelligence back to ground truth evidence",
        authorityLabel: "Illustrative spatial demonstration",
      },
      selectedPlotId: "PLOT-017",
    };
  }

  // ── 4. DEFERRED HOLD (Quiet Evidence Workspace) ────────────
  const camField = stageCameras.field;
  const quietChannels = getSettledChannels("field");
  return {
    camera: camField,
    channels: quietChannels,
    activeLayers: new Set(["stage-raster", "active-lineage"]),
    layerOpacities: buildLayerOpacities(quietChannels),
    stage: "field",
    settledStage: "field",
    fromStage: "field",
    toStage: "field",
    transitionT: 1.0,
    hud: {
      scaleLabel: "FIELD EVIDENCE DOCK",
      contextLabel: "Canonical parcel state",
      authorityLabel: "Illustrative spatial demonstration",
    },
    selectedPlotId: "PLOT-017",
  };
}

function buildLayerOpacities(c: VisualChannelProfile): Record<LayerId, number> {
  return {
    "stage-raster": Math.max(c.opticalField, c.opticalFarm, c.opticalOrg, c.opticalRegion, c.opticalNation),
    "demo-optical": Math.max(c.opticalField, c.opticalFarm),
    "active-lineage": 1.0,
    "field-polygon": 1.0,
    "farm-boundaries": c.microMotion?.farmEnvelope?.opacity || 0,
    "portfolio-centroids": Math.max(c.organizationLinks, c.organizationTopologyNodes),
    "agricultural-regions": Math.max(c.selectedRegion, c.peerRegions),
    "national-boundary": c.countryBoundary,
    "sentinel-derived": c.opticalField * 0.7,
    "sar-geometry": c.opticalField * 0.8,
    "iot-sensor": c.opticalField * 0.9,
    "field-annotations": 0.0,
    "farm-annotations": 0.0,
    "national-annotations": 0.0,
  };
}
