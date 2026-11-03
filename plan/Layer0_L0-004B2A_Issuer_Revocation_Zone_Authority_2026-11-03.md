# Layer 0 — L0-004B2A Issuer Revocation and Zone-Scope Qualification

**Date:** 2026-11-03  
**Repository:** `webClone/AgriWise`  
**Parent:** PR #15, `0265c2002061ac784bc7efad6d764ec40ae2880e`  
**Track:** independent Layer 0 remediation; Pilot PR #9 remains unchanged  
**Status:** NEW CODE CANDIDATE; FOCUSED AND DOWNSTREAM EXECUTION PENDING  
**Authority:** scientific-state evidence admission only. **NOT** pilot publication or actuator authorization.

## 1. Baseline and source-verified correction

The user reported PR #15 at the exact parent SHA:
- Layer 0: **174/174 passed**
- Layer 1 Fusion: **21/21 passed**
- ASMAE: **84 collected**; 83 fast cases passed, 1 real-raster EnKF still in progress in the latest message
- The preceding PR #14 had 84/84 passed at a *different* SHA.

**Do not attribute the parent passes to this new branch.**

Code at PR #15 uses:
- `AKALORIS_LAYER0_ISSUER_KEYS_JSON` and `load_server_issuer_verifier()`
- `NODE_ENV`, `ENVIRONMENT`, `ENV`, `APP_ENV`, and `AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS`
- `Layer0StatePackage.input_hash` plus `positive_state_input_manifest`; `output_hash` binds nonempty `input_hash`
- `health_report.scientific_publication_authorized=False` and `state_output_role=STATE_ESTIMATE`.

Do not substitute older status summaries' variant symbol names for these actual pinned APIs.

## 2. Revocation-aware verifier (L0-004B2A)

`services/agribrain/layer0/issuer_revocation.py` introduces an *independently controlled* `TrustedRevocationGate` over `IssuerRevocationSnapshot`:
- Registry returns exact key-id statuses `active`, `retired`, or `revoked`; **missing key means denied**.
- Snapshot must have valid UTC-aware issue and expiry times, finite freshness window (default 300 seconds), and a monotonic nonnegative revision.
- A lower revision fails as a rollback; a changed snapshot at the same revision fails as a conflict. These protections are **in-process**, not distributed consensus.
- Backend lookup errors, malformed/stale records and unknown issuers fail closed, never silently fall back to the last allowed key.
- `PositiveObservationAdmissionVerifier.verify` checks the live authority **after** verifying exact packet digest, source, signed purpose/scope and HMAC.

`load_server_issuer_verifier()` now optionally loads:
- `AKALORIS_LAYER0_REVOCATION_SNAPSHOT_PATH`: trusted server-managed JSON file re-read on each check. Exact schema `revision`, `issued_at`, `expires_at`, `key_statuses`. The deployment must restrict who can write/replace this file.
- `AKALORIS_LAYER0_REQUIRE_LIVE_REVOCATION=true`: opt-in mandatory enforcement. In a signed-input deployment this causes startup/packet rejection when no trusted live revocation gate is provisioned. False/missing keeps backwards-compatible, explicitly **UNMANAGED**, issuance status and is **not** proof of revocation qualification.

The per-run state entrypoint revalidates every materially admitted signed observation/complete weather receipt against the latest revocation snapshot **both before and after** state computation, before releasing its output package. Any invalidation or snapshot revision change aborts output release. This reduces, but cannot eliminate, the time-of-check/use gap until state and publication are transacted with the authoritative revocation ledger.

The state input manifest includes the accepted revocation revision/digest when configured, and the output hash binds the resulting input root. The health audit labels `issuer_revocation_mode=TRUSTED_LIVE_SNAPSHOT` or `UNMANAGED`. **Neither label grants publication authority.**

### Key rotation semantics

A new key ID may be provisioned alongside an old active key. After the new key is deployed and receipts migrate, the registry must mark the old ID `retired` or `revoked`, then increment its revision. Revocation of the old key denies old receipts even if their HMAC is authentic and unexpired. Replay retention, downstream artifact invalidation, and key-vault audit remain separate.

## 3. Signed zone-specific admission (L0-002 partial)

