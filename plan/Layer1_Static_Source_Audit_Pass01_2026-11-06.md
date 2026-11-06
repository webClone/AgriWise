# AgriBrain Layer 1 — Pass 01: Core Evidence & Layer 0 Handoff

**Report ID:** `AGB-L1-CODE-2026-11-06-P01`  
**Immutable code baseline:** `main@6edd3721c0defa7eed94b44cf96601ba59a49696`  
**Audit-only branch:** `audit/layer1-static-source-20261106`  
**Scope:** source-only; no Layer 1 production edits and no tests executed in this pass.

## Audit denominator and completed full-file reads

The full inventory is **60** production Python files (814,730 bytes) under `services/agribrain/layer1_fusion/`; see Initial Pass document. In this pass, the following **10 files have been fetched fully and inspected** against the pinned SHA:

| # | Full-file source path | Lines | Audit focus |
|---|---|---:|---|
| 1 | `evidence_ledger.py` | 282 | structural admission, supersession, indices |
| 2 | `source_registry.py` | 114 | adapter registry and envelope quarantine |
| 3 | `unit_registry.py` | 81 | canonical units and absence of implicit conversions |
| 4 | `source_family.py` | ~30 | source-family aliases and type confusion |
| 5 | `temporal_alignment.py` | ~83 | forecast, history, time-window assignments |
| 6 | `freshness.py` | ~150 | age, stale/future scoring, status |
| 7 | `provenance.py` | ~100 | run and evidence identifiers, lineage |
| 8 | `invariants.py` | ~100 | legacy FieldTensor invariant reporting |
| 9 | `adapters/l0_state.py` | 405 | canonical/legacy state, trust markers, scope |
| 10 | `adapters/layer0_source_package.py` | 116 | source envelope, packet conversion |

**Strict full-file completion: 10/60 = 16.7%.**
`engine.py`, `runner.py`, `context_invariants.py` and
`truth_bridge.py` have had specific ranges examined, **not full-file
deep review**; they remain outside 10/60. Their callsites are cited below
as directly observed *cross-file evidence* only.

## Corrected prior preliminary finding: Layer 0 state permission

The initial report's L1-P0-01 implied that an invalid Layer 0 state can
directly become **updatable** Layer 1 state. That implication was too broad.

- `adapters/l0_state.py:_add` initially sets
  `state_update_allowed=not diagnostic_only`, and emits
  `observation_type="state_estimate"`, `data_status="assimilated"`.
- But `engine.py:fuse` calls `normalize_evidence_truth(item,
  source_context=pkg)`, and the `truth_bridge.py` **l0_state** branch
  explicitly sets `state_update_allowed=False`.
- Therefore, **direct Layer 1 state-updatable promotion is NOT established
  through this canonical normalization route**.

**Residual trust-class risk:** the same normalization branch sets
`data_status="observed"`, `truth_class="observed_provider"`,
`source_reality="real_provider_raster"`,
`real_provider_product=True`, `production_usable=True` on derived
Kalman state, even if its original provenance was assimilation. This
misrepresents a derived model state as raw provider measurement and does
not check `health_report.scientific_state_admissible` from new L0-C1.

`adapters/l0_state.py:source_health` reports any nonempty canonical
`daily_state` as `source_status="ok"`, `trust_score=0.85` without
the new C1 marker or verification of the original state output root.

**Severity:** P1 cross-layer trust labeling, but not proven direct state
mutation or deployed unauthorized access. Test modern and legacy callers;
valid trusted state must remain `assimilated`/model-derived and
untrusted state must be refused or labeled diagnostic.

## Full-file findings

### L1-F01 — EvidenceLedger structural admission is not acquisition authentication (P2, directly evidenced)

`evidence_ledger.py:_validate` uses
`if not (0.0 <= item.confidence <= 1.0)` and analogously for
`reliability`. This **does reject NaN** under Python comparisons, because both
inequalities are false (so it appends a violation). **No NaN bypass is
claimed here.** However, its structural checks do not verify scientific
source authority, content hash or trust capability. This is intentional
defense in depth, not the full acquisition verifier.

The engine separately calls `validate_evidence` before ledger add,
which adds data-status, truth and quantitative checks. Do not claim that
direct `ledger.add` is the engine's only admission check.

**Test requirement:** source authority cannot be inferred from successful
ledger insertion. Check engine path and every public/direct ledger
consumer; preserve invalid-value quarantine.

### L1-F02 — Supersession identity self-reference allowed (P2 conditional)

