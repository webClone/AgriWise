# AKALORIS Plot Intelligence Workspace — Full Implementation Program v1.0
**Issued:** 2026-11-12  
**State:** DESIGN / PLAN ONLY; no implementation, execution, CI, or deployment evidence  
**Audited code baseline:** `1ee2c20119af29dd1f0a0b46c85217d91206b744`; documentation-only integration head at planning start: `9273098701d2cb534ba7ca2aea1a240af7b1c6f6`. Re-pin before executing.
**Upstream design:** [DESIGN_V1](../DESIGN_V1/00_DESIGN_DECISION_AND_INDEX.md) and [nine-pass capability audit](../00_MASTER_CAPABILITY_AUDIT.md).
**Existing plot audit:** [Round 2 source audit](../../plot-page-refactor-audit-2026-11-12/ROUND_2_DEEPER/R2_MASTER_INDEPENDENT_AUDIT.md).
**Deployment context:** Next.js 16.1.4/React 19, MapLibre + DeckGL, Prisma, Python/FastAPI AgriBrain; preserve versions unless separate upgrade proposal wins security/compatibility review.

## 0. Mandate and constraints
Redesign **the entire existing plot page**, without deleting the full existing tool menu or silently substituting a new scientific engine. Product vision: ONE geospatial canvas; shared selection, time, publication and plot identity; full tool library (94 catalog concepts, to be deduplicated into canonical tool IDs); all 13 frozen ASMAE states; Sensors, Cameras, Drones, MESIA, Research/Experiments, L0–L10 services, field events, agronomic planning, future World Model/Omega accessible even if not deployed.
- **No modification** to scientific monograph, 13-state ordering, released RC tags, protected `main`, Draft PR #28, or provisional 52-plan numbers as part of documentation/UX refactor.
- **Physical irrigation disabled**: `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`; no unverified equipment actuation. Physical drone/robot features separately guarded. No false device success from mock response.
- Preserve Layer 0 admission, Layer 1 evidence, ASMAE uncertainty, Layer10 scientific render authorization, numerical binding, temporal cutoff and browser render receipts. Experiment sandboxes never mutate a canonical snapshot.
- The 94 are *discoverable product concepts*, NOT a promise of 94 functioning, deployed independent applications. All remain visible; capability and action states tell the truth.
- Every pass is a **bounded GitHub PR** (or small stacked PR group), tested independently before merge. Do not mix future hardware commissioning with page refactor completion.

## 1. Parallel specialist review agents (ASSIGNED ROLES, not claimed executions)
See [01_AGENT_ORCHESTRATION_AND_SIGNOFF.md](01_AGENT_ORCHESTRATION_AND_SIGNOFF.md). Roles A0 Lead integrator, A1 Product/UX, A2 Frontend/state, A3 Geospatial, A4 Science/ASMAE, A5 Data/API & devices, A6 Security/safety, A7 QA/adversarial, A8 Accessibility/performance/release. Multiple perspectives review each pass; one owner integrates conflicting decisions. They must not be presumed independent autonomous agents until actually assigned and their signed review receipts exist.

## 2. Program phases / pass order
| Pass | Deliverable | Key dependencies | Principal owners | Release gate |
|---|---|---|---|---|
| P00 | Baseline inventory, fixtures, contracts | pinned repo | A0,A4,A7 | baseline attested |
| P01 | Critical auth/geometry/false science fixes | P00 | A6,A3,A2 | safety regression |
| P02 | UI design system, interaction specs, responsive shell | P00,P01 | A1,A8,A2 | design tokens/a11y |
| P03 | Shared plot identity/selection/time controller | P01,P02 | A2,A6 | state integrity |
| P04 | Full Tool Registry, capability policy, tool host | P03 | A1,A2,A6 | 94 concepts visible |
| P05 | Owner-scoped geospatial API adapters + evidence graph | P01,P03 | A5,A4,A6 | source identity |
| P06 | Unified map scene registry and cross-panel picking | P03,P05 | A3,A2 | map fidelity |
| P07 | SIRE publication, render authority and 13-state Explorer | P01,P03,P06 | A4,A3,A7 | scientific raster proof |
| P08 | Sensor/camera/ground-truth suite | P05,P06 | A5,A3,A6 | no false device claim |
| P09 | Drone mission/track/orthomosaic suite | P04,P05,P06 | A5,A3,A6 | plan!=flight |
| P10 | MESIA receiver, observability and experiment tools | P04,P05,P06 | A4,A5,A6 | unknown!=coverage |
| P11 | Experiments/What-If isolated simulation workbench | P03,P04,P07 | A4,A2,A7 | immutable canonical |
| P12 | Agronomic L2–L9 and operational tool integration | P04,P07,P11 | A4,A5,A6 | recommendation boundaries |
| P13 | Unified temporal replay, event ledger, correlation explorer | P05,P07–P12 | A4,A2,A7 | zero future leakage |
| P14 | Visual polish, responsive, accessibility, performance | P04–P13 | A1,A8,A3 | device/browser matrix |
| P15 | Production-path staging, adversarial QA, rollout, rollback | all | A0,A6,A7,A8 | GO only on evidence |
The dependency DAG and anti-overlap worktree ownership are in [02_DEPENDENCIES_PR_GRAPH_AND_EFFORT.md](02_DEPENDENCIES_PR_GRAPH_AND_EFFORT.md). Each pass has its own detailed file `PASS_Pxx_*.md`.

