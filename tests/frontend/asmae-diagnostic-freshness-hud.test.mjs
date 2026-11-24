import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

const read = name => readFileSync(path.join(process.cwd(), name), "utf8");
const route = read("src/app/api/agribrain/surfaces/latest/route.ts");
const statusHud = read("src/components/farm/workspace/WorkspaceScientificStatus.tsx");
const inspector = read("src/components/farm/workspace/WorkspaceContextInspector.tsx");

test("Route separates publication freshness from observation freshness and surfaces diagnostic fields", () => {
  assert.match(route, /publication_authority/);
  assert.match(route, /evidence_acquisition_date/);
  assert.match(route, /admitted_diagnostic/);
  assert.match(route, /effective_resolution/);
  assert.match(route, /calibration_status/);
  assert.match(route, /supported_layers/);
  assert.match(route, /unsupported_layers/);
  assert.match(route, /raster_availability/);
});

test("WorkspaceScientificStatus renders diagnostic authority and evidence freshness", () => {
  assert.match(statusHud, /Admitted diagnostic publication/);
  assert.match(statusHud, /DIAGNOSTIC_ONLY/);
  assert.match(statusHud, /Diagnostic only \(Numerical authority withheld\)/);
  assert.match(statusHud, /1m field certification withheld/);
  assert.match(statusHud, /uncalibrated_diagnostic/);
  assert.match(statusHud, /Thermal withheld \(unobserved\)/);
});

test("WorkspaceContextInspector surfaces acquisition date, diagnostic authority and calibration", () => {
  assert.match(inspector, /<dt>Authority<\/dt>/);
  assert.match(inspector, /<dt>Acquisition<\/dt>/);
  assert.match(inspector, /<dt>Calibration<\/dt>/);
  assert.match(inspector, /DIAGNOSTIC_ONLY/);
});