`evidence_ledger.py:update_item` explicitly permits
`new_item.evidence_id == target_id` and removes the existing duplicate
violation. It then sets `new_item.supersedes_evidence_id=target_id`
when absent and stores the old item in `_superseded[target_id]`.
A same-ID replacement can therefore point to itself, making a
provenance traversal cyclic unless downstream differentiates versions.

**Test:** same-ID replacement, divergent content hash and audit lineage;
reject self-referential supersession or require an independent revision
identifier.

### L1-F03 — Future observations are treated as maximally fresh (P1 conditional)

`freshness.py:compute_freshness` does:
`if age_hours < 0: age_hours = 0`. A future-dated acquisition therefore
receives today's top freshness score. `temporal_alignment.py`
likewise assigns age < 1 hour to `instant`, even for future evidence.
`context_invariants.py` has a post-fusion future-time check but the
`engine.py` code inspected records violations and continues generating
downstream Layer 2/Layer 10 payloads.

This is a **source-level trust risk**. Verify actual pre-ledger
`validate_evidence` / clock bounds and caller reachability before
declaring a production bypass. No real clock-injection test executed.

**Test:** UTC +1minute, +59 minutes, +2 hours; negative ages must not
gain current-data or publication authority. Separate tolerable clock
skew from impossible future evidence.

### L1-F04 — Available package truth is not independently verified in envelope (P2)

`adapters/layer0_source_package.py:source_health` uses the package's
`is_available`, `data_status`, `package_id`, `package_hash` and
`time_window` fields to construct a source envelope. It does **not**
recompute `package_hash` or independently inspect the issuer/provider
receipt in this method. The packet bridge may perform additional checks
and therefore requires a complete call-chain trace.

`is_layer0_source_package` accepts any object whose
`contract_version` starts with `layer0-source-package-v`, even if it
is not an instance of the nominal dataclass. Structural typing is useful
for import-namespace compatibility, but is not cryptographic authenticity.

**Test:** tampered declared package hash; forged versioned object; actual
packet vs source-package scope mismatch; missing immutable source proof.

### L1-F05 — Legacy FieldTensor audit metadata misreports autofix (P3)

`invariants.py:enforce_layer1_invariants` detects a negative
precipitation value and sets `auto_fixed=True` on its violation, but
that function does not actually modify precipitation. This can
mislead diagnostics if the legacy invariant reports are consumed.

**Test:** negative rainfall is not silently presented as repaired;
identify actual callers of this **legacy** function first. This is not
the modern `context_invariants.py` implementation.

### L1-F06 — Source-family aliases may change evidence semantics (P2 research)

`source_family.py` maps `soilgrids` and `fao` to
`environment`. This may intentionally normalize legacy providers but
it can also collapse static soil/landcover context into a meteorological
family; check actual adapter dispatch, feature types, source-status and
non-updatable policies. This is not proven incorrect without a
provider-specific expected contract.

### L1-F07 — Acquisition/run identifiers do not by themselves prove integrity (informational)

`provenance.py` generates deterministic truncated SHA-256 IDs from
source/time/geometry/payload strings and run params. Correct for
deduplication when inputs are canonical, but not signatures and not
an owner/plot authorization capability. The local `LineageEvent` uses
a random UUID and current timestamp for execution history; do not
conflate event-attempt identity with scientific input root.

## Positive findings

- `source_registry.py` rejects missing IDs, invalid families and
  out-of-range trust scores when processing normal envelopes.
- `unit_registry.py` is verify-only and does not silently convert
  scientific units.
- `temporal_alignment.py` partitions forecast and historical evidence
  explicitly; future-date handling still needs rejection.
- `freshness.py` has family-specific freshness decay rather than a
  single global score.
- `evidence_ledger.py` preserves supersession history and provides
  separate state-updatable/diagnostic queries.
- `Layer0SourcePackageAdapter` makes unavailable packages diagnostic,
  although integrity of availability assertions is a separate problem.

## Next deep-review batch

Full retrieve and inspect `engine.py`, `runner.py`, `truth_bridge.py`,
`context_invariants.py`, `evidence_validation.py` and
`adapters/observation_packet.py` to determine actual reachability,
timing, and the positive observation-to-evidence contract. Only then
upgrade conditional risk candidates to confirmed blockers.

## Safe workstream decision

- L0-C1A code fix at `be02d1ef5422118c4308339562040ab643f7786d`
  has locally reported passing regression gates; numerical PSD and
  cross-layer trust checks are distinct future evidence.
- L0-C2 stays a separate signed-physical-delivery line; no signed
  irrigation is enabled and no L0/Layer1 source code was modified here.
- The Scientific Pilot remains observation-only.
- Do not merge this audit branch into main without review.
