# Design Pass 06 — Release Gates, Migration Plan and Adversarial Test Specification
**Scope:** planning/qualification specifications, not executed tests. Do not count these gates as passed or as 52-plan completed slices.
## A. Test layers
1. Pure model contract tests (scope, geometry, temporal ordering, classification).
2. API adapter tests (auth, filtering, pagination, stale/missing/mutated receipts).
3. UI integration tests (shared selection, map/inspector/tools/time coherence).
4. Real-browser checks (MapLibre/DeckGL pixels, pointer/touch interactions, legends, render receipts, zoom/pan/RTL).
5. Controlled staging integration (canonical publisher -> Python API -> Next.js -> browser, observation-only).
6. Hardware-bound work must pass independent device integration/field evidence later; do not infer from simulation.
## B. Critical gates
| ID | Priority | Test | Acceptance |
|---|---|---|---|
| WS-001 | P0 | Cross-tenant selected feature | Backend rejects and client never displays foreign object |
| WS-002 | P0 | Incomplete session/tenant scope | No telemetry/map data instantiated before authenticated owner context |
| WS-003 | P0 | Geometry with holes | Neither scientific raster nor zone overlay fills hole |
| WS-004 | P0 | MultiPolygon second island | Correct raster mask and object hit tests for every valid part |
| WS-005 | P0 | Geometry epoch changes | Cache recomputed; old selected objects invalidated |
| WS-006 | P0 | Scientific raster vs no-data | Scalar/unsupported state produces plot card, zero false heatmap pixels |
| WS-007 | P0 | Snapshot numerical hash mismatch | Browser denies scientific raster; other benign vector layers may remain visible |
| WS-008 | P0 | Fake or mutated sensor reading | Cannot set admitted science, source hash/time checks enforced |
| WS-009 | P0 | Live reading at historic cutoff | Not silently included in historical publication |
| WS-010 | P0 | Simulation vs canonical | Sandbox cannot replace accepted publication or scientific lineage |
| WS-011 | P0 | Physical irrigation | Zero dispatches while interlock is false, even from tool/library |
| WS-012 | P0 | Mock drone command | Shows SIMULATED; cannot show armed/in-flight physical state |
| WS-013 | P0 | Fake MESIA coverage | Unknown/unobservable results cannot produce measured coverage footprint |
| WS-014 | P0 | Timed-out publication wait | Displays pending/timeout, never false terminal 'worker failed' |
| WS-015 | P1 | Map sensor click -> tool -> timeline | Same ID/plot and correct observation timestamp in every surface |
| WS-016 | P1 | Device list click -> map | Focuses registered point, selecting the exact same entity as map click |
| WS-017 | P1 | Zone -> drone planner | Exact accepted zone source ID and geometry, dashed preview, no dispatch |
| WS-018 | P1 | Drone real telemetry vs plan | Executed path separate, time-indexed; no inferred flight from plan |
| WS-019 | P1 | MESIA experiment and ASMAE | Simulated radio result appears as separate experimental overlay, no state mutation |
| WS-020 | P1 | ASMAE explorer | All 13 frozen coordinates visible with explicit availability |
| WS-021 | P1 | Panel-state agreement | Two simultaneous panels show same selected entity and time scope |
| WS-022 | P1 | Rapid plot switch / outstanding fetch | Old request cannot repopulate new plot; aborted request remains ignored |
| WS-023 | P1 | Time-peel / forecast | Observed, curve proxy, forecast and simulation visually distinct |
| WS-024 | P1 | Map object overlap | User can disambiguate and keyboard-select all overlapping entities |
| WS-025 | P1 | Layer toggle/persistence | Vector layer toggle independent of scientific raster; choice persists only in safe user preference |
| WS-026 | P1 | Browser receipt | Browser materialization proof binds exact scientific pixels, legend and publication |
| WS-027 | P1 | Missing/invalid geolocation | Tool entry remains discoverable but no fake map pin |
| WS-028 | P1 | No false cause assertion | Nearby sensors shown as proximity; assimilation edge needs exact evidence proof |
| WS-029 | P2 | Responsive + RTL | 1600, 1024, 768, 360 widths; Arabic RTL, English/French LTR, keyboard and 200% zoom |
| WS-030 | P2 | Performance/stability | Smooth zoom/pan with representative large scene; no unbounded polling/heap/VRAM growth; metrics measured and threshold set before release |
| WS-031 | P2 | Full library inclusion | All 94 concepts discoverable; unavailable tools show interactive truthful setup/preview states |
| WS-032 | P2 | Scene visual semantics | Planned vs executed; observed vs model; simulated vs historical distinguishable without color |
## C. Instrumented user-flow fixtures (design)
**Fixture A — Sensor and historic ASMAE:** one registered 15 cm probe, one raw late observation, one admitted older reading, ASMAE posterior from admitted receipt. Verify cursor at historic cutoff excludes late record; choose device point and inspect nearest time-admissible ASMAE state without implied causal link.
**Fixture B — Zone/drone/imagery:** one valid MultiPolygon with hole and second island; SIRE zone on second island; planned route; mock dispatch response; QA accepted orthomosaic. Verify exact zone selection, plan dashed, mock flight not solid, hole not colored.
**Fixture C — MESIA experiment:** receiver with a known registered point and valid frequency but absent spatial coverage, hypothetical trial polygon, `NotImplementedError` physical trial harness. Show source's UNKNOWN/no-coverage state and interactive protocol configuration without counterfeit field result.
**Fixture D — Tool concurrency:** select event, open Sensor, open ASMAE, initiate a stale async fetch, switch plot. No entity from previous tenant/plot in new map/tools. Browser receipt cleared appropriately.
**Fixture E — Source-only scientific surface:** plot-level posterior exists with no authorized SIRE raster; state card shows uncertainty and source; map only basemap/geometry + valid vectors.
## D. Design-to-implementation work packages
- **D0 — Design freeze and semantic correction:** approve 5 user journeys, page taxonomy, map object vocabulary and 32 gates. Correct current P1 scope/geometry/simulation/unsupported advice **before** claiming operational release.
- **D1 — Workspace shell**: create unified state store, Tool Library, pinned Dock, inspector host while temporarily embedding legacy tools. Ensure 94 catalog concepts remain discoverable even if integration pending.
- **D2 — Map feature adapters**: registered sensor location, camera registry, drone plan/flight, MESIA receiver/coverage, event ledger, task locations, authoritative SIRE surfaces. No inventing missing geometry.
- **D3 — Correlated interactions**: map/list/panel selection parity, related-to graph, temporal replay. Add side-by-side scientific/hypothetical comparison.
- **D4 — Deep workbenches**: ASMAE 13-state, Drone, Sensor, MESIA, Experiment, Planning and AI investigation; move current full-screen independent tools to shared host.
- **D5 — Operational staging qualification**: publisher->API->browser scientific integrity, cross-tenant negative tests, responsive/a11y/performance, physical interlocks, then actual field hardware qualification on a separate track.
## E. Rollout and reversibility
Feature-flag the **new page shell** and **new spatial adapters** independently; no need to change scientific calculations while making UI. Ship progressive batches through an implementation branch with small reviewable PRs. Preserve existing plot route as fallback until parity. Use immutable snapshot ID on selection and comparison. Never drop or rewrite old publication identities, pilot release tags, Draft PR #28 or protected main.
## F. Release definitions
- **Design accepted**: complete docs and UX decision approval. This file is not proof of implementation.
- **Interactive UI qualified**: true map/list/panel parity and simulated vs actual markers verified in browser with representative fixtures.
- **Scientific visualization qualified**: canonical published snapshot pixel/legend/mask/receipt and negative tests verified in real browser; no false science.
- **Physical field validation**: independently recorded sensor/flight/MESIA measurements; blind validation with raw logger/receiver receipts.
- **Physical action approved**: separate safety/governance/hardware phase. Not part of current observation-only pilot.
## G. Known open design choices
- Default vector layer preset: current proposal displays sensors/zones/recent events and uses toggles for drones/MESIA/cameras/tasks.
- Detail mode: farmer starts with concise provenance; expert can always expand full lineage, posterior and diagnostics.
- Timelines: compact strip default, advanced multi-lane timeline expanded; historical source-availability cutoff always visible.
- Browser compare: one primary authorized raster, one optional comparative; more is offloaded to specialized analysis tools.
These are *defaults for first concept validation*, not fixed requirements in code.
