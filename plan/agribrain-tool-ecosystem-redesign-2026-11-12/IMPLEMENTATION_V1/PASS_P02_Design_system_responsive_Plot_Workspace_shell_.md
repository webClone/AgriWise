# P02 — Design system, responsive Plot Workspace shell and tool-preserving navigation
**Status:** NOT STARTED · design-to-code pass · **Dependency:** P00,P01  
**Owner agents:** A1+A2+A8 · Independent red-team: A7 with A6/A4 as applicable  
**Proposed code branch:** `feat/plot-workspace-p02-shell` (does not exist yet).
## Goal, existing constraints and proposed boundary
Implement the visible reusable layout without removing existing functionality: map-first center, persistent Tool Dock, context inspector, multi-lane timeline host and nonblocking activity center. Use versioned UI flag and retain old layout.
## Source paths to inspect and likely modify (paths grounded in repository, proposed new names clearly marked)
- `src/app/farm/[id]/plot/[plotId]/PlotLayoutClient.tsx`
- `src/components/farm/PlotDashboard.tsx`
- `src/components/farm/PlotContextBand.tsx`
- `src/components/farm/FarmThemeWrapper.tsx`
- `src/components/farm/map/plot-scientific-legend.css`
- `src/components/farm/intelligence/TimelineStrip.tsx`
- `src/components/farm/workspace/ (proposed new)`
- `src/styles/ or existing global styles (inspect before changing)`
## Ordered implementation work packages
### P02.01 — Author component and token sheet
Define contrast-checked semantic surface colors, map-layer legend, epistemic badges, elevation/spacing/typography, dark/light variants and motion rules. Implement locale-safe numbers and design-compatible Arabic RTL, French/English LTR.

### P02.02 — Create layout scaffolding
Make `PlotWorkspaceShell` with header, compact icon+label Dock, main canvas, inspector and timeline slot. Use resizable panel bounds; don't cover map with absolute-position competing HUD elements.

### P02.03 — Preserve old navigation
Add V2 feature flag default OFF; legacy `PlotDashboard` and its tools remain reachable. Provide explicit app-route fallback without hydration differences, missing providers or hidden tool controls.

### P02.04 — Build semantic status display
Use publication-as-of, live telemetry health and worker progress as separate status chips; keep map usable when science unavailable. Distinguish historic scientific layer from real-time device data.

### P02.05 — Accessibility interactions
Implement keyboard tool launcher, focus return, skip map, screen-reader entity list, clickable 44px touch targets, reduced motion, tooltips not dependent on hover, 200% zoom.

### P02.06 — Responsive behavior
At 1600 use 5-column functions; 1024 collapsible inspector; 768 compact dock; 360 bottom sheets and persistent map. No off-screen legends or time rail overlap.

### P02.07 — Tool entry parity smoke suite
Every existing entry point should still open the right capability, with explicit unavailable/simulation state. No mini-map duplication or forced full-screen whenever tool selected.
## Adversarial regression and acceptance matrix
- **P02-G01** V2 OFF matches old route behavior; toggling OFF at runtime restores old page.
- **P02-G02** A screen-reader/keyboard user can select tool, map entity and timeline without pointer.
- **P02-G03** RTL labels/panel edges, popovers and focus order correct at 360/768/1024/1600.
- **P02-G04** A valid old publication remains legible when new run pending.
- **P02-G05** Existing Drone/Sensors/MESIA/Irrigation/Scientific controls remain reachable.
## Evidence package and closure conditions
- Design tokens and annotated layouts at four widths × RTL/LTR.
- Tool-entry parity and screenshots, accessibility checklist.
- Feature flag + documented fallback and zero-deletion migration report.
- Review gate from A1/A2/A8 + independent A7 browser smoke.
**HOLD if:** lost core control, unusable map, invisible trust status or broken RTL.

### Independent multi-agent challenge
- **R0:** owner pins exact baseline, collects negative fixtures, reads competing provider contracts.
- **R1:** A1+A2+A8 produce initial implementation rationale and a separate critique before integration.
- **R2:** A4/A6 check science, ownership and interlock; A3 checks geometry where touched; A1 checks labels and tool discoverability.
- **R3:** A7 writes and runs adversarial tests; report failing-old and passing-new evidence, not fabricated counts.
- **R4:** A2/A8 inspect actual browser where UI changes, cleanup/RTL/perf and no invisible regression.
- **R5:** A0 records exact SHA, test receipts, explicit `GO/CONDITIONAL/HOLD`, unresolved risks and rollback.
