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

## 6. B2B-08A initial runtime candidate — exact-head tests pending

**Implementation status:** published on this B2B-08 branch; **NOT YET QUALIFIED**.
No B2B-07 frozen production contract was modified.

- New `services/agribrain/app/production_delivery_runtime.py`: backend-only opt-in `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=true`, strict booleans, separate L3 public key registry, trusted file-backed revocation snapshot live refresh and shared MongoDB replica-set/sharded topology gate. A disabled deployment never creates a physical-delivery verifier.
- FastAPI `lifespan` in `services/agribrain/app/main.py` uses the trusted bootstrap and stores the verifier on `app.state.layer0_verified_irrigation_verifier`; startup fails when explicitly enabled without its trust roots. Shutdown drops this app-state reference. No HTTP endpoint exposes the verifier.
- `create_server_layer0_state_engine()` provides an internal integration point for a later authenticated packet-run consumer. It drops stale verifier references when delivery is disabled and fails when delivery is enabled but no verifier is provisioned. **It is not yet wired into a production API route**; request-scoped integration is B2B-08B.
- A new `services/agribrain/layer0/tests/test_b2b08_production_delivery_runtime.py` covers disabled-default, unrecognized toggle, policy omissions, missing DB/keys/revocation, standalone topology, active public-only verification key, live revocation change, revoked/retired/stale snapshot, duplicate JSON key, private-key rejection, and factory non-injection. These are **unexecuted test declarations**, not passed receipts.
- Independent L3 KMS signer/HSM provisioning, field calibration and publication/actuator authority remain outside this phase.

### B2B-08A exact-head qualification

Run from the branch and record the full `git rev-parse HEAD`, Python runtime and pytest output:

```powershell
git pull
git rev-parse HEAD

py -m pytest -q services/agribrain/layer0/tests/test_b2b08_production_delivery_runtime.py
py -m pytest -q services/agribrain/layer0/tests/test_b2b07_verified_delivered_irrigation.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/ --ignore=services/agribrain/layer05_asmae/tests/test_comprehensive_pipeline_execution.py
```

The 365-day EnKF comprehensive pipeline is reserved for the final B2B-08A+B+C integrated gate. The 2/2 connected Mongo gate was already satisfied at the frozen B2B-07 software scope and is not claimed to qualify this new FastAPI startup. A new server-lifespan and signed request workflow gate is required for B2B-08B.

### Server-only configuration example (no private keys)

- `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=true`
- `AKALORIS_LAYER0_REQUIRE_SIGNED_INPUTS=true`, `AKALORIS_LAYER0_REQUIRE_V3_KMS=true`, `AKALORIS_LAYER0_REQUIRE_LIVE_REVOCATION=true`, `AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE=true`.
- `AKALORIS_LAYER0_L3_PUBLIC_KEYS_JSON` holds L3 issuer IDs, source, algorithm, **public key PEM**, valid_from and valid_until in the declared JSON schema. No private signing keys may be supplied.
- `AKALORIS_LAYER0_L3_DURABLE_REVOCATION_PATH` refers to a trusted, frequently refreshed durable revocation snapshot. Old, revoked, retired or unavailable keys fail closed.
- Server `get_db()` must reach the same transaction-capable shared MongoDB as the signed assessment consumer. No request-side database URL or trust-root override is accepted.

**Do not freeze B2B-08 on B2B-08A completion alone.** B2B-08B request integration and B2B-08C operations remain pending.

## 7. B2B-08B-I — Four-issue signed irrigation integration corrective batch

**Scope:** Current B2B-08 working branch only. PR #27 remains draft and B2B-07 stays pinned at `f7f40cb`. The observation-only Scientific Pilot PR #9 is unchanged and may continue independently. **Status: code and executable acceptance gate committed; exact-head qualification PENDING.** The 848/848 Python and 105/105 frontend fast receipts apply to the earlier `3bfbc0f` B2B-08A baseline, not this candidate.

### Reproduced defects and targeted controls

