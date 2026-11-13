# P02 Candidate — Design System & Map-First Workspace Shell
**Date:** 2026-11-13  
**Status:** IMPLEMENTED CANDIDATE / SOURCE-LEVEL CHECKED / NOT BUILD OR BROWSER QUALIFIED  
**Branch:** `feat/plot-workspace-p02-responsive-shell-20261113`  
**Pinned base:** `integrate/layer0-layer1-observation-pilot@c7722405d2972a2cea95f12ac27a2a4f6848a97f`  
**Candidate before receipt:** `75b5e76afae04861d599f72c145440097825742f`. This receipt adds one documentation commit.

## Scope implemented
1. `PlotWorkspaceFeatureGate.tsx`: server-side feature gate `NEXT_PUBLIC_PLOT_WORKSPACE_V2 === "true"`, default-off path returns the original `PlotDashboard` with original props. Authenticated page route still validates plot/farm ownership before gate. **No provider ordering changes.**
2. `PlotWorkspaceShell.tsx`: responsive grid, existing PlotDashboard reused as the **single** map/legacy renderer (not rewritten), separate tool dock, context inspector, existing TimelineStrip in docked host, scientific/operational status strip. No independent ASMAE run or new publication fetching.
3. `WorkspaceToolDock.tsx`: P02 tool rail links to existing Map/Analysis/Raw/User Input flows; direct plot-ID-scoped UI-only bridge to the existing Sensors, Drone, MESIA, Irrigation, Evidence and AgriBrain Assistant workspaces. No equipment dispatch invoked by dock itself.
4. `workspace-tool-concepts.ts`: *read-only* 94-concept preview (24 Spatial, 16 Sensors, 14 Drone, 12 MESIA, 16 Simulation, 12 Temporal), searchable, grouped by family, no claims of installed or production qualified implementations. P04 will build the true capability registry, individual permissions, tools, aliases and maturity.
5. `WorkspaceContextInspector.tsx`: shows actual selected Layer10 zone ID, present lens, source snapshot identity and applicability. No invented polygon, posterior or state correlation.
6. `WorkspaceScientificStatus.tsx`: labels canonical publication loaded/pending/unavailable separately from uncertified operational IoT transport and unsealed reading count. Explicitly states loaded publication != verified rendered pixel.
7. `WorkspaceTimelineContainer.tsx` + `TimelineStrip.tsx`: move the EXISTING evidence-aware timeline to a docked host with collapse control; suppress its original instance when V2 is active. No duplicate evidence timeline or altered temporal classifications.
8. `plot-workspace-v2.css`: scoped tokens (Akaloris canopy, pine, copper), responsive desktop/tablet/mobile grid, logical RTL/LTR CSS, accessible focus, 44px+ tool targets, nonmodal Tool Library flyout and topbar stacking correction.
9. `PlotDashboard.tsx`: optional `embeddedInWorkspace` prop, scoped UI-only custom event listener, conditionally hides its duplicate timeline. V2-off behavior remains identical; source scientific map, SIRE gate and Layer10 data flows untouched.
10. `tests/frontend/plot-workspace-p02-shell.test.mjs`: six static-contract checks; new test command is `node --test tests/frontend/plot-workspace-p02-shell.test.mjs`.

## Invariants and scope exclusions
- **Python backend:** not changed; Layer0/Layer1/ASMAE/SIRE contracts unchanged.
- **Render truth:** existing `PlotMapShell` keeps qualified scientific pixels, mask and browser receipt. V2 shell cannot manufacture a scientific raster.
- **Security:** existing server-side owner scope and authenticated providers retained from P01.
- **Actuation:** `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false` remains a mandatory deployment requirement; this shell does not change backend physical action policy.
- **Future tools:** the 94-concept preview is **not** the final Tool Registry or a promise of 94 functioning programs.
- **Cross-tool shared selection:** P03 will replace UI-only interaction bridging with scoped state; P04 will own the Tool Registry. P06 will own new map feature types, P07 the 13-state explorer; P08–P13 migrate specialized workbenches and timeline.
- **Legacy workbench presentations:** some existing workspaces are full-screen overlays, so map persistence during every specialized tool is NOT YET qualified. This is a remaining UX integration gap, not a completed requirement.

## Source-level checks executed here
11 checks were evaluated against GitHub file contents at the P02 candidate branch:
`default-off-v2`, `server-route-switch`, `single-map`, `single-timeline`, `scoped-legacy-bridge`, `all-concepts`, `iot-provenance`, `responsive-rtl`, `dock-accessible`, `css-scoped`, `dashboard-unmodified-when-flag-off`. **11/11 source-level checks PASS.**
These are structural source checks only. The new Node `test.mjs` suite was checked in but **not executed** by the connector.

## Mandatory acceptance gates still NOT RUN
- `npx tsc --noEmit`, `npm run lint`, `npm run test:frontend`, dedicated P02 test and `npm run build`.
- Real browser screenshot + interaction in Chrome at 1600 / 1024 / 768 / 360 width, RTL Arabic and LTR English/French, 200% zoom and keyboard navigation.
- Tool open/close and route navigation smoke tests with actual hydrated Next/React providers; plot switch + stale event negative tests.
- Verify available/invalid/no-L10 scientific states with visible map and accurate epistemic banner; verify map pixel/legend/receipt still valid.
- Telemetry failure, slow materialization and dev bootstrap scenarios under V2 true and V2 false.
- Dense map scene performance baseline and long-run memory.
- P02 six-round independent role review and exact CI evidence.

## Release decision
**DRAFT / REVIEWABLE CANDIDATE.** Do not mark P02 `VERIFIED`, `STAGED` or `RELEASED` until the above gates are actually executed and attached. The feature flag remains OFF by default. No protected `main`, Draft PR #28 or scientific monograph changes are permitted for this UI pass.

## How to test locally (PowerShell, in repository root)
```powershell
git fetch origin
git switch feat/plot-workspace-p02-responsive-shell-20261113
node --test tests/frontend/plot-workspace-p02-shell.test.mjs
npx tsc --noEmit
npm run lint
npm run test:frontend
npm run build
# In development: set NEXT_PUBLIC_PLOT_WORKSPACE_V2=true and restart Next
$env:NEXT_PUBLIC_PLOT_WORKSPACE_V2 = "true"
npm run dev
# To restore the old page: clear the variable and restart Next
Remove-Item Env:NEXT_PUBLIC_PLOT_WORKSPACE_V2
```
**Important:** use `npm run dev` only after your environment has appropriate database/session and existing telemetry dependencies; do not claim a successful browser run from test manifests alone.
