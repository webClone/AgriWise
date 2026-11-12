# P00 — Reproducible baseline, complete behavior inventory and acceptance harness
**Status:** NOT STARTED · design-to-code pass · **Dependency:** approved DESIGN_V1, pinned integration SHA  
**Owner agents:** A0+A4+A7 · Independent red-team: A7 with A6/A4 as applicable  
**Proposed code branch:** `plan/plot-workspace-p00-baseline` (does not exist yet).
## Goal, existing constraints and proposed boundary
Create a reproducible reference before any source rewrite. Establish what actually works, what is simulated, what is incomplete, and a coverage denominator by source path and user behavior. No '100% audited' claims based on structural file listing. Preserve old page as a usable fallback.
## Source paths to inspect and likely modify (paths grounded in repository, proposed new names clearly marked)
- `package.json`
- `src/app/farm/[id]/plot/[plotId]/layout.tsx`
- `src/components/farm/PlotDashboard.tsx`
- `src/components/farm/map/PlotMapShell.tsx`
- `src/hooks/useLayer10.ts`
- `src/hooks/usePlotTelemetry.ts`
- `tests/frontend/`
- `services/agribrain/app/main.py`
- `plan/agribrain-tool-ecosystem-redesign-2026-11-12/DESIGN_V1/`
## Ordered implementation work packages
### P00.01 — Freeze source and environment
Record Git SHA/branch/worktree, Next 16.1.4/React 19, Node/Python/Prisma versions, exact env flags (redacted), database fixtures, map style credentials and API availability. Snapshot current page route and crop-cycle/geometry/snapshot identity.

### P00.02 — Audit every existing entry point
Enumerate route pages, providers, imported tools, overlays, dialogs, hotkeys, API calls and access controls. Build clickable tool parity inventory including Dr​one, Sensors, MESIA, Irrigation, raw data, intelligence, experiments and context-band actions; record each control's real/mock/unavailable status.

### P00.03 — Establish science reference fixtures
Freeze Plot-A observation-only canonical snapshot and a corrupt/tampered variant; prepare scalar-only ASMAE, all 13 absent, authorized raster, stale head and no-data cases. Preserve numerical/source/geometry/temporal bindings.

### P00.04 — Establish spatial scenario fixtures
Use MultiPolygon containing hole + second island; sensor coordinates and absent-coordinate device; drone proposed route and mock dispatch; MESIA receiver with frequency coverage but no spatial support; events with point/plot/no geometry.

### P00.05 — Run baseline checks
Execute `npx tsc --noEmit`, `npm run lint` as applicable, `npm run test:frontend`, `npm run build` and bounded pytest for touched backend contracts. Capture existing failures without silently fixing them in test harness.

### P00.06 — Baseline real browser
Capture screens and interaction logs at 1600/1024/768/360, Arabic RTL, English LTR, keyboard-only, 200% zoom. Record map first-pixel/render receipt, selector/hover behavior, no-L10 status and tool open/close; measure initial performance.

### P00.07 — Reconcile audit claims
Cross-link known Round2 P0/P1 findings to reproducible evidence. Separate source-confirmed, probe-reproduced, browser-confirmed, and unverified hypotheses. Define exact denominator for pass acceptance and open gaps.
## Adversarial regression and acceptance matrix
- **P00-G01** Frozen canonical snapshot must remain inspectable even if latest worker is pending.
- **P00-G02** Original map science remains prohibited for corrupt/foreign publication.
- **P00-G03** Missing authenticated tenant/farm/plot cannot silently initialize certified telemetry.
- **P00-G04** Every existing visible tool has baseline screenshot or unavailable/state receipt.
- **P00-G05** Baseline commands and environment are reproducible by a second reviewer.
## Evidence package and closure conditions
- P00 baseline manifest, source map and 94-concept to existing-feature parity table.
- Failure fixture set and screenshot/performance baseline with exact timestamps.
- Snapshot hash/geometry/owner ID reconciliation; test log commands and outcomes.
- Review evidence report signed by A0, A4, A6, A7.
**HOLD if:** baseline cannot be reproduced or source/tree/route drift is not reconciled.

### Independent multi-agent challenge
- **R0:** owner pins exact baseline, collects negative fixtures, reads competing provider contracts.
- **R1:** A0+A4+A7 produce initial implementation rationale and a separate critique before integration.
- **R2:** A4/A6 check science, ownership and interlock; A3 checks geometry where touched; A1 checks labels and tool discoverability.
- **R3:** A7 writes and runs adversarial tests; report failing-old and passing-new evidence, not fabricated counts.
- **R4:** A2/A8 inspect actual browser where UI changes, cleanup/RTL/perf and no invisible regression.
- **R5:** A0 records exact SHA, test receipts, explicit `GO/CONDITIONAL/HOLD`, unresolved risks and rollback.
