"""Independent IR04 adversarial gate: receipt consistency != journal authority."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from services.agribrain.world_model.canonical_worldline import CanonicalWorldlineService
from services.agribrain.layer05_asmae.resolution.observation_footprint_adapter import (
    verify_bitemporal_replay_receipt,
)
from services.agribrain.layer05_asmae.resolution.journal_authority_gate import (
    verify_replay_against_trusted_worldline,
)


TENANT = "tenant-ir04"
FARM = "farm-ir04"
PLOT = "plot-ir04"
GEOM = "a" * 64
T = "2026-09-08T12:00:00+00:00"


@pytest.fixture
def anchored_replay(tmp_path):
    root = tmp_path / "worldline"
    anchor = tmp_path / "separate_durable_anchor"
    root.mkdir()
    anchor.mkdir()
    service = CanonicalWorldlineService(
        root=root, durable_anchor_root=anchor, require_durable_anchor=True,
    )
    service.commit_event(
        plot_id=PLOT, event_type="CROP_POSTERIOR",
        payload={"crop_posterior": {"lineage_id": "crop-ir04-test"}},
        geometry_hash=GEOM,
        observation_or_valid_time=T,
        effective_at=T,
        authority="qualified_test_authority",
        tenant_id=TENANT, namespace=FARM,
    )
    durable_checkpoint = service.save_durable_checkpoint(
        plot_id=PLOT, checkpoint_id="anchor-ir04-01",
        tenant_id=TENANT, namespace=FARM,
    )
    knowledge_k = durable_checkpoint["committed_at"]
    receipt = service.hydrate_context(
        PLOT,
        {"tenant_id": TENANT, "worldline_namespace": FARM, "geometry_hash": GEOM},
        valid_time_T=T,
        knowledge_cutoff_K=knowledge_k,
    )["bitemporal_replay_receipt"]
    return service, receipt


def _check(receipt, service=None, **changes):
    args = dict(
        tenant_id=TENANT, plot_id=PLOT, geometry_hash=GEOM,
        namespace=FARM, trusted_worldline=service,
    )
    args.update(changes)
    return verify_replay_against_trusted_worldline(receipt, **args)


def test_ir04_worldline_real_anchor_replay_is_accepted(anchored_replay):
    service, receipt = anchored_replay
    assert receipt["selected_evidence_set"]
    assert receipt["durable_anchor_bound"] is True
    ok, reason, knowledge_k = _check(receipt, service)
    assert ok is True, reason
    assert reason == "verified_anchored_worldline_replay"
    assert knowledge_k


def test_ir04_self_consistent_forged_evidence_digest_cannot_bypass_journal(anchored_replay):
    service, receipt = anchored_replay
    forged = copy.deepcopy(receipt)
    forged["selected_evidence_set"][0]["event_id"] = "synthetic-uncommitted-event"
    items = sorted(
        forged["selected_evidence_set"],
        key=lambda item: (str(item.get("event_type")), str(item.get("event_id"))),
    )
    forged["evidence_set_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(items, sort_keys=True).encode("utf-8")
    ).hexdigest()
    # Current digest-only verifier accepts an internally coherent fabrication.
    consistency, _, _ = verify_bitemporal_replay_receipt(
        forged, tenant_id=TENANT, plot_id=PLOT, geometry_hash=GEOM,
    )
    assert consistency is True
    ok, reason, knowledge_k = _check(forged, service)
    assert ok is False
    assert reason == "replay_evidence_not_from_trusted_journal"
    assert knowledge_k is None


def test_ir04_forged_journal_generation_is_rejected(anchored_replay):
    service, receipt = anchored_replay
    forged = copy.deepcopy(receipt)
    forged["journal_generation"] = receipt["journal_generation"] + 1
    ok, reason, _ = _check(forged, service)
    assert ok is False
    assert reason == "replay_generation_mismatch:journal_generation"


def test_ir04_unanchored_worldline_is_rejected(anchored_replay):
    anchored, receipt = anchored_replay
    unanchored = CanonicalWorldlineService(
        root=anchored.root, require_durable_anchor=False,
    )
    ok, reason, _ = _check(receipt, unanchored)
    assert ok is False
    assert reason == "durable_worldline_anchor_required"


def test_ir04_no_deployment_trusted_roots_fails_closed(anchored_replay, monkeypatch):
    _, receipt = anchored_replay
    monkeypatch.delenv("AKALORIS_ASMAE_TRUSTED_WORLDLINE_ROOT", raising=False)
    monkeypatch.delenv("CANONICAL_DURABLE_CHECKPOINT_ROOT", raising=False)
    ok, reason, _ = _check(receipt)
    assert ok is False
    assert reason == "trusted_worldline_roots_not_configured"


def test_ir04_future_cutoff_is_not_authority(anchored_replay):
    service, receipt = anchored_replay
    future = copy.deepcopy(receipt)
    future["query_parameters"]["knowledge_cutoff_time"] = (
        datetime.now(timezone.utc) + timedelta(days=365)
    ).isoformat()
    ok, reason, _ = _check(future, service)
    assert ok is False
    assert reason == "future_replay_knowledge_cutoff"



def test_ir04_cutoff_after_anchor_is_not_authoritative(anchored_replay):
    service, receipt = anchored_replay
    unanchored_cutoff = copy.deepcopy(receipt)
    unanchored_cutoff["query_parameters"]["knowledge_cutoff_time"] = (
        datetime.now(timezone.utc).isoformat()
    )
    ok, reason, _ = _check(unanchored_cutoff, service)
    assert ok is False
    assert reason == "knowledge_cutoff_not_covered_by_durable_checkpoint"