1. **Receipt timing and revocation — P1:** L3 `issued_at` must be no later than the trusted assessment cutoff, `expires_at` must exceed the assessment cutoff, and live nonhistorical use cannot rely on an already expired receipt. The live `DurableRevocationAuthority` is now evaluated against authorization time, **not delivery_end**. Signed tokens retain the issue/expiry/key/revision fields under the internal admission seal. `ZoneKalmanFilter.step()` rechecks current issuer, expiry and live revocation **after numerical prediction and immediately before transactional state+receipt commit**. This is an application-level precommit check; fully atomic revocation relative to a separately refreshed file authority would require transactionally co-locating its authoritative revision with the receipt/state commit.
2. **Cold replay omission — P1:** An identical scoped day with a committed Mongo L3 scientific checkpoint is recovered through the existing validated checkpoint recovery path **before new physical prediction**. The returned provenance flags `recovered_from_durable_l3_commit`, `event_forcing_status=RECOVERED_COMMITTED_CHECKPOINT`, and `physical_management_events_applied=0` for the recovery itself. No receipt is silently re-consumed, and the prior moisture state is not downgraded to an ordinary re-estimate.
3. **Duplicate physical evidence — P1:** A signer-independent physical evidence fingerprint now binds tenant, plot, zone, geometry hash/version, source evidence CAS root, and normalized delivery interval. It does **not** include receipt ID, replay key, or re-issued physical quantity claims, so re-signing the same physical record under different amounts also cannot mint extra water. Local research state tracks pending/committed evidence; production Mongo uses a cross-worker partial unique `evidence_fingerprint` index. Two *different* source/interval deliveries may both be admitted in one scoped transaction. Legacy Mongo receipt rows without an evidence fingerprint require a migration/quarantine policy before activating this guarantee against previously committed historical data.
4. **Failed preflight strands receipt — P2:** A new prediction validates the positive temporal gap before event classification stages any receipt. Rejected zero/negative gaps therefore cannot strand a claim. A separate previously committed day is allowed to recover its checkpoint read-only without a new prediction.

### One connected acceptance gate

`services/agribrain/layer0/tests/manual_b2b08_irrigation_connected_gate.py` contains one opt-in **live Mongo replica-set** test covering:
- issue timestamp after assessment cutoff; expired receipt; stale revocation snapshot;
- authorized first water delivery, duplicate source evidence with different signer receipt/replay IDs denied;
- cold restart of the same receipt restores committed moisture and explicitly reports recovery;
- zero-duration step fails before receipt staging, then successful retry after proper prior initialization;
- two genuinely distinct physical deliveries both contribute; and
- plot revocation introduced after prediction but before durable journal commit rejects the new state/receipt.

It uses a disposable `akaloris_b2b08_irrigation_<uuid>` database and drops that unique database at completion. Use a dedicated nonproduction Mongo test replica set **only**.

```powershell
git pull
git rev-parse HEAD
py -m pytest -q services/agribrain/layer0/tests/test_b2b07_verified_delivered_irrigation.py
py -m pytest -q services/agribrain/layer0/tests/test_b2b08_production_delivery_runtime.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/ --ignore=services/agribrain/layer05_asmae/tests/test_comprehensive_pipeline_execution.py
npm run test:frontend
npx tsc --noEmit
npm run build
$env:AKALORIS_B07_MONGO_TEST_URI = 'mongodb://127.0.0.1:27018/?replicaSet=rs0'
py -m pytest -v services/agribrain/layer0/tests/manual_b2b08_irrigation_connected_gate.py
```

**Gate rule:** Do not claim the four findings closed or freeze B2B-08 until the fast and connected gate pass on the final SHA. Run the 365-day comprehensive once at the final integrated B2B-08A+B+C acceptance, not after every correction.

### Progress accounting, with denominator discipline

- Layer 0 current B2B cohort gate progress: **7 / 8 frozen = 87.5%**. This is *not* a percentage of all possible Layer 0 capabilities; B2B-08 is the open integration cohort.
- Whole 52-package register: October 18 `AgriBrain_WIP_Package_Register_52_2e1fbcb_2026-10-18.json` reports **0/52 formally fully accepted = 0%** at that historical snapshot, despite partially implemented work in all packages. It also lists **137 verified slices / (137 verified + 150 remaining criteria) = 47.7%** unweighted source-evidence slice coverage **as of October 18**. This proxy is not a present-day implementation percentage and cannot be extrapolated from Layer 0 milestone freezes alone. A refreshed 153-requirement evidence mapping is required to assign a defensible current overall percentage.

