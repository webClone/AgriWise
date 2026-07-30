"""
V65C — Resolution Ladder Truthfulness & Anti-Uniform-3m Validation Script
========================================================================
Validates all 14 gates to ensure:
- Missing observed masks default to all-False/ratio=0.0
- Confidence checks pre-backfill observed masks rather than post-backfill continuous NDVI
- IDW-filled pixels do not certify resolution
- 3m requires quality maps or high observed ratio fallback (>= 0.90)
- Demotion of uniform 3m without quality maps to 5m/10m
- Grounding class is determined by observed ratio even when raster values are uniform
- Skip demotion if best_val_res_map or ground truth 3cm or conditional 1m certification or strict microzone maps are present
- Metadata survives JSON serialization
"""

import os
import sys
import json
from dataclasses import dataclass, field as dc_field, asdict
from typing import Dict, Any, List, Optional
import numpy as np

# Adjust path to find layer10_sire
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from layer10_sire.surfaces.resolution_ladder import (
    select_resolution_per_pixel,
    ResolutionLadderConfig,
    ResolutionLadderResult
)
from layer10_sire.surfaces.resolution import generate_resolution_surfaces
from layer10_sire.schema import GroundingClass, SurfaceType, Layer10Input, SurfaceArtifact

@dataclass
class MockL1Data:
    raster_maps: Dict[str, Any] = dc_field(default_factory=dict)
    height: int = 10
    width: int = 10
    resolution_m: float = 10.0
    run_id: str = "mock_run"
    observed_ratios: Dict[str, float] = dc_field(default_factory=dict)
    observed_masks: Dict[str, List[List[bool]]] = dc_field(default_factory=dict)

# Global test registry
GATES = {}

def assert_gate(name: str, passed: bool, message: str = ""):
    GATES[name] = {"pass": bool(passed), "message": message}
    print(f"{' [PASS] ' if passed else ' [FAIL] '} | {name} | {message}")

