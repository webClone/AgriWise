from __future__ import annotations

from services.agribrain.layer05_asmae.runner import ASMAERunner


def test_quick_visual_crop_binding_failure_keeps_typed_failure_code(monkeypatch):
    runner = ASMAERunner({"disable_job_recovery": True})
    monkeypatch.setattr(
        runner,
        "execution_permissions",
        lambda _plot_id: {
            "compute_allowed": True,
            "diagnostic_allowed": True,
            "advisory_allowed": True,
            "plot_state_publication_allowed": True,
            "production_authority_allowed": False,
            "visual_authority_allowed": True,
            "training_export_allowed": False,
        },
    )

    def reject_input(*_args, **_kwargs):
        raise ValueError(
            "Crop influence manifest independent evidence does not match ledger"
        )

    monkeypatch.setattr(runner, "_build_input", reject_input)
    result = runner.execute(
        "plot-1",
        "run-1",
        {
            "tenant_id": "tenant-1",
            "farm_id": "farm-1",
            "plot_id": "plot-1",
            "plot_namespace": {
                "tenant_id": "tenant-1",
                "farm_id": "farm-1",
                "plot_id": "plot-1",
            },
            "layer0_source_packages": {},
        },
        mode="quick_visual",
    )

    assert result["status"] == "error"
    assert result["failure_code"] == (
        "CROP_EVIDENCE_LEDGER_MANIFEST_MISMATCH"
    )
    assert result["error_type"] == "ValueError"
    assert result["reason"].startswith("quick_visual_state_hydration_failed:")
