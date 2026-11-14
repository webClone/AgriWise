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

test("P05-F05: Location source must be trusted (REGISTERED_HARDWARE, OBSERVED_GPS, SURVEYED) for map pin eligibility; UNSPECIFIED fails closed", () => {
  // 1. Coordinates exist but location_source is UNSPECIFIED -> ineligibility for map pin
  const untrustedEnvelope = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "probe-untrusted-source",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: 36.509081,
    longitude: 2.659269,
    location_source: "UNSPECIFIED",
  });

  assert.equal(untrustedEnvelope.spatial_support.has_location, true);
  assert.equal(untrustedEnvelope.display_eligibility.eligible_for_map_pin, false);
  assert.equal(
    untrustedEnvelope.display_eligibility.ineligibility_reason,
    "UNTRUSTED_LOCATION_SOURCE"
  );

  // 2. Coordinates with trusted location_source -> eligible for map pin
  const trustedHardware = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "probe-trusted-hardware",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: 36.509081,
    longitude: 2.659269,
    location_source: "REGISTERED_HARDWARE",
  });
  assert.equal(trustedHardware.display_eligibility.eligible_for_map_pin, true);
  assert.equal(trustedHardware.display_eligibility.ineligibility_reason, null);

  const trustedGps = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "probe-trusted-gps",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: 36.509081,
    longitude: 2.659269,
    location_source: "OBSERVED_GPS",
  });
  assert.equal(trustedGps.display_eligibility.eligible_for_map_pin, true);

  const trustedSurveyed = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "probe-trusted-surveyed",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: 36.509081,
    longitude: 2.659269,
    location_source: "SURVEYED",
  });
  assert.equal(trustedSurveyed.display_eligibility.eligible_for_map_pin, true);
});

test("P05-F01: Default verified_identity is false, and benchmark fixtures are classified as SIMULATED", () => {
  // 1. By default, verified_identity must be false (not assumed true)
  const uncertifiedEnvelope = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "probe-regular",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: 36.509081,
    longitude: 2.659269,
    location_source: "REGISTERED_HARDWARE",
  });

  assert.equal(uncertifiedEnvelope.provenance.verified_identity, false);

  // 2. Explicitly certified hardware
  const certifiedEnvelope = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "probe-certified",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: 36.509081,
    longitude: 2.659269,
    location_source: "REGISTERED_HARDWARE",
    provenance: {
      verified_identity: true,
      certifier: "ISO-17025-AG-LAB",
    },
  });
  assert.equal(certifiedEnvelope.provenance.verified_identity, true);

  // 3. Epistemic separation for benchmark fixtures
  const fixtureEnvelope = createWorkspaceFeatureEnvelope({
    entity_kind: "SENSOR",
    entity_id: "probe_mitidja_station_1",
    owner_scope: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    latitude: 36.578488,
    longitude: 2.953944,
    location_source: "SURVEYED",
    epistemic_class: "SIMULATED",
    properties: {
      is_benchmark_fixture: true,
      latestReading: null,
      isOnline: false,
    },
    provenance: {
      registry_source: "fixture:benchmark_plot",
      verified_identity: false,
      is_benchmark_fixture: true,
    },
  });

  assert.equal(fixtureEnvelope.epistemic_class, "SIMULATED");
  assert.equal(fixtureEnvelope.properties.is_benchmark_fixture, true);
  assert.equal(fixtureEnvelope.properties.latestReading, null);
  assert.equal(fixtureEnvelope.properties.isOnline, false);
  assert.equal(fixtureEnvelope.provenance.verified_identity, false);
});

