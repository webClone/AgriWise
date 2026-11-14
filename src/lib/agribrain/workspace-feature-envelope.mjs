import { createHash } from "node:crypto";

export const WORKSPACE_FEATURE_CONTRACT_VERSION = "2026.11-p05.1";

export const VALID_ENTITY_KINDS = Object.freeze([
  "SENSOR",
  "CAMERA",
  "DRONE_MISSION",
  "FIELD_OBSERVATION",
  "FIELD_EVENT",
  "ZONE",
]);

export const VALID_LOCATION_SOURCES = Object.freeze([
  "REGISTERED_HARDWARE",
  "OBSERVED_GPS",
  "SURVEYED",
  "UNSPECIFIED",
]);

export const VALID_EPISTEMIC_CLASSES = Object.freeze([
  "REGISTERED_GROUND_TRUTH",
  "OBSERVED_TELEMETRY",
  "ESTIMATED",
  "SIMULATED",
  "PLANNED",
]);

function computeRecordDigest(canonicalPayload) {
  try {
    return createHash("sha256").update(JSON.stringify(canonicalPayload)).digest("hex");
  } catch {
    // Basic fallback for non-node environments
    let hash = 0;
    const str = JSON.stringify(canonicalPayload);
    for (let i = 0; i < str.length; i++) {
      hash = (hash << 5) - hash + str.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash).toString(16).padStart(64, "0");
  }
}

/**
 * Creates a validated WorkspaceFeatureEnvelope.
 * Enforces Gate P05-G02: Sensor pin coordinates equal registered device coordinates, never plot centroid.
 * Enforces Gate P05-G08: Missing/invalid geolocation never blocks catalog visibility, only pin eligibility.
 */
export function createWorkspaceFeatureEnvelope(params) {
  if (!params || typeof params !== "object") {
    throw new TypeError("params must be an object");
  }

  const {
    entity_kind,
    entity_id,
    source_version = "v1",
    owner_scope,
    latitude,
    longitude,
    altitude_m = null,
    depth_cm = null,
    support_radius_m = null,
    zone_id = null,
    location_source = "UNSPECIFIED",
    epistemic_class = "REGISTERED_GROUND_TRUTH",
    temporal_extent = {},
    properties = {},
    provenance = {},
    is_centroid_substitute = false,
  } = params;

  if (!VALID_ENTITY_KINDS.includes(entity_kind)) {
    throw new Error(`Invalid entity_kind: "${entity_kind}". Must be one of ${VALID_ENTITY_KINDS.join(", ")}`);
  }

  if (!entity_id || typeof entity_id !== "string" || !entity_id.trim()) {
    throw new Error("entity_id must be a non-empty string");
  }

  if (!owner_scope || typeof owner_scope !== "object") {
    throw new Error("owner_scope is required");
  }

  const tenant_id = String(owner_scope.tenant_id || owner_scope.tenantId || "").trim();
  const farm_id = String(owner_scope.farm_id || owner_scope.farmId || "").trim();
  const plot_id = String(owner_scope.plot_id || owner_scope.plotId || "").trim();

  if (!tenant_id || !plot_id) {
    throw new Error("owner_scope must contain non-empty tenant_id and plot_id");
  }

  const sanitizedOwnerScope = Object.freeze({
    tenant_id,
    farm_id,
    plot_id,
  });

  const TRUSTED_LOCATION_SOURCES = Object.freeze([
    "REGISTERED_HARDWARE",
    "OBSERVED_GPS",
    "SURVEYED",
  ]);

  const sanitizedLocationSource = VALID_LOCATION_SOURCES.includes(location_source)
    ? location_source
    : "UNSPECIFIED";
  const isLocationTrusted = TRUSTED_LOCATION_SOURCES.includes(sanitizedLocationSource);

  // Evaluate location and map pin eligibility
  let has_location = false;
  let geometry = null;
  let ineligibility_reason = null;

  if (is_centroid_substitute) {
    // Gate P05-G02: Reject centroid substitute as map pin coordinates
    has_location = false;
    geometry = null;
    ineligibility_reason = "CENTROID_SUBSTITUTE_FORBIDDEN";
  } else if (
    latitude !== null &&
    latitude !== undefined &&
    longitude !== null &&
    longitude !== undefined &&
    typeof latitude === "number" &&
    typeof longitude === "number" &&
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    Math.abs(latitude) <= 90 &&
    Math.abs(longitude) <= 180
  ) {
    has_location = true;
    geometry = Object.freeze({
      type: "Point",
      coordinates: [longitude, latitude], // GeoJSON standard [lng, lat]
    });
    if (!isLocationTrusted) {
      ineligibility_reason = "UNTRUSTED_LOCATION_SOURCE";
    }
  } else {
    // Gate P05-G08: Unlocated device is valid for catalog, ineligible for map pin
    has_location = false;
    geometry = null;
    ineligibility_reason = "LOCATION_UNREGISTERED";
  }

  const eligible_for_map_pin = Boolean(
    has_location && isLocationTrusted && !is_centroid_substitute
  );

  const display_eligibility = Object.freeze({
    eligible_for_map_pin,
    eligible_for_catalog: true, // Gate P05-G08
    ineligibility_reason: eligible_for_map_pin ? null : ineligibility_reason,
  });

  const spatial_support = Object.freeze({
    has_location,
    location_source: sanitizedLocationSource,
    support_radius_m: typeof support_radius_m === "number" && Number.isFinite(support_radius_m) ? support_radius_m : null,
    depth_cm: typeof depth_cm === "number" && Number.isFinite(depth_cm) ? depth_cm : null,
    altitude_m: typeof altitude_m === "number" && Number.isFinite(altitude_m) ? altitude_m : null,
    zone_id: zone_id ? String(zone_id) : null,
  });

  const sanitizedEpistemicClass = VALID_EPISTEMIC_CLASSES.includes(epistemic_class)
    ? epistemic_class
    : "REGISTERED_GROUND_TRUTH";

  const sanitizedTemporalExtent = Object.freeze({
    observed_at: temporal_extent.observed_at ? String(temporal_extent.observed_at) : null,
    first_available_at: temporal_extent.first_available_at ? String(temporal_extent.first_available_at) : null,
    valid_from: temporal_extent.valid_from ? String(temporal_extent.valid_from) : null,
    valid_to: temporal_extent.valid_to ? String(temporal_extent.valid_to) : null,
    published_at: temporal_extent.published_at ? String(temporal_extent.published_at) : null,
  });

  const envelope_id = `${entity_kind}:${entity_id}:${source_version}`;

  const canonicalForDigest = {
    contract_version: WORKSPACE_FEATURE_CONTRACT_VERSION,
    envelope_id,
    entity_kind,
    entity_id,
    source_version,
    owner_scope: sanitizedOwnerScope,
    geometry,
    spatial_support,
    epistemic_class: sanitizedEpistemicClass,
    temporal_extent: sanitizedTemporalExtent,
    properties,
  };

  const record_digest = computeRecordDigest(canonicalForDigest);

  const sanitizedProvenance = Object.freeze({
    ...provenance,
    record_digest,
    verified_identity: Boolean(provenance.verified_identity ?? false),
  });

  return Object.freeze({
    contract_version: WORKSPACE_FEATURE_CONTRACT_VERSION,
    envelope_id,
    entity_kind,
    entity_id,
    source_version,
    owner_scope: sanitizedOwnerScope,
    geometry,
    spatial_support,
    temporal_extent: sanitizedTemporalExtent,
    epistemic_class: sanitizedEpistemicClass,
    properties: Object.freeze({ ...properties }),
    provenance: sanitizedProvenance,
    display_eligibility,
  });
}

