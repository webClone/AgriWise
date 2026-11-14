# P04 Candidate 03 — Native spatial host extraction (draft)

**Base:** P04 Candidate 02 `599c4f6162c9795ad6e54b262bf8d7abfc50648d`  
**Branch:** `feat/plot-workspace-native-spatial-canvas` (stacked on PR #30)

## Exact architectural replacement

The V2 `PlotWorkspaceShell` no longer imports or mounts `PlotDashboard`. The new `WorkspaceNativeSpatialCanvas` mounts the existing scientifically guarded `PlotMapShell` directly, preserving layer, map, zone, polygon, rendering and pixel validation contracts. It triggers the same canonical ParcelAssessment acquisition previously initiated by `PlotDashboard`, without introducing a second provider or independent Layer10 request.

`WorkspaceExistingToolHost` preserves the six existing tool entry points and removes the P02 browser-global UI event bridge in V2. `WorkspaceLegacyTimelineBridge` temporarily forwards the already-validated Layer10 projection to the existing TimelineStrip via PlotIntelligence until the native timeline is delivered. A plot/selection match is now required to offer contextual zone actions.

The unmodified V2-off feature gate still renders the existing standalone PlotDashboard. Production synthetic zone/test-launch hooks are disallowed.

## Qualification / scope limits

This is an **implementation candidate**, not a qualified completed native spatial engine. Full frontend tests, TypeScript compiler, production build and actual browser map workflow must be independently executed on the exact branch HEAD. Browser steps must involve genuine `PlotMapShell` selection; a development custom event or synthetic zone injection is NOT evidence of map click functionality.

Migrate/qualify the remaining standalone specialized tool screens and replace the legacy timeline separately. The underlying proven MapLibre/DeckGL scientific renderer is intentionally reused; do not rewrite the pixel/receipt masking contracts.

## Acceptance

- V2 on: one map, zero legacy PlotDashboard mounts, no duplicate provider or acquisition.
- V2 off: original legacy dashboard and controls functional.
- Layer10 map rendering/polygon/contour mask, selected zone, proper authoritative publication failure state.
- Timeline receives the current plot's canonical Layer10 projection with no stale-scientific promotion.
- Existing specialized tools still open and close with plot-scope correctness and no physical dispatch claims.
- Full frontend, TS, build, negative control and browser desktop/RTL/mobile receipts on precise commit.
