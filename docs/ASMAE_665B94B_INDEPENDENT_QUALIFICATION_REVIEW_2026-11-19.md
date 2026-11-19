# ASMAE IR-04 / IR-08 — Independent Qualification of 665b94b
**Date:** 2026-11-19
**Reviewed source:** `665b94bf619dccce2adff423e57f2bde97cef21e`
**Draft PR:** #32, head `64a9f69945d8e3eda2bf33de9ff24e98186c9a17`
**Decision:** HOLD fast-forward pending bounded authority/cold-publication verification. Do not merge into main. Keep all scientific holds.

## Verified progress
1. **C752-P1-01 (partial):** `engine.py:2779` passes `committed_at=None`, preserving scene-native timestamps; `state_cell_support.py:241` applies independent valid-time T and committed-time K predicates.
2. **C752-P1-02 (structural):** production footprint path requires full tenant/farm/plot/geometry fields and selected H matrix; rejects diagnostic/test-only scenes.
3. **C752-P1-03 (interim conservative):** mixed-band S2 scenes containing 20m bands select a 20m PSF/reported instrument scale. Does not independently certify state/channel-specific adaptive resolution.
4. **C752-P2-04 (partial):** subprocess cold read of immutable snapshots through FastAPI exact/latest endpoints exists.

## Open qualifications
| ID | Severity | Exact source condition | Required acceptance |
|---|---|---|---|
| IR04-665-01 | P1 | `observation_footprint_adapter.py:163-180` treats a metadata flag, truthy receipt or provider product ID as admission proof. `:351-361` checks only SHA-256 string syntax. Test uses synthetic `"1"*64`. | Verify signed, immutable provider/Layer0 admission receipt against trusted key; hash exact scene assets; bind tenant/farm/plot/geometry, operator, calibration, observed and committed times. Test forged signature, swapped asset hash, foreign namespace and previously admitted product revised under K. |
| IR04-665-02 | P1 | `observation_footprint_adapter.py:209-225` accepts scene field `committed_at` but does not verify journal authority; `engine.py:2757-2763` permits `inp.as_of_utc` as query knowledge cutoff without a proven durable journal watermark. | Require verified Worldline replay receipt K and event-specific journal commitments; test T=Day10/K=Day10 excluding Day5 event committed Day20, then K=Day21 admitting it, through real engine+Worldline+publication. |
| IR04-665-03 | P1 | `test_asmae_c752_p1_p2_source_review_remediation.py:469-518` directly publishes a constructed canonical snapshot before worker reintegration; `publication_reused=True` proves reuse, not worker-first generation. | Cold empty store, true worker result -> reintegration -> new immutable publication, separate OS process exact/latest REST/Next.js admission; negative missing-sigma, tampered hash and quarantined head fallback. |
| IR08-665-04 | P2 | `operator_builder.py` chooses one conservative 20m PSF for whole mixed-band scene. | Retain safe 20m interim claim; do not mark IR-08 complete until state/channel-specific operator footprint, mixed-scale reconstruction and per-cell support prove scientific resolution. |

## Evidence and confidence
- GitHub compare: candidate 4 ahead, 0 behind PR32's `64a9f699`; protected main unchanged; PR32 draft/unmerged.
- User-reported local test receipts: 4/4 new acceptance; 226 backend; 341 frontend; TypeScript 0. **Not independently run here**; no GitHub CI/statuses found at reviewed SHA.
- The original 238 audit findings remain preserved; this review independently closes **zero** original findings.
- Numerical publication authority, certified 1m claims and actuator commands remain ON HOLD. `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`.

## Next bounded batch
Implement verified provenance and strict K on the isolated branch, then execute worker-first cold publication in a true separate process. Only after those tests and full regressions pass should the draft PR head be fast-forwarded using an expected SHA lease, without rebasing or merging into main.
