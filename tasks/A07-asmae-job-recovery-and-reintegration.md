# Task A07: ASMAE Job Recovery Misses Reintegration & NameError Crash

## 1. Finding Overview
* **Finding ID:** A07
* **Severity:** **P1 — Background Task Orchestration & Data Loss Risk**
* **Component:** ASMAE / Layer 0.5 (Background Jobs Engine)
* **Primary Target File:** [`services/agribrain/layer05_asmae/background_jobs.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/background_jobs.py) (lines 1264–1271, 2265)

---

## 2. Technical Analysis & Code Audit

### Defect 1: `COMPLETED_REINTEGRATION_PENDING` Omitted from Recovery
In `services/agribrain/layer05_asmae/background_jobs.py`, line 2265:
```python
candidate_states = [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.STALLED]
pending_jobs = store.get_jobs_by_states(candidate_states)
```
- The ASMAE job engine employs a two-phase completion model:
  1. `RUNNING` $\to$ `COMPLETED_REINTEGRATION_PENDING` (heavy matrix computations done, waiting for worldline transaction write).
  2. `COMPLETED_REINTEGRATION_PENDING` $\to$ `SUCCESS` (posterior state persisted and immutable receipt emitted).
- *The Flaw:* If a server restarts or a worker times out while in `COMPLETED_REINTEGRATION_PENDING`, `recover_pending_jobs` ignores it. The completed computation is never recovered or published into the active pipeline.

---

### Defect 2: NameError in Job Requeue Helper
In `services/agribrain/layer05_asmae/background_jobs.py`, lines 1264–1271:
```python
def _supersede_and_requeue_job(store, job_id: str) -> tuple[bool, Any]:
    ...
    superseded = store.mark_superseded(job_id)
    ...
    return True, resumed  # <-- NameError: name 'resumed' is not defined!
```
The variable name `resumed` does not exist in scope (it was copied from a resume helper and should be `superseded`). If this recovery path is hit, the worker crashes with an unhandled `NameError`.

---

### Defect 3: Active Lease Blindness in Attempt Ceiling
Recovery processes evaluate attempt counts and time limits without first validating whether an active worker lease has expired (`lease_expires_at < utc_now`). This risks having a recovery job preempt or re-execute a job that is currently being computed by a live worker.

---

## 3. Agronomical & Systemic Impact
- **Stranded Computations:** Intensive satellite / SAR time-series matrix inversions that took minutes to run finish their computation but get orphaned, forcing redundant recalculations or leaving plots without fresh posterior estimates.
- **Worker Crashes:** Automatic self-healing routines designed to recover stalled jobs crash on `NameError: 'resumed'`.

---

## 4. Implementation Plan

### Step 1: Fix `NameError` in `_supersede_and_requeue_job`
In `services/agribrain/layer05_asmae/background_jobs.py`, line 1271:
```python
# Fix variable name to match instantiated object
return True, superseded
```

### Step 2: Include Reintegration Phase in Recovery
In line 2265, expand candidate recovery states:
```python
candidate_states = [
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.STALLED,
    JobStatus.COMPLETED_REINTEGRATION_PENDING,
]
```
Add explicit handling for `COMPLETED_REINTEGRATION_PENDING`:
- Do not re-run the numerical pipeline.
- Instead, invoke the reintegration writer directly to commit the cached state artifacts into the worldline store.

### Step 3: Enforce Lease Expiry Check Before Re-Execution
Before taking over a `RUNNING` or `COMPLETED_REINTEGRATION_PENDING` candidate:
```python
now = datetime.now(timezone.utc)
if job.lease_expires_at and job.lease_expires_at > now:
    logger.info(f"Skipping active job {job.job_id}: lease valid until {job.lease_expires_at}")
    continue
```

---

## 5. Verification & Test Plan

### Automated Tests
1. **Helper Execution Test:** Call `_supersede_and_requeue_job` directly and verify it returns `(True, superseded)` without raising `NameError`.
2. **Reintegration Recovery Test:**
   - Seed a job with status `COMPLETED_REINTEGRATION_PENDING` and expired lease.
   - Run `recover_pending_jobs()`.
   - Assert job transitions to `SUCCESS` and posterior receipt is written.
3. **Active Lease Protection Test:**
   - Seed a job with status `RUNNING` and lease valid for 10 minutes.
   - Run `recover_pending_jobs()`.
   - Assert job remains untouched.

---

## 6. Progress Tracking Checklist
- [x] Line 1271 NameError fixed (`resumed` $\to$ `superseded`).
- [x] `COMPLETED_REINTEGRATION_PENDING` added to candidate recovery query.
- [x] Dedicated reintegration recovery dispatcher implemented.
- [x] Worker lease expiration guard enforced.
- [x] Automated recovery tests written and passing.

---

## 7. Resolution Summary
Resolved in Work Package 11 (WP11):
1. Line 1271 NameError resolved by returning `superseded or current` with `_supersede_and_requeue_job = _supersede_recovery_candidate` alias.
2. `completed_reintegration_pending` added to recovery query in `recover_pending_jobs` and `_mark_stalled_if_expired`, safely resuming at `resume_phase='reintegration'`.
3. Active unexpired leases are validated prior to any preemption or supersede action.
4. Validated by automated tests in `services/agribrain/tests/test_wp11_operational_isolation.py`.
