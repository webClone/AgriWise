"""Unit tests for the read-only scientific-pilot baseline receipt parser.

These are deterministic fixtures. They do NOT constitute a Plot A runtime run.
Run from repository root:
  python -m unittest discover -s services/agribrain/tests -p 'test_scientific_pilot_baseline_probe.py'
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "pilot_scientific_fail_closed_probe.py"
)
SPEC = importlib.util.spec_from_file_location("pilot_scientific_fail_closed_probe", MODULE_PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)

PLOT = probe.PLOT_ID
SNAPSHOT = probe.SNAPSHOT_ID
DUMMY_HASH = "a" * 64
CUTOFF = "2026-10-30T17:44:46+00:00"


def snapshot():
    return {
        "available": True,
        "plot_id": PLOT,
        "snapshot_id": SNAPSHOT,
        "canonical_publication_receipt_hash": DUMMY_HASH,
        "evidence_cutoff_at": CUTOFF,
        "validation": {key: True for key in probe.VALIDATION_FLAGS},
    }


def run(status="BLOCKED", recommendations=None, envelope_hash=None):
    return {
        "run_id": "fixture-run-001", "plot_id": PLOT,
        "audit": {"prescription_authorization": {
            "status": status,
            "reason": "L8 authorization envelope is missing",
            "envelope_hash": envelope_hash,
        }},
        "recommendations": [] if recommendations is None else recommendations,
    }


class PilotBaselineReceiptTests(unittest.TestCase):
    def test_valid_snapshot_server_validation_flags(self):
        result = probe.inspect_snapshot(snapshot(), PLOT, SNAPSHOT, 200)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["checks"]["validation_10_of_10"])

    def test_foreign_plot_and_corrupt_receipt_fail(self):
        x = snapshot()
        x["plot_id"] = "different-plot"
        self.assertEqual(probe.inspect_snapshot(x, PLOT, SNAPSHOT)["status"], "FAIL")
        x = snapshot()
        x["canonical_publication_receipt_hash"] = "placeholder"
        self.assertEqual(probe.inspect_snapshot(x, PLOT, SNAPSHOT)["status"], "FAIL")

    def test_invalid_validation_flag_fails(self):
        x = snapshot()
        x["validation"]["receiptValid"] = False
        self.assertEqual(probe.inspect_snapshot(x, PLOT, SNAPSHOT)["status"], "FAIL")

    def test_blocked_run_without_actions_passes_fail_closed(self):
        result = probe.inspect_run({"data": run()}, PLOT)
        self.assertEqual(result["status"], "PASS_FAIL_CLOSED")
        self.assertEqual(result["recommendation_count"], 0)

    def test_blocked_run_with_action_is_inconclusive_not_pass(self):
        result = probe.inspect_run(run(recommendations=[{"action": "IRRIGATE"}]), PLOT)
        self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_authorized_run_is_not_negative_baseline(self):
        result = probe.inspect_run(run(
            status="AUTHORIZED",
            recommendations=[{"action": "IRRIGATE"}],
            envelope_hash=DUMMY_HASH,
        ), PLOT)
        self.assertEqual(result["status"], "NOT_FAIL_CLOSED")

    def test_unscoped_or_unidentified_run_is_invalid(self):
        x = run()
        x["plot_id"] = "other-plot"
        self.assertEqual(probe.inspect_run(x, PLOT)["status"], "INVALID")
        x = run()
        x["run_id"] = ""
        self.assertEqual(probe.inspect_run(x, PLOT)["status"], "INVALID")

    def test_observation_only_guard_disallows_signed_irrigation(self):
        from unittest.mock import patch as env_patch
        from types import SimpleNamespace
        args = SimpleNamespace(
            plot_id=PLOT, snapshot_id=SNAPSHOT,
            self_test=True, snapshot_json=None,
            live_snapshot=True, run_json=None, origin="http://localhost:3000",
        )
        with env_patch.dict(
            "os.environ",
            {"AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION": "true"},
        ):
            result = probe.run_probe(args)
        self.assertEqual(result["gate_status"], "FAIL_SIGNED_IRRIGATION_NOT_DISABLED")
        self.assertEqual(result["observation_only_runtime"]["status"], "FAIL")
        self.assertEqual(result["snapshot"]["status"], "NOT_RUN")
        self.assertEqual(result["source_boundary"]["status"], "NOT_RUN")

    def test_observation_only_guard_allows_explicit_disabled(self):
        from unittest.mock import patch as env_patch
        with env_patch.dict(
            "os.environ",
            {"AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION": "false"},
        ):
            result = probe.inspect_observation_only_runtime()
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["other_processes_verified"])

    def test_no_provider_clock_cannot_be_substituted_for_cutoff(self):
        x = snapshot()
        x["evidence_cutoff_at"] = None
        self.assertEqual(probe.inspect_snapshot(x, PLOT, SNAPSHOT)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
