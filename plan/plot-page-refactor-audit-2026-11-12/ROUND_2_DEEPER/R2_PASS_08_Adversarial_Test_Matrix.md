# Akaloris Plot — Round 2 / Pass 08: adversarial E2E tests, invariants and honest execution status

**Audit baseline:** `1ee2c20119af29dd1f0a0b46c85217d91206b744`. **Test execution:** none; all cases in this file are **requirements, not passes**.

### Existing test evidence and its limits

`tests/frontend/layer10-request-state.test.mjs` checks state helpers and contains multiple source-text regex assertions rather than a complete mounted browser; `parcel-assessment-lifecycle.test.mjs` validates immutable publication identity, staleness and lifecycle with mock data. `operational-telemetry-provider.test.mjs` explicitly operates without a DOM or HTTP DB; `pilot-context-lifecycle.test.mjs` stubs publication validation as valid. These are meaningful contracts but **cannot prove a real localhost publisher→API→Browser SIRE rendering**. See respective files at [`tests/frontend`](https://github.com/webClone/AgriWise/tree/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend).

### Adversarial matrix (22 gates)

| Gate | Input/attack or failure | Required outcome | Priority |
|---|---|---|---|
| A01 | `NODE_ENV=development`, Alice requests Bob plot | 404, no Bob metadata | P1 |
| A02 | No cookie, known plot ID | bootstrap/deny before provider initialization | P1 |
| A03 | Missing tenantId | never mount telemetry; no crash | P1 |
| A04 | Run accepted, head unavailable for 60sec | RUNNING/WAITING, not FAILED | P1 |
| A05 | Worker terminal failure but retry ineligible | no retry button | P1 |
| A06 | Job failed eligible + double-click | exactly one new job | P1 |
| A07 | Plot A→B→A while requests unresolved | no foreign state/event/pixel | P1 |
| A08 | Exact snapshot superseded with 409 | no fallback to different snapshot | P1 |
| A09 | Warm validation cache, receipt bytes mutate | immediate quarantine without cache flush | P1 |
| A10 | ASMAE claim but numerical record absent | cannot claim verified ASMAE posterior | P1 |
| A11 | Provider-only L10 without ASMAE numerical record | legal `not_applicable`, no fake ASMAE claim | P2 |
| A12 | Polygon contains interior hole | hole pixels not rendered | P1 |
| A13 | MultiPolygon has second island | both islands correctly included | P1 |
| A14 | Edited geometry same plot/bounds/grid | mask cache invalidated | P1 |
| A15 | Mask impossible/corrupt | scientific overlay blocked, basemap okay | P1 |
| A16 | Valid layer IDs but raster pixels blank/GPU error | browser visual proof refused | P2 |
| A17 | `linked_actions` treatment text without signed action | no treatment UI text | P1 |
| A18 | Model-only WATER_STRESS zone | no 25mm dose | P1 |
| A19 | Null source/acquisition metadata | Not reported, never `Observed (Sensor)` | P1 |
| A20 | Actuation interlock false | 0 actual device commands, no fake physical E-STOP | P1 |
| A21 | Form saved but no new scientific run | “saved”, not “recalibrated” | P2 |
| A22 | 360px, 200% zoom, RTL, keyboard | reachable and readable | P2 |

### Exact geospatial fixtures

```json
{
  "polygonWithHole": {
    "type": "Polygon",
    "coordinates": [
      [[0,0],[4,0],[4,4],[0,4],[0,0]],
      [[1,1],[3,1],[3,3],[1,3],[1,1]]
    ]
  },
  "twoIslands": {
    "type": "MultiPolygon",
    "coordinates": [
      [[[0,0],[1,0],[1,1],[0,1],[0,0]]],
      [[[3,3],[4,3],[4,4],[3,4],[3,3]]]
    ]
  }
}
```

Point `(2,2)` must be excluded by the first geometry. Point `(3.5,3.5)` must be included by the second. Test two polygons of different shapes inside identical bounding boxes to check cache identity without clearing the cache.

### Strict operational Publisher→API→Browser protocol

1. Start an authenticated test stack with `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`; prove no hardware issuer activity from independent logs.
2. Publish exactly one genuine observation-only Plot-A Layer10 fixture with signed namespace, immutable snapshot ID, content hashes, first-availability, `published_at`, geometry hash and publication receipt. Do **not** label synthetic Phase 1B as field validation.
3. Validate Python `/v2/plots/{id}/snapshot` via real TestClient and actual file-backed reader; test corrupt, stale, superseded, missing-head states and numerical applicability.
4. Query Next `/api/agribrain/surfaces/latest` under real session; assert the exact same publication ID, snapshot ID, scientific run ID, job ID, geometry hash, receipts and schema.
5. Open real plot route in Playwright; assert a visible nontransparent authorized raster, correct polygon mask, real legend units/source, browser render receipt and correct `mode_display_state.canopy.canRenderPixels`.
6. Inject live telemetry from another plot, declined sensor, stale observation, tampered numerical record, slow job and GPU failure. None may increase scientific authority.
7. Record commands, versions, fixture digests, browser screenshots, network trace, timings, request counts and all negative-control results. **No gate is marked passed without that evidence.**

### Release rules

A green unit-test count cannot replace live integration evidence. A raster displayed on a basemap cannot prove field science. Source code inspection cannot prove browser rendering. A system that dispatches **zero physical commands** can still mislead users if it displays fabricated physical success or an unsupported treatment dose.