"""
Satellite RGB Perception Engine — Source Policy Configuration.

This file is the authoritative source for all acquisition, quality,
and freshness policy decisions for the Satellite RGB engine.

Rationale: without a single policy file, source-policy tends to drift
across QA thresholds, cache TTLs, and engine defaults.

Production free-source policy:
  Primary  -> Sentinel-2 (ESA Copernicus, 10m resolution, 5-day revisit)
  Fallback -> Landsat 8 / 9 (USGS, 30m resolution, 16-day revisit)

Test policy:
  Synthetic fixture grids / local pinned RGB samples only.
  No basemap tile ingestion (Google/Mapbox/Esri tiles are basemaps,
  not scientific ingestion sources for this engine).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ============================================================================
# Provider Specifications
# ============================================================================

@dataclass(frozen=True)
class ProviderSpec:
    """Immutable specification for one satellite RGB provider."""
    name: str
    typical_resolution_m: float       # native GSD in meters
    max_resolution_m: float           # coarsest acceptable resolution (meters)
    revisit_days: int                  # nominal revisit period
    max_age_days: int                  # hard max acquisition age for production use
    min_coverage_fraction: float       # minimum fraction of plot covered by valid pixels
    min_plot_pixel_count: int          # absolute minimum pixels inside plot polygon
    notes: str = ""


PROVIDER_SPECS: Dict[str, ProviderSpec] = {
    "sentinel2": ProviderSpec(
        name="Sentinel-2",
        typical_resolution_m=10.0,
        max_resolution_m=20.0,      # 20m bands (SWIR) — still acceptable
        revisit_days=5,
        max_age_days=20,            # For crop-season decisions, 20d is the hard limit
        min_coverage_fraction=0.7,
        min_plot_pixel_count=16,
        notes="ESA Copernicus. Primary free source. Bands: B02/B03/B04 for RGB.",
    ),
    "landsat8": ProviderSpec(
        name="Landsat 8",
        typical_resolution_m=30.0,
        max_resolution_m=30.0,
        revisit_days=16,
        max_age_days=35,            # Longer revisit -> allow older acquisition
        min_coverage_fraction=0.6,
        min_plot_pixel_count=9,
        notes="USGS. Fallback free source. Bands: B4/B3/B2 for RGB.",
    ),
    "landsat9": ProviderSpec(
        name="Landsat 9",
        typical_resolution_m=30.0,
        max_resolution_m=30.0,
        revisit_days=16,
        max_age_days=35,
        min_coverage_fraction=0.6,
        min_plot_pixel_count=9,
        notes="USGS. Fallback free source (upgraded successor to Landsat 8).",
    ),
    "synthetic": ProviderSpec(
        name="Synthetic",
        typical_resolution_m=10.0,
        max_resolution_m=100.0,
        revisit_days=0,
        max_age_days=9999,
        min_coverage_fraction=0.0,
        min_plot_pixel_count=1,
        notes="Synthetic fixtures for testing only. Not for production use.",
    ),
    "other": ProviderSpec(
        name="Other",
        typical_resolution_m=10.0,
        max_resolution_m=30.0,
        revisit_days=5,
        max_age_days=20,
        min_coverage_fraction=0.7,
        min_plot_pixel_count=16,
        notes="Any other georeferenced RGB. Falls back to Sentinel-2 policy.",
    ),
}

# Ordered preference: engine will prefer providers earlier in this list
PROVIDER_PREFERENCE_ORDER: List[str] = [
    "sentinel2",
    "landsat9",
    "landsat8",
    "other",
    # synthetic is never selected in production — test-only
]


# ============================================================================
# Freshness Policy
# ============================================================================

@dataclass(frozen=True)
class FreshnessPolicy:
    """
    Acquisition freshness thresholds.

    These drive the recentness_score in SatelliteRGBQA and determine
    how stale an image can be before being rejected / heavily downgraded.
    """
    fresh_days: int = 5        # ≤ this -> full recentness score
    moderate_days: int = 15    # ≤ this -> moderate recentness (0.8)
    stale_days: int = 30       # ≤ this -> stale (0.5)
    unusable_days: int = 90    # > this -> near-zero recentness; strongly discouraged


FRESHNESS_POLICY = FreshnessPolicy()


# ============================================================================
# Coverage Policy
# ============================================================================

@dataclass(frozen=True)
class CoveragePolicy:
    """
    Minimum spatial coverage requirements for plot-level analysis.

    These are per-engine minimums. Provider-specific overrides are in
    PROVIDER_SPECS above.
    """
    # Absolute minimums — engine will reject (qa=0) below these
    absolute_min_pixels: int = 4
    absolute_min_coverage_fraction: float = 0.1

    # Good-quality thresholds — engine expects these for reliable results
    good_min_pixels: int = 25
    good_min_coverage_fraction: float = 0.7

    # Row detection requires higher pixel density
    row_detection_min_pixels: int = 100
    row_detection_max_resolution_m: float = 2.0      # V1.5 cutoff


COVERAGE_POLICY = CoveragePolicy()


# ============================================================================
# Convenience helpers
# ============================================================================

def get_provider_spec(provider_name: str) -> ProviderSpec:
    """Get the spec for a provider, falling back to 'other'."""
    return PROVIDER_SPECS.get(provider_name.lower(), PROVIDER_SPECS["other"])


def check_provider_policy(
    provider_name: str,
    ground_resolution_m: float,
    recentness_days: Optional[int],
    coverage_fraction: Optional[float],
    pixel_count: Optional[int],
) -> List[str]:
    """
    Check a satellite RGB acquisition against provider policy.

    Returns a list of policy violations (empty = all clear).
    """
    spec = get_provider_spec(provider_name)
    violations: List[str] = []

    if ground_resolution_m > spec.max_resolution_m:
        violations.append(
            f"Resolution {ground_resolution_m}m exceeds {spec.name} max "
            f"{spec.max_resolution_m}m"
        )

    if recentness_days is not None and recentness_days > spec.max_age_days:
        violations.append(
            f"Acquisition age {recentness_days}d exceeds {spec.name} max "
            f"{spec.max_age_days}d"
        )

    if coverage_fraction is not None and coverage_fraction < spec.min_coverage_fraction:
        violations.append(
            f"Coverage {coverage_fraction:.0%} below {spec.name} minimum "
            f"{spec.min_coverage_fraction:.0%}"
        )

    if pixel_count is not None and pixel_count < spec.min_plot_pixel_count:
        violations.append(
            f"Pixel count {pixel_count} below {spec.name} minimum "
            f"{spec.min_plot_pixel_count}"
        )

    return violations
