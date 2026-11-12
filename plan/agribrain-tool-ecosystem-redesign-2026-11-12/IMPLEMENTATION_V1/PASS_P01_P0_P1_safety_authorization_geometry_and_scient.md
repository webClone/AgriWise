# P01 — P0/P1 safety, authorization, geometry and scientific-status corrections
**Status:** NOT STARTED · design-to-code pass · **Dependency:** P00  
**Owner agents:** A6+A3+A2 (A4 veto) · Independent red-team: A7 with A6/A4 as applicable  
**Proposed code branch:** `fix/plot-workspace-p01-safety-contracts` (does not exist yet).
## Goal, existing constraints and proposed boundary
Repair known defects before layering new UI over invalid identity or geometry. Only bounded bug repairs, with failing-before regression cases; no cosmetic redesign.
## Source paths to inspect and likely modify (paths grounded in repository, proposed new names clearly marked)
- `src/lib/farm-services.ts`
- `src/app/farm/[id]/plot/[plotId]/layout.tsx`
- `src/hooks/usePlotTelemetry.ts`
- `src/lib/agribrain/telemetry-contract.mjs`
- `src/components/farm/map/utils/buildPolygonMask.ts`
- `src/components/farm/intelligence/PlotLoadingSequence.tsx`
- `src/hooks/useLayer10.ts`
- `src/components/farm/intelligence/ZoneDetailStrip.tsx`
- `src/hooks/useIrrigationState.ts`
- `src/hooks/useDroneMission.ts`
## Ordered implementation work packages
### P01.01 — Stop development ownership bypass
Ensure owner-scoped relational query is applied whenever session exists, even in development. For no session, route through verified development bootstrap or refuse plot data; never fallback to first farm. Expose verified owner server-side; no invented tenant ID.

### P01.02 — Fix telemetry initialization invariant
Defer provider mounting until session and plot/farm ownership established; keep `createLiveTelemetryStream` strict and rejection tests. Validate route transitions and cancellation under failed bootstrap, unauthorized plot and cross-tenant changes.

### P01.03 — Correct geospatial topology and mask cache
Replace first outer-ring mask algorithm with robust Polygon/MultiPolygon-with-holes support using source CRS/rectification. Key cache on geometry digest/epoch, grid bounds/dimensions and raster/grid identity; test antimeridian and changed boundaries.

### P01.04 — Separate publication wait from engine failure
Model `idle/working/waiting-for-publication/valid/stale/invalid/terminal-failure` distinctly. A 20-second client timeout is transient or request failure, not confirmation that ASMAE failed. Retain older valid publication with as-of badge.

### P01.05 — Remove unsupported prescriptive hardcodes
Replace hard-coded irrigation/fertilizer/fungicide commands in zone UI with observational facts and permissible scouting guidance. Action cards require actual upstream authority and receipt.

### P01.06 — Differentiate simulated physical features
Label mock drone status and dispatch, simulated irrigation command/stop and PTZ as SIMULATION/NOT CONNECTED. Prevent apparent physical acknowledgment and show clear disabled reason.

### P01.07 — Regression lock
Add independent tests for foreign ownership, mask topology+epoch, source-scope time mismatch, fake hardware state and worker timeout. No change to existing backend scientific algorithm.
## Adversarial regression and acceptance matrix
- **P01-G01** Dev with a signed session for tenant A must not load plot B.
- **P01-G02** No-session dev and invalid farm ID do not mount live scoped provider or leak plot.
- **P01-G03** Polygon holes are masked out; second island filled; new geometry version invalidates old mask.
- **P01-G04** No worker completion receipt -> UI never displays verified engine failure solely due to timeout.
- **P01-G05** Simulated stop/dispatch cannot be interpreted as physical confirmation.
- **P01-G06** No unapproved treatment dosage appears in zone detail.
## Evidence package and closure conditions
- P01 isolated changes and failing-old/passing-new regression logs.
- Independent security/science review for provider scope and fake actuation.
- Rendered geometry samples and known raster pixel/hole comparisons.
- No new frontend surface contract break; old page still accessible.
**HOLD if:** any cross-tenant, invalid geometry, false science or simulated physical success remains.

### Independent multi-agent challenge
- **R0:** owner pins exact baseline, collects negative fixtures, reads competing provider contracts.
- **R1:** A6+A3+A2 (A4 veto) produce initial implementation rationale and a separate critique before integration.
- **R2:** A4/A6 check science, ownership and interlock; A3 checks geometry where touched; A1 checks labels and tool discoverability.
- **R3:** A7 writes and runs adversarial tests; report failing-old and passing-new evidence, not fabricated counts.
- **R4:** A2/A8 inspect actual browser where UI changes, cleanup/RTL/perf and no invisible regression.
- **R5:** A0 records exact SHA, test receipts, explicit `GO/CONDITIONAL/HOLD`, unresolved risks and rollback.
