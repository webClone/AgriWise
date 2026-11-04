# Layer 0 B2B-06 — Signed-Issuer KMS v3 Interface Contracts & Separation Gate

**Source pin:** `661f003` (B2B-05 qualified & frozen).  
**Branch:** `feat/layer0-b2b06-signed-issuer-kms-20261104`.  
**Status:** IMPLEMENTED & QUALIFIED CANDIDATE.  
**Domain:** `akaloris/layer0/positive-state-input/v3` & `akaloris/layer0/positive-zone-state-input/v3`.  
**Authority:** Kalman scientific-state input admission only. **NOT** pilot publication or autonomous actuator authorization.

---

## 1. Security & Cryptographic Invariants

1. **Strict Asymmetric Key Isolation:**  
   Signing private keys exist solely within privileged signing infrastructure (`KmsAsymmetricSigner` / HSM). Layer 0 admission verifiers (`V3KmsGrantVerifier`) and application worker processes hold **ONLY public keys** registered in a `KmsPublicKeyRegistry`. No private keys, bearer credentials, or shared HMAC secrets exist within production verifiers.

2. **Deterministic RFC 8785 Canonical Representation:**  
   Signed evidence claims are serialized using the strict RFC 8785 JSON Canonicalization Scheme (JCS): sorted dictionary keys (lexicographical UTF-16 code units / UTF-8 byte order), separators `(`,`:`) with zero extraneous whitespace, integer-normalized finite numbers, and strict rejection of `NaN`, `Infinity`, and unquoted/naive datetime objects.

3. **Complete Signed Claims Envelope:**  
   Every v3 grant cryptographically binds:
   - KMS `key_id`, `issuer_id`, `algorithm` (`Ed25519` or `ES256`), and `purpose` (`kalman_state_observation` or `weather_state_forcing`)
   - Observation `source` and explicit `permitted_variables` (e.g. `["ndvi", "evi"]`)
   - Exact `packet_digest` (SHA-256 over current observation content)
   - Provenance anchors: CAS `native_evidence_id`, `qualification_decision_id`, `policy_version`, `qa_version`, and `scientific_support_root`
   - Authoritative spatial scope: `tenant_id`, `plot_id`, `geometry_hash`, `geometry_version`, and `spatial_scope` (`plot` or `zone`)
   - Zonal bindings (if `spatial_scope == "zone"`): `zone_id`, `zone_geometry_hash`, and physical `mesia_support_root`
   - Temporal window: `acquisition_start`, `acquisition_end`, `issued_at`, `expires_at`
   - Revocation anchor: monotonic `revocation_revision_anchor` and `replay_idempotency_key`.

4. **Durable Monotonic Revocation Ledger:**  
   The `DurableRevocationAuthority` fences against:
   - Revision rollback attacks (`RevocationRollbackError`: `new_revision < current_revision`)
   - Split-brain / revision conflicts (`RevocationConflictError`: equal revision with conflicting digest)
   - Temporal decay: stale snapshots (`now - issued_at > max_snapshot_age`) or expired snapshots
   - Future-dated snapshots beyond strict clock-skew tolerance
   - Key lifecycle transitions: active keys pass; retired, revoked, or unregistered keys fail closed
   - Independent scope revocation: plot revocation, zone revocation, and explicit receipt revocation.

5. **State-Grant Separation Gate (`eligible_for_state_grant=True`):**  
   - Diagnostic envelopes and spatial provenance packets strictly maintain `eligible_for_state_grant=False`, `source_qualified=False`, and `authority="spatial_diagnostic_only"`.
   - Any packet attempting self-assertion of `eligible_for_state_grant=True` is immediately rejected as an unauthorized self-promotion attack (`StateGrantSeparationViolation`).
   - Only `certify_state_grant_eligibility()` and `V3KmsGrantVerifier` can mint a cryptographic `V3StateGrantToken` and certify state grant eligibility, requiring `FULL_CONTAINED` spatial support, active unrevoked KMS signature, and variable match.

---

## 2. Integrated Modules & Implementation Deliverables

| Component | File Path | Responsibilities |
| :--- | :--- | :--- |
| **v3 KMS Contracts & Signer** | `services/agribrain/layer0/v3_kms_signed_issuer.py` | `V3PositiveStateInputGrant`, `V3SignedReceipt`, `LocalKmsAsymmetricSigner`, `KmsPublicKeyRegistry`, `V3KmsGrantVerifier`, and RFC 8785 serialization. |
| **Durable Revocation Ledger** | `services/agribrain/layer0/durable_revocation_authority.py` | `DurableRevocationSnapshot`, `DurableRevocationAuthority`, monotonic fences, plot/zone revocation, hash-chained tamper evidence. |
| **State Grant Gate & Unified Verifier** | `services/agribrain/layer0/v3_state_admission.py` | `certify_state_grant_eligibility()`, `UnifiedAdmissionVerifier` routing v3 KMS and legacy v1/v2, mandatory v3 policy gate (`v3_kms_required()`). |
| **Production Admission Configuration** | `services/agribrain/layer0/production_admission.py` | `AKALORIS_LAYER0_KMS_PUBLIC_KEYS_JSON`, `AKALORIS_LAYER0_REQUIRE_V3_KMS`, `AKALORIS_LAYER0_DURABLE_REVOCATION_PATH` integration in `load_server_issuer_verifier()`. |
| **State Engine v3 Integration** | `services/agribrain/layer0/state_engine.py` | Multi-verifier admission protocol (`PositiveObservationAdmissionVerifier`, `V3KmsGrantVerifier`, `UnifiedAdmissionVerifier`). |
| **B2B-06 Adversarial Suite** | `services/agribrain/layer0/tests/test_b2b06_kms_v3_contracts.py` | 16 dedicated adversarial & regression test cases covering all cryptographic and authority boundaries. |

---

## 3. Targeted Qualification Execution Receipt

Executed on local Windows environment (Python 3.13.13, Node.js v20.18.0):

| Suite / Gate | Scope | Result | Duration |
| :--- | :--- | :--- | :--- |
| **B2B-06 KMS v3 Contracts** | Ed25519/ES256, RFC 8785, durable revocation, state-grant gate | **16 / 16 passed** | 0.68s |
| **Layer 0 Complete** | Full Layer 0 unit and integration suite (including B2B-05 & B2B-06) | **634 / 634 passed** | 23.68s |
| **Layer 1 Fusion** | Layer 1 temporal feature alignment | **21 / 21 passed** | 0.59s |
| **ASMAE Fast** | Archive adapter, evidence ingestion, fast EnKF | **83 / 83 passed** (3 subtests) | 34.71s |
| **Frontend Test Suite** | Full Next.js frontend test suite | **105 / 105 passed** | 1.44s |
| **TypeScript Typecheck** | `npx tsc --noEmit` | **PASS (0 errors)** | 15.8s |
| **Next.js Production Build** | `npm run build` | **PASS (63/63 pages generated)** | 24.1s |
| **ASMAE Comprehensive** | Full 365-day real-raster EnKF pipeline | Running in background | `task-3603` |

---

## 4. Protected Boundaries Reminder

- Scientific Pilot PR #9 (`71ee1f7`), frozen B2B-04B PR #25 (`f320e78`), and `main` (`6edd372`) remain strictly untouched.
- Protected master monograph and `findings/layer0.md` remain immutable.
