# Layer 0 L0-004B1 — Mandatory Production Admission and Verified Input-Root Gate

**Date:** 2026-11-03  
**Parent reported passing baseline:** `6da232430401d664d4f59bba30992ac66d886191`  
**Track:** Layer 0 remediation, independent of Scientific Pilot PR #9  
**Status:** Code candidate committed; **all new-HEAD tests and deployment acceptance PENDING**  
**Architecture monograph and frozen 469-finding audit:** unchanged

## 1. Prior acceptance

The user supplied pinned local receipts for `6da2324`: Layer 0 **149/149**,
Layer 1 Fusion **21/21**, and the full ASMAE set **84/84**, including the
real-raster EnKF test. Those receipts qualify **only that parent commit**;
they do not qualify the current L0-004B1 code or a production deployment.

Important source corrections: the 004A verifier does **not** require a
satellite observation to have been acquired after grant issuance (nor should
it in general: authentic historical imagery may be QA-qualified later).
It does require the observation timestamp not be *future relative to run
time*, valid signature/purpose/scope, and grant issuance/expiry around the
run time. In 004B1, mandatory live runs use a protected UTC clock, not a
user-supplied historical run timestamp.

The prior 004A positive spatial scope is plot/geometry/version plus
`spatial_scope` class; it does **not** certify zone polygon membership,
tenant ACLs, or physical footprint.

## 2. 004B1 code changes

### Mandatory server policy

`services/agribrain/layer0/production_admission.py` requires signed source
inputs if ANY of NODE_ENV/ENVIRONMENT/ENV/APP_ENV indicates
`production`, `prod` or `staging`. A trusted deployment can opt in in
other environments via `AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS=true`.
A `false` value does not disable production.

Mandatory mode never creates a development HMAC key or silently falls back
to unsigned state. A verifier must be present and of the expected type,
both at construction and at packet use (including when policy hardens on
an existing worker).

### Server-only trust root provisioning

`load_server_issuer_verifier()` loads the backend deployment's
`AKALORIS_LAYER0_ISSUER_KEYS_JSON` string, **which must be injected from
a secrets manager** (not an HTTP header, client, user JSON or packet).
Accepted schema: a nonempty JSON object with each key ID mapping to
`{"source":"sentinel2","secret_b64":"<base64 of >=32 random bytes>"}`.
Production startup rejects missing, malformed, duplicate, short or invalid
key records without printing secret material.

Rotation is possible by deploying a new key registry; durable revocation,
tenant/source authority allocation, issuer ACL review, key vault controls,
and issuance remain **external work**. A signed grant establishes an
issuer statement's authenticity, NOT correctness of satellite/sensor data.

### Hard-fenced entrypoints

- `Layer0Runner()` loads trusted server verifier when mandatory and none
  has been injected through trusted application code.
- `Layer0StateEngine.run_from_packets()` requires exact detached grants for
  state observations and environmental forcing; strict checks are
  reevaluated at runtime.
- `Layer0StateEngine.run()` refuses direct raw
  `daily_weather/observations_by_day` calls in mandatory mode unless
  invoked with the engine's private per-instance packet-path capability.
  This is a software API fence, not a protection boundary against already
  compromised Python code in the same process.
- `orchestrator_v2/runner.py` refuses unverified legacy fallback on any
  Layer 0 runner exception while signed policy is mandatory.
- `layer1_fusion/data_fusion.py` also stops modern→legacy and
  interpolation fallback under mandatory policy, until an authorized
  canonical state package integration replaces its direct scalar path.

**Availability consequence:** production/staging scientific processing
may fail closed until real source issuers and receipts are wired. This is
deliberate; do not weaken the policy to make pilot tests pass.

### Live time and historical replay

In mandatory mode `Layer0Runner.run()` and
`Layer0StateEngine.run_from_packets()` use an independently sampled UTC
wall clock for receipt admission and actual run provenance. An old caller
`run_timestamp` cannot resurrect an expired HMAC grant. Historical
satellite acquisition can still precede grant issuance. A fully authorized
historical replay system requires a separate replay-issuer identity,
retention/revocation model and immutable ledger; this PR does not implement
that system.

### Source input lineage and publication boundary

- `Layer0StatePackage.provenance.positive_state_input_manifest` binds
  accepted signed receipts (the public grant+MAC, **never secret keys**),
  plot/geometry/version/window and final weather-field receipt lineage.
- `input_hash` is full SHA-256 of the canonical manifest. Complete
  effective weather forcing only is counted; incomplete weather must
  remain degraded with no applied-weather receipt root.
- `Layer0StatePackage._generate_output_hash()` now also binds a nonempty
  `input_hash` to the output hash, preserving the old form for
  legacy `input_hash=""`. Existing output-hash truncation is **not**
  a high-assurance signed pilot publication receipt.
- Health distinguishes mandatory signed input policy, count of signed
  inputs, and records `state_output_role=STATE_ESTIMATE` plus
  `scientific_publication_authorized=False`.
- Raw Layer 0 source packages and alternate L1/ASMAE consumers must still
  enforce issuer receipts and authoritative spatial support in a separate
  pinned shared-contract integration. The manifest is the proposed
  handoff, not an authorization of pilot publication.

## 3. Mandatory requalification at exact new SHA

Run in a clean development/test environment; **do not set production env**
for the entire suite. The dedicated tests simulate production safely with
monkeypatch, and use test-only HMAC fixtures:

```powershell
git fetch origin
git switch fix/layer0-production-admission-gate-20261103
git pull --ff-only
git rev-parse HEAD

py -m pytest -q services/agribrain/layer0/tests/test_mandatory_source_admission.py
py -m pytest -q services/agribrain/layer0/tests/test_signed_state_input_manifest.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/
```

In addition, test the full production orchestrator explicitly with missing
trust roots: it must not emit an authorized publication or fall back to
unverified layer paths. Run a second test with a secure configured keyring
but **no receipts**: packets must not modify the state as authenticated
observations. Test actual source receipt issuance only after an approved
backend QA/plot authorization service is implemented.

## 4. Remaining release blockers (L0-004B2+)

1. **No verified native data-source issuer integration.** The runtime
   cannot legitimately generate receipts merely by signing packet claims;
   ingestion must independently establish provider and geometry truth.
2. **No deployed secret-vault, durable revocation or per-tenant issuer ACL**.
   The environment adapter is a provisioning boundary, not proof of
   operational key lifecycle management.
3. **No separate authenticated replay ledger or historical security clock**;
   current mandatory policy intentionally operates in live mode.
4. **Legacy adapters and direct source-package paths** in Layer 1/ASMAE
   require a separate inventory and signed lineage enforcement.
5. **No pilot publication/authorization binding yet.** PR #9 remains on
   its independent branch; a future integration must confirm exact SHA,
   signed issuer/geometry/temporal support, proof root and actual
   publication fencing at both producer and consumer.
6. **No zone-geometry receipt membership, empirical covariance calibration,
   or L0-02C3/C4 trusted infiltration/Q/replay**.
7. **No external reproducible test receipt at this new candidate SHA.**
   Previous 149/21/84 results cannot automatically carry forward.

**Disposition:** L0-004B1 software controls **implemented, unqualified**.
L0-002 positive spatial support and L0-004 production authority remain
**PARTIAL/OPEN** until issuer, deployment, and full pilot integration gates
are demonstrated. No modification to the master monograph or historical audit.
