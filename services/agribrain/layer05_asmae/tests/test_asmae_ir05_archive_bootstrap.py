"""Unit and Integration Tests for ASMAE IR-05 Resumable Archive Bootstrap.

Verifies:
  1. Multi-window partitioned execution from mission start (2015).
  2. Durable checkpoint persistence and cursor resumption after interruption.
  3. Strict chronological DAG lineage chaining (parent_event_ids).
  4. Idempotency on completed runs without duplicate worldline events.
  5. Dual-clock bitemporal replay queries against bootstrapped historical evidence.
  6. Graceful failure recording and state preservation.
"""

import json
import hashlib
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from services.agribrain.layer05_asmae.history.archive_bootstrap_service import (
    ArchiveBootstrapService,
    BootstrapCheckpoint,
    MISSION_START_DATE,
)
from services.agribrain.world_model.canonical_worldline import (
    CanonicalWorldlineService,
    _parse_utc_iso,
)


class ASMAEIR05ArchiveBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.worldline_root = Path(self.temp_dir) / "worldline"
        self.bootstrap_root = Path(self.temp_dir) / "bootstrap_checkpoints"

        self.worldline = CanonicalWorldlineService(root=self.worldline_root)
        self.plot_id = "test_plot_mitidja_01"
        self.tenant_id = "tenant_test"
        self.namespace = "default"
        self.geometry_hash = "a" * 64

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _mock_fetcher(self, win_start: str, win_end: str) -> List[Dict[str, Any]]:
        """Synthesize 2 realistic historical scenes per window."""
        dt_start = _parse_utc_iso(win_start)
        scenes = []
        for i in [30, 90]:
            acq_dt = dt_start + timedelta(days=i)
            if acq_dt >= _parse_utc_iso(win_end):
                continue
            acq_iso = acq_dt.isoformat()
            scenes.append({
                "scene_id": f"S2A_MSIL2A_{acq_dt.strftime('%Y%m%d')}_T31SUD",
                "acquisition_time": acq_iso,
                "source": "sentinel2",
                "product_level": "L2A",
                "cloud_score": 12.5,
                "quality_score": 0.92,
                "source_content_hash": hashlib.sha256(acq_iso.encode("utf-8")).hexdigest(),
                "valid_pixel_fraction": 0.98,
                "resolution_m": 10.0,
                "metrics": {"ndvi_mean": 0.54, "ndre_mean": 0.38},
            })
        return scenes

    def test_ir05_t01_full_multi_window_bootstrap_chronological_chain(self):
        """Full bootstrap across 2 years builds an unbroken parent DAG chain."""
        service = ArchiveBootstrapService(
            worldline=self.worldline,
            bootstrap_root=self.bootstrap_root,
            fetcher_factory=self._mock_fetcher,
        )

        end_date = "2017-06-23T00:00:00+00:00"  # 2 years
        res = service.run_bootstrap(
            plot_id=self.plot_id,
            geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id,
            namespace=self.namespace,
            start_date=MISSION_START_DATE,
            target_end_date=end_date,
            window_days=180,
        )

        self.assertEqual(res["status"], "COMPLETED")
        win_count = res["completed_windows_count"]
        self.assertEqual(win_count, 5)
        # 5 windows * 2 scenes = 10 events
        self.assertEqual(res["total_events_committed"], 8)
        self.assertEqual(res["total_scenes_discovered"], 8)

        # Inspect canonical worldline events
        events = self.worldline.load_all_events(
            self.plot_id, self.tenant_id, self.namespace
        )
        self.assertEqual(len(events), 8)

        # Verify strict sequence numbering and unbroken parent chaining
        for i, ev in enumerate(events):
            self.assertEqual(ev["sequence"], i + 1)
            self.assertEqual(ev["event_type"], "ARCHIVE_SCENE_INGESTED")
            if i == 0:
                self.assertEqual(ev.get("parent_event_ids"), [])
            else:
                prev_id = events[i - 1]["event_id"]
                self.assertEqual(ev.get("parent_event_ids"), [prev_id])

            # Verify observation times are strictly increasing
            if i > 0:
                t_prev = _parse_utc_iso(events[i - 1]["observation_or_valid_time"])
                t_curr = _parse_utc_iso(ev["observation_or_valid_time"])
                self.assertGreater(t_curr, t_prev)

    def test_ir05_t02_resumption_from_interrupted_cursor(self):
        """Service resumes from cursor checkpoint after simulated interruption."""
        service = ArchiveBootstrapService(
            worldline=self.worldline,
            bootstrap_root=self.bootstrap_root,
            fetcher_factory=self._mock_fetcher,
        )

        end_date = "2017-06-23T00:00:00+00:00"

        # 1. First run halts after 2 windows (interruption)
        res1 = service.run_bootstrap(
            plot_id=self.plot_id,
            geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id,
            namespace=self.namespace,
            start_date=MISSION_START_DATE,
            target_end_date=end_date,
            window_days=180,
            max_windows=2,
        )

        self.assertEqual(res1["status"], "IN_PROGRESS")
        self.assertEqual(res1["completed_windows_count"], 2)
        self.assertEqual(res1["total_events_committed"], 4)

        # Checkpoint is written to disk
        cp = service.load_checkpoint(self.plot_id, self.tenant_id, self.namespace)
        self.assertIsNotNone(cp)
        self.assertEqual(cp.status, "IN_PROGRESS")
        self.assertEqual(len(cp.completed_windows), 2)

        # 2. Second run resumes and finishes the remaining windows
        res2 = service.run_bootstrap(
            plot_id=self.plot_id,
            geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id,
            namespace=self.namespace,
            start_date=MISSION_START_DATE,
            target_end_date=end_date,
            window_days=180,
        )

        self.assertEqual(res2["status"], "COMPLETED")
        self.assertTrue(res2["resumed"])
        self.assertEqual(res2["completed_windows_count"], 5)
        self.assertEqual(res2["total_events_committed"], 8)

        events = self.worldline.load_all_events(
            self.plot_id, self.tenant_id, self.namespace
        )
        self.assertEqual(len(events), 8)

    def test_ir05_t03_idempotent_reexecution_when_completed(self):
        """Re-running an already completed bootstrap produces zero duplicate events."""
        service = ArchiveBootstrapService(
            worldline=self.worldline,
            bootstrap_root=self.bootstrap_root,
            fetcher_factory=self._mock_fetcher,
        )

        end_date = "2016-06-23T00:00:00+00:00"
        res1 = service.run_bootstrap(
            plot_id=self.plot_id,
            geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id,
            namespace=self.namespace,
            start_date=MISSION_START_DATE,
            target_end_date=end_date,
            window_days=180,
        )
        self.assertEqual(res1["status"], "COMPLETED")
        total_committed = res1["total_events_committed"]
        self.assertEqual(total_committed, 4)

        # Re-run immediately
        res2 = service.run_bootstrap(
            plot_id=self.plot_id,
            geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id,
            namespace=self.namespace,
            start_date=MISSION_START_DATE,
            target_end_date=end_date,
            window_days=180,
        )
        self.assertEqual(res2["status"], "COMPLETED")
        self.assertTrue(res2.get("already_completed"))

        events = self.worldline.load_all_events(
            self.plot_id, self.tenant_id, self.namespace
        )
        self.assertEqual(len(events), total_committed, "Worldline must preserve deduplicated scene inventory")

    def test_ir05_t04_bitemporal_replay_query_against_bootstrapped_history(self):
        """Bitemporal selector correctly filters historical observations by T and K."""
        service = ArchiveBootstrapService(
            worldline=self.worldline,
            bootstrap_root=self.bootstrap_root,
            fetcher_factory=self._mock_fetcher,
        )

        end_date = "2017-06-23T00:00:00+00:00"
        service.run_bootstrap(
            plot_id=self.plot_id,
            geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id,
            namespace=self.namespace,
            start_date=MISSION_START_DATE,
            target_end_date=end_date,
            window_days=180,
        )

        now_iso = datetime.now(timezone.utc).isoformat()

        # Replay at T = 2016-01-01 (should only see events from window 1)
        t_early = "2016-01-01T00:00:00+00:00"
        eligible_early = self.worldline.select_eligible_events(
            plot_id=self.plot_id,
            event_type="ARCHIVE_SCENE_INGESTED",
            valid_time_T=t_early,
            knowledge_cutoff_K=now_iso,
            tenant_id=self.tenant_id,
            namespace=self.namespace,
        )
        self.assertGreater(len(eligible_early), 0)
        self.assertLess(len(eligible_early), 8)
        for ev in eligible_early:
            obs_dt = _parse_utc_iso(ev["observation_or_valid_time"])
            self.assertLessEqual(obs_dt, _parse_utc_iso(t_early))

        # Replay before mission start should yield 0 events
        t_pre = "2014-01-01T00:00:00+00:00"
        eligible_pre = self.worldline.select_eligible_events(
            plot_id=self.plot_id,
            event_type="ARCHIVE_SCENE_INGESTED",
            valid_time_T=t_pre,
            knowledge_cutoff_K=now_iso,
            tenant_id=self.tenant_id,
            namespace=self.namespace,
        )
        self.assertEqual(len(eligible_pre), 0)

    def test_ir05_t05_failure_and_checkpoint_preservation(self):
        """Simulated network failure updates checkpoint to FAILED and preserves progress."""
        fail_window_idx = 1
        call_count = [0]

        def flaky_fetcher(win_start: str, win_end: str):
            call_count[0] += 1
            if call_count[0] > fail_window_idx:
                raise ConnectionError("CDSE STAC endpoint timeout")
            return self._mock_fetcher(win_start, win_end)

        service = ArchiveBootstrapService(
            worldline=self.worldline,
            bootstrap_root=self.bootstrap_root,
            fetcher_factory=flaky_fetcher,
        )

        end_date = "2017-06-23T00:00:00+00:00"
        with self.assertRaises(ConnectionError):
            service.run_bootstrap(
                plot_id=self.plot_id,
                geometry_hash=self.geometry_hash,
                tenant_id=self.tenant_id,
                namespace=self.namespace,
                start_date=MISSION_START_DATE,
                target_end_date=end_date,
                window_days=180,
                fail_fast=True,
            )

        # Checkpoint is marked FAILED and preserves window 0
        cp = service.load_checkpoint(self.plot_id, self.tenant_id, self.namespace)
        self.assertEqual(cp.status, "FAILED")
        self.assertIn("timeout", cp.error_message)
        self.assertEqual(len(cp.completed_windows), 1)
        self.assertEqual(cp.total_events_committed, 2)


    def test_ir05_t06_missing_real_archive_provider_never_completes(self):
        service = ArchiveBootstrapService(worldline=self.worldline, bootstrap_root=self.bootstrap_root)
        with self.assertRaisesRegex(RuntimeError, "archive_provider_not_configured"):
            service.run_bootstrap(
                plot_id=self.plot_id, geometry_hash=self.geometry_hash,
                tenant_id=self.tenant_id, namespace=self.namespace,
                target_end_date="2015-12-23T00:00:00Z",
            )
        checkpoint = service.load_checkpoint(self.plot_id, self.tenant_id, self.namespace)
        self.assertEqual(checkpoint.status, "FAILED")
        self.assertEqual(checkpoint.total_events_committed, 0)

    def test_ir05_t07_checkpoint_corruption_must_not_restart_as_new(self):
        service = ArchiveBootstrapService(
            worldline=self.worldline, bootstrap_root=self.bootstrap_root,
            fetcher_factory=self._mock_fetcher,
        )
        path = service._checkpoint_path(self.plot_id, self.tenant_id, self.namespace)
        path.write_text("{bad_json", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "corrupt_archive_bootstrap_checkpoint"):
            service.run_bootstrap(
                plot_id=self.plot_id, geometry_hash=self.geometry_hash,
                tenant_id=self.tenant_id, namespace=self.namespace,
                target_end_date="2015-12-23T00:00:00Z",
            )
        self.assertEqual(path.read_text(encoding="utf-8"), "{bad_json")

    def test_ir05_t08_checkpoint_namespace_traversal_rejected(self):
        service = ArchiveBootstrapService(worldline=self.worldline, bootstrap_root=self.bootstrap_root)
        with self.assertRaisesRegex(ValueError, "invalid_archive_checkpoint_tenant_id"):
            service.load_checkpoint(self.plot_id, "../foreign", self.namespace)
        with self.assertRaisesRegex(ValueError, "invalid_archive_checkpoint_plot_id"):
            service.load_checkpoint("../plot", self.tenant_id, self.namespace)

    def test_ir05_t09_changed_geometry_cannot_reuse_prior_checkpoint(self):
        service = ArchiveBootstrapService(
            worldline=self.worldline, bootstrap_root=self.bootstrap_root,
            fetcher_factory=self._mock_fetcher,
        )
        args = dict(
            plot_id=self.plot_id, geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id, namespace=self.namespace,
            target_end_date="2015-12-23T00:00:00Z",
        )
        service.run_bootstrap(**args)
        with self.assertRaisesRegex(RuntimeError, "archive_checkpoint_identity_or_version_mismatch"):
            service.run_bootstrap(**dict(args, geometry_hash="b" * 64))

    def test_ir05_t10_scene_beyond_window_must_fail_closed(self):
        def malicious_fetcher(start, end):
            scene = self._mock_fetcher(start, end)[0]
            scene["acquisition_time"] = "2099-01-01T00:00:00Z"
            return [scene]
        service = ArchiveBootstrapService(
            worldline=self.worldline, bootstrap_root=self.bootstrap_root,
            fetcher_factory=malicious_fetcher,
        )
        with self.assertRaisesRegex(RuntimeError, "scene_outside_queried_archive_window"):
            service.run_bootstrap(
                plot_id=self.plot_id, geometry_hash=self.geometry_hash,
                tenant_id=self.tenant_id, namespace=self.namespace,
                target_end_date="2015-12-23T00:00:00Z",
            )
        self.assertEqual(
            self.worldline.load_all_events(self.plot_id, self.tenant_id, self.namespace), []
        )

    def test_ir05_t11_crash_after_commit_does_not_duplicate_inventory(self):
        service = ArchiveBootstrapService(
            worldline=self.worldline, bootstrap_root=self.bootstrap_root,
            fetcher_factory=self._mock_fetcher,
        )
        original = service._commit_scene_to_worldline
        count = [0]
        def crash_once(*args, **kwargs):
            event_id = original(*args, **kwargs)
            count[0] += 1
            if count[0] == 1:
                raise RuntimeError("simulated_postcommit_crash")
            return event_id
        service._commit_scene_to_worldline = crash_once
        args = dict(
            plot_id=self.plot_id, geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id, namespace=self.namespace,
            target_end_date="2015-12-23T00:00:00Z",
        )
        with self.assertRaisesRegex(RuntimeError, "simulated_postcommit_crash"):
            service.run_bootstrap(**args)
        events = self.worldline.load_all_events(self.plot_id, self.tenant_id, self.namespace)
        self.assertEqual(len(events), 1)
        service._commit_scene_to_worldline = original
        result = service.run_bootstrap(**args)
        self.assertEqual(result["status"], "COMPLETED")
        events = self.worldline.load_all_events(self.plot_id, self.tenant_id, self.namespace)
        self.assertEqual(len(events), 2)
        self.assertTrue(all(event["event_type"] == "ARCHIVE_SCENE_INGESTED" for event in events))
        self.assertTrue(all(
            event["payload"]["archive_scene"]["posterior_validated"] is False
            for event in events
        ))

    def test_ir05_t12_scene_revision_requires_selective_replay(self):
        service = ArchiveBootstrapService(
            worldline=self.worldline, bootstrap_root=self.bootstrap_root,
            fetcher_factory=self._mock_fetcher,
        )
        args = dict(
            plot_id=self.plot_id, geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id, namespace=self.namespace,
            target_end_date="2015-12-23T00:00:00Z",
        )
        service.run_bootstrap(**args)
        def revised(start, end):
            scenes = self._mock_fetcher(start, end)
            scenes[0]["source_content_hash"] = "d" * 64
            return scenes
        service._fetcher_factory = revised
        # Expanding the archive forces a new window; a repeated earlier window
        # is explicitly checked below using the uncommitted-window replay path.
        cp = service.load_checkpoint(self.plot_id, self.tenant_id, self.namespace)
        cp.current_cursor = MISSION_START_DATE
        cp.status = "FAILED"
        service.save_checkpoint(cp)
        with self.assertRaisesRegex(RuntimeError, "archive_scene_revision_requires_selective_replay"):
            service.run_bootstrap(**args)


    def test_ir05_t13_completed_checkpoint_requires_cold_journal(self):
        service = ArchiveBootstrapService(
            worldline=self.worldline, bootstrap_root=self.bootstrap_root,
            fetcher_factory=self._mock_fetcher,
        )
        args = dict(
            plot_id=self.plot_id, geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id, namespace=self.namespace,
            target_end_date="2015-12-23T00:00:00Z",
        )
        service.run_bootstrap(**args)
        events = self.worldline.load_all_events(self.plot_id, self.tenant_id, self.namespace)
        self.worldline._event_path(
            self.plot_id, events[-1]["event_id"], self.tenant_id, self.namespace,
        ).unlink()
        with self.assertRaises(Exception):
            service.run_bootstrap(**args)

    def test_ir05_t14_no_fake_posterior_created_by_inventory_only(self):
        service = ArchiveBootstrapService(
            worldline=self.worldline, bootstrap_root=self.bootstrap_root,
            fetcher_factory=self._mock_fetcher,
        )
        service.run_bootstrap(
            plot_id=self.plot_id, geometry_hash=self.geometry_hash,
            tenant_id=self.tenant_id, namespace=self.namespace,
            target_end_date="2015-12-23T00:00:00Z",
        )
        self.assertFalse(self.worldline.latest_payload(
            self.plot_id, "ARCHIVE_POSTERIOR_VALIDATED",
            self.tenant_id, self.namespace,
        ))


if __name__ == "__main__":
    unittest.main()
