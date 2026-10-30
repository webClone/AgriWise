/**
 * P2-C public TypeScript contract. Implementation lives in the shared .mjs
 * module so Node regression tests and the browser execute the same logic.
 */
import {
  TELEMETRY_CONTRACT_VERSION as VERSION,
  TELEMETRY_STATUS as STATUS,
  classifyManifestEvidence as classifyManifestEvidenceCore,
  classifyTelemetryObservation as classifyTelemetryObservationCore,
  createLiveTelemetryStream as createLiveTelemetryStreamCore,
  appendOperationalTelemetry as appendOperationalTelemetryCore,
} from "./telemetry-contract.mjs";
import type {
  ParcelAssessment,
  AssessmentEvidenceEvent,
} from "./parcel-assessment-contract";

export const TELEMETRY_CONTRACT_VERSION: string = VERSION;
export const TELEMETRY_STATUS = STATUS;
export type TelemetryStatus =
  | "CERTIFIED_MANIFEST"
  | "LIVE_UNCERTIFIED"
  | "MODEL_FORECAST"
  | "LATE_ARRIVING_UNADMITTED"
  | "UNVERIFIED";

export interface TelemetryScope {
  tenantId: string;
  farmId: string;
  plotId: string;
}

export interface TelemetryObservation {
  /** Authenticated source scope; must match the active operational buffer. */
  scope: TelemetryScope;
  id: string;
  source: string;
  kind: "observation" | "forecast";
  observedAt?: string;
  ingestedAt?: string | null;
  validAt?: string;
  modelId?: string;
  metric?: string;
  value?: number | null;
  unit?: string;
  // Never accepted as a self-declared promotion or signed manifest receipt.
  manifestMembership?: boolean;
  certified?: boolean;
  certificationStatus?: string;
}

export interface LiveTelemetryStream {
  readonly contractVersion: string;
  readonly scope: Readonly<TelemetryScope>;
  readonly observations: ReadonlyArray<Readonly<TelemetryObservation>>;
}

export const classifyManifestEvidence = (
  assessment: ParcelAssessment | null,
  event: AssessmentEvidenceEvent
): TelemetryStatus => classifyManifestEvidenceCore(assessment, event) as TelemetryStatus;

export const classifyTelemetryObservation = (
  observation: TelemetryObservation,
  evidenceCutoffAt: string | null,
  now?: string
): TelemetryStatus => classifyTelemetryObservationCore(
  observation, evidenceCutoffAt, now
) as TelemetryStatus;

export const createLiveTelemetryStream = (scope: TelemetryScope): LiveTelemetryStream =>
  createLiveTelemetryStreamCore(scope) as LiveTelemetryStream;

export const appendOperationalTelemetry = (
  stream: LiveTelemetryStream,
  observation: TelemetryObservation,
  maxCount?: number
): LiveTelemetryStream => appendOperationalTelemetryCore(
  stream, observation, maxCount
) as LiveTelemetryStream;

