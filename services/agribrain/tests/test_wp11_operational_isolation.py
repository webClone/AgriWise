"""Automated Test Suite for Work Package 11 (WP11):
Operational Isolation, Bounded Execution, and Bootstrapping Integrity.

Verifies:
1. Universal route authentication on plot-scoped endpoints (Finding #32).
2. Tenant and plot ownership cross-parameter mismatch rejection (403 Forbidden).
3. Production environment enforcement on administrative routes (Finding #32).
4. Bounded background worker executor, FIFO queuing, and process alive detection (Finding #34).
5. Defect A07 & P01.3: _supersede_recovery_candidate NameError resolution, completed_reintegration_pending recovery, and lease protection.
6. Distributed single-leader recovery advisory lock (Finding #34).
7. Docker Compose MongoDB bootstrap deadlock repair & host configuration (Finding #35).
"""

import os
import sys
import time
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from services.agribrain.app.main import app, require_internal_service_request
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae.background_jobs import (
    BoundedJobExecutor,
    is_pid_alive,
    _supersede_recovery_candidate,
    _supersede_and_requeue_job,
    _mark_stalled_if_expired,
    recover_pending_jobs,
    acquire_recovery_leader_lock,
    _atomic_json,
    _read_json,
)


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# 1. Universal Route Authentication Tests (Finding #32)
# ============================================================================

def test_unauthenticated_plot_endpoints_rejected_in_prod(client, monkeypatch):
    """Direct unauthenticated calls to plot endpoints must return 401 when dev auth is disabled."""
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED_DEV", "false")
    monkeypatch.setenv("ENVIRONMENT", "production")

    endpoints = [
        ("POST", "/v2/plot-dna", {"plot_id": "test_plot", "lat": 36.0, "lng": 3.0}),
        ("GET", "/v2/satellite-tile-image/test_plot", None),
        ("GET", "/v2/satellite-tile-meta/test_plot", None),
        ("POST", "/v2/plot-intelligence", {"plot_id": "test_plot", "lat": 36.0, "lng": 3.0}),
        ("POST", "/v2/crop-feedback", {"plot_id": "test_plot", "confirmed_crop": "wheat"}),
        ("POST", "/collector/register-plot", {"plot_id": "test_plot", "farm_id": "test_farm", "coordinates": {"lat": 36.0, "lng": 3.0}, "crop": "wheat"}),
        ("POST", "/collector/snapshot/test_farm/test_plot", None),
        ("GET", "/data/test_farm/test_plot/observations", None),
        ("GET", "/v2/gateway/freshness/test_plot", None),
        ("POST", "/v2/gateway/invalidate/test_plot", None),
        ("GET", "/v2/gateway/maturity/test_plot", None),
        ("GET", "/v2/gateway/evolution/test_plot", None),
    ]

    for method, path, payload in endpoints:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json=payload or {})
        assert resp.status_code in (400, 401), f"Expected 401/400 for {method} {path}, got {resp.status_code}: {resp.text}"


def test_cross_tenant_plot_mismatch_rejected(client):
    """Authenticated requests with mismatched plot_id in body must return 403 Forbidden."""
    authed_ns = PlotNamespace(tenant_id="tenant_alpha", farm_id="farm_alpha", plot_id="plot_alpha")
    app.dependency_overrides[require_internal_service_request] = lambda: authed_ns

    try:
        # Mismatched plot_id in /v2/plot-dna
        resp1 = client.post("/v2/plot-dna", json={"plot_id": "plot_beta", "lat": 36.0, "lng": 3.0})
        assert resp1.status_code == 403
        assert "does not match" in resp1.json()["detail"]

        # Mismatched plot_id in /v2/plot-intelligence
        resp2 = client.post("/v2/plot-intelligence", json={"plot_id": "plot_beta", "lat": 36.0, "lng": 3.0})
        assert resp2.status_code == 403
        assert "does not match" in resp2.json()["detail"]

        # Mismatched plot_id in /v2/crop-feedback
        resp3 = client.post("/v2/crop-feedback", json={"plot_id": "plot_beta", "confirmed_crop": "corn"})
        assert resp3.status_code == 403
        assert "does not match" in resp3.json()["detail"]

        # Mismatched farm_id in /collector/register-plot
        resp4 = client.post("/collector/register-plot", json={
            "plot_id": "plot_alpha",
            "farm_id": "farm_spoofed",
            "coordinates": {"lat": 36.0, "lng": 3.0},
            "crop": "corn"
        })
        assert resp4.status_code == 403
        assert "does not match" in resp4.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ============================================================================