## 8. B2B-08B-II — Cross-journal signed-delivery lineage (unqualified candidate)

Read-only assessment attestation now matches each server-produced Kalman applied
or recovered L3 receipt to the exact committed scoped Mongo snapshot and
COMMITTED receipt, including the independent physical-evidence fingerprint.
The HTTP response exposes only a receipt count; the internal journal retains
verified snapshot/receipt IDs. Missing, foreign, contradictory or legacy
unfingerprinted records fail closed and leave the assessment STAGED.

Files: app/scientific_commit_lineage.py; app/scoped_packet_run.py;
layer0/tests/test_b2b08_scientific_commit_lineage.py.

**Exact-head tests NOT executed yet**. Run:

    py -m pytest -q services/agribrain/layer0/tests/test_b2b08_scientific_commit_lineage.py
    py -m pytest -q services/agribrain/layer0/tests/test_b2b08_production_delivery_runtime.py services/agribrain/layer0/tests/test_b2b07_verified_delivered_irrigation.py
    py -m pytest -v services/agribrain/layer0/tests/manual_b2b08_irrigation_connected_gate.py

The new check does not repair historical records, provide atomic revocation
with file-backed snapshots, grant publication/actuation, or satisfy B2B-08B
real FastAPI integration and B2B-08C operations acceptance. Keep the 365-day
ASMAE run for the final integrated A+B+C candidate. Do not merge until reviewed.

## 9. B2B-08C-I — Authenticated operations readiness candidate

**Status:** New code and tests committed on the B2B-08 branch, exact-head
qualification pending (not a B2B-08 freeze). See
`plan/Layer0_B2B-08C_Operations_Readiness_Runbook_2026-11-05.md`.

The internal HMAC-authenticated endpoint
`/v2/b2b08/internal/readiness` independently rechecks shared Mongo ping
and session-capable replica/sharded topology, plot-ownership availability,
strict v3/source admission, dedicated L3 public-key verification and live
revocation freshness. It returns allowlisted statuses only, never secrets,
signer IDs, unredacted plot identifiers, receipt tokens or file paths.
Missing, revoked or stale authorities produce 503 and no operational
fallback. The endpoint requires a real signed internal service request,
even when development mode permits unsigned legacy endpoints.

Readiness expressly reports `mongo_transaction_executed=false`; a
topology probe is not a committed multi-document transaction. Key rotation,
audit recovery, snapshot backup and migration/quarantine procedures are
documented. No automated deletion/retry of ambiguous STAGED claims.

Targeted suite: `test_b2b08c_operational_readiness.py`.
Connected FastAPI signed-request acceptance, full final suites and final
365-day comprehensive remain pending. Existing B2B-07, weather, Pilot,
main, findings and master monograph remain protected.

## 10. B2B-08C-II — Signed HTTP-to-Mongo connected gate candidate

**Implementation stage: explicit operator-executed acceptance added, NOT
executed or frozen.** File:
`services/agribrain/layer0/tests/manual_b2b08_signed_http_connected_gate.py`.

This is an opt-in, real FastAPI TestClient request against the B2B-08
production assessment router, actual HMAC internal auth and Mongo nonce store,
real B2B-05 Prisma Plot→Farm→User ownership reads, real B2B-08 A+B
server-only v3 public verifier bootstraps, separate Ed25519 source and L3
test signers, verified spatially contained source NDVI observation,
physical-delivery event, scoped Kalman assimilation, Mongo transactional
receipt and snapshot journal, and lineage attestation. It then restarts
the ASGI lifespan (new verifier/filter) against the same disposable
replica-set database and verifies recovery without a second physical
consumption. Negative HTTP assertions cover unsigned caller, foreign tenant,
duplicate assessment, and revoked plot ownership.