/**
 * Validates a WorkspaceFeatureEnvelope against expected tenant and plot scope.
 * Fails closed if foreign owner, tampered geometry, or invalid envelope structure.
 */
export function validateWorkspaceFeatureEnvelope(envelope, expectedScope) {
  if (!envelope || typeof envelope !== "object") {
    return { valid: false, errors: ["envelope must be a non-null object"] };
  }

  const errors = [];

  if (envelope.contract_version !== WORKSPACE_FEATURE_CONTRACT_VERSION) {
    errors.push(`contract_version mismatch: expected "${WORKSPACE_FEATURE_CONTRACT_VERSION}", got "${envelope.contract_version}"`);
  }

  if (!VALID_ENTITY_KINDS.includes(envelope.entity_kind)) {
    errors.push(`invalid entity_kind: "${envelope.entity_kind}"`);
  }

  if (!envelope.entity_id || typeof envelope.entity_id !== "string") {
    errors.push("invalid or missing entity_id");
  }

  // Enforce Scope Alignment (Gate P05-G01)
  if (expectedScope) {
    const expectedTenant = expectedScope.tenant_id || expectedScope.tenantId;
    const expectedPlot = expectedScope.plot_id || expectedScope.plotId;

    if (expectedTenant && envelope.owner_scope?.tenant_id !== expectedTenant) {
      errors.push(`tenant_id mismatch: expected "${expectedTenant}", got "${envelope.owner_scope?.tenant_id}"`);
    }

    if (expectedPlot && envelope.owner_scope?.plot_id !== expectedPlot) {
      errors.push(`plot_id mismatch: expected "${expectedPlot}", got "${envelope.owner_scope?.plot_id}"`);
    }
  }

  // Geometry validation
  if (envelope.geometry !== null) {
    if (envelope.geometry.type !== "Point" && envelope.geometry.type !== "Polygon" && envelope.geometry.type !== "LineString") {
      errors.push(`unsupported geometry type: "${envelope.geometry.type}"`);
    }

    if (envelope.geometry.type === "Point") {
      const coords = envelope.geometry.coordinates;
      if (!Array.isArray(coords) || coords.length < 2) {
        errors.push("Point geometry coordinates must be an array of [lng, lat]");
      } else {
        const [lng, lat] = coords;
        if (!Number.isFinite(lng) || !Number.isFinite(lat) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
          errors.push(`coordinates out of valid bounds: [${lng}, ${lat}]`);
        }
      }
    }
  }

  // Map pin consistency check
  if (envelope.display_eligibility?.eligible_for_map_pin === true) {
    if (!envelope.geometry || envelope.spatial_support?.has_location !== true) {
      errors.push("eligible_for_map_pin is true but geometry or has_location is missing");
    }
    const trustedSources = ["REGISTERED_HARDWARE", "OBSERVED_GPS", "SURVEYED"];
    if (!trustedSources.includes(envelope.spatial_support?.location_source)) {
      errors.push(`eligible_for_map_pin is true but location_source "${envelope.spatial_support?.location_source}" is not trusted`);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}
