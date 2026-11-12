# Akaloris Plot — Round 2 / Pass 03: immutable snapshot reader, API and numerical binding

**SHA:** `1ee2c20119af29dd1f0a0b46c85217d91206b744`. **Method:** source trace through Python writer/reader, FastAPI, signed Next.js proxy, frontend validation; **no TestClient run**.

### Actual trust path

`publish_canonical_plot_snapshot` → node/publication/receipt/head files → `load_latest_plot_snapshot` → FastAPI `/v2/plots/{plot_id}/snapshot` → signed Next `/api/agribrain/surfaces/latest` → `canonicalPublicationToAssessment` → `Layer10Provider`.

### R2-07 — P1 conditional: validated head cache can conceal a changed immutable artifact

[`plot_snapshot_store.py#L810-L890`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/services/agribrain/layer05_asmae/plot_snapshot_store.py#L810-L890) caches the validated node by `(namespace, head_file_mtime_ns, snapshot_id, head.frontend_publication_hash)`. A hit returns the cached result **before** the reader reopens/re-hashes the node, publication and receipt; hash recomputation is downstream ([`#L885-L1047`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/services/agribrain/layer05_asmae/plot_snapshot_store.py#L885-L1047)). FastAPI adds another byte-response cache keyed by namespace/snapshot/publication hash ([`main.py#L672-L697`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/services/agribrain/app/main.py#L672-L697)).

**Failure model:** warm valid cache → on-disk publication/receipt file mutates or corrupts without a `head.json` update → a further request can still receive old `validation: true`, until eviction or head revision. This is a file-integrity/fault-injection finding, **not proof of a remote attacker**. The existing tamper tests clear `_CANONICAL_SNAPSHOT_CACHE` explicitly ([`test_p2b_temporal_binding.py#L110-L157`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/services/agribrain/tests/test_p2b_temporal_binding.py#L110-L157)), so they don't close the warm-cache case.

**Fix:** cache only on separately proven immutable storage semantics, or bind cache key to content generations/stat signatures of **all** inputs. Add TTL/force-revalidate policy, invalidation and post-warm mutation fault tests. Acceptance: corrupt node/receipt after valid first read, leave head unchanged, next read must quarantine (without manually clearing cache).

### R2-08 — P2: nine checked booleans are *not* automatically an integrity bypass

Frontend `classifyCanonicalHeadValidation` checks `nodeValid`, `publicationValid`, `receiptValid`, `inventoryValid`, `bindingValid`, `lineageValid`, `schemaValid`, `contractValid`, `publicationStatusValid` ([`layer10-request-state.mjs#L86-L110`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/layer10-request-state.mjs#L86-L110)). Python additionally computes `temporalBindingValid` and nullable `numericalBindingValid`; **`bindingValid` already incorporates temporal validity and any explicitly false numerical verification** ([`plot_snapshot_store.py#L940-L1036`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/services/agribrain/layer05_asmae/plot_snapshot_store.py#L940-L1036)). Earlier audit's 9-versus-11 risk needs this correction; missing explicit JS checks alone **do not demonstrate an integrity bypass**.

**Remaining authority gap:** if `asmae_posterior_numerical_record` is **absent**, `numericalBindingValid=None` and `(numerical_binding_valid is not False)` permits aggregate binding; writer checks numerical proof only when record exists ([`plot_snapshot_store.py#L697-L759`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/services/agribrain/layer05_asmae/plot_snapshot_store.py#L697-L759)). This is legitimate for a **provider-only Layer10 snapshot** without an ASMAE posterior, but needs a fail-closed requirement whenever the payload claims **authoritative ASMAE posterior science**. Use `verified / not_applicable / missing_required / invalid` rather than nullable boolean.

### R2-09 — P2: conflation of scientific run ID with publication job ID

[`surfaces/latest/route.ts#L145-L221`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/agribrain/surfaces/latest/route.ts#L145-L221) overwrites projected `publication_run_id`, `run_id`, `runId` with `canonical_publication_job_id`. If payload scientific run and publication job differ, the browser identity is incorrectly projected. **Actual difference is not established for the user's snapshot.** Require explicit `scientificRunId` and `publicationJobId` fields or assert contract equality.

### Gates

1. Warm-cache artifact mutation without head update → quarantine on read.
2. ASMAE numerical claim with missing record → scientific authority denied; provider-only snapshot remains legitimate.
3. Hash mismatch in state/sigma/proof/lineage → reject.
4. Exact superseded snapshot → HTTP 409, never substitute current.
5. Tenant/farm/plot namespace mismatch → deny upstream and never expose payload.
6. 200/stale vs 409/corrupt vs 200/generating → distinct client states.
7. Publication ID, scientific run ID, job ID, receipt hash and inventory hash must match real typed provenance.

**Status:** source-confirmed conditional cache failure model; tests specified, not executed.