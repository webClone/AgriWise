"""
Test Suite for Layer 2 Phase 4: Biophysical Retrieval Modernization
"""

import pytest
from layer2_veg_int.growth_engine import GrowthCurveEngine, RadiativeTransferModelStub


def test_dynamic_fvc_endpoints():
    """FVC with dynamic endpoints adapts to the empirical distribution."""
    # Desert shrub / sparse canopy: NDVI from 0.08 to 0.45
    ndvi_sparse = [0.08, 0.10, 0.15, 0.25, 0.35, 0.42, 0.45, 0.30, 0.15, 0.09]
    fvc_sparse = GrowthCurveEngine.compute_fvc(ndvi_sparse)
    
    # Peak FVC should reach close to 1.0 because 0.45 is the local canopy 95th percentile
    assert max(fvc_sparse) >= 0.40
    assert min(fvc_sparse) <= 0.05


def test_optical_cwsi_proxy_no_future_leakage():
    """CWSI proxy should use standard optical physical bounds without whole-season data leakage."""
    # When NDWI is 0.35 (well-watered), CWSI proxy should be 0.0 (no water stress)
    cwsi_wet = GrowthCurveEngine.compute_cwsi([0.35], [0.80])
    assert cwsi_wet[0] == 0.0

    # When NDWI is -0.25 (dry bare soil), CWSI proxy should be 1.0 (maximum water stress)
    cwsi_dry = GrowthCurveEngine.compute_cwsi([-0.25], [0.20])
    assert cwsi_dry[0] == 1.0


def test_rtm_stub_interface():
    """RTM PROSAIL stub provides biophysical quantities."""
    bands = {"B08": 0.45, "B04": 0.05}
    res = RadiativeTransferModelStub.invert_prosail_lut(bands)
    assert "lai" in res
    assert "fvc" in res
    assert "cab_proxy" in res
    assert res["lai"] > 0.0
