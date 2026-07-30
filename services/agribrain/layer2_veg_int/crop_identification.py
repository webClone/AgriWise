"""
Layer 2.5: Biophysical Crop Intelligence Engine v5.1.0
=====================================================
11 scientifically-grounded scoring modules + Crop Intelligence overlay:
  A. Per-Crop NDVI Reference Signatures (Gaussian matching + peak scaling)
  B. Regional Crop Calendar Windows (MENA/Algeria focus, evergreen-aware)
  C. Multi-Spectral Index Analysis (EVI, NDMI, NDWI)
  D. Köppen Climate Zone Affinity Matrix
  E. Aridity Index & Water Feasibility
  F. Agronomic Rotation Rules (Bayesian prior)
  G. NDVI Curve Shape Descriptors (slope, integral, asymmetry, peaks, CV)
  H. Botanical Family Clustering + Per-Crop Tiebreaker
  I. Phenological Phase Detector (greenup/peak/senescence/dormancy/evergreen)
  J. Area-Based Likelihood Prior (small→vegetable, large→cereal)
  + CV-gated architecture pre-filter (post-scoring multiplier)

References:
  - Wardlow & Egbert (2008): MODIS NDVI time-series for crop classification
  - Xiao et al. (2005): Multi-spectral indices for rice/crop mapping
  - Bolton & Friedl (2013): Phenology-based crop identification
  - Jonsson & Eklundh (2002): NDVI curve shape analysis
  - FAO Crop Calendar & ASAP-JRC dataset
  - Beck et al. (2018): Köppen-Geiger climate classification
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from crop_database import CropSpec, CROP_REGISTRY, list_crops
from layer2_veg_int.crop_science_data import (
    CROP_NDVI_SIGNATURES,
    CROP_CALENDARS,
    SPECTRAL_SIGNATURES,
    KOPPEN_CROP_AFFINITY,
    ARIDITY_CROP_THRESHOLDS,
    ROTATION_MATRIX,
    BOTANICAL_FAMILIES,
    MENA_CROP_PREVALENCE,
    _CURATED_NDVI_CODES,
    detect_koppen_zone,
    detect_crop_calendar_region,
    CROP_GROUP_MAP,
    get_crop_group,
    CROP_DATA_QUALITY,
)
from layer2_veg_int.crop_ml import (
    smooth_ndvi,
    smooth_ndvi_time_aware,
    extract_phenology,
    gaussian_likelihood,
    BayesianCropClassifier,
    entropy_confidence,
    CropFeedbackStore,
)
from layer2_veg_int.labels.classifier import HierarchicalCropClassifier
from layer2_veg_int.features.crop_feature_vector import extract_crop_features

logger = logging.getLogger(__name__)


# =============================================================================
# Output Schema — Crop Intelligence v5.0
# =============================================================================

# Non-crop classes for fallow/bare detection
NON_CROP_CLASSES = {
    "fallow":               {"architecture": "non_crop", "peak_ndvi_max": 0.20, "cv_max": 0.15},
    "bare_soil":            {"architecture": "non_crop", "peak_ndvi_max": 0.15, "cv_max": 0.10},
    "post_harvest_residue": {"architecture": "non_crop", "peak_ndvi_max": 0.25, "cv_max": 0.20},
    "recently_tilled":      {"architecture": "non_crop", "peak_ndvi_max": 0.18, "cv_max": 0.12},
    "mixed_unknown":        {"architecture": "non_crop", "peak_ndvi_max": 0.30, "cv_max": 0.35},
}

_NON_CROP_NAMES = {
    "fallow": ("Fallow", "أرض بور"),
    "bare_soil": ("Bare Soil", "تربة عارية"),
    "post_harvest_residue": ("Post-Harvest Residue", "بقايا المحصول"),
    "recently_tilled": ("Recently Tilled", "أرض محروثة"),
    "mixed_unknown": ("Unknown / Mixed", "غير معروف"),
}

# Data quality tier → trust multiplier
_QUALITY_MULTIPLIERS = {
    "curated_literature": 1.08,
    "curated": 1.04,
    "architecture_default": 0.92,
    "heuristic": 0.85,
}

# Inference mode → explicit language (user modification #6)
_INFERENCE_MODE_LANGUAGE = {
    "observed_timeseries": "Likely current crop based on observed vegetation/SAR behavior.",
    "context_only": "Likely candidates based on soil, climate, and location. Satellite time-series evidence is insufficient.",
    "prior_only": "No detected crop. These are regional likelihood candidates.",
}


@dataclass
class CropCandidate:
    """A ranked candidate crop identification result."""
    code: str
    name: str
    name_ar: str
    architecture: str
    score: float               # Combined ranking score 0.0 – 1.0
    # Crop Intelligence v5.1 fields
    softmax_candidate_share: Optional[float] = None  # Softmax ranking share 0-1 (NOT a calibrated probability)
    crop_group: str = "unknown"                      # Hierarchical group
    data_quality_tier: str = "heuristic"             # curated | heuristic | ...
    # Per-module scores for explainability
    temporal_score: float = 0.0
    phenological_score: float = 0.0
    sar_score: float = 0.0
    location_score: float = 0.0
    thermal_score: float = 0.0

    def to_dict(self) -> Dict:
        share_val = round(self.softmax_candidate_share, 4) if self.softmax_candidate_share is not None else None
        return {
            "code": self.code,
            "name": self.name,
            "name_ar": self.name_ar,
            "architecture": self.architecture,
            "score": round(self.score, 4),
            "softmax_candidate_share": share_val,
            "crop_group": self.crop_group,
            "data_quality_tier": self.data_quality_tier,
            "breakdown": {
                "temporal": round(self.temporal_score, 4),
                "phenological": round(self.phenological_score, 4),
                "sar": round(self.sar_score, 4),
                "location": round(self.location_score, 4),
                "thermal": round(self.thermal_score, 4),
            },
        }


@dataclass
class CropIdentificationResult:
    """Full Crop Intelligence result with ranked candidates."""
    top_crop: Optional[str]               # Best guess crop code, or None when no detection
    top_confidence: float                 # Softmax ranking share 0.0 – 1.0
    confidence_label: str                 # HIGH / MODERATE / LOW / UNKNOWN
    architecture_class: str               # Best guess architecture
    candidates: List[CropCandidate]       # Top-N ranked crops
    total_crops_evaluated: int
    data_quality: str                     # HIGH / MODERATE / LOW
    recommendation: str                   # Human-readable action hint
    evidence: Dict[str, Any] = field(default_factory=dict)
    # Crop Intelligence v5.1 fields
    inference_mode: str = "prior_only"    # observed_timeseries | context_only | prior_only
    evidence_strength: str = "LOW"        # LOW | MEDIUM | HIGH
    top_group: str = "unknown"            # Hierarchical group of top candidate
    detected_crop: bool = False           # True ONLY when inference_mode == observed_timeseries
    prediction_depth: str = "L0"
    detected_crop_group: bool = False
    ambiguity_is_ambiguous: bool = False
    ambiguity_between: List[str] = field(default_factory=list)
    ambiguity_reason: str = ""

    def to_dict(self) -> Dict:
        return {
            "top_crop": self.top_crop,
            "top_confidence": round(self.top_confidence, 4),
            "confidence_label": self.confidence_label,
            "architecture_class": self.architecture_class,
            "candidates": [c.to_dict() for c in self.candidates],
            "total_crops_evaluated": self.total_crops_evaluated,
            "data_quality": self.data_quality,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
            # Crop Intelligence v5.1
            "inference_mode": self.inference_mode,
            "evidence_strength": self.evidence_strength,
            "detected_crop": self.detected_crop,
            "top_group": self.top_group,
            "prediction_depth": self.prediction_depth,
            "detected_crop_group": self.detected_crop_group,
            "ambiguity": {
                "is_ambiguous": self.ambiguity_is_ambiguous,
                "between": self.ambiguity_between,
                "reason": self.ambiguity_reason,
            },
            "calibration_status": "ranking_share_not_calibrated_probability",
        }


# =============================================================================
# Reference Templates — built once from all 209 crops
# =============================================================================

# Architecture → normalized NDVI curve template
# These are idealized phenological NDVI shapes per architecture class.
# Used as reference templates for temporal matching.
# Each template: dict with fraction-of-season → expected NDVI fraction
# (fraction of peak), enabling DTW-style comparison.

_ARCHITECTURE_TEMPLATES = {
    # Annual crops: clear unimodal bell shape
    "cereal": {
        "shape": "unimodal",
        "emergence_frac": 0.05,    # Season fraction for emergence
        "peak_frac": 0.50,         # When peak occurs (fraction of season)
        "senescence_frac": 0.85,   # When senescence begins
        "peak_ndvi_range": (0.55, 0.85),   # Expected peak NDVI range
        "min_ndvi": 0.10,          # Bare soil baseline
        "greenup_slope": 0.006,    # NDVI units per day during green-up
    },
    "maize": {
        "shape": "unimodal",
        "emergence_frac": 0.08,
        "peak_frac": 0.55,
        "senescence_frac": 0.82,
        "peak_ndvi_range": (0.65, 0.92),
        "min_ndvi": 0.10,
        "greenup_slope": 0.008,
    },
    "rice": {
        "shape": "unimodal",
        "emergence_frac": 0.10,
        "peak_frac": 0.55,
        "senescence_frac": 0.80,
        "peak_ndvi_range": (0.55, 0.80),
        "min_ndvi": 0.05,         # Flooded paddy can be very low
        "greenup_slope": 0.007,
    },
    "legume": {
        "shape": "unimodal",
        "emergence_frac": 0.08,
        "peak_frac": 0.50,
        "senescence_frac": 0.80,
        "peak_ndvi_range": (0.45, 0.75),
        "min_ndvi": 0.10,
        "greenup_slope": 0.005,
    },
    "vegetable": {
        "shape": "unimodal_short",
        "emergence_frac": 0.10,
        "peak_frac": 0.45,
        "senescence_frac": 0.85,
        "peak_ndvi_range": (0.40, 0.70),
        "min_ndvi": 0.10,
        "greenup_slope": 0.005,
    },
    "cotton": {
        "shape": "unimodal",
        "emergence_frac": 0.08,
        "peak_frac": 0.50,
        "senescence_frac": 0.80,
        "peak_ndvi_range": (0.55, 0.80),
        "min_ndvi": 0.10,
        "greenup_slope": 0.006,
    },
    # Perennial crops: persistent high NDVI, low seasonal variation
    "perennial": {
        "shape": "evergreen",
        "emergence_frac": 0.0,     # No emergence (already established)
        "peak_frac": 0.40,
        "senescence_frac": 1.0,    # No senescence
        "peak_ndvi_range": (0.45, 0.75),
        "min_ndvi": 0.30,          # Never drops below 0.30
        "greenup_slope": 0.002,
    },
    "tropical_tree": {
        "shape": "evergreen",
        "emergence_frac": 0.0,
        "peak_frac": 0.45,
        "senescence_frac": 1.0,
        "peak_ndvi_range": (0.50, 0.85),
        "min_ndvi": 0.35,
        "greenup_slope": 0.001,
    },
}


# Climate zone → typical region tags
_CLIMATE_REGION_MAP = {
    "mediterranean": ["mediterranean", "temperate"],
    "semi-arid": ["mena", "mediterranean", "subtropical"],
    "arid": ["mena", "subtropical"],
    "saharan": ["mena", "subtropical", "tropical"],
    "tropical": ["tropical", "subsaharan", "subtropical"],
    "temperate": ["temperate", "mediterranean"],
    "continental": ["temperate"],
}


# =============================================================================
# Engine
# =============================================================================

class CropIdentificationEngine:
    """
    Biophysical Crop Intelligence Engine.

    Scores every crop in the 212-entry registry plus 5 non-crop classes
    against observed biophysical signals, returning ranked candidates with
    calibrated probabilities, inference mode classification, ambiguity
    detection, and hierarchical crop groups.
    """

    VERSION = "5.1.0"

    # ── Module weights (sum to 1.00 when all active) ──
    # A: NDVI signature matching — THE primary discriminator
    W_NDVI_SIGNATURE = 0.22
    # B: Crop calendar window — eliminates out-of-season crops
    W_CROP_CALENDAR = 0.12
    # C: Multi-spectral indices (EVI, NDMI, NDWI)
    W_SPECTRAL = 0.07
    # D: Köppen climate affinity — eliminates climatically impossible
    W_KOPPEN = 0.10
    # E: Aridity feasibility (rough proxy — reduced from 0.04)
    W_ARIDITY = 0.02
    # F: Rotation rules (when previous crop known — rarely active)
    W_ROTATION = 0.02
    # G: NDVI shape descriptors — curve shape fingerprint
    W_SHAPE = 0.12
    # H: Botanical family + per-crop tiebreaker
    W_FAMILY = 0.04
    # I: Phenological phase detector
    W_PHENOPHASE = 0.08
    # J: Area-based likelihood prior
    W_AREA_PRIOR = 0.06
    # K: PlotDNA soil/vigor scoring
    W_DNA = 0.04
    # Legacy modules
    W_SAR = 0.02
    W_PLOT_CONTEXT = 0.04
    W_THERMAL = 0.05

    def __init__(self):
        # Pre-load all 209 crops from centralized registry
        self._all_crops: List[CropSpec] = list(CROP_REGISTRY.values())
        self._templates = _ARCHITECTURE_TEMPLATES
        
        # Initialize Bayesian classifier with crop signatures
        self._bayesian = BayesianCropClassifier(
            crop_signatures=CROP_NDVI_SIGNATURES,
            regional_priors=MENA_CROP_PREVALENCE,
        )
        
        # Initialize feedback store for self-learning
        self._feedback = CropFeedbackStore()
        
        # IMP-5: Cache last identification result per plot for feedback endpoint
        self._last_results: Dict[str, Dict] = {}  # plot_id → {phenology, ndvi, ...}
        
        # Apply learned priors/sigmas if enough feedback exists
        learned_priors = self._feedback.compute_learned_priors()
        if learned_priors:
            # Merge learned priors with MENA priors (learned takes priority)
            for k, v in learned_priors.items():
                self._bayesian.priors[k] = v
            logger.info("[CropID] Applied learned priors from %d feedback entries",
                       len(learned_priors))
        
        # FIX BUG-1: Store learned sigmas PER-CROP (not global override)
        learned_sigmas = self._feedback.compute_learned_sigmas()
        if learned_sigmas:
            self._bayesian.crop_sigmas = learned_sigmas
            logger.info("[CropID] Applied per-crop learned sigmas for %d crops",
                       len(learned_sigmas))

        # Initialize and load HierarchicalCropClassifier
        self._ml_classifier = HierarchicalCropClassifier()
        self._ml_load_status = self._ml_classifier.load()
        
        logger.info(
            "[CropID] Engine v%s initialized with %d crops; Bayesian rules "
            "active, hierarchical ML=%s",
            self.VERSION,
            len(self._all_crops),
            (
                "loaded_validated"
                if self._ml_load_status
                else "not_loaded"
            ),
        )

    def identify(
        self,
        *,
        # NDVI data (from L2 or PlotDNA)
        ndvi_series: Optional[List[float]] = None,
        ndvi_dates: Optional[List[str]] = None,
        ndvi_velocity: Optional[List[float]] = None,
        peak_ndvi: Optional[float] = None,
        trough_ndvi: Optional[float] = None,
        seasonal_profile: Optional[List[Optional[float]]] = None,
        # Phenology data
        peak_doy: Optional[int] = None,
        greenup_doy: Optional[int] = None,
        senescence_doy: Optional[int] = None,
        season_length_days: Optional[int] = None,
        greenup_velocity: Optional[float] = None,
        # SAR data (from L1)
        sar_vh_mean: Optional[float] = None,
        sar_vv_mean: Optional[float] = None,
        sar_vh_seasonal_range: Optional[float] = None,
        # Multi-spectral indices (already fetched by Sentinel pipeline)
        evi_mean: Optional[float] = None,
        ndmi_mean: Optional[float] = None,
        ndwi_mean: Optional[float] = None,
        # Location context
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        climate_zone: Optional[str] = None,
        elevation_m: Optional[float] = None,
        # Thermal data
        mean_temp_c: Optional[float] = None,
        gdd_accumulated: Optional[float] = None,
        gdd_accumulation_days: Optional[int] = None,
        # Climate / Water data (Component 9)
        annual_rainfall_mm: Optional[float] = None,
        et0_mm: Optional[float] = None,
        # Per-plot context
        area_ha: Optional[float] = None,
        soil_type: Optional[str] = None,
        irrigation_type: Optional[str] = None,
        previous_crops: Optional[List[Dict]] = None,
        # PlotDNA traits (from Layer 0 biophysical inversion)
        dna_vigor: Optional[float] = None,           # alpha_vigor: 0.7-1.3
        dna_water_retention: Optional[float] = None,  # theta_retention: 0.5-1.5
        dna_exhaustion: Optional[float] = None,       # exhaustion_index: negative=fatigue
        dna_carbon_memory: Optional[float] = None,    # carbon_memory_proxy
        dna_future_proof: Optional[float] = None,     # future_proof_score: 0-100
        # Config
        top_n: int = 5,
        **kwargs,
    ) -> CropIdentificationResult:
        """
        Run v4.0 crop identification with 11+ scientific scoring modules.
        Now integrates PlotDNA biophysical traits for soil-aware scoring.
        """
        # ── Assess data availability ──
        has_ndvi = ndvi_series is not None and len(ndvi_series) > 5
        has_phenology = peak_doy is not None or season_length_days is not None
        has_sar = sar_vh_mean is not None
        has_spectral = evi_mean is not None or ndmi_mean is not None
        has_location = lat is not None
        has_thermal = mean_temp_c is not None
        has_aridity = has_thermal or (annual_rainfall_mm is not None)
        has_context = area_ha is not None or soil_type is not None or irrigation_type is not None
        has_rotation = previous_crops is not None and len(previous_crops) > 0
        has_dna = dna_vigor is not None

        data_signals = sum([has_ndvi, has_phenology, has_sar, has_spectral,
                           has_location, has_thermal, has_context, has_rotation,
                           has_dna])
        data_quality = "HIGH" if data_signals >= 5 else "MODERATE" if data_signals >= 3 else "LOW"

        # ── Intercept with v6.0C Hierarchical ML Classifier ──
        import os
        import hashlib
        _force_rule_engine = kwargs.get("_force_rule_engine", False)
        ml_enabled = (os.environ.get("AGRIBRAIN_CROP_ML_ENABLED", "false").lower() == "true") and not _force_rule_engine
        field_tensor = kwargs.get("field_tensor")
        feature_vector_snapshot = kwargs.get("feature_vector_snapshot")
        koppen_zone = kwargs.get("koppen_zone")
        aridity_index = kwargs.get("aridity_index")
        if aridity_index is None and annual_rainfall_mm is not None and et0_mm is not None:
            aridity_index = annual_rainfall_mm / max(1.0, et0_mm)
        
        if (
            ml_enabled
            and bool(self._ml_load_status)
            and self._ml_classifier.models is not None
            and (field_tensor is not None or feature_vector_snapshot is not None)
        ):
            try:
                # 1. Build or retrieve the CropFeatureVector
                if feature_vector_snapshot is not None:
                    fv = feature_vector_snapshot
                    fv_version = fv.get("feature_vector_version", "6.0.0")
                    data_completeness = fv.get("data_completeness", 1.0)
                    flat_features = fv.get("flat_features", fv)
                    
                    # Compute feature availability by level
                    flat_keys = sorted(list(self._ml_classifier.feature_names))
                    current_hash = hashlib.sha256(",".join(flat_keys).encode("utf-8")).hexdigest()
                    
                    availability = fv.get("feature_availability_by_level") or {}
                    if "L0" in availability:
                        l0_availability = availability["L0"]
                    else:
                        l0_features = ["peak_ndvi", "base_ndvi", "amplitude", "cv_ndvi", "vv_mean_db", "vh_mean_db", "n_seasons", "is_evergreen"]
                        l0_available = sum(1 for f in l0_features if flat_features.get(f) is not None)
                        l0_availability = l0_available / len(l0_features)
                else:
                    k_zone = climate_zone or koppen_zone
                    if not k_zone and lat is not None and lng is not None:
                        k_zone = detect_koppen_zone(lat, lng, mean_temp_c)
                    
                    fv = extract_crop_features(
                        plot_timeseries=field_tensor.plot_timeseries if hasattr(field_tensor, "plot_timeseries") else (field_tensor or []),
                        plot_id=kwargs.get("plot_id", "unknown"),
                        run_id=kwargs.get("run_id", "unknown"),
                        dates=ndvi_dates,
                        ndvi_series=ndvi_series,
                        latitude=lat,
                        longitude=lng,
                        koppen_zone=k_zone,
                        aridity_index=aridity_index,
                        soil_texture_class=soil_type or kwargs.get("soil_type"),
                        irrigation_type=irrigation_type,
                        plot_area_ha=area_ha,
                    )
                    fv_version = fv.feature_vector_version
                    data_completeness = fv.data_completeness
                    flat_features = fv.to_flat_dict()
                    
                    levels = fv.feature_availability_by_level()
                    l0_availability = levels.get("L0", 0.0)
                    
                    flat_keys = sorted(list(flat_features.keys()))
                    current_hash = hashlib.sha256(",".join(flat_keys).encode("utf-8")).hexdigest()

                # 2. Schema and Completeness Checks (Tweaks #4 & #5)
                meta = self._ml_classifier.metadata
                expected_hash = meta.get("feature_order_hash")
                expected_version = meta.get("feature_vector_version")
                
                if fv_version != expected_version or current_hash != expected_hash:
                    logger.warning(f"[CropML] Schema mismatch: version {fv_version} vs {expected_version}, hash {current_hash[:8]} vs {expected_hash[:8] if expected_hash else None}. Fallback to v5.1.")
                elif data_completeness < 0.4:
                    logger.info(f"[CropML] Bypassing ML path: data completeness {data_completeness} < 0.4 threshold. Fallback to v5.1.")
                elif l0_availability < 0.5:
                    logger.info(f"[CropML] Bypassing ML path: L0 feature availability {l0_availability} < 0.5 threshold. Fallback to v5.1.")
                else:
                    # Run ML prediction!
                    ml_result = self._ml_classifier.predict(fv, apply_constraints=True)
                    ml_output = ml_result["ml_classifier_output"]
                    
                    # Map candidates
                    ml_candidates = []
                    l3_info = ml_output.get("L3", {})
                    top_candidates = l3_info.get("top_candidates", [])
                    fallback_triggered = l3_info.get("agronomic_filter", {}).get("fallback_triggered", False)
                    
                    if not fallback_triggered and top_candidates:
                        for cand in top_candidates:
                            code = cand["code"]
                            prob = cand["probability"]
                            
                            crop_spec = CROP_REGISTRY.get(code)
                            if crop_spec:
                                c_name = crop_spec.name
                                c_name_ar = crop_spec.name_ar
                                c_arch = crop_spec.architecture
                            else:
                                c_name = code.replace("_", " ").title()
                                c_name_ar = code
                                c_arch = "unknown"
                                
                            ml_candidates.append(CropCandidate(
                                code=code,
                                name=c_name,
                                name_ar=c_name_ar,
                                architecture=c_arch,
                                score=prob,
                                softmax_candidate_share=prob,
                                crop_group=get_crop_group(code),
                                data_quality_tier="ml_inference"
                            ))
                            
                    top_crop = l3_info.get("prediction")
                    top_prob = l3_info.get("probability", 0.0)
                    
                    if not top_crop:
                        stop_level = "L2"
                        l2_pred = ml_output.get("L2", {}).get("prediction")
                        l2_prob = ml_output.get("L2", {}).get("probability", 0.0)
                        
                        top_crop = None
                        top_prob = 0.0
                        confidence_label = "LOW"
                        
                        if l2_pred:
                            rec = f"Confidence is too low to identify exact crop species. Stopped at crop group: {l2_pred.replace('_', ' ').title()} (probability {l2_prob:.2f})."
                        else:
                            rec = "ML classifier could not reliably identify the crop hierarchy levels."
                    else:
                        confidence_label = "HIGH" if top_prob >= 0.7 else "MODERATE" if top_prob >= 0.4 else "LOW"
                        crop_spec = CROP_REGISTRY.get(top_crop)
                        top_name = crop_spec.name if crop_spec else top_crop.replace("_", " ").title()
                        rec = f"Hierarchical ML classifier predicted crop species: {top_name} (probability {top_prob:.2f}, confidence {confidence_label})."

                    if fallback_triggered:
                        logger.info("[CropML] Agronomic constraint rejection fallback triggered. Falling back to rule-based v5.1.")
                        if kwargs.get("_force_rule_engine"):
                            raise RuntimeError("[CropML] Infinite recursion loop detected in agronomic constraint fallback.")
                        
                        fallback_kwargs = dict(kwargs)
                        fallback_kwargs["_force_rule_engine"] = True
                        res = self.identify(
                            ndvi_series=ndvi_series,
                            ndvi_dates=ndvi_dates,
                            ndvi_velocity=ndvi_velocity,
                            peak_ndvi=peak_ndvi,
                            trough_ndvi=trough_ndvi,
                            seasonal_profile=seasonal_profile,
                            peak_doy=peak_doy,
                            greenup_doy=greenup_doy,
                            senescence_doy=senescence_doy,
                            season_length_days=season_length_days,
                            greenup_velocity=greenup_velocity,
                            sar_vh_mean=sar_vh_mean,
                            sar_vv_mean=sar_vv_mean,
                            sar_vh_seasonal_range=sar_vh_seasonal_range,
                            evi_mean=evi_mean,
                            ndmi_mean=ndmi_mean,
                            ndwi_mean=ndwi_mean,
                            lat=lat,
                            lng=lng,
                            climate_zone=climate_zone,
                            elevation_m=elevation_m,
                            mean_temp_c=mean_temp_c,
                            gdd_accumulated=gdd_accumulated,
                            gdd_accumulation_days=gdd_accumulation_days,
                            annual_rainfall_mm=annual_rainfall_mm,
                            et0_mm=et0_mm,
                            area_ha=area_ha,
                            soil_type=soil_type,
                            irrigation_type=irrigation_type,
                            previous_crops=previous_crops,
                            dna_vigor=dna_vigor,
                            dna_water_retention=dna_water_retention,
                            dna_exhaustion=dna_exhaustion,
                            dna_carbon_memory=dna_carbon_memory,
                            dna_future_proof=dna_future_proof,
                            top_n=top_n,
                            **fallback_kwargs
                        )
                        
                        # Inject ML output to evidence for tracking/verification
                        res.evidence["ml_classifier_output"] = ml_output
                        res.evidence["probability_calibration"] = ml_result.get("probability_calibration", {})
                        res.evidence["feature_vector_version"] = fv_version
                        res.evidence["data_completeness"] = data_completeness
                        res.evidence["agronomic_fallback_triggered"] = True
                        res.evidence["agronomic_fallback_reason"] = "L3 rejected by agronomic filter"
                        return res
                    else:
                        evidence = {
                            "data_signals_available": data_signals,
                            "engine_version": self.VERSION,
                            "ml_classifier_output": ml_output,
                            "feature_vector_version": fv_version,
                            "probability_calibration": ml_result.get("probability_calibration", {}),
                            "data_completeness": data_completeness,
                            "ml_deployment_contract": dict(
                                self._ml_load_status
                            ),
                            "ml_production_eligible": bool(
                                self._ml_classifier.production_eligible
                            ),
                        }
                        
                        # Determine prediction depth and flags for ML path
                        pred_depth = "L0"
                        det_group = False
                        det_crop = False
                        
                        l0_pred = ml_output.get("L0", {}).get("prediction")
                        l1_pred = ml_output.get("L1", {}).get("prediction")
                        l2_pred = ml_output.get("L2", {}).get("prediction")
                        l3_pred = ml_output.get("L3", {}).get("prediction")
                        
                        if l3_pred:
                            pred_depth = "L3"
                            det_group = True
                            det_crop = True
                        elif l2_pred:
                            pred_depth = "L2"
                            det_group = True
                            det_crop = False
                        elif l1_pred:
                            pred_depth = "L1"
                            det_group = False
                            det_crop = False
                        else:
                            pred_depth = "L0"
                            det_group = False
                            det_crop = False
                        
                        return CropIdentificationResult(
                            top_crop=top_crop,
                            top_confidence=top_prob,
                            confidence_label=confidence_label,
                            architecture_class=ml_output.get("L1", {}).get("prediction") or "unknown",
                            candidates=ml_candidates,
                            total_crops_evaluated=len(self._all_crops) + len(NON_CROP_CLASSES),
                            data_quality=data_quality,
                            recommendation=rec,
                            evidence=evidence,
                            inference_mode="observed_timeseries",
                            evidence_strength="HIGH" if data_signals >= 4 else "MEDIUM",
                            top_group=ml_output.get("L2", {}).get("prediction") or "unknown",
                            detected_crop=det_crop,
                            prediction_depth=pred_depth,
                            detected_crop_group=det_group,
                            ambiguity_is_ambiguous=(l3_info.get("reason") in ("high_entropy_l3", "insufficient_features_l3")),
                            ambiguity_between=[c.code for c in ml_candidates[1:3]] if len(ml_candidates) > 1 else [],
                            ambiguity_reason=l3_info.get("reason", ""),
                        )
            except Exception as e:
                logger.error(f"[CropML] ML prediction failed: {e}. Falling back to rule-based v5.1.")

        # ── Inference mode classification (Crop Intelligence v5.0) ──
        # Drives confidence capping and explicit language
        if has_ndvi or has_sar:
            inference_mode = "observed_timeseries"
            evidence_strength = "HIGH" if has_ndvi and data_signals >= 4 else "MEDIUM"
        elif has_thermal or has_context or has_spectral:
            inference_mode = "context_only"
            evidence_strength = "MEDIUM" if data_signals >= 3 else "LOW"
        else:
            inference_mode = "prior_only"
            evidence_strength = "LOW"

        # ── GUARD: Insufficient data → return UNKNOWN immediately ──
        # Without ANY data signal the engine has nothing to discriminate
        # against, so returning a random crop is misleading.
        if data_signals == 0:
            logger.warning("[CropID] No data signals available — returning UNKNOWN")
            return CropIdentificationResult(
                top_crop="unknown",
                top_confidence=0.0,
                confidence_label="UNKNOWN",
                architecture_class="unknown",
                candidates=[],
                total_crops_evaluated=len(self._all_crops),
                data_quality="LOW",
                recommendation="Cannot identify crop. No satellite, location, or context data available.",
                evidence={"data_signals_available": 0, "engine_version": self.VERSION},
            )

        # ── Derive extra features from NDVI series ──
        if has_ndvi:
            if peak_ndvi is None:
                peak_ndvi = max(ndvi_series)
            if trough_ndvi is None:
                pos = [v for v in ndvi_series if v > 0.0]
                trough_ndvi = min(pos) if pos else 0.0
            if season_length_days is None and ndvi_dates and len(ndvi_dates) > 1:
                try:
                    parsed_dates = sorted(
                        datetime.strptime(str(value)[:10], "%Y-%m-%d")
                        for value in ndvi_dates
                    )
                    season_length_days = max(
                        0, (parsed_dates[-1] - parsed_dates[0]).days
                    )
                except (TypeError, ValueError):
                    season_length_days = None

        # ── Derive peak DOY from ndvi_dates if possible ──
        if peak_doy is None and has_ndvi and ndvi_dates and peak_ndvi is not None:
            try:
                peak_idx = ndvi_series.index(peak_ndvi)
                if peak_idx < len(ndvi_dates):
                    from datetime import datetime
                    dt = datetime.strptime(ndvi_dates[peak_idx][:10], "%Y-%m-%d")
                    peak_doy = dt.timetuple().tm_yday
                    has_phenology = True
            except (ValueError, IndexError):
                pass

        # ── Compute NDVI shape descriptors (Module G) ──
        shape_descriptors = None
        advanced_phenology = None
        smoothed_ndvi = None
        smoothed_list = None  # FIX BUG-9: keep smoothed list for Module A
        smoothing_support = {
            "method": "sample_index_savgol",
            "status": "dates_unavailable",
        }
        if has_ndvi and len(ndvi_series) >= 5:
            if ndvi_dates and len(ndvi_dates) == len(ndvi_series):
                smoothed_ndvi, smoothed_dates, smoothing_support = (
                    smooth_ndvi_time_aware(ndvi_series, ndvi_dates)
                )
                if len(smoothed_ndvi) >= 5:
                    ndvi_dates = smoothed_dates
                else:
                    smoothed_ndvi = smooth_ndvi(ndvi_series, window=7)
                    smoothing_support = {
                        **smoothing_support,
                        "fallback_method": "sample_index_savgol",
                    }
            else:
                smoothed_ndvi = smooth_ndvi(ndvi_series, window=7)
            smoothed_list = smoothed_ndvi.tolist()
            
            # Compute shape descriptors from SMOOTHED series (not raw)
            shape_descriptors = self._compute_shape_descriptors(smoothed_list, peak_ndvi, trough_ndvi)
            
            # STATE-OF-THE-ART: TIMESAT-style phenological metric extraction
            # Extracts SOS, EOS, LOS, POS, growth/senescence rates, integrals
            advanced_phenology = extract_phenology(
                smoothed_ndvi, dates=ndvi_dates, threshold_pct=0.20
            )
            
            # Override peak_ndvi/trough_ndvi with smoothed values
            if advanced_phenology:
                peak_ndvi = advanced_phenology.get("peak_val", peak_ndvi)
                trough_ndvi = advanced_phenology.get("base_val", trough_ndvi)

        # ── Auto-detect climate/region ──
        koppen_zone = None
        calendar_region = None
        if has_location:
            koppen_zone = detect_koppen_zone(lat, lng, mean_temp_c)
            calendar_region = detect_crop_calendar_region(lat, lng)

        # ── Dynamic weight redistribution ──
        w = {
            'ndvi_sig':   self.W_NDVI_SIGNATURE if has_ndvi else 0.0,
            'calendar':   self.W_CROP_CALENDAR if has_location and has_phenology else 0.0,
            'spectral':   self.W_SPECTRAL if has_spectral else 0.0,
            'koppen':     self.W_KOPPEN if has_location else 0.0,
            'aridity':    self.W_ARIDITY if has_aridity else 0.0,
            'rotation':   self.W_ROTATION if has_rotation else 0.0,
            'shape':      self.W_SHAPE if shape_descriptors else 0.0,
            'family':     self.W_FAMILY,  # Always active
            'phenophase': self.W_PHENOPHASE if has_ndvi and has_phenology else 0.0,
            'area':       self.W_AREA_PRIOR if area_ha is not None else 0.0,
            'dna':        self.W_DNA if has_dna else 0.0,
            'sar':        self.W_SAR if has_sar else 0.0,
            'context':    self.W_PLOT_CONTEXT if has_context else 0.0,
            'thermal':    self.W_THERMAL if has_thermal else 0.0,
        }
        total_w = sum(v or 0.0 for v in w.values())
        if total_w > 0:
            for k in w:
                w[k] /= total_w

        # ── Score every crop ──
        candidates: List[CropCandidate] = []
        for crop in self._all_crops:
            # Module A: NDVI Reference Signature Match
            # FIX BUG-9 + IMP-2: Pass SMOOTHED NDVI to Module A for consistency
            _ndvi_for_scoring = smoothed_list if smoothed_list else ndvi_series
            a_score = self._score_ndvi_signature(crop, _ndvi_for_scoring, peak_ndvi, trough_ndvi) if has_ndvi else 0.5

            # Module B: Crop Calendar Window
            b_score = self._score_crop_calendar(crop, peak_doy, calendar_region) if (has_location and has_phenology) else 0.5

            # Module C: Multi-Spectral Indices
            c_score = self._score_spectral(crop, evi_mean, ndmi_mean, ndwi_mean) if has_spectral else 0.5

            # Module D: Köppen Climate Affinity
            d_score = self._score_koppen(crop, koppen_zone) if has_location else 0.5

            # Module E: Aridity Feasibility
            e_score = self._score_aridity(
                crop, mean_temp_c, irrigation_type,
                annual_rainfall_mm=annual_rainfall_mm,
                et0_mm=et0_mm
            ) if has_aridity else 0.5

            # Module F: Rotation Rules
            f_score = self._score_rotation(crop, previous_crops) if has_rotation else 0.5

            # Module G: Shape Descriptors
            g_score = self._score_shape(crop, shape_descriptors) if shape_descriptors else 0.5

            # Module H: Family + Per-Crop Tiebreaker
            h_score = self._score_family_tiebreak(
                crop, lat, mean_temp_c, irrigation_type, area_ha,
                dna_vigor=dna_vigor, dna_water_retention=dna_water_retention,
            )

            # Module I: Phenological Phase Match (NEW v4.0)
            i_score = 0.5
            if has_ndvi and has_phenology:
                i_score = self._score_phenophase(crop, ndvi_series, peak_doy, shape_descriptors)

            # Module J: Area-Based Likelihood (NEW v4.0)
            j_score = self._score_area_prior(crop, area_ha, irrigation_type) if area_ha is not None else 0.5

            # Module K: PlotDNA Soil/Vigor (NEW v4.0)
            k_score = 0.5
            if has_dna:
                k_score = self._score_dna_traits(
                    crop, dna_vigor, dna_water_retention, dna_exhaustion,
                    dna_carbon_memory, dna_future_proof
                )

            # Legacy: SAR
            s_score = self._score_sar(crop, sar_vh_mean, sar_vv_mean, sar_vh_seasonal_range) if has_sar else 0.5

            # Legacy: Plot Context
            ctx_score = self._score_plot_context(crop, area_ha, soil_type, irrigation_type, previous_crops) if has_context else 0.5

            # Legacy: Thermal
            th_score = self._score_thermal(crop, mean_temp_c, gdd_accumulated, gdd_accumulation_days) if has_thermal else 0.5

            # ── Weighted fusion ──
            combined = (
                w['ndvi_sig'] * a_score
                + w['calendar'] * b_score
                + w['spectral'] * c_score
                + w['koppen'] * d_score
                + w['aridity'] * e_score
                + w['rotation'] * f_score
                + w['shape'] * g_score
                + w['family'] * h_score
                + w['phenophase'] * i_score
                + w['area'] * j_score
                + w['dna'] * k_score
                + w['sar'] * s_score
                + w['context'] * ctx_score
                + w['thermal'] * th_score
            )

            # ── HARD ELIMINATION GATES ──
            if d_score <= 0.05:
                combined *= 0.1
            is_evergreen = False
            _ref = CROP_NDVI_SIGNATURES.get(crop.code)
            if _ref and _ref.get("shape") in ("evergreen", "stable"):
                is_evergreen = True
            if b_score <= 0.05 and has_location and has_phenology and not is_evergreen:
                combined *= 0.3
            if has_location and koppen_zone:
                region_compat = self._check_region_compat(crop, koppen_zone)
                if not region_compat:
                    combined *= 0.4

            # ── CV-GATED ARCHITECTURE PRE-FILTER (v4.0) ──
            if shape_descriptors:
                obs_cv = shape_descriptors.get("cv", 0.5)
                ref_shape = _ref.get("shape", "unimodal") if _ref else "unimodal"
                if obs_cv < 0.12:
                    if ref_shape not in ("evergreen", "stable"):
                        combined *= 0.55
                elif obs_cv > 0.35:
                    if ref_shape in ("evergreen", "stable"):
                        combined *= 0.55

            # ── MENA REGIONAL PREVALENCE (v4.0) ──
            # Boost common Algerian/MENA crops, penalize exotic ones
            if has_location and calendar_region and calendar_region.startswith("algeria"):
                prevalence = MENA_CROP_PREVALENCE.get(crop.code, 0.35)
                # Apply as a soft multiplier: 0.7x for rare, 1.0x for common
                combined *= (0.7 + 0.3 * prevalence)

            # ── DATA QUALITY TIER MULTIPLIER (v5.0) ──
            # Replace single 4% curated bonus with graduated per-feature
            # trust multipliers from CROP_DATA_QUALITY.
            crop_quality = CROP_DATA_QUALITY.get(crop.code, {})
            if crop_quality:
                # Use the dominant tier (most common across features)
                tier_counts: Dict[str, int] = {}
                for feat_tier in crop_quality.values():
                    tier_counts[feat_tier] = tier_counts.get(feat_tier, 0) + 1
                dominant_tier = max(tier_counts, key=tier_counts.get) if tier_counts else "heuristic"
                combined *= _QUALITY_MULTIPLIERS.get(dominant_tier, 1.0)
                crop_tier = dominant_tier
            else:
                crop_tier = "heuristic"

            candidates.append(CropCandidate(
                code=crop.code,
                name=crop.name,
                name_ar=crop.name_ar,
                architecture=crop.architecture,
                score=combined,
                crop_group=get_crop_group(crop.code),
                data_quality_tier=crop_tier,
                temporal_score=a_score,
                phenological_score=b_score,
                sar_score=s_score,
                location_score=d_score,
                thermal_score=th_score,
            ))

        # ── Score non-crop classes (Crop Intelligence v5.0) ──
        # Insert fallow/bare candidates when NDVI evidence is available
        if has_ndvi and shape_descriptors:
            obs_peak = peak_ndvi or 0.0
            obs_cv = shape_descriptors.get("cv", 0.5)
            for nc_code, nc_spec in NON_CROP_CLASSES.items():
                nc_score = 0.0
                # High score if observed NDVI matches non-crop profile
                if obs_peak <= nc_spec["peak_ndvi_max"] and obs_cv <= nc_spec["cv_max"]:
                    # Strong match — non-crop likely
                    nc_score = 0.90 - (obs_peak * 0.5)  # Lower NDVI → higher non-crop score
                elif obs_peak <= nc_spec["peak_ndvi_max"] * 1.5:
                    nc_score = 0.40 - (obs_peak * 0.3)
                else:
                    nc_score = max(0.0, 0.15 - obs_peak * 0.2)

                nc_names = _NON_CROP_NAMES.get(nc_code, (nc_code.replace("_", " ").title(), ""))
                candidates.append(CropCandidate(
                    code=nc_code,
                    name=nc_names[0],
                    name_ar=nc_names[1],
                    architecture="non_crop",
                    score=max(0.0, nc_score),
                    crop_group="non_crop",
                    data_quality_tier="curated",
                ))

        # ── Rank by weighted module score descending ──
        candidates.sort(key=lambda c: c.score, reverse=True)

        # ── BAYESIAN POSTERIOR FUSION (v4.1 — state-of-the-art) ──
        # Compute P(crop | data) using Gaussian likelihoods + priors
        # This runs IN PARALLEL with the weighted scoring and is blended
        bayesian_posteriors = {}
        if advanced_phenology and shape_descriptors:
            # Collect per-crop module scores for Bayesian integration
            module_scores_map = {}
            for cand in candidates:
                if cand.architecture != "non_crop":
                    module_scores_map[cand.code] = {
                        "temporal": cand.temporal_score,
                        "phenological": cand.phenological_score,
                        "location": cand.location_score,
                        "thermal": cand.thermal_score,
                    }
            
            # Run Bayesian classifier — ONLY uses Gaussian feature likelihoods + priors
            # Module scores are NOT passed to avoid double-counting with weighted fusion
            posteriors = self._bayesian.classify(
                phenology=advanced_phenology,
                shape_features=shape_descriptors,
                module_scores=None,  # Deliberate: avoid double-counting weighted modules
            )
            
            # Build lookup: crop_code → posterior probability
            bayesian_posteriors = {code: prob for code, prob in posteriors}
        
        # ── BLEND: Weighted Score + Bayesian Posterior (v4.1) ──
        # IMP-7: Adaptive Bayesian weight based on feedback sample count
        # More feedback → Bayesian sigmas are more accurate → increase weight
        n_feedback = len(self._feedback.load_all_samples())
        ALPHA_BAYESIAN = min(0.40, 0.20 + n_feedback * 0.002)  # 20% → 40% max
        ALPHA_WEIGHTED = 1.0 - ALPHA_BAYESIAN
        
        if bayesian_posteriors:
            # Normalize Bayesian posteriors to [0, 1] range matching weighted scores
            max_posterior = max(bayesian_posteriors.values()) if bayesian_posteriors else 1.0
            max_weighted = max(c.score for c in candidates) if candidates else 1.0
            
            for cand in candidates:
                if cand.architecture == "non_crop":
                    continue  # Non-crop classes don't participate in Bayesian
                bayes_score = bayesian_posteriors.get(cand.code, 0.0)
                # Scale Bayesian to same range as weighted scores
                bayes_scaled = (bayes_score / max(1e-10, max_posterior)) * max_weighted
                # Proper weighted average (NOT multiplicative)
                cand.score = ALPHA_WEIGHTED * cand.score + ALPHA_BAYESIAN * bayes_scaled
        
        # Re-sort after blending
        candidates.sort(key=lambda c: c.score, reverse=True)

        # ── SOFTMAX CANDIDATE SHARE (v5.1 — renamed from calibrated_probability) ──
        # Compute softmax ranking share for candidates. This is NOT a
        # calibrated probability — it is a softened ranking share only.
        if len(candidates) >= 3:
            # Softmax over top 20 candidates with temperature scaling
            top_cands = candidates[:20]
            max_s = max(c.score for c in top_cands) if top_cands else 0.0
            if max_s > 0:
                temperature = 2.0  # Smoothing: higher = more uniform
                exp_scores = []
                for c in top_cands:
                    try:
                        exp_scores.append(math.exp((c.score - max_s) / max(0.01, temperature * max_s)))
                    except (OverflowError, ValueError):
                        exp_scores.append(0.0)
                sum_exp = sum(exp_scores) or 1.0
                for i, c in enumerate(top_cands):
                    c.softmax_candidate_share = exp_scores[i] / sum_exp

        # ── INFERENCE-MODE CONFIDENCE CAPPING (v5.1) ──
        # prior_only:  no softmax share, no detected crop — regional priors only
        # context_only: cap softmax share at 0.30, no detected crop
        # observed_timeseries: full share, detected_crop = True
        if inference_mode == "prior_only":
            for c in candidates:
                c.softmax_candidate_share = None
        elif inference_mode == "context_only":
            for c in candidates:
                if c.softmax_candidate_share is not None:
                    c.softmax_candidate_share = min(0.30, c.softmax_candidate_share)

        top = candidates[:top_n]

        # ── ENTROPY-BASED CONFIDENCE (v4.1 — Softmax + Shannon) ──
        top_score = top[0].score if top else 0.0
        top_share = top[0].softmax_candidate_share if top and top[0].softmax_candidate_share else None
        entropy_val = None
        
        if len(candidates) >= 5:
            score_pairs = [(c.code, c.score) for c in candidates[:10]]
            confidence_label, confidence_score, entropy_val = entropy_confidence(score_pairs)
            
            # Hybrid boost: if softmax says LOW but we have strong data,
            # upgrade confidence. Softmax is conservative with tight score gaps.
            if confidence_label == "UNKNOWN" and top_score >= 0.50 and data_signals >= 3:
                confidence_label = "LOW"
            elif confidence_label == "LOW" and top_score >= 0.65 and data_signals >= 4:
                confidence_label = "MODERATE"
            elif confidence_label == "MODERATE" and top_score >= 0.80 and data_signals >= 6:
                confidence_label = "HIGH"
        else:
            second_score = top[1].score if len(top) > 1 else 0.0
            gap = top_score - second_score
            gap_pct = gap / max(0.01, top_score)
            if top_score >= 0.70 and gap_pct >= 0.05 and data_signals >= 4:
                confidence_label = "HIGH"
            elif top_score >= 0.60 and gap_pct >= 0.03:
                confidence_label = "HIGH"
            elif top_score >= 0.40:
                confidence_label = "MODERATE"
            elif top_score >= 0.20:
                confidence_label = "LOW"
            else:
                confidence_label = "UNKNOWN"

        # ── AMBIGUITY DETECTION (v5.0) ──
        ambiguity_is_ambiguous = False
        ambiguity_between: List[str] = []
        ambiguity_reason = ""
        if len(top) >= 2 and top[0].score > 0:
            score_gap_pct = (top[0].score - top[1].score) / max(0.001, top[0].score)
            same_group = top[0].crop_group == top[1].crop_group
            if score_gap_pct < 0.10 and same_group:
                ambiguity_is_ambiguous = True
                ambiguity_between = [c.name for c in top[:3] if c.crop_group == top[0].crop_group]
                ambiguity_reason = (
                    f"Top candidates are within 10% score and belong to the same "
                    f"group ({top[0].crop_group.replace('_', ' ')}). "
                    f"Fine-grained separation requires additional evidence."
                )

        # ── RECOMMENDATION LANGUAGE (v5.0 — per inference mode) ──
        # Use explicit language per user requirement #6
        top_name = top[0].name if top else "unknown"
        top_group_label = top[0].crop_group.replace("_", " ").title() if top else "Unknown"
        second_name = top[1].name if len(top) > 1 else None

        if inference_mode == "observed_timeseries":
            if confidence_label == "HIGH":
                recommendation = f"Likely current crop based on observed satellite time series. Strongest candidate: {top_name}."
            elif confidence_label == "MODERATE":
                recommendation = f"Likely {top_name}" + (f", possibly {second_name}" if second_name else "") + ". Observed vegetation behavior is consistent but not conclusive."
            else:
                recommendation = f"Best candidate from observed data: {top_name}. Evidence is weak — consider farmer confirmation."
        elif inference_mode == "context_only":
            recommendation = f"Plausible candidates based on soil, climate, and location. No satellite time-series evidence. Top candidate: {top_name}."
        else:  # prior_only
            recommendation = f"No crop was detected. These are regional likelihood candidates only."

        if ambiguity_is_ambiguous:
            recommendation += f" Note: ambiguous between {', '.join(ambiguity_between)}."

        # Use softmax share as top_confidence when available
        display_confidence = top_share if top_share is not None else top_score

        # Build evidence dict with full diagnostic data
        evidence = {
            "data_signals_available": data_signals,
            "engine_version": self.VERSION,
            "koppen_zone": koppen_zone,
            "calendar_region": calendar_region,
            "weights": {k: round(v, 3) for k, v in w.items() if v > 0},
            "ml_features": {
                "savitzky_golay_smoothing": smoothed_ndvi is not None,
                "temporal_smoothing_support": smoothing_support,
                "advanced_phenology": bool(advanced_phenology),
                "bayesian_posterior": bool(bayesian_posteriors),
                "entropy_confidence": entropy_val,
                "feedback_samples": n_feedback,
                "bayesian_weight": round(ALPHA_BAYESIAN, 3),
            },
        }
        
        # Add phenology metrics to evidence for debugging
        if advanced_phenology:
            evidence["phenology"] = {
                k: v for k, v in advanced_phenology.items()
                if isinstance(v, (int, float)) and v is not None
            }

        # ── v5.1: PRIOR_ONLY / CONTEXT_ONLY SEMANTIC FIX ──
        if inference_mode == "prior_only":
            result_top_crop = None
            result_top_confidence = 0.0
            result_confidence_label = "LOW"
        elif inference_mode == "context_only":
            result_top_crop = None
            result_top_confidence = 0.0
            result_confidence_label = confidence_label  # keep engine assessment
        else:  # observed_timeseries
            result_top_crop = top[0].code if top else "unknown"
            result_top_confidence = display_confidence
            result_confidence_label = confidence_label

        # Determine prediction depth and group/crop detection flags for rule-based path
        if inference_mode == "prior_only":
            pred_depth = "L0"
            det_group = False
            det_crop = False
        elif inference_mode == "context_only":
            pred_depth = "L1" if calendar_region else "L0"
            det_group = False
            det_crop = False
        else: # observed_timeseries
            # Do not let observed_timeseries alone imply detected_crop=True
            if result_top_crop is not None and result_top_crop != "unknown" and result_confidence_label in ("HIGH", "MODERATE"):
                pred_depth = "L3"
                det_group = True
                det_crop = True
            elif result_top_crop is not None and result_top_crop != "unknown":
                pred_depth = "L2"
                det_group = True
                det_crop = False
            else:
                pred_depth = "L0"
                det_group = False
                det_crop = False

        result = CropIdentificationResult(
            top_crop=result_top_crop,
            top_confidence=result_top_confidence,
            confidence_label=result_confidence_label,
            architecture_class=top[0].architecture if top else "unknown",
            candidates=top,
            total_crops_evaluated=len(self._all_crops) + len(NON_CROP_CLASSES),
            data_quality=data_quality,
            recommendation=recommendation,
            evidence=evidence,
            # Crop Intelligence v5.1 fields
            inference_mode=inference_mode,
            evidence_strength=evidence_strength,
            top_group=top[0].crop_group if top else "unknown",
            detected_crop=det_crop,
            prediction_depth=pred_depth,
            detected_crop_group=det_group,
            ambiguity_is_ambiguous=ambiguity_is_ambiguous,
            ambiguity_between=ambiguity_between,
            ambiguity_reason=ambiguity_reason,
        )

        logger.info(
            "[CropID] Result: %s (%.4f, %s) — evaluated %d crops, Bayesian=%s (α=%.2f)",
            result.top_crop, result.top_confidence,
            result.confidence_label, result.total_crops_evaluated,
            "ON" if bayesian_posteriors else "OFF", ALPHA_BAYESIAN,
        )
        
        # IMP-5: Cache result for feedback endpoint
        try:
            plot_id_arg = kwargs.get("plot_id") if hasattr(self, '_last_results') else None
            # We don't have plot_id in identify() args directly, but it's in the
            # API layer. Cache by top_crop + lat/lng as a proxy key.
            cache_key = f"{lat}_{lng}"
            self._last_results[cache_key] = {
                "phenology": advanced_phenology or {},
                "ndvi_series": (smoothed_list or ndvi_series or [])[:50],
                "top_crop": result.top_crop,
                "top_confidence": result.top_confidence,
                "confidence_label": result.confidence_label,
            }
            # Keep cache bounded (max 100 entries)
            if len(self._last_results) > 100:
                oldest_key = next(iter(self._last_results))
                del self._last_results[oldest_key]
        except Exception:
            pass
        
        return result

    # =========================================================================
    # MODULE I: Phenological Phase Detector (NEW v4.0)
    # =========================================================================

    def _detect_phenophase(self, ndvi_series: List[float], shape_desc: Optional[Dict]) -> str:
        """Detect current phenological phase from NDVI timeseries.
        
        Returns one of: 'greenup', 'peak', 'senescence', 'dormancy', 'evergreen'
        """
        if not ndvi_series or len(ndvi_series) < 5:
            return "unknown"

        cv = self._coefficient_of_variation(ndvi_series)
        if cv < 0.12:
            return "evergreen"

        # Look at the last 5 observations to determine current phase
        recent = ndvi_series[-5:]
        velocities = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
        avg_velocity = sum(velocities) / len(velocities)
        current_ndvi = recent[-1]
        peak_ndvi = max(ndvi_series)
        ndvi_ratio = current_ndvi / max(0.01, peak_ndvi)

        if avg_velocity > 0.02:
            return "greenup"
        elif avg_velocity < -0.02:
            return "senescence"
        elif ndvi_ratio > 0.85:
            return "peak"
        elif ndvi_ratio < 0.40:
            return "dormancy"
        else:
            return "peak" if avg_velocity >= 0 else "senescence"

    def _score_phenophase(
        self, crop: CropSpec,
        ndvi_series: List[float],
        peak_doy: Optional[int],
        shape_desc: Optional[Dict],
    ) -> float:
        """Score how well the detected phenological phase matches the crop's
        expected phase at this time of year."""
        phase = self._detect_phenophase(ndvi_series, shape_desc)
        if phase == "unknown":
            return 0.5

        ref = CROP_NDVI_SIGNATURES.get(crop.code)
        if ref is None:
            return 0.5

        ref_shape = ref.get("shape", "unimodal")

        # Evergreen phase: strongly favor evergreen/stable crops
        if phase == "evergreen":
            if ref_shape in ("evergreen", "stable"):
                return 1.0
            elif ref_shape == "multi_cut":
                return 0.5
            else:
                return 0.1  # Annual crop in evergreen field = very unlikely

        # For seasonal phases, score based on whether the phase is expected
        if phase == "greenup":
            # Greenup phase: crop should be in early season
            if ref_shape in ("evergreen", "stable"):
                return 0.4  # Evergreens don't have greenup
            return 0.8  # Most annual crops have a greenup phase

        if phase == "peak":
            # Peak: crop should be at its maximum
            if ref_shape in ("evergreen", "stable"):
                return 0.6  # Evergreens are always "peaked"
            return 0.9  # Good signal for annual crops

        if phase == "senescence":
            if ref_shape in ("evergreen", "stable"):
                return 0.2  # Evergreens don't senesce
            return 0.7

        if phase == "dormancy":
            if ref_shape in ("evergreen", "stable"):
                return 0.15  # Evergreens don't go dormant
            return 0.5  # Dormancy is normal for annuals between seasons

        return 0.5

    # =========================================================================
    # MODULE J: Area-Based Likelihood Prior (NEW v4.0)
    # =========================================================================

    def _score_area_prior(self, crop: CropSpec, area_ha: Optional[float],
                          irrigation_type: Optional[str] = None) -> float:
        """Score crop likelihood based on plot area and irrigation.
        
        Small plots (< 2ha) -> vegetables, orchards, greenhouse crops
        Medium plots (2-20ha) -> neutral, most crops possible
        Large plots (> 20ha) -> cereals, legumes, cotton, forage
        Drip irrigation -> vegetables, orchards (not cereals)
        """
        if area_ha is None:
            return 0.5

        arch = crop.architecture
        ref = CROP_NDVI_SIGNATURES.get(crop.code, {})
        ref_shape = ref.get("shape", "unimodal")
        is_drip = irrigation_type and irrigation_type.lower() in ("drip", "micro", "trickle")

        if area_ha < 1.0:
            # Very small: intensive crops
            if arch == "vegetable":
                return 0.95
            elif arch == "perennial":
                return 0.85
            elif arch in ("cereal", "legume"):
                return 0.20  # Very unlikely
            elif arch in ("maize", "cotton"):
                return 0.30
            return 0.45
        elif area_ha < 5.0:
            # Small: vegetables, orchards, some cereals
            if is_drip:
                # Drip irrigation on small plots = vegetable/orchard signal
                if arch == "vegetable":
                    return 0.95
                elif arch == "perennial":
                    return 0.90
                elif arch in ("cereal", "legume"):
                    return 0.30  # Cereals are rarely drip-irrigated
                return 0.50
            else:
                if arch == "vegetable":
                    return 0.85
                elif arch == "perennial":
                    return 0.80
                elif arch in ("cereal", "legume"):
                    return 0.55
                return 0.60
        elif area_ha < 20.0:
            # Medium: anything possible
            if is_drip:
                return 0.75 if arch in ("vegetable", "perennial") else 0.55
            return 0.65 if arch in ("vegetable", "perennial") else 0.70
        else:
            # Large: broad-acre crops
            if arch in ("cereal", "legume", "cotton", "maize"):
                return 0.90
            elif arch == "perennial" and ref_shape in ("evergreen", "stable"):
                return 0.70  # Large orchards exist
            elif arch == "vegetable":
                return 0.25
            return 0.50
    # =========================================================================
    # MODULE K: PlotDNA Soil/Vigor Scoring (NEW v4.0)
    # =========================================================================

    def _score_dna_traits(
        self, crop: CropSpec,
        vigor: Optional[float],
        water_retention: Optional[float],
        exhaustion: Optional[float],
        carbon_memory: Optional[float],
        future_proof: Optional[float],
    ) -> float:
        """Score crop suitability based on PlotDNA biophysical traits.
        
        DNA traits capture the inherent soil and microclimate characteristics:
        - vigor (alpha_vigor): Growth efficiency 0.7-1.3. High = productive soil.
        - water_retention (theta_retention): WHC modifier 0.5-1.5. High = wet soil.
        - exhaustion (exhaustion_index): Negative = soil fatigue. Positive = improving.
        - carbon_memory: Total unharvested biomass integral. High = good SOM.
        - future_proof: 0-100 projected viability score.
        """
        score = 0.0
        n = 0

        # 1. Vigor match: high-vigor soils suit demanding crops
        if vigor is not None:
            arch = crop.architecture
            if vigor > 1.1:
                # Vigorous soil — favor high-demand crops
                if arch in ("maize", "vegetable", "cotton"):
                    score += 0.9
                elif arch in ("cereal", "legume"):
                    score += 0.7
                else:
                    score += 0.6
            elif vigor > 0.9:
                # Normal vigor — neutral
                score += 0.7
            else:
                # Low vigor — favor hardy, low-input crops
                if arch in ("legume", "cereal"):
                    score += 0.8  # Legumes fix nitrogen, good for poor soil
                elif arch in ("perennial",):
                    score += 0.7  # Perennials tolerate poor soil
                else:
                    score += 0.4  # Demanding crops struggle
            n += 1

        # 2. Water retention match: high WHC → favor water-loving crops
        if water_retention is not None:
            water = crop.water_needs
            if water_retention > 1.2:
                # Very water-retentive soil
                if water == "high":
                    score += 0.9
                elif water == "medium":
                    score += 0.7
                else:
                    score += 0.5  # Drought-adapted crops don't benefit
            elif water_retention < 0.7:
                # Sandy, fast-draining soil
                if water == "low":
                    score += 0.9  # Drought-adapted crops thrive
                elif water == "medium":
                    score += 0.6
                else:
                    score += 0.3  # Water-loving crops suffer without irrigation
            else:
                score += 0.7  # Moderate retention → neutral
            n += 1

        # 3. Exhaustion penalty: fatigued soil penalizes intensive crops
        if exhaustion is not None:
            if exhaustion < -0.1:
                # Soil is declining
                if crop.architecture in ("maize", "cotton", "vegetable"):
                    score += 0.3  # Intensive crops will worsen exhaustion
                elif crop.architecture == "legume":
                    score += 0.9  # Legumes restore soil
                else:
                    score += 0.6
            else:
                score += 0.7  # Healthy soil
            n += 1

        # 4. Future proof score
        if future_proof is not None:
            if future_proof > 70:
                score += 0.8
            elif future_proof > 40:
                score += 0.6
            else:
                # Low future viability — favor resilient crops
                if crop.architecture in ("perennial", "legume"):
                    score += 0.7
                else:
                    score += 0.4
            n += 1

        return score / max(1, n)

    # =========================================================================
    # MODULE A: Per-Crop NDVI Reference Signature Match
    # =========================================================================

    def _score_ndvi_signature(
        self, crop: CropSpec,
        ndvi_series: Optional[List[float]],
        peak_ndvi: Optional[float],
        trough_ndvi: Optional[float],
    ) -> float:
        """Match observed NDVI against the crop's specific reference signature.
        Tolerances account for real-world NDVI noise (mixed pixels, cloud residuals)."""
        ref = CROP_NDVI_SIGNATURES.get(crop.code)
        if ref is None:
            # Fall back to architecture template matching with STRONG penalty.
            # Crops without science data should NEVER outscore crops with data.
            return self._score_temporal(crop, ndvi_series, None, peak_ndvi, trough_ndvi) * 0.65

        score = 0.0
        n = 0

        # ── Observed peak scaling factor ──
        # Real satellite NDVI is often 60-80% of literature reference values
        # due to sub-pixel mixing, atmospheric residuals, sparse canopy.
        # Normalize by scaling the observed peak to account for this.
        ref_peak = ref["peak_ndvi"]
        scale = 1.0
        if peak_ndvi is not None and ref_peak > 0:
            obs_ref_ratio = peak_ndvi / ref_peak
            # If observed is 50-90% of reference, it's still a match
            if 0.5 <= obs_ref_ratio <= 1.2:
                scale = obs_ref_ratio  # Scale reference down to match

        # 1. Peak NDVI match — account for measurement noise σ=0.15
        if peak_ndvi is not None:
            scaled_ref = ref_peak * min(1.0, max(0.6, scale))
            diff = abs(peak_ndvi - scaled_ref)
            score += math.exp(-(diff ** 2) / (2 * 0.15 ** 2))
            n += 1

        # 2. Trough NDVI match — σ=0.10
        if trough_ndvi is not None:
            ref_trough = ref["trough_ndvi"]
            diff = abs(trough_ndvi - ref_trough)
            score += math.exp(-(diff ** 2) / (2 * 0.10 ** 2))
            n += 1

        # 3. Amplitude match — σ=0.15 (most tolerant, since both peak and trough have noise)
        if peak_ndvi is not None and trough_ndvi is not None:
            obs_amp = peak_ndvi - trough_ndvi
            ref_amp = ref["amplitude"] * min(1.0, max(0.6, scale))
            diff = abs(obs_amp - ref_amp)
            score += math.exp(-(diff ** 2) / (2 * 0.15 ** 2))
            n += 1

        # 4. Shape type match — HARD gate
        if ndvi_series and len(ndvi_series) >= 5:
            obs_cv = self._coefficient_of_variation(ndvi_series)
            ref_shape = ref["shape"]
            if ref_shape in ("evergreen", "stable"):
                # Evergreen crops have CV < 0.15
                if obs_cv < 0.12:
                    score += 1.0
                elif obs_cv < 0.20:
                    score += 0.6
                elif obs_cv < 0.30:
                    score += 0.2
                else:
                    score += 0.02  # Hard mismatch
            elif ref_shape == "multi_cut":
                n_peaks = self._count_peaks(ndvi_series)
                if n_peaks >= 3:
                    score += 1.0
                elif n_peaks >= 2:
                    score += 0.7
                elif obs_cv > 0.25:
                    score += 0.4
                else:
                    score += 0.1
            elif ref_shape == "bimodal":
                n_peaks = self._count_peaks(ndvi_series)
                score += 0.9 if n_peaks == 2 else (0.5 if n_peaks >= 2 else 0.15)
            else:
                # Unimodal annual
                if obs_cv > 0.30:
                    score += 1.0
                elif obs_cv > 0.20:
                    score += 0.7
                elif obs_cv > 0.12:
                    score += 0.4
                else:
                    score += 0.05  # Too flat for annual crop
            n += 1

        # 5. Green-up rate match (BONUS: higher weight crops)
        if ndvi_series and len(ndvi_series) >= 5:
            ref_rate = ref.get("greenup_rate", 0)
            if ref_rate > 0:
                velocities = [ndvi_series[i+1] - ndvi_series[i] for i in range(len(ndvi_series)-1)]
                obs_rate = max(velocities) if velocities else 0
                ratio = min(obs_rate, ref_rate) / max(obs_rate, ref_rate, 0.001)
                score += ratio
                n += 1

        return score / max(1, n)

    # =========================================================================
    # NEW MODULE B: Regional Crop Calendar Windows
    # =========================================================================

    def _score_crop_calendar(
        self, crop: CropSpec,
        peak_doy: Optional[int],
        calendar_region: Optional[str],
    ) -> float:
        """Score whether the observed phenology matches the regional crop calendar.
        
        IMPORTANT: Evergreen/stable crops (citrus, olive, date palm) are
        year-round and should NOT be penalized for peak DOY timing.
        """
        if peak_doy is None or calendar_region is None:
            return 0.5

        # ── Evergreen/perennial exemption ──
        # Crops with "evergreen" or "stable" NDVI shape are green year-round;
        # their satellite "peak" is just noise, not a phenological signal.
        ref = CROP_NDVI_SIGNATURES.get(crop.code)
        if ref and ref.get("shape") in ("evergreen", "stable"):
            return 0.85  # High score: evergreen crops are ALWAYS in season

        calendar = CROP_CALENDARS.get(calendar_region, {})
        cal = calendar.get(crop.code)

        if cal is None:
            # Crop not in regional calendar → significant penalty
            # Crops absent from the local calendar are unlikely candidates.
            return 0.15

        harvest_start = cal["harvest_start"]
        harvest_end = cal["harvest_end"]

        # The peak NDVI should occur BEFORE harvest
        # Typical peak is 30-60 days before harvest start
        expected_peak_start = (harvest_start - 90) % 365
        expected_peak_end = harvest_start

        # Handle wrapping (e.g., peak in Dec-Jan for winter crops)
        if expected_peak_start < expected_peak_end:
            in_window = expected_peak_start <= peak_doy <= expected_peak_end
        else:
            in_window = peak_doy >= expected_peak_start or peak_doy <= expected_peak_end

        if in_window:
            return 1.0

        # Calculate circular distance
        def _circular_dist(a, b):
            d = abs(a - b)
            return min(d, 365 - d)

        dist = min(_circular_dist(peak_doy, expected_peak_start),
                   _circular_dist(peak_doy, expected_peak_end))

        # SHARP exponential decay: σ=15 days → 30 days off = score 0.14
        return max(0.02, math.exp(-dist / 15.0))

    # =========================================================================
    # NEW MODULE C: Multi-Spectral Index Analysis
    # =========================================================================

    def _score_spectral(
        self, crop: CropSpec,
        evi: Optional[float],
        ndmi: Optional[float],
        ndwi: Optional[float],
    ) -> float:
        """Score using EVI/NDMI/NDWI against crop-specific reference ranges."""
        ref = SPECTRAL_SIGNATURES.get(crop.code)
        if ref is None:
            return 0.5  # No spectral reference for this crop

        score = 0.0
        n = 0

        # EVI match
        if evi is not None and "evi_peak" in ref:
            lo, hi = ref["evi_peak"]
            if lo <= evi <= hi:
                score += 1.0
            else:
                dist = min(abs(evi - lo), abs(evi - hi))
                score += max(0.0, 1.0 - dist * 3.0)
            n += 1

        # NDMI match
        if ndmi is not None:
            key = "ndmi_transplant" if "ndmi_transplant" in ref else "ndmi_peak"
            if key in ref:
                lo, hi = ref[key]
                if lo <= ndmi <= hi:
                    score += 1.0
                else:
                    dist = min(abs(ndmi - lo), abs(ndmi - hi))
                    score += max(0.0, 1.0 - dist * 3.0)
                n += 1

        # NDWI match
        if ndwi is not None:
            key = "ndwi_flood" if "ndwi_flood" in ref else "ndwi_peak"
            if key in ref:
                lo, hi = ref[key]
                if lo <= ndwi <= hi:
                    score += 1.0
                else:
                    dist = min(abs(ndwi - lo), abs(ndwi - hi))
                    score += max(0.0, 1.0 - dist * 3.0)
                n += 1

        return score / max(1, n)

    # =========================================================================
    # NEW MODULE D: Köppen Climate Zone Affinity
    # =========================================================================

    def _score_koppen(self, crop: CropSpec, koppen_zone: Optional[str]) -> float:
        """Score crop suitability for the detected Köppen climate zone."""
        if koppen_zone is None:
            return 0.5

        affinity = KOPPEN_CROP_AFFINITY.get(crop.code)
        if affinity is not None:
            raw = affinity.get(koppen_zone, 0.2)
            # Hard elimination: if affinity <= 0.1, the crop is nearly
            # impossible in this climate (e.g., banana in BSk)
            if raw <= 0.1:
                return 0.02
            return raw

        # Fallback: use architecture-level defaults
        arch_defaults = {
            "cereal":       {"Csa": 0.9, "Csb": 0.8, "BSk": 0.7, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.7, "Cfb": 0.7, "Dfa": 0.6},
            "maize":        {"Csa": 0.7, "Csb": 0.6, "BSk": 0.4, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.9, "Cfb": 0.7, "Dfa": 0.8},
            "rice":         {"Csa": 0.4, "Csb": 0.2, "BSk": 0.1, "BSh": 0.2, "BWh": 0.3, "Cfa": 0.8, "Cfb": 0.3, "Dfa": 0.5, "Aw": 0.9, "Af": 1.0},
            "legume":       {"Csa": 0.9, "Csb": 0.7, "BSk": 0.7, "BSh": 0.5, "BWh": 0.3, "Cfa": 0.5, "Cfb": 0.5, "Dfa": 0.4},
            "vegetable":    {"Csa": 0.7, "Csb": 0.8, "BSk": 0.4, "BSh": 0.4, "BWh": 0.3, "Cfa": 0.7, "Cfb": 0.8, "Dfa": 0.6},
            "perennial":    {"Csa": 0.9, "Csb": 0.7, "BSk": 0.5, "BSh": 0.4, "BWh": 0.3, "Cfa": 0.5, "Cfb": 0.4, "Dfa": 0.3},
            "cotton":       {"Csa": 0.7, "Csb": 0.4, "BSk": 0.4, "BSh": 0.7, "BWh": 0.5, "Cfa": 0.9, "Cfb": 0.2, "Dfa": 0.5},
            "tropical_tree":{"Csa": 0.05, "Csb": 0.02, "BSk": 0.01, "BSh": 0.15, "BWh": 0.10, "Cfa": 0.3, "Cfb": 0.02, "Dfa": 0.01, "Aw": 0.9, "Af": 1.0},
        }
        arch_aff = arch_defaults.get(crop.architecture, {})
        raw = arch_aff.get(koppen_zone, 0.2)
        return 0.02 if raw <= 0.1 else raw

    # =========================================================================
    # NEW MODULE E: Aridity Index & Water Feasibility
    # =========================================================================

    def _score_aridity(
        self, crop: CropSpec,
        mean_temp_c: Optional[float],
        irrigation_type: Optional[str],
        annual_rainfall_mm: Optional[float] = None,
        et0_mm: Optional[float] = None,
    ) -> float:
        """Score crop feasibility based on estimated aridity."""
        is_irrigated = irrigation_type and irrigation_type.upper() in ("DRIP", "PIVOT", "SPRINKLER", "FLOOD")

        # 1. Check crop-specific thresholds
        thresholds = ARIDITY_CROP_THRESHOLDS.get(crop.code)
        if thresholds is None:
            # No specific threshold — use water_needs as generic guide
            wn = crop.water_needs
            if is_irrigated:
                return 0.7  # Irrigation makes most crops feasible
            if wn == "low":
                return 0.8
            elif wn == "medium":
                return 0.6
            else:
                return 0.3  # High water needs in unknown aridity

        min_idm, ideal_idm = thresholds

        if is_irrigated:
            # Irrigated: most crops feasible, prefer those adapted to local temps
            if mean_temp_c is not None and crop.optimal_temp_min <= mean_temp_c <= crop.optimal_temp_max:
                return 0.9
            return 0.6

        # 2. Non-irrigated: calculate de Martonne index from precipitation & temperature
        # If we have real rainfall + ET0: calculate P/PET aridity index and map to de Martonne
        if annual_rainfall_mm is not None and et0_mm is not None:
            aridity_index = annual_rainfall_mm / max(1.0, et0_mm)
            estimated_idm = aridity_index * 40.0
        elif annual_rainfall_mm is not None and mean_temp_c is not None:
            estimated_idm = annual_rainfall_mm / max(1.0, mean_temp_c + 10.0)
        elif mean_temp_c is not None:
            # Fallback: estimate aridity from temperature (rough proxy for MENA)
            estimated_idm = max(5.0, 40.0 - mean_temp_c)
        else:
            # No climate parameters available
            return 0.5

        if estimated_idm >= min_idm:
            closeness = min(1.0, (estimated_idm - min_idm) / max(1.0, ideal_idm - min_idm))
            return 0.5 + 0.5 * closeness
        else:
            return max(0.05, 0.5 * (estimated_idm / max(1.0, min_idm)))

    # =========================================================================
    # NEW MODULE F: Agronomic Rotation Rules
    # =========================================================================

    def _score_rotation(
        self, crop: CropSpec,
        previous_crops: Optional[List[Dict]],
    ) -> float:
        """Score based on agronomic rotation rules."""
        if not previous_crops:
            return 0.5

        # Get the last crop's architecture
        last_crop = previous_crops[-1] if previous_crops else {}
        last_code = last_crop.get("code", last_crop.get("crop_code", ""))
        last_arch = last_crop.get("architecture", "")

        # If we have the exact code, look up its architecture
        if not last_arch and last_code:
            last_spec = CROP_REGISTRY.get(last_code)
            if last_spec:
                last_arch = last_spec.architecture

        if not last_arch:
            return 0.5

        # Look up rotation preference
        rotation_prefs = ROTATION_MATRIX.get(last_arch, {})
        return rotation_prefs.get(crop.architecture, 0.4)

    # =========================================================================
    # NEW MODULE G: NDVI Curve Shape Descriptors
    # =========================================================================

    def _compute_shape_descriptors(
        self,
        ndvi_series: List[float],
        peak_ndvi: Optional[float],
        trough_ndvi: Optional[float],
    ) -> Dict[str, float]:
        """Extract 6 shape descriptors from the NDVI timeseries."""
        n = len(ndvi_series)
        if n < 5:
            return {}

        peak_idx = ndvi_series.index(max(ndvi_series)) if ndvi_series else 0

        # 1. Green-up rate (max positive velocity in first half)
        velocities = [ndvi_series[i+1] - ndvi_series[i] for i in range(n-1)]
        greenup_rate = max(velocities[:max(1, peak_idx)]) if peak_idx > 0 else 0.0

        # 2. Senescence rate (max negative velocity in second half)
        senescence_rate = abs(min(velocities[peak_idx:])) if peak_idx < n-1 else 0.0

        # 3. Season integral (normalized AUC)
        season_integral = sum(max(0, v) for v in ndvi_series) / n

        # 4. Asymmetry ratio (how early/late the peak is)
        asymmetry = peak_idx / max(1, n - 1)

        # 5. Number of peaks
        n_peaks = self._count_peaks(ndvi_series)

        # 6. Amplitude
        amplitude = (peak_ndvi or max(ndvi_series)) - (trough_ndvi or min(ndvi_series))

        # 7. Coefficient of variation
        cv = self._coefficient_of_variation(ndvi_series)

        return {
            "greenup_rate": greenup_rate,
            "senescence_rate": senescence_rate,
            "season_integral": season_integral,
            "asymmetry": asymmetry,
            "n_peaks": n_peaks,
            "amplitude": amplitude,
            "cv": cv,
        }

    def _score_shape(self, crop: CropSpec, desc: Dict[str, float]) -> float:
        """Score how well observed shape descriptors match the crop's expected profile."""
        ref = CROP_NDVI_SIGNATURES.get(crop.code)
        if ref is None:
            # Fallback: use architecture-level shape matching
            return self._shape_score_by_architecture(crop, desc)

        score = 0.0
        n = 0

        # 1. Amplitude match
        ref_amp = ref["amplitude"]
        obs_amp = desc.get("amplitude", 0.0)
        diff = abs(obs_amp - ref_amp)
        score += max(0.0, 1.0 - diff * 3.0)
        n += 1

        # 2. Season integral match
        ref_integral = ref["season_integral"]
        obs_integral = desc.get("season_integral", 0.0)
        # Normalize observed integral relative to wheat=1.0 baseline
        norm_integral = obs_integral / 0.35 if obs_integral > 0 else 0  # 0.35 ≈ typical wheat mean NDVI
        diff = abs(norm_integral - ref_integral)
        score += max(0.0, 1.0 - diff * 1.5)
        n += 1

        # 3. Peak timing (asymmetry vs peak_frac)
        ref_peak_frac = ref["peak_frac"]
        obs_asymmetry = desc.get("asymmetry", 0.5)
        diff = abs(obs_asymmetry - ref_peak_frac)
        score += max(0.0, 1.0 - diff * 3.0)
        n += 1

        # 4. Number of peaks + CV match (STRONGEST signal for evergreen)
        ref_n_peaks = ref["n_peaks"]
        obs_n_peaks = desc.get("n_peaks", 1)
        obs_cv = desc.get("cv", 0.5)
        ref_shape = ref.get("shape", "unimodal")

        if ref_shape in ("evergreen", "stable"):
            # Evergreen: expect 0 peaks, very low CV
            if obs_cv < 0.12:
                score += 1.0  # Perfect evergreen match
            elif obs_cv < 0.20:
                score += 0.7
            elif obs_cv < 0.30:
                score += 0.3
            else:
                score += 0.02  # Annual-like CV = hard mismatch for evergreen
        elif ref_n_peaks >= 3:
            # Multi-cut: expect multiple peaks
            score += 1.0 if obs_n_peaks >= 2 else 0.3
        else:
            # Unimodal annual: expect 1 peak + high CV
            if obs_cv < 0.12:
                # Very low CV → this is clearly NOT a seasonal crop
                score += 0.02
            elif obs_n_peaks == 1 and obs_cv > 0.20:
                score += 1.0
            elif obs_n_peaks == 1:
                score += 0.6
            else:
                score += 0.3
        n += 1

        # 5. Green-up rate match
        ref_greenup = ref["greenup_rate"]
        obs_greenup = desc.get("greenup_rate", 0.0)
        if ref_greenup > 0:
            ratio = min(obs_greenup, ref_greenup) / max(obs_greenup, ref_greenup, 0.001)
            score += ratio
        else:
            score += 0.5
        n += 1

        return score / max(1, n)

    def _shape_score_by_architecture(self, crop: CropSpec, desc: Dict[str, float]) -> float:
        """Fallback shape scoring using architecture templates."""
        arch = crop.architecture
        cv = desc.get("cv", 0.5)
        n_peaks = desc.get("n_peaks", 1)

        if arch in ("perennial", "tropical_tree"):
            # Expect low CV (evergreen/stable) but penalize compared to
            # crops WITH actual science data — fallback should never outscore.
            return 0.6 if cv < 0.15 else 0.3 if cv < 0.30 else 0.1
        elif arch in ("cereal", "maize", "legume", "cotton"):
            # Expect high CV, 1 peak (unimodal annual)
            if cv > 0.25 and n_peaks == 1:
                return 0.8
            return 0.4
        elif arch == "rice":
            # Unimodal with very low trough
            return 0.7 if cv > 0.30 else 0.4
        else:
            return 0.5

    # =========================================================================
    # NEW MODULE H: Botanical Family + Per-Crop Tiebreaker
    # =========================================================================

    def _score_family_tiebreak(
        self, crop: CropSpec,
        lat: Optional[float],
        mean_temp_c: Optional[float],
        irrigation_type: Optional[str],
        area_ha: Optional[float],
        *,
        dna_vigor: Optional[float] = None,
        dna_water_retention: Optional[float] = None,
    ) -> float:
        """
        Per-crop discriminator using botanical family and unique registry fields.
        This is the final tiebreaker that separates crops within the same architecture.

        v4.1: Enhanced with botanical-family-specific biophysical rules for
        Rutaceae (Citrus), Oleaceae (Olive), and Arecaceae (Date Palm).
        PlotDNA traits (vigor, water retention) provide additional discrimination
        when available.
        """
        score = 0.0
        n = 0

        # 1. Growing season length vs latitude
        if lat is not None:
            abs_lat = abs(lat)
            gd = crop.growing_days
            if abs_lat >= 40:
                score += 1.0 if gd <= 100 else 0.8 if gd <= 140 else 0.5 if gd <= 200 else 0.2
            elif abs_lat >= 30:
                score += 0.9 if 90 <= gd <= 200 else 0.6 if gd <= 280 else 0.7 if gd >= 365 else 0.4
            elif abs_lat >= 15:
                score += 0.8 if 60 <= gd <= 250 else 0.9 if gd >= 300 else 0.5
            else:
                score += 1.0 if gd >= 200 else 0.6 if gd >= 100 else 0.3
            n += 1

        # 2. GDD base temperature as climate indicator
        if lat is not None:
            abs_lat = abs(lat)
            base_t = crop.gdd_base_temp
            if abs_lat >= 40:
                score += 1.0 if base_t <= 5 else 0.6 if base_t <= 10 else 0.2
            elif abs_lat >= 30:
                score += 0.9 if base_t <= 10 else 0.6 if base_t <= 15 else 0.3
            else:
                score += 1.0 if base_t >= 10 else 0.6 if base_t >= 5 else 0.3
            n += 1

        # 3. Optimal temperature range vs observed
        if mean_temp_c is not None:
            opt_min = crop.optimal_temp_min
            opt_max = crop.optimal_temp_max
            mid_opt = (opt_min + opt_max) / 2.0
            if opt_min <= mean_temp_c <= opt_max:
                closeness = 1.0 - abs(mean_temp_c - mid_opt) / max(1, (opt_max - opt_min) / 2)
                score += 0.7 + 0.3 * max(0, closeness)
            elif mean_temp_c < opt_min:
                score += max(0.05, 1.0 - (opt_min - mean_temp_c) * 0.1)
            else:
                score += max(0.05, 1.0 - (mean_temp_c - opt_max) * 0.1)
            n += 1

        # 4. Water needs vs irrigation
        if irrigation_type:
            wn = crop.water_needs
            irrig = irrigation_type.upper()
            if irrig in ("DRIP", "PIVOT", "SPRINKLER"):
                score += {"high": 0.9, "medium": 0.7, "low": 0.4}.get(wn, 0.5)
            elif irrig in ("RAINFED", "NONE", ""):
                score += {"low": 1.0, "medium": 0.6, "high": 0.2}.get(wn, 0.5)
            elif irrig == "FLOOD":
                score += 1.0 if crop.architecture == "rice" else (0.6 if wn == "high" else 0.2)
            else:
                score += 0.5
            n += 1

        # ── 6. Botanical Family Discriminator (v4.1) ──────────────────────
        # Use the crop's botanical family to apply biophysically grounded
        # discriminator rules. This is the primary mechanism that separates
        # Citrus (Rutaceae) from Olive (Oleaceae) and Date Palm (Arecaceae)
        # when they share the same "perennial" architecture.
        family = BOTANICAL_FAMILIES.get(crop.code, crop.family if hasattr(crop, 'family') else "")
        irrig_up = (irrigation_type or "").upper()
        is_drip = irrig_up in ("DRIP", "PIVOT", "SPRINKLER")
        is_rainfed = irrig_up in ("RAINFED", "NONE", "")

        if family == "Rutaceae":
            # ── CITRUS (Rutaceae) ─────────────────────────────────────
            # Citrus orchards are *always* drip-irrigated in MENA/Algeria.
            # They require fertile, high-vigor soil with good water-holding
            # capacity. Rainfed citrus is extremely rare in this region.
            fam_score = 0.5  # baseline
            if is_drip:
                fam_score += 0.35  # strong boost: drip + citrus is canonical
            elif is_rainfed:
                fam_score -= 0.20  # rainfed citrus is very unlikely in MENA
            # Vigor: citrus needs productive soil
            if dna_vigor is not None:
                if dna_vigor > 1.0:
                    fam_score += 0.10
                elif dna_vigor < 0.85:
                    fam_score -= 0.10
            # Water retention: citrus prefers moderate-to-high WHC
            if dna_water_retention is not None:
                if dna_water_retention > 0.9:
                    fam_score += 0.05
                elif dna_water_retention < 0.6:
                    fam_score -= 0.10
            score += max(0.05, min(1.0, fam_score))
            n += 1

        elif family == "Oleaceae":
            # ── OLIVE (Oleaceae) ──────────────────────────────────────
            # Olives are extremely drought-tolerant and commonly rainfed
            # in Mediterranean/MENA. They thrive in low-vigor, low-WHC
            # soils. Drip-irrigated olives exist but are less common.
            fam_score = 0.5
            if is_rainfed:
                fam_score += 0.30  # rainfed olive is canonical
            elif is_drip:
                fam_score -= 0.05  # drip olive is possible but less typical
            # Vigor: olives tolerate low-vigor soil well
            if dna_vigor is not None:
                if dna_vigor < 0.95:
                    fam_score += 0.10
                elif dna_vigor > 1.15:
                    fam_score -= 0.05  # very high vigor → more likely citrus
            # Water retention: olives prefer low WHC (dry rocky soils)
            if dna_water_retention is not None:
                if dna_water_retention < 0.8:
                    fam_score += 0.10
                elif dna_water_retention > 1.2:
                    fam_score -= 0.05
            score += max(0.05, min(1.0, fam_score))
            n += 1

        elif family == "Arecaceae":
            # ── DATE PALM (Arecaceae) ─────────────────────────────────
            # Date palms require extreme heat (>25°C mean) and are found
            # only at low latitudes (<33°) in the Saharan belt. Always
            # irrigated (oasis agriculture).
            fam_score = 0.5
            if lat is not None and abs(lat) < 33:
                fam_score += 0.25
            elif lat is not None and abs(lat) >= 37:
                fam_score -= 0.25  # too far north for date palms
            if mean_temp_c is not None:
                if mean_temp_c >= 25:
                    fam_score += 0.20
                elif mean_temp_c < 18:
                    fam_score -= 0.20
            if is_drip:
                fam_score += 0.05
            score += max(0.05, min(1.0, fam_score))
            n += 1

        return score / max(1, n)

    # =========================================================================
    # Utility methods
    # =========================================================================

    @staticmethod
    def _coefficient_of_variation(series: List[float]) -> float:
        """Compute CV = std/mean for a numeric series."""
        if not series:
            return 0.0
        mean = sum(series) / len(series)
        if mean == 0:
            return 0.0
        variance = sum((x - mean) ** 2 for x in series) / len(series)
        return math.sqrt(variance) / abs(mean)

    @staticmethod
    def _count_peaks(series: List[float], threshold: float = 0.05) -> int:
        """Count local maxima in a timeseries, filtering noise below threshold."""
        if len(series) < 3:
            return 0
        peaks = 0
        for i in range(1, len(series) - 1):
            if series[i] > series[i-1] + threshold and series[i] > series[i+1] + threshold:
                peaks += 1
        return peaks

    def _check_region_compat(self, crop: CropSpec, koppen_zone: str) -> bool:
        """Check if the crop's region_tags are compatible with the detected climate.
        Returns False if there's a definitive mismatch (e.g., tropical-only crop in BSk).
        """
        tags = crop.region_tags
        if not tags:
            return True  # No tags → assume compatible

        # Map Köppen zones to broad climate regions
        koppen_region_map = {
            "Af": {"tropical"}, "Am": {"tropical"}, "Aw": {"tropical", "subtropical"},
            "BWh": {"arid", "desert"}, "BWk": {"arid", "desert", "continental"},
            "BSh": {"semi-arid", "subtropical"}, "BSk": {"semi-arid", "temperate"},
            "Csa": {"mediterranean", "temperate", "warm-temperate"},
            "Csb": {"mediterranean", "temperate"},
            "Cfa": {"subtropical", "temperate", "humid"},
            "Cfb": {"temperate", "oceanic"},
            "Dfa": {"continental", "temperate"}, "Dfb": {"continental"},
        }

        possible_regions = koppen_region_map.get(koppen_zone, set())
        if not possible_regions:
            return True  # Unknown zone → don't penalize

        # Check if ANY crop tag overlaps with the climate region
        tag_set = set(t.lower().replace("_", "-") for t in tags)
        # Also add broader aliases
        if "mena" in tag_set or "north-africa" in tag_set or "algeria" in tag_set:
            tag_set.update({"mediterranean", "semi-arid", "arid"})
        if "europe" in tag_set:
            tag_set.update({"temperate", "mediterranean"})
        if "asia" in tag_set or "south-asia" in tag_set:
            tag_set.update({"tropical", "subtropical"})
        if "global" in tag_set or "worldwide" in tag_set:
            return True  # Globally grown → always compatible

        # If the crop has explicit tropical-only tags and we're in Mediterranean → incompatible
        overlap = tag_set & possible_regions
        if overlap:
            return True

        # No overlap but check if crop has generic/broad tags
        if any(t in tag_set for t in ("temperate", "subtropical", "warm", "warm-temperate")):
            return True

        return False

    # =========================================================================
    # LEGACY Module 1: NDVI Temporal Signature Matcher (w=0.30)
    # =========================================================================

    def _score_temporal(
        self,
        crop: CropSpec,
        ndvi_series: Optional[List[float]],
        velocity: Optional[List[float]],
        peak_ndvi: Optional[float],
        trough_ndvi: Optional[float],
    ) -> float:
        """
        Score how well the observed NDVI curve matches the expected shape
        for this crop's architecture class.

        Uses:
          - Peak NDVI amplitude match
          - Trough NDVI (evergreen vs annual discrimination)
          - Curve shape (seasonal range)
          - Growth velocity consistency
        """
        if peak_ndvi is None:
            return 0.5  # No data → neutral score

        template = self._templates.get(crop.architecture)
        if not template:
            return 0.5

        score = 0.0
        n_checks = 0

        # Check 1: Peak NDVI within expected range
        pmin, pmax = template["peak_ndvi_range"]
        if pmin <= peak_ndvi <= pmax:
            score += 1.0
        else:
            # Distance-based degradation
            dist = min(abs(peak_ndvi - pmin), abs(peak_ndvi - pmax))
            score += max(0.0, 1.0 - dist * 5.0)
        n_checks += 1

        # Check 2: Trough NDVI discriminates evergreen vs annual
        if trough_ndvi is not None:
            expected_min = template["min_ndvi"]
            is_evergreen = template["shape"] == "evergreen"

            if is_evergreen:
                # Evergreen should have high trough
                if trough_ndvi >= expected_min:
                    score += 1.0
                else:
                    score += max(0.0, trough_ndvi / max(0.01, expected_min))
            else:
                # Annual should have low trough
                if trough_ndvi <= expected_min + 0.10:
                    score += 1.0
                elif trough_ndvi <= expected_min + 0.25:
                    score += 0.6
                else:
                    score += 0.2  # High trough but expected annual → poor match
            n_checks += 1

        # Check 3: Seasonal amplitude
        if peak_ndvi is not None and trough_ndvi is not None:
            seasonal_range = peak_ndvi - trough_ndvi
            if template["shape"] == "evergreen":
                # Expect low seasonal range
                if seasonal_range < 0.20:
                    score += 1.0
                elif seasonal_range < 0.35:
                    score += 0.6
                else:
                    score += 0.2
            else:
                # Expect high seasonal range
                if seasonal_range > 0.30:
                    score += 1.0
                elif seasonal_range > 0.15:
                    score += 0.6
                else:
                    score += 0.2
            n_checks += 1

        # Check 4: Growth velocity match (if available)
        if velocity and len(velocity) > 20:
            max_vel = max(velocity)
            expected_slope = template["greenup_slope"]
            if expected_slope > 0:
                ratio = max_vel / expected_slope
                # Good match if ratio is between 0.5 and 2.0
                if 0.5 <= ratio <= 2.0:
                    score += 1.0
                elif 0.3 <= ratio <= 3.0:
                    score += 0.5
                else:
                    score += 0.1
            n_checks += 1

        return score / max(1, n_checks)

    # =========================================================================
    # Module 2: Phenological Profile Scorer (w=0.25)
    # =========================================================================

    def _score_phenological(
        self,
        crop: CropSpec,
        peak_doy: Optional[int],
        greenup_doy: Optional[int],
        senescence_doy: Optional[int],
        season_length_days: Optional[int],
        greenup_velocity: Optional[float],
        gdd_accumulated: Optional[float],
    ) -> float:
        """
        Score phenological timing match.

        Key discriminators:
          - Season length: barley~130d, olive~365d, cotton~160d
          - GDD to maturity match
          - Peak DOY timing (winter vs summer crop)
        """
        score = 0.0
        n_checks = 0

        # If no data at all, return neutral (FIX: was returning 0.0)
        if all(x is None for x in [peak_doy, greenup_doy, senescence_doy,
                                     season_length_days, greenup_velocity, gdd_accumulated]):
            return 0.5

        # Check 1: Season length match
        if season_length_days is not None and season_length_days > 0:
            expected_days = crop.growing_days
            ratio = season_length_days / expected_days
            # Perfect match at ratio=1.0
            deviation = abs(1.0 - ratio)
            if deviation < 0.15:
                score += 1.0
            elif deviation < 0.30:
                score += 0.7
            elif deviation < 0.50:
                score += 0.4
            else:
                score += 0.1
            n_checks += 1

        # Check 2: GDD match
        if gdd_accumulated is not None and gdd_accumulated > 0:
            # Approximate expected GDD from growing_days and base temp
            # Typical GDD = growing_days × (mean_temp - base_temp)
            # For this comparison, use registry's growing_days as proxy
            # Crops with similar GDD requirements will score similarly
            expected_gdd = crop.growing_days * max(1, (25 - crop.gdd_base_temp) * 0.6)
            gdd_ratio = gdd_accumulated / max(1, expected_gdd)
            deviation = abs(1.0 - gdd_ratio)
            if deviation < 0.20:
                score += 1.0
            elif deviation < 0.40:
                score += 0.6
            elif deviation < 0.60:
                score += 0.3
            else:
                score += 0.1
            n_checks += 1

        # Check 3: Peak DOY classification
        # Winter crops: peak DOY 100-160 (Apr-Jun in Northern Hemisphere)
        # Summer crops: peak DOY 180-260 (Jul-Sep)
        # Perennials: peak DOY 120-180 (May-Jun) with weak signal
        if peak_doy is not None:
            arch = crop.architecture
            if arch in ("cereal",):
                # Winter cereals peak DOY 100-160
                if 90 <= peak_doy <= 170:
                    score += 1.0
                elif 60 <= peak_doy <= 200:
                    score += 0.5
                else:
                    score += 0.2
            elif arch in ("maize", "cotton"):
                # Summer crops peak DOY 180-260
                if 170 <= peak_doy <= 270:
                    score += 1.0
                elif 140 <= peak_doy <= 300:
                    score += 0.5
                else:
                    score += 0.2
            elif arch in ("rice",):
                # Rice: variable, but typically DOY 200-280
                if 180 <= peak_doy <= 290:
                    score += 0.9
                elif 150 <= peak_doy <= 310:
                    score += 0.5
                else:
                    score += 0.3
            elif arch in ("legume",):
                # Legumes: variable, DOY 100-200
                if 90 <= peak_doy <= 210:
                    score += 0.8
                else:
                    score += 0.4
            elif arch in ("vegetable",):
                # Vegetables: any season, low discrimination
                score += 0.5
            elif arch in ("perennial", "tropical_tree"):
                # Perennials: weak seasonal signal, any peak is OK
                score += 0.6
            n_checks += 1

        # Check 4: Green-up velocity
        if greenup_velocity is not None and greenup_velocity > 0:
            template = self._templates.get(crop.architecture, {})
            expected_slope = template.get("greenup_slope", 0.005)
            # greenup_velocity from phenological fingerprint is ×1000 scaled
            obs_slope = greenup_velocity / 1000.0
            if expected_slope > 0:
                ratio = obs_slope / expected_slope
                if 0.5 <= ratio <= 2.0:
                    score += 1.0
                elif 0.3 <= ratio <= 3.0:
                    score += 0.5
                else:
                    score += 0.1
            n_checks += 1

        return score / max(1, n_checks)

    # =========================================================================
    # Module 3: SAR Structure Discriminator (w=0.15)
    # =========================================================================

    def _score_sar(
        self,
        crop: CropSpec,
        vh_mean: Optional[float],
        vv_mean: Optional[float],
        vh_seasonal_range: Optional[float],
    ) -> float:
        """
        Score SAR backscatter profile match.

        Discrimination rules (Veloso et al., 2017):
          - Trees/orchards: high VH (-10 to -14 dB), low seasonal variation
          - Cereals: moderate VH (-14 to -18 dB), strong seasonal variation
          - Bare/low veg: low VH (< -18 dB)
          - Rice: distinctive flooding signature (very low VV during paddy)
          - VH/VV ratio: broadleaf > narrow-leaf
        """
        if vh_mean is None:
            return 0.5  # No SAR data → neutral

        score = 0.0
        n_checks = 0
        arch = crop.architecture

        # Check 1: VH mean backscatter level
        if arch in ("perennial", "tropical_tree"):
            # Trees: high VH (-8 to -14 dB)
            if -14.0 <= vh_mean <= -8.0:
                score += 1.0
            elif -16.0 <= vh_mean <= -6.0:
                score += 0.6
            else:
                score += 0.2
        elif arch in ("cereal", "legume", "cotton"):
            # Field crops: moderate VH (-14 to -20 dB)
            if -20.0 <= vh_mean <= -14.0:
                score += 1.0
            elif -22.0 <= vh_mean <= -12.0:
                score += 0.6
            else:
                score += 0.2
        elif arch == "maize":
            # Maize: higher VH than wheat (-12 to -16 dB) due to tall canopy
            if -16.0 <= vh_mean <= -10.0:
                score += 1.0
            elif -18.0 <= vh_mean <= -8.0:
                score += 0.6
            else:
                score += 0.2
        elif arch == "rice":
            # Rice: variable VH due to flooding cycles
            if -20.0 <= vh_mean <= -14.0:
                score += 0.8
            else:
                score += 0.4
        elif arch == "vegetable":
            # Low canopy vegetables: low VH
            if -22.0 <= vh_mean <= -16.0:
                score += 0.8
            else:
                score += 0.4
        n_checks += 1

        # Check 2: VH seasonal range discriminates annual vs perennial
        if vh_seasonal_range is not None:
            if arch in ("perennial", "tropical_tree"):
                # Low seasonal variation expected
                if vh_seasonal_range < 3.0:
                    score += 1.0
                elif vh_seasonal_range < 5.0:
                    score += 0.6
                else:
                    score += 0.2
            else:
                # Annual crops: high seasonal variation
                if vh_seasonal_range > 4.0:
                    score += 1.0
                elif vh_seasonal_range > 2.0:
                    score += 0.6
                else:
                    score += 0.3
            n_checks += 1

        # Check 3: Cross-pol ratio VH/VV discriminates leaf type
        if vv_mean is not None and vh_mean is not None:
            # Cross-pol ratio in dB
            xpol = vh_mean - vv_mean
            if arch in ("maize", "perennial", "tropical_tree"):
                # Broadleaf/tall: higher cross-pol (closer to 0)
                if xpol > -6.0:
                    score += 0.8
                else:
                    score += 0.3
            elif arch in ("cereal", "rice"):
                # Narrow-leaf: lower cross-pol
                if xpol <= -6.0:
                    score += 0.8
                else:
                    score += 0.3
            else:
                score += 0.5  # Neutral for other types
            n_checks += 1

        return score / max(1, n_checks)

    # =========================================================================
    # Module 4: Location Prior Filter (w=0.20)
    # =========================================================================

    def _score_location(
        self,
        crop: CropSpec,
        lat: Optional[float],
        lng: Optional[float],
        climate_zone: Optional[str],
        elevation_m: Optional[float],
    ) -> float:
        """
        Score geographic and climatic compatibility.

        Uses the crop's region_tags from the centralized registry (209 crops)
        to filter climatically impossible crops and boost likely ones.
        """
        if lat is None and climate_zone is None:
            return 0.5  # No location data → neutral

        score = 0.0
        n_checks = 0
        crop_tags = set(crop.region_tags)

        # Check 1: Region tag specificity scoring
        # More specific matches score higher; generic catch-all tags score lower.
        if climate_zone:
            zone_key = climate_zone.lower().replace(" ", "").replace("-", "")
            expected_regions = _CLIMATE_REGION_MAP.get(zone_key, [])

            if expected_regions:
                overlap = crop_tags.intersection(expected_regions)
                if overlap:
                    # Score based on tag specificity:
                    # Crops with fewer region tags are more specific → higher score
                    specificity = 1.0 / max(1, len(crop_tags))
                    tag_match = len(overlap) / len(expected_regions)
                    score += 0.5 + 0.3 * tag_match + 0.2 * specificity
                else:
                    score += 0.1
            else:
                score += 0.4
            n_checks += 1

        # Check 2: Latitude-based filtering (tighter bands)
        if lat is not None:
            abs_lat = abs(lat)

            if abs_lat < 15:
                # Deep tropical
                if "tropical" in crop_tags or "subsaharan" in crop_tags:
                    score += 1.0
                elif "subtropical" in crop_tags:
                    score += 0.5
                else:
                    score += 0.1
            elif abs_lat < 25:
                # Subtropical / arid
                if "subtropical" in crop_tags:
                    score += 1.0
                elif "tropical" in crop_tags:
                    score += 0.7
                elif "mena" in crop_tags:
                    score += 0.8
                else:
                    score += 0.2
            elif abs_lat < 37:
                # Mediterranean / MENA
                if "mediterranean" in crop_tags:
                    # Specificity bonus: fewer total tags = more specialized
                    score += 0.7 + 0.3 * (1.0 / max(1, len(crop_tags)))
                elif "mena" in crop_tags:
                    score += 0.7
                elif "subtropical" in crop_tags:
                    score += 0.5
                elif "temperate" in crop_tags:
                    score += 0.4
                else:
                    score += 0.1
            elif abs_lat < 50:
                # Temperate
                if "temperate" in crop_tags:
                    score += 0.8 + 0.2 * (1.0 / max(1, len(crop_tags)))
                elif "mediterranean" in crop_tags:
                    score += 0.6
                else:
                    score += 0.15
            else:
                # Cold
                if "temperate" in crop_tags:
                    score += 0.7
                else:
                    score += 0.05
            n_checks += 1

        # Check 3: Longitude discrimination (Africa vs Middle East vs Europe)
        if lat is not None and lng is not None:
            if 25 < abs(lat) < 40:
                # MENA-Mediterranean band: longitude matters
                if -10 < lng < 15:
                    # Western Mediterranean (Maghreb, Iberia)
                    if "mediterranean" in crop_tags:
                        score += 0.9
                    elif "mena" in crop_tags:
                        score += 0.7
                    else:
                        score += 0.3
                elif 15 <= lng < 45:
                    # Eastern Mediterranean / Mashreq
                    if "mena" in crop_tags:
                        score += 0.9
                    elif "mediterranean" in crop_tags:
                        score += 0.7
                    else:
                        score += 0.3
                elif lng >= 45:
                    # Gulf / Iran
                    if "mena" in crop_tags:
                        score += 0.8
                    elif "subtropical" in crop_tags:
                        score += 0.6
                    else:
                        score += 0.2
                else:
                    score += 0.5
                n_checks += 1

        # Check 4: Elevation constraint
        if elevation_m is not None:
            if elevation_m > 2000 and crop.architecture == "tropical_tree":
                score += 0.1
            elif elevation_m > 1500 and crop.optimal_temp_min > 20:
                score += 0.2
            else:
                score += 0.7
            n_checks += 1

        return score / max(1, n_checks)

    # =========================================================================
    # Module 5: Thermal Response Matcher (w=0.10)
    # =========================================================================

    def _score_thermal(
        self,
        crop: CropSpec,
        mean_temp_c: Optional[float],
        gdd_accumulated: Optional[float],
        gdd_accumulation_days: Optional[int],
    ) -> float:
        """
        Score thermal compatibility.

        Compares observed temperature and GDD accumulation rate against the
        crop's base temperature and optimal range from the registry.
        """
        if mean_temp_c is None and gdd_accumulated is None:
            return 0.5  # No thermal data → neutral

        score = 0.0
        n_checks = 0

        # Check 1: Mean temperature within optimal range
        if mean_temp_c is not None:
            t_min = crop.optimal_temp_min
            t_max = crop.optimal_temp_max

            if t_min <= mean_temp_c <= t_max:
                score += 1.0
            else:
                dist = min(abs(mean_temp_c - t_min), abs(mean_temp_c - t_max))
                score += max(0.0, 1.0 - dist * 0.1)
            n_checks += 1

        # Check 2: Temperature above base temp
        if mean_temp_c is not None:
            if mean_temp_c > crop.gdd_base_temp:
                # Good — crop can accumulate GDD here
                surplus = mean_temp_c - crop.gdd_base_temp
                score += min(1.0, surplus / 15.0)
            else:
                # Too cold for this crop's base temp
                score += 0.1
            n_checks += 1

        # Check 3: GDD accumulation rate
        if gdd_accumulated is not None and gdd_accumulation_days is not None and gdd_accumulation_days > 0:
            daily_gdd = gdd_accumulated / gdd_accumulation_days
            # Expected daily GDD for this crop's base temp
            # In its optimal zone: ~(optimal_mean - base_temp)
            optimal_mean = (crop.optimal_temp_min + crop.optimal_temp_max) / 2
            expected_daily = max(1, optimal_mean - crop.gdd_base_temp)
            ratio = daily_gdd / expected_daily
            deviation = abs(1.0 - ratio)
            if deviation < 0.30:
                score += 1.0
            elif deviation < 0.50:
                score += 0.6
            else:
                score += 0.2
            n_checks += 1

        return score / max(1, n_checks)

    # =========================================================================
    # Module 6: Plot Context Scorer (w=0.20)
    # =========================================================================

    # Soil type affinities — which crop architectures prefer which soils
    _SOIL_CROP_AFFINITY = {
        "CLAY":      {"rice": 0.9, "cereal": 0.7, "cotton": 0.6, "legume": 0.5, "maize": 0.5, "vegetable": 0.4, "perennial": 0.5, "tropical_tree": 0.3},
        "CLAY_LOAM": {"cereal": 0.9, "maize": 0.8, "cotton": 0.7, "legume": 0.7, "rice": 0.6, "vegetable": 0.7, "perennial": 0.7, "tropical_tree": 0.5},
        "LOAM":      {"cereal": 0.9, "maize": 0.9, "vegetable": 0.9, "legume": 0.8, "cotton": 0.7, "perennial": 0.8, "tropical_tree": 0.7, "rice": 0.4},
        "SANDY_LOAM":{"vegetable": 0.9, "legume": 0.8, "maize": 0.7, "cereal": 0.6, "perennial": 0.7, "cotton": 0.5, "tropical_tree": 0.6, "rice": 0.2},
        "SANDY":     {"vegetable": 0.7, "legume": 0.6, "perennial": 0.5, "tropical_tree": 0.6, "maize": 0.4, "cereal": 0.3, "cotton": 0.3, "rice": 0.1},
        "SILT_LOAM": {"cereal": 0.9, "maize": 0.8, "vegetable": 0.8, "legume": 0.7, "cotton": 0.6, "perennial": 0.7, "tropical_tree": 0.5, "rice": 0.5},
        "SILT":      {"rice": 0.7, "cereal": 0.7, "vegetable": 0.6, "maize": 0.6, "legume": 0.5, "cotton": 0.5, "perennial": 0.6, "tropical_tree": 0.4},
    }

    # Irrigation type affinities
    _IRRIGATION_CROP_AFFINITY = {
        "DRIP":      {"vegetable": 0.9, "perennial": 0.9, "tropical_tree": 0.8, "cotton": 0.6, "legume": 0.5, "maize": 0.5, "cereal": 0.3, "rice": 0.1},
        "SPRINKLER": {"cereal": 0.8, "maize": 0.8, "legume": 0.7, "vegetable": 0.7, "cotton": 0.6, "perennial": 0.5, "tropical_tree": 0.3, "rice": 0.2},
        "FLOOD":     {"rice": 1.0, "cereal": 0.6, "maize": 0.5, "legume": 0.4, "vegetable": 0.3, "cotton": 0.3, "perennial": 0.2, "tropical_tree": 0.1},
        "PIVOT":     {"cereal": 0.9, "maize": 0.9, "cotton": 0.7, "legume": 0.7, "vegetable": 0.5, "perennial": 0.3, "tropical_tree": 0.2, "rice": 0.3},
        "RAINFED":   {"cereal": 0.9, "legume": 0.8, "maize": 0.6, "perennial": 0.7, "tropical_tree": 0.6, "cotton": 0.5, "vegetable": 0.3, "rice": 0.3},
        "NONE":      {"cereal": 0.8, "legume": 0.7, "perennial": 0.6, "tropical_tree": 0.5, "maize": 0.4, "cotton": 0.3, "vegetable": 0.2, "rice": 0.1},
    }

    # Area range affinities (hectares)
    _AREA_CROP_AFFINITY = {
        # small plots (<1 ha): likely vegetables/garden crops
        "tiny":      {"vegetable": 0.9, "legume": 0.7, "perennial": 0.6, "cereal": 0.3, "maize": 0.4, "cotton": 0.2, "tropical_tree": 0.5, "rice": 0.3},
        # small-medium (1-5 ha): mixed
        "small":     {"vegetable": 0.7, "legume": 0.8, "cereal": 0.7, "maize": 0.7, "perennial": 0.7, "cotton": 0.5, "tropical_tree": 0.6, "rice": 0.6},
        # medium (5-20 ha): field crops
        "medium":    {"cereal": 0.9, "maize": 0.9, "cotton": 0.8, "legume": 0.7, "rice": 0.7, "vegetable": 0.4, "perennial": 0.6, "tropical_tree": 0.5},
        # large (>20 ha): industrial field crops
        "large":     {"cereal": 1.0, "maize": 0.9, "cotton": 0.9, "rice": 0.8, "legume": 0.6, "perennial": 0.5, "vegetable": 0.2, "tropical_tree": 0.4},
    }

    def _score_plot_context(
        self,
        crop: CropSpec,
        area_ha: Optional[float],
        soil_type: Optional[str],
        irrigation_type: Optional[str],
        previous_crops: Optional[List[Dict]],
    ) -> float:
        """
        Score based on plot-specific context: area, soil, irrigation, crop history.

        This module is critical when satellite data is unavailable (e.g., Sentinel
        Hub 403) — it provides the primary differentiation signal between plots
        on the same farm.
        """
        score = 0.0
        n_checks = 0

        # Check 1: Area-based filtering
        if area_ha is not None and area_ha > 0:
            if area_ha < 1:
                size_class = "tiny"
            elif area_ha < 5:
                size_class = "small"
            elif area_ha < 20:
                size_class = "medium"
            else:
                size_class = "large"

            affinity = self._AREA_CROP_AFFINITY.get(size_class, {})
            score += affinity.get(crop.architecture, 0.5)
            n_checks += 1

        # Check 2: Soil type compatibility
        if soil_type:
            soil_key = soil_type.upper().replace(" ", "_")
            affinity = self._SOIL_CROP_AFFINITY.get(soil_key, {})
            if affinity:
                score += affinity.get(crop.architecture, 0.5)
                n_checks += 1

        # Check 3: Irrigation type compatibility
        if irrigation_type:
            irrig_key = irrigation_type.upper().replace(" ", "_")
            affinity = self._IRRIGATION_CROP_AFFINITY.get(irrig_key, {})
            if affinity:
                score += affinity.get(crop.architecture, 0.5)
                n_checks += 1

        # Check 4: Previous crops (crop rotation patterns)
        if previous_crops and len(previous_crops) > 0:
            # Extract architecture of last crop grown
            last_crop_code = previous_crops[0].get("code", "").lower().replace(" ", "_")
            last_crop_spec = CROP_REGISTRY.get(last_crop_code)

            if last_crop_spec:
                last_arch = last_crop_spec.architecture
                # Rotation logic: farmers often rotate crop architectures
                # Same architecture → less likely (monoculture penalty)
                if crop.architecture == last_arch:
                    score += 0.3  # Monoculture possible but less likely
                # Cereal → legume or legume → cereal (classic rotation)
                elif (last_arch in ("cereal", "maize") and crop.architecture == "legume") or \
                     (last_arch == "legume" and crop.architecture in ("cereal", "maize")):
                    score += 1.0  # Strong rotation signal
                # Perennial/tree crops tend to persist
                elif crop.architecture in ("perennial", "tropical_tree") and last_arch == crop.architecture:
                    score += 0.9  # Perennials keep going
                else:
                    score += 0.6  # Neutral rotation
            else:
                score += 0.5  # Unknown last crop
            n_checks += 1

        # If no plot context available, return neutral
        if n_checks == 0:
            return 0.5

        return score / n_checks

    # =========================================================================
    # Module 7: Crop-Specific Prior Discriminator (w=0.20)
    # =========================================================================

    def _score_crop_prior(
        self,
        crop: CropSpec,
        lat: Optional[float],
        mean_temp_c: Optional[float],
        irrigation_type: Optional[str],
        area_ha: Optional[float],
    ) -> float:
        """
        Score each crop using its INDIVIDUAL registry fields that differ
        between crops in the same architecture class.

        This is the KEY discriminator that breaks ties between e.g.,
        Wheat (growing_days=150, gdd_base=0°C) vs Barley (growing_days=130, gdd_base=0°C)
        vs Chickpea (growing_days=120, gdd_base=5°C).

        Uses:
          - growing_days: longer seasons penalized in hot climates
          - gdd_base_temp: cold-tolerant vs warm-season discrimination
          - optimal_temp_min/max: climate fit
          - water_needs: irrigation compatibility
          - kc_mid: water demand level
          - max_root_depth_cm: soil depth compatibility
          - harvest_index: horticultural vs field crop signal
          - family: botanical family as a weak prior
        """
        score = 0.0
        n_checks = 0

        # ── 1. Growing season length vs latitude ──
        # Short-season crops suit northern latitudes (short summers)
        # and double-cropping regions. Long-season suit tropics/perennials.
        if lat is not None:
            abs_lat = abs(lat)
            gd = crop.growing_days

            if abs_lat >= 40:
                # High latitude: short growing season preferred
                if gd <= 100:
                    score += 1.0
                elif gd <= 140:
                    score += 0.8
                elif gd <= 200:
                    score += 0.5
                else:
                    score += 0.2
            elif abs_lat >= 30:
                # Mediterranean: moderate season
                if 90 <= gd <= 200:
                    score += 0.9
                elif gd <= 280:
                    score += 0.6
                elif gd >= 365:
                    score += 0.7  # Perennials ok
                else:
                    score += 0.4
            elif abs_lat >= 15:
                # Subtropical: flexible
                if 60 <= gd <= 250:
                    score += 0.8
                elif gd >= 300:
                    score += 0.9  # Tropical long-season ok
                else:
                    score += 0.5
            else:
                # Tropical: long season preferred
                if gd >= 200:
                    score += 1.0
                elif gd >= 100:
                    score += 0.6
                else:
                    score += 0.3
            n_checks += 1

        # ── 2. GDD base temperature as climate indicator ──
        # Warm-season crops (gdd_base ≥ 10°C) need warm climates.
        # Cool-season crops (gdd_base ≤ 5°C) tolerate cold.
        if lat is not None:
            abs_lat = abs(lat)
            base_t = crop.gdd_base_temp

            if abs_lat >= 40:
                # Cold region: cool-season crops preferred
                if base_t <= 5:
                    score += 1.0
                elif base_t <= 10:
                    score += 0.6
                else:
                    score += 0.2
            elif abs_lat >= 30:
                # Mediterranean: both ok, slight cool-season preference
                if base_t <= 10:
                    score += 0.9
                elif base_t <= 15:
                    score += 0.6
                else:
                    score += 0.3
            else:
                # Tropical/subtropical: warm-season preferred
                if base_t >= 10:
                    score += 1.0
                elif base_t >= 5:
                    score += 0.6
                else:
                    score += 0.3
            n_checks += 1

        # ── 3. Optimal temperature range vs observed temp ──
        if mean_temp_c is not None:
            opt_min = crop.optimal_temp_min
            opt_max = crop.optimal_temp_max
            mid_opt = (opt_min + opt_max) / 2.0

            if opt_min <= mean_temp_c <= opt_max:
                # Perfect fit
                closeness = 1.0 - abs(mean_temp_c - mid_opt) / max(1, (opt_max - opt_min) / 2)
                score += 0.7 + 0.3 * max(0, closeness)
            elif mean_temp_c < opt_min:
                diff = opt_min - mean_temp_c
                score += max(0.05, 1.0 - diff * 0.1)
            else:
                diff = mean_temp_c - opt_max
                score += max(0.05, 1.0 - diff * 0.1)
            n_checks += 1

        # ── 4. Water needs vs irrigation type ──
        wn = crop.water_needs  # "low", "medium", "high"
        if irrigation_type:
            irrig = irrigation_type.upper()
            if irrig in ("DRIP", "PIVOT", "SPRINKLER"):
                # Irrigated: high-water crops feasible
                if wn == "high":
                    score += 0.9
                elif wn == "medium":
                    score += 0.7
                else:
                    score += 0.4
            elif irrig in ("RAINFED", "NONE", ""):
                # Rainfed: low-water crops preferred
                if wn == "low":
                    score += 1.0
                elif wn == "medium":
                    score += 0.6
                else:
                    score += 0.2
            elif irrig == "FLOOD":
                # Flood: rice or high-water
                if crop.architecture == "rice":
                    score += 1.0
                elif wn == "high":
                    score += 0.6
                else:
                    score += 0.2
            else:
                score += 0.5
            n_checks += 1

        # ── 5. Kc_mid as intensity discriminator ──
        # Higher kc_mid = more intensive crop = more water/input demanding
        kc = crop.kc_mid
        if area_ha is not None:
            if area_ha < 2:
                # Small plots: intensive crops (high kc) typical
                if kc >= 1.0:
                    score += 0.9
                else:
                    score += 0.5
            elif area_ha > 20:
                # Large plots: extensive crops (lower kc) typical
                if kc <= 1.10:
                    score += 0.8
                else:
                    score += 0.4
            else:
                score += 0.6
            n_checks += 1

        # ── 6. Harvest index as crop type signal ──
        # High HI (>0.60): tuber/leaf crops, low HI (<0.35): tree/fiber crops
        hi = crop.harvest_index
        if area_ha is not None:
            if area_ha < 1:
                # Tiny plots: likely high-HI vegetable/garden crops
                if hi >= 0.50:
                    score += 0.9
                else:
                    score += 0.3
            else:
                # Larger: field crops with moderate HI
                if 0.30 <= hi <= 0.50:
                    score += 0.8
                else:
                    score += 0.5
            n_checks += 1

        # ── 7. Growing days uniqueness hash ──
        return score / max(1, n_checks)



crop_id_engine = CropIdentificationEngine()


# =============================================================================
# Convenience Entry Point
# =============================================================================

def identify_crop(**kwargs) -> CropIdentificationResult:
    """Convenience wrapper around the singleton engine."""
    return crop_id_engine.identify(**kwargs)
