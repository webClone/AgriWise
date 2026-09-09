"""Unit & Integration tests for Layer 1 21-step Fusion Pipeline."""

from datetime import datetime, timezone
import pytest

from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
from services.agribrain.layer1_fusion.schemas import (
    Layer1InputBundle,
    Layer1ContextPackage,
    FORBIDDEN_DIAGNOSIS_TERMS,
)


def test_fusion_pipeline_minimal_bundle():
    """Verify Layer1FusionEngine executes 21-step pipeline on minimal bundle."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    bundle = Layer1InputBundle(
        plot_id="plot_fusion_test",
        run_id="run_fusion_001",
        run_timestamp=now,
        window_start=datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
        window_end=now,
    )

    engine = Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    assert isinstance(pkg, Layer1ContextPackage)
    assert pkg.plot_id == "plot_fusion_test"
    assert pkg.run_id == "run_fusion_001"
    assert pkg.generated_at is not None
    assert pkg.content_hash() != ""
    assert pkg.provenance is not None
    assert pkg.diagnostics is not None

    # Verify hard prohibition results are computed
    prohibitions = pkg.diagnostics.hard_prohibition_results
    assert len(prohibitions) > 0


def test_fusion_pipeline_missing_required_ids_raise():
    """Verify Layer1FusionEngine raises ValueError if plot_id or run_id is missing."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    engine = Layer1FusionEngine()

    with pytest.raises(ValueError, match="plot_id is required"):
        engine.fuse(Layer1InputBundle(
            plot_id="",
            run_id="run_1",
            run_timestamp=now,
            window_start=now,
            window_end=now,
        ))

    with pytest.raises(ValueError, match="run_id is required"):
        engine.fuse(Layer1InputBundle(
            plot_id="plot_1",
            run_id="",
            run_timestamp=now,
            window_start=now,
            window_end=now,
        ))


def test_fusion_pipeline_determinism():
    """Verify Layer1FusionEngine produces identical content_hash on repeated execution."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    bundle = Layer1InputBundle(
        plot_id="plot_det_01",
        run_id="run_det_001",
        run_timestamp=now,
        window_start=datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
        window_end=now,
    )

    engine = Layer1FusionEngine()
    pkg1 = engine.fuse(bundle)
    pkg2 = engine.fuse(bundle)

    assert pkg1.content_hash() == pkg2.content_hash()


def test_no_forbidden_diagnostic_vocabulary_emitted():
    """Verify no forbidden agronomic diagnostic vocabulary appears in fused features."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    bundle = Layer1InputBundle(
        plot_id="plot_vocab_01",
        run_id="run_vocab_001",
        run_timestamp=now,
        window_start=datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
        window_end=now,
    )

    engine = Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    # Walk all fused feature names across 7 groups and check forbidden vocabulary
    groups = [
        pkg.fused_features.water_context,
        pkg.fused_features.vegetation_context,
        pkg.fused_features.phenology_context,
        pkg.fused_features.stress_evidence_context,
        pkg.fused_features.soil_site_context,
        pkg.fused_features.operational_context,
        pkg.fused_features.data_quality_context,
    ]
    all_features = [f for grp in groups for f in grp]
    for feat in all_features:
        name_lower = feat.name.lower()
        for forbidden in FORBIDDEN_DIAGNOSIS_TERMS:
            assert forbidden not in name_lower, f"Forbidden diagnostic term '{forbidden}' found in feature {feat.name}"
