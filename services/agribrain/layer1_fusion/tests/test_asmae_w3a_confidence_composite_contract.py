"""W3-A RED tests for ASMAE confidence RasterRefs and composite invariants.

These are intentionally failing contract tests on PR #32 base, not passing
regression receipts. Full runtime Layer10 authority tests are a separate gate.
"""
from pathlib import Path
import inspect

from services.agribrain.layer1_fusion.raster_ingest import ingest_asmae_raster_refs
from services.agribrain.layer10_sire.invariants import enforce_layer10_invariants
from services.agribrain.layer10_sire.schema import SurfaceType


def _one_cell_grid():
    return {
        "crs": "EPSG:32631",
        "bounds": [500000.0, 4000000.0, 500010.0, 4000010.0],
        "transform": [10.0, 0.0, 500000.0, 0.0, -10.0, 4000010.0],
        "width": 1, "height": 1, "resolution_m": 10.0,
    }


def test_w3a_posterior_concentration_is_a_real_diagnostic_rasterref():
    output = {
        "status": "partial",
        "grid_spec": _one_cell_grid(),
        "resolution_decision": {"selected_effective_resolution_m": 10.0},
        "raster_maps": {},
        "uncertainty_maps": {},
        "confidence_maps": {
            "ASMAE_POSTERIOR_CONCENTRATION": [[0.72]],
        },
        "provenance": {}, "diagnostics": {},
    }
    refs = ingest_asmae_raster_refs(output, plot_id="plot-w3a")
    canonical = [ref for ref in refs
                 if ref.variable == "asmae_posterior_concentration"]
    assert len(canonical) == 1, (
        "Canonical confidence cannot disappear because RasterRef is a class, "
        "not a plain dict."
    )
    assert canonical[0].diagnostic_only is True
    assert canonical[0].state_update_allowed is False
    assert canonical[0].asmae_channel == "diagnostic"
    assert canonical[0].grid == [[0.72]]


def test_w3a_legacy_confidence_alias_deduplicates_to_one_canonical_raster():
    output = {
        "status": "partial", "grid_spec": _one_cell_grid(),
        "resolution_decision": {"selected_effective_resolution_m": 10.0},
        "raster_maps": {}, "uncertainty_maps": {},
        "confidence_maps": {
            "ASMAE_CONFIDENCE": [[0.3]],
            "CONFIDENCE_ASMAE": [[0.3]],
            "ASMAE_POSTERIOR_CONCENTRATION": [[0.3]],
        },
        "provenance": {}, "diagnostics": {},
    }
    refs = ingest_asmae_raster_refs(output, plot_id="plot-w3a")
    assert sum(ref.variable == "asmae_posterior_concentration"
               for ref in refs) == 1


def test_w3a_composite_invariants_are_reachable_before_asmae_skip():
    # Cheap source guard: not a substitute for behavioral mutation tests.
    source = inspect.getsource(enforce_layer10_invariants)
    composite_pos = source.find('is_composite = s.semantic_type.value.startswith("COMPOSITE_")')
    asmae_skip_pos = source.find("if not is_asmae:")
    assert composite_pos >= 0 and asmae_skip_pos >= 0
    assert composite_pos < asmae_skip_pos, (
        "Composite authority checks must run before unrelated ASMAE skip."
    )


def test_w3a_expected_composite_semantic_family_remains_enumerated():
    assert SurfaceType.COMPOSITE_ADVISORY_CANOPY.value == "COMPOSITE_ADVISORY_CANOPY"
    assert SurfaceType.COMPOSITE_UNCERTAINTY.value == "COMPOSITE_UNCERTAINTY"
    assert SurfaceType.ASMAE_POSTERIOR_CONCENTRATION.value == "ASMAE_POSTERIOR_CONCENTRATION"
