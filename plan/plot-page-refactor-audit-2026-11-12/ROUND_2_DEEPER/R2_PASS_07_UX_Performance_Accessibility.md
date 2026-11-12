# Akaloris Plot — Round 2 / Pass 07: full screen, controls, responsiveness and performance

**Baseline SHA:** `1ee2c20119af29dd1f0a0b46c85217d91206b744`. **Observed viewport:** user-supplied 1600×900 screenshot. **Not measured:** mobile layout, FPS, GPU memory, screen reader or actual request count.

### R2-22 — P2, page structure is neither a clear farmer view nor a stable expert workspace

The primary view combines an interactive map, pipeline, raw-data sidebar, zones, heatmaps, timeline, visual lenses, sensor/MESIA/irrigation toggles, debug NDVI, science provenance, and a centrally positioned job-failure popup. The code has substantial entanglement: `PlotDashboard.tsx` 847 lines, `PlotMapShell.tsx` 1748, `useLayer10.ts` 2688, `buildLayerStack.ts` 1453, `plot-map-evidence-state.ts` 1740. Line counts are a **maintainability indicator, not measured performance**.

**Design aim:** prioritize `(1) plot identity and crop cycle, (2) evidence status and acquisition time, (3) interactive map + authoritative overlays, (4) uncertainty/explanation, (5) safe next step`. Build a separate expert workbench from the same immutable publication identity, not a different science result.

### R2-23 — P2, fixed offsets and compressed text

[`PlotDashboard.tsx#L370-L610`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx#L370-L610) positions HUD and buttons at values including `right:344px` and `calc(50% + 440px)`; publication overlay is pinned around `top:270px` ([`#L752-L777`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx#L752-L777)). `RawDataSidebar` uses fixed 320px width and top/bottom offsets ([`RawDataSidebar.tsx#L170-L207`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/RawDataSidebar.tsx#L170-L207)). Context CSS shows labels 10–11px and legend CSS text 9–11px. Likely responsive/zoom issues require browser tests. Replace absolute offsets with adaptive grid zones, panels/drawers that respect safe areas and text zoom; normal body text 14–16px, interactive tap targets ~44px.

### R2-24 — P2, production debug and scientific controls visually conflated

[`PlotMapShell.tsx#L1656-L1712`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/PlotMapShell.tsx#L1656-L1712) always includes a yellow `🔬 NDVI` debug button. The map also offers color lenses (Standard/Thermal/Chloro/Chroma) even when screenshot shows **no scientific raster**. Those visual color transforms are not independent thermal/chlorophyll measurements; each tool must say whether it changes basemap colors, an authorized raster, or is unavailable. Hide dev diagnostic tools from operational UI unless explicitly in a developer mode.

### R2-25 — P2, performance opportunities require profiling, not assumptions

- `SemanticSurfaceLayer.ts` generates pixels via a browser canvas, then wraps in DeckGL layer. Cache by `(snapshot,surface,mode,palette,geometry epoch)` and measure RGBA raster regeneration/upload time ([`#L60-L132`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/SemanticSurfaceLayer.ts#L60-L132)).
- `PlotMapShell` separates surface/zone layers (good), but `onAfterRender` repeatedly rebuilds a layer-id set and offers a receipt; measure frequency before optimizing.
- `usePlotFit.ts` calculates simplified geometry with turf and auto-fits on dimension/plot changes; verify resizing does not unexpectedly reset user pan/zoom.
- Telemetry polls every 30s, worker progress ~1.5s, visual tile status separately. Measure request volume and abort resource handling after tab/plot switches; do not presume a leak.
- No full browser CPU/GPU flamegraph or memory data was recorded; all performance claims here are **hypotheses and instrumentation needs**, not benchmarks.

### Proposed screen

```text
PlotOperatingShell [owner-scoped, publication-scoped]
  CompactHeader: plot | crop cycle | evidence age | publication status
  TabRail: Overview | Scientific Layers | Evidence | Operations | History
  MapCanvas: user polygon + basemap; authorized scientific overlays optional
  NonblockingJobStatus: durable worker state, exact snapshot/trace ID
  MapLegend: provider, acquisition, unit, resolution, authority, uncertainty
  RightEvidenceDrawer: selected cell/zone source, dates and verification steps
  LowerTimeline: immutable publication evidence vs uncertified live telemetry
  DevInspector [explicit opt-in]: NDVI debug, render/transport diagnostics
```

### Test criteria

- Viewport 360px, 768px, 1024px, 1600px; 200% text zoom; Arabic RTL and English LTR; keyboard only.
- All controls labeled and reachable, no obscured map-status overlay, no motion-dependent understanding.
- Unpublished state has informative empty panel, **not** error full-screen blocker; basemap remains usable.
- On accepted publication, exact raster/legend/provenance cohere; no false “thermal sensor” claim from color lens.
- Instrument `requests/min`, `runCount`, `activeTimers`, `canvasRasterizations`, `GPU upload`, `memory after 20 plot changes`, accessibility errors.