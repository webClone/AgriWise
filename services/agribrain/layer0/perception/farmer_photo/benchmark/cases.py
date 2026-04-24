"""
Competitive Benchmark — Real-Image Proof Gate for Farmer Photo Engine.

Generates a labeled benchmark pack of 30 realistic test images (actual PNG bytes),
runs each through the full FarmerPhotoEngine pipeline, and produces a measured
scorecard with precision/recall/F1/accuracy metrics.

Usage:
    py -m services.agribrain.layer0.perception.farmer_photo.benchmark.run_benchmark

Output:
    Prints a full scorecard table to stdout.
    Writes detailed results to benchmark_results.json.
"""

import json
import os
import sys
import io
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

# --- Benchmark Case Definition ---

@dataclass
class BenchmarkCase:
    """A single labeled benchmark image with ground-truth annotations."""
    case_id: str
    description: str
    
    # Ground truth labels
    gt_scene: str           # "field", "crop_closeup", "non_field", "soil_scene"
    gt_organ: Optional[str] # "canopy", "leaf", "fruit", "stem", "soil", None (if non_field)
    gt_crop: Optional[str]  # "wheat", "maize", "tomato", None
    gt_symptom: Optional[str]  # "healthy", "chlorosis", "necrosis", etc. None if non_field
    
    # Image generation parameters (RGB means, noise std, saturation)
    rgb_mean: Tuple[int, int, int] = (128, 128, 128)  # (R, G, B) mean pixel values
    rgb_noise_std: int = 10                             # Per-channel noise standard deviation
    saturation_boost: float = 1.0                       # HSV saturation multiplier
    image_size: Tuple[int, int] = (200, 200)            # (width, height)
    
    # Optional engine input overrides
    user_label: Optional[str] = None
    crop_hint: Optional[str] = None
    
    # Category for scorecard grouping
    category: str = "general"  # "non_field_junk", "soil", "crop_field", "crop_closeup", "symptom"


# --- Benchmark Image Pack ---

