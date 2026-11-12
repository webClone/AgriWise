# Akaloris Plot Page — Pass 04: MapLibre/DeckGL, Raster/Mask Geometry, Legend, and Render Receipts

> **Audit evidence scope:** Static GitHub source inspection pinned to commit `1ee2c20119af29dd1f0a0b46c85217d91206b744` and the provided 1600×900 browser screenshot. Files were retrieved from the repository and inspected structurally; selected control-flow paths were deep-traced. No local Next.js/FastAPI runtime, tests, browser automation, or production hardware was executed. Findings distinguish observed screenshot behavior, confirmed source behavior, and test-required hypotheses.


## Pass coverage

- Source files inventoried and inspected: **23/23 (100% of this pass’s selected static inventory)**.
- Detailed data-flow traced: **9/23**
- Browser/runtime verification: **0 executed sessions** (source-and-screenshot audit only).

### Sources inspected

- [`src/components/farm/map/PlotMapShell.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/PlotMapShell.tsx) — **detailed trace**
- [`src/components/farm/map/buildLayerStack.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/buildLayerStack.ts) — **detailed trace**
- [`src/components/farm/map/layers/SemanticSurfaceLayer.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/SemanticSurfaceLayer.ts) — **detailed trace**
- [`src/components/farm/map/layers/ContourSurfaceLayer.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/ContourSurfaceLayer.ts) — structural scan
- [`src/components/farm/map/layers/UncertaintyGridLayer.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/UncertaintyGridLayer.ts) — structural scan
- [`src/components/farm/map/layers/UniformEvidenceTintLayer.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/UniformEvidenceTintLayer.ts) — structural scan
- [`src/components/farm/map/layers/zones/UnifiedZoneLayer.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/zones/UnifiedZoneLayer.ts) — structural scan
- [`src/components/farm/map/layers/zones/zoneUtils.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/zones/zoneUtils.ts) — **detailed trace**
- [`src/components/farm/map/layers/zones/ZoneGlowLayer.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/zones/ZoneGlowLayer.ts) — structural scan
- [`src/components/farm/map/layers/zones/ZoneChip.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/zones/ZoneChip.tsx) — structural scan
- [`src/components/farm/map/layers/NdviDebugOverlay.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/NdviDebugOverlay.tsx) — structural scan
- [`src/components/farm/map/usePlotFit.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/usePlotFit.ts) — structural scan
- [`src/components/farm/map/sceneProviders.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/sceneProviders.ts) — structural scan
- [`src/components/farm/map/utils/buildPolygonMask.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/utils/buildPolygonMask.ts) — **detailed trace**
- [`src/components/farm/map/PlotScientificLegend.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/PlotScientificLegend.tsx) — **detailed trace**
- [`src/components/farm/map/SurfaceLegendBar.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/SurfaceLegendBar.tsx) — structural scan
- [`src/components/farm/map/plot-scientific-legend.css`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/plot-scientific-legend.css) — **detailed trace**
- [`src/lib/agribrain/render-materialization.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/render-materialization.ts) — **detailed trace**
- [`src/lib/agribrain/source-policy-display-resolver.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/source-policy-display-resolver.ts) — **detailed trace**
- [`src/lib/agribrain/surface-contract.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/surface-contract.ts) — structural scan
- [`src/lib/agribrain/surface-legend-meta.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/surface-legend-meta.mjs) — structural scan
- [`src/lib/agribrain/plot-geometry.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/plot-geometry.ts) — structural scan
- [`src/lib/agribrain/pixel-inspector-authority.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/pixel-inspector-authority.mjs) — structural scan

## Why the screenshot can show a beautiful field but no science

