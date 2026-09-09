# Work Package 11: Complete Operational Isolation and Bounded Execution

## 1. Executive Summary & Objective
Production readiness requires that backend services, background workers, and persistent databases operate with strict tenant isolation, authenticated access controls, bounded compute resources, and resilient bootstrapping:
1. **Unprotected API Endpoints (Finding #32)**: `services/agribrain/app/main.py` contains numerous plot-scoped routes, observation retrieval endpoints, and feedback submission handlers that lack FastAPI dependency authentication (`require_internal_service_request`). Direct HTTP calls to the backend can bypass frontend ownership checks.
2. **Unbounded Background Process Spawning (Finding #34)**: ASMAE's `background_jobs.py` launches a detached operating system process for every background assimilation run without a global worker concurrency cap or memory budget. If multiple API instances start up simultaneously, each executes an independent filesystem recovery scan, causing process storms and lock contention.
3. **Database Bootstrap Deadlock (Finding #35)**: In `infra/docker-compose.yml`, MongoDB health depends on `rs.status()`. On an uninitialized volume, `rs.status()` fails. However, the `mongo-init` container waits for MongoDB to be healthy before calling `rs.initiate()`, creating a circular dependency deadlock that prevents cold starts. Furthermore, `localhost:27017` is advertised as the replica member, breaking inter-container networking.

Work Package 11 enforces universal route authentication, implements a bounded worker pool for background jobs, and repairs the deployment infrastructure.

---

## 2. Affected Subsystems & Source References
- **FastAPI Main Application**: [`services/agribrain/app/main.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/app/main.py).
- **Internal Service Authentication**: [`services/agribrain/app/internal_service_auth.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/app/internal_service_auth.py).
- **ASMAE Background Jobs**: [`services/agribrain/layer05_asmae/background_jobs.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer05_asmae/background_jobs.py).
- **Docker Compose Infrastructure**: [`infra/docker-compose.yml`](file:///c:/Users/E-C/Desktop/agriwise/infra/docker-compose.yml#L12-L28).

---

## 3. Root Cause & Architectural Breakdown

### 3.1 Unauthenticated Plot-Scoped Routes (Finding #32)
In `services/agribrain/app/main.py`, `require_internal_service_request` is imported at line 34, but no FastAPI routes use it via `Depends(require_internal_service_request)`. Endpoints accepting `plot_id` directly query Mongo or execute pipelines without verifying that the caller possesses a valid HMAC signature matching the tenant and plot.

### 3.2 Unbounded Worker Processes (Finding #34)
In `background_jobs.py`, `launch_worker_process()` invokes `subprocess.Popen([sys.executable, "-m", ...])` directly. There is no semaphore or pool manager limiting how many processes run concurrently. A burst of 50 incoming plot assimilation requests will spawn 50 concurrent Python processes, exhausting system RAM and triggering OOM kills. In multi-replica API deployments, every instance scans the jobs directory every 30 seconds, racing to recover the same jobs.

### 3.3 The MongoDB Bootstrap Deadlock (Finding #35)
In `infra/docker-compose.yml`:
```yaml
  mongo:
    image: mongo:7
    command: ["--replSet", "rs0", "--bind_ip_all"]
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "rs.status()"]
      interval: 10s
      timeout: 5s
      retries: 5

  mongo-init:
    image: mongo:7
    depends_on:
      mongo:
        condition: service_healthy
    entrypoint: >
      mongosh --host mongo:27017 --eval '
        try { rs.initiate({ _id: "rs0", members: [{ _id: 0, host: "localhost:27017" }] }) }
        catch(e) { if (e.codeName !== "AlreadyInitialized") throw e; }
      '
```
On a clean volume, `rs0` is not yet initiated. `rs.status()` exits with code 94 (`NotYetInitialized`). `mongo` remains permanently unhealthy. `mongo-init` never runs. The database never starts. If manually forced, `host: "localhost:27017"` tells client containers inside Docker to connect to their own localhost rather than the `mongo` container!

---

## 4. Implementation Specification

### 4.1 Step 1: Universal Route Authentication & Ownership Resolution
1. Apply `require_internal_service_request` as a router-level or global dependency in `app/main.py`:
   ```python
   app.include_router(plot_router, dependencies=[Depends(require_internal_service_request)])
   ```
2. Verify tenant and plot ownership context on every request:
   - Match the HMAC header `X-Signature` against `(method, path, tenant_id, plot_id, timestamp, nonce)`.
   - Forbid cross-tenant data access.

### 4.2 Step 2: Implement Bounded Worker Pool for Background Jobs
1. In `services/agribrain/layer05_asmae/background_jobs.py`, introduce `BoundedJobExecutor`:
   - Enforce `MAX_CONCURRENT_WORKERS = int(os.getenv("AGRIBRAIN_MAX_WORKERS", "4"))`.
   - Maintain a FIFO queue for pending jobs; workers dequeue jobs only when capacity permits.
   - Enforce memory quotas ($2\text{GB}$ per worker) and execution deadlines ($300\text{s}$ timeout).
2. For multi-replica recovery:
   - Use distributed advisory leases in MongoDB (`job_recovery_leader_lock`) so only one API replica performs recovery scans at a time.

### 4.3 Step 3: Repair Docker Compose Bootstrapping
Update `infra/docker-compose.yml`:
1. Change MongoDB healthcheck to test server ping rather than replica status:
   ```yaml
   healthcheck:
     test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
     interval: 5s
     timeout: 5s
     retries: 5
   ```
2. In `mongo-init`, advertise the service name `mongo:27017` on the Docker network:
   ```yaml
   entrypoint: >
     mongosh --host mongo:27017 --eval '
       try { rs.initiate({ _id: "rs0", members: [{ _id: 0, host: "mongo:27017" }] }) }
       catch(e) { if (e.codeName !== "AlreadyInitialized") throw e; }
     '
   ```

---

## 5. Verification & Completion Criteria
- **Clean Bootstrap Test**: Running `docker compose down -v && docker compose up -d` against an empty volume brings up MongoDB, initializes replica set `rs0`, and reaches healthy status within 20 seconds.
- **Route Authentication Test**: Directly querying `/v2/plots/{plot_id}/intelligence` without valid HMAC headers returns `401 Unauthorized` or `403 Forbidden`.
- **Worker Concurrency Cap**: Triggering 20 background ASMAE jobs results in exactly `MAX_CONCURRENT_WORKERS` running concurrently, with the remainder queued cleanly without OOM errors.

---

## 6. Monograph & Defect Task Traceability
- **Monograph Findings**: Finding #32 (Inconsistent route authentication), Finding #34 (Background job capacity control), Finding #35 (Docker compose MongoDB bootstrap cycle).
- **Defect Tasks**: [A07-asmae-job-recovery-and-reintegration.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/A07-asmae-job-recovery-and-reintegration.md).
- **Phase Tasks**: [P01.3-make-asmae-job-recovery-resilient.md](file:///c:/Users/E-C/Desktop/agriwise/tasks/P01.3-make-asmae-job-recovery-resilient.md).
