# Layer 0 B2B-05 — Spatial & Tenant Authority: Initial Contract Gate

**Source pin:** `f320e7875abf8e451e55a539f88c711f189b35bf` (B2B-04B frozen).
**Branch:** `feat/layer0-b2b05-spatial-tenant-authority-20261104`.
**Status:** Initial code and adversarial contract tests only; NOT the integrated B2B-05 acceptance gate.

## Security and science invariants

1. No request body, packet, or source claim is a tenant/plot authorization credential. A trusted upstream authentication layer supplies a principal; a trusted DB-backed resolver independently supplies plot ownership, exact WGS84 polygon, geometry hash, and geometry version. Missing/foreign/revoked identities fail closed.
2. Geometry version is a strict positive integer (not boolean). Stored and requested hashes must match a digest of the actual authoritative polygon. The resulting scoped context binds tenant, plot, version and hash; neither an ID string nor a geometry digest alone is a digital signature.
3. Pixel footprints are polygons, not center/snap points. Intersections use a local WGS84 Lambert azimuthal equal-area projection. Report fractional interior and exterior area. Partial overlap is `FRACTIONAL_BOUNDARY`, never a full plot-qualified pixel; exterior footprints are quarantined.
4. This is a geometric support gate only. It does not establish electromagnetic sensitivity (MESIA eta lower bounds), authorize plot observations, qualify providers, grant Kalman updates, or mint actionable recommendations.
5. Sources and observation evidence IDs are *claims* until verified by separate provider/source authority. All exported packets explicitly retain `source_qualified=false`, `eligible_for_state_grant=false` and `authority=spatial_diagnostic_only`.

## Follow-up integration in the same B2B-05 cohort

| Module | Required integration acceptance |
| --- | --- |
| FastAPI/application auth | Resolve authenticated principal from trusted middleware; do not deserialize it from body |
| Plot datastore | Independently query owner, active status and canonical geometry epoch; include revocation/version invalidation |
| `DataRequestBroker` and caches | Perform positive authorization before any cache read/consolidation/provider fetch; key by authenticated tenant + plot + geometry epoch; no unscoped bypass in production callers |
| `ObservationPacket`/`Layer0StateEngine` | Require scope binding prior to state admission, not only negative foreign-plot filtering |
| MESIA → ASMAE geometry | Use fractional support and verified grid mask with DEM/radio footprint uncertainty; no point-snap shortcuts or zero-leakage assumption |
| Runtime authority | Validate signed issuer/zone/scope grants independently; spatial diagnostic never upgrades source authority |

## Targeted qualification

`py -m pytest -q services/agribrain/layer0/tests/test_b2b05_spatial_tenant_contract.py`

Must also test: cross-tenant cache collision, direct broker cache bypass, adjacent plots, identical coordinate with different tenant, geometry supersession/revocation, fragmented MultiPolygon/holes, area cut fractions, missing spatial CRS, and same-day cross-plot packet replay at integrated cohort gate.

**Evidence disclaimer:** Initial contract tests and source code are committed candidates; they have not been executed by the GitHub connector. Full Layer 0/Layer 1/ASMAE real-raster qualification is deferred to the B2B-05 milestone gate under the accelerated policy. Do not inherit the 651/651 B2B-04B execution receipt for these edits.

**Protected records:** Historical 469-finding audit and master monograph remain immutable; PR #25, Scientific Pilot PR #9 and `main` are not modified.

## B2B-05 integrated Python broker and packet wiring candidate

- Trusted registry: `plot_ownership_store.py` implements `PlotOwnershipStore` and a
  read-only `CollectionPlotOwnershipStore`. Its normalized Mongo-like records
  MUST represent current authoritative app ownership. A replicated collection
  is not itself proof of consistency with the frontend Prisma ownership table.
- Trusted identity: `DataRequestBroker.configure_plot_authority(store, provider)`
  must be called by application startup; `provider()` reads verified
  middleware identity, never user JSON. Background bulk workers inherit
  `ContextVar` context.
