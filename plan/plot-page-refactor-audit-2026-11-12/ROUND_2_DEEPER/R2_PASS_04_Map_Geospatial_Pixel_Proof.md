# Akaloris Plot — Round 2 / Pass 04: geometric correctness and actual raster rendering

**SHA:** `1ee2c20119af29dd1f0a0b46c85217d91206b744`. **Runtime:** no mounted DeckGL, GPU capture, or Playwright.

### R2-10 — P1, first outer ring masquerades as whole plot

[`buildPolygonMask.ts#L16-L121`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/utils/buildPolygonMask.ts#L16-L121) chooses `geometry.coordinates[0][0]` for MultiPolygon and `geometry.coordinates[0]` for Polygon. It tests pixel centers against only that ring. **Interior holes are not subtracted; other multipolygon islands are ignored.** [`usePlotFit.ts#L44-L89`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/usePlotFit.ts#L44-L89) similarly calculates viewport extent from first ring only. A MapLibre polygon outline can therefore disagree with raster masking and zone membership.

**Adversarial fixture:** Polygon exterior square `(0,0)-(4,4)` with hole `(1,1)-(3,3)` must exclude a pixel centered `(2,2)`. Multipolygon islands `(0,0)-(1,1)` and `(3,3)-(4,4)` must include both island centers. Current first-ring handling cannot do both. Implement full Feature/Polygon/MultiPolygon + holes and validity checks; use one topology engine for mask, fit and zone clipping.

### R2-11 — P1, stale mask after geometry edit

`buildPolygonMask()` caches under `plotId-width-height-boundsKey`, **not geometry hash/epoch** ([`#L25-L32`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/utils/buildPolygonMask.ts#L25-L32)). Edit vertices without changing raster bounds and dimensions: the first polygon's mask may be reused. Key by `(tenant,plot,geometryHash,geometryVersion,gridSpecHash,resolution)`; invalidate on crop/geometry scope edits. Test A→B→A with same bounding box and no explicit cache clear.

### R2-12 — P1 conditional, failed spatial mask can turn into unmasked grid

The helper returns null on unsupported/malformed geometry. [`buildLayerStack.ts#L1106-L1178`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/buildLayerStack.ts#L1106-L1178) counts full grid cells when no mask is present in a zone extraction branch. Exact rendering combination still requires E2E testing; this fail-open fallback is not appropriate for **scientific bounded-zone claims**. On mask failure block scientific geometry/zone support, but allow base satellite imagery.

### R2-13 — P2, rendered receipt is not on-screen pixel proof

[`PlotMapShell.tsx#L823-L895`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/PlotMapShell.tsx#L823-L895) runs `DeckGL.onAfterRender`, collects configured layer IDs, and creates a `BrowserRenderReceipt`. [`render-materialization.ts#L393-L465`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/render-materialization.ts#L393-L465) checks commitment and exact identity. **Good:** a useful renderer-configuration receipt. **Limit:** does not independently verify visible nontransparent pixels, GPU/context health, correct physical alignment, source raster provenance or legend scale. Separate *layer committed* from *visual pixels verified* in the acceptance language.

### Preserved safeguards

`validateSurfaceGrid` checks rectangular values, CRS, bounds, affine consistency and nonempty finite values, while `resolveRenderMaterialization` consults authorization/mask policy ([`render-materialization.ts#L115-L391`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/render-materialization.ts#L115-L391)). `PlotScientificLegend` correctly labels visual basemap as non-scientific and shows `No scientific surface` when no published raster exists. Preserve these rules.

### Acceptance cases

| Scene | Expected |
|---|---|
| Polygon with hole | No raster/zone cells inside hole |
| Two disjoint plot islands | Both clipped correctly; viewport fits union |
| Same plot + bounds, changed polygon | Mask recomputed, no stale pixels |
| Missing geometry/mask | Scientific overlay and zone blocked, basemap intact |
| Metric CRS passed to WGS84 renderer | Rejected; no fake alignment |
| DeckGL layer exists but GPU pixels absent | No claim of complete browser visual proof |
| Legend wrong units/acquisition/resolution | Reject visual demonstration |

**No measured FPS, raster screenshot, 3D GPU status or interactive map tests in this audit.**