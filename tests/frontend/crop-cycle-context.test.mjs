import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  buildCanonicalCropCycleContextV2,
  canonicalScientificHash,
} from "../../src/lib/agribrain/crop-cycle-context.mjs";

function buildInput(refs = ["task:b", "input:a", "task:b"]) {
  return {
    plot_namespace: {
      tenant_id: "tenant-1",
      farm_id: "farm-1",
      plot_id: "plot-1",
    },
    crop_cycle_id: "cycle-1",
    geometry_version: "sha256:geometry-1",
    effective_at: "2026-06-02T12:30:00.000Z",
    declared_crop_code: "Tomato",
    declared_crop_authority: "FARMER_CONFIRMED",
    declared_crop_at: "2026-06-02T12:00:00.000Z",
    declared_crop_source: "authenticated_farmer_crop_identity",
    variety: "Roma",
    irrigation_type: "DRIP",
    plant_date: {
      status: "confirmed",
      source: "crop_cycle_registry",
      confidence: 1,
      nominal: "2026-06-01T00:00:00.000Z",
      range_start: "2026-06-01T00:00:00.000Z",
      range_end: "2026-06-01T00:00:00.000Z",
    },
    harvest_dates: {
      expected: "2026-09-15T00:00:00.000Z",
      actual: null,
    },
    administrative_status: "GROWING",
    management_event_refs: refs,
  };
}

test("crop-cycle V2 is deeply frozen and hash-stable", () => {
  const first = buildCanonicalCropCycleContextV2(buildInput());
  const reordered = buildCanonicalCropCycleContextV2(
    buildInput(["input:a", "task:b"]),
  );

  assert.equal(first.content_hash, reordered.content_hash);
  assert.equal(
    first.content_hash,
    "7c3c905f3ff6139d1ff9c3c23f6aa7fb4560e95da86fb7f67201e26ab982d8b3",
  );
  assert.equal(first.declared_crop_code, "tomato");
  assert.equal(first.declared_crop_authority, "FARMER_CONFIRMED");
  assert.equal(first.declared_crop_at, "2026-06-02T12:00:00.000Z");
  assert.equal(
    first.declared_crop_source,
    "authenticated_farmer_crop_identity",
  );
  assert.equal(first.effective_at, "2026-06-02T12:30:00.000Z");
  assert.equal(first.irrigation_type, "drip");
  assert.equal(first.plant_date, "2026-06-01T00:00:00.000Z");
  assert.equal(first.planting_date, first.plant_date);
  assert.equal(first.plant_date_status, "confirmed");
  assert.equal(first.plant_date_min, first.plant_date);
  assert.equal(first.plant_date_max, first.plant_date);
  assert.deepEqual(first.management_event_refs, ["input:a", "task:b"]);
  assert.equal(first.phenology_from_administrative_status_allowed, false);
  assert.equal(
    first.administrative_status_role,
    "workflow_only_not_phenology_evidence",
  );
  assert.equal(Object.isFrozen(first), true);
  assert.equal(Object.isFrozen(first.harvest_dates), true);
  assert.equal(Object.isFrozen(first.management_event_refs), true);
  assert.throws(() => first.management_event_refs.push("task:c"), TypeError);

  const { content_hash: _ignored, ...scientificPayload } = first;
  assert.equal(first.content_hash, canonicalScientificHash(scientificPayload));
});

test("crop-cycle V2 enforces date status and declaration taxonomies", () => {
  for (const authority of ["FARMER_CONFIRMED", "OFFICIAL_PARCEL_LABEL"]) {
    const value = buildCanonicalCropCycleContextV2({
      ...buildInput(),
      declared_crop_authority: authority,
    });
    assert.equal(value.declared_crop_authority, authority);
  }

  assert.throws(
    () => buildCanonicalCropCycleContextV2({
      ...buildInput(),
      plant_date: { ...buildInput().plant_date, status: "registry_declared" },
    }),
    /plant_date_status/,
  );
  assert.throws(
    () => buildCanonicalCropCycleContextV2({
      ...buildInput(),
      plant_date: "2026-06-01T00:00:00.000Z",
      planting_date: "2026-06-02T00:00:00.000Z",
      plant_date_status: "confirmed",
    }),
    /aliases disagree/,
  );
});

