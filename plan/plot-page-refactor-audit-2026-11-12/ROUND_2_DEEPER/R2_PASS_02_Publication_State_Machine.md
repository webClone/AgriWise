# Akaloris Plot — Round 2 / Pass 02: producer, canonical head, client and worker progress

**Pinned commit:** `1ee2c20119af29dd1f0a0b46c85217d91206b744`.

### Reconstructing the exact screenshot error

1. [`PlotDashboard.tsx#L127-L152`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx#L127-L152) calls `parcelAssessment.fetchAssessment()` on mount/geometry/crop-cycle changes.
2. [`useParcelAssessment.tsx#L154-L326`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useParcelAssessment.tsx#L154-L326) first reads the canonical snapshot; if missing, it can automatically call `/api/agribrain/run`.
3. On a successful run request, it polls `/api/agribrain/surfaces/latest` up to **40** times, sleeping **500ms** between unsuccessful polls (roughly **20 seconds sleep plus network latency**). It then sets `unavailable` with exact message `Timed out waiting for canonical publication head`.
4. [`PlotDashboard.tsx#L258-L291`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx#L258-L291) treats *any* `l10.error` as surface failure, while [`PlotLoadingSequence.tsx#L245-L355`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/PlotLoadingSequence.tsx#L245-L355) shows `FAILED` and offers a forced replacement. Yet `/api/agribrain/run` has a separate **360-second upstream HTTP budget** ([`run/route.ts#L483-L520`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/run/route.ts#L483-L520)). The timeout alone cannot diagnose a failed scientific worker.

### R2-04 — P1, false terminal classification and potential duplicate-run trigger

The screenshot's exact timeout is **a client-side head-adoption wait failure**, not demonstrated Python worker failure. The retry calls `setCanopySource('asmae_diagnostic')` and `fetchLayer10(...,{forceRefresh:true})`; no proof it checks the durable job's terminal and retry-eligible flags first. Whether duplicate upstream jobs actually occur requires a live trace.

**Fix:** typed states `HEAD_MISSING`, `RUN_ACCEPTED`, `QUEUED`, `RUNNING`, `WAITING_FOR_HEAD`, `PUBLISHED`, `VALIDATION_QUARANTINED`, `CONTRACT_STALE`, `TRANSPORT_ERROR`, `FAILED_TERMINAL`. Only offer replacement on a durable terminal failure with explicit retry authorization. A timeout says *still awaiting publication; inspect progress*.

### R2-05 — P1 conditional, multiple completion/progress observers

[`PlotLoadingSequence.tsx#L120-L241`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/PlotLoadingSequence.tsx#L120-L241) polls the progress endpoint and dispatches completion events. [`useLayer10.ts#L1740-L1905`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useLayer10.ts#L1740-L1905) also watches status/completion. Existing generation checks are useful but do not eliminate architectural duplication. **No actual double execution is established.**

**Fix:** one job observer keyed `(tenant,farm,plot,jobId,generation)`; one terminal receipt; exact `snapshot_id` adoption; cancel and discard old requests on plot/crop/geometry change.

### R2-06 — P2, duplicated presentation state

`ParcelAssessmentProvider` owns immutable assessment and raw publication; `Layer10Provider` maintains its own `publication` mirror and an effect to project new assessment ([`useLayer10.ts#L970-L1175`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useLayer10.ts#L970-L1175)). The refactor should expose a single canonical state and derived selectors, not two independently evolving publication stores.

### Acceptance table

| Input | Required UI/network behavior |
|---|---|
| Valid worker running 60 seconds without head | Pending/processing, not Failed; 0 new retries |
| FastAPI 409 corrupt canonical head | Quarantine; never show current scientific pixels |
| Worker terminal failure, retry ineligible | Show cause, no replacement action |
| Worker terminal failure, retry eligible | Exactly 1 replacement job, new bounded identity |
| Valid new head published at 30 seconds | Exactly 1 adoption; same snapshot in all panels |
| Navigate A→B→A during slow requests | No cross-scope data or old progress events |

**Unverified:** actual worker state, API timings and duplicate job count; browser/network logs are needed.