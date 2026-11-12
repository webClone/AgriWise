# P13 — Unified event timeline historical time peel correlation and provenance explorer
**Status:** NOT STARTED · **Dependency:** P05,P07,P08,P09,P10,P11,P12 · **Primary agents:** A2+A4+A7 · **Independent reviews:** A4 science, A6 security/safety, A7 adversarial QA, A8 UX release as applicable  
**Proposed code branch:** `feat/plot-workspace-p13-temporal-replay` (not created).
## Goal and critical boundaries
One multi-track time rail for satellite acquisitions, sensor/receiver readings, drone plans/telemetry, field operations, experiments and published scientific snapshots. Timeline, map and right panels must use the same explicit temporal/knowledge basis, including historical access rules. Correlation means navigation and association, not automatically causal explanation.
## Code paths and anticipated integrations
- `src/components/farm/intelligence/TimelineStrip.tsx`
- `src/lib/agribrain/telemetry-contract.mjs`
- `src/hooks/usePlotTelemetry.ts`
- `src/hooks/useLayer10.ts`
- `services/agribrain/layer10_sire/temporal_bundle.py`
- `services/agribrain/layer05_asmae/retrovalidation/ (relevant selected modules)`
- `services/agribrain/drone_mission/mission_history.py`
- `services/agribrain/ground_truth/registry.py`
- `src/components/farm/workspace/WorkspaceTimeRail.tsx (proposed)`
- `src/components/farm/workspace/EvidenceRelationshipInspector.tsx (proposed)`
## Detailed implementation tasks
### P13.01 — Define full temporal semantics
Observed_at, available_at, ingested/accepted, published_at, valid_for and time-since; knowledge cutoff separated from displayed calendar date. Each event type must identify its own clock and trust source. Handle timezone and user locale.

### P13.02 — Build normalized event ledger projection
On read, source-specific event adapters join only immutable event IDs and actual provenance, preserving source type and scope. Sensor alert currently stderr diagnostic; cannot appear as durable historical alarm until persisted.

### P13.03 — Multi-lane timeline UI
Tracks: satellite scene, sensor, MESIA radio, drone mission, plot operations, camera/photo/field sample, ASMAE science, Layer10 publication, experiment/simulation and forecast. Zoom day/week/season and filters with no events explanation.

### P13.04 — Historical publication selector
Select explicit canonical immutable snapshot ID available at replay knowledge cutoff; no fallback to newer head for exact snapshot reads. Preserve old snapshot's crop cycle and geometry. Wrong plot snapshot rejected.

### P13.05 — Historical map scene materialization
Scrubbing restores time-valid polygons/raster, mission flown path segments, sensor readings and task states; today's live status always separately marked live, never injected into past. Forecast slice labeled projected; L2 curve-derived retrospective labeled proxy, not actual scene.

### P13.06 — Evidence relationship graph
Show explicit IDs: observed source→admitted evidence→ASMAE state update→SIRE publication→browser render. Nearby/overlap relations flagged correlational. Only data-lineage/receipt can say a particular reading contributed.

### P13.07 — Time/selection handling
Selected zone/source from old publication retained as historical reference or removed with explicit reason; no automatic ID remap. Browser moving time cursor doesn't mutate backend state or trigger new scientific run unless user explicitly chooses.

### P13.08 — Playback interaction and performance
Scrub requests debounced and cancelable, cached exact snapshot keyed by owner+geometry+publication. Reuse map layers and render receipts tied to current selected scene; pointer hover and event lists load only visible interval.

### P13.09 — Causality explanation UX
'Related events' list with class `spatially_close / temporally_close / explicitly_correlated / source_contributed`. No invented causal certainty. Users can open the same event in Sensors/Drone/MESIA/ASMAE/Experiment.

### P13.10 — Adversarial replay suite
Try observation timestamp before cutoff but first-available timestamp after; out-of-order event delivery; timezone offset; future forecast; corrupt old publication; replay with missing geometry; simultaneous live alert. Check all surfaces.
## Pass acceptance / adversarial cases
- **P13-G01** Historical cutoff rejects later-known sensor/drone/MESIA observation.
- **P13-G02** Exact snapshot selection never silently upgrades to current head.
- **P13-G03** L2 fitted historical curve not marked observed L1 raster.
- **P13-G04** Selecting timeline event highlights map geometry when real, otherwise list/plot scope only.
- **P13-G05** Time scrub cancels old requests and preserves temporal truth on every panel.
- **P13-G06** Data-lineage causal edge requires source receipt; proximity cannot claim contribution.
- **P13-G07** Farmer and expert timeline use same underlying event IDs and timestamps.
- **P13-G08** Live 30s telemetry refresh doesn't rewrite historical publication.
## Evidence needed to close
- Temporal schema/source ledger with explicit observed/known/published/valid times.
- Multi-track timeline UI, source availability view and correlated map screenshots.
- Reproducible historic replay with future-leak adversarial fixture.
- A4/A7 proof of exact historical publication and evidence graph semantics.
**HOLD:** any future-observation leakage, false observed classification or snapshot identity substitution.
## Multi-agent R0–R5 protocol
R0 pin exact source & immutable fixture; R1 owner writes proposal and independent reviewer separately critiques; R2 A4+A6/A3 challenge math, source identity, device safety, security and geometry; R3 A7 executes negative tests; R4 A2+A8 perform integrated real-browser and performance review where UI changes; R5 A0 issues signed GO/HOLD with exact commit, logs, rollback and remaining risks. None of these reviews should be marked complete until actually executed.
