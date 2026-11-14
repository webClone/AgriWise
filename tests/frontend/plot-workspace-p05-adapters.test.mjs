import test from "node:test";
import assert from "node:assert/strict";
import {
  WORKSPACE_FEATURE_CONTRACT_VERSION,
  createWorkspaceFeatureEnvelope,
  validateWorkspaceFeatureEnvelope,
} from "../../src/lib/agribrain/workspace-feature-envelope.mjs";

test("P05.01: Feature Envelope adheres to versioned contract schema", () => {
  const envelope = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "probe-alpha-15",
    source_version: "2026-03-01T00:00:00Z",
    owner_scope: {
      tenant_id: "tenant-algiers-1",
      farm_id: "farm-mitidja-1",
      plot_id: "plot-citrus-a",
    },
    latitude: 36.509081,
    longitude: 2.659269,
    depth_cm: 15.0,
    location_source: "REGISTERED_HARDWARE",
    epistemic_class: "REGISTERED_GROUND_TRUTH",
    properties: {
      deviceId: "sensor_probe_alpha_15cm",
      vendor: "Sentek Drill & Drop",
      type: "MOISTURE",
      battery: 94,
    },
  });

  assert.equal(envelope.contract_version, WORKSPACE_FEATURE_CONTRACT_VERSION);
  assert.equal(envelope.envelope_id, "SENSOR:probe-alpha-15:2026-03-01T00:00:00Z");
  assert.equal(envelope.entity_kind, "SENSOR");
  assert.equal(envelope.entity_id, "probe-alpha-15");
  assert.equal(envelope.owner_scope.tenant_id, "tenant-algiers-1");
  assert.equal(envelope.owner_scope.plot_id, "plot-citrus-a");
  assert.equal(envelope.spatial_support.has_location, true);
  assert.equal(envelope.spatial_support.depth_cm, 15.0);
  assert.equal(envelope.geometry?.type, "Point");
  assert.deepEqual(envelope.geometry?.coordinates, [2.659269, 36.509081]); // GeoJSON [lng, lat]
  assert.equal(envelope.display_eligibility.eligible_for_map_pin, true);
  assert.equal(envelope.display_eligibility.eligible_for_catalog, true);
  assert.ok(envelope.provenance.record_digest);
  assert.equal(envelope.provenance.record_digest.length, 64); // SHA-256 hex
});

test("P05-G01: Feature Envelope fails validation on foreign tenant or plot scope mismatch", () => {
  const envelope = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "probe-beta-10",
    owner_scope: {
      tenant_id: "tenant-legitimate",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: 36.50785,
    longitude: 2.66015,
  });

  // Valid when matching
  const matchingValidation = validateWorkspaceFeatureEnvelope(envelope, {
    tenant_id: "tenant-legitimate",
    plot_id: "plot-1",
  });
  assert.equal(matchingValidation.valid, true);

  // Fails closed on foreign tenant
  const foreignTenantValidation = validateWorkspaceFeatureEnvelope(envelope, {
    tenant_id: "tenant-attacker",
    plot_id: "plot-1",
  });
  assert.equal(foreignTenantValidation.valid, false);
  assert.ok(foreignTenantValidation.errors.some((e) => e.includes("tenant_id mismatch")));

  // Fails closed on foreign plot
  const foreignPlotValidation = validateWorkspaceFeatureEnvelope(envelope, {
    tenant_id: "tenant-legitimate",
    plot_id: "plot-foreign",
  });
  assert.equal(foreignPlotValidation.valid, false);
  assert.ok(foreignPlotValidation.errors.some((e) => e.includes("plot_id mismatch")));
});

test("P05-G02: Rejects plot centroid substitution for registered sensor pin coordinates", () => {
  const envelopeWithCentroid = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "sensor-unlocated",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: 36.5667,
    longitude: 2.9167,
    is_centroid_substitute: true, // Attempted centroid substitute
  });

  assert.equal(envelopeWithCentroid.spatial_support.has_location, false);
  assert.equal(envelopeWithCentroid.geometry, null);
  assert.equal(envelopeWithCentroid.display_eligibility.eligible_for_map_pin, false);
  assert.equal(envelopeWithCentroid.display_eligibility.eligible_for_catalog, true);
  assert.equal(
    envelopeWithCentroid.display_eligibility.ineligibility_reason,
    "CENTROID_SUBSTITUTE_FORBIDDEN"
  );
});

test("P05-G08: Unlocated sensors remain visible in catalog without generating fake map pins", () => {
  const unlocatedSensor = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "sensor-no-gps-probe",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: null,
    longitude: null,
    properties: {
      deviceId: "ESP32-SOIL-01",
      vendor: "Generic Modbus",
    },
  });

  assert.equal(unlocatedSensor.spatial_support.has_location, false);
  assert.equal(unlocatedSensor.geometry, null);
  assert.equal(unlocatedSensor.display_eligibility.eligible_for_map_pin, false);
  assert.equal(unlocatedSensor.display_eligibility.eligible_for_catalog, true);
  assert.equal(
    unlocatedSensor.display_eligibility.ineligibility_reason,
    "LOCATION_UNREGISTERED"
  );

  const validation = validateWorkspaceFeatureEnvelope(unlocatedSensor, {
    tenantId: "tenant-1",
    plotId: "plot-1",
  });
  assert.equal(validation.valid, true);
});

test("P05.10: Rejects non-finite (NaN, Infinity) and out-of-bounds WGS84 coordinates", () => {
  // NaN coordinates fail closed to unlocated
  const nanEnvelope = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "sensor-nan",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: NaN,
    longitude: 2.65,
  });
  assert.equal(nanEnvelope.spatial_support.has_location, false);
  assert.equal(nanEnvelope.display_eligibility.eligible_for_map_pin, false);

  // Out of bounds latitude (> 90) fails closed
  const outOfBoundsEnvelope = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "sensor-oob",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: 91.5,
    longitude: 2.65,
  });
  assert.equal(outOfBoundsEnvelope.spatial_support.has_location, false);
  assert.equal(outOfBoundsEnvelope.display_eligibility.eligible_for_map_pin, false);
});
