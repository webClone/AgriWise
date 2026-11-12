# Akaloris Plot Page — Round 2 Independent Deep Audit

**Date:** 2026-11-12  
**Pinned source:** [Integration commit `1ee2c20119af29dd1f0a0b46c85217d91206b744`](https://github.com/webClone/AgriWise/commit/1ee2c20119af29dd1f0a0b46c85217d91206b744)  
**Verified remote baseline:** `integrate/layer0-layer1-observation-pilot` at that commit; `main@6edd3721` (not modified).  
**Evidence:** exact-commit GitHub source, existing first-pass Markdown reports, and supplied browser screenshot showing `AgriBrain surface publication failed` and `Timed out waiting for canonical publication head`.  
**Independent result:** **Source-level refactor HOLD for operational launch, but redesign is justified.** Neither live SIRE publication nor authentic field validation has been established by this audit.

## What was actually audited — corrected percentage

| Measure | Result | Denominator and significance |
|---|---:|---|
| First-round declared inventory | 109 paths | selected page dependency set (not complete transitive import graph) |
| Four newly added backend/verification paths | +4 | Python snapshot store, Python temporal tamper test, Layer10 surface contract and mounted browser harness source |
| **Explicitly enumerated structural source inventory** | **113 / 113 (100%)** | at least structural/source targeted examination, not all code paths |
| **Paths with at least one targeted branch/data-flow trace** | **73 / 113 (64.6%)** | 47 previously traced + 22 additional existing paths + 4 newly added paths |
| Selected paths not yet deeply traced | 40 / 113 (35.4%) | names recorded in `R2_COVERAGE_MANIFEST.json` |
| **Authenticated browser sessions / Playwright runs independently executed** | **0** | cannot claim E2E verified |
| **Native FastAPI / scientific worker tests independently executed** | **0** | cannot claim server/hardware qualification |
| **Standalone, source-equivalent adversarial scenarios executed** | **6 / 6** | logic counterexamples only; not real repo/server/browser tests; details in Pass 10 |

**Read the percentage precisely:** **64.6% is a targeted source-path inspection metric, not a percentage of how “finished” or “correct” the Plot Page is.** The denominator excludes unknown indirect dependencies. Some traced paths had selected routines/branches examined; it does not mean every line and branch was audited. Runtime qualification remains **0% independently executed**.

## Highest-impact findings (round 2)

| Finding | Severity | Precise effect | Confidence |
|---|---|---|---|
| R2-01 | **P1** | Development plot owner filter omitted even with valid session | Source-confirmed; production bypass not shown |
| R2-02 | **P1** | Owner absent from mapped farm and empty telemetry tenant fallback; earlier scope exception | Source-confirmed route condition |
| R2-04 | **P1** | Client 40×500ms canonical-head wait can be incorrectly labeled terminal ASMAE failure; forced replacement offered | Exact source + screenshot message; backend root cause unknown |
| R2-07 | **P1 conditional** | Warm cached snapshot may not revalidate modified node/receipt/publication bytes when head mtime unchanged | Source-confirmed conditional fault model |
| R2-10 | **P1** | First-ring-only raster masking misses polygon holes and multipolygon islands | Source-confirmed mathematical defect |
| R2-11 | **P1** | Raster-mask cache lacks geometry hash/epoch | Source-confirmed stale-key risk |
| R2-14 | **P1** | Hard-coded fertilizer, irrigation and fungicide action protocols presented as zone-specific | Source-confirmed latent behavior |
| R2-15 | **P1** | Raw linked actions bypass scientific prescription authorization in zone renderers | Source-confirmed latent behavior |
| R2-18 | **P1** | Mock irrigation returns success / E-STOP semantics without physical acknowledgment | Source-confirmed simulation, not observed actuation |
| R2-08 | P2 | Numerical binding nullable and typed applicability missing; nine aggregate flags do already incorporate explicit binding failures | Nuanced contract finding, not a proven bypass |
| R2-09 | P2 | Publication job ID can be projected as scientific run ID | Conditional mismatch; no real ID disagreement shown |
| R2-13 | P2 | DeckGL layer receipt not independent pixel-visibility evidence | Source-confirmed proof limitation |
| R2-16 | P2 | Zone inspector invents provenance and sensor status when absent | Source-confirmed display problem |
| R2-21 | P2 | UI “Model Recalibrated” signaled by timer, not scientific job receipt | Source-confirmed |
| R2-23 | P2 | Fixed layout offsets/small text | Source-confirmed design; real clipping untested |

### Correction to round 1

The previous audit's “nine frontend validation flags instead of eleven” concern is **not** itself evidence of accepting a forged snapshot. Backend `bindingValid` includes `temporalBindingValid` and fails if `numericalBindingValid` is explicitly false. However, absent ASMAE numerical record currently yields nullable verification, so authority must be gated by publication kind and claim. See **Pass 03** for direct Python source references and the acceptance matrix.

### The screenshot's true meaning

Your screenshot proves the basemap, plot outline and controls render. It shows **no committed scientific surface** and a client-side head-wait timeout. It does **not** show that ASMAE mathematically failed, that Python worker terminated, that the Sentinel data are invalid, or that a new run is safe to start. Capture actual `/api/agribrain/run`, `/api/agribrain/progress` and `/api/agribrain/surfaces/latest` responses plus durable job ID before fixing the root cause.

## Pass-by-pass Markdown files

| Pass | Report | Main scope |
|---|---|---|
| 01 | [R2_PASS_01_Routes_Ownership.md](R2_PASS_01_Routes_Ownership.md) | Route owner/session/scope and irrigation layout |
| 02 | [R2_PASS_02_Publication_State_Machine.md](R2_PASS_02_Publication_State_Machine.md) | Exact error trace, async state and concurrency |
| 03 | [R2_PASS_03_Snapshot_Reader_Security.md](R2_PASS_03_Snapshot_Reader_Security.md) | Python immutable hashes, caching, FastAPI/Next contracts |
| 04 | [R2_PASS_04_Map_Geospatial_Pixel_Proof.md](R2_PASS_04_Map_Geospatial_Pixel_Proof.md) | Full polygon topology, stale mask, pixel proof |
| 05 | [R2_PASS_05_Scientific_Advice_And_Trust.md](R2_PASS_05_Scientific_Advice_And_Trust.md) | Treatment instructions, linked action authorization, trust wording |
| 06 | [R2_PASS_06_Telemetry_Simulator_Irrigation.md](R2_PASS_06_Telemetry_Simulator_Irrigation.md) | Mock E-STOP and telemetry data-plane separation |
| 07 | [R2_PASS_07_UX_Performance_Accessibility.md](R2_PASS_07_UX_Performance_Accessibility.md) | Layout, mobile/RTL/accessibility, rendering performance plan |
| 08 | [R2_PASS_08_Adversarial_Test_Matrix.md](R2_PASS_08_Adversarial_Test_Matrix.md) | 22 concrete adversarial gates and E2E qualification |
| 09 | [R2_PASS_09_Refactor_Batches_Release_Gates.md](R2_PASS_09_Refactor_Batches_Release_Gates.md) | 12 isolated batches and release criteria |
| 10 | [R2_PASS_10_Executable_Source_Equivalent_Counterexamples.md](R2_PASS_10_Executable_Source_Equivalent_Counterexamples.md) | Six executable isolated counterexamples, reproducible Node script and JSON receipts |

### Added reproducible counterexamples

Pass 10 executes six **source-equivalent** counterexamples in a standalone Node environment. The model reproduces: hole pixel wrongly present, second polygon island missing, geometry-change mask reused, omitted development owner predicate, blocked treatment text still visible, and publication-await timeout classified as `FAILED`. These are **not** native application tests; they strengthen source-level evidence while preserving the **0** authentic browser/worker execution count.

## Recommended refactor sequence

**First: preserve truth and safety.** Fix owner scope, explicitly label/disable simulated actuation, suppress unqualified zone treatments, distinguish run pending from failed, and harden cached publication integrity and polygon masks. 

**Second: prove the operational vertical slice.** One genuine observation-only Plot-A scientific publication, signed FastAPI read, Next.js proxy, real browser raster and legend, same immutable snapshot/receipt identities, complete negative controls and **zero physical commands dispatched**.

**Third: modernize the screen.** Modular `PlotOperatingShell`, readable responsive header/sidebars, separate Observations / Scientific Layers / Live Telemetry / Decisions, provenance and uncertainty always visible. Use unified authorization for every action, not duplicated component heuristics.

**Fourth: close the gates.** Real browser/worker/owner-crossover tests, full geometry fixtures, mobile/RTL/keyboard, GPU materialization, resource usage, cache mutation, correct retry, rollback and production canary.

## Governance and caveats

No changes to protected `main`, Draft PR #28, the intended-architecture monograph, immutable tags or 52-package register; no hardware action. `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false` is a **required rollout invariant**, not a setting independently read from the user's running server in this audit. Source inspection cannot certify pilot readiness or physical sensor origin. Do not merge/activate based only on this report; use the negative tests and runtime receipts.