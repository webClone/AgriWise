# B2B-08 Post-Freeze Integration — Observation-Only Pilot Safety

**Status:** Implementation candidate; exact-head qualification PENDING.
**Base:** frozen B2B-08 documentation commit `a26bf80e54394a755aa599dc952c3402c707da8a`; frozen runtime `4197e09a1bf6c3af6b18d3db009baabf64d5669c`.
**Branch:** `fix/layer0-b2b08-postfreeze-input-boundary-20261105`.
**Protected:** `main@6edd372`, Pilot PR #9, weather PR #25, B2B-01..08 freeze receipts, `findings/layer0.md`, intended master monograph.

## Safety / deployment boundary

The Scientific Pilot stays **observation-only**. Do not enable
`AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION` for the pilot.
No switch, release, merge, actuator authorization, publication authority,
or field command is introduced here. The signed-L3 runtime remains opt-in
for isolated integration qualification only. Existing weather, satellite,
numerical endurance and frontend acceptance evidence is preserved.

## Bounded corrections

1. **Checkpoint input identity / I03:** A durable physical delivery snapshot
   now stores a versioned SHA-256 digest of the zone/day weather, ordered
   Kalman observations, management evidence (including signed L3 grants),
   and the pre-step scientific state/covariance. A cold state is recovered
   only when this exact digest matches. Changed rainfall, an added receipt,
   or changed observations cause
   `CheckpointInputConflict("committed_irrigation_checkpoint_input_conflict")`,
   surfaced as HTTP 409. No new L3 reservation is staged on a mismatch.
   Old snapshots without the digest are **not** silently reused and need
   an explicit operator recovery/migration decision.
2. **Receipt attestation timing / I01:** The actual signed L3 verifier and
   precommit revalidator reject `issued_at < delivery_end`. A signed
   attestation is not proof of a completed physical delivery if issued
   before completion.
3. **HTTP journal / L3 filter identity:** The filter and HTTP assessment
   share `extract_irrigation_receipt`. Evidence is discovered by the
   irrigation receipt contract rather than the caller's `event_role`
   string. The journal's canonical grant digest equals the Mongo staged
   receipt's canonical grant digest, including defaults. `REPORTED`
   labels cannot hide a committed L3 receipt from crash recovery.
4. **Receipt-level transactional revocation:** Strict Mongo staging
   transactionally establishes `Layer0RevocationLedger["receipt:<id>"]`
   alongside `Layer0IrrigationReceiptConsumption` without overwriting
   a previously revoked status. The committer transaction **writes**
   this exact active receipt authority document after fencing the issuer
   key. The revoker must update **the same** `receipt:<id>` document,
   so overlapping revocation writes produce WiredTiger conflicts instead
   of accepting snapshot-isolated stale reads. Missing or revoked rows
   fail closed. No unauthenticated public revocation API is added.
   The revoker's authorized operational endpoint and ledger provenance
   remain deployment prerequisites.

The original findings I02 and I04 remain controlled by existing preflight,
CAS identity, and legacy quarantine/migration gates. This batch does not
reopen them or rewrite the 469-finding historical audit.

## One isolated connected gate

`services/agribrain/layer0/tests/manual_b2b08_postfreeze_observation_only_connected_gate.py`

This single opt-in gate runs against a **dedicated local** MongoDB replica
set at `127.0.0.1:27018/?replicaSet=rs0`, using a random disposable
`akaloris_b08_postfreeze_<uuid>` database. It covers:

- Positive: two independently metered signed deliveries on a fresh day.
- Positive: an exact cold retry returns the committed water state without
  staging or applying a second receipt.
- Negative: changed rainfall, second delivery, and both changed inputs on
  an already committed day conflict before physical staging.
- Negative: genuine signature with `issued_at < delivery_end`.
- Negative: overlapping per-receipt revocation writer during commit,
  demonstrating atomic rollback and no published state.
- HTTP crash boundary: a valid signed L3 receipt with `REPORTED` role
  commits physically, interrupted journal remains STAGED with complete
  receipt manifest, and authorized exact-scope operator reconciliation
  reconstructs the committed assessment.
- HTTP new evidence: a subsequent valid signed delivery returns an
  explicit 409 conflict instead of silently reusing the old posterior.

```powershell
git checkout fix/layer0-b2b08-postfreeze-input-boundary-20261105
git pull
git rev-parse HEAD
py -m pytest -q services/agribrain/layer0/tests/test_b2b08_postfreeze_input_identity.py
py -m pytest -q services/agribrain/layer0/tests/test_b2b08_transactional_revocation_fence.py
$env:AKALORIS_B07_MONGO_TEST_URI = 'mongodb://127.0.0.1:27018/?replicaSet=rs0'
py -m pytest -v services/agribrain/layer0/tests/manual_b2b08_postfreeze_observation_only_connected_gate.py
```

**No local Mongo or Python execution receipt has been obtained in this
implementation environment.** Do not claim pass or freeze until the
operator executes the exact-head gate. On failure, inspect the traceback,
fix only the reproduced issue, then rerun this bounded battery.

After the focused gate, run the affected existing B2B-07/08 signed
HTTP/cold-restart and transactional revocation connected suites and
Layer 0 fast tests. Do **not** rerun unrelated real-raster weather,
Sentinel, 365-day numerical or frontend tests unless changed dependencies
justify doing so. Treat this as a separate post-freeze integration candidate,
not an amendment to the formally frozen B2B-08 implementation.