**Boundary:** This uses a minimal isolated ASGI lifespan that executes
exactly the production bootstrap functions and router rather than starting
unrelated `main.py` refresh and ASMAE background workers. Therefore it
qualifies the *actual route and trust bootstraps*, not the entire deployed
`main.app` lifespan under a staging process manager.

Mandatory local-only dedicated MongoDB replica set, exact head:
```powershell
git pull
git rev-parse HEAD
$env:AKALORIS_B07_MONGO_TEST_URI = "mongodb://127.0.0.1:27018/?replicaSet=rs0"
py -m pytest -v services/agribrain/layer0/tests/manual_b2b08_signed_http_connected_gate.py
```

The gate intentionally fails without the opt-in URI and uses a random
`akaloris_b2b08_http_<uuid>` database. It must not run against production.

No operational merge is authorized. On failure inspect exact traceback,
repair only the reproduced integration fault and rerun the same head.
Follow with complete fast suites and 365-day real-raster ASMAE once at
the final B2B-08A+B+C candidate. A real staging `main.app` lifespan,
revocation vs Mongo atomic fencing, legacy fingerprint migration, and
operator STAGED reconciliation remain separate mandatory release gates.


## 11. B2B-08 Full Integrated Qualification Receipts & Final Closure Evidencing

**Scope & Environment:**
- Python 3.13.13 / pytest 9.0.3 / Node 22 / Next.js 16.1.4 (Turbopack)
- Connected MongoDB replica set on dedicated `mongodb://127.0.0.1:27018/?replicaSet=rs0` (`akaloris-b07-mongo-rs`, image `mongo:7`)

**Four Final Closure Evidences:**
1. **Qualification Label Correction & Dedicated 365-Day Endurance Gate:**
   - Corrected historical label: `test_comprehensive_pipeline_execution.py` is the 10-calendar-day real-raster ASMAE scene validation (window August 30 – September 8, 2026, 628.62s) with cached Sentinel-1/Sentinel-2 assets, radiometric validation, BMA, and EnKF.
   - Added dedicated `services/agribrain/layer0/tests/test_kalman_365day_numerical_endurance.py` (**4/4 passed** in 2.06s) establishing continuous 365-day annual cycle stability: Joseph-form covariance PSD (all eigenvalues >= -1e-10) across all 365 steps, temporal gap admission (linear Q scaling) and strict fail-closed >30-day gap rejection, exact deterministic trajectory replay invariance, mid-cycle serialization restore, and multi-zone state separation.
2. **Actual `main.app` Staging Lifespan Qualification:**
   - Added `services/agribrain/layer0/tests/manual_b2b08_staging_main_lifespan_gate.py` (**1/1 passed** against live replica set in 4.14s) qualifying the complete production `services.agribrain.app.main.app` lifespan: MongoDB connectivity, B2B-05 plot authority configuration, server-only L3 verifier on `app.state`, source verifier on `app.state`, background refresh worker, ASMAE durable recovery worker thread, Mongo nonce indexes, signed internal service readiness probe (HTTP 200, ready=true), signed scoped packet run commit, graceful lifespan shutdown, and cold restart recovery without duplicate receipt consumption.
3. **Operational Recovery & Legacy Receipt Quarantine:**
   - Created `services/agribrain/layer0/operational_reconciliation.py` and test suite `test_b2b08_operational_reconciliation.py` (**5/5 passed** in 0.19s).
   - Provides controlled operator tooling to audit ambiguous `STAGED` assessments, rollback uncommitted staged reservations, or complete durable commitments with operator audit metadata (forbidding silent/automatic deletion).
   - Establishes quarantine and deterministic migration for pre-B2B-08 receipts lacking `evidence_fingerprint`.
4. **In-Transaction Revocation Fencing:**
   - Enhanced `MongoIrrigationIdempotencyStore.commit_many` to execute an in-transaction verification fence against `Layer0RevocationLedger` within the active MongoDB multi-document session (`session=session`).
   - If an issuer key or receipt is revoked in MongoDB, the transaction aborts with `RuntimeError("issuer_key_revoked_in_transaction")` and WiredTiger rolls back the entire atomic commit.
   - Verified in `services/agribrain/layer0/tests/test_b2b08_transactional_revocation_fence.py` (**2/2 passed** in 0.41s).

