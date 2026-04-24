"""
Satellite RGB V1 Benchmark Cases — satrgb_benchmark_v1

Frozen benchmark pack for the Satellite RGB structural perception engine.
30+ synthetic pixel cases across 7 slices:

  Slice 1: Dense vegetation
  Slice 2: Sparse / stressed vegetation
  Slice 3: Bare soil / fallow / pre-planting
  Slice 4: Mixed scenes
  Slice 5: Cloud / haze / contamination
  Slice 6: Boundary / small-plot / contamination
  Slice 7: Phenology ordering

Each case provides:
  - Synthetic RGB pixel grids (40×40 default)
  - Ground truth: vegetation fraction, soil fraction, density class,
    phenology stage, anomaly expected, boundary expected
  - QA inputs: cloud_estimate, ground_resolution_m, recentness_days, etc.

DO NOT SILENTLY MUTATE THIS FILE after baseline is frozen.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import math
import random


@dataclass
class SatRGBBenchmarkCase:
    """Single benchmark case for Satellite RGB V1."""
    case_id: str
    description: str
    slice_name: str

    # Ground truth
    gt_vegetation_fraction: float      # 0.0–1.0
    gt_soil_fraction: float            # 0.0–1.0
    gt_density_class: str              # "bare", "sparse", "moderate", "dense"
    gt_phenology_stage: float          # 0=dormant → 4=senescence
    gt_anomaly_expected: bool          # True = anomaly should be elevated
    gt_boundary_contamination: bool    # True = boundary score should be > 0

    # QA inputs
    cloud_estimate: float = 0.02
    ground_resolution_m: float = 10.0
    recentness_days: int = 2
    plot_area_ha: Optional[float] = None
    haze_score: Optional[float] = None
    sun_angle: Optional[float] = None

    # Expected QA behavior
    gt_qa_usable: bool = True          # True = engine should produce packets
    gt_qa_downgraded: bool = False     # True = QA should be significantly reduced

    # Image dimensions
    image_width: int = 40
    image_height: int = 40

    # Pixel generation parameters
    rgb_mean: tuple = (0.3, 0.4, 0.2)     # (R, G, B) mean values 0–1
    rgb_noise_std: float = 0.02            # per-channel noise
    pattern: str = "uniform"               # "uniform", "patchy", "gradient", "banded"
    patch_fraction: float = 0.0            # fraction of pixels with alternate color
    patch_rgb: tuple = (0.4, 0.2, 0.15)    # alternate patch color

    notes: str = ""


def _generate_pixel_grid(case: SatRGBBenchmarkCase) -> Dict[str, Any]:
    """Generate synthetic RGB pixel grid from case parameters."""
    h, w = case.image_height, case.image_width
    # Use deterministic seed (hash() is randomized per-process in Python 3.3+)
    import hashlib
    seed = int(hashlib.md5(case.case_id.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    red = [[0.0] * w for _ in range(h)]
    green = [[0.0] * w for _ in range(h)]
    blue = [[0.0] * w for _ in range(h)]

    r_mean, g_mean, b_mean = case.rgb_mean
    noise = case.rgb_noise_std

    for r in range(h):
        for c in range(w):
            # Determine base color
            if case.pattern == "patchy" and rng.random() < case.patch_fraction:
                base_r, base_g, base_b = case.patch_rgb
            elif case.pattern == "gradient":
                # Vertical gradient: top = green, bottom = brown
                t = r / max(h - 1, 1)
                base_r = r_mean * (1 - t) + case.patch_rgb[0] * t
                base_g = g_mean * (1 - t) + case.patch_rgb[1] * t
                base_b = b_mean * (1 - t) + case.patch_rgb[2] * t
            elif case.pattern == "banded":
                # Horizontal bands: alternating veg/soil
                band = (r // 5) % 2
                if band == 1:
                    base_r, base_g, base_b = case.patch_rgb
                else:
                    base_r, base_g, base_b = r_mean, g_mean, b_mean
            else:
                base_r, base_g, base_b = r_mean, g_mean, b_mean

            # Add noise
            red[r][c] = max(0.0, min(1.0, base_r + rng.gauss(0, noise)))
            green[r][c] = max(0.0, min(1.0, base_g + rng.gauss(0, noise)))
            blue[r][c] = max(0.0, min(1.0, base_b + rng.gauss(0, noise)))

    return {"red": red, "green": green, "blue": blue}


# ============================================================================
# Slice 1: Dense vegetation
# ============================================================================

DENSE_VEG_CASES = [
    SatRGBBenchmarkCase(
        case_id="dense_maize_canopy",
        description="Dense maize canopy, peak vegetative stage",
        slice_name="dense_vegetation",
        gt_vegetation_fraction=0.98,
        gt_soil_fraction=0.00,
        gt_density_class="dense",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.15, 0.52, 0.12),
        rgb_noise_std=0.03,
        notes="High green, low red/blue — textbook dense canopy",
    ),
    SatRGBBenchmarkCase(
        case_id="dense_wheat_canopy",
        description="Dense wheat canopy, strong vegetative growth",
        slice_name="dense_vegetation",
        gt_vegetation_fraction=0.98,
        gt_soil_fraction=0.00,
        gt_density_class="dense",
        gt_phenology_stage=2.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.18, 0.48, 0.14),
        rgb_noise_std=0.03,
        notes="Wheat is slightly less green than maize",
    ),
    SatRGBBenchmarkCase(
        case_id="dense_orchard_canopy",
        description="Dense orchard/tree crop, full canopy cover",
        slice_name="dense_vegetation",
        gt_vegetation_fraction=0.97,
        gt_soil_fraction=0.00,
        gt_density_class="dense",
        gt_phenology_stage=2.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.12, 0.50, 0.10),
        rgb_noise_std=0.04,
        notes="Dark green orchard canopy, higher variance from tree structure",
    ),
    SatRGBBenchmarkCase(
        case_id="dense_rice_paddy",
        description="Dense rice paddy, full cover",
        slice_name="dense_vegetation",
        gt_vegetation_fraction=0.98,
        gt_soil_fraction=0.00,
        gt_density_class="dense",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.14, 0.55, 0.15),
        rgb_noise_std=0.02,
        notes="Very high green, uniform — rice paddy signature",
    ),
]

# ============================================================================
# Slice 2: Sparse / stressed vegetation
# ============================================================================

SPARSE_STRESS_CASES = [
    SatRGBBenchmarkCase(
        case_id="sparse_emergence",
        description="Early crop emergence, sparse seedlings on soil",
        slice_name="sparse_stressed",
        gt_vegetation_fraction=0.25,
        gt_soil_fraction=0.60,
        gt_density_class="sparse",
        gt_phenology_stage=0.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.35, 0.25, 0.18),
        rgb_noise_std=0.03,
        pattern="patchy", patch_fraction=0.25,
        patch_rgb=(0.15, 0.45, 0.12),
        notes="Mostly soil with scattered green seedling patches",
    ),
    SatRGBBenchmarkCase(
        case_id="drought_stressed",
        description="Drought-stressed canopy, yellowing and gaps",
        slice_name="sparse_stressed",
        gt_vegetation_fraction=0.40,
        gt_soil_fraction=0.40,
        gt_density_class="moderate",
        gt_phenology_stage=2.5,
        gt_anomaly_expected=True,
        gt_boundary_contamination=False,
        rgb_mean=(0.40, 0.28, 0.16),
        rgb_noise_std=0.06,
        pattern="patchy", patch_fraction=0.40,
        patch_rgb=(0.15, 0.48, 0.12),
        notes="40% green patches on brown stressed base",
    ),
    SatRGBBenchmarkCase(
        case_id="gap_heavy_stand",
        description="Crop with heavy gaps (missing plants/rows)",
        slice_name="sparse_stressed",
        gt_vegetation_fraction=0.45,
        gt_soil_fraction=0.45,
        gt_density_class="moderate",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=True,
        gt_boundary_contamination=False,
        rgb_mean=(0.40, 0.26, 0.18),
        rgb_noise_std=0.04,
        pattern="banded",
        patch_rgb=(0.15, 0.48, 0.12),
        notes="Alternating green rows / brown gaps",
    ),
    SatRGBBenchmarkCase(
        case_id="sparse_cover",
        description="Very sparse ground cover, mostly visible soil",
        slice_name="sparse_stressed",
        gt_vegetation_fraction=0.15,
        gt_soil_fraction=0.70,
        gt_density_class="sparse",
        gt_phenology_stage=0.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.38, 0.24, 0.16),
        rgb_noise_std=0.03,
        pattern="patchy", patch_fraction=0.15,
        patch_rgb=(0.12, 0.46, 0.10),
        notes="Mostly bare with rare green patches",
    ),
]

# ============================================================================
# Slice 3: Bare soil / fallow / pre-planting
# ============================================================================

BARE_SOIL_CASES = [
    SatRGBBenchmarkCase(
        case_id="dry_brown_soil",
        description="Dry brown fallow field, no vegetation",
        slice_name="bare_soil",
        gt_vegetation_fraction=0.05,
        gt_soil_fraction=0.93,
        gt_density_class="bare",
        gt_phenology_stage=0.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.45, 0.28, 0.18),
        rgb_noise_std=0.03,
        notes="Brown earth tones, no green — distinct from senescent crop",
    ),
    SatRGBBenchmarkCase(
        case_id="wet_dark_soil",
        description="Wet dark soil after rain, pre-planting",
        slice_name="bare_soil",
        gt_vegetation_fraction=0.00,
        gt_soil_fraction=0.98,
        gt_density_class="bare",
        gt_phenology_stage=0.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.18, 0.15, 0.12),
        rgb_noise_std=0.02,
        notes="Very dark, low brightness — saturated soil",
    ),
    SatRGBBenchmarkCase(
        case_id="sandy_soil",
        description="Sandy pale soil, arid/semi-arid region",
        slice_name="bare_soil",
        gt_vegetation_fraction=0.05,
        gt_soil_fraction=0.92,
        gt_density_class="bare",
        gt_phenology_stage=0.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.55, 0.48, 0.40),
        rgb_noise_std=0.03,
        notes="Pale, high brightness — sandy substrate",
    ),
    SatRGBBenchmarkCase(
        case_id="post_harvest_stubble",
        description="Post-harvest field with crop stubble residue",
        slice_name="bare_soil",
        gt_vegetation_fraction=0.30,
        gt_soil_fraction=0.65,
        gt_density_class="sparse",
        gt_phenology_stage=4.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.40, 0.32, 0.22),
        rgb_noise_std=0.04,
        pattern="patchy", patch_fraction=0.08,
        patch_rgb=(0.25, 0.38, 0.18),
        notes="Mostly brown with tiny green patches from stubble regrowth",
    ),
]

# ============================================================================
# Slice 4: Mixed scenes
# ============================================================================

MIXED_CASES = [
    SatRGBBenchmarkCase(
        case_id="crop_soil_mosaic",
        description="50/50 crop-soil mosaic, mid-season transition",
        slice_name="mixed",
        gt_vegetation_fraction=0.60,
        gt_soil_fraction=0.35,
        gt_density_class="moderate",
        gt_phenology_stage=1.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.20, 0.42, 0.14),
        rgb_noise_std=0.03,
        pattern="patchy", patch_fraction=0.40,
        patch_rgb=(0.40, 0.28, 0.18),
        notes="Mixed green/brown mosaic",
    ),
    SatRGBBenchmarkCase(
        case_id="weed_patches",
        description="Field with weed patches (heterogeneous green)",
        slice_name="mixed",
        gt_vegetation_fraction=0.95,
        gt_soil_fraction=0.02,
        gt_density_class="dense",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=True,
        gt_boundary_contamination=False,
        rgb_mean=(0.18, 0.44, 0.12),
        rgb_noise_std=0.07,
        notes="All-green uniform base — anomaly from variance not gaps",
    ),
    SatRGBBenchmarkCase(
        case_id="partial_canopy",
        description="Partial canopy, crop establishing but incomplete",
        slice_name="mixed",
        gt_vegetation_fraction=0.70,
        gt_soil_fraction=0.25,
        gt_density_class="dense",
        gt_phenology_stage=1.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.22, 0.40, 0.15),
        rgb_noise_std=0.04,
        pattern="patchy", patch_fraction=0.30,
        patch_rgb=(0.38, 0.26, 0.18),
        notes="Growing canopy with visible soil gaps",
    ),
    SatRGBBenchmarkCase(
        case_id="transitional_growth",
        description="Transitional growth stage — greening up from dormancy",
        slice_name="mixed",
        gt_vegetation_fraction=0.50,
        gt_soil_fraction=0.40,
        gt_density_class="moderate",
        gt_phenology_stage=0.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.15, 0.48, 0.12),
        rgb_noise_std=0.04,
        pattern="gradient",
        patch_rgb=(0.42, 0.28, 0.18),
        notes="Top=green, bottom=brown gradient",
    ),
]

# ============================================================================
# Slice 5: Cloud / haze / contamination
# ============================================================================

CLOUD_HAZE_CASES = [
    SatRGBBenchmarkCase(
        case_id="thin_cloud",
        description="Thin translucent cloud over crop field",
        slice_name="cloud_haze",
        gt_vegetation_fraction=0.90,
        gt_soil_fraction=0.02,
        gt_density_class="dense",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        cloud_estimate=0.35,
        gt_qa_usable=True,
        gt_qa_downgraded=True,
        rgb_mean=(0.30, 0.38, 0.28),
        rgb_noise_std=0.02,
        notes="Washed out but still green-dominant — QA should downgrade",
    ),
    SatRGBBenchmarkCase(
        case_id="heavy_cloud",
        description="Heavy cloud cover, most of plot obscured",
        slice_name="cloud_haze",
        gt_vegetation_fraction=0.0,
        gt_soil_fraction=0.0,
        gt_density_class="bare",
        gt_phenology_stage=0.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        cloud_estimate=0.80,
        gt_qa_usable=False,
        gt_qa_downgraded=True,
        rgb_mean=(0.65, 0.65, 0.65),
        rgb_noise_std=0.02,
        notes="White/gray — should be rejected as unusable",
    ),
    SatRGBBenchmarkCase(
        case_id="strong_haze",
        description="Strong atmospheric haze over field",
        slice_name="cloud_haze",
        gt_vegetation_fraction=0.85,
        gt_soil_fraction=0.05,
        gt_density_class="dense",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        cloud_estimate=0.15,
        haze_score=0.60,
        gt_qa_usable=True,
        gt_qa_downgraded=True,
        rgb_mean=(0.32, 0.38, 0.30),
        rgb_noise_std=0.02,
        notes="Green-dominant through haze — reliability should drop",
    ),
    SatRGBBenchmarkCase(
        case_id="partial_cloud",
        description="Partial cloud shadow over half the plot",
        slice_name="cloud_haze",
        gt_vegetation_fraction=0.80,
        gt_soil_fraction=0.10,
        gt_density_class="dense",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=True,
        gt_boundary_contamination=False,
        cloud_estimate=0.45,
        gt_qa_usable=True,
        gt_qa_downgraded=True,
        rgb_mean=(0.22, 0.40, 0.16),
        rgb_noise_std=0.04,
        pattern="gradient",
        patch_rgb=(0.50, 0.50, 0.48),
        notes="Half green, half washed out — should trigger anomaly + QA",
    ),
]

# ============================================================================
# Slice 6: Boundary / small-plot / contamination
# ============================================================================

BOUNDARY_CASES = [
    SatRGBBenchmarkCase(
        case_id="heavy_edge_contamination",
        description="Small plot with heavy boundary contamination",
        slice_name="boundary",
        gt_vegetation_fraction=0.98,
        gt_soil_fraction=0.00,
        gt_density_class="dense",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=True,
        image_width=12, image_height=12,
        rgb_mean=(0.15, 0.50, 0.12),
        rgb_noise_std=0.03,
        notes="Small image → large boundary fraction from margin/edge masking",
    ),
    SatRGBBenchmarkCase(
        case_id="narrow_strip_plot",
        description="Narrow strip plot (pivot edge or trial strip)",
        slice_name="boundary",
        gt_vegetation_fraction=0.98,
        gt_soil_fraction=0.00,
        gt_density_class="dense",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=True,
        image_width=8, image_height=40,
        rgb_mean=(0.18, 0.46, 0.14),
        rgb_noise_std=0.03,
        notes="Very narrow — most pixels are edge or margin",
    ),
    SatRGBBenchmarkCase(
        case_id="too_small_plot",
        description="Tiny plot at coarse resolution — insufficient pixels",
        slice_name="boundary",
        gt_vegetation_fraction=0.0,
        gt_soil_fraction=0.0,
        gt_density_class="bare",
        gt_phenology_stage=0.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=True,
        image_width=6, image_height=6,
        ground_resolution_m=40.0,
        plot_area_ha=0.001,
        gt_qa_usable=False,
        gt_qa_downgraded=True,
        rgb_mean=(0.20, 0.45, 0.15),
        rgb_noise_std=0.03,
        notes="Too few pixels — QA should reject or heavily downgrade",
    ),
    SatRGBBenchmarkCase(
        case_id="normal_plot_clean_boundary",
        description="Normal-sized plot with clean interior, minimal edge effects",
        slice_name="boundary",
        gt_vegetation_fraction=0.98,
        gt_soil_fraction=0.00,
        gt_density_class="dense",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        image_width=50, image_height=50,
        rgb_mean=(0.15, 0.52, 0.12),
        rgb_noise_std=0.03,
        notes="Large plot — boundary fraction should be small",
    ),
]

# ============================================================================
# Slice 7: Phenology ordering
# ============================================================================

PHENOLOGY_CASES = [
    SatRGBBenchmarkCase(
        case_id="pheno_dormant",
        description="Dormant / bare field, winter season",
        slice_name="phenology",
        gt_vegetation_fraction=0.15,
        gt_soil_fraction=0.80,
        gt_density_class="sparse",
        gt_phenology_stage=0.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.35, 0.28, 0.20),
        rgb_noise_std=0.03,
        notes="Brown/gray, no green — dormant stage",
    ),
    SatRGBBenchmarkCase(
        case_id="pheno_early_vegetative",
        description="Early vegetative growth, emerging green",
        slice_name="phenology",
        gt_vegetation_fraction=0.30,
        gt_soil_fraction=0.55,
        gt_density_class="sparse",
        gt_phenology_stage=0.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.40, 0.26, 0.18),
        rgb_noise_std=0.03,
        pattern="patchy", patch_fraction=0.30,
        patch_rgb=(0.14, 0.50, 0.12),
        notes="30% green seedling patches on brown soil base",
    ),
    SatRGBBenchmarkCase(
        case_id="pheno_strong_vegetative",
        description="Strong vegetative growth, full green canopy",
        slice_name="phenology",
        gt_vegetation_fraction=0.98,
        gt_soil_fraction=0.00,
        gt_density_class="dense",
        gt_phenology_stage=1.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.14, 0.54, 0.12),
        rgb_noise_std=0.02,
        notes="Peak green — strong vegetative",
    ),
    SatRGBBenchmarkCase(
        case_id="pheno_flowering",
        description="Flowering / peak canopy, beginning color shift",
        slice_name="phenology",
        gt_vegetation_fraction=0.98,
        gt_soil_fraction=0.00,
        gt_density_class="dense",
        gt_phenology_stage=2.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.20, 0.45, 0.15),
        rgb_noise_std=0.03,
        notes="Still green but starting to shift — mid-season",
    ),
    SatRGBBenchmarkCase(
        case_id="pheno_ripening",
        description="Ripening / yellowing, senescence beginning",
        slice_name="phenology",
        gt_vegetation_fraction=0.40,
        gt_soil_fraction=0.45,
        gt_density_class="moderate",
        gt_phenology_stage=3.0,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.42, 0.30, 0.18),
        rgb_noise_std=0.04,
        pattern="patchy", patch_fraction=0.40,
        patch_rgb=(0.20, 0.42, 0.14),
        notes="40% remaining green patches on yellowing/brown base",
    ),
    SatRGBBenchmarkCase(
        case_id="pheno_senescent",
        description="Full senescence / dry standing crop",
        slice_name="phenology",
        gt_vegetation_fraction=0.10,
        gt_soil_fraction=0.60,
        gt_density_class="sparse",
        gt_phenology_stage=3.5,
        gt_anomaly_expected=False,
        gt_boundary_contamination=False,
        rgb_mean=(0.42, 0.30, 0.20),
        rgb_noise_std=0.03,
        notes="Brown/dry — very low green ratio, high brightness",
    ),
]


# ============================================================================
# Master case list
# ============================================================================

BENCHMARK_CASES: List[SatRGBBenchmarkCase] = (
    DENSE_VEG_CASES
    + SPARSE_STRESS_CASES
    + BARE_SOIL_CASES
    + MIXED_CASES
    + CLOUD_HAZE_CASES
    + BOUNDARY_CASES
    + PHENOLOGY_CASES
)

BENCHMARK_VERSION = "satrgb_benchmark_v1"
