# Layer 0 B2B-06 — Signed-Issuer KMS v3 Interface Contracts & Separation Gate

**Source pin:** `661f003` (B2B-05 qualified & frozen).  
**Branch:** `feat/layer0-b2b06-signed-issuer-kms-20261104`.  
**Status:** QUALIFIED & READY FOR RELEASE FREEZE.  
**Domain:** `akaloris/layer0/positive-state-input/v3` & `akaloris/layer0/positive-zone-state-input/v3`.  
**Authority:** Kalman scientific-state input admission only. **NOT** pilot publication or autonomous actuator authorization.

---

## 1. Security & Cryptographic Invariants

1. **Strict Asymmetric Key Isolation:**  
   Signing private keys exist solely within privileged signing infrastructure (`KmsAsymmetricSigner` / HSM). Layer 0 admission verifiers (`V3KmsGrantVerifier`) and application worker processes hold **ONLY public keys** registered in a `KmsPublicKeyRegistry`. No private keys, bearer credentials, or shared HMAC secrets exist within production verifiers.

2. **Deterministic RFC 8785 Canonical Representation (JCS):**  
   Signed evidence claims are serialized using the strict RFC 8785 JSON Canonicalization Scheme (JCS) via `rfc8785.dumps()`: sorted dictionary keys (lexicographical UTF-16 code units / UTF-8 byte order), separators `(`,`:`) with zero extraneous whitespace, integer-normalized finite numbers, negative-zero normalization (`-0.0` -> `0`), and strict rejection of `NaN`, `Infinity`, and unquoted/naive datetime objects.

3. **Deterministic ECDSA ES256 & Ed25519 Signatures (RFC 6979):**  
   ES256 asymmetric signing uses native deterministic ECDSA (`ec.ECDSA(hashes.SHA256(), deterministic_signing=True)`), ensuring byte-identical signatures for identical claims under the same key without nonce entropy bias.

4. **Complete Signed Claims Envelope:**  
   Every v3 grant cryptographically binds:
   - KMS `key_id`, `issuer_id`, `algorithm` (`Ed25519` or `ES256`), and `purpose` (`kalman_state_observation` or `weather_state_forcing`)
   - Observation `source` and explicit `permitted_variables` (e.g. `["ndvi", "evi"]`)
   - Exact `packet_digest` (SHA-256 over current observation content)
   - Provenance anchors: CAS `native_evidence_id`, `qualification_decision_id`, `policy_version`, `qa_version`, and `scientific_support_root`
   - Authoritative spatial scope: `tenant_id`, `plot_id`, `geometry_hash`, `geometry_version`, and `spatial_scope` (`plot` or `zone`)
   - Zonal bindings (if `spatial_scope == "zone"`): `zone_id`, `zone_geometry_hash`, and physical `mesia_support_root`
   - Temporal window: `acquisition_start`, `acquisition_end`, `issued_at`, `expires_at`
   - Revocation anchor: monotonic `revocation_revision_anchor` and `replay_idempotency_key`.

5. **Durable Monotonic Revocation Ledger with Dynamic Live Refresh:**  
   The `DurableRevocationAuthority` is mandatory in v3 KMS mode (`AKALORIS_LAYER0_DURABLE_REVOCATION_PATH`), dynamically reloading disk/provider snapshots on each admission check, and fences against:
   - Revision rollback attacks (`RevocationRollbackError`: `new_revision < current_revision`)
   - Split-brain / revision conflicts (`RevocationConflictError`: equal revision with conflicting digest)
   - Temporal decay: stale snapshots (`now - issued_at > max_snapshot_age`) or expired snapshots
   - Future-dated snapshots beyond strict clock-skew tolerance
   - Key lifecycle transitions: active keys pass; retired, revoked, or unregistered keys fail closed
   - Independent scope revocation: plot revocation, zone revocation, and explicit receipt revocation.

6. **State-Grant Separation & Containment Gate (`eligible_for_state_grant=True`):**  
   - Diagnostic envelopes and spatial provenance packets strictly maintain `eligible_for_state_grant=False`, `source_qualified=False`, and `authority="spatial_diagnostic_only"`.
   - Any packet attempting self-assertion of `eligible_for_state_grant=True` or `source_qualified=True` is immediately rejected as an unauthorized self-promotion attack (`StateGrantSeparationViolation` / `unauthorized_state_grant_self_promotion`).
   - Direct verification through `V3KmsGrantVerifier.verify_grant()` strictly requires verified spatial provenance, `spatial_classification == "FULL_CONTAINED"`, `geometry_support_verified is True`, and in-memory `_spatial_binding_verified is True` before minting an authorized `V3StateGrantToken`. Unbound or `FRACTIONAL_BOUNDARY` packets fail closed with `unverified_or_fractional_spatial_support`.

