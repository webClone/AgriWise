"""
ASMAE IR-03 Bitemporal Historical Replay Executable Contract Test Suite.

Verifies the 8 mandatory bitemporal replay scenarios:
  IR03-T01: Late backfill invisibility before commitment time K.
  IR03-T02: Future observation exclusion and scenario forecast isolation.
  IR03-T03: Deterministic idempotence across cold restarts with identical (T, K, evidence).
  IR03-T04: Non-destructive late backfill revision without mutating historical K1 snapshot.
  IR03-T05: Cross-artifact generation consistency (archive, crop, phenology, BMA).
  IR03-T06: Fail-closed on tenant, plot, geometry, or cycle mismatch.
  IR03-T07: Ordinary incremental assimilation vs selective historical replay.
  IR03-T08: Cache isolation enforcing (T, K) boundary keys without leaking latest events.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    WorldlineEventProposal,
    CorruptedWorldlineError,
    WORLDLINE_IDENTITY_V2,
    WORLDLINE_CONTRACT_VERSION,
)
from services.agribrain.layer05_asmae.runner import ASMAERunner
from services.agribrain.layer05_asmae import plot_snapshot_store
from services.agribrain.layer05_asmae.plot_snapshot_store import (
    publish_canonical_plot_snapshot,
    load_latest_plot_snapshot,
    _plot_dir,
)
from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash
from services.agribrain.layer10_sire.surface_contract import (
    RENDER_AUTHORIZATION_VERSION,
    SURFACES_SCHEMA_VERSION,
)


class BitemporalWorldlineHarness:
    """Helper delegating to production CanonicalWorldlineService dual-clock methods."""

    def __init__(self, worldline: CanonicalWorldlineService):
        self.worldline = worldline

    def query_eligible_events(
        self,
        plot_id: str,
        event_type: str,
        valid_time_T: datetime,
        knowledge_cutoff_K: datetime,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> List[Dict[str, Any]]:
        return self.worldline.select_eligible_events(
            plot_id=plot_id,
            event_type=event_type,
            valid_time_T=valid_time_T,
            knowledge_cutoff_K=knowledge_cutoff_K,
            tenant_id=tenant_id,
            namespace=namespace,
            fail_on_corrupt=True,
        )

    def latest_eligible_payload(
        self,
        plot_id: str,
        event_type: str,
        valid_time_T: datetime,
        knowledge_cutoff_K: datetime,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> Optional[Dict[str, Any]]:
        return self.worldline.latest_eligible_payload(
            plot_id=plot_id,
            event_type=event_type,
            valid_time_T=valid_time_T,
            knowledge_cutoff_K=knowledge_cutoff_K,
            tenant_id=tenant_id,
            namespace=namespace,
            fail_on_corrupt=True,
        )

    def hydrate_bitemporal_context(
        self,
        plot_id: str,
        valid_time_T: datetime,
        knowledge_cutoff_K: datetime,
        geometry_hash: str,
        tenant_id: str = "default_tenant",
        namespace: str = "default",
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "plot_id": plot_id,
            "tenant_id": tenant_id,
            "geometry_hash": geometry_hash,
            "worldline_namespace": namespace,
        }
        res = self.worldline.hydrate_context(
            plot_id=plot_id,
            context=context,
            valid_time_T=valid_time_T,
            knowledge_cutoff_K=knowledge_cutoff_K,
        )
        receipt = res.get("bitemporal_replay_receipt") or {}
        res["selected_event_ids"] = [e["event_id"] for e in receipt.get("selected_evidence_set", [])]
        res["evidence_set_digest"] = receipt.get("evidence_set_digest")
        return res


class ASMAEIR03BitemporalReplayContractTests(unittest.TestCase):
    """Authoritative test suite for the IR-03 Bitemporal Replay Contract."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="asmae_ir03_test_")
        self.worldline_root = Path(self.temp_dir) / "worldline"
        self.worldline = CanonicalWorldlineService(root=self.worldline_root)
        self.harness = BitemporalWorldlineHarness(self.worldline)

        self.tenant_id = "tenant-algeria-west"
        self.farm_id = "farm-mitidja-01"
        self.plot_id = "plot-afroun-citrus"
        self.geometry_hash = "620804f4"
        self.crop_cycle_id = "cycle-2026-harvest"

        self.base_time = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _commit_worldline_event(
        self,
        event_type: str,
        valid_day: int,
        commit_day: int,
        payload_data: Dict[str, Any],
        parent_ids: Optional[List[str]] = None,
        parent_event_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Commit an immutable event with explicit valid time T and commitment time K."""
        valid_dt = self.base_time + timedelta(days=valid_day)
        commit_dt = self.base_time + timedelta(days=commit_day)

        parents = tuple(parent_ids or parent_event_ids or ())
        prop = WorldlineEventProposal(
            event_type=event_type,
            geometry_version=self.geometry_hash,
            observation_or_valid_time=valid_dt.isoformat(),
            model_version="asmae_v83_test",
            evidence_set_hash=hashlib.sha256(f"evidence-{event_type}-{valid_day}".encode()).hexdigest(),
            authority_contract_version="canonical_test_v1",
            authority_ref="test_authority",
            payload=payload_data,
            parent_event_ids=parents,
        )
        rec = self.worldline.commit_proposal(
            plot_id=self.plot_id,
            proposal=prop,
            tenant_id=self.tenant_id,
            namespace="default",
            effective_at=valid_dt.isoformat(),
        )
        # To simulate the exact commitment time K in testing, update committed_at on disk
        event_path = self.worldline._event_path(self.plot_id, rec["event_id"], self.tenant_id, "default")
        event_data = json.loads(event_path.read_text(encoding="utf-8"))
        event_data["committed_at"] = commit_dt.isoformat()
        if parents:
            event_data["parent_event_ids"] = list(parents)
        event_path.write_text(json.dumps(event_data), encoding="utf-8")
        rec["committed_at"] = commit_dt.isoformat()
        if parents:
            rec["parent_event_ids"] = list(parents)
        return rec

    # =========================================================================
    # IR03-T01: Late Backfill Invisibility Before Commitment Time K
    # =========================================================================
    def test_ir03_t01_late_backfill_invisibility_before_commitment(self):
        """Archive accepted on day 20 for observations dated day 5 is invisible to (T=day 10, K=day 10) but visible to (T=day 10, K=day 21)."""
        # Event 1: Early baseline archive valid on Day 2, committed on Day 3
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=2,
            commit_day=3,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "version": "v1_early"}},
        )

        # Event 2: Late-arriving backfilled archive valid on Day 5, committed on Day 20
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=5,
            commit_day=20,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "version": "v2_late_backfill"}},
        )

        # Replay at (T=Day 10, K=Day 10): Backfill committed on Day 20 MUST BE INVISIBLE
        t_day10 = self.base_time + timedelta(days=10)
        k_day10 = self.base_time + timedelta(days=10)
        res_k10 = self.harness.latest_eligible_payload(
            plot_id=self.plot_id,
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_time_T=t_day10,
            knowledge_cutoff_K=k_day10,
            tenant_id=self.tenant_id,
        )
        self.assertIsNotNone(res_k10)
        self.assertEqual(res_k10["archive_posterior"]["version"], "v1_early", "Late backfill must NOT leak into Day 10 cutoff")

        # Replay at (T=Day 10, K=Day 21): After commitment on Day 20, backfill MUST BE VISIBLE
        k_day21 = self.base_time + timedelta(days=21)
        res_k21 = self.harness.latest_eligible_payload(
            plot_id=self.plot_id,
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_time_T=t_day10,
            knowledge_cutoff_K=k_day21,
            tenant_id=self.tenant_id,
        )
        self.assertIsNotNone(res_k21)
        self.assertEqual(res_k21["archive_posterior"]["version"], "v2_late_backfill", "Late backfill must be visible after commitment cutoff")

    # =========================================================================
    # IR03-T02: Future Observation Exclusion & Scenario Forecast Separation
    # =========================================================================
    def test_ir03_t02_future_observation_exclusion_and_forecast_separation(self):
        """Event committed on day 9 containing observation valid day 12 is excluded from day 10 historical state."""
        # Event with future valid date (Day 12) committed on Day 9 (e.g. forecast scenario)
        self._commit_worldline_event(
            event_type="SCENARIO_FORECAST",
            valid_day=12,
            commit_day=9,
            payload_data={"scenario": "projected_drought"},
        )
        # Event with observed valid date (Day 8) committed on Day 9
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=8,
            commit_day=9,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "version": "day8_observed"}},
        )

        t_day10 = self.base_time + timedelta(days=10)
        k_day10 = self.base_time + timedelta(days=10)

        # Query for ARCHIVE_POSTERIOR_VALIDATED at Day 10: Day 8 is accepted
        arch = self.harness.latest_eligible_payload(
            plot_id=self.plot_id,
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_time_T=t_day10,
            knowledge_cutoff_K=k_day10,
            tenant_id=self.tenant_id,
        )
        self.assertEqual(arch["archive_posterior"]["version"], "day8_observed")

        # Query for SCENARIO_FORECAST at Day 10: valid_day=12 > 10, must NOT be returned as historical observation
        forecast_eligible = self.harness.query_eligible_events(
            plot_id=self.plot_id,
            event_type="SCENARIO_FORECAST",
            valid_time_T=t_day10,
            knowledge_cutoff_K=k_day10,
            tenant_id=self.tenant_id,
        )
        self.assertEqual(len(forecast_eligible), 0, "Future valid date must be excluded from historical replay")

    # =========================================================================
    # IR03-T03: Deterministic Idempotence Across Cold Restarts
    # =========================================================================
    def test_ir03_t03_deterministic_idempotence_across_restarts(self):
        """Identical (T, K, evidence-set, model-config) replay produces identical results across restarts."""
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=4,
            commit_day=5,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "soil_moisture": 0.320}},
        )
        self._commit_worldline_event(
            event_type="CROP_POSTERIOR",
            valid_day=4,
            commit_day=5,
            payload_data={"crop_posterior": {"crop_type": "citrus", "stage": "fruiting"}, "content_hash": "hash-crop-c1"},
        )

        t = self.base_time + timedelta(days=7)
        k = self.base_time + timedelta(days=7)

        # Hydrate run 1
        ctx1 = self.harness.hydrate_bitemporal_context(
            plot_id=self.plot_id,
            valid_time_T=t,
            knowledge_cutoff_K=k,
            geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id,
        )

        # Re-instantiate worldline (cold restart)
        cold_worldline = CanonicalWorldlineService(root=self.worldline_root)
        cold_harness = BitemporalWorldlineHarness(cold_worldline)

        # Hydrate run 2
        ctx2 = cold_harness.hydrate_bitemporal_context(
            plot_id=self.plot_id,
            valid_time_T=t,
            knowledge_cutoff_K=k,
            geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id,
        )

        self.assertEqual(ctx1["selected_event_ids"], ctx2["selected_event_ids"])
        self.assertEqual(ctx1["evidence_set_digest"], ctx2["evidence_set_digest"])
        self.assertEqual(ctx1["archive_posterior"], ctx2["archive_posterior"])

    # =========================================================================
    # IR03-T04: Non-Destructive Backfill Revision (Preserves Original Snapshot)
    # =========================================================================
    def test_ir03_t04_nondestructive_backfill_revision(self):
        """Late backfill yields new knowledge version without mutating original published Day 10 snapshot."""
        # 1. State as known on Day 10
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=7,
            commit_day=8,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "value": 100}},
        )
        t_day10 = self.base_time + timedelta(days=10)
        k_day10 = self.base_time + timedelta(days=10)
        h10 = self.harness.hydrate_bitemporal_context(self.plot_id, t_day10, k_day10, self.geometry_hash, self.tenant_id)

        # 2. Backfill admitted on Day 25
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=9,
            commit_day=25,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "value": 200}},
        )

        # Re-query under K=Day 10: Original answer MUST BE UNCHANGED
        h10_post = self.harness.hydrate_bitemporal_context(self.plot_id, t_day10, k_day10, self.geometry_hash, self.tenant_id)
        self.assertEqual(h10["evidence_set_digest"], h10_post["evidence_set_digest"])
        self.assertEqual(h10_post["archive_posterior"]["value"], 100)

        # Query under K=Day 26: New knowledge version
        k_day26 = self.base_time + timedelta(days=26)
        h26 = self.harness.hydrate_bitemporal_context(self.plot_id, t_day10, k_day26, self.geometry_hash, self.tenant_id)
        self.assertNotEqual(h10["evidence_set_digest"], h26["evidence_set_digest"])
        self.assertEqual(h26["archive_posterior"]["value"], 200)

    # =========================================================================
    # IR03-T05: Generation Consistency Across Context (No Mixed Generations)
    # =========================================================================
    def test_ir03_t05_generation_consistency_no_mixed_generations(self):
        """Archive, crop, phenology, and BMA all come from an eligible, mutually compatible knowledge generation."""
        # Gen 1: committed on Day 4
        self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 3, 4, {"archive_posterior": {"geometry_hash": self.geometry_hash, "gen": 1}})
        self._commit_worldline_event("CROP_POSTERIOR", 3, 4, {"crop_posterior": {"gen": 1}, "content_hash": "gen1-crop"})

        # Gen 2: archive committed on Day 15, crop committed on Day 22
        self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 8, 15, {"archive_posterior": {"geometry_hash": self.geometry_hash, "gen": 2}})
        self._commit_worldline_event("CROP_POSTERIOR", 8, 22, {"crop_posterior": {"gen": 2}, "content_hash": "gen2-crop"})

        t = self.base_time + timedelta(days=10)
        # At K=Day 18: Archive Gen 2 is committed, but Crop Gen 2 was NOT committed until Day 22.
        # System must hydrate Archive Gen 2 and Crop Gen 1 (pre-K), preserving auditable cutoff without crash
        k_day18 = self.base_time + timedelta(days=18)
        ctx = self.harness.hydrate_bitemporal_context(self.plot_id, t, k_day18, self.geometry_hash, self.tenant_id)

        self.assertEqual(ctx["archive_posterior"]["gen"], 2)
        self.assertEqual(ctx["crop_posterior"]["gen"], 1, "Crop posterior from Day 22 must not leak into Day 18 cutoff")

    # =========================================================================
    # IR03-T06: Fail-Closed on Mismatch
    # =========================================================================
    def test_ir03_t06_fail_closed_on_geometry_or_tenant_mismatch(self):
        """Mismatched tenant or geometry version fails closed, returning unavailable rather than latest head."""
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=5,
            commit_day=6,
            payload_data={"archive_posterior": {"geometry_hash": "old_geometry_9999", "value": 50}},
        )

        t = self.base_time + timedelta(days=10)
        k = self.base_time + timedelta(days=10)

        # Hydrate with current geometry: should fail-closed and omit mismatched archive
        ctx = self.harness.hydrate_bitemporal_context(
            plot_id=self.plot_id,
            valid_time_T=t,
            knowledge_cutoff_K=k,
            geometry_hash=self.geometry_hash,  # "620804f4" != "old_geometry_9999"
            tenant_id=self.tenant_id,
        )
        self.assertNotIn("archive_posterior", ctx, "Mismatched geometry must fail closed")

        # Cross-tenant query: foreign tenant must return zero eligible events
        foreign_events = self.harness.query_eligible_events(
            plot_id=self.plot_id,
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_time_T=t,
            knowledge_cutoff_K=k,
            tenant_id="tenant-foreign-attacker",
        )
        self.assertEqual(len(foreign_events), 0, "Foreign tenant must never access worldline events")

    # =========================================================================
    # IR03-T07: Ordinary Incremental Assimilation vs Selective Replay
    # =========================================================================
    def test_ir03_t07_ordinary_incremental_vs_selective_replay(self):
        """Ordinary observation uses incremental progression; late backfill triggers selective historical replay."""
        # Baseline Day 1 -> Day 2 -> Day 3 incremental events
        self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 1, 1, {"step": 1})
        self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 2, 2, {"step": 2})
        self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 3, 3, {"step": 3})

        t3 = self.base_time + timedelta(days=3)
        k3 = self.base_time + timedelta(days=3)
        events_t3 = self.harness.query_eligible_events(self.plot_id, "ARCHIVE_POSTERIOR_VALIDATED", t3, k3, self.tenant_id)
        self.assertEqual(len(events_t3), 3)

        # Targeted selective replay at Day 2: only walks events up to Day 2
        t2 = self.base_time + timedelta(days=2)
        events_t2 = self.harness.query_eligible_events(self.plot_id, "ARCHIVE_POSTERIOR_VALIDATED", t2, k3, self.tenant_id)
        self.assertEqual(len(events_t2), 2)
        self.assertEqual(events_t2[-1]["payload"]["step"], 2)

    # =========================================================================
    # IR03-T08: Cache Isolation Enforcing (T, K) Boundary Keys
    # =========================================================================
    def test_ir03_t08_cache_isolation_enforcing_dual_clock_boundary_keys(self):
        """Warm and cold cache responses obey (T, K) selection and never leak post-cutoff events."""
        self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 5, 5, {"archive_posterior": {"geometry_hash": self.geometry_hash, "val": 10}})

        t5 = self.base_time + timedelta(days=5)
        k5 = self.base_time + timedelta(days=5)
        res1 = self.harness.latest_eligible_payload(self.plot_id, "ARCHIVE_POSTERIOR_VALIDATED", t5, k5, self.tenant_id)
        self.assertEqual(res1["archive_posterior"]["val"], 10)

        # Add later event on Day 15
        self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 15, 15, {"archive_posterior": {"geometry_hash": self.geometry_hash, "val": 20}})

        # Subsequent query with key (T=5, K=5) MUST STILL return val=10, not 20
        res2 = self.harness.latest_eligible_payload(self.plot_id, "ARCHIVE_POSTERIOR_VALIDATED", t5, k5, self.tenant_id)
        self.assertEqual(res2["archive_posterior"]["val"], 10, "Cache key (T, K) must not leak newer event")

    # =========================================================================
    # IR03-T09: Corrupt Worldline Journal & Sequence Gaps Fail Closed (IR03-R02)
    # =========================================================================
    def test_ir03_t09_corrupt_worldline_and_sequence_gaps_fail_closed(self):
        """Unreadable event journal files or sequence gaps fail closed under fail_on_corrupt=True."""
        # Commit event 1 (sequence 1)
        ev1 = self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=1,
            commit_day=1,
            payload_data={"step": 1},
        )
        # Commit event 2 (sequence 2)
        ev2 = self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=2,
            commit_day=2,
            payload_data={"step": 2},
        )

        t = self.base_time + timedelta(days=5)
        k = self.base_time + timedelta(days=5)

        # Baseline: normal query succeeds
        events = self.worldline.select_eligible_events(
            self.plot_id, "ARCHIVE_POSTERIOR_VALIDATED", t, k, self.tenant_id, fail_on_corrupt=True
        )
        self.assertEqual(len(events), 2)

        # 1. Simulate sequence gap: delete event 1 from disk (only seq 2 remains)
        p1 = self.worldline._event_path(self.plot_id, ev1["event_id"], self.tenant_id, "default")
        backup_bytes = p1.read_bytes()
        p1.unlink()

        with self.assertRaises(CorruptedWorldlineError) as cm_gap:
            self.worldline.load_all_events(self.plot_id, self.tenant_id, fail_on_corrupt=True)
        self.assertIn("sequence gap detected", str(cm_gap.exception).lower())

        with self.assertRaises(CorruptedWorldlineError):
            self.worldline.select_eligible_events(
                self.plot_id, "ARCHIVE_POSTERIOR_VALIDATED", t, k, self.tenant_id, fail_on_corrupt=True
            )

        # 2. Restore event 1 and corrupt event 2 with invalid JSON
        p1.write_bytes(backup_bytes)
        p2 = self.worldline._event_path(self.plot_id, ev2["event_id"], self.tenant_id, "default")
        p2.write_text("{ malformed json corrupted bytes", encoding="utf-8")

        with self.assertRaises(CorruptedWorldlineError) as cm_corrupt:
            self.worldline.load_all_events(self.plot_id, self.tenant_id, fail_on_corrupt=True)
        self.assertIn("corruption", str(cm_corrupt.exception).lower())

        # Hydrate context in bitemporal mode must fail closed on corruption
        with self.assertRaises(CorruptedWorldlineError):
            self.worldline.hydrate_context(
                plot_id=self.plot_id,
                context={
                    "plot_id": self.plot_id,
                    "tenant_id": self.tenant_id,
                    "geometry_hash": self.geometry_hash,
                },
                valid_time_T=t,
                knowledge_cutoff_K=k,
            )

    # =========================================================================
    # IR03-T10: Derived Posterior Post-K Parent Dependency Rejected (IR03-R03/R05)
    # =========================================================================
    def test_ir03_t10_derived_posterior_post_k_parent_dependency_rejected(self):
        """Derived posterior whose parent dependencies post-date knowledge cutoff K is rejected."""
        # 1. Create parent archive event valid on Day 2, but committed late on Day 25
        parent_ev = self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=2,
            commit_day=25,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "val": "parent_archive"}},
        )
        parent_id = parent_ev["event_id"]

        # 2. Create child crop posterior valid on Day 5, committed on Day 20, referencing parent_id
        prop = WorldlineEventProposal(
            event_type="CROP_POSTERIOR",
            geometry_version=self.geometry_hash,
            observation_or_valid_time=(self.base_time + timedelta(days=5)).isoformat(),
            model_version="asmae_v83_test",
            evidence_set_hash="hash-evidence-child",
            authority_contract_version="canonical_test_v1",
            authority_ref="test_authority",
            parent_event_ids=(parent_id,),
            payload={"crop_posterior": {"stage": "derived_stage"}, "content_hash": "child-crop-hash"},
        )
        child_rec = self.worldline.commit_proposal(
            plot_id=self.plot_id,
            proposal=prop,
            tenant_id=self.tenant_id,
            namespace="default",
            effective_at=(self.base_time + timedelta(days=5)).isoformat(),
        )
        child_path = self.worldline._event_path(self.plot_id, child_rec["event_id"], self.tenant_id, "default")
        child_data = json.loads(child_path.read_text(encoding="utf-8"))
        child_data["committed_at"] = (self.base_time + timedelta(days=20)).isoformat()
        child_path.write_text(json.dumps(child_data), encoding="utf-8")

        t_day10 = self.base_time + timedelta(days=10)

        # Query at K=Day 22:
        # Child was committed on Day 20 <= Day 22.
        # BUT parent was committed on Day 25 > Day 22!
        # Provenance enforcement MUST reject child as look-ahead contaminated.
        k_day22 = self.base_time + timedelta(days=22)
        res_k22 = self.worldline.latest_eligible_payload(
            plot_id=self.plot_id,
            event_type="CROP_POSTERIOR",
            valid_time_T=t_day10,
            knowledge_cutoff_K=k_day22,
            tenant_id=self.tenant_id,
            fail_on_corrupt=True,
        )
        self.assertIsNone(res_k22, "Child posterior with post-K parent dependency must be rejected")

        # Query at K=Day 26:
        # Both child (Day 20) and parent (Day 25) are <= Day 26.
        # Provenance check passes!
        k_day26 = self.base_time + timedelta(days=26)
        res_k26 = self.worldline.latest_eligible_payload(
            plot_id=self.plot_id,
            event_type="CROP_POSTERIOR",
            valid_time_T=t_day10,
            knowledge_cutoff_K=k_day26,
            tenant_id=self.tenant_id,
            fail_on_corrupt=True,
        )
        self.assertIsNotNone(res_k26)
        self.assertEqual(res_k26["crop_posterior"]["stage"], "derived_stage")

    # =========================================================================
    # IR03-T11: ASMAERunner Execution Binds Bitemporal Replay Receipt
    # =========================================================================
    def test_ir03_t11_runner_execute_binds_bitemporal_replay_receipt(self):
        """ASMAERunner.execute() transparently binds bitemporal_replay_receipt on dual-clock queries."""
        # Commit archive event valid on Day 3, committed on Day 4
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=3,
            commit_day=4,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "version": "r_arch_v1"}},
        )

        runner = ASMAERunner()
        t_req = self.base_time + timedelta(days=7)
        k_req = self.base_time + timedelta(days=7)

        context: Dict[str, Any] = {
            "plot_id": self.plot_id,
            "tenant_id": self.tenant_id,
            "farm_id": self.farm_id,
            "geometry_hash": self.geometry_hash,
            "worldline_root": self.worldline_root,
            "observation_valid_time": t_req.isoformat(),
            "knowledge_cutoff_time": k_req.isoformat(),
            "mode": "quick_visual",
            "execution_permissions": {
                "compute_allowed": True,
                "visual_authority_allowed": True,
                "diagnostic_allowed": True,
            },
        }

        result = runner.execute(
            self.plot_id,
            "run-test-ir03-11",
            context,
            mode="quick_visual",
        )
        self.assertIsNotNone(result)
        receipt = result.get("bitemporal_replay_receipt")
        self.assertIsNotNone(receipt, "Result must contain bitemporal_replay_receipt")
        self.assertEqual(receipt.get("replay_mode"), "bitemporal_deterministic_v1")
        self.assertEqual(receipt.get("contract_version"), "canonical_bitemporal_replay_receipt_v1")
        self.assertEqual(receipt.get("query_parameters", {}).get("observation_valid_time"), t_req.isoformat())
        self.assertEqual(receipt.get("query_parameters", {}).get("knowledge_cutoff_time"), k_req.isoformat())
        self.assertTrue(receipt.get("evidence_set_digest", "").startswith("sha256:"))
        self.assertEqual(len(receipt.get("selected_evidence_set", [])), 1)
        self.assertEqual(receipt["selected_evidence_set"][0]["event_type"], "ARCHIVE_POSTERIOR_VALIDATED")

    # =========================================================================
    # IR03-T12: Head Watermark Detects Tail Journal Truncation
    # =========================================================================
    def test_ir03_t12_head_watermark_detects_tail_journal_truncation(self):
        """Head watermark detects deletion of tail events even when internal sequences are contiguous."""
        # Commit 3 events: sequences 1, 2, 3
        e1 = self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 1, 2, {"archive_posterior": {"geometry_hash": self.geometry_hash, "val": 1}})
        e2 = self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 2, 3, {"archive_posterior": {"geometry_hash": self.geometry_hash, "val": 2}})
        e3 = self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 3, 4, {"archive_posterior": {"geometry_hash": self.geometry_hash, "val": 3}})

        # Head sequence is 3
        head = self.worldline.load_head(self.plot_id, self.tenant_id)
        self.assertEqual(int(head["sequence"]), 3)

        # Contiguous check passes initially
        events = self.worldline.load_all_events(self.plot_id, self.tenant_id, fail_on_corrupt=True)
        self.assertEqual(len(events), 3)

        # Adversarially delete tail event (e3) from disk, leaving e1 and e2 (contiguous 1, 2)
        e3_path = self.worldline._event_path(self.plot_id, e3["event_id"], self.tenant_id)
        self.assertTrue(e3_path.exists())
        e3_path.unlink()

        # load_all_events with fail_on_corrupt must raise CorruptedWorldlineError
        with self.assertRaises(CorruptedWorldlineError) as ctx_err:
            self.worldline.load_all_events(self.plot_id, self.tenant_id, fail_on_corrupt=True)
        self.assertIn("truncation", str(ctx_err.exception).lower())

    # =========================================================================
    # IR03-T13: Recursive Ancestor Lineage Rejects Post-K Grandparent
    # =========================================================================
    def test_ir03_t13_recursive_ancestor_lineage_rejects_post_k_grandparent(self):
        """Recursive DAG traversal detects when an ancestor grandparent was committed after cutoff K."""
        # Grandparent A: committed on Day 30
        grandparent_a = self._commit_worldline_event(
            event_type="OBSERVATION_RAW",
            valid_day=1,
            commit_day=30,
            payload_data={"raw_val": 42},
        )

        # Parent B: committed on Day 10, references Grandparent A
        parent_b = self._commit_worldline_event(
            event_type="INTERMEDIATE_FEATURE",
            valid_day=2,
            commit_day=10,
            payload_data={"parent_val": 42},
            parent_ids=[grandparent_a["event_id"]],
        )

        # Child C: committed on Day 15, references Parent B
        child_c = self._commit_worldline_event(
            event_type="CROP_POSTERIOR",
            valid_day=3,
            commit_day=15,
            payload_data={"crop_posterior": {"stage": "deep_lineage_test"}},
            parent_ids=[parent_b["event_id"]],
        )

        t_eval = self.base_time + timedelta(days=5)
        # Query at K=Day 20: Child C (Day 15) <= Day 20, Parent B (Day 10) <= Day 20.
        # BUT Grandparent A was committed at Day 30 > Day 20!
        k_day20 = self.base_time + timedelta(days=20)
        res_k20 = self.worldline.latest_eligible_payload(
            plot_id=self.plot_id,
            event_type="CROP_POSTERIOR",
            valid_time_T=t_eval,
            knowledge_cutoff_K=k_day20,
            tenant_id=self.tenant_id,
            fail_on_corrupt=True,
        )
        self.assertIsNone(res_k20, "Child C must be rejected because its transitive ancestor A post-dates K")

        # Query at K=Day 35: All ancestors A (30), B (10), C (15) <= Day 35.
        k_day35 = self.base_time + timedelta(days=35)
        res_k35 = self.worldline.latest_eligible_payload(
            plot_id=self.plot_id,
            event_type="CROP_POSTERIOR",
            valid_time_T=t_eval,
            knowledge_cutoff_K=k_day35,
            tenant_id=self.tenant_id,
            fail_on_corrupt=True,
        )
        self.assertIsNotNone(res_k35)
        self.assertEqual(res_k35["crop_posterior"]["stage"], "deep_lineage_test")

    # =========================================================================
    # IR03-T14: Evidence Classification Rejects Forecast/Scenario Masquerade
    # =========================================================================
    def test_ir03_t14_evidence_classification_rejects_forecast_masquerading_as_observation(self):
        """Forecast, synthetic, and scenario packets must never masquerade as historical observations."""
        # Commit legitimate observation on Day 3, committed Day 4
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=3,
            commit_day=4,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "kind": "real_observation"}},
        )

        # Commit forecast event valid on Day 5, committed Day 6
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=5,
            commit_day=6,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "kind": "projected_forecast"}, "is_forecast": True},
        )

        # Commit scenario event valid on Day 6, committed Day 7
        self._commit_worldline_event(
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_day=6,
            commit_day=7,
            payload_data={"archive_posterior": {"geometry_hash": self.geometry_hash, "kind": "counterfactual_scenario"}, "scenario": True},
        )

        t_eval = self.base_time + timedelta(days=10)
        k_eval = self.base_time + timedelta(days=10)

        # Query latest eligible payload
        latest = self.worldline.latest_eligible_payload(
            plot_id=self.plot_id,
            event_type="ARCHIVE_POSTERIOR_VALIDATED",
            valid_time_T=t_eval,
            knowledge_cutoff_K=k_eval,
            tenant_id=self.tenant_id,
            fail_on_corrupt=True,
        )
        self.assertIsNotNone(latest)
        self.assertEqual(latest["archive_posterior"]["kind"], "real_observation")

    # =========================================================================
    # IR03-T15: Security & Filesystem Containment Blocks Path Traversal
    # =========================================================================
    def test_ir03_t15_security_filesystem_containment_blocks_path_traversal(self):
        """Path traversal characters in worldline_root, tenant_id, namespace, or event_id raise SecurityViolation."""
        from services.agribrain.world_model.canonical_worldline import SecurityViolation

        # 1. Traversal in worldline_root init
        with self.assertRaises(SecurityViolation):
            CanonicalWorldlineService(root="../traversal_root")

        # 2. Traversal in event_path
        with self.assertRaises(SecurityViolation):
            self.worldline._event_path(self.plot_id, "../evil_event", self.tenant_id)

        # 3. Traversal in runner context worldline_root
        runner = ASMAERunner()
        bad_context = {
            "plot_id": self.plot_id,
            "tenant_id": self.tenant_id,
            "farm_id": self.farm_id,
            "worldline_root": "../escaped_dir",
            "knowledge_cutoff_time": (self.base_time + timedelta(days=5)).isoformat(),
            "execution_permissions": {"production_authority_allowed": True},
        }
        with self.assertRaises(SecurityViolation):
            runner.execute(self.plot_id, "run-bad-traversal", bad_context, mode="quick_visual")

    # =========================================================================
    # IR03-T16: Snapshot Store Binds Bitemporal Replay Receipt and Digest
    # =========================================================================
    def test_ir03_t16_snapshot_store_binds_bitemporal_replay_receipt_and_digest(self):
        """Published canonical plot snapshot envelopes (node, publication, receipt, head) bind replay receipt."""
        from services.agribrain.layer05_asmae.plot_snapshot_store import (
            publish_canonical_plot_snapshot,
            load_plot_snapshot_by_id,
            _plot_dir,
            _coerce_namespace,
        )

        mock_replay_receipt = {
            "contract_version": "canonical_bitemporal_replay_receipt_v1",
            "replay_mode": "bitemporal_deterministic_v1",
            "evidence_set_digest": "sha256:d17e3f890b5ca7b649a21e428cf157bb674e2bda63914a1c5d98fa6a8b7c93e1",
            "observation_valid_time": "2026-09-08T12:00:00+00:00",
            "knowledge_cutoff_time": "2026-09-08T12:00:00+00:00",
        }

        snapshot_id = "ASMAE-SNAPSHOT-replayreceiptbind001"
        asmae_result = {
            "snapshot_id": snapshot_id,
            "content_hash": "sha256:mock_asmae_hash_123",
            "bitemporal_replay_receipt": mock_replay_receipt,
            "crop_posterior_lineage": "lineage-001",
            "crop_worldline_event_id": "evt-crop-001",
            "phenology_worldline_event_id": "evt-pheno-001",
            "canRenderPixels": False,
        }
        frontend_payload = {
            "intelligence_snapshot_id": snapshot_id,
            "surface_inventory_hash": "mock_inventory_hash_123",
            "evidence_cutoff_at": "2026-09-08T12:00:00+00:00",
            "scientific_evidence_lineage": {
                "crop_posterior_lineage": "lineage-001",
                "crop_worldline_event_id": "evt-crop-001",
                "phenology_worldline_event_id": "evt-pheno-001",
            },
        }

        head = publish_canonical_plot_snapshot(
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            plot_id=self.plot_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend_payload,
            job_id="job-ir03-receipt-test",
            manifest_hash="manifest-ir03-test",
            snapshot_kind="asmae",
        )

        # 1. Head contains replay receipt and evidence_set_digest
        self.assertIn("bitemporal_replay_receipt", head)
        self.assertEqual(head["evidence_set_digest"], mock_replay_receipt["evidence_set_digest"])

        # 2. Loaded snapshot node contains replay receipt and digest
        loaded = load_plot_snapshot_by_id(
            snapshot_id=snapshot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            plot_id=self.plot_id,
        )
        self.assertIsNotNone(loaded)
        self.assertIn("bitemporal_replay_receipt", loaded)
        self.assertEqual(loaded["evidence_set_digest"], mock_replay_receipt["evidence_set_digest"])

        # 3. Publication file on disk contains replay receipt and digest
        ns = _coerce_namespace(self.plot_id, tenant_id=self.tenant_id, farm_id=self.farm_id)
        pub_path = Path(head["frontend_publication_ref"])
        self.assertTrue(pub_path.exists())
        with open(pub_path, "r", encoding="utf-8") as f:
            pub_data = json.load(f)
        self.assertIn("bitemporal_replay_receipt", pub_data)
        self.assertEqual(pub_data["evidence_set_digest"], mock_replay_receipt["evidence_set_digest"])

        # 4. Receipt file on disk contains replay receipt and digest
        rec_path = Path(head["publication_receipt_ref"])
        self.assertTrue(rec_path.exists())
        with open(rec_path, "r", encoding="utf-8") as f:
            rec_data = json.load(f)
        self.assertIn("bitemporal_replay_receipt", rec_data)
        self.assertEqual(rec_data["evidence_set_digest"], mock_replay_receipt["evidence_set_digest"])

    # =========================================================================
    # IR03-T17: Missing Intermediate Ancestor Fails Closed (IR03-V04)
    # =========================================================================
    def test_ir03_t17_missing_intermediate_ancestor_fails_closed(self):
        """Deleting an intermediate ancestor file from disk must fail closed; never silently accept."""
        # 1. Grandparent A (Day 1)
        gp_a = self._commit_worldline_event("OBSERVATION_RAW", 1, 2, {"val": "gp_a"})
        # 2. Parent B (Day 2, references gp_a)
        parent_b = self._commit_worldline_event(
            "INTERMEDIATE_FEATURE", 2, 3, {"val": "p_b"}, parent_ids=[gp_a["event_id"]]
        )
        # 3. Child C (Day 3, references parent_b)
        child_c = self._commit_worldline_event(
            "CROP_POSTERIOR", 3, 4, {"crop_posterior": {"stage": "t17_test"}}, parent_ids=[parent_b["event_id"]]
        )

        t = self.base_time + timedelta(days=10)
        k = self.base_time + timedelta(days=10)

        # Baseline: query succeeds
        res_ok = self.worldline.latest_eligible_payload(
            self.plot_id, "CROP_POSTERIOR", t, k, self.tenant_id, fail_on_corrupt=True
        )
        self.assertIsNotNone(res_ok)

        # Adversarially delete intermediate parent_b from disk
        p_b_path = self.worldline._event_path(self.plot_id, parent_b["event_id"], self.tenant_id)
        self.assertTrue(p_b_path.exists())
        p_b_path.unlink()

        # Under fail_on_corrupt=False, child_c must be rejected, returning None (never silently accepted)
        res_soft = self.worldline.latest_eligible_payload(
            self.plot_id, "CROP_POSTERIOR", t, k, self.tenant_id, fail_on_corrupt=False
        )
        self.assertIsNone(res_soft, "Derived event with missing ancestor must never be accepted")

        # Now test fail_on_corrupt=True when child references an ancestor that was deleted but sequences intact:
        # Re-commit parent_b to restore sequence continuity
        p_b_data = json.loads(p_b_path.with_suffix(".json.bak").read_text(encoding="utf-8")) if p_b_path.with_suffix(".json.bak").exists() else {"event_id": parent_b["event_id"], "sequence": parent_b["sequence"], "event_type": "INTERMEDIATE_FEATURE", "committed_at": parent_b["committed_at"], "observation_or_valid_time": parent_b["observation_or_valid_time"], "payload": {"val": "restored"}}
        p_b_path.write_text(json.dumps(p_b_data), encoding="utf-8")

        # Tamper child_c's parent_event_ids to reference a missing ancestor ID
        child_c_path = self.worldline._event_path(self.plot_id, child_c["event_id"], self.tenant_id)
        child_data = json.loads(child_c_path.read_text(encoding="utf-8"))
        child_data["parent_event_ids"] = ["evt_missing_ancestor_phantom"]
        child_c_path.write_text(json.dumps(child_data), encoding="utf-8")

        with self.assertRaises(CorruptedWorldlineError) as ctx_err:
            self.worldline.select_eligible_events(
                self.plot_id, "CROP_POSTERIOR", t, k, self.tenant_id, fail_on_corrupt=True
            )
        self.assertIn("missing ancestor", str(ctx_err.exception).lower())

    # =========================================================================
    # IR03-T18: Joint Head and Journal Rollback Detected (IR03-V02)
    # =========================================================================
    def test_ir03_t18_joint_head_and_journal_rollback_detected(self):
        """Rollback of both mutable head and event files is detected via durable checkpoints."""
        # 1. Commit 3 events
        e1 = self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 1, 2, {"archive_posterior": {"geometry_hash": self.geometry_hash, "v": 1}})
        e2 = self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 2, 3, {"archive_posterior": {"geometry_hash": self.geometry_hash, "v": 2}})
        e3 = self._commit_worldline_event("ARCHIVE_POSTERIOR_VALIDATED", 3, 4, {"archive_posterior": {"geometry_hash": self.geometry_hash, "v": 3}})

        # 2. Record a durable checkpoint at sequence 3
        checkpoints_dir = self.worldline._plot_dir(self.plot_id, self.tenant_id) / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        cp_file = checkpoints_dir / "checkpoint_seq3.json"
        now_str = datetime.now(timezone.utc).isoformat()
        cp_file.write_text(json.dumps({"checkpoint_id": "cp3", "sequence": 3, "timestamp": now_str}), encoding="utf-8")

        # 3. Adversarially roll back head.json to sequence 2 and delete event 3
        head_path = self.worldline._head_path(self.plot_id, self.tenant_id)
        head_data = json.loads(head_path.read_text(encoding="utf-8"))
        head_data["sequence"] = 2
        head_data["latest_event_id"] = e2["event_id"]
        head_path.write_text(json.dumps(head_data), encoding="utf-8")

        e3_path = self.worldline._event_path(self.plot_id, e3["event_id"], self.tenant_id)
        e3_path.unlink()

        # Both head sequence (2) and events count (2) agree, but checkpoint recorded sequence 3!
        # load_all_events MUST detect rollback and raise CorruptedWorldlineError
        with self.assertRaises(CorruptedWorldlineError) as ctx_err:
            self.worldline.load_all_events(self.plot_id, self.tenant_id, fail_on_corrupt=True)
        self.assertIn("rollback detected", str(ctx_err.exception).lower())

        # Test missing head while events exist fails closed
        head_path.unlink()
        with self.assertRaises(CorruptedWorldlineError) as ctx_missing:
            self.worldline.load_all_events(self.plot_id, self.tenant_id, fail_on_corrupt=True)
        self.assertIn("missing head watermark", str(ctx_missing.exception).lower())

    # =========================================================================
    # IR03-T19: Ancestor Observed Post-T or Derived Post-K BMA Rejected (IR03-V04)
    # =========================================================================
    def test_ir03_t19_ancestor_observed_post_T_or_derived_post_K_bma_rejected(self):
        """Ancestor observed after valid time T or with nested BMA derived after cutoff K is rejected."""
        # Scenario A: Ancestor observed at T+2 days (future observation leakage)
        # Parent observed at Day 12, committed Day 3
        parent_future = self._commit_worldline_event("OBSERVATION_RAW", 12, 3, {"raw": 99})
        # Child observed at Day 5, committed Day 4, referencing parent_future
        child_future = self._commit_worldline_event(
            "CROP_POSTERIOR", 5, 4, {"crop_posterior": {"stage": "leak_test"}}, parent_ids=[parent_future["event_id"]]
        )

        t_day10 = self.base_time + timedelta(days=10)
        k_day10 = self.base_time + timedelta(days=10)

        # Query at T=Day 10: Parent was observed at Day 12 > Day 10. Child MUST BE REJECTED.
        res_a = self.worldline.latest_eligible_payload(
            self.plot_id, "CROP_POSTERIOR", t_day10, k_day10, self.tenant_id, fail_on_corrupt=False
        )
        self.assertIsNone(res_a, "Derived child whose ancestor was observed after T must be rejected")

        # Scenario B: Ancestor observed Day 2, committed Day 3, but nested BMA was derived at Day 25 > K
        parent_bma = self._commit_worldline_event(
            "ARCHIVE_POSTERIOR_VALIDATED",
            2,
            3,
            {
                "archive_posterior": {"geometry_hash": self.geometry_hash},
                "bma_weights": {
                    "derived_at": (self.base_time + timedelta(days=25)).isoformat(),
                    "weights": [0.6, 0.4],
                },
            },
        )
        child_bma = self._commit_worldline_event(
            "CROP_POSTERIOR", 4, 5, {"crop_posterior": {"stage": "bma_dep_test"}}, parent_ids=[parent_bma["event_id"]]
        )

        # Query at K=Day 20: Parent BMA was derived at Day 25 > Day 20. Child MUST BE REJECTED.
        k_day20 = self.base_time + timedelta(days=20)
        res_b = self.worldline.latest_eligible_payload(
            self.plot_id, "CROP_POSTERIOR", t_day10, k_day20, self.tenant_id, fail_on_corrupt=False
        )
        self.assertIsNone(res_b, "Derived child whose ancestor carries BMA derived after K must be rejected")

        # Query at K=Day 30: All pre-conditions met (Parent BMA Day 25 <= Day 30). Child ADMITTED.
        k_day30 = self.base_time + timedelta(days=30)
        res_b_ok = self.worldline.latest_eligible_payload(
            self.plot_id, "CROP_POSTERIOR", t_day10, k_day30, self.tenant_id, fail_on_corrupt=False
        )
        self.assertIsNotNone(res_b_ok)

    # =========================================================================
    # IR03-T20: Replay Receipt Cold Read Recompute & Tamper Rejection (IR03-V06)
    # =========================================================================
    def test_ir03_t20_replay_receipt_cold_read_recompute_and_tamper_rejection(self):
        """Cold read recomputes receipt binding; deliberate tamper triggers quarantine."""
        from services.agribrain.layer05_asmae.plot_snapshot_store import (
            publish_canonical_plot_snapshot,
            load_latest_plot_snapshot,
            evaluate_snapshot_admission,
            SURFACES_SCHEMA_VERSION,
        )
        from services.agribrain.layer10_sire.surface_contract import RENDER_AUTHORIZATION_VERSION

        mock_replay_receipt = {
            "contract_version": "canonical_bitemporal_replay_receipt_v1",
            "replay_mode": "bitemporal_deterministic_v1",
            "evidence_set_digest": "sha256:d17e3f890b5ca7b649a21e428cf157bb674e2bda63914a1c5d98fa6a8b7c93e1",
            "observation_valid_time": "2026-09-08T12:00:00+00:00",
            "knowledge_cutoff_time": "2026-09-08T12:00:00+00:00",
        }

        snapshot_id = f"L10-coldtamper-{int(datetime.now(timezone.utc).timestamp()*1000)}"
        asmae_result = {
            "snapshot_id": snapshot_id,
            "content_hash": "sha256:cold_hash_123",
            "bitemporal_replay_receipt": mock_replay_receipt,
            "crop_posterior_lineage": "lineage-t20",
            "crop_worldline_event_id": "evt-crop-t20",
            "phenology_worldline_event_id": "evt-pheno-t20",
            "canRenderPixels": False,
        }
        frontend_payload = {
            "version": SURFACES_SCHEMA_VERSION,
            "surface_schema_version": SURFACES_SCHEMA_VERSION,
            "intelligence_snapshot_id": snapshot_id,
            "publication_id": f"pub-{snapshot_id}",
            "publication_run_id": f"run-{snapshot_id}",
            "run_id": f"run-{snapshot_id}",
            "pipeline_state": "terminal_layer10_published",
            "publication_status": "VALID_NORMAL",
            "declared_publication_status": "VALID_NORMAL",
            "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
            "render_authorizations": {"canopy": {"authorized": True}},
            "asmae_proof": {"proof_id": f"proof-{snapshot_id}", "status": "valid"},
            "mode_display_state": {"mode": "scientific"},
            "source_policy_display_state": {"policy": "standard"},
            "core_asmae_evidence_state": {"status": "nominal"},
            "publication_surface_state": {"status": "published"},
            "surfaces": [{
                "surface_id": "surface-canopy-vigor",
                "surface_type": "canopy_vigor",
                "content_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
            }],
            "evidence_cutoff_at": "2026-09-08T12:00:00+00:00",
            "scientific_evidence_lineage": {
                "crop_posterior_lineage": "lineage-t20",
                "crop_worldline_event_id": "evt-crop-t20",
                "phenology_worldline_event_id": "evt-pheno-t20",
            },
        }

        job_id = f"job-t20-{int(datetime.now(timezone.utc).timestamp()*1000)}"
        head = publish_canonical_plot_snapshot(
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            plot_id=self.plot_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend_payload,
            job_id=job_id,
            manifest_hash="manifest-t20",
            snapshot_kind="layer10_terminal",
        )

        # 1. Cold read with force_verify=True succeeds
        cold_snap = load_latest_plot_snapshot(
            self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            force_verify=True,
        )
        self.assertIsNotNone(cold_snap)
        self.assertTrue(cold_snap["validation"]["replayReceiptValid"])
        self.assertTrue(cold_snap["validation"]["bindingValid"])

        admission = evaluate_snapshot_admission(cold_snap)
        self.assertTrue(admission["is_valid"])

        # 2. Adversarially tamper with evidence_set_digest in node on disk
        node_file = Path(head["node_ref"])
        node_content = json.loads(node_file.read_text(encoding="utf-8"))
        node_content["bitemporal_replay_receipt"]["evidence_set_digest"] = "sha256:tampered_digest_deadbeef"
        node_file.write_text(json.dumps(node_content), encoding="utf-8")

        # Cold read with force_verify=True detects tamper
        tampered_snap = load_latest_plot_snapshot(
            self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            force_verify=True,
        )
        self.assertIsNotNone(tampered_snap)
        self.assertFalse(tampered_snap["validation"]["replayReceiptValid"])
        self.assertFalse(tampered_snap["validation"]["bindingValid"])

        # Admission predicate quarantines tampered snapshot
        tampered_admission = evaluate_snapshot_admission(tampered_snap)
        self.assertFalse(tampered_admission["is_valid"])
        self.assertEqual(tampered_admission["status"], "quarantined")
        self.assertIn("replayReceiptValid", tampered_admission["invalid_integrity_flags"])

    # =========================================================================
    # IR03-T21: Real Execution with Two K Cutoffs & Warm Cache Isolation (IR03-V05)
    # =========================================================================
    def test_ir03_t21_real_execution_two_k_cutoffs_warm_cache_isolation(self):
        """Real ASMAE runner executions with two different K cutoffs maintain strict cache isolation."""
        # Commit archive event valid Day 2, committed Day 3
        self._commit_worldline_event(
            "ARCHIVE_POSTERIOR_VALIDATED",
            2,
            3,
            {"archive_posterior": {"geometry_hash": self.geometry_hash, "val": 100}},
        )

        runner = ASMAERunner()
        t_req = (self.base_time + timedelta(days=10)).isoformat()
        k1_req = (self.base_time + timedelta(days=5)).isoformat()

        ctx_k1 = {
            "plot_id": self.plot_id,
            "tenant_id": self.tenant_id,
            "farm_id": self.farm_id,
            "geometry_hash": self.geometry_hash,
            "worldline_root": self.worldline_root,
            "observation_valid_time": t_req,
            "knowledge_cutoff_time": k1_req,
            "mode": "quick_visual",
            "execution_permissions": {"compute_allowed": True, "visual_authority_allowed": True, "diagnostic_allowed": True},
        }

        # Execution 1 at K1 (Day 5)
        res_k1 = runner.execute(self.plot_id, "run-t21-k1", ctx_k1, mode="quick_visual")
        receipt_k1 = res_k1.get("bitemporal_replay_receipt")
        digest_k1 = receipt_k1["evidence_set_digest"]

        # Commit backfill event valid Day 4, committed Day 15
        self._commit_worldline_event(
            "ARCHIVE_POSTERIOR_VALIDATED",
            4,
            15,
            {"archive_posterior": {"geometry_hash": self.geometry_hash, "val": 200}},
        )

        # Execution 2 at K2 (Day 20)
        k2_req = (self.base_time + timedelta(days=20)).isoformat()
        ctx_k2 = dict(ctx_k1)
        ctx_k2["knowledge_cutoff_time"] = k2_req
        res_k2 = runner.execute(self.plot_id, "run-t21-k2", ctx_k2, mode="quick_visual")
        receipt_k2 = res_k2.get("bitemporal_replay_receipt")
        digest_k2 = receipt_k2["evidence_set_digest"]

        # K1 and K2 digests MUST be different because K2 includes backfilled event
        self.assertNotEqual(digest_k1, digest_k2)

        # Re-execution at K1 (warm cache scenario) MUST return original digest_k1
        res_k1_repeat = runner.execute(self.plot_id, "run-t21-k1-repeat", ctx_k1, mode="quick_visual")
        receipt_k1_repeat = res_k1_repeat.get("bitemporal_replay_receipt")
        self.assertEqual(receipt_k1_repeat["evidence_set_digest"], digest_k1)


if __name__ == "__main__":
    unittest.main()
