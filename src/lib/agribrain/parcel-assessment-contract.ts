/**
 * Akaloris / AgriBrain — Parcel Assessment Identity & Scientific Content Contract (Phase 2-A)
 *
 * Enforces the architectural boundary:
 *   "One parcel assessment, one verified scientific state, many presentation views."
 *
 * Separates immutable assessment identity from scientific content, simulations,
 * and live late-arriving telemetry.
 */

export const PARCEL_ASSESSMENT_CONTRACT_VERSION = "2026.10-p2a.1";

export interface ParcelAssessmentIdentity {
  tenantId: string;
  farmId: string;
  plotId: string;
  cropCycleId: string | null;
  publicationId: string;
  runId: string;
  snapshotId: string;
  geometryHash: string;
  observationWindow: {
    start: string;
    end: string;
  };
  evidenceCutoffAt: string;
  publishedAt: string;
  receiptHash: string;
  contractVersion: string;
}

export interface LayerResult {
  layerId: string;
  status: "OK" | "DEGRADED" | "SKIPPED" | "UNAVAILABLE" | "FAILED";
  confidence: number;
  sources: string[];
  summary?: string;
  flags?: string[];
  data?: Record<string, unknown>;
}

export interface Finding {
  id: string;
  title: string;
  severity: "low" | "medium" | "high" | "critical" | "info";
  description: string;
  layerId?: string;
  actionable?: boolean;
  evidenceSources?: string[];
}

export interface AssessmentQuality {
  degradationMode: string;
  reliabilityScore: number;
  warnings: string[];
  criticalErrors?: string[];
  surfacesGenerated: number;
  zonesGenerated: number;
}

export interface AssessmentEvidenceEvent {
  id: string;
  type: "observation" | "assimilation" | "prediction" | "simulation";
  source: string;
  capturedAt: string;
  ingestedAt?: string;
  summary: string;
  verified: boolean;
}

export interface ParcelAssessment {
  readonly identity: Readonly<ParcelAssessmentIdentity>;
  readonly canonicalLayerResults: Readonly<Record<string, LayerResult>>;
  readonly authoritativeSurfaces: ReadonlyArray<any>;
  readonly topFindings: ReadonlyArray<Finding>;
  readonly quality: Readonly<AssessmentQuality>;
  readonly evidenceTimeline: ReadonlyArray<AssessmentEvidenceEvent>;
}

export type AssessmentState =
  | { status: "loading" }
  | { status: "ready"; assessment: ParcelAssessment }
  | { status: "unavailable"; reason: string }
  | { status: "invalid"; reason: string }
  | { status: "superseded"; snapshotId: string };

/**
 * Deterministic string hash (SHA-256 in Node, deterministic FNV-1a 64-bit fallback in browser).
 */
export function computeDeterministicHash(input: string): string {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const nodeCrypto = require("crypto");
    if (nodeCrypto?.createHash) {
      return nodeCrypto.createHash("sha256").update(input, "utf8").digest("hex");
    }
  } catch {
    // Fallback for pure browser environments without node:crypto
  }

  // 64-bit FNV-1a deterministic hash formatted as 16-char hex
  let h1 = 0x811c9dc5;
  let h2 = 0x49f2b87b;
  for (let i = 0; i < input.length; i++) {
    const ch = input.charCodeAt(i);
    h1 ^= ch;
    h1 = Math.imul(h1, 0x01000193);
    h2 ^= ch;
    h2 = Math.imul(h2, 0x01000193);
  }
  const hex1 = (h1 >>> 0).toString(16).padStart(8, "0");
  const hex2 = (h2 >>> 0).toString(16).padStart(8, "0");
  return `${hex1}${hex2}`;
}

/**
 * Compute deterministic geometry hash from GeoJSON geometry, coordinates, or bounds.
 */
export function computeGeometryHash(geometry: unknown): string {
  if (!geometry) return "empty_geometry";
  let target = geometry;
  if (typeof geometry === "string") {
    try {
      target = JSON.parse(geometry);
    } catch {
      return computeDeterministicHash(geometry);
    }
  }
  const canonicalString = JSON.stringify(target, Object.keys(target as object).sort());
  return computeDeterministicHash(canonicalString);
}

/**
 * Compute receipt hash for assessment identity.
 */
export function computeReceiptHash(identity: Omit<ParcelAssessmentIdentity, "receiptHash">): string {
  const canonicalPayload = [
    identity.contractVersion,
    identity.tenantId,
    identity.farmId,
    identity.plotId,
    identity.cropCycleId ?? "null",
    identity.publicationId,
    identity.runId,
    identity.snapshotId,
    identity.geometryHash,
    identity.observationWindow.start,
    identity.observationWindow.end,
    identity.evidenceCutoffAt,
    identity.publishedAt,
  ].join("|");
  return computeDeterministicHash(canonicalPayload);
}

/**
 * Deep freeze helper to guarantee immutability across React presentation layers.
 */
export function deepFreeze<T>(obj: T): T {
  if (obj === null || typeof obj !== "object") return obj;
  Object.freeze(obj);
  for (const key of Object.getOwnPropertyNames(obj)) {
    const value = (obj as any)[key];
    if (value !== null && (typeof value === "object" || typeof value === "function") && !Object.isFrozen(value)) {
      deepFreeze(value);
    }
  }
  return obj;
}

function isValidIsoDate(str: unknown): str is string {
  if (typeof str !== "string" || !str) return false;
  const d = new Date(str);
  return !isNaN(d.getTime());
}

/**
 * Validate assessment identity according to Phase 2 contract rules.
 */
