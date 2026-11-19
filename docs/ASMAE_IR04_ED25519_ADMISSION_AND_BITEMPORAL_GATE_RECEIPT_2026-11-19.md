# ASMAE IR-04 / IR-08 — Asymmetric Ed25519 Admission & Bitemporal Authority Receipt

**Date:** 19 November 2026  
**Review Branch:** `feat/akaloris-asmae-ir04-r03-r04-review-20261119`  
**Draft PR #32 Status:** Held unmerged at `64a9f699` (fast-forward strictly on hold)  
**Master Findings Register:** 238 findings preserved across 3 cohorts; 0 newly closed  
**Safety Interlocks:** `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false` (fail-closed)  
**Certification Holds:** 1 m spatial resolution certification & numerical publication authority strictly **ON HOLD**  

---

## 1. Executive Summary

This qualification receipt documents the focused security and bitemporal authority remediation addressing the four open findings from the candidate `5ccca4a` source review:
1. **IR04-5CC-P0-01 (P0 Critical Security Blocker):** Removed all embedded production HMAC secrets and default keyrings from ASMAE source code. Deployed asymmetric, verifier-only Ed25519 public key infrastructure with fail-closed behavior when trusted keys are unconfigured. Required explicit private key capability for signing grants, raising `PermissionError` if omitted.
2. **IR04-5CC-P1-02 (P1):** Wired independent `verify_bitemporal_replay_receipt` at the ASMAE engine boundary. Verified schema, contract version, replay mode, tenant/plot/geometry scope, evidence set digest integrity, and absence of future bitemporal leakage; forged cutoffs and unverified receipts fail closed.
3. **IR04-5CC-P1-03 (P1):** Implemented strict issuer scope checking for authorized source (`sentinel2` vs `sentinel1`) and purpose (`kalman_state_observation` / `asmae_observation_admission`). Enforced cross-sensor rejection and wrong-purpose rejection.
4. **IR04-5CC-P2-04 (P2):** Replaced ad-hoc Python dictionary serialization with strict RFC 8785 JSON Canonicalization Scheme (`canonical_grant_bytes` via `rfc8785.dumps`) with non-finite float rejection and explicit `"canonical_format": "rfc8785_jcs_v1"` claim.
5. **IR08-665-04 (P2 Safe Interim Claim):** Retained conservative 20 m PSF ($\sigma=10.0\text{ m}$, $\text{FWHM} \approx 23.55\text{ m}$, native resolution $= 20.0\text{ m}$); 1 m spatial resolution certification and numerical publication authority remain strictly ON HOLD.

---

## 2. Technical Remediation Details

### 2.1 Critical Security Blocker (IR04-5CC-P0-01) — Verifier-Only Ed25519 Public Keys
- **Elimination of Embedded Secrets:** Removed `DEFAULT_ADMISSION_SECRET` and hardcoded production secret tuples from `services/agribrain/layer05_asmae/resolution/observation_footprint_adapter.py`.
- **Verifier-Only Public Keyring:** Introduced `TrustedAdmissionIssuerKey` dataclass holding `key_id`, `public_key: ed25519.Ed25519PublicKey`, `source`, and `purpose`.
- **Fail-Closed Default:** In-memory `_TRUSTED_PUBLIC_KEYS` starts strictly empty. If no keys are registered via `register_trusted_admission_public_key` or injected via environment `AKALORIS_LAYER0_ADMISSION_PUBLIC_KEYS`, verification fails closed with `"no_trusted_public_keys_configured"`.
- **Prohibition of Self-Signing:** `create_scene_admission_receipt` requires an explicit `private_key: ed25519.Ed25519PrivateKey`. If `private_key is None`, it raises `PermissionError("Authorized issuer capability required: private_key must be explicitly provided; production verifier and worker code cannot self-provision or embed private keys.")`.
- **Detached Signature Format:** Signed grants generate `"ed25519:<hex>"` signatures over canonical RFC 8785 bytes, verified via `trusted_key.public_key.verify(sig_bytes, canonical_bytes)`.

### 2.2 Bitemporal Authority at Engine Boundary (IR04-5CC-P1-02)
- Implemented `verify_bitemporal_replay_receipt(receipt, *, tenant_id, plot_id, geometry_hash, journal_watermark=None)`:
  1. Validates structure: `contract_version == "canonical_bitemporal_replay_receipt_v1"`, `replay_mode == "bitemporal_deterministic_v1"`, `status == "replayed"`.
  2. Binds namespace: `tenant_id`, `plot_id`, and `geometry_hash` must match the engine query.
  3. Recomputes evidence digest over canonical sorted `selected_evidence_set` and compares against `evidence_set_digest`.
  4. Detects bitemporal leakage: asserts that no event in `selected_evidence_set` has `committed_at` or `effective_at` strictly greater than knowledge cutoff $K$.
  5. Enforces journal watermark: if `journal_watermark` is provided, asserts $K \le \text{journal\_watermark}$.
