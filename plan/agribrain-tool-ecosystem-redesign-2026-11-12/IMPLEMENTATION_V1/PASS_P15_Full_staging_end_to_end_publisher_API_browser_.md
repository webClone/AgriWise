# P15 — Full staging end to end publisher API browser adversarial acceptance rollout and rollback
**Status:** NOT STARTED · **Dependency:** all P00–P14 gates · **Primary agents:** A0+A7+A6+A8 (A4 scientific) · **Independent reviews:** A4 science, A6 security/safety, A7 adversarial QA, A8 UX release as applicable  
**Proposed code branch:** `release/plot-workspace-p15-staging` (not created).
## Goal and critical boundaries
Demonstrate the completed workspace through the production scientific path in controlled staging, preserving observation-only safety and all tool discovery. Validate real browser pixels, event/panel correlations and negative inputs. No automatic promotion to protected main or hardware-enabled status.
## Code paths and anticipated integrations
- `services/agribrain/app/main.py`
- `services/agribrain/layer05_asmae/plot_snapshot_store.py`
- `src/app/api/agribrain/surfaces/latest/route.ts`
- `src/components/farm/map/PlotMapShell.tsx`
- `src/hooks/useLayer10.ts`
- `src/hooks/usePlotTelemetry.ts`
- `src/components/farm/workspace/ (proposed)`
- `tests/frontend/ (expanded)`
- `services/agribrain/tests/ (targeted Python integration tests)`
- `plan/agribrain-tool-ecosystem-redesign-2026-11-12/IMPLEMENTATION_V1/`
## Detailed implementation tasks
### P15.01 — Freeze candidate and evidence inventory
Document exact candidate SHA, target integration SHA, full diff, deployed environment/settings, tool migration inventory, manifest schema versions, database/geometry fixtures, cache invalidation and science version.

### P15.02 — Publish genuine canonical snapshot
Execute the validated observation-only Plot-A scientific pipeline, using truthful acquired Sentinel/S1 context and clearly distinguishing controlled in-situ fixture from physical independent field evidence. Record numeric serialization/hash, inventory, lineage, UTC cutoff and publication receipt.

### P15.03 — Verify FastAPI snapshot endpoint
Call `/v2/plots/{plotId}/snapshot` with proper signed owner scope. Exact snapshot ID, numerical/temporal/lineage/inventory/contract/receipt validations verified (the current endpoint has a set of required aggregate flags; add explicit checks for any field not covered, do not assume 11 are already enforced).

### P15.04 — Verify Next.js proxy same source
Call `/api/agribrain/surfaces/latest?plotId=...` and `?snapshotId=...` via authenticated Next session; response identity, geometry hash, source clocks, state inventory, surface grid and receipt unchanged. Query foreign/blank/invalid snapshot and verify safe error.

### P15.05 — Verify real browser visible pixels
Navigate actual plot route, validate raster authorization, visible MapLibre/DeckGL pixels, correct legend/units/valid mask/nodata, browser render receipt bound to published scientific snapshot. Repeat in history/compare modes.

### P15.06 — Verify cross-tool integrated user journeys
Click zone -> ASMAE inspector -> sensor device -> relevant admitted evidence -> drone mission dashed plan -> MESIA receiver/experiment -> historical time event -> returning to map. All use same scope/time/source; simulated data labeled.

### P15.07 — Adversarial security and authority
Cross-tenant device map, wrong farm/session, expired calibration, old/new geometry epoch, hash-collision attempt, late-known observation, spoofed flight track, fake MESIA coverage, provenance mismatch, corrupted raster/zone. Expected 'fail closed' from relevant data plane.

### P15.08 — Safety and physical device negative
Observe-only `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`, zero physical command dispatch; drone mock cannot claim real aircraft state; PTZ simulator not actual camera movement; no claim of completed MESIA physical campaign.

### P15.09 — Full frontend and backend checks
Run `npx tsc --noEmit`, `npm run lint`, `npm run test:frontend`, `npm run build`; targeted expanded `node --test` suites and Python pytest with command list, count, logs and source SHAs. Run browser matrix as P14 and repeat after merge candidate freeze.

### P15.10 — Feature flag staged rollout and rollback
Staged V2 enable for permitted test accounts, monitor errors, latency, render receipts, memory and data-scope negative tests. Prepare fast rollback to old plot route without modifying scientific publications. No main merge without explicit separate approval.

### P15.11 — Formal independent release readout
A0 aggregates R0–R5 receipts from all prior passes, gives GO/HOLD for UI scientific visualization vs separate hardware field acceptance. P0 unresolved => HOLD. 52-plan register only updated if original plan's exact independently qualified criteria are genuinely met.
## Pass acceptance / adversarial cases
- **P15-G01** Publisher→Python→Next→Browser exact science identity with visible pixel + render receipt.
- **P15-G02** All thirteen ASMAE catalog items visible in no-data and valid-posterior modes.
- **P15-G03** At least one real-source or honest fixture source object from sensors, drone, MESIA, events, zones accessible and correlated (not claimed field verified).
- **P15-G04** Every one of 94 concepts discoverable and legacy tools reachable.
- **P15-G05** Wrong scope/head/hash/geometry cannot produce authorized raster or foreign map feature.
- **P15-G06** Selected map sensor/zone/mission persists across tool and time transitions only when valid.
- **P15-G07** Simulation never marks physical execution; hardware commands remain zero.
- **P15-G08** Real browser/RTL/mobile/performance logs attached and measured.
- **P15-G09** Rollback flag returns old page without data-loss or backend state mutation.
- **P15-G10** Final signoff includes limitations on physical field validation and hardware commissioning.
## Evidence needed to close
- Exact staging environment, pipeline and browser trace with immutable receipt identities.
- Authenticated API responses, screenshots/videos, frontend and pytest logs.
- Adversarial attack matrix with independent reviewer identity and GO/HOLD per gate.
- Rollback drill with measured result, release decision, protected repo status proof.
**HOLD:** any P0 violation, missing pixel/browser receipt, unsupported field/hardware claim, inability to rollback safely.
## Multi-agent R0–R5 protocol
R0 pin exact source & immutable fixture; R1 owner writes proposal and independent reviewer separately critiques; R2 A4+A6/A3 challenge math, source identity, device safety, security and geometry; R3 A7 executes negative tests; R4 A2+A8 perform integrated real-browser and performance review where UI changes; R5 A0 issues signed GO/HOLD with exact commit, logs, rollback and remaining risks. None of these reviews should be marked complete until actually executed.
