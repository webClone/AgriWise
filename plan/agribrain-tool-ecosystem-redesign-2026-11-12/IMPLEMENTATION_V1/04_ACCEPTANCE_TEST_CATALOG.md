# Unified Adversarial Acceptance Catalog — Cross-Pass Test Specifications
**Status:** test specifications, NOT executed.
## Test harness tiers
T0 static architecture/parity; T1 pure unit; T2 owner-authenticated route; T3 Python science/geometry and source protocols; T4 Next API integration; T5 actual browser map/hardware simulator, screenshots/receipts; T6 controlled staging; T7 genuine physical device/field validation (separate HOLD).
## Global P0 assertions
1. No user can enumerate or select foreign tenant's plot, feature, device, mission, or scientific publication.
2. No map pin without source-supported WGS84/CRS geometry; no mask fill in polygon holes or outside all MultiPolygon members.
3. No past scientific snapshot may include observation whose `first_available_at` is beyond its cutoff.
4. No renderer can show authoritative raster if its owner/geometry/grid/surface/numerical/publication proof invalid.
5. Mock drone/PTZ/irrigation returns never imply physical execution. Physical irrigation dispatch remains 0 under flag=false.
6. No treatment instructions without required scientific evidence and signed/authorized action contract.
7. Experiment/model proxy/forecast/hypothesis not presented as observed empirical field evidence.
## Tool-source adversarial cases by subsystem
**Sensors:** registered-without-coordinate; coordinate changed after last reading; inactive device; unknown depth; calibration expiry; replayed message ID; sensor timestamp future skew; late knowledge; spoof packet reusing ID; conflicting sensor family; device with wrong farm.
**Drones:** target zone wrong geometry epoch; plan with 0 points; infeasible high-resolution leaf-level full plot; mock driver; missing GPS; planned route moved to another plot; stale history in-memory; mixed actual+planned track; invalid orthomosaic GSD; tampered frame provenance.
**MESIA:** receiver health UNKNOWN; frequency observable but spatial position absent; antenna pose drift; blind band; noisy/collision RF event; unavailable physical experiment DB; hardcoded invariant fallback; simulation presented as measured; wrong receiver/plot.
**ASMAE/SIRE:** only 1 scalar posterior but 13 registry entries; raster with bad mask/hole; missing sigma; corrupt node/inventory/receipt; false numerical binding; reused plot+wrong snapshot; old snapshot after new head; invalid source edge; L2 curve mislabeled L1 observation.
**Tools/UX:** 94 discovery count via aliases; disabled tool can configure but not execute; stale tool open after plot switch; multi-panel simultaneous selection; Arabic mixed LTR IDs; 200% zoom; screen reader without canvas; failing map tiles; large scene.
## Mandatory cross-panel end-to-end scripts
### E2E-01: authenticated sensor across map and ASMAE
Given plot P, sensor S at registered location and a late unadmitted record: open map, select S, verify sensor list focus/coordinates/depth, select root_zone_water, compare only historical admissible state, assert late record marked unadmitted, changing plot removes S.
### E2E-02: SIRE zone → planned drone path → optional actual track
Given qualified zone Z with source publication ID: choose Z, open Drone Planner, edit overlap/GSD, assert same Z and updated dashed planned path; simulate dispatch and assert no solid physically executed path; optional authenticated real flight fixture shows separate solid timestamped track.
### E2E-03: MESIA receiver → lab → experiment
Given registered receiver with frequency coverage and unknown area: select receiver, inspect real manifest and UNKNOWN map coverage, open controlled experiment, run simulated preview, assert experimental watermark, no ASMAE science update.
### E2E-04: true publication → API → browser
Given real backend canonical publication: verify signed FastAPI exact response, Next proxy exact identity and numerical+temporal proof, map pixel/legend/valid mask and DeckGL materialization receipt. Tamper receipt/inventory/geometry -> no authoritative rendering.
### E2E-05: historical replay vs live
Given Sept publication and Nov device now: scrub to Sept with knowledge cutoff, assert Nov live reading not added to historical scene and no silent projection; choose older exact snapshot, verify no fallback to current on 404/409.
### E2E-06: sandbox A/B comparison
Select a qualified zone and immutable current snapshot, open What-if, adjust rainfall, run two variations; synthetic overlay marked simulated, original publication untouched, quote source/time/assumptions and correct units.
### E2E-07: farmer and expert UI accessibility
With keyboard only select state, zone and sensor; launch tool with Dock, inspect timeline, collapse/restore panels; repeat at 360/768/1024/1600, RTL Arabic and LTR English/French; no clipped key details.
### E2E-08: severe concurrency and reset
Open Drone, Sensors, MESIA; issue three slow API calls; switch to different plot; all previous responses ignored, map layers cleared, telemetry stream scope reset, tool host doesn't show foreign data.
### E2E-09: no-data / planned tools
Disable scientific service and all real hardware; map still works as basemap with plot boundary; catalog remains complete, 13 ASMAE states show reason unavailable, drone simulator labeled and physical actions disabled, MESIA setup accessible.
### E2E-10: actuation isolation
Try calling all UI action affordances while observe-only flag false; measure 0 real irrigation commands, no real drone/mast control without trusted hardware permission; no client-only toggle bypass.
## Test commands (verify with package and environment before running)
```powershell
# App source checks from repo root (Windows PowerShell)
npx tsc --noEmit
npm run lint
npm run test:frontend
npm run build
# For added targeted suites:
node --test tests/frontend/<new-suite-name>.test.mjs
# Backend scoped suites:
py -m pytest services/agribrain/tests/<selected-test-file>.py -q
```
Playwright/browser harness is proposed, not in package.json at audited head. Install/configure only through approved implementation PR, not just to produce a report.
## Acceptance evidence grading
For every test: ID, repo SHA, fixture source & synthetic/field classification, command, exact started/finished time, raw exit code/test output, screenshots/trace if browser, expected vs actual, reviewer identity, dependencies, and reason PASS/FAIL/BLOCKED. 'Operator reported 170 tests' from a prior milestone does not qualify the new UI passes automatically.
## Release gate
Any P0 FAIL or missing physical-claim provenance means HOLD. Staging UI can pass with physical MESIA/drone experiments explicitly NOT TESTED, so long as no product claim of physical operation is made. Tool discovery and research simulations may be released separately from actual hardware.
