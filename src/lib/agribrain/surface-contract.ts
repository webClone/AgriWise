export const SURFACES_SCHEMA_VERSION = "v925_bc10_24r5_phenology_authority_v2";
export const RENDER_AUTHORIZATION_VERSION = "v924_bc10_22r5_render_identity_v1";

export const PUBLICATION_STATUS = {
  VALID_NORMAL: "VALID_NORMAL",
  VALID_DEGRADED: "VALID_DEGRADED",
  INVALID_PUBLICATION: "INVALID_PUBLICATION",
  FAILED_PUBLICATION: "FAILED_PUBLICATION",
} as const;

export type SurfacePublicationStatus =
  (typeof PUBLICATION_STATUS)[keyof typeof PUBLICATION_STATUS];

export type PublicationInspection = {
  status: SurfacePublicationStatus;
  reason: string;
  declaredStatus: string;
  valid: boolean;
};

function nonEmptyRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(
    value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length > 0
  );
}

/**
 * Derive authority from the actual serialized envelope. The declared status
 * never participates in derivation, so it cannot authorize incomplete data.
 */
export function inspectSurfacePublication(payload: any): PublicationInspection {
  const declaredStatus = String(
    payload?.publication_status ?? payload?.provenance?.publication_status ?? ""
  );

  let status: SurfacePublicationStatus;
  let reason: string;
  const explicitState = String(payload?.status ?? "").toLowerCase();
  const layer10State = String(payload?.layer_results?.layer_10?.status ?? "").toLowerCase();

  if (!payload) {
    status = PUBLICATION_STATUS.FAILED_PUBLICATION;
    reason = "payload_missing";
  } else if (["failed", "error"].includes(explicitState) || ["failed", "error"].includes(layer10State)) {
    status = PUBLICATION_STATUS.FAILED_PUBLICATION;
    reason = "execution_failed";
  } else if (!Array.isArray(payload.surfaces)) {
    status = PUBLICATION_STATUS.INVALID_PUBLICATION;
    reason = "surfaces_not_a_sequence";
  } else {
    const hasSurfaces = payload.surfaces.length > 0;
    const rawDegradation = String(
      payload.degradation_mode ??
        payload.quality?.degradation_mode ??
        payload.provenance?.degradation ??
        ""
    );
    const degradation = rawDegradation.includes(".")
      ? rawDegradation.split(".").at(-1)!.toUpperCase()
      : rawDegradation.toUpperCase();
    const terminalNoData =
      !hasSurfaces &&
      (payload.placeholder_only === true ||
        explicitState === "degraded" ||
        ["DATA_GAP", "NO_SPATIAL", "DEGRADED"].includes(degradation) ||
        payload.provenance?.spatial_processing_short_circuited === true);

    const publicationId = payload.publication_id ?? payload.provenance?.publication_id ?? "";
    const publicationRunId =
      payload.publication_run_id ?? payload.provenance?.publication_run_id ?? "";
    const scientificRunId = payload.run_id ?? "";
    const schemaVersion =
      payload.schema_version ??
      payload.version ??
      payload.surface_schema_version ??
      payload.provenance?.surface_schema_version ??
      "";

    const invalid: string | null =
      !hasSurfaces && !terminalNoData
        ? "surface_inventory_empty"
        : payload.render_authorization_version !== RENDER_AUTHORIZATION_VERSION
          ? "render_authorization_version_invalid"
          : !nonEmptyRecord(payload.render_authorizations)
            ? "render_authorizations_missing"
            : !nonEmptyRecord(payload.asmae_proof)
              ? "asmae_proof_missing"
              : !nonEmptyRecord(payload.mode_display_state)
                ? "mode_display_state_missing"
              : !nonEmptyRecord(payload.source_policy_display_state)
                  ? "source_policy_display_state_missing"
                  : !nonEmptyRecord(payload.core_asmae_evidence_state ?? payload.asmae_evidence_state)
                    ? "core_asmae_evidence_state_missing"
                    : !nonEmptyRecord(payload.publication_surface_state)
                      ? "publication_surface_state_missing"
                  : !publicationId
                      ? "publication_id_missing"
                      : !publicationRunId || !scientificRunId
                        ? "publication_run_identity_missing"
                        : String(publicationRunId) !== String(scientificRunId)
                          ? "publication_run_identity_mismatch"
                          : schemaVersion !== SURFACES_SCHEMA_VERSION
                            ? "surface_schema_version_invalid"
                            : null;

    if (invalid) {
      status = PUBLICATION_STATUS.INVALID_PUBLICATION;
      reason = invalid;
    } else {
      const degraded =
        terminalNoData ||
        explicitState === "degraded" ||
        payload.placeholder_only === true ||
        !["", "NORMAL"].includes(degradation) ||
        payload.publication_demotion?.applied === true;
      status = degraded
        ? PUBLICATION_STATUS.VALID_DEGRADED
        : PUBLICATION_STATUS.VALID_NORMAL;
      reason = degraded
        ? "degraded_authoritative_envelope"
        : "normal_authoritative_envelope";
    }
  }

  const knownDeclared = Object.values(PUBLICATION_STATUS).includes(
    declaredStatus as SurfacePublicationStatus
  );
  const declarationMatches = knownDeclared && declaredStatus === status;
  const valid =
    declarationMatches &&
    (status === PUBLICATION_STATUS.VALID_NORMAL ||
      status === PUBLICATION_STATUS.VALID_DEGRADED);
  return {
    status,
    reason: declarationMatches
      ? reason
      : knownDeclared
        ? `publication_status_mismatch:${declaredStatus}!=${status}:${reason}`
        : "publication_status_missing_or_unknown",
    declaredStatus,
    valid,
  };
}
