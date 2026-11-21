"""W2-B RED: standalone Layer4 cannot inject unqualified ASMAE LAI.

Test real standalone entry point, not an invented helper or mock result.
"""
from types import SimpleNamespace
import pytest
from layer4_nutrients.runner import run_layer4_standalone


def _weather():
    return [{"t_max": 25.0, "t_min": 14.0, "rain_mm": 0.0,
             "et0": 4.5, "vpd_kpa": 1.5} for _ in range(14)]


def _run_with_lai(feature):
    biological = {"lai_current": 1.2}
    run_layer4_standalone(
        plot_id="plot-w2b-lai",
        crop_type="wheat",
        management_goal="yield_max",
        irrigation_type="rainfed",
        planting_date="2025-11-15",
        daily_weather=_weather(),
        stages=["vegetative"] * 14,
        l2_biophysical=biological,
        asmae_features={"ASMAE_LAI": feature},
        # Empty lineage cannot establish crop-specific scientific authority.
        semantic_lineage={},
    )
    return biological


@pytest.mark.parametrize("feature", [
    SimpleNamespace(value=7.3, state_update_allowed=False, diagnostic_only=True),
    SimpleNamespace(value=7.3, state_update_allowed=False, diagnostic_only=False),
    SimpleNamespace(value=7.3, state_update_allowed=True, diagnostic_only=True),
    SimpleNamespace(value=7.3, state_update_allowed=True, diagnostic_only=False,
                    uncertainty=None, asmae_channel="diagnostic"),
])
def test_w2b_unqualified_asmae_lai_cannot_override_independent_l2(feature):
    output = _run_with_lai(feature)
    assert output["lai_current"] == pytest.approx(1.2), (
        "A raw ASMAE .value cannot replace legitimate independent Layer2 LAI."
    )


def test_w2b_standalone_without_asmae_keeps_independent_l2_input():
    biological = {"lai_current": 1.2}
    run_layer4_standalone(
        plot_id="plot-w2b-baseline",
        crop_type="wheat",
        management_goal="yield_max",
        daily_weather=_weather(),
        l2_biophysical=biological,
        asmae_features=None,
    )
    assert biological["lai_current"] == pytest.approx(1.2)