`spatial_scope="zone"` alone is not proof of a particular zone. Therefore:
- Legacy **v1** grants are accepted for `plot` scope only. They cannot authorize zone observations.
- A zonal grant must use `ZONE_GRANT_DOMAIN=akaloris/layer0/positive-zone-state-observation/v2` and include signed `zone_id` and `zone_geometry_hash` fields.
- The packet's exact content digest must match; its `payload.zone_id` and `payload.zone_geometry_hash` must match the signed grant.
- The verifier independently checks that zone ID and hash against its backend-trusted registry for the caller's plot hash and geometry version.
- The Layer 0 state entrypoint also rejects a zone not explicitly listed in that run's `zone_ids`. Signed zone weather forcing is *not* authorized by these observation grants.
- `AKALORIS_LAYER0_ZONE_REGISTRY_PATH` optionally loads a backend-managed JSON object of plot IDs to `{geometry_hash,geometry_version,zones:{zone_id:zone_geometry_hash}}` entries.

**Scope limitation:** matching signed zone IDs and hash values **is not** a proof of actual raster footprint intersection, support-fraction qualification, tenant ownership, or MESIA containment. Those are separate trusted producer/plot registry and geospatial predicates. Do not equate `zone_authority_configured=True` with full MESIA certification.

## 4. Tests (new candidate)

`services/agribrain/layer0/tests/test_issuer_revocation_zone_authority.py` covers:
- active/unknown/retired/revoked key IDs
- trusted-policy outage, stale/future snapshot, rollback and same-revision conflict
- dual-key rotation with old-key retirement
- v1 plot compatibility; v1 signed zone denial; v2 zone with/without registered trusted zone hash
- forged zone ID/hash, tampered payload, cross-purpose weather denial
- wrong/unlisted zone at canonical state run and correctly admitted selected zone
- live file-backed policy change without packet/client control
- revocation before state estimation AND revocation during computation blocking output release
- mandatory live revocation with no trusted configuration.

Required exact new-head execution:

```powershell
git fetch origin
git switch fix/layer0-issuer-revocation-zone-20261103
git pull --ff-only
git rev-parse HEAD

py -m pytest -q services/agribrain/layer0/tests/test_issuer_revocation_zone_authority.py
py -m pytest -q services/agribrain/layer0/tests/test_positive_observation_admission.py
py -m pytest -q services/agribrain/layer0/tests/test_mandatory_source_admission.py
py -m pytest -q services/agribrain/layer0/tests/test_signed_state_input_manifest.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

**No new-head execution receipt has been independently produced in this session.** Mark candidate DRAFT, not accepted.

## 5. Unresolved L0-004B2B and pilot integration

1. **No real native provider issuer.** There is no independent production issuer that verifies a Sentinel scene ID, signed/confirmed provider response, QA, actual spatial/temporal coverage and trusted plot registration *before* issuing a grant. Do not invent a signer from arbitrary packet JSON. Build isolated provider-specific acquisition validators and a server-only issuance worker, with a separate signing key and forced source/purpose/geometry ACL.
2. **No real DB/KMS integration.** The trusted-file adapter assumes deployment protects its files. Cross-worker monotonicity, replacement/write isolation, key rotation/revocation distribution, proof of freshness, historical replay permissions and audit immutability require operational testing.
3. **No full zonal geospatial evidence.** Trust registry data must come from authoritative plot/zone polygons and MESIA-qualified spatial support; a user-defined `zone_geometry_hash` by itself is not sufficient.
4. **No transactionally bound publication revocation.** State input manifests are evidence-lineage artifacts, not signed permission to publish. A separate pinned integration with Pilot PR #9 must bind producer receipts, revoked-source preflight, exact plot/zone geometry/temporal support, output root, and all existing pilot publication/authorization controls.
5. **No L0-02C3/4 closure.** Verified delivered irrigation/net infiltration, calibrated process/forcing/exposure uncertainty `Q(Δt)`, and durable event replay remain separate.
6. **Pilot, main and architecture monograph stay untouched.** Preserve frozen audit and record current repair dispositions separately.

**Disposition:** L0-004B2A revocation/zone controls IMPLEMENTED AS A TEST CANDIDATE. L0-002 positive geometry and L0-004 complete producer issuance/revocation remain **PARTIAL/OPEN**. No merge until all pinned gates pass.
