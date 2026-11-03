# ADR-L0-004B2B-001 — Native acquisition evidence and v3 receipt boundary

- **Date:** 2026-11-03
- **Status:** ACCEPTED FOR B2B-01 DESIGN; v3 signing service NOT IMPLEMENTED
- **Pinned base:** `952d41118322ee19d0ffe1c28c37db355e91dfb5` (PR #16)
- **Implementation branch:** `fix/layer0-native-acquisition-evidence-20261103`
- **Planning reference:** PR #17 `fb28f0e49edeeb350db8651dfdd4d0c7a36e6722`, held separately
- **Scope:** B2B-01 native acquisition capture only; do NOT modify the R3 monograph, pilot PR #9, or historical Layer 0 audit.

## Decision 1: Evidence must precede authority

Capture **the exact provider response bytes** and a canonical request digest at the HTTP fetch boundary, not by reconstructing a response from previously cached raster values or copying an unverified `metadata.json`. Record allowlisted endpoint, sensor, retrieval UTC, product selection (Process request), request/response SHA-256 and a nonsecret backend credential reference. A record is `NOT_QUALIFIED` with `provider_signature_verified=false` even if obtained via authenticated TLS.

B2B-01 uses a local content-addressed write-once object+manifest store. Equal concurrent writes agree; altered existing objects fail. This local adapter **does not** defend against a compromised filesystem operator, arbitrary deletion, filesystem rollback, or distributed-worker inconsistency. Production use requires versioned WORM/immutable object storage with independent IAM and audit, tested before trusted issuance.

Never insert bearer tokens, provider client secrets, API keys or request Authorization headers into evidence manifests. Refuse ambiguous or noncanonical request JSON. Provider responses over 256 MiB fail rather than truncate. Non-allowlisted endpoints cannot generate a live capture.

`OriginClass` is a **retrieval classification**, not scientific or cryptographic authorization:
- `LIVE_PROVIDER_AUTHENTICATED`: captured immediately from allowlisted backend HTTPS request using service credentials. It is *not* a provider-signed statement; the local capture cannot prove truth independently.
- `PROVENANCE_VERIFIED_CACHE`: persisted local manifest and raw-object hashes match a previously captured live response; never reclassify a cache read as a new live request.
- `REANALYSIS`, `FORECAST`, `TEST_FIXTURE`, `USER_DECLARED`: distinct origins requiring their own qualifier; never promoted through self-asserted booleans.

`capture_backend_provider_response()` is opt-in under `AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT`; `AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE=true` makes the root mandatory. Without configured storage, existing retrieval remains `UNATTESTED` for this new provenance contract. **Neither mode grants positive signed state-input admission.**

## Decision 2: Keep native acquisition separate from the state-input grant

B2B-01 produces `NativeAcquisitionReceipt` only. It is not a new `ObservationPacket`, not an HMAC grant, not an issuer decision and not an authorized Layer 0 source. `SceneProduct.native_catalog_acquisition_id` and `native_process_acquisition_id` are links to unqualified evidence, with `native_evidence_status=CAPTURED_UNQUALIFIED` only when a Process response has been stored.

Catalog and Process are separate responses with separate digests, because a Catalog scene ID alone does not guarantee the Process payload contains the selected product. B2B-02/B2B-03 must join these records and independently verify exact Catalog→Process binding, masks/orbit, product date, CRS/grid/polygon support and science QA **before** an issuer ever signs.

Cached files from the existing real_scene directories are NOT automatically retroactively attested. A future cache migration requires original independently recorded raw acquisition and storage version, not a self-generated hash made after the fact.

## Decision 3: Versioned asymmetric v3 grant is the target

Production receipt target: `akaloris/layer0/positive-state-input/v3` with asymmetric signing. Prefer Ed25519 when supported by the approved HSM/KMS; otherwise ECDSA P-256/SHA-256 with strict deterministic encoding. Issuer private keys remain in an isolated privileged signing service, and Layer 0 verifiers hold only public keys. Select and test one exact canonical signed representation before enabling either algorithm; **existing Python canonical JSON and prospective RFC 8785/JCS must not be treated as interchangeable without test vectors**.

Minimum v3 signed claims:
- explicit domain/version/algorithm/key ID and issuer identity
- complete SHA-256 of **current** ObservationPacket, purpose (`kalman_state_observation` or `weather_state_forcing`), source and permitted variables
- independently qualified acquisition/evidence ID, qualification decision ID, policy/QA versions and immutable scientific support root
- tenant/plot ID, authoritative geometry hash/version; signed zone ID, zone geometry hash and physical MESIA support root for zonal evidence
- acquisition UTC start/end, provenance type (observation, modeled historical, reanalysis or forecast) and allowed temporal role
- issue/expiry timestamps, bounded validity, revocation revision anchor, issuer decision ledger ID and replay/idempotency key
- explicit DENY/no-grant on missing/unknown evidence or mismatched science/tenant/scope.

### v1/v2 transition and deprecation checkpoints

Current HMAC v1 plot and v2 zone domains are **verification-compatible legacy paths only**. Do not modify their field sets or domains, expose HMAC keys to frontend/API clients or authorize new issuer endpoints that sign arbitrary JSON.

- **Checkpoint A / B2B-01:** no new issuer at all; legacy verifier unchanged.
- **Checkpoint B / B2B-06 issuer qualification:** if a transitional internal v1/v2 issuer is essential, document exact isolated producer/IAM/expiry limits and require review; do not create it by default.
- **Checkpoint C / B2B-08 pilot integration:** all production source-specific receipt issuers must use tested asymmetric v3; legacy v1/v2 inputs remain explicitly classified and do not become newly publication-authorized merely because they pass the existing verifier.
- **Checkpoint D / production launch:** prohibit production issuance of v1/v2; disable acceptance of legacy source grants on critical scientific publication paths after data migration and historical replay contract are accepted.

These are **acceptance milestones**, not invented calendar dates. No cryptographic migration is claimed complete by this ADR.

## Decision 4: Fail closed without scientific side effects

No raw response or manifest can set `production_usable=True`, update Kalman state, produce verified delivery, or grant pilot publication. The pilot and master monograph remain unchanged; the Layer 0 state output is always a `STATE_ESTIMATE`.

Required B2B-01 regressions:
1. Raw bytes and canonical request mutation change exact digests; response ID and retrieval timestamp bound to acquisition identity.
2. Partial or tampered objects/manifests fail; same idempotent capture does not overwrite different bytes; no symlink promotion.
3. Missing bearer-bound service request, wrong HTTPS endpoint/status, secrets inside requests, nonfinite values and oversized payloads reject.
4. Cache read returns `PROVENANCE_VERIFIED_CACHE`, never LIVE or QUALIFIED.
5. Provider fetches include separate Catalog and Process acquisition IDs; no fallback cache or test override gets a fabricated live ID.
6. All existing Layer 0, Layer 1 and ASMAE suites rerun at the **new head**, not inherited from PR #16. Actual Sentinel Hub calls must be opt-in because of credentials/quota.

**Not in B2B-01:** native weather connector, provider QA, actual crop/zone spatial support, issuer KMS, signed revocation snapshots, distributed durability, L0-02C3/C4 or pilot publication binding. Continue each as separate bounded work.
