# Scientific Pilot Phase 1 — Publication-Bound Authorization V2 Contract

**Status:** Versioned contract and tests implemented; **production promotion, signing, and farmer export deliberately not enabled**.  
**Branch:** \`feat/akaloris-scientific-pilot-qualification\`  
**Base:** \`main@6edd3721c0defa7eed94b44cf96601ba59a49696\`  
**Previous negative baseline:** Source-level missing-envelope gate PASS; real exact Plot A head read PASS; actual Plot A run response **INCONCLUSIVE** (no recorded run), as reported by local execution.

## Trust and threat model

A SHA-256 content hash provides content-addressed identity and detects accidental/content tampering when compared to a trusted reference. **It is not a signature, receipt verification, or permission.** No authorization can be inferred from an unsigned candidate V2 object received from an untrusted client.

**V1 remains unchanged** for compatibility and its already-covered legacy serialization path. V2 objects are explicitly blocked from that path: the existing \`run_schema._validated_authorization\` rejects both V2 in-memory objects and V2 dictionaries until a real server-validated publication/promotion integration is written. This is intentional and must not be removed during contract rollout.

## Versioned payload

\`PrescriptionAuthorizationEnvelopeV2\` extends V1 and includes the unchanged hash-covered lineage fields:

- \`input_belief_id\`, \`tribunal_content_hash\`, \`prescription_manifest_hash\`, \`prescription_manifest_entry_ids\`, \`policy_snapshot_hash\`, \`l8_run_id\`, \`l8_content_hash\`, \`final_execution_plan_hash\`, \`actions\`.

V2 adds **first-class content-addressed fields**, not detached metadata:

| Field | Required trustworthy upstream source | Gate |
|---|---|---|
| \`tenant_id\`, \`farm_id\`, \`plot_id\` | Authenticated server context **and** canonical head | Exact equality, nonempty |
| \`geometry_hash\`, \`crop_cycle_id\` | Current validated parcel geometry/cycle | Exact equality; geometry is 64-hex |
| \`snapshot_id\` | Current exact ASMAE publication | No stale/superseded substitution |
| \`canonical_publication_receipt_hash\` | Canonical publication receipt \`publication_receipt_hash\` | Required 64-hex, exact match |
| \`evidence_manifest_hash\` | Canonical ASMAE head \`manifest_hash\` | Required 64-hex, exact match; **not** a substitute for per-evidence admission receipts |
| \`evidence_cutoff_at\`, \`published_at\` | Immutable head | UTC-normalized exact match |
| \`observation_window_start/end\` | Immutable head \`observation_window\` | UTC-normalized exact match |
| \`issued_at\`, \`expires_at\` | Trusted authorization issuer (future) | Timezone-aware, valid order, strict expiry |
| \`uncertainty_receipt_hash\` | Separately verified scientific uncertainty receipt (future) | Required 64-hex and exact server-supplied match |

Ordered temporal contract: \`observation_window_start <= observation_window_end <= evidence_cutoff_at <= published_at <= issued_at < expires_at\`. Compare parsed UTC instants, never string ordering.

**Action constraints:** V2 forbids machine execution; dose-bearing actions need finite, nonnegative \`min_safe <= recommended <= max_safe\` and a nonempty unit. Only SCOUT, MONITOR, WAIT may omit a dose. This numeric check does **not** establish clinical/agronomic efficacy, policy approval, or uncertainty receipt authenticity.

## Public pilot validator

\`validate_published_pilot_envelope(...)\` requires:
1. A genuine V2 (never V1), validated with its content hash.
2. **Trusted current-head** \`canonical_head\` obtained after authenticated, immutable ASMAE lookup: \`available=True\`, \`snapshot_kind=asmae\`, all ten validation flags true.
3. Independent authenticated \`tenant_id/farm_id/plot_id/crop_cycle_id/geometry_hash\`; both the head and V2 must match.
4. Matching exact snapshot, receipt, admitted manifest, cutoff, published time, observation window.
5. Matching trusted uncertainty receipt hash and non-expired issued time.

This helper deliberately does **not** fetch the head, validate admission receipts, cryptographically recompute snapshot hashes or issue an authorization. The caller must establish that the head and uncertainty receipt are trusted; fabricating them in unit tests cannot give real scientific authority.

## Production activation is not part of this commit

Remaining work for the next integration phase:

1. Add server-side, scope-authenticated **current published head** retrieval at the exact moment of action export. Include proof that \`manifest_hash\` is the accepted evidence root for the specific L8 belief and tribunal, not merely two independent 64-character hashes.
2. Enforce mandatory physical evidence receipts and explicit authority promotion in \`DiagnosticPromotionService\`; never implicitly promote diagnostics or live uncertified telemetry.
3. Create the authorization issuer/cryptographic signer or equivalent trusted durable issuance and revocation policy with expiry; verify issuer, scope, and canonical head before responding.
4. Bind \`uncertainty_receipt_hash\` to a verified published uncertainty payload and require action-specific feasibility/policy checks.
5. Add a **new guarded** public export path that verifies V2 end to end. Only then remove/replace the explicit V2 quarantine; maintain separate V1 legacy compatibility and prohibit it for parcel-specific pilot claims.
6. Make \`/api/farms/recommendations\` visibly generic reference education, not scientific parcel prescription, unless it is later routed through the same authorization.
7. Run a genuine Plot A orchestrator with a stored receipt and test mutation of plot, cycle, cutoff, snapshot, geometry, manifest, uncertainty, authorization age and action payload. An unauthorized \`recommendations=[]\` is a correct negative gate but not a positive pilot success.

## Regression scope and execution

\`\`\`powershell
py -3 -m pytest -q services/agribrain/tests/test_pilot_prescription_authorization_v2.py
py -3 -m pytest -q services/agribrain/tests/test_corrected_maturity_boundary.py
py -3 -m pytest -q services/agribrain/tests/test_scientific_pilot_baseline_probe.py
\`\`\`

The first suite covers V1 compatibility, V2 serialization/hash round trips, tamper, invalid/expired cutoff, missing flags, altered canonical identity, uncertainty matching, real chronology with fractional seconds, bounded rate rejection, observational no-dose, no machine execution, and both object/dict V2 legacy-export bypass.

**Evidence boundary:** These tests are committed to GitHub but were **not executed in the GitHub-only review environment**. Earlier 8/8 baseline receipt parser tests were locally reported on an older candidate; they do not count as testing V2. No deployed V2 authorizer, live Plot A run, or production permission uplift is claimed.
