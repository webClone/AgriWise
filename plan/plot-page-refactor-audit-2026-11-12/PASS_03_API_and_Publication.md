# Akaloris Plot Page — Pass 03: Next.js APIs, FastAPI Publication, Auth, and Cross-Service Contracts

> **Audit evidence scope:** Static GitHub source inspection pinned to commit `1ee2c20119af29dd1f0a0b46c85217d91206b744` and the provided 1600×900 browser screenshot. Files were retrieved from the repository and inspected structurally; selected control-flow paths were deep-traced. No local Next.js/FastAPI runtime, tests, browser automation, or production hardware was executed. Findings distinguish observed screenshot behavior, confirmed source behavior, and test-required hypotheses.


## Pass coverage

- Source files inventoried and inspected: **13/13 (100% of this pass’s selected static inventory)**.
- Detailed data-flow traced: **7/13**
- Browser/runtime verification: **0 executed sessions** (source-and-screenshot audit only).

### Sources inspected

- [`src/app/api/agribrain/surfaces/latest/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/surfaces/latest/route.ts) — **detailed trace**
- [`src/app/api/agribrain/run/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/run/route.ts) — **detailed trace**
- [`src/app/api/agribrain/progress/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/progress/route.ts) — **detailed trace**
- [`src/app/api/agribrain/plot-intelligence/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/plot-intelligence/route.ts) — structural scan
- [`src/app/api/agribrain/plot-intelligence/refresh/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/plot-intelligence/refresh/route.ts) — structural scan
- [`src/app/api/agribrain/runs/[runId]/result/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/runs/[runId]/result/route.ts) — structural scan
- [`src/app/api/agribrain/visual-tile/status/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/visual-tile/status/route.ts) — structural scan
- [`src/app/api/plots/[id]/telemetry/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/plots/[id]/telemetry/route.ts) — **detailed trace**
- [`src/app/api/plots/[id]/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/plots/[id]/route.ts) — structural scan
- [`src/lib/agribrain/internal-service-auth.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/internal-service-auth.ts) — **detailed trace**
- [`src/lib/agribrain/internal-service-auth-canonical.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/internal-service-auth-canonical.mjs) — structural scan
- [`src/lib/agribrain/authorize-plot.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/authorize-plot.ts) — **detailed trace**
- [`services/agribrain/app/main.py`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/services/agribrain/app/main.py) — **detailed trace**

## End-to-end source trace

```text
Authenticated plot URL
   ↓  POST /api/agribrain/surfaces/latest (Next.js)
Owner-authorized plot + signed internal-service headers
   ↓  GET /v2/plots/{plotId}/snapshot (FastAPI)
Canonical snapshot store + validation flags
   ├─ valid → frontend_payload → ParcelAssessment → Layer10 → DeckGL
   └─ unavailable/stale/invalid → client state, progress, optional /run
                                    ↓
                        POST /api/agribrain/run
                                    ↓
                        FastAPI /v2/run + async publishing
```