- Enforced scope when `AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE=1` or
  `plot_scope` is supplied. Authorization occurs before source registry,
  consolidation, storage, hot/warm cache or network. Every scoped cache
  identity incorporates authenticated tenant, plot and geometry epoch.
- No production configuration is automatically enabled. Legacy unscoped
  calls remain compatible when strict scope mode is disabled.
- Scoped user data ingestion, freshness, invalidation and archive query are
  also positively gated; user data stored under the scoped namespace.
  Existing legacy archives require migration/tenant-safe replay before
  they can be returned in strict mode.
- ObservationPacket binds tenant ID, geometry epoch and fractional pixel
  support; a caller-populated dict cannot mint a verified in-memory binding.
  Partial/exterior pixel footprints receive zero effective spatial weight.
  This does NOT independently attest provider or Kalman state authority.
- Runtime gaps: actual Prisma-authoritative registry wiring and middleware
  connection, state engine/ASMAE independent packet re-verification,
  plot-epoch invalidation during concurrent requests, and admin-only raw
  StorageManager access. These remain cohort release gates.

Targeted test: `py -m pytest -q services/agribrain/layer0/tests/test_b2b05_production_wiring.py`.

This candidate has NOT been executed by the connected GitHub assistant;
the prior 562/562 receipt belongs to an older B2B-05 head.

## B2B-05 Prisma and state-ingestion integration candidate

- PrismaPlotOwnershipStore joins actual case-sensitive MongoDB collections Plot, Farm, User with BSON ObjectIds, validates Farm.userId ownership and active User, and checks the current exact plot geometry hash and version.
- Schema now adds Plot.geometryVersion (optional int), geometryHash (optional string), isActive, isRevoked and deletedAt. This DOES NOT backfill existing Mongo documents or establish an atomic geometry-write lifecycle. Strict scoped requests intentionally deny uninitialized epochs.
- StateEngine.run_from_packets accepts tenant_id and scope_hash. In strict scope mode it independently resolves authenticated principal and authoritative current plot, rejects packet claims not matching the caller scope, blocks deserialized/unbound/partial/exterior packets, and rechecks current geometry before and after the state run.
- Direct scalar run() is blocked in mandatory spatial scope mode; signed-purpose source admission remains separate and unchanged.
- The in-memory spatial binding marker is not a cryptographic issuer or standalone statement of physical provenance; source grants and actual producer footprint validation remain required.
- Targeted test: py -m pytest -q services/agribrain/layer0/tests/test_b2b05_prisma_state_ingestion.py
- Also run all Layer 0 tests and affected Layer 1/ASMAE fast tests at the exact new head. Existing 684/684 receipt is not transferable.
- Deployment gates remain: live DB authorization tests, Prisma schema/index rollout and backfill, atomic geometry epoch writes, middleware principal wiring, operational entry-point strict configuration and publication scoped receipt integration.

## B2B-05 startup and atomic geometry epoch lifecycle

- FastAPI lifespan configures the *existing singleton* Layer0 broker from a live MongoDB ping and PrismaPlotOwnershipStore before its refresh worker starts. Strict plot scope fails startup on missing authoritative DB.
- Signed internal-service dependency creates and resets a ContextVar authenticated principal; unsigned development requests never inherit ownership authority. Request signing authenticates the server caller, not evidence from user JSON.
- Python PlotGeometryEpochService compares expected owner, active plot, farm ID, canonical GeoJSON and geometry version, and atomically increments the version while replacing geoJson and geometryHash in one Mongo document update.
- New plot initialization is a separate CAS restricted to genuinely uninitialized epochs. An old plot with a different unversioned geometry cannot be silently reinitialized; backfill requires trusted administrative migration.
- Signed POST initialize and PUT geometry endpoints use authenticated internal namespace and broker authority. Frontend plot creation and both plot PUT endpoints delegate geometry writes to this API, excluding direct Prisma geometry/hash/version mutations.
- Old scoped hot/filesystem cache invalidation is attempted after commit; even if storage cleanup errors occur, a stale scope cannot pass the next live-ownership validation. Best-effort cleanup is not transactional with Mongo mutation.
- New test: py -m pytest -q services/agribrain/layer0/tests/test_b2b05_geometry_epoch_lifecycle.py
- Must also run: full Layer 0 suite, affected Layer 1 and ASMAE fast, Next.js typecheck/build and route tests before milestone acceptance.
- Open deployment/architecture gates: actual Mongo replica ownership race validation, live FastAPI signed endpoints, frontend session signer integration, trusted backfill and atomic plot ownership transfer protocol, scoped background refresh and direct raw storage access.
- This candidate does not inherit any prior passing test count. Do not merge without exact-head verification.

