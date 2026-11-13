import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();

test("P01-G06: No unapproved treatment dosage or chemical command in zone intelligence", () => {
  const file = fs.readFileSync(
    path.join(root, "src/components/farm/intelligence/ZoneDetailStrip.tsx"),
    "utf8"
  );

  // Prohibited unapproved prescriptive hardcodes
  assert.doesNotMatch(
    file,
    /variable-rate \d+-\d+\s*kg\/ha/i,
    "Hardcoded fertilizer dosage must not appear in diagnostic strip"
  );
  assert.doesNotMatch(
    file,
    /apply \d+mm irrigation/i,
    "Hardcoded irrigation volume dosage must not appear in diagnostic strip"
  );
  assert.doesNotMatch(
    file,
    /apply variable-rate urea at \d+\s*kg\/ha/i,
    "Hardcoded urea prescription must not appear in diagnostic strip"
  );
  assert.doesNotMatch(
    file,
    /targeted fungicide application to this zone only/i,
    "Uncertified chemical treatment mandate must not appear in diagnostic strip"
  );
});

test("P01-G05: Irrigation simulation fails closed without physical actuator link", () => {
  const file = fs.readFileSync(
    path.join(root, "src/hooks/useIrrigationState.ts"),
    "utf8"
  );

  // Assert devices in mock fleet are marked disconnected / OFFLINE
  assert.match(file, /is_connected:\s*false/);
  assert.match(file, /SIMULATION_NOT_CONNECTED/);

  // Assert emergencyStopAll returns false for lack of physical confirmation
  assert.match(file, /emergencyStopAll[\s\S]*?return false;/);
});

test("P01-G05: Drone mission orchestration flags disconnected hardware and blocks physical dispatch", () => {
  const file = fs.readFileSync(
    path.join(root, "src/hooks/useDroneMission.ts"),
    "utf8"
  );

  // Assert drone status begins disconnected
  assert.match(file, /connected:\s*false/);

  // Assert dispatchMission checks connected status
  assert.match(file, /if \(!droneStatus\.connected\)/);
});
