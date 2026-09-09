"""Unit tests for Layer 1 Legacy FieldTensor Compatibility Bridge."""

from datetime import datetime, timezone
import pytest

from services.agribrain.layer1_fusion.engine import Layer1FusionEngine
from services.agribrain.layer1_fusion.schemas import Layer1InputBundle
from services.agribrain.layer1_fusion.outputs.legacy_compat import build_legacy_fieldtensor
from services.agribrain.layer1_fusion.schema import FieldTensor


def test_build_legacy_fieldtensor_from_context_package():
    """Verify build_legacy_fieldtensor constructs compliant FieldTensor for downstream L2-L10 consumers."""
    now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
    bundle = Layer1InputBundle(
        plot_id="plot_compat_test",
        run_id="run_compat_001",
        run_timestamp=now,
        window_start=datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
        window_end=now,
    )

    engine = Layer1FusionEngine()
    pkg = engine.fuse(bundle)

    field_tensor = build_legacy_fieldtensor(pkg)

    assert field_tensor is not None
    assert field_tensor.plot_id == "plot_compat_test"
    assert field_tensor.run_id == "run_compat_001"
    assert field_tensor.version == "2.0.0-v1bridge"
    assert hasattr(field_tensor, "plot_timeseries")
    assert isinstance(field_tensor.plot_timeseries, list)
    assert len(field_tensor.plot_timeseries) == 10  # 10 days in window
    assert hasattr(field_tensor, "channels")
    assert hasattr(field_tensor, "provenance")
    assert field_tensor.provenance.get("engine_version") == "layer1_fusion_v1"
