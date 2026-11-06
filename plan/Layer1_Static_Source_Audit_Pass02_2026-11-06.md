# AgriBrain Layer 1 — Pass 02: Core Execution-Path Review

**Audit ID:** `AGB-L1-CODE-2026-11-06-P02`
**Immutable source baseline:** `main@6edd3721c0defa7eed94b44cf96601ba59a49696`
**Audit branch:** `audit/layer1-static-source-20261106`
**Status:** source inspection recorded; audit-only changes. No production edits, no tests or field measurements executed on this audit branch.

## Denominator and completion

Pass 01: 10/60 native production Python files.
Pass 02: 6 more full-file source reads (approximately 3,560 source lines):
- `engine.py` (~898 substantive lines): modern deterministic fusion orchestration, evidence validation, spatial/temporal alignment, invariants and downstream dispatch;
- `runner.py` (~689 lines): public convenience and modern V1 APIs, environment-conditioned legacy fallback;
- `truth_bridge.py` (~869 lines): physical truth labels and observation/derived role restrictions;
- `context_invariants.py` (~579 lines): post-fusion validation and mutation rules;
- `evidence_validation.py` (~216 lines): per-item pre-ledger scientific admission;
- `adapters/observation_packet.py` (~311 lines): canonical Layer 0 physical packet translation.

**Full-file source review coverage: 16/60 = 26.7%.**
This is a file-coverage metric, not correctness, implementation, field calibration or test coverage. Source files outside this list are NOT counted.

## Confirmed findings and actual call chains

### L1-P02-01 — Derived L0 state becomes provider-observed evidence (P1 semantic)

`runner.py:run_layer1_fusion_v1` packages `layer0_state_package`;
`engine.py:fuse` dispatches to `Layer0StateAdapter`; this adapter emits
`observation_type="state_estimate"`, `data_status="assimilated"`.
`truth_bridge.normalize_evidence_truth` then labels `l0_state` as
`data_status="observed"`, `truth_class="observed_provider"`,
`source_reality="real_provider_raster"`,
`real_provider_product=True` despite Kalman provenance.

**Verified safety distinction:** this same branch unconditionally sets
`state_update_allowed=False`; so the source review does NOT show
direct physical-state update or unauthorized irrigation application.
The remaining defect is overpromotion of semantic evidence truth.

### L1-P02-02 — No mandatory C1 state gate (P1 structural handoff)

The modern `Layer1FusionEngine.fuse` checks bundle.plot_id and run_id,
but does not require an authoritative Layer0StatePackage whose
`health_report.scientific_state_admissible` is explicitly true.
`Layer0StateAdapter.can_read` accepts nonempty legacy dicts; the
canonical `source_health` marks any populated daily_state as `ok`
without checking the C1 integrity flag.

A failed/missing C1 gate thus need not stop Layer 1 evidence and
visualization. Source review does not establish a public tenant-auth
bypass; an authenticated namespace is absent from the current
`Layer1InputBundle` schema and must be addressed separately.

### L1-P02-03 — Future observation freshness is accepted before fusion (P1 temporal)

`evidence_validation.validate_evidence` has no `run_timestamp`
boundary. `engine.fuse` calls it before ledger admission and then
`compute_freshness_batch`. In `freshness.compute_freshness`,
negative `age_hours` is clamped to zero and scores as recent.
`context_invariants.check_temporal_coherence` reports future observations
beyond one hour but attaches a warning only; `engine.fuse` still
constructs downstream `layer2_input` and `layer10_payload` after
collecting `ctx_violations`.

**Acceptance:** a caller-scoped UTC reference and bounded clock skew
must be applied **before** state-qualified ledger/fusion ingestion.

### L1-P02-04 — EvidenceLedger trusts upstream source authenticity (P2 boundary)

`engine.fuse` performs pre-ledger numeric, type, truth, unit and
source-family validations. These are not a cryptographic proof of
provider acquisition, calibrated instrument state or tenant/plot
authorization. The original-source trust boundary must be proven
in L0 and carried forward without promoting source metadata to signed
authority.

### L1-P02-05 — Production fallback currently blocks modern-engine failure (positive)

`runner.is_production()` recognizes a set of `AGRIWISE_*`, `ENV`,
and `ENVIRONMENT` variables. The convenience runner refuses
`layer0_output=None` when production is recognized and rethrows
modern-engine failures in recognized production mode. In other
environments a diagnostic legacy fallback is still possible. Validate
the actual deployment's environment classification before claiming
unreachable production fallback in every hosted configuration.

## Corrective candidate separate from audit baseline

C1B fixes are authored **on a separate branch**:
`fix/layer0-c1b-layer1-handoff-20261106`. Changes include:
- canonical C1 Layer0StatePackage gate and output-root consistency;
- derived-state truth classification;
- future evidence pre-ledger rejection beyond 5 minutes;
- tests for valid/invalid state and future-timestamp controls.

**These changes have NOT been executed or qualified on this report's
audit branch.** The source baseline `main@6edd372` is unchanged.

## Remaining work

Full-file review the remaining **44/60** modules with exact source
locations and reproducible counterexamples. Priority: signed source
adapters, temporal/spatial alignment, contextual/fusion rules, confidence
model, downstream Layer 2/ASMAE mapping, legacy callpaths, and
authoritative sensor/source admission. C1B tenant principal/scope binding
is still open. C1/C5 scientific acceptance requires an independently
sourced observation through the actual native chain.

Do not update historical Layer 0 findings or the master intended-
architecture monograph; preserve the observation-only Scientific Pilot
and keep signed irrigation disabled.
