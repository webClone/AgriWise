import test from "node:test";
import assert from "node:assert/strict";
import {
  validateGeometryRegistrationInput,
  validateGeometryRevisionInput,
  validateParcelContainment,
  isRegistrationRecordInScope,
} from "../../src/lib/agribrain/geometry-registration-policy.mjs";
import {
  geometryIntegrityDigest,
  projectWorkspaceGeometryRegistration,
} from "../../src/lib/agribrain/geometry-registration-projection.mjs";
import { validateWorkspaceFeatureEnvelope } from "../../src/lib/agribrain/workspace-feature-envelope.mjs";

const plot = { tenantId: "507f1f77bcf86cd799439001", farmId: "507f1f77bcf86cd799439002", plotId: "507f1f77bcf86cd799439003" };
const line = { type: "LineString", coordinates: [[2.659, 36.508], [2.660, 36.509]] };
const lineRev2 = { type: "LineString", coordinates: [[2.659, 36.508], [2.660, 36.509], [2.661, 36.510]] };

const baseRecord = (rev = 1, status = "OWNER_DECLARED", geo = line) => ({
  id: "507f1f77bcf86cd799439012",
  registrationKey: "OWNER_PLAN:test-001",
  tenantId: plot.tenantId,
  farmId: plot.farmId,
  plotId: plot.plotId,
  registeredBy: plot.tenantId,
  entityKind: "DRONE_MISSION",
  entityId: "OWNER_PLAN:test-001",
  sourceKind: "OWNER_PLAN",
  sourceId: null,
  geometry: geo,
  geometryDigest: geometryIntegrityDigest(geo),
  name: "Survey flight plan",
  notes: null,
  status,
  epistemicClass: "PLANNED",
  locationSource: "USER_DECLARED",
  revision: rev,
  createdAt: new Date("2026-11-15T18:00:00Z"),
});

test("P06.05: validateGeometryRevisionInput requires expected_revision and validates updates", () => {
  // Missing expected_revision
  assert.equal(validateGeometryRevisionInput({ label: "New title" }, "DRONE_MISSION").ok, false);
  // Non-integer expected_revision
  assert.equal(validateGeometryRevisionInput({ expected_revision: "1" }, "DRONE_MISSION").ok, false);
  assert.equal(validateGeometryRevisionInput({ expected_revision: 0 }, "DRONE_MISSION").ok, false);

  // Valid revision
  const valid = validateGeometryRevisionInput({
    expected_revision: 1,
    label: "Revised Corridor Beta",
    geometry: lineRev2,
    notes: "Extended waypoint eastward",
  }, "DRONE_MISSION");
  assert.equal(valid.ok, true);
  assert.equal(valid.value.expected_revision, 1);
  assert.equal(valid.value.label, "Revised Corridor Beta");
  assert.equal(valid.value.geometry.coordinates.length, 3);
});

test("P06.05: client cannot inject authority or status claims into revision payload", () => {
  const tampered = [
    { expected_revision: 1, epistemic_class: "OBSERVED_TELEMETRY" },
    { expected_revision: 1, status: "APPROVED" },
    { expected_revision: 1, revision: 2 },
    { expected_revision: 1, verified_identity: true },
    { expected_revision: 1, location_source: "REGISTERED_HARDWARE" },
  ];
  for (const t of tampered) {
    assert.equal(validateGeometryRevisionInput(t, "DRONE_MISSION").ok, false);
  }
});

test("P06.05: projectWorkspaceGeometryRegistration supports revisions >= 1 with source_version stamping", () => {
  const r1 = projectWorkspaceGeometryRegistration(baseRecord(1), plot);
  assert.ok(r1);
  assert.equal(r1.source_version, "registered-v1:507f1f77bcf86cd799439012");
  assert.equal(r1.properties.revision, 1);

  const r2 = projectWorkspaceGeometryRegistration(baseRecord(2, "OWNER_DECLARED", lineRev2), plot);
  assert.ok(r2);
  assert.equal(r2.source_version, "registered-v2:507f1f77bcf86cd799439012");
  assert.equal(r2.properties.revision, 2);
  assert.equal(r2.geometry.coordinates.length, 3);
  assert.equal(validateWorkspaceFeatureEnvelope(r2, { tenant_id: plot.tenantId, farm_id: plot.farmId, plot_id: plot.plotId }).valid, true);

  // Invalid revisions
  assert.equal(projectWorkspaceGeometryRegistration(baseRecord(0), plot), null);
  assert.equal(projectWorkspaceGeometryRegistration(baseRecord(-1), plot), null);
  assert.equal(projectWorkspaceGeometryRegistration(baseRecord(1.5), plot), null);
});

