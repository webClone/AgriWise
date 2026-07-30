export const SOURCE_POLICIES = Object.freeze([
  "satellite",
  "experimental",
  "asmae_diagnostic",
  "hybrid",
]);

export function normalizeSourcePolicy(value, fallback = "satellite") {
  if (SOURCE_POLICIES.includes(value)) return value;
  return SOURCE_POLICIES.includes(fallback) ? fallback : "satellite";
}

function normalizedIntensity(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(2) : "0.40";
}

export function buildLayer10RequestIdentity({
  sequence,
  plotId,
  sourcePolicy,
  visualIntensity,
  experimental1m,
}) {
  return [
    "request:" + (Number(sequence) || 0),
    "plot:" + String(plotId || ""),
    "policy:" + normalizeSourcePolicy(sourcePolicy),
    "intensity:" + normalizedIntensity(visualIntensity),
    "experimental:" + (experimental1m === true ? "1" : "0"),
  ].join("|");
}

export function buildRenderViewIdentity({
  publicationId,
  plotId,
  sourcePolicy,
  mode,
  surfaceType,
  overlaySurfaceType,
  overlayEnabled,
}) {
  return [
    "publication:" + String(publicationId || "unpublished"),
    "plot:" + String(plotId || ""),
    "policy:" + normalizeSourcePolicy(sourcePolicy),
    "mode:" + String(mode || "canopy"),
    "base:" + String(surfaceType || "none"),
    "overlay:" + (overlayEnabled === true ? String(overlaySurfaceType || "none") : "off"),
  ].join("|");
}

export function shouldRetainLastKnownGood(previous, candidate, plotId) {
  return Array.isArray(candidate?.surfaces)
    && candidate.surfaces.length === 0
    && previous?.plot_id === plotId
    && Array.isArray(previous?.surfaces)
    && previous.surfaces.length > 0;
}

export function isLatestLayer10Request(activeSequence, candidateSequence, aborted = false) {
  return aborted !== true
    && Number(activeSequence) === Number(candidateSequence);
}

function materializationSignature(materialization) {
  const receipt = materialization?.receipt;
  return JSON.stringify({
    status: materialization?.status || null,
    surfaceType: materialization?.surfaceType || null,
    policy: materialization?.policy || null,
    mode: materialization?.mode || null,
    role: materialization?.role || null,
    reason: materialization?.reason || null,
    layerId: materialization?.layerId || null,
    gridBounds: materialization?.gridBounds || null,
    gridWidth: materialization?.gridWidth ?? null,
    gridHeight: materialization?.gridHeight ?? null,
    receipt: receipt ? {
      publicationId: receipt.publicationId || null,
      sourceId: receipt.sourceId || null,
      layerId: receipt.layerId || null,
      renderKind: receipt.renderKind || null,
      mapInstanceId: receipt.mapInstanceId || null,
    } : null,
  });
}

export function browserRenderReceiptSignature(receipt) {
  if (!receipt) return "none";
  return JSON.stringify({
    viewIdentity: receipt.viewIdentity || null,
    base: materializationSignature(receipt.baseMaterialization),
    overlay: materializationSignature(receipt.overlayMaterialization),
  });
}