The Next.js proxy [`src/app/api/agribrain/surfaces/latest/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/surfaces/latest/route.ts#L35-L73) authorizes a plot through `authorizePlot()`, derives tenant/farm/plot from an approved record, signs backend headers and requests a canonical head. That is a **good boundary to preserve**.

### Findings

| ID | Priority | Source | Evidence / remediation |
|---|---|---|---|
| API-01 | P1 | [`src/app/api/agribrain/surfaces/latest/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/surfaces/latest/route.ts#L109-L143), [`src/lib/agribrain/layer10-request-state.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/layer10-request-state.mjs#L86-L111), [`services/agribrain/app/main.py`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/services/agribrain/app/main.py#L628-L649) | The canonical API/read classifiers gate **six integrity + three contract flags**. `temporalBindingValid` and `numericalBindingValid` are **not independently named in those checks**. A producer may validate them under umbrella flags; the page must explicitly assert them for new scientific snapshots and quarantine missing/false binding, rather than rely on assumption. Do not claim cryptographic bypass without a native malformed-payload test. |
| API-02 | P1 | [`src/app/api/agribrain/run/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/run/route.ts#L496-L519) and [`src/hooks/useParcelAssessment.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useParcelAssessment.tsx#L294-L367) | Backend has a 360s request timeout while UI polls the publication for ~20s. Design a durable job handoff returning accepted job ID promptly, not a long synchronous POST or misleading 20s failure. |
| API-03 | P1 | [`src/app/api/agribrain/surfaces/latest/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/surfaces/latest/route.ts#L90-L114) | Exact snapshot requests correctly fail on identity mismatch. Preserve exact publication identity; a refactor must **never replace a requested old snapshot with the latest**. |
| API-04 | P2 | [`src/app/api/agribrain/progress/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/progress/route.ts#L1-L66) / [`src/components/farm/intelligence/PlotLoadingSequence.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/PlotLoadingSequence.tsx#L128-L245) | Progress API is scoped by plot but client UI can lose the exact active `runId` in polling. Bind displayed status to active job ID and generation to prevent outdated terminal state appearing during retries. |
| API-05 | P2 | [`src/app/api/agribrain/plot-intelligence/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/plot-intelligence/route.ts#L40-L95), [`src/app/api/agribrain/plot-intelligence/refresh/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/plot-intelligence/refresh/route.ts#L20-L147) | Distinct intelligence cache is operational context, not canonical science. UI should keep data-plane labels, timestamps and stale status clearly separated. |
| API-06 | P2 | [`src/app/api/agribrain/run/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/run/route.ts#L207-L290) | `executeRun` creates run IDs and marshals context; preserve the source namespace, geometry epoch and independent durable publication identity. Test idempotent retries under double-clicks and network reconnection. |
| API-07 | P2 | [`src/app/api/plots/[id]/telemetry/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/plots/[id]/telemetry/route.ts), [`src/lib/agribrain/operational-telemetry-transport.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/operational-telemetry-transport.mjs#L1-L135) | Persisted `SensorReading.timestamp` denotes server receipt/write time; operational rows are **not certified measurement instants**. Preserve acquisition-clock labels and never promote these into historical scientific evidence. |
| API-08 | P2 | [`src/app/api/agribrain/visual-tile/status/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/visual-tile/status/route.ts), [`src/app/api/agribrain/runs/[runId]/result/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/runs/[runId]/result/route.ts) | Developer/visual status and run-result routes are separate channels; ensure stale UI buttons cannot present status from a different tenant or run; verify controls in deployed environment, not just source. |

### Expected API response contract (new page view)

```json
{
  "available": false,
  "status": "waiting_for_publication",
  "plotId": "...",
  "runId": "...",
  "jobId": "...",
  "publication": null,
  "progress": { "stage": "scientific_processing", "percent": null },
  "retry": { "eligible": false, "reason": "job_not_terminal" }
}
```

This is a **proposed** status shape, not a claim about existing API responses. Explicit statuses should cover `unpublished`, `waiting`, `published`, `stale`, `invalid`, `failed`, `superseded`, `offline`.

### Contract acceptance gate

- Authorized owner, wrong tenant, nonexistent plot, wrong plot header, exact superseded snapshot, invalid numerical binding, stale schema, incomplete timestamp envelope, no published head, worker still running, worker terminal failed.
- On `available=true`, verify **all 11 requested validation indicators** (the previously proposed spec accidentally called them ten): `nodeValid`, `publicationValid`, `receiptValid`, `inventoryValid`, `temporalBindingValid`, `numericalBindingValid`, `bindingValid`, `lineageValid`, `schemaValid`, `contractValid`, `publicationStatusValid`.
- Same `publicationId`, `snapshotId`, `surfaceInventoryHash`, geometry epoch and scientific lineage must survive publisher → Python API → Next API → browser.
- Record response codes, time budget, trace IDs, worker lease state and event sequence. **No production service or browser API was executed here.**