# MULTI-AGENT EXECUTION RUNBOOK — Akaloris Plot Workspace
**Status:** role assignment blueprint and prompts; no specialist agents have been independently launched or executed by this document.
**Use:** Assign different human reviewers, coding-agent sessions or CI verification runners to A0–A8 as they become available. If one assistant performs several roles, explicitly state that the reviews are not independent.
## Global scope message to EVERY agent
> We are redesigning the Akaloris / AgriBrain Plot page on the GitHub repository `webClone/AgriWise`. Read the exact source baseline and its DESIGN_V1 plus IMPLEMENTATION_V1 files; do not assume a feature is production-ready because a module exists. Do not modify protected `main`, Draft PR #28, historical release tags, or the scientific architecture monograph. Preserve the 13 ASMAE state dimensions, Layer0/Layer1 admission, SIRE publication proof, temporal cutoffs, and `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`. All 94 intended tool concepts remain discoverable, including experiment and future tools. One map must visualize all spatially supported devices, drones, MESIA, scenes, zones, events and tasks. Never fabricate coordinates, scientific pixels, actual equipment state, or field validation. Record exact source SHA, files touched, real commands/tests executed and outcomes. A pass is not complete without independent acceptance and rollback.

## Independent work-package prompts
### A0 — Program lead / integration
**Task:** Read `00_MASTER_IMPLEMENTATION_PROGRAM.md`, `02_DEPENDENCIES_PR_GRAPH_AND_EFFORT.md`, current branch and latest code diff. Verify staged prerequisites, select a bounded Pxx, assign owners and reviewers, pin baseline, approve file ownership and integration sequence.
**Deliverables:** ADR, PR scope, dependency status, changed-path manifest, comparison to protected main/Draft PR #28, GO/HOLD and rollback receipts. Reject over-broad PR, closed risk without evidence, silent 52-plan inflation.

### A1 — Product designer / IA and localization
**Task:** Read DESIGN_V1 and 94-concept inventory. Design the plot shell and full Tool Library without hiding any existing tool. Maintain map-first UX, compact Dock, contextual inspector, timeline, full workbench and farmer/expert presentations; Arabic RTL and French/English at desktop/mobile. Every empty state truthful.
**Deliverables:** annotated states, interaction maps, responsive/keyboard flows, status vocabulary, tool concept-to-entry mappings. Challenge excessive overlays, confusing jargon and invisible planned modules.

### A2 — Frontend state and Next.js
**Task:** Read current plot layout and providers, useLayer10/usePlotTelemetry/PlotDashboard and P03. Create scoped selection, time, plot geometry, publication and tool host state, with request generation cancellation. Preserve legacy fallback and scientific/operational data-plane separation.
**Deliverables:** pure store tests, provider composition, owner scope and route guard behavior, cross-panel identity test, migration proof and actual browser screenshot. Challenge stale React closures, hydration differences and async scope races.

### A3 — Geospatial and map science
**Task:** Read PlotMapShell, buildLayerStack, buildPolygonMask, zone layers, raster bounds and render receipts. Make typed layered scene; ensure all entities with real geodata can be displayed and selected; distinguish planned/actual/simulated; preserve raster numerical proof.
**Deliverables:** polygon holes/MultiPolygon/antimeridian tests, geometry epoch/digest cache, map picking and accessibility list, actual render receipt and dense-scene performance profile. Challenge false footprints, changing pixel values, incorrect hit tests.

### A4 — ASMAE/scientific integrity
**Task:** Read canonical 13-state schema, L0→L1 admission, ASMAE posterior and SIRE source/publish contracts. Design all 13 state tools, posterior/sigma, identifiability, historical replay and exact source-to-state evidence edges. Review all agronomic recommendations, World Model/Omega descriptions and experimental claims.
**Deliverables:** 13-state consistency matrix, fail-closed rendered-pixel test, source authority map, numerical/time/hash checks, signed scientific GO/HOLD. Reject proximity presented as assimilation, scalar plot posterior painted as raster, measured vs proxy confusion.

### A5 — Backend IoT/drone/MESIA adapters
**Task:** Read device registry/calibration, status API, drone planner/mock driver, photogrammetry, MESIA receiver coverage/experiment scaffolding. Build owner-scoped read-only feature adapters; distinguish physical location, observed reading, plan, live track, receiver observability and experiment.
**Deliverables:** versioned geometry/time/authority contracts, API fixture dataset with missing geometry and foreign tenant cases, pagination, exact source refs, physical/virtual device status labeling. Challenge full RF-area inferred from frequency, mock drone completion, stderr-only alert treated as historical event.

