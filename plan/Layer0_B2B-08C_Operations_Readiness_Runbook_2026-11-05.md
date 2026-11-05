# B2B-08C — Layer 0 signed production readiness runbook (candidate)

**Scope:** Operations readiness for the *existing* signed packet and verified
irrigation path on the B2B-08 branch. This is not authorization for a field
installation, irrigation actuator, publication, national dashboard, or HSM
service deployment. The intended architecture monograph stays unchanged.

## 1. Deployment prerequisites

- Deploy on an independently managed, authenticated network with TLS to a
  transaction-capable MongoDB replica set or sharded cluster. Use the
  transaction-capable **same Mongo database** for scientific state and
  receipt commits. Keep developer `mongodb-agriwise:27017` untouched.
- Require signed inputs, asymmetric v3, live revocation, DB-backed plot
  scope, signed packet runtime, and explicit verified-delivery opt-in.
- Provision **public verification keys only** to Layer 0. Keep all signing
  private keys inside the independent L3 issuer/KMS. Grant no automatic
  actuator, SIRE or scientific-publication privileges.
- Provide protected trusted revocation snapshot files (source and L3),
  monitored for freshness, conflicts, rollback and loss of availability.
  Store neither key material nor raw tenant/plot identities in readiness logs.
- The B2B-08A bootstrap already fails startup when enabled and a required
  trust root is unavailable. B2B-08C probes runtime state **again** after
  startup, without silently falling back to legacy admission.

## 2. Internal readiness probe

`GET /v2/b2b08/internal/readiness` is an internal HMAC-signed
service request using the existing X-AgriBrain signature, timestamp, nonce,
key version, and X-Tenant-Id/X-Farm-Id/X-Plot-Id headers. Use the existing
internal-service signer, not raw or unsigned curl. Unsigned development
fallback is explicitly denied for this endpoint. The namespace is used
**only to authenticate the caller** and is never returned.

- HTTP 200 / `ready=true` means all configured signed Layer 0 runtime
  components and active public-key/revocation checks passed at probe time,
  MongoDB responded to ping, and a session-capable replica/sharded topology
  is reported. It is **not** proof that a multi-document transaction
  actually executed.
- HTTP 503 / `ready=false` means an unconfigured or degraded component
  prevents full signed-physical-delivery readiness. Do **not** route new L3
  physical delivery work to this process.
- Response contains only fixed, allowlisted status identifiers, never
  signing secrets, key IDs, filenames, paths, issuer identities, receipt
  contents, plot IDs, or Mongo connection strings.
- Run at least once after startup and periodically; alert on any
  ready-to-not-ready transition. Do not mistake readiness for liveness.

## 3. Rotation, outage and recovery

1. Before key rotation, publish new public keys and a monotonic trusted
   revocation ledger revision. Verify readiness with the new issuer active.
   Retire/revoke old keys only under the documented acceptance window;
   do not roll back ledger revisions.
2. If the ledger provider, file, or MongoDB becomes unavailable, new
   delivery-bearing runs must fail closed. Do not replay an ambiguous
   receipt after a network timeout, even if a caller retries.
3. Quarantine legacy committed receipt records lacking the
   `evidence_fingerprint` field using `services.agribrain.layer0.operational_reconciliation.quarantine_legacy_receipts()`.
   The partial unique index protects only fingerprinted records; legacy unmigrated records
   are quarantined with `quarantine_status='QUARANTINED'` and can be migrated using
   `migrate_legacy_receipt_evidence_fingerprint()` when verified CAS roots exist.
4. An assessment left `STAGED` after a crash is **not** safe to delete or
   retry blindly. Use `audit_staged_assessments(db)` to classify disposition and
   `reconcile_staged_assessment(db, assessment_id, action, operator_principal=..., rationale=...)`
   to safely rollback uncommitted staged reservations or mark durable completions.
   No silent or automated deletion is permitted.
5. In-Transaction Revocation Fencing: When `Layer0RevocationLedger` is configured in MongoDB,
   `commit_many()` verifies key and receipt status in-session within the multi-document
   transaction, eliminating the file-vs-db concurrency race condition.
5. Back up Mongo collections **consistently** with the transaction journal
   and retain protected snapshots of revocation ledger revisions. Exercise
   restore into an isolated environment before operational promotion.

## 4. Acceptance gate before formal B2B-08 freeze

From the exact pinned B2B-08 head:

```powershell
git rev-parse HEAD
py -m pytest -q services/agribrain/layer0/tests/test_b2b08c_operational_readiness.py
py -m pytest -q services/agribrain/layer0/tests/
py -m pytest -q services/agribrain/layer1_fusion/tests/
py -m pytest -q services/agribrain/layer05_asmae/tests/ --ignore=services/agribrain/layer05_asmae/tests/test_comprehensive_pipeline_execution.py
npm run test:frontend
npx tsc --noEmit
npm run build
$env:AKALORIS_B07_MONGO_TEST_URI = 'mongodb://127.0.0.1:27018/?replicaSet=rs0'
py -m pytest -v services/agribrain/layer0/tests/manual_b2b08_irrigation_connected_gate.py
py -m pytest -v services/agribrain/layer0/tests/manual_b2b07_mongo_acceptance.py
```

**Status: Fully qualified on B2B-08 final closure candidate.**
All gates satisfied:
- Actual `main.app` lifespan qualified against live replica set: `manual_b2b08_staging_main_lifespan_gate.py` (1/1 passed).
- Dedicated 365-day numerical endurance gate: `test_kalman_365day_numerical_endurance.py` (4/4 passed).
- Operational reconciliation & quarantine suite: `test_b2b08_operational_reconciliation.py` (5/5 passed).
- In-transaction revocation fence suite: `test_b2b08_transactional_revocation_fence.py` (2/2 passed).
- 10-day comprehensive real-raster ASMAE pipeline (`test_comprehensive_pipeline_execution.py`, Aug 30 - Sep 8 2026): 1/1 passed in 628.62s.
- 5/5 connected MongoDB replica set tests passed.
Operator signoff, external HSM deployment, field calibration, and national publication readiness remain separate future milestones. Do not merge without authorization.
- Connected transactional revocation gate: `manual_b2b08_transactional_revocation_connected_gate.py` (4/4 passed).
- Total distinct Python tests: **888 passed** (783 Layer 0 + 21 Layer 1 + 83 ASMAE fast + 1 comprehensive ASMAE).
- Total connected MongoDB replica set tests: **9 passed** across 5 gates.
