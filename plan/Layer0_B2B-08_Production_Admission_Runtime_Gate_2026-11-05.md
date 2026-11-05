# Layer 0 B2B-08 — Production Admission Runtime & Operational Readiness

**Parent / frozen milestone:** `B2B-07@f7f40cbfd45bfb43a7a02a2519e6991e300b22bf` (formal freeze).  
**Branch:** `feat/layer0-b2b08-production-admission-runtime-20261105`.  
**Status:** INITIAL INTEGRATED B2B-08 COHORT — NOT QUALIFIED OR FROZEN.  
**Scope:** connect existing B2B-05/B2B-06/B2B-07 trusted inputs to actual service startup, scoped request execution, and operational evidence. **Not** new physical theory, actuator control, field-validation claims or a repeat of 469 findings.

## 1. Starting point and evidence

- **B2B-07:** 829/829 distinct Python tests, 105/105 frontend tests, and connected Docker Mongo rs0 signed L3 delivery 2/2. This is local operator-reported software/integration qualification, not field calibration, HSM production attestation, or national publication authority.
- **B2B-08 code gap:** `services/agribrain/layer0/production_admission.py` provides `configure_server_delivery_verifier()`, but `services/agribrain/app/main.py` lifespan does **not** provision a verifier on `app.state`. The B2B-07 tests manually constructed a trusted verifier rather than proving production application wiring. `Layer0StateEngine` accepts injected verifiers, so untrusted HTTP callers must never supply authority adapters.
- **Audit baseline:** 469 historical static findings are grouped under six remediated clusters; this reconciles the classification, not 469 individually inspected test receipts. B2B-08 does not modify `findings/layer0.md`.
- **Plan precedence:** existing `plan/README.md`, 52-package plan and 17-stage sequencing remain authoritative. New production runtime integration does not revise the intended master monograph or retroactively grant completion of package cards.

## 2. B2B-08A — Fail-closed trusted runtime bootstrap

**Goal:** fully separate deployment-provisioned trust roots from HTTP and start a safe server-owned delivery-verifier lifecycle.

1. Add `app/production_delivery_runtime.py` with a mandatory explicit opt-in flag `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=true`. Default **OFF** means no L3 physical forcing, no L3 signer/verifier created. An unrecognized flag value is an error, not implicit authorization.
2. Opt-in requires signed input policy, mandatory asymmetric v3, live revocation and strict authenticated plot scope. Bind only to the shared server MongoDB database, verified replica set/sharded transaction support, operator-provisioned L3 public keys and a live durable revocation snapshot. Do not accept configuration in request payloads or persist signing secrets in Layer 0.
3. Separate purpose-specific L3 key configuration from observation issuers. Enforce public-key-only schema, valid timestamps/algorithms, active issuer + fresh revocation ledger, and protected file-backed live revocation refresh.
4. Wire a single verifier instance into FastAPI lifespan `app.state`, with fail-closed process startup when enabled and prerequisites are missing. Retain disabled baseline and never change B2B-07 cryptographic or idempotency contracts.
5. Introduce a *server-only* Layer0StateEngine construction helper that takes this verifier from `app.state`; neither HTTP body nor untrusted packet may inject verifier, tenant, geometry epoch or revocation configuration.

**Acceptance:** startup-disabled baseline, enabled happy path, missing secret, private key injection, stale/revoked snapshot, wrong Mongo mode, invalid config, strict-v3 off, missing geometry gate; all deny with stable, non-secret errors. Record exact-head test counts.

## 3. B2B-08B — Scoped production execution surface

1. Route a real authenticated plot-scoped **packet** run through the trusted engine constructor. Scope identity must come from `PrismaPlotOwnershipStore` + the authenticated principal provider and current geometry epoch; do not create a bypassing parallel state engine.
2. Persist and reference input lineage, delivery receipt IDs, durable commit snapshot ID, numerical uncertainty, Q assumption and signed state provenance. Explicitly propagate diagnostic-only / unverified evidence without state update authority.
3. Guarantee replay/restart recovery under multiple application workers, and reject stale tenant ownership/geometry changes at request and state commit boundaries.
4. Keep Layer 0 estimates distinct from SIRE publication and actuator grant issuance. The integration must not invoke `irrigation_runtime/dispatcher.py` or alter independent Pilot PR #9.

**Acceptance:** authenticated create → edit → scoped packet admission → signed physical delivery → Kalman state → durable snapshot → process-restart recovery; foreign tenant, stale geometry, revoked issuer, missing trusted keys, tampered L3 receipt and cross-worker replay negative cases. Use disposable DB/plot.

## 4. B2B-08C — Operations, observability and deployment gates

- Service readiness reports whether L0 trust roots and Mongo transaction capability are provisioned, **never** issuer secrets, receipt seals, unredacted plot identities, or token objects.
- Environment/deployment playbook for local Docker replica set, staging, key rotation, revocation refresh, backup and snapshot-journal recovery; no silent fallback on network outage.
- Preserve numerical uncertainty/calibration disclaimers. Field measurement calibration, external L3 signer/HSM, human operating approvals and national publication readiness are separate qualifications.
- Run targeted B2B-08 startup tests; full L0, L1, ASMAE fast; TypeScript and frontend; 365-day real-raster pipeline once on final A+B+C SHA; connected multiworker Mongo and one signed L3 plot workflow.

## 5. Protected boundaries and release discipline

- Frozen B2B-04B weather PR #25 `f320e78`; B2B-05 `661f003`; B2B-06 `985b6af`; B2B-07 `f7f40cb`; Scientific Pilot PR #9 `71ee1f7`; `main@6edd372`.
- No modifications to `findings/layer0.md`, the master monograph, or prior frozen gate documents.
- Do not merge PR #26, PR #27 or B2B-08 without explicit authorization.
- B2B-08 stays **NOT FROZEN** until live service and actual packet-run acceptance; passing isolated factory/startup tests is only B2B-08A progress.
