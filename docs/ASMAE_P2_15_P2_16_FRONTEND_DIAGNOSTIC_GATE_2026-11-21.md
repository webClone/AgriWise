# ASMAE verified P2-15/P2-16 — frontend diagnostic and resolution truthfulness

**Date:** 21 November 2026  
**Base:** `b6338fda6a57958c246e4443454673f370a6de5f`  
**Branch:** `feat/akaloris-p2-frontend-diagnostic-authority-20261121`  
**State:** Source remediation candidate, **not independently test-executed**.

## Exact verified findings
- **P2-15:** `src/components/farm/map/PlotMapShell.tsx` previously allowed transect diagnosis when `canInterpretDiagnostically` was false but a sampled ASMAE raster happened to exist (`resolvedIsAsmae && canSamplePixel`). Now transect permission requires explicit diagnostic authority and a useEffect clears active transect state, points and hover on revocation. Scouting pixel labels remain separately available without authorizing a diagnostic transect.
- **P2-16:** `src/components/farm/intelligence/ResolutionCoverageHUD.tsx` previously reported `undefined` or zero 1m approval as `available` by comparing only to `null`. New `hasQualifiedOneMeterApproval()` requires a finite numeric percentage strictly >0 and <=100 **plus** the separate backend `current_1m_approval_allowed === true` flag. Composite and standard approval labels follow that same predicate; no `advisory_certified` statement is made from the number alone.

## Regression gates
New `tests/frontend/asmae-p2-15-p2-16-diagnostic-authority.test.mjs` contains six Node tests: explicit diagnostic denial, active transect revocation, absent/negative/NaN/zero/infinite approval, backend denial despite positive percent, positive control and source wiring.

```powershell
git fetch origin
git switch feat/akaloris-p2-frontend-diagnostic-authority-20261121
node --test tests/frontend/asmae-p2-15-p2-16-diagnostic-authority.test.mjs
node scripts/run-frontend-tests.mjs
npx tsc --noEmit
```
Also execute a real Layer10 Plot Workspace interaction showing a revoked diagnostic permission immediately disables ongoing cross-section sampling, and that a zero/undefined approval is visible as unavailable. This is display truthfulness, not a signed 1m approval proof.

**Protected holds:** PR #32 untouched; 1m certified science, numerical publication and physical actuation held. Findings remain open until full testing and integration qualification.

## 2026-11-21 additional missing-render boundary
The original six source and helper tests checked the approval value and backend flag, but **did not require `asmaeRasterMaterialized`**. On this branch, the helper now demands all three: (1) positive finite `0 < pct <= 100`, (2) backend `current_1m_approval_allowed === true`, and (3) **current-view rendered ASMAE base raster receipt** (`asmaeRasterMaterialized === true`). The HUD calculates this predicate only after resolving the actual browser render receipt.

All six tests remain in place, with expanded cases for `undefined`, `null`, `0`, `NaN`, negative/overflow percent, positive percent with absent raster, and positive percent with valid materialization. The source-wiring test checks the HUD passes `asmaeRasterMaterialized` into the predicate. **This remains a pure-helper + source-wiring suite, not a mounted React component render test**. Full Next.js TAP and browser/React integration remain required.
