import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import {
  isTransectDiagnosisAuthorized,
  hasQualifiedOneMeterApproval,
} from "../../src/lib/agribrain/diagnostic-display-authority.mjs";

const read = name => readFileSync(path.join(process.cwd(), name), "utf8");
const map = read("src/components/farm/map/PlotMapShell.tsx");
const hud = read("src/components/farm/intelligence/ResolutionCoverageHUD.tsx");

test("P2-15 sampled ASMAE raster never overrides explicit diagnostic denial", () => {
  assert.equal(isTransectDiagnosisAuthorized(false), false);
  assert.equal(isTransectDiagnosisAuthorized(undefined), false);
  assert.equal(isTransectDiagnosisAuthorized(null), false);
  assert.equal(isTransectDiagnosisAuthorized(true), true);
  assert.match(map, /inspectorDiagnosisAllowed = isTransectDiagnosisAuthorized\(canInterpretDiagnostically\)/);
  assert.doesNotMatch(map, /inspectorDiagnosisAllowed\s*=\s*canInterpretDiagnostically\s*\|\|/);
});

test("P2-15 transect sampling, entry control and revocation use same authority", () => {
  assert.match(map, /if \(!inspectorDiagnosisAllowed\) return null;/);
  assert.match(map, /canTransect: inspectorDiagnosisAllowed/);
  assert.match(map, /if \(!inspectorDiagnosisAllowed\) \{\s*setShowProxyBanner\(true\)/);
  assert.match(map, /if \(!inspectorDiagnosisAllowed\) \{\s*setTransectMode\(false\);\s*setTransectPoints\(\[\]\);/);
});

test("P2-16 null, undefined, zero, negative and NaN never report 1m available", () => {
  for (const bad of [null, undefined, 0, -1, NaN, Infinity, -Infinity, "50", 101]) {
    assert.equal(hasQualifiedOneMeterApproval(bad, true, false), false, String(bad));
    assert.equal(hasQualifiedOneMeterApproval(bad, true, true), false, String(bad));
  }
});

test("P2-16 backend denial wins even if ladder states 100% approved", () => {
  for (const val of [0.01, 1, 33, 100]) {
    assert.equal(hasQualifiedOneMeterApproval(val, false, false), false);
    assert.equal(hasQualifiedOneMeterApproval(val, false, true), false);
    assert.equal(hasQualifiedOneMeterApproval(val, undefined, false), false);
    assert.equal(hasQualifiedOneMeterApproval(val, undefined, true), false);
    assert.equal(hasQualifiedOneMeterApproval(val, null, false), false);
    assert.equal(hasQualifiedOneMeterApproval(val, null, true), false);
  }
});

test("P2-16 positive finite approval still withheld without an ASMAE raster receipt", () => {
  for (const pct of [0.01, 1, 50, 100]) {
    assert.equal(hasQualifiedOneMeterApproval(pct, true, false), false);
    assert.equal(hasQualifiedOneMeterApproval(pct, true, undefined), false);
    assert.equal(hasQualifiedOneMeterApproval(pct, true, null), false);
    assert.equal(hasQualifiedOneMeterApproval(pct, true, true), true);
  }
});

test("P2-16 every HUD 1m approval label follows the qualified predicate", () => {
  assert.match(hud, /const qualifiedOneMeterApproval = hasQualifiedOneMeterApproval\(/);
  assert.match(hud, /data\?\.asmae_evidence_state\?\.current_1m_approval_allowed/);
  assert.match(hud, /const asmaeRasterMaterialized = baseRasterMaterialized/);
  assert.match(hud, /data\?\.asmae_evidence_state\?\.current_1m_approval_allowed,\s*asmaeRasterMaterialized,/);
  assert.ok(hud.indexOf("const asmaeRasterMaterialized") < hud.indexOf("const qualifiedOneMeterApproval"));
  assert.doesNotMatch(hud, /oneMeterAsmaeApprovalPct\s*!==\s*null\s*\?\s*"available"/);
  assert.match(hud, /qualifiedOneMeterApproval\s*\?\s*"available"/);
  assert.doesNotMatch(hud, /advisory_certified/);
});
