# P03 — Scoped Workspace Store, selection reducer, temporal controller and safe concurrency
**Status:** IMPLEMENTED CANDIDATE · Fully Qualified P03-R2 (163/163 Frontend, 172/172 Python, 63/63 Routes)  
**Dependency:** P01 (commit `0517f43`), P02 (commit `89512f7`)  
**Owner agents:** A2+A6+A4 · Independent red-team: A7 with A6/A4 as applicable  
**Branch:** `feat/plot-workspace-p03-shared-context`  
## Goal, existing constraints and proposed boundary
Build one immutable state controller for plot/tenant/crop-cycle/geometry/publication/time/selected entity/active tool. Split presentation state from authoritative scientific data; no broad global mutable dataset.
## Source paths to inspect and likely modify (paths grounded in repository, proposed new names clearly marked)
- `src/app/farm/[id]/plot/[plotId]/layout.tsx`
- `src/hooks/useLayer10.ts`
- `src/hooks/usePlotTelemetry.ts`
- `src/hooks/usePlotIntelligence.ts`
- `src/components/farm/PlotDashboard.tsx`
- `src/lib/agribrain/telemetry-contract.mjs`
- `src/components/farm/workspace/PlotWorkspaceProvider.tsx (proposed)`
- `src/components/farm/workspace/workspace-reducer.mjs (proposed)`
- `tests/frontend/ (new contract suites proposed)`
## Ordered implementation work packages
### P03.01 — Freeze scope types and identity
Define `OwnerScope`, `PlotScope` (crop cycle, geometry epoch), `PublicationRef`, `SelectedEntityRef`, `TimeCursor` and `RenderIntent`. Require verified scope from server layout; no client authority via user-asserted tenant.

### P03.02 — Build pure reducer with actions
Implement `PLOT_CHANGED`, `SNAPSHOT_SELECTED`, `TIME_SET`, `ENTITY_SELECTED`, `ACTIVE_TOOL_CHANGED`, `VECTOR_VISIBILITY_SET`, `SCENARIO_STARTED/ENDED` and `REQUEST_INVALIDATED`. Unit tests for deterministic state transitions.

### P03.03 — Manage request generations
Every fetch/subscription records generation and scope tuple. On plot/time/geometry change: bump generation, AbortController cancellation, ignore late responses and clear stale sensitive results, even if network cannot cancel.

### P03.04 — Separate clocks
Scientific snapshot as-of/knowledge cutoff, live telemetry observed/ingested, forecast valid time, experiment simulation time. Historical replay cannot acquire future-admitted data; activity center can still show current operational info marked NOW.

### P03.05 — Selection semantics
Shared selected entity ID, not raw object; validate its owner/time/source version. When selecting zone from old snapshot, preserve a comparison reference or clear with reason; never silently remap to same zone ID in another publication.

### P03.06 — Independent UI view state
Maintain map camera/visible vectors/dock/tool modes separately from source of truth; persisted settings are harmless preferences only. Refresh doesn't certify data.

### P03.07 — Provider composition and bridging
Bridge old `Layer10Provider`, `ParcelAssessmentProvider`, `PlotTelemetryProvider` into new store via adapters rather than duplicating fetch; ensure no circular rerenders or state churn.

### P03.08 — Race and invariant test harness
Run rapid plot switch, 3 simultaneous tool opens, failed fetch and snap switch; verify all panels and map read same selected ID and current scope.
## Adversarial regression and acceptance matrix
- **P03-G01** Tenant A response arriving after switching to tenant B is discarded.
- **P03-G02** Selection of old zone/snapshot is not interpreted as new publication evidence.
- **P03-G03** Live reading at historical cursor is labeled live, not admitted historical input.
- **P03-G04** Wrong plot ID, crop-cycle mismatch or absent geometry epoch cannot enter scientific selection.
- **P03-G05** Two panels and map use one identity and one authoritative time basis.
- **P03-G06** No old telemetry stream survives provider scope switch.
## Evidence package and closure conditions
- Typed/validated pure reducer and state machine diagram.
- Independent source authority vs UI presentation model documentation.
- Unit and end-to-end selection/race fixtures; minimal bundle impact measurement.
- Safe fallback to old provider mode when V2 disabled.
**HOLD if:** stale async source leak or client scope can fake certified science.