### A6 — Security/physical safety red team
**Task:** Read authentication, signing, tenant authorization, telemetry, source-policy gates, action endpoints and P01/P05/P15. Attack cross-tenant scope, spoofed coordinates, historic cutoff, raw packet mutation, forged rendered surface, simulation→actuation, missing hardware authorization.
**Deliverables:** reproducible negative exploit cases, expected rejection, proof of no physical irrigation command, no fake drone/PTZ confirmations, release veto for any unresolved P0. Do not weaken checks to make UI function.

### A7 — Adversarial QA/verification
**Task:** For each Pxx read pass acceptance and centralized test catalog; create tests that fail before patch and pass after. Check official commands in package.json, Python pytest, Next API, MapLibre actual browser and cross-panel scenarios. Differentiate 'not run' from 'passed'.
**Deliverables:** command/exit/log/screenshot/time/commit, matrix of Pxx-Gxx and E2E-xx, open issues, exact current repo SHA, independent signoff or HOLD. Challenge selection parity assertions without browser or mocked source authority.

### A8 — Accessibility/performance/release
**Task:** Review user modes, keyboard, ARIA, RTL, responsive panel/popup/navigation, map layer density, memory/GPU/network and staging flags. Test at 1600/1024/768/360 and zoom 200%, reader list alternatives.
**Deliverables:** measured baselines and regressions, annotated screen recordings, mobile keyboard/touch checks, RTL review, rollback drill and release monitor. Challenge inaccessible map-only interactions, heavy overlays and no fallback.

## Agent handoff contracts
An agent should submit this Markdown report with each code PR:
```yaml
pass: Pxx
role: A0-A8
review_kind: implementation|independent_review|adversarial_qa
baseline_sha: <exact>
candidate_sha: <exact>
files_read: []
files_changed: []
source_contracts_checked: []
tests_run:
  - command: ...
    status: PASS|FAIL|BLOCKED|NOT_RUN
    raw_log_ref: ...
scientific_authority: preserved|risk|not_applicable
owner_scope: verified|risk
physical_action: disabled|hardware_approved|not_applicable
findings: []
release_recommendation: GO|CONDITIONAL|HOLD
signature_or_reviewer_id: ...
```
Text-only summaries without actual SHA/logs are review notes, not independent pass verification.

## Handoff synchronization
- Source of truth for application code: PR commit SHA and checked-in contracts, not chat transcripts.
- Source of truth for tool registry: versioned manifest, namespaced IDs, aliases; never edit source science enum to suit UI.
- Map owner A3 controls typed vector layers and picking, A4 controls scientific raster semantics; A5 controls owner-scoped device/experiment source projections; A2 owns global selection and time transitions.
- Change requests to shared contracts require ADR and reviewers A2/A3/A4/A6; consumers cannot silently interpret a field differently.
- Parallel contributors should develop against versioned mock contracts but only merge after the actual adapter contract tests pass.
- A7 tests every risky boundary after all required merges, rather than trusting isolated green PR suites.

## Suggested red-team debate protocol
1. Primary agent writes proposal and code with explicit assumptions.
2. Independent agent (not exposed to the original argument where feasible) lists 3 failure hypotheses and attack fixtures.
3. Primary agent answers with source references and changes/tests, not arguments from authority.
4. A7 runs targeted reproducible counterexamples and records failing or passing outcomes.
5. A0 adjudicates remaining scope/UX disagreements; A4/A6 veto hard science/safety failures.
6. If no independent agent available, mark review `ROLE_BASED_NOT_INDEPENDENT`.

## Prohibited shortcuts
- "Everything is implemented" because all 94 cards are visible.
- "All 13 states have maps" because the backend SurfaceType enum includes them.
- Using a random position, plot centroid or L2 curve-fit to fabricate observed local measurements.
- Treating Python `TestClient` alone as evidence pixels rendered in actual browser.
- Updating protected main, old releases, Draft PR #28, or the scientific monograph while addressing UI tasks.
- Claiming physical field validation from controlled fixture/replay or mocked driver.
- Adding heavy or new dependencies without targeted PR/compatibility review.
## First agent handoff for P00
A0 assigns source inventory and scope; A6 owns development auth and session edge-case negative plan; A3 owns geometric fixture generation and baseline mask proof; A4 owns frozen 13-state/scientific publication fixture; A7 owns runbook execution/capture; A1/A8 own screenshot/RTL/perf baseline. Only after R0–R5 evidence should P01 launch.
