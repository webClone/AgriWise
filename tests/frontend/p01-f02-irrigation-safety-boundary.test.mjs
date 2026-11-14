import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();

test("P01-F02: Irrigation hook mock fleet enforces 100% disconnected devices and consistent summary", async () => {
  const hookPath = path.join(root, "src/hooks/useIrrigationState.ts");
  const content = fs.readFileSync(hookPath, "utf8");

  // Verify that all devices in the mock generator have is_connected: false and status: 'OFFLINE'
  assert.doesNotMatch(
    content,
    /is_connected:\s*true/i,
    "No mock device may be marked as is_connected: true in observation pilot"
  );
  assert.doesNotMatch(
    content,
    /status:\s*['"]ONLINE['"]/i,
    "No mock device may be marked as status: ONLINE"
  );
  assert.doesNotMatch(
    content,
    /status:\s*['"]EXECUTING['"]/i,
    "No mock device may be marked as status: EXECUTING"
  );

  // Status summary must have ONLINE: 0 and EXECUTING: 0
  assert.match(content, /ONLINE:\s*0/);
  assert.match(content, /EXECUTING:\s*0/);

  // Fictitious delivered water quantities must not exist in events or budget
  assert.doesNotMatch(
    content,
    /actual_volume_l:\s*12500/,
    "Fictitious 12,500L delivered water must be removed"
  );
  assert.doesNotMatch(
    content,
    /daily_consumed_mm:\s*13\.5/,
    "Fictitious 13.5mm daily consumed water must be removed"
  );

  // Safety controls must return false (no false positive physical acknowledgments)
  assert.match(content, /emergencyStopAll[\s\S]*?return false;/);
  assert.match(content, /emergencyStopDevice[\s\S]*?return false;/);
  assert.match(content, /cancelEvent[\s\S]*?return false;/);

  // Observability exports
  assert.match(content, /isSimulationMode:\s*true/);
  assert.match(content, /isPhysicalHardwareConnected:\s*false/);
  assert.match(content, /actuatorLinkStatus:\s*['"]DISCONNECTED['"]/);

  // F06: Safety score must not be fabricated as nominal 0.95 in simulation mode
  assert.doesNotMatch(
    content,
    /setSafetyScore\(\s*0\.95\s*\)/,
    "F06: Must not assign fabricated nominal safety score 0.95"
  );
  assert.match(
    content,
    /setSafetyScore\(\s*null\s*\)/,
    "F06: Safety score in simulation mode must be null (not evaluated)"
  );
  assert.match(
    content,
    /approved_by:\s*['"]farmer \(local preview only — non-operational\)['"]/,
    "F06: Mock schedule approval must be marked explicitly local preview only"
  );
});

test("P01-F02 & F06: IrrigationDashboard displays simulation safety badge and local preview approvals", () => {
  const dashPath = path.join(root, "src/components/irrigation/IrrigationDashboard.tsx");
  const content = fs.readFileSync(dashPath, "utf8");

  // F06: Safety badge must display 'Safety: Not evaluated — Simulation'
  assert.match(
    content,
    /Safety:\s*Not evaluated\s*—\s*Simulation/,
    "F06: Irrigation dashboard must display 'Safety: Not evaluated — Simulation' when safetyScore is null"
  );
  assert.match(
    content,
    /Approve \(Local Preview\)/,
    "F06: Schedule approval action must explicitly state Local Preview"
  );
  assert.match(
    content,
    /APPROVED \(Local Preview — Non-operational\)/,
    "F06: Approved schedule status must state non-operational local preview"
  );

  // Must render simulation mode banner with alert role
  assert.match(content, /role="alert"/);
  assert.match(content, /SIMULATION \/ OBSERVATION-ONLY MODE/);
  assert.match(content, /NO PHYSICAL ACTUATOR HARDWARE CONNECTED/);

  // Header must state SIMULATION / DISCONNECTED
  assert.match(content, /SIMULATION \/ DISCONNECTED/);
  assert.match(content, /0 Connected Actuators/);

  // E-STOP button must be labeled as simulation
  assert.match(content, /E-STOP \(Simulation\)/);

  // Stat cards must report 0 online and 0 physical water delivered
  assert.match(content, /label="Online Actuators"[\s\S]*?sub="No hardware connected"/);
  assert.match(content, /label="Executing"[\s\S]*?sub="Physical dispatch blocked"/);
  assert.match(content, /label="Water Today"[\s\S]*?sub="0 L delivered \(Observation-only\)"/);

  // Event cards must display [SIMULATED] badge
  assert.match(content, /\[SIMULATED\]/);
  assert.match(content, /0 L physical delivered/);
});

test("P01-F01 & Order 3: buildLayerStack and ContourSurfaceLayer fail closed when mask is null", () => {
  const layerStackPath = path.join(root, "src/components/farm/map/buildLayerStack.ts");
  const layerStackContent = fs.readFileSync(layerStackPath, "utf8");

  // buildLayerStack must NOT set totalInPolygonCells = gridW * gridH when mask is null
  assert.doesNotMatch(
    layerStackContent,
    /totalInPolygonCells\s*=\s*gridW\s*\*\s*gridH/,
    "buildLayerStack must not fail open to entire grid on missing mask"
  );
  assert.match(
    layerStackContent,
    /if\s*\(!mask\s*\|\|\s*mask\.data\[r\s*\*\s*gridW\s*\+\s*c\]\s*===\s*0\)\s*continue;/,
    "buildLayerStack must require cell to be inside mask, skipping all when mask is null"
  );

  const contourPath = path.join(root, "src/components/farm/map/layers/ContourSurfaceLayer.ts");
  const contourContent = fs.readFileSync(contourPath, "utf8");

  // ContourSurfaceLayer must return [] when mask is null
  assert.match(
    contourContent,
    /if\s*\(!mask\)\s*\{[\s\S]*?return\s*\[\];[\s\S]*?\}/,
    "ContourSurfaceLayer must return [] immediately if polygon mask is null"
  );

  // Must not contain the old fail-open (!mask || mask.data[...] === 1)
  assert.doesNotMatch(
    contourContent,
    /!mask\s*\|\|\s*mask\.data/,
    "ContourSurfaceLayer must not permit pixels when mask is null"
  );
});
