# Akaloris Scientific Pilot — Phase 1: Provenance and Authority Vector Audit

**Status:** Code-trace baseline / validation design; **not** an executed end-to-end pilot.  
**Source SHA:** `main@6edd3721c0defa7eed94b44cf96601ba59a49696`  
**Working branch:** `feat/akaloris-scientific-pilot-qualification`  
**Pilot parcel candidate:** Plot A `6ab14f59ad442f274c3f2a62`  
**Scope:** Published ASMAE/Layer 10 → diagnostic integration/tribunal → L3/L8 prescriptions → public serialization/chat → farmer-facing API.

## Non-negotiable pilot contract

A parcel-specific prescriptive action can appear to the farmer only if a server-validated, immutable publication receipt and prescription authorization jointly establish:

1. Authenticated tenant/farm/plot identity and applicable geometry/crop cycle.
2. Exact immutable `snapshot_id`, `canonical_publication_receipt_hash`, `evidence_cutoff_at`, observation window, and validated integrity flags.
3. Immutable assimilated evidence/lineage hashes; separately admitted evidence rather than floating operational telemetry.
4. Correct belief, tribunal, influence manifest, approved policy, L8 output and selected final plan.
5. Authority ceiling at every ordinary transformation; *policy-controlled explicit promotion* is distinct from an ordinary `demote` operation and needs independent eligibility/receipt verification.
6. Action-specific uncertainty/range, contraindication, user confirmation and expiry/requalification behavior.

No permission follows merely from a string hash being present or from a matched belief/run ID. Descriptive reference guidance must not be labeled as personalized, scientific prescription.

## Verified guards (source-level)

- `scientific_contracts/authority.py`: `AuthorityVector.demote` rejects False→True field promotion and `ScientificProductEnvelope.validate` checks prescription/execution dependencies.
- `diagnostic_integration/adapters.py`: diagnostic adapters explicitly preserve visualization and diagnosis only. `contracts.py`/ `influence.py` filter requested use by contribution authority.
- `orchestrator_v2/runner.py` `_build_diagnostic_integration`: L1 diagnosis permission now requires numeric evidence_count > 0 and nonempty usable health state; this removes the prior None-based false positive described in older task notes. A separate `DiagnosticPromotionService` processes accepted evidence/tribunal contributions before a `PRESCRIPTION_DRIVER` manifest is generated.
- `orchestrator_v2/run_schema.py` `_validated_authorization`: matches the existing L8 authorization envelope to belief, tribunal, influence manifest, selected entries, policy hash, L8 run/content, exact authorized actions, and serialized execution-plan hash. Without this verified envelope, `_extract_recommendations` emits no actions and action-shaped content is redacted.
- `orchestrator_v2/chat_adapter.py`: the structured chat action list uses the same `_validated_authorization` check.
- `src/app/api/agribrain/surfaces/latest/route.ts`: exact snapshot retrieval and canonical publication envelope carry snapshot, publication receipt and evidence cutoff, with invalid/unavailable results failing closed.
- Prior PR #8 operational telemetry remains a separate uncertified channel; no pilot change is authorized to reinterpret its readings as manifest evidence.

## Phase-1 findings / bounded qualification targets

### PILOT-AUTH-01 — Published snapshot is not a first-class field of L8 action authorization [HIGH: traceability gap]

**Code evidence:** `PrescriptionAuthorizationEnvelopeV1.identity_payload()` includes `input_belief_id`, tribunal/manifest/policy/L8/final-plan hashes and actions, but **not** `snapshot_id`, `canonical_publication_receipt_hash`, `evidence_cutoff_at`, geometry/crop-cycle identity or the canonical assimilated-evidence digest. `run_schema._validated_authorization` validates internal pipeline identities, but does not compare its envelope to the exact published ASMAE snapshot/receipt. Meanwhile `surfaces/latest` publishes these canonical identifiers through a separate route.

**Impact:** A valid internal action authorization is not, by itself, proof of the exact published parcel assessment requested for this pilot. This is a missing binding, *not evidence that existing authorization hashes can be forged*.

**Required qualification:** Introduce a read-only server-validated publication binding/gate (versioned contract) before farmer-specific action export; verify snapshot and publication receipt against stored canonical artifact, tenant/plot geometry/cycle, cutoff, manifest/digest and the precise L8 source inputs. Never invent a match from an ID string. Negative cases: altered receipt, swapped plot, old/superseded snapshot, altered cutoff or evidence digest, changed crop cycle.

### PILOT-AUTH-02 — Explicit authority elevation requires a mandatory publication/receipt gate [HIGH: policy hardening target]

