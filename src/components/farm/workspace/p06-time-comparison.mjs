/**
 * P06 temporal context for selected P05 entities.
 * Chronology is not equivalent to signed historical admission or a raster sample.
 * Only the current scoped entity API record is used, never selection.metadata.
 */
function timestamp(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? new Date(ms).toISOString() : null;
}
function relativeToCutoff(observed, cutoff) {
  if (!observed || !cutoff) return "Unknown (missing timestamp)";
  const difference = Date.parse(observed) - Date.parse(cutoff);
  return difference === 0 ? "At cutoff" : difference < 0 ? "Before cutoff" : "After cutoff";
}
export function buildEntityTemporalComparison({workspace, entity}) {
  const empty = (status, guidance) => ({
    status, guidance, entityKind: null, entityId: null, epistemicClass: null,
    observedAt: null, firstAvailableAt: null, publishedAt: null,
    observationRelation: "Unknown (missing timestamp)",
    availabilityRelation: "Unknown (missing timestamp)",
    envelopeDigest: null, scientificReferenceQualified: false,
  });
  const selected = workspace?.selectedEntity;
  if (!selected?.id || !selected?.kind || selected.kind === "ZONE") {
    return empty("no_selection", "Select a mapped sensor, camera, mission or field observation.");
  }
  if (!entity) return empty("unavailable", "The selected entity is absent from the current plot's authenticated entity list.");
  const owner = entity.owner_scope || {};
  const scope = workspace?.plotScope || {};
  if (!workspace?.ownerScope?.tenantId ||
      owner.tenant_id !== workspace.ownerScope.tenantId ||
      !scope.farmId || owner.farm_id !== scope.farmId ||
      !scope.plotId || owner.plot_id !== scope.plotId ||
      entity.entity_kind !== selected.kind ||
      (entity.entity_id !== selected.id && entity.envelope_id !== selected.id) ||
      (selected.sourceSnapshotId && entity.source_version &&
       selected.sourceSnapshotId !== entity.source_version)) {
    return empty("scope_mismatch", "Entity identity, version, or owner scope does not match this workspace.");
  }
  const t = entity.temporal_extent || {};
  const observedAt = timestamp(t.observed_at);
  const firstAvailableAt = timestamp(t.first_available_at);
  const publishedAt = timestamp(t.published_at);
  const cutoff = timestamp(workspace?.clocks?.scientificAsOf);
  const epistemicClass = entity.epistemic_class || "UNCLASSIFIED";
  const fixture = entity.properties?.is_benchmark_fixture === true || epistemicClass === "SIMULATED";
  const planned = epistemicClass === "PLANNED";
  const scientificReferenceQualified = Boolean(
    workspace?.publication?.authorityStatus === "CERTIFIED" &&
    !workspace?.publication?.isStale &&
    workspace?.publication?.snapshotId && cutoff
  );
  const observationRelation = relativeToCutoff(observedAt, cutoff);
  const availabilityRelation = relativeToCutoff(firstAvailableAt, cutoff);
  let guidance;
  if (fixture) guidance = "DEMO FIXTURE: simulated or illustrative placement only; no real telemetry or historical admission is claimed.";
  else if (planned) guidance = "PLANNED: this entity is not proof of an executed or observed mission.";
  else if (!scientificReferenceQualified) guidance = "Scientific cutoff is not attached to a current certified publication. No cross-source scientific comparison is authorized.";
  else if (!observedAt) guidance = "No qualified observation timestamp is available for this entity.";
  else if (!firstAvailableAt) guidance = "Observation time is provided, but signed first-availability proof is not established by this envelope. No historical admission is inferred.";
  else if (observationRelation === "After cutoff" || availabilityRelation === "After cutoff") guidance = "Observation or availability falls after the scientific cutoff; do not backdate it into the scientific publication.";
  else guidance = "Times are chronologically compatible, but this UI has not verified the sensor receipt or historical admission. No scientific value comparison is implied.";
  return {
    status: "matched", guidance, entityKind: entity.entity_kind, entityId: entity.entity_id,
    epistemicClass, observedAt, firstAvailableAt, publishedAt,
    observationRelation, availabilityRelation,
    envelopeDigest: entity.provenance?.record_digest || null,
    scientificReferenceQualified,
  };
}
