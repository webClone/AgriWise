/* ═══ AgriWise R2 — Illustrative Scientific Run Schema ═════════
   Canonical TypeScript types for the frozen deterministic demonstration
   data contract. Eliminates numerical literals and fake mock percentages
   from UI components.
   ═══════════════════════════════════════════════════════════════ */

export type DemoStatus =
  | "ILLUSTRATIVE"
  | "REAL_ANONYMIZED"
  | "SYNTHETIC_TEST_FIXTURE";

export type MeasurementReality =
  | "DIRECT_OBSERVATION"
  | "PHYSIO_ASSIMILATION"
  | "INVERSE_RECONSTRUCTION"
  | "BAYESIAN_ESTIMATE"
  | "AGRONOMIC_DIAGNOSTIC"
  | "POLICY_CONSTRAINT";

export type TransformationClass =
  | "RAW_PROVIDER_TILE"
  | "ATMOSPHERIC_CORRECTION"
  | "RADIOMETRIC_CLOSURE"
  | "SPATIOTEMPORAL_INTERPOLATION"
  | "HYPOTHESIS_ATTRIBUTION"
  | "GOVERNED_PRESCRIPTION";

export type UncertaintyClass =
  | "OBSERVED_PRECISION"
  | "P10_P90_INTERVAL"
  | "BMA_DISAGREEMENT"
  | "POSTERIOR_RASTER";

export interface AuthorityCeiling {
  stateUpdate: boolean;
  diagnostic: boolean;
  prescription: boolean;
  visual: boolean;
}

export interface RunManifest {
  runId: string;
  timestamp: string;
  demoStatus: DemoStatus;
  plotId: string;
  anonymizedLocation: {
    label: string;
    latitude: number;
    longitude: number;
    boundingPolygon: [number, number][];
  };
  cropContext: {
    cropName: string;
    cropCode: string;
    seasonYear: number;
    sowingDate: string;
    expectedHarvest: string;
  };
}

export interface EvidenceNode {
  id: string;
  label: string;
  family: string;
  icon: string;
  provider: string;
  acquisitionTime: string;
  nativeResolution: string;
  effectiveResolution: string;
  measurementReality: MeasurementReality;
  transformationClass: TransformationClass;
  authorityCeiling: AuthorityCeiling;
  fieldCubeVoxelRef?: string;
  worldlineEventRef?: string;
}

export interface CanonicalEvidenceGraphDemo {
  nodes: EvidenceNode[];
  edges: { source: string; target: string; relationship: string }[];
}

export interface FieldCubeCell {
  voxelId: string;
  coordinate: [number, number]; // spatial offset
  layer: string;
  valueLabel: string;
  observedMask: boolean;
  reconstructionMask: boolean;
  uncertaintyValue: number; // 0 to 1
  supportType: "OBSERVED" | "RECONSTRUCTED" | "BROAD_SUPPORT" | "PRIOR" | "MISSING";
  authority: string;
}

export interface CanonicalFieldCubeDemo {
  dimensions: { x: number; y: number; timeSteps: number };
  cells: FieldCubeCell[];
}

export interface WorldlineEvent {
  id: string;
  date: string;
  stage: string;
  title: string;
  evidenceSourceRef: string;
  authority: string;
  description: string;
  provenanceHash: string;
}

export interface CanonicalPlotWorldlineDemo {
  events: WorldlineEvent[];
}

export interface LayerExecutionDemo {
  layerId: string; // L0 to L10
  layerName: string;
  scientificRole: string;
  inputs: string[];
  outputs: string[];
  enginesUsed: string[];
  evidenceRequirements: string[];
  uncertaintyClass: UncertaintyClass;
  authorityCeiling: AuthorityCeiling;
  failureAbstentionBehavior: string;
  validationMethod: string;
  whatItMayNotClaim: string;
}

export interface AsmaeClosureStep {
  stepIndex: number;
  stepName: string;
  description: string;
  nativeSupportLabel: string;
  effectiveResolutionLabel: string;
  radiometricResidualNormalized: number;
  posteriorUncertaintyLabel: string;
  authorityAssigned: string;
}

export interface IllustrativeAsmaeRun {
  algorithm: string;
  parentObservation: string;
  microzoneCount: number;
  closureSteps: AsmaeClosureStep[];
}

export interface DemoClaim {
  claimId: string;
  statement: string;
  authorityLevel: string;
  evidenceRefs: string[];
  prohibitedClaims: string[];
}

export interface IllustrativeScientificRun {
  manifest: RunManifest;
  evidenceGraph: CanonicalEvidenceGraphDemo;
  fieldCube: CanonicalFieldCubeDemo;
  worldline: CanonicalPlotWorldlineDemo;
  layerExecutions: LayerExecutionDemo[];
  asmae: IllustrativeAsmaeRun;
  claims: DemoClaim[];
}