def run_all_validation_gates():
    H, W = 10, 10
    total_pixels = H * W

    # -------------------------------------------------------------------------
    # GATE 1: no_uniform_3m_without_quality_gates
    # -------------------------------------------------------------------------
    # When quality maps are missing and observed_ratio is partial (<0.90),
    # the ladder must demote to 5m/10m and NOT generate a uniform 3m surface.
    l1_g1 = MockL1Data(
        raster_maps={
            "ndvi": [[0.5] * W for _ in range(H)],
        },
        observed_ratios={"ndvi": 0.50},
        observed_masks={"ndvi": [[True if c < 5 else False for c in range(W)] for r in range(H)]}
    )
    res_res_g1 = select_resolution_per_pixel(l1_g1, H, W)
    res_map_g1, pcts_g1 = res_res_g1
    meta_g1 = res_res_g1.metadata
    
    g1_ok = (3.0 not in np.unique(res_map_g1))
    assert_gate("no_uniform_3m_without_quality_gates", g1_ok, 
                f"Unique values: {np.unique(res_map_g1).tolist()}, demoted={meta_g1.get('anti_uniform_3m_demoted')}")

    # -------------------------------------------------------------------------
    # GATE 2: resolution_ladder_uses_pre_backfill_observed_mask
    # -------------------------------------------------------------------------
    # Verify that the resolution ladder uses the pre-backfilled observed mask rather than valid_coverage
    # Even if NDVI has values everywhere (due to IDW backfilling), resolution should only be promoted
    # on pixels that were actually observed.
    # Provide uncertainty and obs counts to pass quality gates.
    l1_g2 = MockL1Data(
        raster_maps={
            "ndvi": [[0.5] * W for _ in range(H)],
            "ndvi_uncertainty": [[0.05] * W for _ in range(H)],
            "observation_count": [[5] * W for _ in range(H)]
        },
        observed_ratios={"ndvi": 0.50},
        observed_masks={"ndvi": [[True if c < 5 else False for c in range(W)] for r in range(H)]}
    )
    res_res_g2 = select_resolution_per_pixel(l1_g2, H, W)
    res_map_g2, pcts_g2 = res_res_g2
    # Observed pixels (c < 5) should be 3.0 (or better). Unobserved (c >= 5) must be 10.0 (or 5.0 fallback).
    observed_ok = np.all(res_map_g2[:, :5] == 3.0)
    unobserved_ok = np.all((res_map_g2[:, 5:] == 10.0) | (res_map_g2[:, 5:] == 5.0))
    g2_ok = observed_ok and unobserved_ok
    assert_gate("resolution_ladder_uses_pre_backfill_observed_mask", g2_ok,
                f"Observed res: {np.unique(res_map_g2[:, :5]).tolist()}, Unobserved res: {np.unique(res_map_g2[:, 5:]).tolist()}")

    # -------------------------------------------------------------------------
    # GATE 3: idw_filled_pixels_do_not_certify_resolution
    # -------------------------------------------------------------------------
    # Verify that pixels backfilled by IDW (not in observed_mask) are not certified as 3m, 2m, or 1m.
    # This is directly checked in G2 where unobserved pixels are not 3m.
    g3_ok = np.all(~np.isin(res_map_g2[:, 5:], [1.0, 2.0, 3.0]))
    assert_gate("idw_filled_pixels_do_not_certify_resolution", g3_ok,
                f"Unobserved pixels resolutions: {np.unique(res_map_g2[:, 5:]).tolist()}")

    # -------------------------------------------------------------------------
    # GATE 4: three_meter_requires_uncertainty_or_obs_count_or_high_observed_ratio
    # -------------------------------------------------------------------------
    # If quality maps are missing:
    #   - If observed_ratio >= 0.90, 3m is allowed on observed pixels.
    #   - If observed_ratio < 0.90, 3m is NOT allowed.
    l1_g4_low = MockL1Data(
        raster_maps={"ndvi": [[0.5] * W for _ in range(H)]},
        observed_ratios={"ndvi": 0.85},
        observed_masks={"ndvi": [[True if c < 9 or r < 9 else False for c in range(W)] for r in range(H)]}
    )
    res_res_low = select_resolution_per_pixel(l1_g4_low, H, W)
    res_map_low, _ = res_res_low
    
    l1_g4_high = MockL1Data(
        raster_maps={"ndvi": [[0.5] * W for _ in range(H)]},
        observed_ratios={"ndvi": 0.95},
        observed_masks={"ndvi": [[True if (r != 0 or c != 0) else False for c in range(W)] for r in range(H)]}
    )
    res_res_high = select_resolution_per_pixel(l1_g4_high, H, W)
    res_map_high, _ = res_res_high

    g4_ok = (3.0 not in np.unique(res_map_low)) and (3.0 in np.unique(res_map_high))
    assert_gate("three_meter_requires_uncertainty_or_obs_count_or_high_observed_ratio", g4_ok,
                f"Low ratio (0.85) unique res: {np.unique(res_map_low).tolist()}. High ratio (0.95) unique res: {np.unique(res_map_high).tolist()}")

    # -------------------------------------------------------------------------
    # GATE 5: partial_raster_without_quality_maps_demotes_to_5m_or_10m
    # -------------------------------------------------------------------------
    # Verify that partial raster with ratio = 0.52 and no quality maps gets 5m on observed and 10m on unobserved.
    l1_g5 = MockL1Data(
        raster_maps={"ndvi": [[0.5] * W for _ in range(H)]},
        observed_ratios={"ndvi": 0.52},
        observed_masks={"ndvi": [[True if c < 5 else False for c in range(W)] for r in range(H)]}
    )
    res_res_g5 = select_resolution_per_pixel(l1_g5, H, W)
    res_map_g5, _ = res_res_g5
    g5_ok = np.all(res_map_g5[:, :5] == 5.0) and np.all(res_map_g5[:, 5:] == 10.0)
    assert_gate("partial_raster_without_quality_maps_demotes_to_5m_or_10m", g5_ok,
                f"Observed: {np.unique(res_map_g5[:, :5]).tolist()}, Unobserved: {np.unique(res_map_g5[:, 5:]).tolist()}")

    # -------------------------------------------------------------------------
    # GATE 6: resolution_grounding_not_forced_to_uniform_when_class_values_uniform
    # -------------------------------------------------------------------------
    # Verify that GroundingClass is determined by observed ratio (e.g. RASTER_GROUNDED if ratio >= 0.90),
    # even when the resolution values are uniform (e.g. 10m everywhere).
    l10_in = Layer10Input(field_tensor=None, veg_int=None, plot_id="g6_plot")
    
    l1_g6_uniform = MockL1Data(
        raster_maps={
            "ndvi": [[0.5] * W for _ in range(H)],
            "best_val_res_map": [[10.0] * W for _ in range(H)]
        },
        observed_ratios={"ndvi": 0.95},
        observed_masks={"ndvi": [[True] * W for _ in range(H)]}
    )
    surfaces_uniform = generate_resolution_surfaces(l10_in, H, W, l1_data=l1_g6_uniform)
    surf_g6_uniform = surfaces_uniform[0]

    # Check grounding class and values uniformity
    g6_ok = (surf_g6_uniform.grounding_class == GroundingClass.RASTER_GROUNDED.value)
    assert_gate("resolution_grounding_not_forced_to_uniform_when_class_values_uniform", g6_ok,
                f"Uniform values map grounding class: {surf_g6_uniform.grounding_class} (expected RASTER_GROUNDED)")

    # -------------------------------------------------------------------------
    # GATE 7: resolution_surface_provenance_exposes_ladder_inputs
    # -------------------------------------------------------------------------
    # Verify that the generated surface contains the resolution ladder metadata in its provenance.
    l1_g6 = MockL1Data(
        raster_maps={
            "ndvi": [[0.5] * W for _ in range(H)],
        },
        observed_ratios={"ndvi": 0.95},
        observed_masks={"ndvi": [[True] * W for _ in range(H)]}
    )
    surfaces = generate_resolution_surfaces(l10_in, H, W, l1_data=l1_g6)
    surf_g6 = surfaces[0]
    prov = surf_g6.provenance
    g7_ok = ("ladder_inputs" in prov) and ("selection_policy" in prov) and ("anti_uniform_3m_demoted" in prov)
    assert_gate("resolution_surface_provenance_exposes_ladder_inputs", g7_ok,
                f"Provenance keys: {list(prov.keys())}")

    # -------------------------------------------------------------------------
    # GATE 8: best_val_res_map_path_still_preserved
    # -------------------------------------------------------------------------
    # If best_val_res_map is present, it should use pixel_resolved strategy.
    l1_g8 = MockL1Data(
        raster_maps={
            "best_val_res_map": [[2.0] * W for _ in range(H)],
        }
    )
    surfaces_g8 = generate_resolution_surfaces(l10_in, H, W, l1_data=l1_g8)
    g8_ok = (surfaces_g8[0].provenance.get("spatial_precision") == "pixel_resolved")
    assert_gate("best_val_res_map_path_still_preserved", g8_ok,
                f"Spatial precision: {surfaces_g8[0].provenance.get('spatial_precision')}")

    # -------------------------------------------------------------------------
    # GATE 9: ground_truth_3cm_mask_still_overrides_satellite_ladder
    # -------------------------------------------------------------------------
    # 3cm ground truth mask overrides other satellite decisions.
    gt_mask = np.zeros((H, W), dtype=bool)
    gt_mask[3:6, 3:6] = True
    res_res_g9 = select_resolution_per_pixel(l1_g2, H, W, ground_truth_mask=gt_mask)
    res_map_g9, _ = res_res_g9
    g9_ok = np.all(res_map_g9[3:6, 3:6] == 0.03) and not np.any(res_map_g9[~gt_mask] == 0.03)
    assert_gate("ground_truth_3cm_mask_still_overrides_satellite_ladder", g9_ok,
                f"Ground truth pixels value: {np.unique(res_map_g9[3:6, 3:6]).tolist()}")

    # -------------------------------------------------------------------------
    # GATE 10: one_meter_and_two_meter_still_require_strict_microzone_gates
    # -------------------------------------------------------------------------
    # 1m requires retrovalidation score and zone policy, 2m requires zone policy.
    # Test that if retrovalidation score is too low, we don't get 1m but get 2m.
    l1_g10_low_retro = MockL1Data(
        raster_maps={
            "ndvi": [[0.5] * W for _ in range(H)],
            "ndvi_uncertainty": [[0.05] * W for _ in range(H)],
            "microzone_zone_policy": [[1.0] * W for _ in range(H)],
            "microzone_retrovalidation_score": [[0.5] * W for _ in range(H)] # below 0.70
        },
        observed_ratios={"ndvi": 1.0},
        observed_masks={"ndvi": [[True]*W for _ in range(H)]}
    )
    res_res_g10 = select_resolution_per_pixel(l1_g10_low_retro, H, W)
    res_map_g10, _ = res_res_g10
    g10_ok = (1.0 not in np.unique(res_map_g10)) and (2.0 in np.unique(res_map_g10))
    assert_gate("one_meter_and_two_meter_still_require_strict_microzone_gates", g10_ok,
                f"Unique values with low retro score: {np.unique(res_map_g10).tolist()}")

    # -------------------------------------------------------------------------
    # GATE 11: missing_observed_mask_does_not_promote_to_3m
    # -------------------------------------------------------------------------
    # Verify that when observed_mask is missing, it defaults to ratio=0.0/all-False, preventing promotion to 3m/5m.
    l1_g11 = MockL1Data(
        raster_maps={
            "ndvi": [[0.5] * W for _ in range(H)],
        }
    )
    res_res_g11 = select_resolution_per_pixel(l1_g11, H, W)
    res_map_g11, pcts_g11 = res_res_g11
    meta_g11 = res_res_g11.metadata
    g11_ok = np.all(res_map_g11 == 10.0) and (meta_g11["ladder_inputs"]["ndvi_observed_ratio"] == 0.0)
    assert_gate("missing_observed_mask_does_not_promote_to_3m", g11_ok,
                f"Missing observed mask unique res: {np.unique(res_map_g11).tolist()}, ratio={meta_g11['ladder_inputs']['ndvi_observed_ratio']}")

    # -------------------------------------------------------------------------
    # GATE 12: anti_uniform_3m_does_not_override_best_val_res_map
    # -------------------------------------------------------------------------
    # If uses_best_val_res_map is True, anti-uniform 3m demotion is skipped, retaining 3m everywhere.
    l1_g12_high = MockL1Data(
        raster_maps={"ndvi": [[0.5] * W for _ in range(H)]},
        observed_ratios={"ndvi": 0.95},
        observed_masks={"ndvi": [[True]*W for _ in range(H)]}
    )
    # High observed ratio + no quality maps normally creates 3.0 everywhere.
    # By default, without uses_best_val_res_map, it evaluates to 3.0 everywhere,
    # which triggers the demotion because it's uniform 3m without quality maps!
    res_res_default = select_resolution_per_pixel(l1_g12_high, H, W, uses_best_val_res_map=False)
    res_default, _ = res_res_default
    meta_default = res_res_default.metadata
    
    # With uses_best_val_res_map=True, it should skip demotion and remain 3.0.
    res_res_skip = select_resolution_per_pixel(l1_g12_high, H, W, uses_best_val_res_map=True)
    res_skip, _ = res_res_skip
    meta_skip = res_res_skip.metadata
    
    g12_ok = (np.all(res_default != 3.0) and meta_default["anti_uniform_3m_demoted"]) and (np.all(res_skip == 3.0) and not meta_skip["anti_uniform_3m_demoted"])
    assert_gate("anti_uniform_3m_does_not_override_best_val_res_map", g12_ok,
                f"Default (uses_best_val_res_map=False) unique: {np.unique(res_default).tolist()}, demoted={meta_default['anti_uniform_3m_demoted']}. "
                f"Override (uses_best_val_res_map=True) unique: {np.unique(res_skip).tolist()}, demoted={meta_skip['anti_uniform_3m_demoted']}.")

    # -------------------------------------------------------------------------
    # GATE 13: anti_uniform_3m_does_not_override_ground_truth_3cm
    # -------------------------------------------------------------------------
    # If ground_truth_mask is present, anti-uniform demotion is skipped.
    gt_mask_g13 = np.zeros((H, W), dtype=bool)
    gt_mask_g13[0, 0] = True
    res_res_g13 = select_resolution_per_pixel(l1_g12_high, H, W, ground_truth_mask=gt_mask_g13)
    res_g13, _ = res_res_g13
    meta_g13 = res_res_g13.metadata
    
    g13_ok = (not meta_g13["anti_uniform_3m_demoted"]) and (0.03 in np.unique(res_g13))
    assert_gate("anti_uniform_3m_does_not_override_ground_truth_3cm", g13_ok,
                f"Ground truth present demoted={meta_g13['anti_uniform_3m_demoted']}, unique={np.unique(res_g13).tolist()}")

    # -------------------------------------------------------------------------
    # GATE 14: resolution_ladder_metadata_survives_serialization
    # -------------------------------------------------------------------------
    # Verify that the generated SurfaceArtifact is serializable to JSON and retains all metadata keys.
    serialized = asdict(surf_g6)
    json_str = json.dumps(serialized)
    loaded = json.loads(json_str)
    
    loaded_prov = loaded.get("provenance", {})
    g14_ok = (
        "ladder_inputs" in loaded_prov and
        "selection_policy" in loaded_prov and
        "anti_uniform_3m_demoted" in loaded_prov and
        loaded_prov["ladder_inputs"].get("ndvi_observed_ratio") == 0.95
    )
    assert_gate("resolution_ladder_metadata_survives_serialization", g14_ok,
                f"Loaded provenance ladder_inputs: {loaded_prov.get('ladder_inputs')}")

    # Write the formal JSON test report for the runner
    report = {
        "milestone": "V65C_resolution_ladder_truthfulness",
        "gates": GATES,
        "all_pass": all(bool(g["pass"]) for g in GATES.values())
    }
    
    report_dir = os.path.join(BASE, "artifacts")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "v65c_resolution_ladder_truthfulness_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nWritten formal validation report to {report_path}")
    
    if report["all_pass"]:
        print("\nALL 14 V65C GATES PASSED SUCCESSFULLY!")
        return 0
    else:
        print("\nSOME GATES FAILED. PLEASE DEBUG.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_validation_gates())
