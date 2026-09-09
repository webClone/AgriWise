"""Unit tests for Layer 1 Context Invariants."""

import math
import pytest

from services.agribrain.layer1_fusion.schemas import EvidenceItem
from services.agribrain.layer1_fusion.context_invariants import (
    check_no_nan_inf,
    check_value_bounds,
)


def test_check_no_nan_inf_auto_fix():
    """Verify check_no_nan_inf intercepts NaN and Inf values and sets to None when auto_fix is True."""
    nan_item = EvidenceItem(
        evidence_id="ev_nan",
        plot_id="p1",
        variable="ndvi",
        value=float("nan"),
        source_family="sentinel2",
        source_id="s2",
        observation_type="derived_feature",
        spatial_scope="plot",
    )
    inf_item = EvidenceItem(
        evidence_id="ev_inf",
        plot_id="p1",
        variable="soil_moisture_vwc",
        value=float("inf"),
        source_family="sensor",
        source_id="probe1",
        observation_type="measurement",
        spatial_scope="point",
    )

    violations = check_no_nan_inf([nan_item, inf_item], auto_fix=True)
    assert len(violations) == 2
    assert all(v.auto_fixed for v in violations)
    assert nan_item.value is None
    assert inf_item.value is None


def test_check_value_bounds_clamping():
    """Verify check_value_bounds clamps NDVI and moisture to physical bounds."""
    out_of_bounds_ndvi = EvidenceItem(
        evidence_id="ev_ndvi_bad",
        plot_id="p1",
        variable="ndvi",
        value=1.45,  # Max is 1.0
        source_family="sentinel2",
        source_id="s2",
        observation_type="derived_feature",
        spatial_scope="plot",
    )
    negative_moisture = EvidenceItem(
        evidence_id="ev_sm_bad",
        plot_id="p1",
        variable="soil_moisture_vwc",
        value=-0.15,  # Min is 0.0
        source_family="sensor",
        source_id="probe1",
        observation_type="measurement",
        spatial_scope="point",
    )

    violations = check_value_bounds([out_of_bounds_ndvi, negative_moisture], auto_clamp=True)
    assert len(violations) == 2
    assert out_of_bounds_ndvi.value == 1.0
    assert negative_moisture.value == 0.0