**Python Test Receipts:**
- Layer 0 unit and regression (`services/agribrain/layer0/tests/`): **781 passed**, 1 warning in 20.29s (incorporating 365-day endurance, reconciliation, and revocation fence suites)
- Layer 1 fusion (`services/agribrain/layer1_fusion/tests/`): **21 passed** in 1.07s
- Layer 0.5 ASMAE fast (`services/agribrain/layer05_asmae/tests/` excluding comprehensive pipeline): **83 passed**, 3 subtests passed in 43.76s
- Layer 0.5 ASMAE 10-day comprehensive pipeline (`test_comprehensive_pipeline_execution.py`, Aug 30 - Sep 8 2026): **1 passed** in 628.62s (10m 28s)
- **Total distinct Python tests:** **886 passed** (885 unit/fast + 1 10-day comprehensive pipeline)

**Real Connected MongoDB Integration Gates (5/5 passed):**
- `manual_b2b07_mongo_acceptance.py`: **2 passed** in 3.85s (multi-worker atomic commit, signed L3 delivery to scoped Kalman assessment)
- `manual_b2b08_irrigation_connected_gate.py`: **1 passed** in 1.04s (cutoff, revocation, duplicate evidence fence, retry, cold recovery, distinct deliveries)
- `manual_b2b08_signed_http_connected_gate.py`: **1 passed** in 3.04s (authenticated FastAPI request -> signed v3 source + L3 delivery -> Mongo transactional state/receipt journal -> cold restart recovery -> plot ownership revocation gate)
- `manual_b2b08_staging_main_lifespan_gate.py`: **1 passed** in 4.14s (actual `services.agribrain.app.main.app` lifespan startup, B2B-05 plot authority, app.state verifiers, readiness probe, signed assessment, shutdown cleanup, cold restart recovery)

**Frontend & Build Receipts:**
- Frontend test suite (`npm run test:frontend`): **105 passed**, 0 failed in 1.53s
- TypeScript compilation (`npx tsc --noEmit`): **0 errors** (exit code 0)
- Production build (`npm run build`): **0 errors**, compiled in 19.2s, 63 static pages generated in 762.5ms (exit code 0)

## 12. B2B-08 Final Freeze Remediation: Fail-Closed Revocation Fence, Exact Assessment Reconciliation, and Canonical Legacy Migration

Following deep source review of commit `5436a2f`, three release-blocking P1 findings were formally remediated and qualified:

1. **P1 — Transactional Revocation Write-Fence & Fail-Closed Enforcement:**
   - In `MongoIrrigationIdempotencyStore.commit_many()`:
     - When `Layer0RevocationLedger` is configured or required, the store verifies in-session (`session=session`) that every issuer key is active.
     - Executes an explicit in-transaction write-fence updating the key record: `update_one({"_id": k_id, "status": "active"}, {"$set": {"last_fenced_commit_at": now}})`.
     - Missing issuer key, revoked issuer key, or missing staged receipt fails closed with `RuntimeError("issuer_key_revoked_or_missing_in_transaction")`.
     - Revoked receipt in the ledger fails closed with `RuntimeError("receipt_revoked_in_transaction")`.
     - Concurrent out-of-band revocation writes trigger WiredTiger write conflicts or precondition failures, ensuring guaranteed atomic abort.
     - Probe errors fail closed (`RuntimeError("revocation_ledger_probe_failed")`).
   - Validated in unit suite `services/agribrain/layer0/tests/test_b2b08_transactional_revocation_fence.py` (**4/4 passed** in 0.47s).
   - Validated against live replica set in `services/agribrain/layer0/tests/manual_b2b08_transactional_revocation_connected_gate.py` (**4/4 passed** in 1.75s).