[`src/components/farm/map/sceneProviders.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/sceneProviders.ts) supplies Esri/dynamic basemap raster tiles. [`src/components/farm/map/PlotMapShell.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/PlotMapShell.tsx#L823-L934) renders those with MapLibre/DeckGL plus a polygon boundary. The separate **canonical scientific surface** is authorized by [`src/lib/agribrain/source-policy-display-resolver.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/source-policy-display-resolver.ts), [`src/lib/agribrain/render-materialization.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/render-materialization.ts), [`src/lib/agribrain/plot-map-evidence-state.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/plot-map-evidence-state.ts) and [`src/components/farm/map/buildLayerStack.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/buildLayerStack.ts). Therefore **base imagery visible ≠ NDVI/ASMAE raster published**. The screenshot's “No scientific surface” is consistent with that separation.

### Findings

| ID | Priority | Code | Assessment / fix |
|---|---|---|---|
| MAP-01 | P1 | [`src/components/farm/map/utils/buildPolygonMask.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/utils/buildPolygonMask.ts#L27-L38) and [`src/components/farm/map/utils/buildPolygonMask.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/utils/buildPolygonMask.ts#L81-L105) | **Polygon mask drops geometry.** For `MultiPolygon`, only `coordinates[0][0]`; for Polygon only exterior `[0]`. Interior holes and additional polygons are ignored. This can draw scientific pixel overlays in excluded areas. Replace with canonical Polygon/MultiPolygon-with-holes point containment; test ring orientation, holes, disjoint pieces, winding, antimeridian. |
| MAP-02 | P1 | [`src/components/farm/map/utils/buildPolygonMask.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/utils/buildPolygonMask.ts#L25-L33) | **Mask cache key omits geometry hash / epoch.** `${plotId}-${width}-${height}-${boundsKey}` can reuse old mask after boundary changes with unchanged plot/grid bounds. Key on canonical geometry digest and surface grid/bounds; invalidate after edits. |
| MAP-03 | P2 | [`src/components/farm/map/layers/zones/zoneUtils.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/zones/zoneUtils.ts#L381-L405) / [`src/components/farm/map/layers/NdviDebugOverlay.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/NdviDebugOverlay.tsx#L48-L61) | Similar first-ring-only handling appears in zone geometry and NDVI debug; they may disagree with the canonical mask. Consolidate geospatial conversion and clipping into one library with exact geometry epoch. |
| MAP-04 | P2 | [`src/components/farm/map/PlotMapShell.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/PlotMapShell.tsx#L839-L891), [`src/lib/agribrain/render-materialization.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/render-materialization.ts#L393-L464) | **Render receipt is linked to layer presence and DeckGL `onAfterRender`, not a screenshot of visible pixels.** Retain it as structural materialization evidence, add Playwright visible-canvas/screenshot assertion for the actual scientific surface, pixel bounds and aligned legend. |
| MAP-05 | P2 | [`src/components/farm/map/PlotMapShell.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/PlotMapShell.tsx#L1666-L1676) | **Developer “🔬 NDVI” debug is always drawn**, even when canonical NDVI absent. Gate behind authorized development/expert debug mode, and make screenshot-only basemap state explicit. |
| MAP-06 | P2 | [`src/components/farm/map/PlotMapShell.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/PlotMapShell.tsx#L896-L899) | MapLibre `attributionControl={false}`; imagery is displayed without the native attribution control. Review provider attribution requirements and provide visible compliant attribution (not simply disabling the control). |
| MAP-07 | P2 | [`src/components/farm/map/layers/SemanticSurfaceLayer.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/layers/SemanticSurfaceLayer.ts#L60-L180), [`src/components/farm/map/buildLayerStack.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/buildLayerStack.ts) | Large CPU canvas/mask/layer assembly occurs in a changing React/DeckGL tree. Profile actual rebuilds on pan/hover/zoom; memoize by surface digest + authorization + geometry epoch, and avoid regenerating canvases on nonsemantic pointer events. Actual FPS/memory was not measured. |
| MAP-08 | P2 | [`src/components/farm/map/PlotScientificLegend.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/PlotScientificLegend.tsx#L24-L63) / [`src/components/farm/map/plot-scientific-legend.css`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/plot-scientific-legend.css) | Scientific evidence legend is honest about missing science but tiny and visually crowded; mobile media rules hide rows. Make compact badge plus expandable evidence drawer rather than hiding provenance. |
| MAP-09 | P2 | [`src/components/farm/map/SurfaceLegendBar.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/SurfaceLegendBar.tsx) / [`src/lib/agribrain/surface-legend-meta.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/surface-legend-meta.mjs) | Palette and physical legend must derive from one committed surface scale. Visual color lens is stylistic only, never a scientific value change. Negative test when surface absent or nonspatial. |

### New map architecture

```text
PlotMapCanvas (MapLibre basemap, polygon boundary, attribution)
  ├─ ScientificSurfaceController (snapshot-scoped authorized layer selection)
  │    ├─ CanonicalGridValidator (CRS, extent, transform, mask, epoch)
  │    ├─ SurfaceRasterLayer (materialize committed pixels)
  │    ├─ AuthorizedZoneLayer (zones tied to materialized surface)
  │    └─ RenderReceiptCollector (actual committed identities)
  ├─ ScientificLegend (source/date/resolution/uncertainty/authority)
  ├─ ToolDock (inspection, transect, palette; permission-aware)
  └─ MapStatus (basemap only / ready / degraded / no science)
```

### Tests before refactor completion

1. Polygon with a hole: hole has zero pixel materialization.
2. Multipolygon: both independent areas render, intervening area does not.
3. Edit same plot geometry while keeping same bounding box: cache invalidates and old pixels disappear.
4. Invalid/missing grid transform: no scientific pixels, no positive render receipt.
5. Authorized NDVI raster: actual browser canvas nontransparent in expected cells, correct legend, snapshot/content hash recorded.
6. `canRenderPixels=false` / no surface: only satellite basemap and truthful no-science marker; no fabricated NDVI debug data.
7. Screenreader reads source date, units, spatial resolution and evidence tier. Attributions visible.

**Not tested:** WebGL browser output, MapLibre engine, mobile interactions, actual spatial alignment with real Plot-A data.