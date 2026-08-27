/* ═══ AgriWise R2 Pass 3B — World Authority Data Contract Schema ═
   Defines the geometry classes, structural parent-child relationships,
   narrative intents, and visual contracts for the spatial world.
   
   STRICT SEPARATION: Contains ONLY spatial features and hierarchy.
   Zero scientific state, zero mock risk scores in the world contract.
   ═══════════════════════════════════════════════════════════════ */

export type GeometryClass =
  | "REFERENCE_GEOGRAPHY"
  | "ILLUSTRATIVE_GEOMETRY"
  | "DERIVED_AGGREGATION";

export interface ReferenceSource {
  name: string;
  license: string;
  sourceVersion?: string;
  originalCrs?: string;
  simplification?: string;
}

export interface WorldPlot {
  id: string;
  name: string;
  farmId: string;
  geometryClass: GeometryClass;
  registrationMethod?: string;
  coordinates: [number, number][]; // Polygon ring [[lng, lat], ...]
}

export interface WorldFarm {
  id: string;
  name: string;
  portfolioId: string;
  plotIds: string[];
  geometryClass: GeometryClass;
  registrationMethod?: string;
  envelopeCoordinates?: [number, number][];
  displayGeometry?: [number, number][];
}

export interface WorldPortfolio {
  id: string;
  name: string;
  regionId: string;
  farmIds: string[];
  geometryClass: GeometryClass;
}

export interface WorldRegion {
  id: string;
  name: string;
  countryId: string;
  portfolioIds: string[];
  geometryClass: GeometryClass;
  coordinates: [number, number][];
}

export interface WorldCountry {
  id: string;
  name: string;
  nameAr?: string;
  geometryClass: GeometryClass;
  referenceSource: ReferenceSource;
  coordinates: [number, number][];
}

export interface WorldMeta {
  id: string;
  version: string;
  status: "ILLUSTRATIVE";
  liveAssessment: boolean;
  primaryPlotId: string;
  primaryLineage: [string, string, string, string, string]; // [plotId, farmId, portfolioId, regionId, countryId]
}

export interface IllustrativeWorld {
  meta: WorldMeta;
  plots: WorldPlot[];
  farms: WorldFarm[];
  portfolios: WorldPortfolio[];
  regions: WorldRegion[];
  country: WorldCountry;
}

/* ── Narrative & Visual Intent Contracts ───────────────────── */

export interface NarrativeIntent {
  stage: "field" | "farm" | "organization" | "region" | "nation";
  visitorQuestion: string;
  coreMessage: string;
  cognitiveGoal: "orientation" | "comprehension" | "aggregation" | "pattern" | "ambition";
  emotionalTone: "control" | "clarity" | "leverage" | "confidence" | "possibility";
  proofCue?: string;
  maxHeadlineWords: number;
  maxSupportingWords: number;
}

export interface VisualIntent {
  focalEntityId: string;
  dominantRepresentation: "physical" | "topological" | "aggregate" | "regional" | "sovereign";
  complexity: "low" | "medium" | "high";
  copySide: "left" | "right" | "center";
  focusX: number; // 0.0 -> 1.0 (viewport normalized)
  focusY: number;
}
