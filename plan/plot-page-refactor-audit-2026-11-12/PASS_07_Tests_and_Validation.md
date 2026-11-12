# Akaloris Plot Page — Pass 07: Test Coverage, Regression Quality, and Evidence Gaps

> **Audit evidence scope:** Static GitHub source inspection pinned to commit `1ee2c20119af29dd1f0a0b46c85217d91206b744` and the provided 1600×900 browser screenshot. Files were retrieved from the repository and inspected structurally; selected control-flow paths were deep-traced. No local Next.js/FastAPI runtime, tests, browser automation, or production hardware was executed. Findings distinguish observed screenshot behavior, confirmed source behavior, and test-required hypotheses.


## Pass coverage

- Source files inventoried and inspected: **9/9 (100% of this pass’s selected static inventory)**.
- Detailed data-flow traced: **5/9**
- Browser/runtime verification: **0 executed sessions** (source-and-screenshot audit only).

### Sources inspected

- [`tests/frontend/layer10-request-state.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/layer10-request-state.test.mjs) — **detailed trace**
- [`tests/frontend/parcel-assessment-identity.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/parcel-assessment-identity.test.mjs) — structural scan
- [`tests/frontend/parcel-assessment-lifecycle.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/parcel-assessment-lifecycle.test.mjs) — **detailed trace**
- [`tests/frontend/operational-telemetry-provider.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/operational-telemetry-provider.test.mjs) — **detailed trace**
- [`tests/frontend/pilot-context-lifecycle.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/pilot-context-lifecycle.test.mjs) — **detailed trace**
- [`tests/frontend/pilot-farmer-advice.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/pilot-farmer-advice.test.mjs) — structural scan
- [`tests/frontend/operational-telemetry-route.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/operational-telemetry-route.test.mjs) — **detailed trace**
- [`tests/frontend/timeline-telemetry-separation.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/timeline-telemetry-separation.test.mjs) — structural scan
- [`tests/frontend/plot-write-lifecycle-security.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/plot-write-lifecycle-security.test.mjs) — structural scan

## What existing test files actually demonstrate

I inspected all nine **selected** frontend test files. Important distinction: **test assertions were reviewed; suites were not run**. GitHub source can contain extensive tests without proving that this screenshot has passed a real browser-to-service demonstration.

| Test | What it covers | Missing proof |
|---|---|---|
| [`tests/frontend/layer10-request-state.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/layer10-request-state.test.mjs) | Policy classifier, request identities, render commitment, worker-progress helpers; some `assert.match(source, regex)` checks | A real mounted map, actual worker progressing and published pixels. |
| [`tests/frontend/parcel-assessment-identity.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/parcel-assessment-identity.test.mjs) | Geometry/crop-cycle staleness, immutable identity, cutoff, receipt syntax | Actual Python backend and browser acceptance. |
| [`tests/frontend/parcel-assessment-lifecycle.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/parcel-assessment-lifecycle.test.mjs) | Canonical assessment adaptation, stale/missing provenance, shared identity | Real Next/React DOM and backend publication. |
| [`tests/frontend/operational-telemetry-provider.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/operational-telemetry-provider.test.mjs#L17-L85) | Hook state transitions using authored simulation of hooks/fetch/intervals, A→B→A | The **actual** React renderer, owner cookie and DB, which the test explicitly excludes. |
| [`tests/frontend/pilot-context-lifecycle.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/pilot-context-lifecycle.test.mjs#L1-L10) | Client parcel context lifecycle with stubbed validation | Production receipt cryptographic verification. |
| [`tests/frontend/pilot-farmer-advice.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/pilot-farmer-advice.test.mjs) | Static helper tests for suppression of treatment doses | Actual displayed/advised information in browser at denied authority. |
| [`tests/frontend/operational-telemetry-route.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/operational-telemetry-route.test.mjs#L15-L70) | GET handler with injected auth and Prisma adapters | Real cookies, DB indexes, concurrent tenancy, network service. |
| [`tests/frontend/timeline-telemetry-separation.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/timeline-telemetry-separation.test.mjs) | Raw vs forecast vs manifest classification and source/time labels | Visual timeline focus/keyboard and full data workflow. |
| [`tests/frontend/plot-write-lifecycle-security.test.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/tests/frontend/plot-write-lifecycle-security.test.mjs) | Guarded plot create/update, geometry epochs, invalid nested writes | Actual DB authorization in staging and UI updated geometry. |

### Gaps that explain why the screenshot escaped qualification

| ID | Priority | Missing scenario |
|---|---|---|
| TST-01 | P1 | **Real ASMAE job runs beyond 20s**: verify UI remains waiting, does not display false FAILED, does not queue new job, eventually adopts the exact publication. |
| TST-02 | P1 | FastAPI + Next.js + authenticated browser on one exact canonical snapshot, including all 11 explicit validation fields and actual DeckGL render receipt. |
| TST-03 | P1 | Polygon holes, multipolygons, same-bounds geometry edit and stale mask invalidation. |
| TST-04 | P1 | Real authenticated plot context: no session in localhost bootstrap, foreign owner, missing plot, expired session and navigation between farms. |
| TST-05 | P1 | Irrigation **simulator** never claims real hardware action/stop and observation-only pages hide actuation states. |
| TST-06 | P2 | Mobile 320/375/768, 200% zoom, focus/order, screenreader, modal focus, reduced motion and contrast. |
| TST-07 | P2 | Map layer materialization: no science screenshot vs authoritative surface pixels and matching legend. |
| TST-08 | P2 | Snapshot partial/stale, revoked, schema/numerical invalid, pending, backend offline, network interrupted, stale request A→B→A, retry once. |

### Suggested qualification matrix

```text
PR/CI:
  npm run build
  npx tsc --noEmit
  node --test tests/frontend/*.test.mjs
  (focused Python publisher + snapshot API tests)
Staging (not mocked):
  playwright --project=chromium:desktop,mobile
  live FastAPI + Next.js + read-only DB + 1 known good snapshot
  cold-start / pending / completed / tampered snapshot / plot switching
  screenshot + video + Network trace + render receipt + no command dispatch
```

**Note:** CLI commands above are an example plan, not an assertion that a Playwright test project already exists. Production data can remain controlled/fixture-backed, but the **services and browser must be real** for the operational acceptance.

### Evidence standard

Attach source commit, exact source snapshot ID, test command/output with deduplicated counts, screenshot/console, status codes, job IDs and hash comparison. Source-string tests do not substitute for browser behavior. A test-green status never permits an invalid scientific raster to render.