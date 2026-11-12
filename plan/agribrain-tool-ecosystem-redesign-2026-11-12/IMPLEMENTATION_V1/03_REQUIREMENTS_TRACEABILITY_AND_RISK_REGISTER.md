# Akaloris Plot Workspace — Requirements, 94-Concept Traceability & Risk Register
**Status:** prospective implementation tracking, all rows initially OPEN. This is not a claim that any test was executed.

## Requirement matrix
| Req | Behavior/constraint | Pass(s) | Source owner | Proof required |
|---|---|---|---|---|
| R01 | One map persistent across tools, overlays independently selectable | P02,P03,P06 | UX+Geospatial | real-browser map/panel parity |
| R02 | Entire intended Tool Library visible incl. hardware/future | P04 | UX+Frontend | catalog coverage 94/94 and alias reconciliation |
| R03 | All 13 ASMAE coordinates independently selectable | P07 | Science | canonical order+availability+no-data test |
| R04 | Exact SIRE raster pixel/legend/hash/receipt | P01,P06,P07,P15 | Science+Geo | publisher→browser receipt |
| R05 | User-scoped tenant/farm/plot/geometry/crop-cycle | P01,P03,P05 | Security | foreign-tenant and plot-switch tests |
| R06 | Sensors pinned to registered physical coordinates; depth, calibration, health | P05,P08 | Device | registry/DB-to-map fixture proof |
| R07 | IP cameras, photos, sampling and field events | P05,P08,P13 | Device | no fake geolocation, event time/source |
| R08 | Drone planning + waypoints, actual tracks separate | P05,P06,P09 | Drone | mock vs live + planned vs flown tests |
| R09 | Orthomosaic/flight QA, source observation admission | P09,P07 | Science+Drone | QA and explicit lineage test |
| R10 | MESIA receiver point, qualified spatial RF coverage, control/experiment panel | P05,P06,P10 | MESIA+Geo | UNKNOWN gap/receiver epoch/hardware tests |
| R11 | Controlled bench/field & what-if experiments appear in UI | P10,P11 | Science+UX | simulator isolated; no false physical results |
| R12 | Layers 2–9 water/nutrient/biotic/planning/operations usable | P12 | Science+Operations | each tool semantics/authority test |
| R13 | World Model and Omega concepts visible without fabricated model | P04,P12 | Product+Science | future-state catalog proof |
| R14 | A map click or tool list click selects same source entity | P03,P06,P08–P13 | Frontend+Geo | E2E selected ID and version |
| R15 | Timeline historical/live/forecast/simulation with knowledge cutoff | P03,P13 | Science+Frontend | retrovalidation/no-future test |
| R16 | Every source relationship truthfully categorized | P05,P07,P13 | Science | proximity != assimilation test |
| R17 | Real and simulated physical commands distinguishable | P01,P09–P12,P15 | Security | zero actuator commands |
| R18 | Arabic RTL/French/English, mobile, accessibility | P02,P14 | UX+A11y | real-browser matrix |
| R19 | Large map density and tool transitions responsive/stable | P06,P14 | Geo+Perf | measured heap/GPU/frame/latency |
| R20 | Feature-flag rollback preserving existing page | P00,P02,P15 | Integration | rollback drill |
| R21 | Pinned canonically scoped source and test provenance | all | A0+A7 | SHA, logs, reviewers per PR |
| R22 | Preserve monograph/release/PR/52-plan governance | all | A0+A4+A6 | unchanged governance refs |

## Concept coverage rubric
Tool audit [PASS_08](../PASS_08_Complete_Tool_Registry.md) names 94 concepts in 6 families (17 Observation, 12 ASMAE, 13 Drone, 15 MESIA, 19 Agronomy, 18 Operations/AI/Research). For each concept, maintain a ledger with:
`conceptId, canonicalToolId, aliases[], category, baseSourcePaths[], maturity, availability, requiredScopes[], observedData?, supportsMap?, mapKind?, supportedPanelModes[], supportedActions[], tests[], enabledInPilot?, ownedByPass, reviewer, currentStatus`.
100% catalog coverage requires every concept mapped to canonical tool or explicit explained alias with a discoverable search result. It does NOT mean 100% functional or physical validation.
## Initial risk register (not closed)
| Risk | Priority | Occurrence / effect | Owner pass | Proposed mitigation / evidence |
|---|---|---|---|---|
| X01 Developer-scoped plot query not owner-bound | P0 | foreign tenant information risk | P01 | scope+no-session adversarial tests |
| X02 Telemetry provider missing scope crashes route | P1 | page inaccessible | P01 | verified owner bootstrap and provider guard |
| X03 Polygon holes/MultiPolygon/epoch cache wrong | P0 | spatial false precision | P01,P06 | raster membership/invalid epoch fixtures |
| X04 Browser timeout falsely shown as ASMAE failed | P1 | false scientific operational status | P01 | job/readiness state machine |
| X05 Hardcoded chemical/irrigation advice | P0 | unsafe prescription claim | P01,P12 | source-authorized suggestion only |
| X06 Mock drone or irrigation shown physically complete | P0 | false actuation/flight | P01,P09,P12 | explicit mock driver state + dispatch denial |
| X07 Wrong sensor geolocation/uncalibrated data | P0 | false evidence footprint | P05,P08 | authoritative registry join, admission separation |
| X08 RF frequency coverage interpreted as geography | P1 | invented MESIA RF map | P05,P10 | spatial support proof, UNKNOWN |
| X09 ASMAE 13 enum entries treated as 13 actual rasters | P0 | invented subfield science | P07 | state availability matrix and no-pixel test |
| X10 Current snapshot replaced during historic replay | P0 | future-information leakage | P03,P13 | explicit knowledge cutoff, exact snapshot |
| X11 Multi-tool local state races/leaks | P0 | cross-tenant or wrong snapshot | P03 | request generations + abort tests |
| X12 94 tool concepts lose controls in refactor | P1 | product regression | P04 | tool parity/alias/visibility ledger |
| X13 MESIA hardcoded demo readings appear real | P0 | invented physics evidence | P10 | demo status and receipt gate |
| X14 Experiment modifies canonical publication | P0 | scientific integrity | P11 | immutable sandbox source/target tests |
| X15 New platform breaks old plot route | P1 | rollout rollback impossible | P02,P15 | independent feature flags and rollback |
| X16 Dense geospatial scene stalls browser | P1/P2 | unusable field map | P06,P14 | extent queries, clustering, perf logs |
| X17 Tool permission implemented client only | P0 | unauthorized operation | P04,P05 | server authority and negative tests |
| X18 Claimed physical independent field validation without logger | P0 | unsupported scientific acceptance | P15 | honest fixture labels, separate field track |

## Risk evaluation workflow
For each risk: actual root-cause evidence, reproduction, owner, remediation SHA, negative test ID, independently run verification, status OPEN/IN_PROGRESS/VERIFIED/WAIVED; WAIVED only under documented non-P0 rationale. Closing by editing Markdown alone is prohibited.

## Acceptance level definitions
- **Tool catalog availability**: discoverable entry, documented behavior and disabled/setup/preview state.
- **UI implementation complete**: real browser interaction and parity across supported layouts.
- **Scientific visualization qualified**: signed/backend validated snapshot, correct numeric map, immutable proof and browser render receipt.
- **Operational hardware qualified**: real hardware/loggers and authorization independent of simulation. Not part of current plot UI rollout.
