"""
Layer 0.6: DNA Cache — Persistent Biophysical Trait Storage

Caches Plot DNA sequencing results to avoid 5-30s re-sequencing on every
pipeline run. Also provides the critical mapping functions that translate
inverted DNA traits into ProcessModel-compatible crop parameters.

Cache is file-based JSON, mirroring the state_persistence.py pattern.
TTL: 24 hours by default (DNA traits don't change on sub-daily timescales).
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import hashlib
import json
import os
import logging

from services.agribrain.layer0.state_vector import DEFAULT_CROP_PARAMS

logger = logging.getLogger("agribrain.dna_cache")

# Default cache directory (relative to agribrain root)
_DEFAULT_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".cache", "dna"
)


def save_dna_cache(
    plot_id: str,
    dna_result: Dict[str, Any],
    cache_dir: Optional[str] = None,
) -> str:
    """
    Persist DNA sequencing result for a plot.

    Args:
        plot_id: unique plot identifier
        dna_result: the full dict returned by trigger_dna_sequencing()
        cache_dir: override cache directory

    Returns:
        Path to the saved cache file.
    """
    cache_dir = cache_dir or _DEFAULT_CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)

    envelope = {
        "version": "dna-cache-v1",
        "plot_id": plot_id,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "dna_hash": _hash_dna_traits(dna_result),
        "payload": dna_result,
    }

    fname = f"dna_{plot_id}.json"
    fpath = os.path.join(cache_dir, fname)

    with open(fpath, "w") as f:
        json.dump(envelope, f, indent=2, default=str)

    logger.info(f"DNA cached for plot {plot_id} → {fpath}")
    return fpath


def load_dna_cache(
    plot_id: str,
    cache_dir: Optional[str] = None,
    max_age_hours: float = 24.0,
) -> Optional[Dict[str, Any]]:
    """
    Load cached DNA result for a plot.

    Returns None if:
      - No cache file exists
      - Cache is stale (older than max_age_hours)
      - Cache is corrupt

    Returns:
        The original dna_result dict, or None.
    """
    cache_dir = cache_dir or _DEFAULT_CACHE_DIR
    fname = f"dna_{plot_id}.json"
    fpath = os.path.join(cache_dir, fname)

    if not os.path.exists(fpath):
        return None

    try:
        with open(fpath, "r") as f:
            envelope = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"DNA cache corrupt for {plot_id}: {e}")
        return None

    # Version check
    if envelope.get("version") != "dna-cache-v1":
        logger.warning(f"DNA cache version mismatch for {plot_id}")
        return None

    # Staleness check
    try:
        cached_at = datetime.fromisoformat(envelope["cached_at"])
        # Ensure both are timezone-aware for comparison
        now = datetime.now(timezone.utc)
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        age_hours = (now - cached_at).total_seconds() / 3600
        if age_hours > max_age_hours:
            logger.info(f"DNA cache stale for {plot_id}: {age_hours:.1f}h > {max_age_hours}h")
            return None
    except (KeyError, ValueError):
        return None

    payload = envelope.get("payload")
    if not payload or "traits" not in payload:
        logger.warning(f"DNA cache missing payload/traits for {plot_id}")
        return None

    logger.info(f"DNA cache HIT for {plot_id} (age={age_hours:.1f}h)")
    return payload


def dna_to_crop_params(dna_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map DNA biophysical traits to ProcessModel-compatible crop_params.

    This is the critical bridge function. Each DNA trait scales a specific
    DEFAULT_CROP_PARAMS value:

      theta_retention → WHC (water holding capacity)
      beta_resilience → t_max (thermal ceiling)
      alpha_vigor     → lai_growth_rate (growth efficiency)
      t_shift         → gdd_vegetative (microclimate GDD offset)

    Returns:
        Dict of crop_params overrides (merged with defaults by ProcessModel).
    """
    traits = dna_result.get("traits", {})

    theta = traits.get("theta_retention", 1.0)
    beta = traits.get("beta_resilience", 0.0)
    alpha = traits.get("alpha_vigor", 1.0)
    t_shift = traits.get("t_shift", 0.0)

    # theta_retention: multiplicative WHC modifier (0.5–1.5×)
    #   theta=1.0 → default WHC (150 mm/m)
    #   theta=1.3 → soil retains 30% more water (195 mm/m)
    whc = DEFAULT_CROP_PARAMS["whc_mm_per_m"] * max(0.3, theta)

    # beta_resilience: thermal penalty coefficient (0–5 degrees)
    #   beta=0 → no penalty shift (crops tolerate heat well)
    #   beta=3 → effective t_max drops by 3°C (heat-sensitive site)
    t_max = DEFAULT_CROP_PARAMS["t_max"] - beta

    # alpha_vigor: growth efficiency modifier (0.7–1.3×)
    #   alpha=1.0 → default growth rate
    #   alpha=1.2 → 20% faster canopy development
    lai_growth_rate = DEFAULT_CROP_PARAMS["lai_growth_rate"] * max(0.5, alpha)

    # t_shift: microclimate GDD offset (±50 GDD)
    #   t_shift=+20 → later phenological transitions (cooler microclimate)
    #   t_shift=-15 → earlier transitions (warmer microclimate / heat island)
    gdd_veg = DEFAULT_CROP_PARAMS["gdd_vegetative"] + t_shift
    gdd_flo = DEFAULT_CROP_PARAMS["gdd_flowering"] + t_shift
    gdd_rip = DEFAULT_CROP_PARAMS["gdd_ripening"] + t_shift
    gdd_sen = DEFAULT_CROP_PARAMS["gdd_senescence"] + t_shift

    overrides = {
        "whc_mm_per_m": round(whc, 1),
        "t_max": round(max(25.0, t_max), 1),  # Floor at 25°C
        "lai_growth_rate": round(lai_growth_rate, 5),
        "gdd_vegetative": max(50, round(gdd_veg)),
        "gdd_flowering": max(200, round(gdd_flo)),
        "gdd_ripening": max(400, round(gdd_rip)),
        "gdd_senescence": max(600, round(gdd_sen)),
    }

    logger.info(
        f"DNA→CropParams: WHC={overrides['whc_mm_per_m']}mm/m "
        f"t_max={overrides['t_max']}°C "
        f"LAI_rate={overrides['lai_growth_rate']} "
        f"GDD_veg={overrides['gdd_vegetative']}"
    )
    return overrides


