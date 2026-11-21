# ASMAE W1-B — API, Learning and Prescription Authority (test-first specification)

**Date:** 2026-11-21 · **Parent:** W1-A `2ff298afafbcada3dcc7802986631d6e54bfb042` · **Status:** Specification and deliberately RED regression tests only. Do not promote until W1-A independently qualifies.

## Production source boundaries and exact contracts

### W1B-01 — P2-03 learning candidate is fail-closed at *every* entry point
- `services/agribrain/rollout/validation_ledger.py::record_asmae_run`: human approval must be retained as feedback, **not** expressed as `training_use.eligible_for_asmae_learn=True` before scientific candidate qualification.
- `promote_ledger_run_validation`: treat `build_learning_candidate(view)` as required evidence. On exception: preserve manual approval, record a blocked reason, zero independent eligibility; never fabricate 1.0 trust or agreement. Builder returns `eligible=False`: outer `eligible_for_asmae_learn` stays false even on `validation_status="approved"`.
- The *final* learning eligibility must be `manual_approval AND candidate.eligible AND valid lineage/retro/BMA/uncertainty AND current authority`, not any single field.
- On event replay through `get_run_validation_view`, human feedback and candidate status remain distinct; the projection must not relabel failed learning science as approved training data.
- Append-only ledger writes must not silently corrupt or discard existing event histories on failures.

### W1B-02 — API run-result authorization before upstream access
- `src/app/api/agribrain/runs/[runId]/result/route.ts` currently calls `fetch(.../v2/runs/:runId/result)` before `getSession` or plot ownership is established. `getSession` is imported but unused; `prisma` is also imported but unused in this route.
- Before invoking the upstream endpoint, establish a valid session and trustworthy tenant-scoped runID → plot/farm relationship through server-owned records or a dedicated authorized metadata mechanism. Reject missing/foreign associations without requesting an upstream payload.
- An upstream response's self-reported `plot_id` must not become the *source* of authorization. Prevent ID enumeration via identical not-found responses, no sensitive upstream error forwarding, and `Cache-Control: private, no-store` on both success and denial.
- Do not use a client-supplied plot ID, query string, or farm ID as run ownership proof.

### W1B-03 — Server-side prescription eligibility
- Apply the same effective registry and per-state authority at the server action/prescription boundary, not only in map UI. Unqualified diagnostics, 1m advisory maps, missing sigma, revoked plots and conflicting independent evidence must not authorize executable actions.
- Physical actuator `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false` stays off throughout this wave.
- A diagnostic insight may be displayed honestly without granting `prescription_driver_allowed`, training export or delivery.

## RED tests already authored
`services/agribrain/rollout/tests/test_asmae_w1b_learning_eligibility_contract.py`
1. Approved human review + builder exception => no science eligibility, no fabricated trust.
2. Approved human review + builder returns `eligible=False` => no science eligibility.
3. Rejected human review + builder returns `eligible=True` => no science eligibility.
4. Both positive => eligible, retaining actual trust and candidate provenance.
5. Initial approved run record => approval retained, learning flag still false.

## API tests to implement alongside production patch (not claimed written)
- Unauthenticated GET: zero calls to the upstream result endpoint; response indistinguishable from foreign run.
- Authenticated user, foreign-tenant run ID: zero upstream calls.
- Owner with authorized run plot: exactly one upstream call, response constrained to the owned run.
- Nonexistent run ID: same externally observable status/body as foreign ID; never reflect upstream internal errors.
- Upstream spoofed `plot_id` does not change the already-verified run ownership.
- Revocation between authorization and fetch: deny or revalidate with an atomically versioned authorization receipt.
- Server-side action attempts with `diagnostic_only`, missing sigma, 1m advisory, revoked state or conflicting evidence all remain blocked.

## Gate
Run exact-HEAD targeted tests, route API unit tests and full rollout/Layer05/backend/frontend regressions. Require a real cold run-result request under two test tenants plus replay of the completed ledger after builder failure. Report passed counts and exact SHA. No PR #32 fast-forward, no 1m or irrigation enablement.