export function validateAssessmentIdentity(identity: unknown): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  if (!identity || typeof identity !== "object") {
    return { valid: false, errors: ["identity_must_be_non_null_object"] };
  }

  const id = identity as Partial<ParcelAssessmentIdentity>;

  if (!id.tenantId || typeof id.tenantId !== "string") errors.push("tenantId_required");
  if (!id.farmId || typeof id.farmId !== "string") errors.push("farmId_required");
  if (!id.plotId || typeof id.plotId !== "string") errors.push("plotId_required");
  if (!id.publicationId || typeof id.publicationId !== "string") errors.push("publicationId_required");
  if (!id.runId || typeof id.runId !== "string") errors.push("runId_required");
  if (!id.snapshotId || typeof id.snapshotId !== "string") errors.push("snapshotId_required");
  if (!id.geometryHash || typeof id.geometryHash !== "string") errors.push("geometryHash_required");

  if (id.contractVersion !== PARCEL_ASSESSMENT_CONTRACT_VERSION) {
    errors.push(`contractVersion_mismatch:expected_${PARCEL_ASSESSMENT_CONTRACT_VERSION}_got_${id.contractVersion}`);
  }

  if (!id.observationWindow || typeof id.observationWindow !== "object") {
    errors.push("observationWindow_required");
  } else {
    if (!isValidIsoDate(id.observationWindow.start)) errors.push("observationWindow_start_invalid");
    if (!isValidIsoDate(id.observationWindow.end)) errors.push("observationWindow_end_invalid");
    if (
      isValidIsoDate(id.observationWindow.start) &&
      isValidIsoDate(id.observationWindow.end) &&
      new Date(id.observationWindow.start).getTime() > new Date(id.observationWindow.end).getTime()
    ) {
      errors.push("observationWindow_start_after_end");
    }
  }

  if (!isValidIsoDate(id.evidenceCutoffAt)) {
    errors.push("evidenceCutoffAt_invalid");
  }
  if (!isValidIsoDate(id.publishedAt)) {
    errors.push("publishedAt_invalid");
  }

  if (isValidIsoDate(id.evidenceCutoffAt) && isValidIsoDate(id.publishedAt)) {
    if (new Date(id.publishedAt).getTime() < new Date(id.evidenceCutoffAt).getTime()) {
      errors.push("publishedAt_before_evidenceCutoffAt");
    }
  }

  if (!id.receiptHash || typeof id.receiptHash !== "string") {
    errors.push("receiptHash_required");
  } else if (errors.length === 0) {
    const expectedReceipt = computeReceiptHash(id as Omit<ParcelAssessmentIdentity, "receiptHash">);
    if (id.receiptHash !== expectedReceipt) {
      errors.push("receiptHash_mismatch");
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Factory to create an immutable, validated ParcelAssessment.
 * Fails closed if validation fails or if late-arriving evidence was included.
 */
export function createImmutableParcelAssessment(params: {
  identity: ParcelAssessmentIdentity;
  canonicalLayerResults: Record<string, LayerResult>;
  authoritativeSurfaces?: any[];
  topFindings?: Finding[];
  quality: AssessmentQuality;
  evidenceTimeline?: AssessmentEvidenceEvent[];
}): ParcelAssessment {
  const validation = validateAssessmentIdentity(params.identity);
  if (!validation.valid) {
    throw new Error(`Invalid ParcelAssessmentIdentity: ${validation.errors.join("; ")}`);
  }

  const cutoffTime = new Date(params.identity.evidenceCutoffAt).getTime();
  const timeline = params.evidenceTimeline || [];

  // Enforce boundary: verified observations cannot have timestamps past evidenceCutoffAt
  for (const event of timeline) {
    if (event.verified && event.type === "observation") {
      const eventTime = new Date(event.capturedAt).getTime();
      if (!isNaN(eventTime) && eventTime > cutoffTime) {
        throw new Error(
          `Observation evidence event ${event.id} (${event.capturedAt}) exceeds evidenceCutoffAt (${params.identity.evidenceCutoffAt}). Late observations cannot be part of published assessment.`
        );
      }
    }
  }

  const assessment: ParcelAssessment = {
    identity: params.identity,
    canonicalLayerResults: params.canonicalLayerResults,
    authoritativeSurfaces: params.authoritativeSurfaces || [],
    topFindings: params.topFindings || [],
    quality: params.quality,
    evidenceTimeline: timeline,
  };

  return deepFreeze(assessment);
}

/**
 * Returns true if an observation was captured after the assessment's evidence cutoff.
 */
export function isLateArrivingEvidence(
  identity: ParcelAssessmentIdentity,
  observationTimeIso: string
): boolean {
  const cutoff = new Date(identity.evidenceCutoffAt).getTime();
  const obs = new Date(observationTimeIso).getTime();
  if (isNaN(cutoff) || isNaN(obs)) return false;
  return obs > cutoff;
}

/**
 * Check if the current plot geometry differs from the geometry used for the assessment.
 */
export function isAssessmentStaleForGeometry(
  identity: ParcelAssessmentIdentity,
  currentGeometry: unknown
): boolean {
  const currentHash = computeGeometryHash(currentGeometry);
  return identity.geometryHash !== currentHash;
}

/**
 * Check if the active crop cycle differs from the crop cycle context of the assessment.
 */
export function isAssessmentStaleForCropCycle(
  identity: ParcelAssessmentIdentity,
  currentCropCycleId: string | null
): boolean {
  return (identity.cropCycleId ?? null) !== (currentCropCycleId ?? null);
}