### Independent multi-agent challenge
- **R0:** owner pins exact baseline, collects negative fixtures, reads competing provider contracts.
- **R1:** A2+A6+A4 produce initial implementation rationale and a separate critique before integration.
- **R2:** A4/A6 check science, ownership and interlock; A3 checks geometry where touched; A1 checks labels and tool discoverability.
- **R3:** A7 writes and runs adversarial tests; report failing-old and passing-new evidence, not fabricated counts.
- **R4:** A2/A8 inspect actual browser where UI changes, cleanup/RTL/perf and no invisible regression.
- **R5:** A0 records exact SHA, test receipts, explicit `GO/CONDITIONAL/HOLD`, unresolved risks and rollback.

### Verification Matrix & Acceptance Receipts (November 14, 2026 · P03-R2 Remediation)
- **P03-R1-F05 Scope Precedence over Invalidation:** Verified in `tests/frontend/plot-workspace-p03-concurrency.test.mjs` (test 4) and reducer suite, proving a stale invalidation from Plot A cannot clear Plot B's publication.
- **P03-R1-F06 Mandatory Identity & Authority Verification:** Verified in `tests/frontend/plot-workspace-p03-concurrency.test.mjs` (test 5) and reducer suite, proving missing scope fields are rejected and unauthoritative CERTIFIED claims are demoted to PENDING.
- **P03-R2 Same-Digest Publication Re-Bridging:** Verified in `tests/frontend/plot-workspace-p03-concurrency.test.mjs` (test 6), ensuring valid publications are restored after generation change.
- **P03-F01 & P03-G01 Discard Cross-Tenant / Cross-Plot Late Response:** Verified via live mutable state and incoming scope ref checks in `tests/frontend/plot-workspace-p03-concurrency.test.mjs` (test 1).
- **P03-F02 Concurrent Request Controller Independence:** Verified in `tests/frontend/plot-workspace-p03-concurrency.test.mjs` (test 2) with 3 concurrent requests where early completion does not delete sibling controllers.
- **P03-F03 Verified Server Scope:** Verified in `tests/frontend/plot-workspace-p03-concurrency.test.mjs` (test 3) for `mapFarm`, `mapPlot`, `mapCropCycle`, and `page.tsx`.
- **P03-F04 Loss-of-Applicability Publication Invalidation:** Verified in `tests/frontend/plot-workspace-p03-concurrency.test.mjs` (test 4).
- **P03 Reducer Purity & Determinism:** Verified in `tests/frontend/plot-workspace-p03-reducer.test.mjs` (test 7) with zero non-deterministic Date calls inside reducer.
- **P03 Reducer Scope Gates & Temporal Modes:** Verified in `tests/frontend/plot-workspace-p03-reducer.test.mjs` (tests 8-11), classifying FORECAST, HISTORICAL, LATEST, SCENARIO and rejecting mismatched scopes.
- **P03-G02 Selection Isolation Across Snapshots:** Verified by `tests/frontend/plot-workspace-p03-concurrency.test.mjs` (test 7).
- **P03-G03 Clock Separation (Live Telemetry vs Scientific As-Of):** Verified by `tests/frontend/plot-workspace-p03-concurrency.test.mjs` (test 8).
- **Frontend Test Suite:** 163/163 passed (`node --experimental-vm-modules --test`).
- **Python Scientific Suite:** 172/172 passed (`pytest`).
- **Production Build:** 63/63 routes compiled successfully (`npm run build`).
- **TypeScript:** 0 errors without `as any` casting (`npx tsc --noEmit`).
