# Scientific Pilot Phase 1C — Authenticated Evidence Membership & Uncertainty Roots

**Status:** Non-authorizing source-bound *contract gates* and negative regression fixtures committed. **No positive issuer, trusted production root publisher, revocation record, or public export** has been enabled.

**Baseline:** \`main@6edd3721c0defa7eed94b44cf96601ba59a49696\`  
**Prior qualified branch:** \`10632a77953fcc74d5f7a1b5efee60a6da5b72de\`  
**Scope:** Publication-to-action trust gap after corrected P899-TIME-01; no edits to PR #8 telemetry or canonical snapshot publisher.

## Source-backed findings

1. \`layer05_asmae/job_manifest.py\` creates \`manifest_hash\` from a canonical encoded ASMAE **job manifest**. Its verified \`identity\` includes capability-plan, execution-plan, quarantine-ledger and crop evidence/crop influence hashes. It does **not** identify all tribunal-selected \`input_evidence_ids\` and all corresponding calibrated physical receipts that later feed L8.
2. \`layer05_asmae/plot_snapshot_store.py\` stores and validates the exact ASMAE scientific node, publication and receipt. Its current head contains \`manifest_hash\` and geometry/crop/cutoff but not \`admitted_evidence_root_hash\`, \`bounded_uncertainty_receipt_hash\` or \`scientific_posterior_hash\`. Do not infer or synthesise these missing roots at the consumer.
3. \`scientific_contracts/evidence_receipt.py\` defines a typed \`EvidenceReceipt\` with observation time, freshness, calibration, spatial support, content hashes, action class and stage receipt reference. Its \`from_dict()\` has permissive legacy boolean conversions and the receipt has no issuer signature. This source alone cannot prove membership in a specific immutable published assessment.
4. \`diagnostic_integration/tribunal.py\` and \`influence.py\` expose exact accepted contribution IDs, dependency evidence, selected influence entries and manifest hashes. A valid tribunal verdict is not, by itself, proof of ASMAE admission.
5. No production uncertainty-receipt issuer with per-action zone, unit and timing domain was established by the reviewed code path.

## Implemented contract (not production authorization)

\`services/agribrain/orchestrator_v2/pilot_proof_gate.py\` defines two verification steps, both requiring a **server-trusted current head**. It is *not* called from farmer action export and has no signing API.

### A. \`verify_published_evidence_membership()\`

Requires a future immutable \`head.admitted_evidence_root_hash\` published alongside the ASMAE node **and validated as part of the exact scientific publication**. A versioned \`pilot_admitted_membership_v1\` witness must hash exactly to this trusted root. It binds current plot/tenant/farm, geometry/crop, snapshot, canonical receipt, ASMAE job manifest, evidence cutoff, input belief, tribunal and selected L8 influence manifest.

For each selected accepted contribution, it checks a typed physical \`EvidenceReceipt\` and an exact evidence-ID/content-hash pair; stage and calibration references; source observation no later than the frozen cutoff; matching spatial support; policy-permitted truth class; and action eligibility. **The complete receipt's content hash** must appear in the immutable witness. It prevents post-publication mutation of calibration, freshness or metadata without changing the published root.

All synthetic positives are labeled \`STRUCTURAL_MATCH_ONLY\`: caller still has to prove raw acquisition integrity, authoritative calibration and actual scientific admission in the trusted producer, not via a newly invented client flag.

### B. \`verify_published_uncertainty_bounds()\`

Requires a future published \`head.bounded_uncertainty_receipt_hash\` and \`head.scientific_posterior_hash\`, bound to the already root-matched admission witness. A versioned \`pilot_bounded_uncertainty_v1\` witness must include every selected L8 action exactly once, with matching IDs, zones, timing, dose unit and a posterior-derived finite interval that covers its proposed safe rate bounds. The uncertainty hash must also equal V2's \`uncertainty_receipt_hash\`.

The check is structural only; a trusted ASMAE scientific producer must compute and publish the actual posterior/uncertainty evidence. A client-supplied SHA-256 string is not that proof.

### Current, expected behavior

**Actual current ASMAE heads lack the above committed roots and therefore fail closed.** Synthetic fixtures create matching roots to exercise validation logic, but they are not digitally signed, calibrated on real devices, or authenticated live observations. No reported positive pilot or action issuance results from passing the unit fixtures.

The earlier \`pilot_publication_gate.preflight_pilot_issuer()\` remains BLOCKED and \`run_schema._validated_authorization()\` continues to reject both object and JSON V2 via the explicit export quarantine. No V1 behavior is changed.

## Production completion design — one coherent issuer/export cohort

1. **Producer:** At ASMAE publication time, atomically create the admitted-evidence membership witness and its root in the immutable scientific node, bind the specific canonical job/accepted evidence IDs and independent evidence-stage receipts, then include and revalidate this root in the node/publication/receipt/hash checks. Backfill nothing into existing immutable heads; old snapshots stay diagnosis-only.
2. **Uncertainty:** Create an ASMAE posterior-domain receipt with actual calibrated per-zone/interval uncertainty and an immutable source posterior root. Publish both roots with the membership root in the same atomic snapshot generation. Explicit units, target zone, crop cycle, time window and rate bounds must align with L8 actions.
3. **Policy:** Require \`require_evidence_receipts is True\` for EXACT_PRESCRIPTION and reject any unverified receipt/content, under-powered confidence or disallowed scope. Promotion is explicit and policy-audited, not an automatic \`AuthorityVector\` uplift.
4. **Issuer:** Use a server-owned cryptographic signing key or authenticated durable issuer record and atomic revocation lookup (scope, key ID/rotation, nonce, issuance, \`expires_at\`, revoked status). The issuer must re-read the current validated head before minting and record exact V2 content hash, selection, policy and evidence/uncertainty proof identities. Never trust an L8 object or request JSON as proof of issuance.
5. **Exporter:** Add a **separate** guarded V2 action-export path: authenticate owner and current plot, re-read canonical head and issuance record, check publication/receipt/geometry/crop/cutoff/uncertainty/expiry/revocation and exact L8 action/plan hash before showing an intervention. Keep V1 compatibility separate and V2 quarantined in the legacy serializer until the guarded path is qualified. **No machine execution**, farmer confirmation remains mandatory.
6. **Tests and live pilot:** Mutate each binding field, received time, post-cutoff evidence, foreign plot, stage/calibration provenance, missing/altered hashes, source posterior, zone/time/rate, signer/key/nonce/revocation. Require diagnosis-only redaction on denial. Run one genuine positive Plot A with stored issuer and receipt before allowing farmer advice.

## Focused new tests

\`\`\`powershell
git pull origin feat/akaloris-scientific-pilot-qualification
py -3 -m pytest -q services/agribrain/tests/test_pilot_proof_gate.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_publication_gate.py
py -3 -m pytest -q services/agribrain/tests/test_pilot_prescription_authorization_v2.py
py -3 -m pytest -q services/agribrain/tests/test_corrected_maturity_boundary.py
\`\`\`

**Evidence limit:** New fixture tests and code were not executed in the GitHub-only authoring environment. The user-reported 98/98 V2, 29/29 preflight, 14/14 V1, and 97/97 frontend pass results apply to \`10632a7\`, **not automatically to this newer candidate**. No full build or live Plot A run is claimed. Preserve main at \`6edd372\`; do not merge or lift the V2 quarantine based solely on structural proof fixtures.
