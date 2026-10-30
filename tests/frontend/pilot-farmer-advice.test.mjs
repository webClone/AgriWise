/**
 * Pilot farmer advisory contract regression (source helper, not a mounted UI).
 * Inspects the exact current explainer and verifies that a diagnostic/scouting
 * zone cannot display a fabricated fertilizer or salinity treatment dose.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { stripTypeScriptTypes } from "node:module";
import { resolve } from "node:path";

const source = fs.readFileSync(resolve(process.cwd(), "src/components/farm/intelligence/SidebarFarmerView.tsx"), "utf8");
const helperSource = source.slice(
  source.indexOf("const FARMER_ZONE_EXPLAINER"),
  source.indexOf("// ── Zone Alert Card"),
);
assert.ok(helperSource.startsWith("const FARMER_ZONE_EXPLAINER"));
const ctx = {};
vm.createContext(ctx);
vm.runInContext(
  stripTypeScriptTypes(helperSource + "\nglobalThis.explain = _getFarmerExplain;", { mode: "transform" }),
  ctx,
);

const zone = {
  zone_type: "NUTRIENT_RISK", authority: "algorithmic_scouting_region",
  management_eligible: false, prescription_driver_allowed: false,
  severity: 0.7, top_drivers: ["NITROGEN"],
};

test("scouting-only nutrient and salinity alerts never synthesize a treatment dose", () => {
  for (const type of ["NUTRIENT_RISK", "SALINITY_RISK"]) {
    const result = ctx.explain({ ...zone, zone_type: type });
    assert.match(result.todo, /test|inspect|check|sample|review/i);
    assert.doesNotMatch(result.todo, /\d+\s*(?:-|–|to)\s*\d+\s*(?:kg\/ha|mm)|apply a targeted dose|deep leaching event/i);
    assert.doesNotMatch(result.why, /has high salt levels|aren't getting enough nutrients|detected.*fungal/i);
  }
});

test("farmer view does not promote free-text linked actions or invent a health score", () => {
  assert.doesNotMatch(source, /20-30 kg\/ha|50–75mm|computeAgronomicHealth|healthScore|healthCI/);
  assert.match(source, /field-health-unavailable/);
  assert.doesNotMatch(source, /zone\.linked_actions\.map\(/);
  assert.match(source, /Unqualified free-text treatment advice withheld/);
});