- In `services/agribrain/layer05_asmae/engine.py`:
  - When `bitemporal_replay_receipt` is supplied, the engine calls `verify_bitemporal_replay_receipt`. If verification fails, $K$ is set to empty and `diagnostics["bitemporal_receipt_validation"]` records the failure reason.
  - When $K$ is empty, `build_statewise_engine_support` fails closed with status `unavailable` and reason `unbound_namespace_or_bitemporal_receipt`.

### 2.3 Issuer Scope & Cross-Sensor Enforcement (IR04-5CC-P1-03)
- In `verify_scene_admission_receipt`:
  - Validates `grant["purpose"]` against `ALLOWED_ADMISSION_PURPOSES` (`kalman_state_observation`, `asmae_observation_admission`) and the key's configured purpose. Mismatches return `wrong_admission_purpose`.
  - Normalizes and compares `grant["source"]`, `scene.sensor`, and `trusted_key.source`. If a key provisioned for Sentinel-1 is presented for a Sentinel-2 scene, verification fails closed with `cross_sensor_admission_denied` or `issuer_source_scope_mismatch`.

### 2.4 Strict RFC 8785 Canonical JSON Serialization (IR04-5CC-P2-04)
- Implemented `canonical_grant_bytes(grant_claims)` using `rfc8785.dumps(_canonical_normalize(grant_claims))`.
- Replaced non-deterministic `json.dumps(..., sort_keys=True)` encoding.
- Rejects non-finite floats (`NaN`, `Infinity`, `-Infinity`) with `ValueError`.
- Added `"canonical_format": "rfc8785_jcs_v1"` to grant claims.

---

## 3. Test Execution Summary

| Test Suite | Execution Command | Result | Duration |
| :--- | :--- | :--- | :--- |
| **Focused Acceptance Suite** | `pytest services/agribrain/layer05_asmae/tests/test_asmae_c752_p1_p2_source_review_remediation.py -v` | **5 / 5 PASSED** | 6.41s |
| **Full Layer 05 Suite** | `pytest services/agribrain/layer05_asmae/tests/ -q` | **227 PASSED**, 1 deselected, 1 warning | 68.94s |
| **Frontend TAP Suite** | `node scripts/run-frontend-tests.mjs` | **341 / 341 PASSED** | 4.16s |
| **TypeScript Typecheck** | `npx tsc --noEmit` | **0 ERRORS** | ~2.5s |

### Acceptance Suite Breakdown
1. `test_c752_p1_01_bitemporal_replay_and_engine_separation`: Real `CanonicalWorldlineService` hydration and engine statewise evaluation separating valid time $T$ and knowledge cutoff $K$ ($K=10$ demotes to `none`; $K=21$ admits with effective resolution $11.77\text{ m}$).
2. `test_c752_p1_02_mandatory_namespace_and_positive_admission_authority`: 16 adversarial sub-tests verifying namespace matching, forged Ed25519 signature rejection, swapped asset byte detection, synthetic string rejection, untrusted key rejection, empty keyring fail-closed, missing private key `PermissionError`, cross-sensor rejection, wrong-purpose rejection, and RFC 8785 canonical determinism.
3. `test_c752_p1_02_bitemporal_authority_and_forged_cutoff_rejection`: 7 adversarial sub-tests verifying authentic receipt admission, forged `evidence_set_digest` rejection, tampered event detection, bitemporal future leakage rejection, forged watermark overshoot rejection, foreign namespace rejection, and engine boundary fail-closed behavior.
4. `test_c752_p1_03_multiband_s2_physics_conservative_psf`: Verifies conservative 20 m PSF ($\sigma=10.0\text{ m}$, $\text{FWHM} \approx 23.55\text{ m}$, native resolution $= 20.0\text{ m}$) for mixed 10 m / 20 m Sentinel-2 scenes.
5. `test_c752_p2_04_worker_reintegration_and_subprocess_cold_read`: True worker reintegration cold publication (`publication_reused: False`), out-of-process subprocess reading exact and latest snapshots, FastAPI `TestClient` REST endpoints 200, negative tampered node rejection (HTTP 409), corrupted head rejection, and missing sigma authority stripping.

---

## 4. Protected Invariants

- **Draft PR #32:** Remained open and unmerged at `64a9f699`. Fast-forwarding is strictly held pending user authorization.
- **Draft PR #30:** Untouched at `599c4f6`.
- **Protected `main`:** Untouched at `6edd372`.
- **Master Findings Register:** 238 findings across 3 cohorts (40 / 48 / 150) preserved; 0 closed.
- **Actuator Interlocks:** Strictly fail closed (`AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`).
- **Spatial Resolution & Numerical Publication:** 1 m spatial resolution certification and numerical publication authority remain strictly **ON HOLD**.