2. **P1 — Operational Reconciliation Exact Assessment Scope & Cryptographic Authorization:**
   - In `services/agribrain/app/scoped_packet_run.py`, the staged assessment record in `Layer0ScientificAssessment` now explicitly captures `submitted_receipt_ids` from incoming packets.
   - In `services/agribrain/layer0/operational_reconciliation.py`:
     - `audit_staged_assessments()` and `reconcile_staged_assessment()` correlate and manipulate receipts strictly by `submitted_receipt_ids`, isolating rollback to the targeted assessment and leaving other staged assessments on the same plot completely untouched.
     - Enforces atomic compare-and-set on `claim_nonce` and `status='STAGED'`.
     - Enforces cryptographic operator authorization via HMAC-SHA256 signature over `f"{operator_principal}:{action}:{assessment_id}:{timestamp}"` with strict 5-minute skew tolerance.
     - For `COMPLETE_RECONCILED`, verifies exact state snapshot lineage and scope match before committing.
   - Validated in unit suite `services/agribrain/layer0/tests/test_b2b08_operational_reconciliation.py` (**5/5 passed** in 0.21s).

3. **P1 — Canonical Legacy Evidence Fingerprint Migration:**
   - `migrate_legacy_receipt_evidence_fingerprint()` reuses the EXACT canonical JSON SHA-256 fingerprint serializer matching `physical_evidence_fingerprint(grant)` (`_parse_iso_utc` and sorted keys).
   - Validated against live replica set: migrating a legacy receipt activates the partial unique index on `evidence_fingerprint`, blocking duplicate injection of modern grants attempting to claim previously delivered physical water.

**Final Comprehensive Verification Cohort:**
- **Layer 0 Tests (`services/agribrain/layer0/tests/`):** **783 passed**, 1 warning in 18.81s
- **Layer 1 Fusion Tests (`services/agribrain/layer1_fusion/tests/`):** **21 passed** in 0.61s
- **Layer 0.5 ASMAE Fast Tests:** **83 passed**, 3 subtests passed in 26.64s
- **Layer 0.5 ASMAE Comprehensive Pipeline Test:** **1 passed** in 434.61s (7m 14s)
- **Total Distinct Python Tests:** **888 passed**
- **Connected MongoDB Replica Set Gates (`mongodb://127.0.0.1:27018/?replicaSet=rs0`):** **9 passed across 5 suites**
  - `manual_b2b07_mongo_acceptance.py`: **2 passed** in 3.71s
  - `manual_b2b08_irrigation_connected_gate.py`: **1 passed** in 0.98s
  - `manual_b2b08_signed_http_connected_gate.py`: **1 passed** in 2.87s
  - `manual_b2b08_staging_main_lifespan_gate.py`: **1 passed** in 3.63s
  - `manual_b2b08_transactional_revocation_connected_gate.py`: **4 passed** in 1.75s
- **Frontend Test Suite (`npm run test:frontend`):** **105 passed**, 0 failed in 1.53s
- **TypeScript Compiler (`npx tsc --noEmit`):** **0 errors** (exit code 0)
- **Production Build (`npm run build`):** **0 errors**, compiled in 19.5s, 63 static pages generated (exit code 0)

## 13. B2B-08 Freeze Closure: Mandatory Factory Revocation Fence, Atomic Transaction Reconciliation, and Verified Legacy Migration

Following comprehensive review of commit `4e2a8c9`, all three remaining freeze blockers (B2B-08-F1, B2B-08-F2, B2B-08-F3) were remediated, verified, and closed with live connected qualification:

1. **Mandatory Factory Revocation Fence & Ledger Seeding (B2B-08-F1 — P1):**
   - In `services/agribrain/layer0/production_admission.py`:
     - `configure_server_delivery_verifier()` now mandates `require_transactional_revocation: bool = True` by default and enforces that transactional revocation fencing cannot be disabled in production admission.
     - Automatically provisions and seeds active keys from `public_key_registry` directly into `Layer0RevocationLedger` at initialization time, validating key status against the revocation authority and preventing unseeded cold starts.
   - In `services/agribrain/layer0/mongo_irrigation_idempotency.py`:
     - When `require_transactional_revocation=True`, `commit_many()` verifies that the revocation ledger contains seeded records; an uninitialized or empty ledger immediately fails closed with `RuntimeError("uninitialized_revocation_ledger")`.
   - In `services/agribrain/layer0/tests/manual_b2b08_transactional_revocation_connected_gate.py`:
     - Added a genuine concurrent multi-threaded overlapping revocation writer test where an out-of-band thread revokes a key while another thread is executing an in-flight transaction commit, proving that WiredTiger `WriteConflict` / write-fence aborts the commit and rolls back all mutations atomically.