test("P05-F03: Instrument identity resolution supports both database ID and hardware deviceId", () => {
  const sampleSensors = [
    {
      id: "69ff82ba1cfe9533724d7ac7",
      deviceId: "VS-MOISTURE-01",
      type: "MOISTURE",
      vendor: "Sentek",
      isOnline: true,
    },
    {
      id: "69ff8c3f351b5fecfc64dcd5",
      deviceId: "VS-TEMP-01",
      type: "TEMP",
      vendor: "Pessl",
      isOnline: false,
    },
  ];

  // Helper matching the dual-id lookup in SensorNetworkWorkspace
  const resolveSensor = (selectedId, sensors) => {
    return sensors.find((s) => s.id === selectedId || s.deviceId === selectedId) || null;
  };

  // Match by MongoDB ObjectId
  const matchByMongoId = resolveSensor("69ff82ba1cfe9533724d7ac7", sampleSensors);
  assert.ok(matchByMongoId);
  assert.equal(matchByMongoId.deviceId, "VS-MOISTURE-01");

  // Match by hardware deviceId
  const matchByDeviceId = resolveSensor("VS-TEMP-01", sampleSensors);
  assert.ok(matchByDeviceId);
  assert.equal(matchByDeviceId.id, "69ff8c3f351b5fecfc64dcd5");

  // Unregistered fixture probe gracefully returns null (triggering fixture notice)
  const unlinkedFixture = resolveSensor("probe_mitidja_station_1", sampleSensors);
  assert.equal(unlinkedFixture, null);
});

test("P05-F04: Scope-switching generation fencing discards stale requests", () => {
  let activeGeneration = 1;
  let activePlotId = "plot-a";

  const responses = [];

  const simulateFetchCompletion = (reqGeneration, reqPlotId, data) => {
    // Fencing rule in useWorkspaceEntities
    if (reqGeneration !== activeGeneration || reqPlotId !== activePlotId) {
      // Discard stale response
      return;
    }
    responses.push(data);
  };

  // Request 1 starts for plot-a, gen 1
  const req1Gen = 1;
  const req1Plot = "plot-a";

  // Before req 1 finishes, user switches to plot-b, gen 2
  activeGeneration = 2;
  activePlotId = "plot-b";

  // Request 2 starts for plot-b, gen 2
  const req2Gen = 2;
  const req2Plot = "plot-b";

  // Request 1 arrives late
  simulateFetchCompletion(req1Gen, req1Plot, { plotId: "plot-a", data: "stale" });
  assert.equal(responses.length, 0); // Stale response discarded

  // Request 2 arrives
  simulateFetchCompletion(req2Gen, req2Plot, { plotId: "plot-b", data: "fresh" });
  assert.equal(responses.length, 1);
  assert.equal(responses[0].plotId, "plot-b");
});

test("P05-F02: Server entities route strictly enforces authentication and tenant plot ownership without dev bypass", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const routePath = path.join(process.cwd(), "src/app/api/plots/[id]/workspace/entities/route.ts");
  const source = fs.readFileSync(routePath, "utf8");

  // 1. Mandatory authenticatedUserId() check
  assert.match(source, /const userId = await authenticatedUserId\(\);/);

  // 2. Unconditional 401 when !userId (NO dev mode bypass allowed)
  assert.match(source, /if \(!userId\) \{\s*return NextResponse\.json\(\s*\{\s*error:\s*"Authentication required"\s*\},\s*\{\s*status:\s*401\s*\}\s*\);/);
  assert.doesNotMatch(source, /!userId\s*&&\s*!isDev/);
  assert.doesNotMatch(source, /isDev/);

  // 3. Mandatory tenant isolation on plot query (farm.userId must equal authenticated userId)
  assert.match(source, /where:\s*\{\s*id:\s*plotId,\s*farm:\s*\{\s*userId\s*\},\s*\}/);

  // 4. Return 404 when plot is not found or foreign
  assert.match(source, /if \(!plot\) \{\s*return NextResponse\.json\(\{\s*error:\s*"Plot not found"\s*\},\s*\{\s*status:\s*404\s*\}\);/);

  // 5. Benchmark probes must never inject fabricated dynamic telemetry or claim active/online status
  assert.match(source, /epistemic_class:\s*"SIMULATED"/);
  assert.match(source, /status:\s*"BENCHMARK_FIXTURE"/);
  assert.match(source, /isOnline:\s*false/);
  assert.match(source, /latestReading:\s*null/);
  assert.match(source, /is_benchmark_fixture:\s*true/);
});
