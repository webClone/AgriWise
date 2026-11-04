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