def dna_quality_to_noise_inflation(dna_result: Dict[str, Any]) -> float:
    """
    Compute Kalman process noise inflation factor from DNA data quality.

    When the underlying weather/NDVI data used for DNA sequencing had
    significant null-fills, we inflate the process noise Q to express
    reduced confidence in the DNA-derived parameters.

    Returns:
        Noise multiplier: 1.0 (clean data) to 3.0 (heavily degraded).
    """
    quality = dna_result.get("data_quality", {})
    null_pct = quality.get("weather_null_fill_pct", 0.0)
    ndvi_obs = quality.get("ndvi_observations", 100)

    # Null-fill contribution: 0% → 1.0x, 50% → 2.0x, 100% → 3.0x
    null_factor = 1.0 + (null_pct / 50.0)

    # Observation sparsity contribution: <30 obs in 5yr → inflate
    if ndvi_obs < 30:
        sparse_factor = 1.0 + (30 - ndvi_obs) / 30.0
    else:
        sparse_factor = 1.0

    factor = min(3.0, max(1.0, null_factor * sparse_factor))

    if factor > 1.1:
        logger.info(
            f"DNA noise inflation: {factor:.2f}x "
            f"(null_pct={null_pct:.1f}%, ndvi_obs={ndvi_obs})"
        )

    return round(factor, 3)


def _hash_dna_traits(dna_result: Dict[str, Any]) -> str:
    """Deterministic hash of DNA traits for invalidation checks."""
    traits = dna_result.get("traits", {})
    raw = json.dumps(traits, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def get_dna_hash(plot_id: str, cache_dir: Optional[str] = None) -> Optional[str]:
    """
    Get the trait hash from a cached DNA result without loading the full payload.
    Used by state_persistence for invalidation checks.
    """
    cache_dir = cache_dir or _DEFAULT_CACHE_DIR
    fname = f"dna_{plot_id}.json"
    fpath = os.path.join(cache_dir, fname)

    if not os.path.exists(fpath):
        return None

    try:
        with open(fpath, "r") as f:
            envelope = json.load(f)
        return envelope.get("dna_hash")
    except Exception:
        return None
