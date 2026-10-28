import { createHash } from "node:crypto";

export const PARCEL_ASSESSMENT_CONTRACT_VERSION = "2026.10-p2a.1";

export function computeDeterministicHash(input) {
  return createHash("sha256").update(String(input), "utf8").digest("hex");
}

export function computeGeometryHash(geometry) {
  if (!geometry) return "empty_geometry";
  let target = geometry;
  if (typeof geometry === "string") {
    try {
      target = JSON.parse(geometry);
    } catch {
      return computeDeterministicHash(geometry);
    }
  }
  const canonicalString = JSON.stringify(target, Object.keys(target).sort());
  return computeDeterministicHash(canonicalString);
}

export function computeClientFingerprint(identity) {
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
    identity.observationWindow?.start,
    identity.observationWindow?.end,
    identity.evidenceCutoffAt,
    identity.publishedAt,
    identity.publicationReceiptHash || identity.receiptHash || "",
  ].join("|");
  return computeDeterministicHash(canonicalPayload);
}

export function computeReceiptHash(identity) {
  return computeClientFingerprint(identity);
}

export function deepFreeze(obj) {
  if (obj === null || typeof obj !== "object") return obj;
  Object.freeze(obj);
  for (const key of Object.getOwnPropertyNames(obj)) {
    const value = obj[key];
    if (value !== null && (typeof value === "object" || typeof value === "function") && !Object.isFrozen(value)) {
      deepFreeze(value);
    }
  }
  return obj;
}

function isValidIsoDate(str) {
  if (typeof str !== "string" || !str) return false;
  const d = new Date(str);
  return !isNaN(d.getTime());
}

export function validateAssessmentIdentity(identity) {
  const errors = [];
  if (!identity || typeof identity !== "object") {
    return { valid: false, errors: ["identity_must_be_non_null_object"] };
  }

  const id = identity;

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

  const receipt = id.publicationReceiptHash || id.receiptHash;
  if (!receipt || typeof receipt !== "string") {
    errors.push("publicationReceiptHash_required");
  } else if (receipt.length < 8) {
    errors.push("publicationReceiptHash_malformed");
  }

  if (id.clientFingerprint && errors.length === 0) {
    const expectedFingerprint = computeClientFingerprint(id);
    if (id.clientFingerprint !== expectedFingerprint) {
      errors.push("clientFingerprint_mismatch");
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

export function createImmutableParcelAssessment(params) {
  const validation = validateAssessmentIdentity(params.identity);
  if (!validation.valid) {
    throw new Error(`Invalid ParcelAssessmentIdentity: ${validation.errors.join("; ")}`);
  }

  const cutoffTime = new Date(params.identity.evidenceCutoffAt).getTime();
  const timeline = params.evidenceTimeline || [];

  for (const event of timeline) {
    if (event.verified && event.type === "observation") {
      const eventTime = new Date(event.observedAt || event.capturedAt).getTime();
      if (!isNaN(eventTime) && eventTime > cutoffTime && event.manifestMembership === true) {
        throw new Error(
          `Observation evidence event ${event.id} (${event.observedAt || event.capturedAt}) exceeds evidenceCutoffAt (${params.identity.evidenceCutoffAt}). Late observations cannot be part of published assessment manifest.`
        );
      }
    }
  }

  const normalizedIdentity = {
    ...params.identity,
    publicationReceiptHash: params.identity.publicationReceiptHash || params.identity.receiptHash,
    receiptHash: params.identity.receiptHash || params.identity.publicationReceiptHash,
  };

  const assessment = {
    identity: normalizedIdentity,
    canonicalLayerResults: params.canonicalLayerResults,
    authoritativeSurfaces: params.authoritativeSurfaces || [],
    topFindings: params.topFindings || [],
    quality: params.quality,
    evidenceTimeline: timeline,
  };

  return deepFreeze(assessment);
}

export function isLateArrivingEvidence(identity, evidence) {
  if (evidence.manifestMembership === true) return false;
  const cutoff = new Date(identity.evidenceCutoffAt).getTime();
  const ingested = evidence.ingestedAt ? new Date(evidence.ingestedAt).getTime() : NaN;
  const observed = new Date(evidence.observedAt || evidence.capturedAt || "").getTime();

  if (!isNaN(ingested) && ingested > cutoff) return true;
  if (!isNaN(observed) && observed > cutoff) return true;
  return evidence.manifestMembership === false;
}

export function isAssessmentStaleForGeometry(identity, currentGeometry) {
  const currentHash = computeGeometryHash(currentGeometry);
  return identity.geometryHash !== currentHash;
}

export function isAssessmentStaleForCropCycle(identity, currentCropCycleId) {
  return (identity.cropCycleId ?? null) !== (currentCropCycleId ?? null);
}