**Code evidence:** `AuthorityVector.demote()` is monotone, but `DiagnosticPromotionService.promote_to_prescription_eligibility()` intentionally constructs a new vector with `prescription_driver_allowed=True`. Its default `policy_snapshot.get("require_evidence_receipts", False)` allows a contribution to pass the receipt presence check when the policy does not demand receipts. Promotion also checks confidence, identifiability, policy target and block reasons. This is a legitimate explicit promotion mechanism but not a monotone transformation.

**Required qualification:** Policy must explicitly require validated evidence receipts for exact physical interventions, bind those receipts to published snapshot identity, and disallow promotion when policy/receipt is missing, malformed, stale, mismatched or lower authority. Test both approved and denied paths; keep scouting/general diagnosis available as non-prescriptive output.

### PILOT-AUTH-03 — Separate authenticated crop-reference advice endpoint has no scientific publication context [HIGH if treated as parcel-specific advice]

**Code evidence:** `src/app/api/farms/recommendations/route.ts` authenticates the user, then generates soil compatibility, crop-stage `tasks` and water-requirement text based on request body plus `prisma.crop`; the request and response have no plot, publication receipt, evidence cutoff, L8 authorization or uncertainty. `src/components/farm/RecommendationsWidget.tsx` renders the messages as `نصائح ذكية` (smart advice). Code search found the widget definition/API caller but did not establish that it is mounted on the current plot page.

**Required qualification:** Classify the endpoint explicitly as generic reference education (never individual farm actions), or gate farmer-specific recommendations behind the same validated publication authorization contract. Do not describe this endpoint as scientifically authorized without evidence. Verify the actual route consumers and current pilot UI mount before assigning runtime impact.

### PILOT-AUTH-04 — Runtime creation of L8 authorization and exact published binding not yet demonstrated [QUALIFICATION BLOCKER]

**Code evidence:** `Layer8Output.authorization_envelope` defaults to `None`; `layer8_prescriptive/runner.py` returns an output tagged `SHADOW_ONLY_PENDING_AUTHORIZATION_ENVELOPE`. The code search located `PrescriptionAuthorizationEnvelopeV1(...)` in an injected-boundary test but did not locate a production constructor/assignment. `run_schema` and chat correctly fail closed when the envelope is absent.

**Required qualification:** Execute a real parcel run and capture the envelope creation/promotion step, or explicitly record that the accepted behavior is diagnosis/scouting only with `recommendations=[]`. Do not paper over this with an invented/mock authorization. If a publisher exists outside indexed code, locate its concrete call graph and receipt.

### PILOT-AUTH-05 — Chat narrative must never turn unapproved numeric models into actionable instructions [MEDIUM: targeted behavior probe]

**Code evidence:** `chat_adapter.py` properly gates its structured `actions` list; a separate offline narrative fallback contains query-triggered prose including “Gross Irrigation Refill Requirement”, “SMP Lime Requirement”, and other computed values. This may be diagnostic information or actionable advice depending on UI and context; source inspection alone does not prove public emission during an unauthorized run.

**Required qualification:** With `_validated_authorization` denied, prompt for watering and liming advice and assert no actionable dose/rate/scheduling command is exposed as authorized. Allow clearly labeled raw measurements/diagnostic estimates with uncertainty where policy permits. Include LLM and offline-fallback paths.

## Dependency order / gates

| Gate | Evidence | Exit criterion |
|---|---|---|
| P1-A | Exact canonical snapshot and receipt read | Identity, integrity, cutoff, geometry and cycle validated server-side |
| P1-B | Assimilation-to-tribunal lineage | Stable evidence digest and trustworthy belief/manifest mapping |
| P1-C | Authority promotion | Verified receipt required for exact prescription, demotion honored, counterexamples blocked |
| P1-D | Authorized action export | L8 action, plan, hash and canonical publication binding jointly verified |
| P1-E | All public consumers | Route/widget/chat cannot bypass scientific authorization or mislabel generic advice |

## Phase 2 pilot execution design

Use Plot A only after establishing explicit owner scope. Record immutable pre-run snapshot, receipt, evidence cutoff, geometry and crop cycle. Trigger qualified acquisition/assimilation without substituting current PR #8 operational telemetry for admitted evidence. Retrieve the exact resulting snapshot, run the authorized decision chain and inspect one **real** action end to end. If no L8 promotion envelope is actually produced, record a **correct fail-closed negative outcome**, not a passed positive prescription pilot.

Adversarial cases: change one field at a time (snapshot ID, receipt, evidence digest, cutoff, plot scope, policy, uncertainty/range, action identity), plus missing evidence and stale publication. None may yield an authorized intervention.

## Evidence limits

This is a static code-path audit performed through GitHub at the locked source commit. No Python orchestration, live Mongo/ASMAE execution, full web build, farmer UI browser run or cryptographic re-verification was performed in this Phase-1 review. Findings distinguish demonstrated source behavior from runtime hypotheses. No accepted PR #6/#7/#8 code was changed.
