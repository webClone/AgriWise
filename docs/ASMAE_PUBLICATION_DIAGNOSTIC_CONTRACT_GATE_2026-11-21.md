# ASMAE publication lane — diagnostic and certified numerical modes

Status: implementation candidate, qualification HOLD. Base: PR #32 @ `64a9f699` (unchanged, draft).

## Implementation
- `plot_snapshot_store.requires_verified_numerical_binding` infers numerical obligation from *claims and records*, not the ASMAE snapshot kind or ID prefix.
- Latest and historical readers no longer treat means without sigma as a numerical certification claim.
- `asmae_numerical_publication_contract` is frozen in the immutable frontend payload with `diagnostic` or `verified_numerical` mode.
- Exact HTTP API uses the same numerical claim/mode predicate and requires both `numericalBindingValid` and `nodeAgreementValid` for certified results.
- Three new tests include cold exact/latest diagnostic reads, supersession by qualified science, deliberate claim laundering, and diagnostic prefix semantics.

## Acceptance gates
Run full `test_scientific_publication_integrity_gates.py`, Layer05, API/worker integration and frontend regressions at the exact branch SHA. Reproduce an actual `rebuild_canonical_plot_snapshot` result through cold exact/latest HTTP reads and prove corrupted certified vectors remain quarantined. Tests authored here have **not been executed independently**. No numerical authority is bestowed on diagnostics. Original 238 findings remain open. No PR merge/fast-forward.
