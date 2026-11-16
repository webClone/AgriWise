# Akaloris P07 — Spatial Workspace Experience, Candidate 01

**Base:** accepted P06.05 `dd73cbd7ca104f36443400a96cfdb34e60810606`  
**Branch:** `feat/plot-workspace-p07-workspace-experience`  
**Canonical Draft PR #30:** unchanged at `599c4f6`  
**Scope:** UX-only consolidation; no scientific publication, geometry persistence, evidence qualification or actuator changes.

## Delivered in Candidate 01
1. **Canvas dominance:** the continuously floating Color Lens / Spatial Analysis block is a compact, expandable control on the right edge in native V2 only; its old controls, palette IDs and scientific cross-section gate are reused, not reimplemented. The V2 map viewport is unobscured when closed. The standalone legacy PlotMapShell still presents its original dock and coordinates.
2. **Drawing / revision states:** P03 shell sets `data-spatial-mode` for idle/selected/drawing/revising. Drawing uses a pointer-transparent border and accessible authoring status; the authoring HUD clears the header by respecting topbar clearance. The existing selection and Layer10 drawing interlocks remain unchanged.
3. **Publication display:** scientific status compresses to one operable disclosure pill. Expanding reveals the canonical publication status and snapshot, and a **separate** operational IoT/unsealed count. Availability does not claim scientific raster-render authority.
4. **No new interpretation:** visual color lenses continue to be display-only, cross-section is still authorized by `inspectorDiagnosisAllowed`, and physical actuation remains disabled in the pilot.

## Qualification still required locally
- `node --test tests/frontend/p07-workspace-experience.test.mjs`
- `node scripts/run-frontend-tests.mjs`
- `npx tsc --noEmit`
- `npm run build`
- **Browser V2:** at 1600x900 and mobile, verify View & analysis opens and closes without covering plot by default, palettes still switch, and Cross-section stays unavailable when no authorized scientific surface exists.
- **Browser modes:** start new drawing and graphical revision, verify crosshair/highlight status and that normal zone/entity selection remains suppressed. Close or cancel; previous selection and normal pointer behavior return.
- **Publication:** expand status and verify that the unsealed operational count is clearly not scientific evidence. On a valid publication, only claim source availability—not rendered pixels absent a browser render receipt.
- **V2 off:** verify legacy PlotDashboard and unchanged PlotMapShell control dock.

## Follow-on P07 UX slices
- Move the View & analysis trigger *into* the unified scene header to eliminate a second right-rail entry point, while keeping cross-section authority owned by PlotMapShell.
- Improve the Context Inspector's selected entity hierarchy: overview, registered geometry metrics, revision provenance, and prioritized actions.
- Responsive position testing for status / authoring HUD / scene controls / inspector on short windows and touch devices.
- Do not interpret the screenshot's absence of admitted scientific publication as an error in the visual basemap.
