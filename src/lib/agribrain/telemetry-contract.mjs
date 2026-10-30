/**
 * P2-C — Scientific publication and operational telemetry are different data planes.
 * Live feed objects cannot self-assert manifest certification or rewrite history.
 */
export const TELEMETRY_CONTRACT_VERSION = "2026.10-p2c.1";
export const TELEMETRY_STATUS = Object.freeze({
  CERTIFIED_MANIFEST: "CERTIFIED_MANIFEST",
  LIVE_UNCERTIFIED: "LIVE_UNCERTIFIED",
  MODEL_FORECAST: "MODEL_FORECAST",
  LATE_ARRIVING_UNADMITTED: "LATE_ARRIVING_UNADMITTED",
  UNVERIFIED: "UNVERIFIED",
});
const isoMillis = value => {
  if (typeof value !== "string" || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d/.test(value)) return NaN;
  return Date.parse(value);
};
const validIso = value => Number.isFinite(isoMillis(value));

/**
 * Only an event directly referenced by the immutable ParcelAssessment manifest
 * may be certified. Matching a timestamp or a caller-supplied flag is insufficient.
 */
export function classifyManifestEvidence(assessment, event) {
  const cutoff = isoMillis(assessment?.identity?.evidenceCutoffAt);
  const observed = isoMillis(event?.observedAt || event?.capturedAt);
  const ingested = event?.ingestedAt == null ? NaN : isoMillis(event.ingestedAt);
  const accepted = event?.acceptedAt == null ? NaN : isoMillis(event.acceptedAt);
  const manifest = assessment?.evidenceTimeline || [];
  const member = Array.isArray(manifest) && manifest.some(item => item === event);
  const identity = assessment?.identity;
  if (
    !identity?.snapshotId || !identity?.publicationReceiptHash || !Number.isFinite(cutoff)
    || !Number.isFinite(observed) || !member || event?.verified !== true
    || event?.manifestMembership !== true || observed > cutoff
    || (event.ingestedAt != null && (!Number.isFinite(ingested) || ingested > cutoff))
    || (event.acceptedAt != null && (!Number.isFinite(accepted) || accepted > cutoff))
  ) return TELEMETRY_STATUS.UNVERIFIED;
  return TELEMETRY_STATUS.CERTIFIED_MANIFEST;
}

/** Live observations NEVER become certified solely by falling before cutoff. */
export function classifyTelemetryObservation(observation, evidenceCutoffAt, now = new Date().toISOString()) {
  const cutoff = isoMillis(evidenceCutoffAt);
  const current = isoMillis(now);
  if (!Number.isFinite(current)) return TELEMETRY_STATUS.UNVERIFIED;
  const kind = String(observation?.kind || "").toLowerCase();
  if (kind === "forecast") {
    const target = isoMillis(observation?.validAt || observation?.observedAt);
    return Number.isFinite(target) && observation?.modelId && observation?.source
      ? TELEMETRY_STATUS.MODEL_FORECAST : TELEMETRY_STATUS.UNVERIFIED;
  }
  if (kind !== "observation" || !observation?.source) return TELEMETRY_STATUS.UNVERIFIED;
  const observed = isoMillis(observation?.observedAt);
  if (!Number.isFinite(observed) || observed > current || !Number.isFinite(cutoff)) {
    return TELEMETRY_STATUS.UNVERIFIED;
  }
  return observed <= cutoff
    ? TELEMETRY_STATUS.LATE_ARRIVING_UNADMITTED
    : TELEMETRY_STATUS.LIVE_UNCERTIFIED;
}

export function createLiveTelemetryStream(scope) {
  if (!scope?.tenantId || !scope?.farmId || !scope?.plotId) {
    throw new Error("telemetry_scope_incomplete");
  }
  return Object.freeze({
    contractVersion: TELEMETRY_CONTRACT_VERSION,
    scope: Object.freeze({
      tenantId: String(scope.tenantId),
      farmId: String(scope.farmId),
      plotId: String(scope.plotId),
    }),
    observations: Object.freeze([]),
  });
}

/** Pure append-only operational stream; deliberately no assessment argument. */
export function appendOperationalTelemetry(stream, observation, maxCount = 500) {
  if (!stream || stream.contractVersion !== TELEMETRY_CONTRACT_VERSION) {
    throw new Error("telemetry_stream_contract_invalid");
  }
  if (!observation || typeof observation !== "object" || Array.isArray(observation)) {
    throw new Error("telemetry_observation_invalid");
  }
  if (observation.manifestMembership === true || observation.certified === true
    || observation.certificationStatus === TELEMETRY_STATUS.CERTIFIED_MANIFEST) {
    throw new Error("telemetry_cannot_assert_manifest_membership");
  }
  if (!observation.id || !observation.source
    || !["observation", "forecast"].includes(observation.kind)) {
    throw new Error("telemetry_observation_identity_missing");
  }
  const validTime = observation.kind === "forecast"
    ? observation.validAt && validIso(observation.validAt) && observation.modelId
    : validIso(observation.observedAt);
  if (!validTime) throw new Error("telemetry_observation_time_invalid");
  const key = item => [item.kind, item.source, item.id, item.observedAt || item.validAt].join("|");
  const previous = stream.observations.find(item => key(item) === key(observation));
  if (previous) {
    if (JSON.stringify(previous) !== JSON.stringify(observation)) {
      throw new Error("telemetry_observation_identity_collision");
    }
    return stream;
  }
  const record = Object.freeze({ ...observation });
  const bound = Number.isInteger(maxCount) && maxCount > 0 ? maxCount : 500;
  return Object.freeze({
    ...stream,
    observations: Object.freeze([...stream.observations, record].slice(-bound)),
  });
}

/** New canonical publication, never a client mutation, changes certified truth. */
export function canAdoptNewPublication(previous, next) {
  const a = previous?.identity;
  const b = next?.identity;
  return !!a && !!b
    && a.tenantId === b.tenantId && a.farmId === b.farmId && a.plotId === b.plotId
    && !!b.snapshotId && b.snapshotId !== a.snapshotId
    && !!b.publicationReceiptHash && b.publicationReceiptHash !== a.publicationReceiptHash
    && validIso(b.evidenceCutoffAt) && validIso(a.evidenceCutoffAt)
    && isoMillis(b.evidenceCutoffAt) >= isoMillis(a.evidenceCutoffAt);
}