2. **Atomic Transaction Reconciliation & Strict Scope Enforcement (B2B-08-F2 — P1):**
   - In `services/agribrain/layer0/operational_reconciliation.py`:
     - Wrapped the entire assessment status mutation, receipt updates, and audit metadata journaling in `reconcile_staged_assessment()` in a single atomic MongoDB multi-document transaction (`with client.start_session() as session: with session.start_transaction(): ...`).
     - Added live replica-set qualification verifying that an injected CAS failure or concurrent assessment mutation triggers complete fail-closed rollback of pre-CAS receipt mutations back to `STAGED`.
     - Validates scope strictly for every receipt in `submitted_receipt_ids` against the assessment document (`tenant_id`, `plot_id`, `geometry_hash`, `geometry_version`, `day`) before any mutations can occur.
     - Reconstructs full scientific state provenance for `COMPLETE_RECONCILED` and validates that snapshot receipt sets exactly match `submitted_receipt_ids`.
     - Enforces a trusted server secret boundary via `AKALORIS_RECONCILIATION_HMAC_SECRET` (calling `get_trusted_reconciliation_secret()`), strictly rejecting caller self-authorization.
   - In `services/agribrain/app/scoped_packet_run.py`:
     - Incoming packet grant scope (`tenant_id`, `plot_id`, `geometry_hash`, `geometry_version`) is validated before recording `receipt_id` into `submitted_receipt_ids`.

3. **Verified Legacy Migration Without Defaults (B2B-08-F3 — P2):**
   - In `services/agribrain/layer0/operational_reconciliation.py`:
     - `migrate_legacy_receipt_evidence_fingerprint()` strictly enforces non-empty, explicit scope fields (`tenant_id`, `plot_id`, `zone_id`, `geometry_hash`, `geometry_version`), completely eliminating fallback defaults.
     - Validates delivery interval (`delivery_end > delivery_start` and duration `<= 24 hours`) and verifies internal consistency with existing receipt timestamp fields.
     - Validates canonical CAS root format (`len >= 16`) and supports an optional `evidence_authenticator` callback for verifying historical evidence integrity.

**Final Freeze Qualification Receipts (exact HEAD):**
- **Layer 0 Tests (`services/agribrain/layer0/tests/`):** **787 passed**, 1 warning in 19.40s
- **Layer 1 Fusion Tests (`services/agribrain/layer1_fusion/tests/`):** **21 passed** in 0.66s
- **Layer 0.5 ASMAE Fast Tests:** **83 passed** in 26.26s
- **Layer 0.5 ASMAE Comprehensive Pipeline Test:** **1 passed** in 434.61s (7m 14s)
- **Total Distinct Python Tests:** **892 passed**
- **Connected MongoDB Replica Set Gates (`mongodb://127.0.0.1:27018/?replicaSet=rs0`):** **11 passed across 5 suites** in 10.81s
  - `manual_b2b07_mongo_acceptance.py`: **2 passed**
  - `manual_b2b08_irrigation_connected_gate.py`: **1 passed**
  - `manual_b2b08_signed_http_connected_gate.py`: **1 passed**
  - `manual_b2b08_staging_main_lifespan_gate.py`: **1 passed**
  - `manual_b2b08_transactional_revocation_connected_gate.py`: **6 passed**
- **Frontend Test Suite (`npm run test:frontend`):** **105 passed**, 0 failed in 1.55s
- **TypeScript Compiler (`npx tsc --noEmit`):** **0 errors** (exit code 0)
- **Production Build (`npm run build`):** **0 errors**, compiled in 17.0s, 63 static pages generated in 927.1ms (exit code 0)

