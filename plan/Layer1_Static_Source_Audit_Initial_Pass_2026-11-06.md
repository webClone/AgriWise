# AgriBrain — Layer 1 Frozen Source Inventory and Entry-Point Pass

**Audit ID:** AGB-CODE-L1-2026-11-06-P0
**Baseline:** `main@6edd3721c0defa7eed94b44cf96601ba59a49696` (immutable).
**Audit branch:** `audit/layer1-static-source-20261106`.
**Relationship:** Parallel to Layer 0 C1 on `fix/layer0-c1-scientific-integrity-20261106` and the observation-only Scientific Pilot. There are **no Layer 1 source edits** in this audit branch.
**Status:** Full directory inventory established; entrypoint/adapters/invariant **targeted inspection only**. NOT the complete 60-file deep audit; no runtime tests executed.

## Inventory and frozen denominator

All paths under `services/agribrain/layer1_fusion/` at the pinned SHA
were enumerated using GitHub `contents` recursively, including root,
`adapters/`, `outputs/`, `validation/`, and `tests/`.

- **60 production `.py` files / 814,730 bytes**
- **8 tests Python files** under the `tests/` folder
- Production by directory: **33 root**, **18 adapters**, **7 outputs**,
  **2 validation** (includes `__init__.py` per original L0 counting rules)
- Additional non-Python files not in the production denominator.
- The baseline source inventory is complete; **full-file deep-review
  completion remains 0/60** under the original audit's strict definition.
  Reading snippets, signatures, and selected branches does NOT count as
  full-file review.
- The 21/21 passing Layer 1 tests on another candidate branch are
  regression evidence but not tests executed for this frozen baseline.

## Source-traced initial risk candidates

### L1-P0-01 — Unqualified Layer 0 state can be upgraded to fusion evidence (P1 candidate)

`adapters/l0_state.py`:
- `can_read` accepts any nonempty `dict` or an object with
  `daily_state` / `zone_summaries`; no trusted-state authorization.
- `extract_evidence` maps state variables to
  `observation_type="state_estimate"`, `data_status="assimilated"`
  with `state_update_allowed=not diagnostic_only` (default true).
- `source_health` assigns status `ok` and `trust_score=0.85`
  if the canonical package has any daily_state zones, regardless of a
  named scientific integrity/validation result.

`engine.py::fuse` checks `plot_id` and `run_id`, validates source/evidence
schemata, but has **no mandatory Layer 0 scientific-state-admissibility
check** at the entrypoint before adapters run.

**Impact:** A package whose Layer 0 validation or audit failed can be
expressed as fusion-state evidence if a caller supplies it. Whether a
specific production route can submit that object needs an exact caller
trace; do not report deployed bypass before that trace. This will matter
once L0-C1 exports the `scientific_state_admissible` marker.

**Required gate:** only a genuine canonical Layer0StatePackage whose
producer-bound authorization, scope, output hash, and fail-closed C1
integrity receipt validate can contribute updatable state. Missing,
legacy/dict, failed or malformed marker remains diagnostic-only /
quarantined; never self-promoted by field strings.

### L1-P0-02 — Legacy fallback after modern fusion exceptions (P1/P2 conditional)

`runner.py::run_layer1_fusion` catches `Exception` in the modern
pipeline and automatically executes `run_layer1_fusion_legacy`
in non-production mode. Production disables fallback according to
`is_production()`, which checks a set of `AGRIWISE_*`, `ENV`, and
`ENVIRONMENT` variables.

**Impact:** If a deployment's environment classification is wrong or
absent, a failed modern scientific route can silently switch to a
different source/trust implementation. Check the actual ASGI and worker
deployment environment before calling this a reachable production defect.

**Required gate:** unify trusted deployment environment policy with
Layer 0; forbid fallback after *any* failed canonical scoped admission
independent of a loosely interpreted development flag.

### L1-P0-03 — Context invariants may mutate and still return (P1 candidate)

`engine.py::fuse` calls `enforce_context_invariants(pkg)` after fused
features are built. `context_invariants.py` defaults
`auto_fix=True` and returns violations; `engine.py` attaches them
to `pkg.provenance.invariant_violations` and still builds downstream
Layer2/Layer10 payloads and returns.

**Impact:** Physically invalid input or fused output might be clamped
into a plausible state and exported instead of explicitly refused.
Requires tests for which violations are structural vs merely warnings;
do not blanket-abort on all QA warnings.

**Required gate:** non-mutating scientific validation, fatal error
categories on updatable evidence, and a separate diagnostic-only path
that never conveys scientific authority.

### L1-P0-04 — Source identity and ledger are not identical (P2 research)

`evidence_ledger.py::EvidenceLedger._validate` checks item ID,
plot ID, variable, source family, spatial scope and confidence ranges.
The engine separately invokes `validate_evidence` before insertion,
which supplies additional truth, status and numeric checks. Neither
basic ledger structural checks nor a `SourceEnvelope.input_hash` is
by itself proof of a source's original signed acquisition or producer
qualification.

**Required gate:** trace exact signed source packet receipt and full
content root across Layer0SourcePackage adapter, EvidenceItem, ledger,
fusion rules, temporal/spatial resolution, and downstream payloads.
Verify provenance is not transformed from diagnostic evidence to
measurement/state authority; check duplicate/reordered/corrected roots.

## Entry points inspected in this pass

- `runner.py:run_layer1_fusion` and `run_layer1_fusion_v1`
- `engine.py:fuse`, `_gather_packages`, evidence quarantine and
  invariant handling
- `adapters/l0_state.py`
- `adapters/layer0_source_package.py`
- `evidence_ledger.py`, `evidence_validation.py`
- `context_invariants.py`
- `outputs/layer2_adapter.py` (selected downstream dispatch)

These are **selected source-range inspections**, not entire-file review
receipts. Prior strict audit rules must be maintained.

## Next planned passes (frozen denominator)

1. **L1-01** — Root entrypoints, import namespace, strict input schema,
   evidence capture, fail-closed production routing.
2. **L1-02** — Source adapters for S1/S2/sensor/weather/geo/perception/SIF,
   including null/failed provider and signed provenance treatment.
3. **L1-03** — Temporal/spatial alignment, mixed resolutions, footprint
   containment, data freshness/availability, confidence and crop support.
4. **L1-04** — Evidence ledger, contradiction/quarantine, fusion rules,
   context invariants, downstream Layer2/ASMAE/Layer10 adapters.
5. **L1-05** — Legacy/conditional, cross-layer caller provenance,
   exact-head controlled runtime acceptance, aggregate finding map.

Every file becomes "deep reviewed" only after full retrieval and
inspection. Use exact static source locations, not tests or report
citations, as the basis for the initial code-only audit. Do not rewrite
the existing Layer 0 audit or master monograph.

## No-production-authority decision

The Layer 1 audit may proceed independently. But promoting L0-C1
into trusted Layer 1 input requires an additional signed,
scope-bound cross-layer integration candidate and negative tests.
This audit creates **no** runtime permission, merge, publication
authority or actuator enablement.