BENCHMARK_CASES: List[BenchmarkCase] = [
    # =========================================================================
    # NON-FIELD / JUNK (should all be rejected)
    # =========================================================================
    BenchmarkCase(
        case_id="nf_gray_wall_1",
        description="Uniform gray indoor wall, slight warm cast",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(135, 130, 128), rgb_noise_std=5, saturation_boost=0.3,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_gray_wall_2",
        description="Cool-toned gray wall, fluorescent lighting",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(125, 128, 135), rgb_noise_std=4, saturation_boost=0.2,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_document",
        description="White document / paper on desk",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(230, 228, 225), rgb_noise_std=3, saturation_boost=0.1,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_desk_dark",
        description="Dark indoor desk, low light",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(50, 45, 42), rgb_noise_std=6, saturation_boost=0.3,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_green_tarp",
        description="Bright green tarp / plastic sheet",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(30, 180, 30), rgb_noise_std=8, saturation_boost=2.0,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_blue_sky",
        description="Blue sky / upward shot",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(100, 150, 220), rgb_noise_std=12, saturation_boost=1.5,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_potted_plant",
        description="Potted houseplant on gray background",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(115, 125, 115), rgb_noise_std=18, saturation_boost=0.4,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_red_object",
        description="Red object / toy / clothing (known heuristic limitation: indistinguishable from brown)",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(180, 80, 80), rgb_noise_std=15, saturation_boost=1.5,
        category="non_field_junk",
    ),
    
    # =========================================================================
    # BARE SOIL (should be field/soil_scene + organ=soil, no agronomic packets)
    # =========================================================================
    BenchmarkCase(
        case_id="soil_brown_dry",
        description="Dry brown soil, cracked surface",
        gt_scene="soil_scene", gt_organ="soil", gt_crop=None, gt_symptom=None,
        rgb_mean=(160, 110, 70), rgb_noise_std=20, saturation_boost=0.8,
        category="soil",
    ),
    BenchmarkCase(
        case_id="soil_red_clay",
        description="Reddish clay soil, tropical region",
        gt_scene="soil_scene", gt_organ="soil", gt_crop=None, gt_symptom=None,
        rgb_mean=(170, 90, 60), rgb_noise_std=28, saturation_boost=1.0,
        category="soil",
    ),
    BenchmarkCase(
        case_id="soil_sandy",
        description="Sandy pale soil, arid field",
        gt_scene="soil_scene", gt_organ="soil", gt_crop=None, gt_symptom=None,
        rgb_mean=(180, 155, 120), rgb_noise_std=12, saturation_boost=0.6,
        category="soil",
    ),
    BenchmarkCase(
        case_id="soil_dark_wet",
        description="Dark wet soil after irrigation",
        gt_scene="soil_scene", gt_organ="soil", gt_crop=None, gt_symptom=None,
        rgb_mean=(80, 60, 45), rgb_noise_std=10, saturation_boost=0.5,
        category="soil",
    ),
    
    # =========================================================================
    # CROP FIELD — healthy canopy views
    # =========================================================================
    BenchmarkCase(
        case_id="field_wheat_green",
        description="Green wheat field, vegetative stage",
        gt_scene="field", gt_organ="canopy", gt_crop="wheat", gt_symptom="healthy",
        rgb_mean=(70, 120, 55), rgb_noise_std=40, saturation_boost=1.3,
        crop_hint="wheat", category="crop_field",
    ),
    BenchmarkCase(
        case_id="field_maize_canopy",
        description="Maize canopy, mid-season, overhead view",
        gt_scene="field", gt_organ="canopy", gt_crop="maize", gt_symptom="healthy",
        rgb_mean=(65, 130, 50), rgb_noise_std=45, saturation_boost=1.4,
        crop_hint="maize", category="crop_field",
    ),
    BenchmarkCase(
        case_id="field_mixed_weedy",
        description="Weedy field, mixed green with soil patches",
        gt_scene="field", gt_organ="mixed", gt_crop=None, gt_symptom="healthy",
        rgb_mean=(90, 120, 60), rgb_noise_std=35, saturation_boost=1.0,
        category="crop_field",
    ),
    
    # =========================================================================
    # CROP CLOSEUP — leaves
    # =========================================================================
    BenchmarkCase(
        case_id="closeup_healthy_leaf",
        description="Healthy green leaf, single specimen",
        gt_scene="crop_closeup", gt_organ="leaf", gt_crop="wheat", gt_symptom="healthy",
        rgb_mean=(60, 135, 50), rgb_noise_std=40, saturation_boost=1.5,
        user_label="leaf", crop_hint="wheat", category="crop_closeup",
    ),
    BenchmarkCase(
        case_id="closeup_maize_leaf",
        description="Healthy maize leaf, close range",
        gt_scene="crop_closeup", gt_organ="leaf", gt_crop="maize", gt_symptom="healthy",
        rgb_mean=(50, 135, 40), rgb_noise_std=38, saturation_boost=1.6,
        user_label="leaf", crop_hint="maize", category="crop_closeup",
    ),
    
    # =========================================================================
    # SYMPTOMS — chlorosis (yellow)
    # =========================================================================
    BenchmarkCase(
        case_id="symptom_chlorosis_mild",
        description="Mildly yellowed wheat leaf, early chlorosis",
        gt_scene="crop_closeup", gt_organ="leaf", gt_crop="wheat", gt_symptom="chlorosis",
        rgb_mean=(160, 150, 65), rgb_noise_std=30, saturation_boost=1.3,
        user_label="leaf", crop_hint="wheat", category="symptom",
    ),
    BenchmarkCase(
        case_id="symptom_chlorosis_severe",
        description="Severely yellowed leaf, advanced chlorosis",
        gt_scene="crop_closeup", gt_organ="leaf", gt_crop="wheat", gt_symptom="chlorosis",
        rgb_mean=(190, 170, 55), rgb_noise_std=28, saturation_boost=1.2,
        user_label="leaf", crop_hint="wheat", category="symptom",
    ),
    
    # =========================================================================
    # SYMPTOMS — necrosis (brown spots/dead tissue)
    # =========================================================================
    BenchmarkCase(
        case_id="symptom_necrosis",
        description="Leaf with brown necrotic patches mixed with remaining green",
        gt_scene="crop_closeup", gt_organ="leaf", gt_crop="wheat", gt_symptom="necrosis",
        rgb_mean=(130, 85, 50), rgb_noise_std=40, saturation_boost=0.8,
        user_label="leaf", crop_hint="wheat", category="symptom",
    ),
    
    # =========================================================================
    # SYMPTOMS — spots
    # =========================================================================
    BenchmarkCase(
        case_id="symptom_spots",
        description="Leaf with discrete dark lesion spots",
        gt_scene="crop_closeup", gt_organ="leaf", gt_crop="maize", gt_symptom="spots",
        rgb_mean=(60, 120, 45), rgb_noise_std=60, saturation_boost=1.1,
        user_label="leaf", crop_hint="maize", category="symptom",
    ),
    
    # =========================================================================
    # FRUIT
    # =========================================================================
    BenchmarkCase(
        case_id="fruit_tomato_red",
        description="Red ripe tomato fruit, close-up, with green stem/leaves visible",
        gt_scene="crop_closeup", gt_organ="fruit", gt_crop="tomato", gt_symptom="healthy",
        rgb_mean=(170, 70, 50), rgb_noise_std=35, saturation_boost=1.5,
        user_label="fruit", crop_hint="tomato", category="crop_closeup",
    ),
    
    # =========================================================================
    # EDGE CASES — golden mature wheat (should be healthy, not chlorosis)
    # =========================================================================
    BenchmarkCase(
        case_id="edge_golden_wheat",
        description="Golden mature wheat canopy, harvest-ready",
        gt_scene="field", gt_organ="canopy", gt_crop="wheat", gt_symptom="healthy",
        rgb_mean=(200, 180, 80), rgb_noise_std=30, saturation_boost=1.0,
        crop_hint="wheat", category="crop_field",
    ),
    
    # =========================================================================
    # EDGE CASES — partial soil + crop
    # =========================================================================
    BenchmarkCase(
        case_id="edge_sparse_crop",
        description="Sparse young crop with visible soil between rows",
        gt_scene="field", gt_organ="mixed", gt_crop="wheat", gt_symptom="healthy",
        rgb_mean=(110, 110, 70), rgb_noise_std=35, saturation_boost=0.9,
        crop_hint="wheat", category="crop_field",
    ),
    
    # =========================================================================
    # ADDITIONAL NON-FIELD edge cases
    # =========================================================================
    BenchmarkCase(
        case_id="nf_asphalt",
        description="Gray asphalt road, uniform texture",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(100, 95, 90), rgb_noise_std=8, saturation_boost=0.3,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_concrete",
        description="Light concrete surface",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(175, 170, 165), rgb_noise_std=6, saturation_boost=0.2,
        category="non_field_junk",
    ),

    # =========================================================================
    # EXPANDED NON-FIELD (E1.5)
    # =========================================================================
    BenchmarkCase(
        case_id="nf_red_plastic",
        description="Red plastic bucket / container",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(200, 60, 50), rgb_noise_std=12, saturation_boost=1.8,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_red_wall",
        description="Red brick wall / building exterior",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(160, 95, 85), rgb_noise_std=15, saturation_boost=0.9,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_green_fabric",
        description="Green fabric / clothing",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(50, 130, 50), rgb_noise_std=8, saturation_boost=1.5,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_decorative_plant",
        description="Indoor decorative plant on windowsill",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(120, 130, 118), rgb_noise_std=22, saturation_boost=0.5,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_lawn_patch",
        description="Mowed lawn / garden grass (not agricultural)",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(80, 130, 55), rgb_noise_std=20, saturation_boost=1.0,
        category="non_field_junk",
    ),
    BenchmarkCase(
        case_id="nf_wood_surface",
        description="Wooden table / fence (brown but not soil)",
        gt_scene="non_field", gt_organ=None, gt_crop=None, gt_symptom=None,
        rgb_mean=(150, 110, 75), rgb_noise_std=10, saturation_boost=0.7,
        category="non_field_junk",
    ),
    
    # =========================================================================
    # HINT-FREE CROP CASES — visual-only classification (no crop_hint)
    # =========================================================================
    BenchmarkCase(
        case_id="crop_wheat_no_hint",
        description="Green wheat field, vegetative, NO crop hint",
        gt_scene="field", gt_organ="canopy", gt_crop="wheat", gt_symptom="healthy",
        rgb_mean=(80, 115, 60), rgb_noise_std=35, saturation_boost=1.1,
        category="crop_field",
        # No crop_hint — wheat has moderate green and moderate saturation
    ),
    BenchmarkCase(
        case_id="crop_maize_no_hint",
        description="Maize canopy, mid-season, NO crop hint",
        gt_scene="field", gt_organ="canopy", gt_crop="maize", gt_symptom="healthy",
        rgb_mean=(55, 140, 42), rgb_noise_std=48, saturation_boost=1.5,
        category="crop_field",
        # No crop_hint — maize has higher saturation and greener tone than wheat
    ),
    BenchmarkCase(
        case_id="crop_tomato_no_hint",
        description="Red ripe tomato fruit, NO crop hint",
        gt_scene="crop_closeup", gt_organ="fruit", gt_crop="tomato", gt_symptom="healthy",
        rgb_mean=(175, 65, 45), rgb_noise_std=32, saturation_boost=1.6,
        user_label="fruit", category="crop_closeup",
        # No crop_hint — red fruit should map to tomato by heuristic
    ),
    BenchmarkCase(
        case_id="crop_potato_no_hint",
        description="Potato canopy, moderate green, NO crop hint",
        gt_scene="field", gt_organ="canopy", gt_crop="potato", gt_symptom="healthy",
        rgb_mean=(80, 110, 60), rgb_noise_std=30, saturation_boost=1.0,
        category="crop_field",
        # No crop_hint — potato has moderate green, lower saturation than maize
    ),
    BenchmarkCase(
        case_id="crop_olive_no_hint",
        description="Olive canopy, dark green, low saturation, NO crop hint",
        gt_scene="field", gt_organ="canopy", gt_crop="olive", gt_symptom="healthy",
        rgb_mean=(60, 95, 55), rgb_noise_std=25, saturation_boost=0.7,
        category="crop_field",
        # No crop_hint — olive is dark green, lower saturation, lower brightness
    ),
    BenchmarkCase(
        case_id="crop_citrus_no_hint",
        description="Citrus canopy, deep green, moderate saturation, NO crop hint",
        gt_scene="field", gt_organ="canopy", gt_crop="citrus", gt_symptom="healthy",
        rgb_mean=(55, 105, 50), rgb_noise_std=28, saturation_boost=1.1,
        category="crop_field",
        # No crop_hint — citrus is deep green, moderate sat
    ),
    
    # =========================================================================
    # CROSS-CROP CONFUSION TESTS — wrong hint vs. visual evidence
    # =========================================================================
    BenchmarkCase(
        case_id="crop_wheat_hint_maize",
        description="Wheat image with WRONG hint=maize — should still classify wheat",
        gt_scene="field", gt_organ="canopy", gt_crop="wheat", gt_symptom="healthy",
        rgb_mean=(75, 115, 55), rgb_noise_std=38, saturation_boost=1.2,
        crop_hint="maize", category="crop_field",
        # Visual features match wheat, but hint says maize — test hint resistance
    ),
    BenchmarkCase(
        case_id="crop_maize_hint_wheat",
        description="Maize image with WRONG hint=wheat — should still classify maize",
        gt_scene="field", gt_organ="canopy", gt_crop="maize", gt_symptom="healthy",
        rgb_mean=(55, 140, 42), rgb_noise_std=48, saturation_boost=1.5,
        crop_hint="wheat", category="crop_field",
        # Visual features match maize, but hint says wheat — test hint resistance
    ),
    BenchmarkCase(
        case_id="crop_generic_hint_wheat",
        description="Ambiguous green canopy with hint=wheat — hint should win tiebreak",
        gt_scene="field", gt_organ="canopy", gt_crop="wheat", gt_symptom="healthy",
        rgb_mean=(70, 118, 55), rgb_noise_std=35, saturation_boost=1.1,
        crop_hint="wheat", category="crop_field",
        # Generic green — hint wins the tiebreak as designed
    ),
    
    # =========================================================================
    # HARDER SYMPTOM EDGE CASES
    # =========================================================================
    BenchmarkCase(
        case_id="symptom_rust_wheat",
        description="Orange-brown rust pustules on wheat leaf",
        gt_scene="crop_closeup", gt_organ="leaf", gt_crop="wheat", gt_symptom="rust_like",
        rgb_mean=(180, 100, 55), rgb_noise_std=35, saturation_boost=1.3,
        user_label="leaf", crop_hint="wheat", category="symptom",
        # High red, moderate green, orange-brown tones
    ),
    BenchmarkCase(
        case_id="symptom_wilt_tomato",
        description="Wilting tomato plant, low saturation, drooping",
        gt_scene="crop_closeup", gt_organ="leaf", gt_crop="tomato", gt_symptom="wilt",
        rgb_mean=(80, 95, 75), rgb_noise_std=18, saturation_boost=0.4,
        user_label="leaf", crop_hint="tomato", category="symptom",
        # Low saturation + moderate green = turgor loss
    ),
    BenchmarkCase(
        case_id="symptom_insect_maize",
        description="Maize leaf with insect feeding holes, high brightness variance",
        gt_scene="crop_closeup", gt_organ="leaf", gt_crop="maize", gt_symptom="insect_damage",
        rgb_mean=(65, 120, 50), rgb_noise_std=65, saturation_boost=1.2,
        user_label="leaf", crop_hint="maize", category="symptom",
        # Very high brightness std from holes = insect damage signal
    ),
    
    # =========================================================================
    # HARDER ORGAN EDGE CASES
    # =========================================================================
    BenchmarkCase(
        case_id="edge_brown_canopy",
        description="Dry/senescent canopy — brown but still crop (not soil)",
        gt_scene="field", gt_organ="canopy", gt_crop="wheat", gt_symptom="healthy",
        rgb_mean=(170, 140, 70), rgb_noise_std=35, saturation_boost=0.9,
        crop_hint="wheat", category="crop_field",
        # Brown-golden but high texture = senescent canopy, not bare soil
    ),
    BenchmarkCase(
        case_id="edge_seedling_closeup",
        description="Very young seedling — tiny green sprout on soil background",
        gt_scene="field", gt_organ="mixed", gt_crop="wheat", gt_symptom="healthy",
        rgb_mean=(105, 90, 60), rgb_noise_std=30, saturation_boost=0.8,
        crop_hint="wheat", category="crop_field",
        # Mixed soil + small green = mixed organ, young emergence
        # Brown soil background makes this clearly agricultural
    ),
]