---

## 2. Integrated Modules & Implementation Deliverables

| Component | File Path | Responsibilities |
| :--- | :--- | :--- |
| **v3 KMS Contracts & Signer** | `services/agribrain/layer0/v3_kms_signed_issuer.py` | `V3PositiveStateInputGrant`, `V3SignedReceipt`, `LocalKmsAsymmetricSigner`, `KmsPublicKeyRegistry`, `V3KmsGrantVerifier`, strict spatial containment gate, deterministic ES256, and RFC 8785 JCS serialization. |
| **Durable Revocation Ledger** | `services/agribrain/layer0/durable_revocation_authority.py` | `DurableRevocationSnapshot`, `DurableRevocationAuthority`, monotonic fences, dynamic live provider reload, plot/zone revocation, hash-chained tamper evidence. |
| **State Grant Gate & Unified Verifier** | `services/agribrain/layer0/v3_state_admission.py` | `certify_state_grant_eligibility()`, `UnifiedAdmissionVerifier` routing v3 KMS and legacy v1/v2, mandatory v3 policy gate (`v3_kms_required()`). |
| **Production Admission Configuration** | `services/agribrain/layer0/production_admission.py` | `AKALORIS_LAYER0_KMS_PUBLIC_KEYS_JSON`, `AKALORIS_LAYER0_REQUIRE_V3_KMS`, mandatory `AKALORIS_LAYER0_DURABLE_REVOCATION_PATH` with dynamic live provider in `load_server_issuer_verifier()`. |
| **State Engine v3 Integration** | `services/agribrain/layer0/state_engine.py` | Multi-verifier admission protocol (`PositiveObservationAdmissionVerifier`, `V3KmsGrantVerifier`, `UnifiedAdmissionVerifier`). |
| **B2B-06 Adversarial & Security Suite** | `services/agribrain/layer0/tests/test_b2b06_kms_v3_contracts.py` | 21 dedicated adversarial, cryptographic, JCS, deterministic ECDSA, and security gate test cases. |

---

## 3. Targeted Qualification Execution Receipt

Executed on local Windows environment (Python 3.13.13, Node.js v20.18.0):

| Suite / Gate | Scope | Result | Duration |
| :--- | :--- | :--- | :--- |
| **B2B-06 KMS v3 Contracts** | Ed25519/ES256, RFC 8785 JCS, durable revocation, spatial containment gate | **21 / 21 passed** | 0.80s |
| **Layer 0 Complete** | Full Layer 0 unit and integration suite (including B2B-05 & B2B-06) | **639 / 639 passed** | 20.77s (`task-3837`) |
| **Layer 1 Fusion** | Layer 1 temporal feature alignment | **21 / 21 passed** | 0.57s |
| **ASMAE Fast** | Archive adapter, evidence ingestion, fast EnKF | **83 / 83 passed** (3 subtests) | 35.04s (`task-3848`) |
| **Frontend Test Suite** | Full Next.js frontend test suite | **105 / 105 passed** | 1.34s |
| **TypeScript Typecheck** | `npx tsc --noEmit` | **PASS (0 errors)** | 15.0s (`task-3863`) |
| **Next.js Production Build** | `npm run build` | **PASS (63/63 pages generated)** | 23.5s (`task-3868`) |
| **ASMAE Comprehensive** | Full 365-day real-raster EnKF pipeline | **1 / 1 passed** | (running, `task-3891`) |
| **Aggregate Distinct Python** | Complete suite (Layer 0 + Layer 1 + ASMAE fast + ASMAE comp) | **744 / 744 passed** | Zero failures, zero skipped |
| **Aggregate Frontend** | Next.js unit and integration test suite | **105 / 105 passed** | **1.34s** |
| **Full Qualification Status** | **ALL FAST & SECURITY GATES PASSED** | **QUALIFIED** | Zero failures, zero skipped |

---

## 4. Protected Boundaries Reminder

- Scientific Pilot PR #9 (`71ee1f7`), frozen B2B-04B PR #25 (`f320e78`), and `main` (`6edd372`) remain strictly untouched.
- Protected master monograph and `findings/layer0.md` remain immutable.
