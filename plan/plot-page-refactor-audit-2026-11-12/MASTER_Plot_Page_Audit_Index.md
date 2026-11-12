# Akaloris — Plot Page Complete Refactor Audit (Master Index)

**Audit date:** 2026-11-12  
**Pinned integration source:** [`1ee2c20119af29dd1f0a0b46c85217d91206b744`](https://github.com/webClone/AgriWise/commit/1ee2c20119af29dd1f0a0b46c85217d91206b744)  
**Observed UI:** user-supplied `localhost:3000/farm/…/plot/…` screenshot on 2026-11-12.  
**Scope:** server plot page and six related tabs, owner/session, data providers, canonical publication, FastAPI/Next API, map and controls, scientific evidence UI, telemetry, irrigation simulator, tests and refactor architecture.  
**Status:** **source audit & refactor plan delivered; no code changed; no live browser validation performed.**

## Coverage — measured, not invented

| Coverage basis | Count | Percentage | Meaning |
|---|---:|---:|---|
| Source paths retrieved and structurally scanned in this explicitly selected page dependency inventory | **109/109** | **100.0%** | All named paths inspected; **not** a claim that all functions/branches are correct or audited line-by-line. |
| Sources with detailed control-flow/authority trace | **47/109** | **43.1%** | Specific business logic, user interactions, data flow or failure paths were traced beyond structural scanning. |
| Real local browser + API end-to-end execution conducted in this audit | **0 runs** | **0% independently executed** | Screenshot is observed evidence; live localhost and Python backend were not accessible from the GitHub source audit. |
| Broad potentially related GitHub namespaces found by nontruncated recursive tree | **224** | *Not a page completion denominator* | Includes many unrelated or lazy-loaded components; excludes some ancillary support paths. Cannot honestly use it to claim full code coverage. |

**How to interpret the headline:** **100% of the declared 109-path static audit inventory was scanned, but only 43.1% received detailed source control-flow tracing; no runtime was exercised.** A complete behavioral page audit cannot be claimed until a real mounted browser + API + backend test is performed. These separate metrics are more informative than one arbitrary “% analyzed.”

### Pass-by-pass audit coverage

| Pass | Domain | Structurally inspected | Deep-traced | Static pass coverage | Audit file |
|---|---|---:|---:|---:|---|
| 01 | Route, Authentication, Ownership, and Page Lifecycle | 14 | 7 | 100% selected paths | [Open Markdown](PASS_01_Route_Auth_Ownership.md) |
| 02 | React Providers, Publication State, Telemetry, and Job Lifecycle | 11 | 7 | 100% selected paths | [Open Markdown](PASS_02_Providers_and_State.md) |
| 03 | Next.js APIs, FastAPI Publication, Auth, and Cross-Service Contracts | 13 | 7 | 100% selected paths | [Open Markdown](PASS_03_API_and_Publication.md) |
| 04 | MapLibre/DeckGL, Raster/Mask Geometry, Legend, and Render Receipts | 23 | 9 | 100% selected paths | [Open Markdown](PASS_04_Map_and_Geospatial.md) |
| 05 | Dashboard Experience, Navigation, Forms, and Irrigation Controls | 12 | 6 | 100% selected paths | [Open Markdown](PASS_05_Dashboard_UX_and_Controls.md) |
| 06 | Scientific Intelligence Panels, Evidence Wording, and Advice Safety | 27 | 6 | 100% selected paths | [Open Markdown](PASS_06_Intelligence_and_Trust.md) |
| 07 | Test Coverage, Regression Quality, and Evidence Gaps | 9 | 5 | 100% selected paths | [Open Markdown](PASS_07_Tests_and_Validation.md) |
| 08 | Target Refactor Architecture, Priority Plan, and Exit Gates | 0 | 0 | cross-cutting synthesis | [Open Markdown](PASS_08_Refactor_Roadmap.md) |


**Repository breadth context:** 8 plot-route entries, 124 farm-component files, 8 hooks, 45 scientific-frontend library files, 24 AgriBrain API routes, and 15 frontend tests. This broad set totals 224 paths but is deliberately **not** the denominator for “percentage of this page analyzed,” because it contains numerous unrelated utility pages and lacks other dependencies. The page’s transitive dependency graph was not executed/fully enumerated.

## Screenshot interpretation — what the user actually sees

| Visible part | Observed state | Audit implication |
|---|---|---|
| Map | High-resolution aerial/satellite basemap, field polygon outline | **Basemap and spatial context render**; this is *not* proof of an authorized NDVI/ASMAE raster. |
| Center card | `AgriBrain surface publication failed` and `Timed out waiting for canonical publication head`, with `Start replacement ASMAE run` | **Most actionable UI defect.** Client wait timer can expire while job remains pending; don't call that a producer failure without durable job evidence. |
| Upper-right evidence panel | `No scientific surface`, source/resolution not reported | May be correct absent a canonical head; improve hierarchical status and provenance clarity. |
| Right tool dock | Standard / Thermal / Chloro / Chroma, unavailable cross-section | Tools should explain whether they operate on the basemap, a real scientific raster or an unavailable source. |
| Bottom-left NDVI | `🔬 NDVI` debug button | Production/debug boundary and authority label require tightening. |
| Header | Plot `cmara`/orange, `Stage unknown`, tabs Overview / Raw Data / User Inputs / AgriBrain / Live Help | Small text and excessive header chrome; crop stage absence must not be “fixed” by inventing phenology. |

## Executive finding register

| Priority | Finding | User impact | Status / first action |
|---|---|---|---|
| **P1** | ST-01: 20s canonical-head wait treated as failed publication | False error and misleading retry; primary screenshot issue | Implement durable async state machine; log jobId and worker terminal state. |
| **P1** | ST-02 / ST-03: duplicate progress observers and untargeted replacement retry | Duplicate execution, confusing progress | One publisher/job lifecycle owner; retry only terminal eligible job. |
| **P1** | MAP-01 / MAP-02: first-ring-only mask and cache key lacking geometry hash | Pixels can be shown in incorrect field areas after edits | Canonical polygon-with-holes geometry and epoch-keyed caching. |
| **P1** | UX-02: irrigation simulator returns `success:true` and fake E-STOP | False impression of real physical control or safety | Segregate simulator + observation-only gating; no mock successes. |
| **P1** | RTE-01: dev scope may mount with empty `tenantId` | Previously observed render crash | Ensure session bootstrap and real owner before providers. |
| **P1** | API-01: reader/proxy checks nine flags, not all 11 requested | Scientific interpretation/completeness gap; actual exploit unproven | Explicit typed numerical/temporal gates or formally proven compound mapping. |
| **P2** | SCI-01: template intervention instructions in zone views | Unsupported field advice | Rewrite as supported scouting language, proof-gate every action. |
| **P2** | SCI-03 / SCI-04: fabricated default source/status data | Misleading scientific confidence | Replace arbitrary defaults with Not reported. |
| **P2** | UX-03: fixed-size panel stacking + 7–10px text | Overlap and inaccessible small viewports | Responsive grid-shell design and accessibility pass. |
| **P2** | MAP-04: browser render receipt != visible proof | Overstated SIRE browser qualification | Playwright screenshot/pixel + committed ID proof. |
| **P2** | TST-01..08: contract tests are not integrated browsers | Synthetic test counts do not close screenshot failure | Real publisher→API→browser acceptance with failure matrix. |

## Recommended implementation waves

1. **Wave A — correctness and user-trust**: route session/scope, canonical async state machine, retry eligibility, canonical polygon masks, irrigation simulator segregation, explicit 11-flag snapshot validation.
2. **Wave B — one working operational vertical slice**: exact precomputed Layer10 snapshot through FastAPI, Next.js, DeckGL and visible SIRE browser proof, including real errors and no actuation.
3. **Wave C — visual and maintainability refactor**: split 2688-line Layer10 hook and 1748-line map shell, remove hardcoded offsets, readable panels, farmer/expert modes, source-aware controls.
4. **Wave D — performance, accessibility and regression**: real browser responsiveness, renderer/pixel tests, timer/no-duplicate-run tests, map geometry tests, owner-scope and snapshot-negative cases, documented rollback.

## Refactor guardrails

- **Do not modify** AgriBrain intended-architecture monograph, Draft PR #28, immutable RC tags, or `main` as part of this audit.
- **Do not promote** basemap imagery, raw telemetry, synthetic demos or weather forecasts into scientifically certified rasters.
- **Do not enable** physical irrigation: `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false` and independent hardware/issuer interlocks remain mandatory.
- A browser should expose source, acquisition time, content/hash identity, spatial support and diagnostic authority before agronomic advice.

## Evidence classification and limitations

- **Observed:** screenshot from the user; GitHub branch/head and source code at exact SHA.
- **Confirmed source defects:** 20s wait classification, raster polygon holes/cache, mocking irrigation success, dev-session initialization in pinned source, tiny CSS and hardcoded positioning.
- **Risk/integration hypotheses needing execution:** actual job duplication in the user's session, real DOM overlap across screen widths, runtime signature/authority bypass, performance, exact scientific publisher cause, live API and device status.
- **Not executed:** tests, localhost, Network logs, Python worker jobs, full DOM, real multi-size Playwright browser, actual Sentinel/field sensors, or hardware commands.

**Use the pass files for the full, source-anchored findings, refactor contracts and acceptance gates.**