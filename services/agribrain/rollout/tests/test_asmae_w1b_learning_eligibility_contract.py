"""W1-B RED regression tests: human approval never substitutes scientific eligibility.

Spec-only branch. These tests are intentionally expected to fail on the
unremediated W1-A base; they are NOT evidence that implementation is qualified.
"""
import importlib
import json

import pytest

from rollout import validation_ledger as ledger


def _seed_view(tmp_path, run_id="run-w1b"):
    path = tmp_path / "run_validation.jsonl"
    path.write_text(json.dumps({
        "record_type": "asmae_run",
        "run_id": run_id,
        "plot_id": "plot-w1b",
        "execution_status": "executed",
        "geometry_hash": "a" * 64,
        "layer0_output_hash": "b" * 64,
        "asmae_content_hash": "c" * 64,
        "asmae_artifact_instance_hash": "d" * 64,
        "validation": {"manual_validation_status": "pending"},
        "training_use": {"eligible_for_asmae_learn": False},
        "eligible_for_asmae_learn": False,
    }) + "\n", encoding="utf-8")
    return path


def _candidate(eligible):
    return {
        "candidate_id": "cand_run-w1b",
        "candidate_type": "validated_state_candidate",
        "eligible": eligible,
        "blocked_reasons": [] if eligible else ["retrovalidation_failed"],
        "validation_event_ids": ["evidence-1"] if eligible else [],
        "disagreement_report_hash": "h" * 64 if eligible else "",
        "evidence_count": 1 if eligible else 0,
        "validation_trust_score": 0.8 if eligible else 0.2,
        "agreement_score": 0.9 if eligible else 0.1,
        "bma_status": "success" if eligible else "blocked",
        "retro_status": "success_with_holdouts" if eligible else "missing",
        "retro_score": 0.83 if eligible else None,
        "uncertainty": 0.20 if eligible else None,
    }


def _last_record(path):
    return json.loads(path.read_text(encoding="utf-8").splitlines()[-1])


def _patch_builder(monkeypatch, implementation):
    builder = importlib.import_module("asmae_learn.candidate_builder")
    monkeypatch.setattr(builder, "build_learning_candidate", implementation)


def test_w1b_builder_failure_cannot_be_promoted_by_manual_approval(monkeypatch, tmp_path):
    monkeypatch.setenv("AGRIWISE_ARCHIVE_PILOT_MODE", "false")
    path = _seed_view(tmp_path)
    def failed_builder(_):
        raise RuntimeError("missing trusted lineage")
    _patch_builder(monkeypatch, failed_builder)
    assert ledger.promote_ledger_run_validation(
        "run-w1b", "approved", ledger_path=path
    ) is True  # preserve manual feedback as a recorded event
    rec = _last_record(path)
    assert rec["eligible_for_asmae_learn"] is False
    assert rec["candidate"]["eligible"] is False
    assert rec["candidate"]["validation_trust_score"] != 1.0
    assert rec["candidate"]["agreement_score"] != 1.0
    assert rec["candidate"]["blocked_reasons"]


def test_w1b_builder_returning_ineligible_wins_over_approval(monkeypatch, tmp_path):
    monkeypatch.setenv("AGRIWISE_ARCHIVE_PILOT_MODE", "false")
    path = _seed_view(tmp_path)
    _patch_builder(monkeypatch, lambda view: _candidate(False))
    assert ledger.promote_ledger_run_validation(
        "run-w1b", "approved", ledger_path=path
    ) is True
    rec = _last_record(path)
    assert rec["eligible_for_asmae_learn"] is False
    assert rec["candidate"]["eligible"] is False
    assert "retrovalidation_failed" in rec["candidate"]["blocked_reasons"]


def test_w1b_manual_rejection_overrides_positive_builder(monkeypatch, tmp_path):
    monkeypatch.setenv("AGRIWISE_ARCHIVE_PILOT_MODE", "false")
    path = _seed_view(tmp_path)
    _patch_builder(monkeypatch, lambda view: _candidate(True))
    assert ledger.promote_ledger_run_validation(
        "run-w1b", "rejected", ledger_path=path
    ) is True
    rec = _last_record(path)
    assert rec["eligible_for_asmae_learn"] is False


def test_w1b_success_requires_both_positive_builder_and_approval(monkeypatch, tmp_path):
    monkeypatch.setenv("AGRIWISE_ARCHIVE_PILOT_MODE", "false")
    path = _seed_view(tmp_path)
    _patch_builder(monkeypatch, lambda view: _candidate(True))
    assert ledger.promote_ledger_run_validation(
        "run-w1b", "approved", ledger_path=path
    ) is True
    rec = _last_record(path)
    assert rec["eligible_for_asmae_learn"] is True
    assert rec["candidate"]["eligible"] is True
    assert rec["candidate"]["validation_trust_score"] == 0.8


def test_w1b_approval_in_initial_run_record_is_not_learning_authority(monkeypatch, tmp_path):
    monkeypatch.setenv("AGRIWISE_ARCHIVE_PILOT_MODE", "false")
    path = tmp_path / "run_validation.jsonl"
    run = ledger.record_asmae_run({
        "run_id": "run-initial-approved",
        "plot_id": "plot-w1b",
        "geometry_hash": "a" * 64,
        "layer0_output_hash": "b" * 64,
        "asmae_content_hash": "c" * 64,
        "asmae_artifact_instance_hash": "d" * 64,
        "execution_status": "executed",
        "validation": {"manual_validation_status": "approved"},
    }, ledger_path=path)
    assert run["validation"]["manual_validation_status"] == "approved"
    assert run["eligible_for_asmae_learn"] is False
    assert run["training_use"]["eligible_for_asmae_learn"] is False