# 2. Production Environment Enforcement on Admin Routes (Finding #32)
# ============================================================================

def test_admin_token_production_enforcement(client, monkeypatch):
    """ENVIRONMENT=production must strictly prohibit fallback to dev_admin_token."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AGRIBRAIN_ADMIN_TOKEN", raising=False)

    # 1. /v2/crop-model/train
    resp1 = client.post(
        "/v2/crop-model/train",
        json={"min_quality_tier": "B"},
        headers={"X-Admin-Token": "dev_admin_token"},
    )
    assert resp1.status_code == 403
    assert "Forbidden" in resp1.json()["detail"]

    # 2. /v2/crop-model/evaluate
    resp2 = client.post(
        "/v2/crop-model/evaluate",
        json={"min_quality_tier": "B"},
        headers={"X-Admin-Token": "dev_admin_token"},
    )
    assert resp2.status_code == 403
    assert "Forbidden" in resp2.json()["detail"]

    # 3. /v2/crop-model/readiness
    resp3 = client.get(
        "/v2/crop-model/readiness",
        headers={"X-Admin-Token": "dev_admin_token"},
    )
    assert resp3.status_code == 403
    assert "Forbidden" in resp3.json()["detail"]


# ============================================================================
# 3. Bounded Background Worker Pool (Finding #34)
# ============================================================================

def test_pid_alive_detection():
    """Verify is_pid_alive accurately identifies current process and invalid PIDs."""
    assert is_pid_alive(os.getpid()) is True
    assert is_pid_alive(0) is False
    assert is_pid_alive(-1) is False
    assert is_pid_alive(9999999) is False


def test_bounded_worker_executor_concurrency_and_fifo(tmp_path, monkeypatch):
    """Verify BoundedJobExecutor caps concurrency and sorts queued jobs FIFO."""
    monkeypatch.setenv("AGRIBRAIN_MAX_WORKERS", "2")
    executor = BoundedJobExecutor(max_workers=2)

    # Initially 0 active workers -> can spawn
    assert executor.max_workers == 2
    assert executor.can_spawn() is True

    # Seed mock job records in tmp_path
    monkeypatch.setattr("services.agribrain.layer05_asmae.background_jobs.JOBS_DIR", tmp_path)

    now = datetime.now(timezone.utc)
    # Job 1: Running with live PID (current process) and valid lease
    job1_path = tmp_path / "job1.job.json"
    _atomic_json(job1_path, {
        "job_id": "job_1",
        "status": "running",
        "supervisor_pid": os.getpid(),
        "lease_expires_at": (now + timedelta(minutes=5)).isoformat(),
        "created_at": (now - timedelta(minutes=10)).isoformat(),
    })

    # Job 2: Running with live PID and valid lease
    job2_path = tmp_path / "job2.job.json"
    _atomic_json(job2_path, {
        "job_id": "job_2",
        "status": "running",
        "supervisor_pid": os.getpid(),
        "lease_expires_at": (now + timedelta(minutes=5)).isoformat(),
        "created_at": (now - timedelta(minutes=8)).isoformat(),
    })

    # Job 3: Queued (oldest)
    job3_path = tmp_path / "job3.job.json"
    _atomic_json(job3_path, {
        "job_id": "job_3",
        "status": "queued",
        "created_at": (now - timedelta(minutes=5)).isoformat(),
    })

    # Job 4: Queued (newer)
    job4_path = tmp_path / "job4.job.json"
    _atomic_json(job4_path, {
        "job_id": "job_4",
        "status": "queued",
        "created_at": (now - timedelta(minutes=2)).isoformat(),
    })

    # Active count is 1 (current PID deduplicated) -> can still spawn
    # If max_workers is set to 1, it should report cannot spawn
    executor_one = BoundedJobExecutor(max_workers=1)
    assert executor_one.can_spawn() is False

    # FIFO ordering: job3 should precede job4
    queued = executor.get_queued_jobs()
    assert len(queued) == 2
    assert queued[0].name == "job3.job.json"
    assert queued[1].name == "job4.job.json"


# ============================================================================
# 4. Defect A07 & P01.3: Resilient Job Recovery Tests
# ============================================================================

def test_supersede_helper_returns_without_name_error(tmp_path):
    """Verify _supersede_recovery_candidate and its alias return cleanly without NameError."""
    job_path = tmp_path / "test_target.job.json"
    _atomic_json(job_path, {
        "job_id": "target_job",
        "plot_id": "plot_target",
        "status": "queued",
        "revision": 1,
    })

    winner = {"job_id": "winner_job", "run_id": "winner_run"}
    initial_payload = _read_json(job_path)

    # Call _supersede_recovery_candidate directly
    result = _supersede_recovery_candidate(job_path, initial_payload, winner)
    assert result is not None
    assert result.get("status") == "superseded"
    assert result.get("superseded_by_job_id") == "winner_job"

    # Call via task A07 alias
    job2_path = tmp_path / "test_target2.job.json"
    _atomic_json(job2_path, {
        "job_id": "target_job_2",
        "plot_id": "plot_target_2",
        "status": "queued",
        "revision": 1,
    })
    result2 = _supersede_and_requeue_job(job2_path, _read_json(job2_path), winner)
    assert result2.get("status") == "superseded"


def test_completed_reintegration_pending_stalled_transition(tmp_path):
    """Verify expired completed_reintegration_pending transitions to stalled with resume_phase=reintegration."""
    job_path = tmp_path / "reintegration_stalled.job.json"
    past_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    _atomic_json(job_path, {
        "job_id": "reint_job",
        "plot_id": "reint_plot",
        "status": "completed_reintegration_pending",
        "lease_expires_at": past_time,
        "revision": 1,
    })

    updated = _mark_stalled_if_expired(job_path)
    assert updated.get("status") == "stalled"
    assert updated.get("resume_phase") == "reintegration"
    assert updated.get("recovery_reason") == "expired_worker_lease"


def test_active_unexpired_lease_is_protected_from_preemption(tmp_path, monkeypatch):
    """Running worker with valid unexpired lease must not be preempted or recovered."""
    monkeypatch.setattr("services.agribrain.layer05_asmae.background_jobs.JOBS_DIR", tmp_path)

    future_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    job_path = tmp_path / "live_worker.job.json"
    _atomic_json(job_path, {
        "job_id": "live_job",
        "plot_id": "plot_protected",
        "tenant_id": "tenant_1",
        "farm_id": "farm_1",
        "status": "running",
        "lease_expires_at": future_time,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    recovered = recover_pending_jobs(plot_id="plot_protected")
    assert recovered == 0

    # Verify job status remained running
    current = _read_json(job_path)
    assert current.get("status") == "running"


# ============================================================================
# 5. Distributed Single-Leader Recovery Lock (Finding #34)
# ============================================================================

def test_recovery_leader_lock_advisory(tmp_path, monkeypatch):
    """Verify single-leader advisory lock prevents multi-replica recovery collisions."""
    monkeypatch.setattr("services.agribrain.layer05_asmae.background_jobs.JOBS_DIR", tmp_path)

    # First acquisition succeeds
    acquired1 = acquire_recovery_leader_lock(lease_seconds=30)
    assert acquired1 is True

    # Second acquisition within active lease window returns False
    # (Simulating a second replica attempting startup recovery scan)
    lock_file = tmp_path / ".recovery_leader.lock"
    assert lock_file.exists()

    # If another process/replica checks with valid lease:
    data = _read_json(lock_file)
    data["leader_id"] = "other_replica_pid_8888"
    _atomic_json(lock_file, data)

    acquired2 = acquire_recovery_leader_lock(lease_seconds=30)
    assert acquired2 is False


# ============================================================================
# 6. Docker Compose MongoDB Bootstrap Verification (Finding #35)
# ============================================================================

def test_docker_compose_mongodb_bootstrap_repaired():
    """Verify docker-compose.yml uses db.adminCommand('ping') and advertises mongo:27017."""
    dc_path = Path(__file__).resolve().parents[3] / "infra" / "docker-compose.yml"
    assert dc_path.exists(), f"docker-compose.yml not found at {dc_path}"

    with open(dc_path, "r", encoding="utf-8") as f:
        dc_text = f.read()

    # 1. MongoDB healthcheck must use ping, avoiding rs.status() circular deadlock
    assert "db.adminCommand('ping')" in dc_text, (
        "Expected db.adminCommand('ping') in MongoDB healthcheck"
    )
    assert "rs.status()" not in dc_text, (
        "rs.status() circular healthcheck must not be present in mongo service"
    )

    # 2. mongo-init must advertise mongo:27017 on the Docker network
    assert "mongo:27017" in dc_text, (
        "mongo-init must advertise 'mongo:27017' host on the Docker network"
    )
    assert "localhost:27017" not in dc_text, (
        "mongo-init must NOT advertise 'localhost:27017' inside container"
    )
