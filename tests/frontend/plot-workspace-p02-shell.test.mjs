/**
 * P02 source-level regression: verifies the legacy feature gate, transitional
 * UI wiring, catalog coverage and responsive shell contract. These tests do
 * NOT replace a Next.js build or real browser/map qualification.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const read = relative => fs.readFileSync(path.join(ROOT, relative), "utf8");
const gate = read("src/components/farm/workspace/PlotWorkspaceFeatureGate.tsx");
const page = read("src/app/farm/[id]/plot/[plotId]/page.tsx");
const shell = read("src/components/farm/workspace/PlotWorkspaceShell.tsx");
const dock = read("src/components/farm/workspace/WorkspaceToolDock.tsx");
const concepts = read("src/components/farm/workspace/workspace-tool-concepts.ts");
const dashboard = read("src/components/farm/PlotDashboard.tsx");
const timeline = read("src/components/farm/intelligence/TimelineStrip.tsx");
const styles = read("src/components/farm/workspace/plot-workspace-v2.css");
const trust = read("src/components/farm/workspace/WorkspaceScientificStatus.tsx");

test("V2 is opt-in and V2-disabled renders the unmodified legacy component path", () => {
  assert.match(gate, /NEXT_PUBLIC_PLOT_WORKSPACE_V2\s*===\s*"true"/);
  assert.match(gate, /if \(!isPlotWorkspaceV2Enabled\(\)\) return <PlotDashboard \{\.\.\.props\} \/>/);
  assert.match(page, /import PlotWorkspaceFeatureGate/);
  assert.match(page, /<PlotWorkspaceFeatureGate\s/);
  assert.doesNotMatch(page, /<PlotDashboard\s/);
  assert.doesNotMatch(shell, /createLiveTelemetryStream|createLayer10|fetch\("/);
});

test("V2 mounts native spatial canvas without legacy dashboard and one moved existing timeline", () => {
  assert.equal((shell.match(/<PlotDashboard /g) || []).length, 0);
  assert.match(shell, /<WorkspaceSpatialCanvas\s/);
  assert.match(gate, /<PlotDashboard \{\.\.\.props\} \/>/);
  assert.match(dashboard, /\{!embeddedInWorkspace\s*&&\s*<TimelineStrip\s*\/>\}/);
  assert.match(timeline, /export default function TimelineStrip\(\{ docked = false \}/);
  assert.match(shell, /<WorkspaceTimelineContainer\s*\/>/);
  assert.match(read("src/components/farm/workspace/WorkspaceTimelineContainer.tsx"), /<TimelineStrip docked\s*\/>/);
  assert.doesNotMatch(shell, /<PlotMapShell/);
});

test("Tool Dock preserves real legacy feature entry points with plot-scoped UI bridge", () => {
  for (const action of ["sensors", "drone", "mesia", "irrigation", "evidence", "assistant"]) {
    assert.match(dashboard, new RegExp('case "' + action + '"'));
    assert.match(dock, new RegExp('action: "' + action + '"'));
  }
  assert.match(dashboard, /detail\.plotId !== plotId/);
  assert.match(shell, /CustomEvent\("akaloris:p02:open-tool"/);
  assert.match(dock, /aria-label=\{item\.label\}|title=\{item\.label\}/);
});

test("P02 catalog lists 94 discoverable concepts in the six specified families", () => {
  const sections = [...concepts.matchAll(/concepts:\s*\[([\s\S]*?)\]\s*,/g)];
  assert.equal(sections.length, 6);
  const counts = sections.map(match => (match[1].match(/"[^"]+"/g) || []).length);
  assert.deepEqual(counts, [24, 16, 14, 12, 16, 12]);
  assert.equal(counts.reduce((a,b) => a+b, 0), 94);
  assert.match(dock, /Catalog entries are design concepts/);
  assert.match(dock, /Full capability and permission qualification belongs to P04/);
});

test("Scientific and live IoT status are separated and not promoted to proof of rendered pixels", () => {
  assert.match(trust, /useParcelAssessment\(\)/);
  assert.match(trust, /usePlotTelemetry\(\)/);
  assert.match(trust, /Operational IoT · not scientific evidence/);
  assert.match(trust, /A loaded publication does not prove that a scientific raster is rendered/);
});

test("Responsive tokens, logical properties, keyboard and RTL affordances exist", () => {
  for (const required of ["--pw-canopy", "--pw-panel", "inset-inline-start", "inset-inline-end",
    "border-inline-start", "@media (max-width: 1120px)", "@media (max-width: 820px)",
    "@media (max-width: 600px)", "[dir=\"rtl\"]", "focus-visible", "min-height: 44px"]) {
    assert.ok(styles.includes(required), "missing style contract " + required);
  }
  assert.match(dock, /aria-controls="pw-tool-library"/);
  assert.match(dock, /if \(event\.key === "Escape"\)/);
});
