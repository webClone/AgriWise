# Akaloris P06 — Map Scene Candidate 01 / Engineering Receipt

Base: P06 temporal candidate **215323d** (full SHA on GitHub: 215323dc8660971f9a20c71619535fc932f271ca).  
Feature branch: `feat/plot-workspace-p06-map-scene`.  
Canonical draft PR #30: **untouched** at 599c4f6.  
Scope: P06.01 scene registry and initial P06.02 interaction parity; not the full P06.01–P06.10 plan.

## Delivered
- Pure six-family scene registry: scientific raster, management zones, sensors, cameras, drones, field observations. Dynamic counts use tenant/farm/plot-scoped envelopes, not unverified metadata.
- P03 safe presentation reducer actions: `TOGGLE_SCENE_LAYER`, `SET_LAYER_OPACITY`, `SET_ALL_LAYERS_VISIBILITY`. None changes a publication, evidence or hardware authority state.
- Responsive floating Layers / Entities controls with independent toggles, opacity sliders, show/hide all, keyboard-focusable entity and zone directory. Catalog retains unlocated devices with explicit list-only label.
- Scientific surface visibility is independent of zone and vector visibility. `PlotMapShell` still calls `buildLayerStack` and `createCommittedRenderReceipt`; hidden raster layers are absent from the post-render committed layer-ID set and cannot establish a displayed pixel receipt.
- Per-kind entity pin gating and halo color alpha, preserving simulated-fixture colors and actual Layer10/pixel scientific source policy.
- Coincident DeckGL picks open a keyboard-focusable disambiguation chooser rather than silently selecting one pin; selected registered coordinates center the map. View changes never synthesize positions for unknown locations.
- Scope change resets selection through P03 and filters counts; overlap chooser closes on generation/visibility changes.

## Executed here
- Pure JS scene registry/reducer regression suite: **8/8 passed**, directly executed in a V8 runtime from the committed GitHub source.
- Repository source checks for mapped controls and route boundaries.
- **Not executed:** `npm run test:frontend`, `npx tsc --noEmit`, `npm run build` or actual Chrome, because this edit uses the GitHub connector without the user's application runtime.

## Local qualification, required before accepting P06 map scene
1. Run `node scripts/run-frontend-tests.mjs`, `npx tsc --noEmit`, `npm run build` on the **exact branch HEAD**, and correct any integration failures.
2. With V2 on, load a known plot containing raster, zones, sensor, camera, drone and observation.
3. Hide scientific raster: zone and sensor remain visible and clickable; ensure no scientific raster render receipt is claimed while hidden.
4. Switch scientific lens with Sensors/Cameras enabled: vector layers and selection remain.
5. Disable each family independently; check layer counts, opacity, show/hide all, simulation badge and keyboard directory.
6. For two pins with the same WGS84 coordinates, click their visible location and select each via the overlapping picker (mouse and keyboard/Escape). No hidden or foreign plot entity may appear as an option.
7. Select a registered sensor from directory and confirm camera centers on its actual position; choose an unlocated device and confirm no invented camera target.
8. Switch plots rapidly with pending entity fetches; confirm previous plot's counts, pins, picker and selection disappear.
9. Verify pixel-mask/geometry/source authorization remains unchanged against P05/P06 Candidate 01 receipts; actuator gate remains disabled.

This is a usable engineering candidate, **not a browser-qualified production release**. Planned drone tracks, generalized polygon overlays, clustering/LOD, touch parity and P13 dual-publication scientific comparison remain future slices.
