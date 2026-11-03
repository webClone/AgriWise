# L0-004A — Positive State-Input Admission: Candidate Qualification and Migration Gates
Date: 2026-11-03

## Control plane and independent workstreams

- Source branch: `fix/layer0-positive-source-admission-20261103`
- Parent accepted software-regression baseline: `687a8e5b32b5fce94125aeacbbbf0d042d99a896` (reported L0 122, L1 21, ASMAE 84 all passed).
- Scientific Pilot PR #9 remains independent; neither its head nor main, master monograph, or historical frozen Layer 0 audit has been updated.
- This specification is a *bounded PR candidate and integration checklist*, not a statement that cryptographically authenticated data are deployed.

## Fixed vulnerabilities vs limits of scope

Before this change, `Layer0StateEngine.run_from_packets()` treated absent `real_provider_product`, absent `production_usable`, and absent positive source grants as permissible defaults. A packet could assert its own flags and modify state; even benign signed observational inputs would not protect against unsigned weather forcing. `ObservationPacket.content_hash` is not a signature and does not bind every mutable QA field.

**L0-004A code candidate:**
- `positive_observation_admission.py` implements a detached HMAC-SHA256 *verification* primitive, with domain/purpose separation:
  - `akaloris/layer0/positive-state-observation/v1`
  - `kalman_state_observation`
  - `weather_state_forcing`
- The trusted, server-provisioned issuer keyring maps key IDs to **authorized source values** and secret bytes. No key is hardcoded in production code or taken from the packet.
- The packet fingerprint is a full SHA256 of its current serialized evidence, not merely the user-supplied/stale 20-character content_hash. It covers source, timestamp, spatial identity, payload, uncertainty, QA, reliability, provenance and status.
- A receipt binds that fingerprint to exact expected plot, geometry hash/version, source, spatial scope, issue/expiry times and purpose; bad/unknown keys, cross-source/role use, mismatched content, future/counterfeit grant, or unbound caller scope are denied.
- When the engine is **explicitly provisioned** with the verifier, the canonical packet path requires appropriate signed receipts for BOTH scalar state observations and weather state forcing; ungranted data cannot enter those state inputs.
- The `Layer0Runner` accepts detached receipts and independently provisioned verifier. Health reports label authenticated state inputs and publish the exact packet digests actually admitted after numerical and QA checks.
- Without a verifier, the existing path remains available for backwards compatibility and is **explicitly labelled `LEGACY_UNVERIFIED`**. It is not a cryptographically qualified state path.
- The state package output hash is recalculated **after** excluded packet and authority health fields are attached; formerly it was sealed *before* those mutations.

## What this does *NOT* prove

1. This module does not issue grants, validate actual provider science or determine whether issuer payloads are true. Issuer signing must be controlled by independently authenticated data acquisition, quality QA, spatial calibration and a trusted scope/role registry.
2. It is not enough for a user to include `production_usable=True`, a claimed `VERIFIED_DELIVERY` label or a self-generated HMAC over their data. The **issuer keyring must stay server-controlled**.
3. It does not provide a live production key vault, rotation/revocation policy, per-tenant issuer ACLs, replay nonce ledger or a trusted wall-clock cut-off. The current receipt expiration uses injected `run_timestamp`, which must only be supplied by a trusted backend until a separate authenticated replay mode is implemented.
4. `Layer0StateEngine.run()` can still accept direct scalar `KalmanObservation` values without passing through this packet verifier; the internal API must be fenced or explicitly classed as simulation/diagnostic for production.
5. Existing runtime `Layer0Runner()` calls default to `LEGACY_UNVERIFIED`; strict mode cannot be declared mandatory until approved issuers, deployment secrets and all producer/consumer migrations are proven.
6. Full publication authorization, Layer 1/ASMAE data lineage, credible interval calibration, partial spatial support and persistence/immutability remain separate release gates.
7. HMAC verifies **issuer authenticity and exact statement content**, not whether a remote sensor truly measured that value. Raw state outputs remain **state estimates**.

## Required L0-004B implementation before closing the original finding

- Configure an independently authorized issuer registry, key isolation and rotation. Do not expose signing keys to public API routes, farmer clients, or untrusted ingestion payloads.
- Restrict receipt issuance to native provider QA and documented sensor validation, with issuer identity, plot and geometry authorization derived from trusted backend context, not request JSON.
- Make strict input admission mandatory for every scientific-state production entrypoint. Audit and fence `Layer0StateEngine.run`, Layer 1 legacy input adapters, orchestration paths and any direct `ProcessModel.predict` calls.
- Bind correct source-specific origin, scope, geometry version, acquisition/ingestion dates, temporal cutoff, quality, support and scientific evidence availability. Sign source receipts only AFTER actual QA.
- Move receipt expiry and revocation to a trusted security clock; distinguish reproducible historical replay from valid live authorization. Add an immutable replay ledger and key-revocation receipts.
- Require full receipt lineage and complete forcing-content identity in the pilot's signed publication root before any merge into shared main; integration only at a pinned cross-track commit.
- Test producer-to-receipt-to-state-to-L1/ASMAE-to-pilot flow with real relevant source and DB/browser gates.

## Tests and acceptance

New candidate regressions:
`services/agribrain/layer0/tests/test_positive_observation_admission.py`
assert correct signed observation acceptance, unknown key/malformed MAC, cross-source and cross-purpose rejection, scope mismatch, lack of caller geometry, expired/future/naive time, current QA/reliability/payload tampering, empty receipts, signed weather/observation separation, legacy classification, and output hash sealing.

Existing suites required again on the **new exact commit**:
```powershell
git fetch origin
git switch fix/layer0-positive-source-admission-20261103
git pull --ff-only
git rev-parse HEAD
py -m pytest -q services/agribrain/layer0/tests/test_positive_observation_admission.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

No new test execution has been independently conducted by the authoring assistant in this connector session. The earlier 122/21/84 pass receipt belongs only to `687a8e5`, not these subsequent commits.

**Disposition:** L0-004A verifier+optional strict gate **implemented / unqualified**. L0-004 **OPEN** until trusted mandatory runtime issuance, independent scope grants and full published-lineage integration are qualified. L0-002 is also **PARTIAL**; matching strings and signature over a signed claim do not independently prove plot ownership or physical footprint without issuer ACLs.
