# Akaloris Plot Page — Pass 02: React Providers, Publication State, Telemetry, and Job Lifecycle

> **Audit evidence scope:** Static GitHub source inspection pinned to commit `1ee2c20119af29dd1f0a0b46c85217d91206b744` and the provided 1600×900 browser screenshot. Files were retrieved from the repository and inspected structurally; selected control-flow paths were deep-traced. No local Next.js/FastAPI runtime, tests, browser automation, or production hardware was executed. Findings distinguish observed screenshot behavior, confirmed source behavior, and test-required hypotheses.


## Pass coverage

- Source files inventoried and inspected: **11/11 (100% of this pass’s selected static inventory)**.
- Detailed data-flow traced: **7/11**
- Browser/runtime verification: **0 executed sessions** (source-and-screenshot audit only).

### Sources inspected

- [`src/hooks/useLayer10.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useLayer10.ts) — **detailed trace**
- [`src/hooks/useParcelAssessment.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useParcelAssessment.tsx) — **detailed trace**
- [`src/hooks/usePlotIntelligence.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/usePlotIntelligence.ts) — **detailed trace**
- [`src/hooks/usePlotTelemetry.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/usePlotTelemetry.ts) — **detailed trace**
- [`src/hooks/useSubsystemParameters.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useSubsystemParameters.ts) — structural scan
- [`src/lib/agribrain/parcel-assessment-contract.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/parcel-assessment-contract.mjs) — **detailed trace**
- [`src/lib/agribrain/layer10-request-state.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/layer10-request-state.mjs) — **detailed trace**
- [`src/lib/agribrain/telemetry-contract.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/telemetry-contract.mjs) — **detailed trace**
- [`src/lib/agribrain/telemetry-contract.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/telemetry-contract.ts) — structural scan
- [`src/lib/agribrain/operational-telemetry-transport.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/operational-telemetry-transport.mjs) — structural scan
- [`src/lib/agribrain/plot-map-evidence-state.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/plot-map-evidence-state.ts) — structural scan

## The current publication lifecycle and the screenshot failure

The page sets up **nested providers** in [`src/app/farm/[id]/plot/[plotId]/layout.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/layout.tsx): ParcelAssessmentProvider → Layer10Provider → PlotTelemetryProvider → PlotIntelligenceProvider. The actual publication owner should be the canonical assessment; Layer10 is a presentation adapter, while telemetry is a separate uncertified data plane.

### Concrete state-transition defect explaining the central overlay

[`src/hooks/useParcelAssessment.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useParcelAssessment.tsx#L154-L365) requests `/api/agribrain/surfaces/latest`; when no applicable head exists it calls `/api/agribrain/run`, then tries up to **40 publication reads separated by 500 ms** (roughly **20s polling budget**, plus request latencies). It then returns `unavailable` with reason **`Timed out waiting for canonical publication head`**. The screenshot contains that exact reason.

The server path [`src/app/api/agribrain/run/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/run/route.ts#L483-L519) can allow a substantially longer upstream run (360s). A 20s **browser-side head-wait timeout is not proof a scientific worker failed**. [`src/components/farm/PlotDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx#L258-L291) treats any `l10.error` as publication failure; [`src/components/farm/intelligence/PlotLoadingSequence.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/PlotLoadingSequence.tsx#L245-L281) maps it to **FAILED** and offers `Start replacement ASMAE run`, potentially while a valid run is still ongoing. An independent progress poll ([`src/components/farm/intelligence/PlotLoadingSequence.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/PlotLoadingSequence.tsx#L110-L243)) and Layer10 poll add complexity and ordering problems.

### Findings

| ID | Priority | Code evidence | Change |
|---|---|---|---|
| ST-01 | P1 | [`src/hooks/useParcelAssessment.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useParcelAssessment.tsx#L324-L370), [`src/components/farm/PlotDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx#L258-L290) | **Misclassification:** timeout awaiting head becomes generic science failure. Introduce `WAITING_FOR_HEAD`, `RUN_ACCEPTED`, `RUNNING`, `REINTEGRATING`, `PUBLISHED`, `HEAD_INVALID`, `JOB_FAILED`, `OFFLINE`, `STALE` with clear separation of what was observed. |
| ST-02 | P1 | [`src/components/farm/intelligence/PlotLoadingSequence.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/PlotLoadingSequence.tsx#L128-L243) / [`src/hooks/useLayer10.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useLayer10.ts#L1815-L1895) | **Two polling owners** can independently watch the same job and dispatch completion events. Consolidate durable progress into one subscription (SSE or scoped polling), keyed by `{plotId,runId,jobId,generation}`; use AbortController on scope changes. |
| ST-03 | P1 | [`src/components/farm/PlotDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx#L279-L291) | “Start replacement ASMAE run” on a generic error **may queue a duplicate execution**. Permit retry only after a durable terminal failure and explicit retry eligibility; never promote client timeout into an actuation-like restart. |
| ST-04 | P2 | [`src/hooks/useLayer10.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useLayer10.ts#L964-L1175) / [`src/hooks/useParcelAssessment.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useParcelAssessment.tsx#L119-L160) | Two layers of independent `publication` and `assessment` state plus receipt coherence checks create complex intermediary states; adopt a single immutable canonical snapshot identity in a typed, discriminated client store. |
| ST-05 | P2 | [`src/hooks/usePlotIntelligence.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/usePlotIntelligence.ts#L323-L437) / [`src/components/farm/RawTelemetryHub.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/RawTelemetryHub.tsx#L12-L23) | Plot Intelligence has a separate cache/refresh path for noncanonical operational context. This is okay **only if clearly labeled non-authoritative** and never used as a second source of scientific publication authority. |
| ST-06 | P2 | [`src/hooks/usePlotTelemetry.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/usePlotTelemetry.ts#L33-L137) / [`src/lib/agribrain/telemetry-contract.mjs`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/telemetry-contract.mjs#L73-L119) | Telemetry correctly rejects missing/foreign scope and late-arriving uncertified events; keep these validations. Fix provider initialization instead of replacing the exception with an empty tenant. |

### Recommended state model

```ts
// Conceptual contract (not drop-in source code)
type PlotScienceState =
  | { kind: 'no_snapshot'; plotId: string }
  | { kind: 'waiting'; plotId: string; runId: string; jobId?: string; stage?: string }
  | { kind: 'published'; snapshotId: string; publicationId: string; receiptHash: string }
  | { kind: 'stale'; snapshotId: string; reason: 'geometry'|'crop_cycle'|'time' }
  | { kind: 'invalid'; snapshotId?: string; invalidFlags: string[] }
  | { kind: 'failed'; runId: string; errorCode: string; retryEligible: boolean };
```

Keep **visual basemap** as a separate state: the imagery visible in the screenshot is not part of a certified NDVI/ASMAE raster.

### Exit tests

1. Run accepted but not published at 20s → state remains `waiting`; replacement button absent.
2. Durable `failed` with retry eligibility → actionable one-click retry, exactly once; original run IDs maintained.
3. A later valid snapshot appears → overlay clears only after identity-checked Layer10 commit.
4. Head invalid → last-known-good raster remains only if same plot/geometry and is clearly marked historical, not authoritative now.
5. A→B→A rapid navigation cannot surface other plot telemetry or a prior run result.

**Not established:** whether the local screenshot's particular job is still running, stalled, completed or failed; that requires browser Network and backend job/worker logs.