## B2B-05 owned plot write-envelope completion — P1/P2 closure candidate

**Status: implementation published; NOT frozen; exact-head tests and connected workflow pending.**

This bounded addition closes only the two audit findings at prior head 256e6e7.
It does NOT reopen the frozen B2B-04B selected historical Open-Meteo software path.

- **B05-API-01 (P1), both PUT paths:** `src/lib/plot/owned-plot-mutation.ts`
  is the sole scalar metadata parser. It constructs a typed Prisma update object
  from explicit fields: name, nameAr, area, perimeter, ownership,
  irrigationDistrict, soilType, irrigation, physicalConstraints. Geometry
  remains separately handled by the signed CAS epoch service. Unknown,
  authority-bearing and relation fields (`farm`, `photos`, `sensors`,
  `farmId`, geometryHash, etc.) are rejected, not stripped or forwarded.
  The root PUT accepts an authenticated plot ID in its request envelope;
  the detail PUT uses the URL plot ID. No generic Prisma nested writes.
- **B05-API-02 (P2), POST:** after a successful geometry initialization
  receipt, the handler re-reads the plot under the authenticated owner's
  relationship and requires exactly matching committed geometryVersion/hash.
  The response uses that persisted record, not the earlier detached create
  object. Missing/unmatched identity or failed initialization yields explicit
  spatial-authority-unready status (not a false successful 201).
- **Focused regression:** `tests/frontend/plot-write-lifecycle-security.test.mjs`
  executes both native route functions with explicit session/Prisma/epoch/
  HTTP fixtures. It checks the original foreign-farm nested `connect`
  counterexample, other relation envelopes, scalar edits, existing 401/404
  controls, stale create response, failed/mismatched epoch and signed-epoch
  invocation. The file is included in `npm run test:frontend`.
  Fixture tests do not prove a real Prisma/MongoDB relation mutation.

### Required final candidate qualification

Run **at one final SHA** and record command output, exact HEAD, failure/skips:

```powershell
git rev-parse HEAD
node --test tests/frontend/plot-write-lifecycle-security.test.mjs
npm run test:frontend
npx prisma generate
npx tsc --noEmit
npm run build
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
# Also run the known ASMAE fast tests and existing comprehensive
# 365-day real-raster EnKF command as pinned by prior local receipts.
```

**One connected workflow (not covered by fixture tests):**
create an owned plot with real Prisma MongoDB + signed FastAPI endpoint;
verify returned 201 geometry hash/version equals a fresh owned GET;
perform a normal scalar metadata PUT with neither farmId nor Farm association
changed; submit original `farm.connect` payload to BOTH PUT routes and
verify zero Prisma writes / unchanged owner; edit the geometry through signed
CAS and verify old epoch scope rejected; initiate the existing scoped plot
assessment and require its tenant/geometry context to match the new epoch.
Keep the DB isolated and use a test tenant and disposable test plots only.

A passing 365-day numerical pipeline alone does NOT close a frontend
authorization P1. Conversely, the bounded frontend fix does not reopen
already-closed weather/numerical/source-lineage work.

**No merge, freeze or B2B-06 release handoff before those exact-head
checks and connected workflow are recorded.** Protected master monograph,
frozen findings/layer0.md, Pilot PR #9, PR #25 and main are unchanged.