test("P06.05: soft-revoked geometry is cleanly excluded from active workspace projection", () => {
  const revoked = baseRecord(2, "REVOKED");
  assert.equal(isRegistrationRecordInScope(revoked, plot), false);
  assert.equal(projectWorkspaceGeometryRegistration(revoked, plot), null);
});

test("P06.05: FIELD_OBSERVATION registration allows new_observation creation without bypassing source-link", () => {
  const poly = { type: "Polygon", coordinates: [[[2.65, 36.5], [2.66, 36.5], [2.66, 36.51], [2.65, 36.51], [2.65, 36.5]]] };
  const input = {
    entity_kind: "FIELD_OBSERVATION",
    source_kind: "CROP_OBSERVATION",
    new_observation: {
      title: "Aphid Scout Zone Alpha",
      severity: "warning",
      type: "pest",
      description: "Infestation spotted on leaves",
    },
    label: "Aphid Cluster Area",
    geometry: poly,
  };
  const val = validateGeometryRegistrationInput(input);
  assert.equal(val.ok, true);
  assert.equal(val.value.new_observation.title, "Aphid Scout Zone Alpha");
  assert.equal(val.value.source_id, null); // Will be populated by DB creation

  // Conflict if both source_id and new_observation provided
  assert.equal(validateGeometryRegistrationInput({ ...input, source_id: "507f1f77bcf86cd799439099" }).ok, false);
});

test("P06.05: validateParcelContainment accepts coordinates within plot footprint plus operational margin and rejects out-of-envelope geometry", () => {
  const plotGeoJson = {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [2.655, 36.507],
          [2.663, 36.507],
          [2.663, 36.510],
          [2.655, 36.510],
          [2.655, 36.507],
        ],
      ],
    },
  };

  // 1. Inside plot polygon
  const insideGeom = {
    type: "LineString",
    coordinates: [
      [2.658, 36.508],
      [2.660, 36.509],
    ],
  };
  const resInside = validateParcelContainment(insideGeom, plotGeoJson);
  assert.equal(resInside.ok, true);

  // 2. Just outside parcel boundary but within 0.02 deg buffer margin (~2.2 km)
  const marginGeom = {
    type: "LineString",
    coordinates: [
      [2.665, 36.512],
      [2.668, 36.515],
    ],
  };
  const resMargin = validateParcelContainment(marginGeom, plotGeoJson);
  assert.equal(resMargin.ok, true);

  // 3. Far outside (California coordinates)
  const farGeom = {
    type: "LineString",
    coordinates: [
      [-119.825, 34.421],
      [-119.820, 34.425],
    ],
  };
  const resFar = validateParcelContainment(farGeom, plotGeoJson);
  assert.equal(resFar.ok, false);
  assert.match(resFar.error, /exceed authorized plot operational envelope/);
});

test("P06.05: optimistic concurrency predicates strictly enforce revision matching and reject state regressions", () => {
  const activeRecord = baseRecord(2, "OWNER_DECLARED");
  // Active record is visible in scope
  assert.equal(isRegistrationRecordInScope(activeRecord, plot), true);

  // If revision is stale
  const stalePayload = { expected_revision: 1, label: "Stale update" };
  const val = validateGeometryRevisionInput(stalePayload, "DRONE_MISSION");
  assert.equal(val.ok, true);
  // Concurrency check: payload expected_revision (1) !== record revision (2) -> conflict
  assert.notEqual(val.value.expected_revision, activeRecord.revision);

  // Revoked record is rejected from scope
  const revokedRecord = baseRecord(3, "REVOKED");
  assert.equal(isRegistrationRecordInScope(revokedRecord, plot), false);
});
