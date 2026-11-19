# ASMAE IR-04 — Admission trust boundary security candidate

Date: 2026-11-19
Origin: 5ccca4a source review / 8c357ad3 tracking review head
Isolation: feat/akaloris-asmae-ir04-admission-trust-review-20261119
Status: CODE SUBMITTED FOR INDEPENDENT QUALIFICATION — NOT SCIENTIFICALLY CERTIFIED

## Delivered code

1. Removed hardcoded production HMAC secrets, issuer-secret registration and receipt-signing functions from the production observation-footprint adapter.
2. Added verifier-only Ed25519 admission_trust.py. Public keys are read exclusively from explicitly configured AKALORIS_LAYER0_ADMISSION_VERIFIERS_JSON. No default root exists, and absent/malformed configuration rejects scientific support.
3. Each issuer is restricted to one source (S1 or S2), purpose (kalman_state_observation), and domain (akaloris/layer05/positive-scene-admission/v1). Grants bind tenant, farm, plot, geometry, exact asset bytes, H operator and calibration digests, valid/commit timestamps, issuance and expiry.
4. Versioned the canonical payload profile as akaloris/sorted-json-utf8-strings/v1. This is an intentionally limited sorted UTF-8 JSON profile over a fixed schema of string fields; do NOT describe it as RFC 8785 compliant.
5. Added bitemporal_receipt_verifier.py: rehydrate a claimed (T,K) from the process-configured durable-anchored CanonicalWorldlineService, independently compare selected evidence identity/digest, namespace and generation. The engine no longer treats raw receipt query fields, scene dates, or a caller-provided journal_watermark as scientific temporal authority.
6. Updated the historical C752 suite to use ephemeral Ed25519 test-only signers, and added security tests for absent keys, HMAC rejection, wrong issuer/source/purpose, tampering, expiry and forged T/K.

## External deployment obligations

- Provision only raw Ed25519 public verification keys out of band. Keep private Layer 0 issuer keys outside ASMAE and the tracked repository.
- Rotate every secret that was previously embedded in source if used in any deployment. Reject and revoke old HMAC grants.
- Emit detached Ed25519 signatures from an independently controlled authorized Layer 0 issuer.
- Missing credentials or durable journal authority must result in unavailable local scientific support, not synthetic acceptance.

## Qualification state

- Scoped source changes exist on isolated security review branch.
- Targeted new tests were AUTHORED BUT NOT EXECUTED in this environment.
- Backend 226, frontend 341, and earlier test receipts belong to older candidates, NOT this patch.
- Full ASMAE standard / quick-visual, actual cold worker publication, frontend, and TypeScript checks remain REQUIRED.
- Durable journal rehydration proves consistency with the local Worldline store; it is NOT yet a cryptographically signed external (T,K) authority. Signed durable anchor/watermark qualification remains OPEN.
- Legacy evidence_classifier.py has separately embedded HMAC trust material and is not remediated by this focused adapter batch.
- Original 238 master findings remain preserved; zero independently closed.
- IR-08 adaptive solver and certified 1 m resolution remain ON HOLD.
- Numerical publication authority and verified irrigation actuation remain ON HOLD.

## Git boundaries

No change to draft PR #32, PR #30, or protected main. Independent source review and SHA-specific test logs required before considering any fast-forward.