## 3. Three independent notions of completion
**Catalog coverage** = every intended concept has tool ID, discovery text, intent, capability state, requirements and docs. Target 100% of 94 initial concepts, after deduplication.
**Functional migration** = actual current UI features are routed into new host with parity checks, no lost controls, and map selection parity.
**Scientific/operational qualification** = runtime APIs, real browser render receipts, privacy/safety and hardware evidence actually checked. Catalog completion does **not** imply hardware qualification.
Use `not_started / source_reviewed / implemented / locally_tested / independently_verified / staged / released` per acceptance receipt; never use one subjective page percentage as a release claim.

## 4. Quality hierarchy
P0 fatal: wrong-tenant data exposure, unauthorized physical actuation, corrupted scientific raster/ledger, temporal leakage, phantom observed data, unsupported safety-critical advice, geometry confusion used for decisions.
P1 material: cross-panel identity drift, fake mission/receiver statuses, loss of core tools, false ASMAE failure, improper source interpretation, selection stale after plot switch, inaccessible essential controls.
P2: user ergonomics, performance, non-blocking enhancement.
**Any unresolved P0 = hard HOLD**; P1 requires explicit justified waiver only if non-safety/non-scientific and isolated.
All exceptions documented with residual risk, owner and expiry; never waive source authority, tenant isolation or actuation gate.

## 5. Required evidence in each pass PR
- Baseline / working branch / head SHA / diffstat; exact changed file list.
- Before/after contracts and traceability to DESIGN_V1, page audit, monograph constraints.
- Independent role-based reviews with challenge/response/resolution.
- Unit + negative + API integration + real browser tests where UI involved; exact command, result, environment and test counts, no unsupported 'all passed'.
- Screenshots or traces for map/desktop/mobile/Arabic RTL; browser render receipt for scientific raster.
- Source-to-display proof: plot/tenant/snapshot/geometry/observed_at/first_available_at/authority/source IDs in same result.
- Red-team signoff, security permission matrix, rollback path and feature flag.
- Decision `GO / CONDITIONAL / HOLD`; proof-backed rather than code-count-based.

## 6. Instrumentation + release safety
Feature flags: `AKALORIS_PLOT_WORKSPACE_V2` UI shell, `AKALORIS_MAP_ENTITY_ADAPTERS_V1`, `AKALORIS_TOOL_REGISTRY_V1` and independently scoped per-tool capability flags (names **proposed**, not existing). Default off in released pilot unless staging qualification passes. Route legacy plot unchanged as immediate rollback.
Track actual time to first basemap, first authenticated entity, first authorized scientific pixel, layer-to-panel selection propagation, time scrub latency, failures/retries, memory/GPU pressure, map render receipts and feature count; set baselines in P00, enforce measured thresholds in P14/P15.

## 7. Deliverables of program
- 16 bounded implementation passes + nine role charters + dependency/branch graph + acceptance/traceability register.
- Complete Tool Library, responsive map-first shell, typed object adapters, source-aware multi-panel selection and timeline.
- 13-ASMAE-state laboratory and all tool family workbenches with realistic availability.
- Cross-tool workflows: sensor↔ASMAE, zone↔drone, MESIA↔experiment, evidence↔field tasks, SIRE↔timeline.
- Controlled staging Publisher→FastAPI→Next.js→Browser and independent adversarial validation; physical field qualification remains separately tracked.
- No fabricated real scene/physical device readiness in docs or UI.

## 8. Immediate starting step
Execute **P00 only** on a new code branch after design approval. First collect baselines and update file paths/risks against the then-current integration head. Only proceed to P01 after first independent security/science signoff.
