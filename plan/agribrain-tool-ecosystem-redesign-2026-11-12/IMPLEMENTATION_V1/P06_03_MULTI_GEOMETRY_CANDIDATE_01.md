# Akaloris P06.03 — Native Multi-Geometry Candidate 01

Base: `77c0fb5`, `feat/plot-workspace-p06-map-scene`.  
Branch: `feat/plot-workspace-p06-multigeometry`.  
PR #30 stays unchanged at `599c4f6`.

## Delivered source slice

- Versioned `2026.11-p06.3` `WorkspaceFeatureEnvelope` with WGS84 `Point`, `LineString`, `Polygon`, `MultiPolygon`. Coordinates are validated (finite, within bounds, closed nonzero-area polygon rings), deeply detached, and included in the envelope checksum.
- `eligible_for_map_geometry` separately authorizes non-point display. A line or area is never reinterpreted as a point pin, and invalid/centroid-substitute/untrusted geometry is not display-eligible. Catalog-only records remain catalog-only.
- Independent DeckGL `PathLayer` for supplied mission routes and `GeoJsonLayer` for supplied field/camera/mission areas. Selection highlights use the same `entity_id` and `source_version` context model as the P06 point pins. Layer visibility and opacity remain presentation-only.
- Directory, inspector and context controls accommodate non-point geometry and geographic bounds. The map pans to a geometry's extent midpoint only as a *viewport target*; it does not emit a synthetic spatial observation.
- An entity can only be selected from the current plot-scoped API list. The UI does not reconstruct missing evidence from stale `selection.metadata`.
- Envelope validation recomputes the checksum on read. SHA-256 checksums are integrity evidence, **not signatures or hardware attestations**.

## Scientific and product boundaries

This is a **geometry renderer and typed-envelope contract**, not a claim that existing IoT/drone/photo database records already contain verified camera FOV, registered mission flight paths, or surveyed scouting polygons. Current Prisma `Sensor` and `PlotPhoto` schema lack those fields. Missing source geometries remain missing; no cone or corridor is extrapolated from a lone GPS point.

Layer 10 management-zone polygons continue via the existing governed scientific zone pipeline. Migrating them into a single signed typed-envelope stream requires a separate source-authorized projection; the current change does **not** reissue or promote that scientific authority.

No historical execution or flight status is inferred from `PLANNED` metadata. Physical actuation stays disabled, and no production algorithm, cutoff, materialization, publication receipt, or hardware command code is changed.

## Executed source-level checks

- 10 new pure envelope/geometry tests and 10 existing-plus-new scene registry/reducer tests passed via direct V8 evaluation of the committed source. The V8 adapter used a deterministic placeholder hash because that host does not expose Node `crypto`; it confirms comparison behavior but **not actual SHA-256 runtime**.
- Structural wiring tests are committed for the normal frontend runner.
- Full frontend suite, TypeScript compile, Next.js build and authenticated browser walkthrough are **pending**, not claimed as passed.

## Local qualification on pinned commit

```powershell
node scripts/run-frontend-tests.mjs
npx tsc --noEmit
npm run build
```

Browser gate (V2 workspace, authenticated plot):
1. Load point entities alongside a separately sourced registered LineString path and survey-backed Polygon/MultiPolygon; verify no synthetic geometry is rendered when a source is unavailable.
2. Hide the scientific raster. Verify paths, areas and ordinary pins remain visible, clickable, and independently filtered by Sensors/Cameras/Drones/Observations.
3. Click a route midpoint, a polygon interior and a point pin; confirm the exact selected envelope/version in context and the visible highlight. Verify no stale entity metadata is shown.
4. Select a path or area from keyboard directory and confirm map centers on its actual geographic bounds.
5. Open Compare Time; simulated/planned metadata must not look like observed flight or published scientific history.
6. Switch plot/tenant with delayed API requests and verify all selected geometries disappear. Repeat with invalid, out-of-bounds and untrusted geometry.
7. Confirm rendering authorization, observed masks, physical irrigation fail-closed, and V2-off fallback are unchanged.

**Acceptance:** source implementation delivered; production/Chrome qualification pending. The next integration slice is an authoritative geometry-registration adapter and separately governed zone-envelope projection; do not backfill them with invented GPS-derived shapes.