test("crop-cycle V2 rejects administrative status-to-phenology coercion", () => {
  assert.throws(
    () => buildCanonicalCropCycleContextV2({
      ...buildInput(),
      stage: "FLOWERING",
    }),
    /cannot be coerced into phenology/,
  );
  assert.throws(
    () => buildCanonicalCropCycleContextV2({
      ...buildInput(),
      phenology_stage: "FLOWERING",
    }),
    /cannot be coerced into phenology/,
  );
});

test("Next run route transports full cycle context without status as stage", async () => {
  const source = await readFile(
    new URL("../../src/app/api/agribrain/run/route.ts", import.meta.url),
    "utf8",
  );
  assert.match(source, /buildCanonicalCropCycleContextV2\(/);
  assert.match(source, /context\.crop_cycle_context = cropCycleContext/);
  assert.match(source, /management_event_refs: managementEventRefs/);
  assert.match(source, /effective_at: activeCycle\.updatedAt\.toISOString\(\)/);
  assert.match(source, /irrigation_type: irrigationType/);
  assert.match(source, /declared_crop_authority: declaredCropAuthority/);
  assert.match(source, /declared_crop_at: declaredCropAt/);
  assert.match(source, /declared_crop_source: declaredCropSource/);
  assert.match(source, /activeCycle\.declaredCropAt\?\.toISOString\(\) \|\| null/);
  assert.doesNotMatch(source, /activeCycle\.declaredCropAt \|\| activeCycle\.updatedAt/);
  assert.match(source, /activeCycle\.declaredCropAuthority \|\| "REGISTRY_DECLARED"/);
  assert.match(source, /status: plantDateStatus/);
  assert.match(source, /activeCycle\.plantDateStatus \|\| "unknown"/);
  assert.match(source, /expected: activeCycle\.expectedHarvest/);
  assert.doesNotMatch(source, /context\.stage\s*=\s*activeCycle\.status/);
});

test("what-if sandbox keeps administrative crop status out of phenology stage", async () => {
  const source = await readFile(
    new URL("../../src/app/api/agribrain/sandbox/route.ts", import.meta.url),
    "utf8",
  );
  assert.match(source, /administrative_status:\s*cycle\.status/);
  assert.match(
    source,
    /administrative_status_role:\s*"workflow_only_not_phenology_evidence"/,
  );
  assert.doesNotMatch(source, /context\.stage\s*=\s*.*\.status/);
});

test("cycle creation leaves planting date unknown unless the farmer enters it", async () => {
  const modalSource = await readFile(
    new URL("../../src/components/farm/StartCycleModal.tsx", import.meta.url),
    "utf8",
  );
  const routeSource = await readFile(
    new URL("../../src/app/api/plots/[id]/cycle/route.ts", import.meta.url),
    "utf8",
  );
  assert.match(modalSource, /startDate:\s*""/);
  assert.doesNotMatch(modalSource, /startDate:\s*new Date\(/);
  assert.match(routeSource, /plantDateStatus: start \? "confirmed" : "unknown"/);
  assert.match(routeSource, /declaredCropAuthority: "REGISTRY_DECLARED"/);
  assert.match(routeSource, /declaredCropAt: \{ "\$date": now\.toISOString\(\) \}/);
  assert.match(routeSource, /declaredCropSource: "crop_cycle_form"/);
  assert.match(routeSource, /if \(start\) \{/);
  assert.match(routeSource, /for \(const stage of aiPlan\)/);
  assert.doesNotMatch(routeSource, /if \(!cropName \|\| !startDate\)/);
});
