"""
Resolution Ladder Selector (V61C)
==================================

Per-pixel resolution class selector implementing the six-tier priority ladder:

    0.03m  → external ground-truth (drone/proximal)
    1.0m   → certified advisory visual layer (state_update=False)
    2.0m   → adaptive production (state_update=True)
    3.0m   → adaptive production (state_update=True)
    5.0m   → adaptive production (state_update=True)
    10.0m  → native Sentinel fallback (state_update=True)

Policy:
  - 3cm has highest priority and overwrites satellite-derived classes.
  - 1m must pass satellite gates AND not be blocked by ground-truth conflicts.
  - 2m/3m/5m are evaluated from highest to lowest resolution.
  - 10m is used ONLY as a last fallback when all other gates fail.
  - Absence of ground truth ≠ automatic 10m.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class ResolutionLadderResult(tuple):
    """
    Subclass of tuple (res_map, percentages) representing the resolution ladder output.
    Maintains backward compatibility for unpacking (res_map, pcts = result) while
    transporting metadata cleanly to generate_resolution_surfaces().
    """
    def __new__(cls, res_map: np.ndarray, percentages: Dict[str, float], metadata: Dict[str, Any]):
        obj = super().__new__(cls, (res_map, percentages))
        obj.res_map = res_map
        obj.percentages = percentages
        obj.metadata = metadata
        return obj

    def __init__(self, res_map: np.ndarray, percentages: Dict[str, float], metadata: Dict[str, Any]):
        pass


@dataclass(frozen=True)
class ResolutionLadderConfig:
    """
    Configurable thresholds for satellite-derived resolution gates.
    
    Defaults are physically meaningful starting points based on
    retrovalidation and zone_policy data. Can be tuned later by
    crop type, geography, sensor density, or season.
    """
    # 1m gate thresholds
    uncertainty_1m_max: float = 0.08
    retrovalidation_1m_min: float = 0.70
    require_zone_policy_for_1m: bool = True

    # 2m gate thresholds
    uncertainty_2m_max: float = 0.10
    require_zone_policy_for_2m: bool = True

    # 3m gate thresholds
    uncertainty_3m_max: float = 0.15
    observation_density_3m_min: int = 3

    # 5m gate: any valid NDVI/SAR coverage
    # (no additional uncertainty threshold — coverage is sufficient)


# Canonical resolution tiers with their metadata
RESOLUTION_TIERS = {
    0.03: {"origin": "external_ground_truth", "role": "validation_anchor", "state_update_allowed": False},
    1.0:  {"origin": "model_assisted_from_10m_evidence", "role": "advisory_fine_detail", "state_update_allowed": False},
    2.0:  {"origin": "model_assisted_from_10m_evidence", "role": "model_assisted_representation", "state_update_allowed": False},
    3.0:  {"origin": "model_assisted_from_10m_evidence", "role": "model_assisted_representation", "state_update_allowed": False},
    5.0:  {"origin": "sentinel_10m_native_support", "role": "model_assisted_representation", "state_update_allowed": False},
    10.0: {"origin": "sentinel_temporal_baseline", "role": "native_fallback", "state_update_allowed": True},
}

# Percentage field names in priority order
PERCENTAGE_FIELDS = [
    "three_cm_external_ground_truth_pct",
    "one_meter_advisory_pct",
    "two_meter_production_pct",
    "three_meter_production_pct",
    "five_meter_production_pct",
    "ten_meter_fallback_pct",
]


def select_resolution_per_pixel(
    l1_data: Any,
    H: int,
    W: int,
    ground_truth_mask: Optional[np.ndarray] = None,
    one_meter_block_mask: Optional[np.ndarray] = None,
    config: Optional[ResolutionLadderConfig] = None,
    uses_best_val_res_map: bool = False,
    conditional_1m_certification: Optional[bool] = None,
    strict_microzone_maps: Optional[bool] = None,
) -> ResolutionLadderResult:
    """
    Evaluate the six-tier resolution ladder per pixel.

    Args:
        l1_data: Adapted L1 spatial data (has .raster_maps and .observed_masks dicts)
        H, W: grid dimensions
        ground_truth_mask: Optional bool array (H×W). True where 3cm
                           external ground truth is valid.
        one_meter_block_mask: Optional bool array (H×W). True where 1m
                              is blocked by ground-truth conflicts.
        config: Threshold configuration. Uses defaults if None.
        uses_best_val_res_map: If True, indicates the best_val_res_map path is active.
        conditional_1m_certification: Optional flag indicating conditional 1m certification is present.
        strict_microzone_maps: Optional flag indicating strict microzone maps are present.

    Returns:
        ResolutionLadderResult containing:
        - res_map: np.ndarray (H, W) with resolution class per pixel
        - resolution_percentages: dict with all 6 percentage fields summing to 100
        - metadata: dict with diagnostic/provenance information
    """
    if config is None:
        config = ResolutionLadderConfig()

    total_pixels = H * W
    res_map = np.full((H, W), 10.0, dtype=np.float64)

    # ── Extract L1 observed mask & ratio ──────────────────────────────────
    observed_masks = getattr(l1_data, 'observed_masks', {}) or {}
    observed_ratios = getattr(l1_data, 'observed_ratios', {}) or {}

    # Look for primary NDVI key first
    ndvi_key = next((k for k in ['ndvi', 'NDVI'] if k in observed_masks), None)
    if ndvi_key:
        observed_mask_list = observed_masks[ndvi_key]
        observed_ratio = observed_ratios.get(ndvi_key, 0.0)
        observed_mask_available = True
    else:
        # Fallback to other keys if available (e.g. SAR/vh)
        other_key = next(iter(observed_masks.keys()), None)
        if other_key:
            observed_mask_list = observed_masks[other_key]
            observed_ratio = observed_ratios.get(other_key, 0.0)
            observed_mask_available = True
        else:
            observed_mask_list = None
            observed_ratio = 0.0
            observed_mask_available = False

    if observed_mask_available and observed_mask_list is not None:
        observed_mask = np.asarray(observed_mask_list, dtype=bool)
        if observed_mask.shape != (H, W):
            # Resample mask if shape mismatch
            row_idx = np.linspace(0, observed_mask.shape[0] - 1, H).astype(int)
            col_idx = np.linspace(0, observed_mask.shape[1] - 1, W).astype(int)
            observed_mask = observed_mask[np.ix_(row_idx, col_idx)]
    else:
        observed_mask = np.zeros((H, W), dtype=bool)

    # ── Extract L1 raster data ────────────────────────────────────────────
    raster_maps = {}
    if l1_data is not None:
        raster_maps = getattr(l1_data, 'raster_maps', {}) or {}

    asmae_res = _extract_raster(raster_maps, ['ASMAE_EFFECTIVE_RESOLUTION_MAP', 'asmae_effective_resolution_map'], H, W)
    if asmae_res is not None:
        uses_best_val_res_map = True

    ndvi = _extract_raster(raster_maps, ['ndvi', 'NDVI'], H, W)
    uncertainty = _extract_raster(raster_maps, ['ndvi_uncertainty', 'uncertainty', 'microzone_uncertainty', 'ASMAE_UNCERTAINTY', 'asmae_uncertainty'], H, W)
    sar_vh = _extract_raster(raster_maps, ['vh', 'VH', 'sar_vh', 'sar_backscatter'], H, W)
    fallback_mask = _extract_raster(raster_maps, ['microzone_fallback_mask', 'fallback_mask'], H, W)
    zone_policy = _extract_raster(raster_maps, ['microzone_zone_policy', 'zone_policy_map', 'ASMAE_1M_ADVISORY_MASK', 'asmae_1m_advisory_mask', 'ASMAE_ENKF_SUPPORT', 'asmae_enkf_support'], H, W)
    retro_score = _extract_raster(raster_maps, ['microzone_retrovalidation_score', 'retrovalidation_score', 'ASMAE_RETROVALIDATION_SCORE', 'asmae_retrovalidation_score'], H, W)
    obs_count = _extract_raster(raster_maps, ['observation_count', 'obs_density', 'ASMAE_ARCHIVE_SUPPORT', 'asmae_archive_support'], H, W)

    # ── Build validity masks ──────────────────────────────────────────────
    has_ndvi = ndvi is not None
    has_sar = sar_vh is not None
    has_uncertainty = uncertainty is not None
    has_fallback = fallback_mask is not None
    has_zone_policy = zone_policy is not None
    has_retro = retro_score is not None
    has_obs_count = obs_count is not None

    # Base coverage mask: pixel has NDVI or SAR data
    valid_coverage = np.zeros((H, W), dtype=bool)
    if has_ndvi:
        valid_coverage |= np.isfinite(ndvi) & (ndvi > -1.0)
    if has_sar:
        valid_coverage |= np.isfinite(sar_vh) & (sar_vh != 0.0)

    # ── Gate 5m: valid Sentinel coverage exists ──────────────────────────
    if has_uncertainty or has_obs_count:
        gate_5m = observed_mask & valid_coverage
    else:
        # For no uncertainty/obs-count cases
        if observed_ratio >= 0.30:
            gate_5m = observed_mask & valid_coverage
        else:
            gate_5m = np.zeros((H, W), dtype=bool)
    res_map[gate_5m] = 5.0

    # ── Gate 3m: lower uncertainty + observation density ──────────────────
    if has_uncertainty:
        unc_ok = uncertainty < config.uncertainty_3m_max
    else:
        unc_ok = np.zeros((H, W), dtype=bool)

    if has_obs_count:
        obs_ok = obs_count >= config.observation_density_3m_min
    else:
        obs_ok = np.zeros((H, W), dtype=bool)

    selection_policy = "standard_ladder"
    quality_maps_missing = False

    if not has_uncertainty and not has_obs_count:
        quality_maps_missing = True
        if observed_ratio >= 0.90:
            gate_3m = observed_mask & valid_coverage
            selection_policy = "high_observed_ratio_no_quality_maps_3m"
        else:
            gate_3m = np.zeros((H, W), dtype=bool)
            selection_policy = "partial_observed_pixels_5m_else_10m"
    else:
        gate_3m = unc_ok & obs_ok & observed_mask & valid_coverage
        
    res_map[gate_3m] = 3.0

    # ── Gate 2m: tighter uncertainty + deconvolution zone active ─────────
    if has_uncertainty:
        unc_2m_ok = uncertainty < config.uncertainty_2m_max
    else:
        unc_2m_ok = np.zeros((H, W), dtype=bool)

    if config.require_zone_policy_for_2m and has_zone_policy:
        zone_ok_2m = zone_policy >= 0.5  # zone_policy=1 means deconv active
    elif config.require_zone_policy_for_2m:
        zone_ok_2m = np.zeros((H, W), dtype=bool)
    else:
        zone_ok_2m = np.ones((H, W), dtype=bool)

    # Fallback mask: pixel must not be in fallback
    if has_fallback:
        not_fallback = fallback_mask < 0.5
    else:
        not_fallback = np.ones((H, W), dtype=bool)

    gate_2m = unc_2m_ok & zone_ok_2m & not_fallback & observed_mask & valid_coverage
    res_map[gate_2m] = 2.0

    # ── Gate 1m: tightest uncertainty + retro score + zone + no fallback ──
    if has_uncertainty:
        unc_1m_ok = uncertainty < config.uncertainty_1m_max
    else:
        unc_1m_ok = np.zeros((H, W), dtype=bool)

    if has_retro:
        retro_ok = retro_score >= config.retrovalidation_1m_min
    else:
        retro_ok = np.zeros((H, W), dtype=bool)

    if config.require_zone_policy_for_1m and has_zone_policy:
        zone_ok_1m = zone_policy >= 0.5
    elif config.require_zone_policy_for_1m:
        zone_ok_1m = np.zeros((H, W), dtype=bool)
    else:
        zone_ok_1m = np.ones((H, W), dtype=bool)

    gate_1m = unc_1m_ok & retro_ok & zone_ok_1m & not_fallback & observed_mask & valid_coverage

    # Apply 1m ground-truth block mask
    if one_meter_block_mask is not None:
        block = np.asarray(one_meter_block_mask, dtype=bool)
        if block.shape == (H, W):
            gate_1m = gate_1m & ~block

    res_map[gate_1m] = 1.0
    if asmae_res is not None:
        res_map = np.copy(asmae_res)

    # ── Gate 3cm: external ground truth mask (highest priority) ──────────
    # 3cm overwrites ALL satellite-derived classes
    has_3cm = False
    if ground_truth_mask is not None:
        gt_mask = np.asarray(ground_truth_mask, dtype=bool)
        if gt_mask.shape == (H, W) and np.any(gt_mask):
            res_map[gt_mask] = 0.03
            has_3cm = True

    # ── Hard Anti-Uniform-3m Gate ──────────────────────────────────────────
    unique_vals = sorted(set(np.round(res_map.ravel(), 4)))
    missing_quality_gates = (
        uncertainty is None and
        obs_count is None and
        zone_policy is None and
        retro_score is None
    )

    anti_uniform_demoted = False

    # Skip anti-uniform demotion if overrides/exceptions are active
    skip_anti_uniform_3m_demotion = False
    if uses_best_val_res_map:
        skip_anti_uniform_3m_demotion = True
    if has_3cm:
        skip_anti_uniform_3m_demotion = True
    if conditional_1m_certification is not None and conditional_1m_certification:
        skip_anti_uniform_3m_demotion = True
    if strict_microzone_maps is not None and strict_microzone_maps:
        skip_anti_uniform_3m_demotion = True

    if unique_vals == [3.0] and missing_quality_gates and not skip_anti_uniform_3m_demotion:
        # Demote to 5m/10m based on observed mask
        res_map[:] = 10.0
        if observed_mask_available:
            res_map[observed_mask] = 5.0
        anti_uniform_demoted = True
        selection_policy = "partial_observed_pixels_5m_else_10m"

        import sys
        print(
            f"[RESOLUTION_LADDER] Anti-uniform-3m demotion triggered. "
            f"Observed ratio={observed_ratio:.4f}. Demoted to 5m/10m.",
            file=sys.stderr
        )

    # ── Compute resolution percentages ────────────────────────────────────
    percentages = _compute_percentages(res_map, total_pixels)
    percentages["two_meter_model_assisted_pct"] = percentages.get("two_meter_production_pct", 0.0)
    percentages["three_meter_model_assisted_pct"] = percentages.get("three_meter_production_pct", 0.0)
    percentages["five_meter_model_assisted_pct"] = percentages.get("five_meter_production_pct", 0.0)
    percentages["two_meter_production_pct"] = 0.0
    percentages["three_meter_production_pct"] = 0.0
    percentages["five_meter_production_pct"] = 0.0

    metadata = {
        "ladder_inputs": {
            "has_best_val_res_map": uses_best_val_res_map,
            "has_uncertainty": has_uncertainty,
            "has_observation_count": has_obs_count,
            "has_zone_policy": has_zone_policy,
            "has_retrovalidation_score": has_retro,
            "ndvi_observed_ratio": round(observed_ratio, 4),
            "ndmi_observed_ratio": round(observed_ratios.get('ndmi', 0.0) or observed_ratios.get('NDMI', 0.0), 4)
        },
        "selection_policy": selection_policy,
        "anti_uniform_3m_demoted": anti_uniform_demoted
    }
    metadata["resolution_class_labels"] = {
        "5.0": "5 m model-assisted representation",
        "10.0": "10 m source-evidence support",
    }
    metadata["source_evidence_resolution_m"] = 10.0
    metadata["five_meter_model_assisted_pct"] = percentages.get("five_meter_model_assisted_pct", 0.0)
    metadata["two_meter_model_assisted_pct"] = percentages.get("two_meter_model_assisted_pct", 0.0)
    metadata["three_meter_model_assisted_pct"] = percentages.get("three_meter_model_assisted_pct", 0.0)
    if quality_maps_missing:
        metadata["quality_maps_missing"] = True

    return ResolutionLadderResult(res_map, percentages, metadata)


def _extract_raster(
    raster_maps: Dict[str, Any],
    keys: List[str],
    H: int,
    W: int,
) -> Optional[np.ndarray]:
    """Extract a raster from L1 raster_maps, trying multiple key aliases."""
    for key in keys:
        if key in raster_maps:
            val = raster_maps[key]
            if val is not None:
                arr = np.asarray(val, dtype=float)
                if arr.ndim == 2 and arr.shape[0] > 0 and arr.shape[1] > 0:
                    # Resample if shape mismatch
                    if arr.shape != (H, W):
                        row_idx = np.linspace(0, arr.shape[0] - 1, H).astype(int)
                        col_idx = np.linspace(0, arr.shape[1] - 1, W).astype(int)
                        arr = arr[np.ix_(row_idx, col_idx)]
                    return arr
    return None


def _compute_percentages(res_map: np.ndarray, total_pixels: int) -> Dict[str, float]:
    """Compute the six-bucket resolution percentage breakdown."""
    finite_mask = np.isfinite(res_map)
    finite_count = int(np.sum(finite_mask))
    if finite_count > 0:
        total_pixels = finite_count
    if total_pixels == 0:
        return {field: 0.0 for field in PERCENTAGE_FIELDS}

    counts = {
        0.03: int(np.sum(np.isclose(res_map[finite_mask], 0.03))),
        1.0:  int(np.sum(np.isclose(res_map[finite_mask], 1.0))),
        2.0:  int(np.sum(np.isclose(res_map[finite_mask], 2.0))),
        3.0:  int(np.sum(np.isclose(res_map[finite_mask], 3.0))),
        5.0:  int(np.sum(np.isclose(res_map[finite_mask], 5.0))),
        10.0: int(np.sum(np.isclose(res_map[finite_mask], 10.0))),
    }

    pcts = {
        "three_cm_external_ground_truth_pct": round(100.0 * counts[0.03] / total_pixels, 2),
        "one_meter_advisory_pct":             round(100.0 * counts[1.0] / total_pixels, 2),
        "two_meter_production_pct":           round(100.0 * counts[2.0] / total_pixels, 2),
        "three_meter_production_pct":         round(100.0 * counts[3.0] / total_pixels, 2),
        "five_meter_production_pct":          round(100.0 * counts[5.0] / total_pixels, 2),
        "ten_meter_fallback_pct":             round(100.0 * counts[10.0] / total_pixels, 2),
    }

    # Enforce sum-to-100 by adjusting 10m fallback for rounding
    total = sum(pcts.values())
    if abs(total - 100.0) > 0.01:
        pcts["ten_meter_fallback_pct"] = round(pcts["ten_meter_fallback_pct"] + (100.0 - total), 2)

    return pcts
