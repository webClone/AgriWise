# Akaloris P06.04 — Persistent Geometry Registration, Candidate 01

Branch: `feat/plot-workspace-p06-geometry-integration`  
Base: accepted P06.03 `fce622379c22b059c14960492b09ea8f9202cb4e`  
Draft PR #30: unchanged at `599c4f6`.

## Scope delivered
- New MongoDB Prisma `WorkspaceGeometryRegistration` model, unique per plot/registration key. Immutable revision 1; no update/execute/approve mutation in this slice.
- Owner-scoped GET and POST `/api/plots/:id/workspace/geometries`, using `authenticatedUserId` and `plot.farm.userId`. Unauthorized plot returns 404.
- A user-owned `OWNER_PLAN` can register a planned `LineString`/area. A `CAMERA` footprint requires an actual `IPCamera` source record in the same plot. A scouting polygon requires an existing `CropObservation` whose crop cycle belongs to the plot.
- On GET, those camera and scouting source links are revalidated in bulk so deleted or moved source records no longer appear.
- Input rejects caller-supplied tenant, epistemic, timestamp, attestation, execution, hardware and scientific publication claims.
- Spatial registration geometry is never silently converted to a point, and its SHA-256 digest is checked on every read.
- The existing `/workspace/entities` API now projects persisted shapes into the P06 native map. The directory, selection and inspector use the same P03 state; owner-declared features receive explicit provisional presentation and color.
- A user-drawn camera coverage footprint is `ESTIMATED`, not calibrated camera optics. A planned flight path is `PLANNED`, never executed telemetry. A source-linked scouting polygon is `ESTIMATED`, not admitted crop evidence. No scientific/sensor publisher has been changed.

## API example: register owner-planned mission
```http
POST /api/plots/<plot-ObjectId>/workspace/geometries
Content-Type: application/json

{
  "entity_kind": "DRONE_MISSION",
  "source_kind": "OWNER_PLAN",
  "label": "North-field reconnaissance plan",
  "geometry": {"type":"LineString","coordinates":[[2.659,36.508],[2.660,36.509]]}
}
```

Expected: 201 with envelope `PLANNED`, `USER_DECLARED`, `verified_identity:false`, `source_evidence_admitted:false`; no telemetry or historical admission. Camera source `IP_CAMERA` and scouting source `CROP_OBSERVATION` require `source_id` with an authorized Mongo ObjectId.

## Qualification plan (must be run in the actual application environment)
1. `npx prisma validate` and `npx prisma generate` after reviewing the schema change. Apply `npx prisma db push` **only to a staging MongoDB** after backup and migration review; do not change production automatically.
2. `node scripts/run-frontend-tests.mjs`, `npx tsc --noEmit`, `npm run build`.
3. Authenticated POST planned path returns 201 and subsequent GET + `/workspace/entities` return the same database-backed geometry and integrity receipt.
4. No session 401; foreign plot 404; foreign camera or observation source 404; duplicate linked source 409. Tampered or foreign stored records never reach the map.
5. Remove/move a source from its plot: the matching registered geometry disappears on the next read. No previously registered shape may silently remain authorized.
6. Browser: click each registered line/polygon; verify identity, provisional badge, geometry bounds, Compare Time status, independent raster toggle and scope resets.
7. Confirm Layer 10 scientific zone polygons still originate from their governed publication path. Do not fabricate a new scientific authority envelope for them.
8. Physical actuation flag remains `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`.

## Explicitly deferred
- True surveyed-geometry approval/attestation; signed drone flight telemetry; optical FOV calibration; empirically verified scouting; governed Layer 10 zone-envelope projection.
- Geometry revision, revocation, deletion, source audit ledger and end-user geometry drawing workflow.
- Schema/client generation and authenticated HTTP/CDP runs cannot be performed through repository-only GitHub editing and remain **pending** for local qualification.
