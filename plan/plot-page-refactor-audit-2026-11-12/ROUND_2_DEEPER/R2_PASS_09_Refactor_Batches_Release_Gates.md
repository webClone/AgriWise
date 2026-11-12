# Akaloris Plot — Round 2 / Pass 09: full technical refactor, dependencies and GO/HOLD gates

**Baseline:** `1ee2c20119af29dd1f0a0b46c85217d91206b744`. **Status:** plan only; no branch modified.

### Recommended modular operating surface

```text
PlotRouteServer
  ├── ownerScopedRouteContext (session, tenant, farm, plot, cropCycle, geometryEpoch)
  ├── CanonicalPublicationController (head, exact IDs, async job, strict state)
  ├── OperationalTelemetryController (never manifest authority)
  └── PlotOperatingShell
       ├── PlotHeaderAndNavigation
       ├── MapCanvasWithScientificLayers
       ├── PublicationAndWorkerStatus (nonblocking)
       ├── ScientificEvidenceLegend
       ├── AuthorizedZoneInspector
       ├── EvidenceTimeline
       ├── OptionalExpertWorkstation
       └── ReadOnlyObservationOperations
```

Use stable, discriminated TypeScript interfaces for `OwnerPlotScope`, `CanonicalSnapshotIdentity`, `ScientificAvailability`, `WorkerRunState`, `RasterDisplayAuthority`, `SignedActionAuthorization`, `OperationalTelemetryScope`, `MapGeometryEpoch`, `RenderReceipt`. Client display selectors can never invent a stronger evidence class than the publication.

### Twelve PR-sized remediation batches

| Batch | Work | Required gate | Order |
|---|---|---|---|
| A01 | Fix development owner scoping and bootstrap tenant | A01–A03 | 1 |
| A02 | Replace timer-based FAIL with durable worker state machine | A04–A08 | 2 |
| A03 | Python immutable snapshot warm-cache integrity | A09 | 3 |
| A04 | Numerical proof applicability and typed run/job IDs | A10–A11 | 4 |
| A05 | Full Polygon/MultiPolygon holes and geometry-version cache | A12–A15 | 5 |
| A06 | Browser committed layer vs visible raster proof | A16 | 6 |
| B01 | Remove static treatment doses and raw `linked_actions` presentation | A17–A19 | Immediate |
| B02 | Segregate irrigation simulator and make acknowledgments honest | A20–A21 | Immediate |
| C01 | New responsive design system + adaptive map/sidebars | A22 | 7 |
| C02 | Decompose oversized hooks and map stack; preserve publication identity | typecheck/regressions | 8 |
| D01 | Real Publisher→FastAPI→Next→Browser SIRE demonstration | all E2E gates | 9 |
| D02 | Accessibility/security/performance and rollback readiness | all measured gates | 10 |

### Dependency boundaries

**Phase A — safety/correctness before visuals:** work A01/A02/A03/A04/A05 and immediately quarantine advice/physical mock feedback B01/B02. Avoid updating ASMAE math or monograph merely to improve UI.

**Phase B — working vertical slice:** prove one genuine published Layer10 observation-only snapshot through FastAPI and browser; no hardcoded data, no generated last-known-good masquerading as fresh, no physical actuation.

**Phase C — architectural modernization:** migrate feature by feature to a common shell, keep old route behind feature flag while comparing scientific identities, and retire old components only when equivalent acceptance gates pass.

**Phase D — release qualification:** real owner-switched browser, 360px/768px/1600px viewport snapshots, 200% zoom, keyboard-only and RTL, WebGL recovery and no degraded trust inflation. Profile the map and bound polling/network/heap growth.

### Priority blockers vs improvement work

**P1 scientific/safety correctness:** owner bypass in dev, misleading worker failure/restart, snapshot warm-cache hash verification, polygon mask topology/cache, static prescriptive text, fake irrigation success and live telemetry certification boundary. Do not go live while unqualified treatment/control guidance remains.

**P2 architecture/UX:** typed UI state split, run/job IDs, small text/layout collisions, hidden debug controls, screen reader and mobile usability. Ship after baseline correctness but before broad release.

### Non-negotiable repository governance

Create a new refactor branch. Preserve `main@6edd3721`, Draft PR #28 at `7713333`, immutable RC tags and the scientifically intended master monograph. Do not alter the 52-package register unless packages are separately verified. Keep `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false` independently at backend and hardware. No live field validation is inferred from synthetic Phase 1B.

### Exit criteria

- **Code remediation GO:** each identified P1 is fixed and demonstrated with a negative test against the exact new commit; no protected branch silently altered.
- **Browser demonstration GO:** same valid canonical publication across Python→Next→Browser with actual raster pixels and correct provenance, all negative controls.
- **Authentic science GO:** separate real physical field logger data and blind held-out validation, not the Phase 1B synthetic suite.
- **Production rollout GO:** controls truthful, errors diagnostically accurate, scoped auth, accessibility/performance/security tested; rollback documented.

**No code remediation or runtime gate is asserted complete by this report.**