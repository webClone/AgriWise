"""
Layer 4.3: Nutrient Observation & Proxy Engine — Multi-index spectral + SAR tillage.

Converts remote sensing signals into nutrient evidence with confounder control.
Integrates user soil analysis as direct nutrient measurements.

Spectral science:
  - NDVI -> biomass/vigor (saturates at high LAI)
  - NDRE (Red Edge) -> chlorophyll/N status (penetrates dense canopy)
  - REIP (Red Edge Inflection Point) -> N stress indicator
  - NDMI -> moisture confound separation

SAR tillage detection:
  - Sentinel-1 VV/VH backscatter change -> soil roughness change
  - Conventional tillage: VV +2 to +6 dB, VH +1 to +4 dB
  - No-till: VV < +2 dB, minimal VH change
  - Temporal decorrelation of InSAR coherence

References:
  - Clevers & Gitelson (2013): NDRE for chlorophyll estimation
  - Satalino et al. (2014): SAR-based tillage detection
  - Nawar et al. (2017): SOC estimation from radar
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from layer4_nutrients.schema import (
    TillageDetection, TillageClass, SOCDynamics, Nutrient, Driver,
)


# ============================================================================
# Stage-aware spectral baselines per crop
# ============================================================================

# NDVI baselines: (mean, stddev) for healthy crop
NDVI_BASELINES = {
    "corn": {
        "initial": (0.20, 0.05), "vegetative": (0.72, 0.08),
        "reproductive": (0.85, 0.05), "maturity": (0.60, 0.12), "senescence": (0.30, 0.10),
    },
    "wheat": {
        "initial": (0.25, 0.05), "vegetative": (0.70, 0.08),
        "reproductive": (0.80, 0.05), "maturity": (0.50, 0.12), "senescence": (0.25, 0.08),
    },
    "_default": {
        "initial": (0.22, 0.06), "vegetative": (0.70, 0.10),
        "reproductive": (0.82, 0.06), "maturity": (0.55, 0.12), "senescence": (0.28, 0.10),
    },
}

# NDRE baselines: (mean, stddev) — more sensitive to chlorophyll in dense canopies
NDRE_BASELINES = {
    "_default": {
        "initial": (0.12, 0.04), "vegetative": (0.40, 0.06),
        "reproductive": (0.50, 0.05), "maturity": (0.30, 0.08), "senescence": (0.15, 0.06),
    },
}


# ============================================================================
# SAR Tillage Detection
# ============================================================================

# Tillage classification thresholds (dB change in VV backscatter)
TILLAGE_THRESHOLDS = {
    TillageClass.CONVENTIONAL: 4.0,  # > 4 dB VV change
    TillageClass.REDUCED: 2.0,       # 2-4 dB
    TillageClass.NO_TILL: 0.0,       # < 2 dB
}

# N mineralization multiplier by tillage class
# Science: Conventional tillage exposes organic matter to oxidation,
# accelerating N mineralization. No-till preserves SOC.
TILLAGE_MINERALIZATION_FACTOR = {
    TillageClass.CONVENTIONAL: 1.30,  # +30% mineralization
    TillageClass.REDUCED: 1.10,       # +10%
    TillageClass.NO_TILL: 0.90,       # -10% (SOC preserved)
    TillageClass.UNKNOWN: 1.00,
}


def detect_tillage(
    sar_vv_pre: Optional[float],
    sar_vv_post: Optional[float],
    sar_vh_pre: Optional[float] = None,
    sar_vh_post: Optional[float] = None,
    coherence_drop: float = 0.0,
    detection_date: Optional[str] = None,
    days_since: int = -1,
) -> TillageDetection:
    """Detect tillage events from SAR backscatter changes.

    Args:
        sar_vv_pre: VV backscatter (dB) before suspected event
        sar_vv_post: VV backscatter (dB) after suspected event
        sar_vh_pre: VH backscatter (dB) before
        sar_vh_post: VH backscatter (dB) after
        coherence_drop: InSAR temporal coherence drop [0-1]
        detection_date: ISO date string
        days_since: Days since detection
    """
    if sar_vv_pre is None or sar_vv_post is None:
        return TillageDetection(detected=False, tillage_class=TillageClass.UNKNOWN)

    vv_change = abs(sar_vv_post - sar_vv_pre)
    vh_change = abs(sar_vh_post - sar_vh_pre) if sar_vh_pre is not None and sar_vh_post is not None else 0.0

    # Classify
    if vv_change >= TILLAGE_THRESHOLDS[TillageClass.CONVENTIONAL]:
        tillage_class = TillageClass.CONVENTIONAL
    elif vv_change >= TILLAGE_THRESHOLDS[TillageClass.REDUCED]:
        tillage_class = TillageClass.REDUCED
    else:
        tillage_class = TillageClass.NO_TILL

    detected = vv_change >= TILLAGE_THRESHOLDS[TillageClass.REDUCED]

    # Confidence from multiple indicators
    confidence = min(1.0, vv_change / 6.0)  # Normalize by max expected change
    if vh_change > 1.0:
        confidence = min(1.0, confidence + 0.15)
    if coherence_drop > 0.3:
        confidence = min(1.0, confidence + 0.20)

    mineralization_mult = TILLAGE_MINERALIZATION_FACTOR[tillage_class]

    return TillageDetection(
        detected=detected,
        tillage_class=tillage_class,
        confidence=round(confidence, 3),
        vv_change_db=round(vv_change, 2),
        vh_change_db=round(vh_change, 2),
        coherence_loss=round(coherence_drop, 3),
        detection_date=detection_date,
        days_since_detection=days_since,
        mineralization_multiplier=mineralization_mult,
    )


# ============================================================================
# SOC Dynamics
# ============================================================================

def estimate_soc_mineralization(
    soc_pct: Optional[float],
    soc_source: str,
    tillage: TillageDetection,
    clay_pct: float = 22.0,
    temperature_c: float = 20.0,
) -> SOCDynamics:
    """Estimate N mineralization from SOC with tillage adjustment.

    Science:
      - Base mineralization rate: 2-4% of total soil N per year
      - Soil N ≈ SOC/10 (C:N ratio ≈ 10:1)
      - Total soil N in top 30cm ≈ SOC_pct * 300 * bulk_density / 10
      - Simplified: mineralization ≈ SOC_pct * 15 kg N/ha/yr (base)
      - Temperature Q10 factor: rate doubles per 10°C above 10°C
      - Clay protection: high clay slows decomposition

    References:
      - Stanford & Smith (1972): N mineralization potential
      - van Veen & Paul (1981): SOC decomposition model
    """
    if soc_pct is None:
        soc_pct = 1.5  # Global median
        soc_source = "estimated"

    # Base mineralization: SOC_pct * 15 kg N/ha/yr (empirical)
    base_rate = soc_pct * 15.0

    # Temperature adjustment (Q10 = 2.0)
    q10 = 2.0
    temp_factor = q10 ** ((temperature_c - 20.0) / 10.0)
    base_rate *= temp_factor

    # Clay protection factor (high clay slows decomposition)
    clay_factor = 1.0 - 0.003 * max(0, clay_pct - 20)
    clay_factor = max(0.7, clay_factor)
    base_rate *= clay_factor

    # Tillage adjustment
    tillage_adjusted = base_rate * tillage.mineralization_multiplier

    # Carbon sequestration potential
    if soc_pct > 3.0:
        seq_potential = "low"  # Already high SOC
    elif soc_pct > 1.5:
        seq_potential = "moderate"
    else:
        seq_potential = "high"  # Low SOC → high potential with no-till

    return SOCDynamics(
        soc_pct=round(soc_pct, 2),
        soc_source=soc_source,
        mineralization_rate_kg_ha_yr=round(base_rate, 2),
        tillage_adjusted_mineralization=round(tillage_adjusted, 2),
        carbon_sequestration_potential=seq_potential,
        tillage_history=tillage,
    )


# ============================================================================
# Spectral Proxy Engine
# ============================================================================

class NutrientObservationProxyEngine:
    """Extracts nutrient evidence from spectral indices + SAR + user soil data."""

    def extract_features(
        self,
        ndvi: float,
        stage: str,
        crop_type: str = "corn",
        ndre: Optional[float] = None,
        growth_velocity: float = 0.0,
        spatial_heterogeneity: bool = False,
        user_soil_n_ppm: Optional[float] = None,
        user_soil_p_ppm: Optional[float] = None,
        user_soil_k_ppm: Optional[float] = None,
        user_soil_ph: Optional[float] = None,
        sar_vv_change: Optional[float] = None,
        sar_vh_change: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Compute nutrient evidence features.

        Returns dict of features for the inference engine.
        """
        crop_lower = crop_type.lower()
        stage_lower = stage.lower()

        # 1. NDVI Z-Score (deviation from healthy baseline)
        ndvi_baselines = NDVI_BASELINES.get(crop_lower, NDVI_BASELINES["_default"])
        ndvi_mean, ndvi_std = ndvi_baselines.get(stage_lower, (0.5, 0.15))
        ndvi_z = (ndvi - ndvi_mean) / max(ndvi_std, 0.01)

        # 2. NDRE Z-Score (chlorophyll proxy, more sensitive in dense canopies)
        ndre_z = 0.0
        if ndre is not None:
            ndre_baselines = NDRE_BASELINES["_default"]
            ndre_mean, ndre_std = ndre_baselines.get(stage_lower, (0.30, 0.08))
            ndre_z = (ndre - ndre_mean) / max(ndre_std, 0.01)

        # 3. Growth adequacy (slope check)
        growth_adequacy = 1.0
        if stage_lower in ("vegetative", "initial"):
            expected_growth = 0.015 if stage_lower == "vegetative" else 0.005
            if expected_growth > 0:
                growth_adequacy = max(0, min(1.5, growth_velocity / expected_growth))

        # 4. User soil analysis (direct measurements → strongest evidence)
        soil_n_status = None
        soil_p_status = None
        soil_k_status = None

        if user_soil_n_ppm is not None:
            # N (NO3-N ppm): <10=deficient, 10-25=adequate, >25=high
            if user_soil_n_ppm < 10:
                soil_n_status = "deficient"
            elif user_soil_n_ppm < 25:
                soil_n_status = "adequate"
            else:
                soil_n_status = "high"

        if user_soil_p_ppm is not None:
            # Olsen P (ppm): <10=deficient, 10-25=adequate, >25=high
            if user_soil_p_ppm < 10:
                soil_p_status = "deficient"
            elif user_soil_p_ppm < 25:
                soil_p_status = "adequate"
            else:
                soil_p_status = "high"

        if user_soil_k_ppm is not None:
            # K (ppm): <100=deficient, 100-200=adequate, >200=high
            if user_soil_k_ppm < 100:
                soil_k_status = "deficient"
            elif user_soil_k_ppm < 200:
                soil_k_status = "adequate"
            else:
                soil_k_status = "high"

        # 5. pH-dependent P availability
        ph_p_availability = 1.0
        if user_soil_ph is not None:
            # P is most available at pH 6.0-7.0
            if user_soil_ph < 5.5:
                ph_p_availability = 0.5  # Al/Fe fixation
            elif user_soil_ph > 7.5:
                ph_p_availability = 0.6  # Ca fixation
            elif 6.0 <= user_soil_ph <= 7.0:
                ph_p_availability = 1.0

        return {
            "ndvi_z": round(ndvi_z, 3),
            "ndre_z": round(ndre_z, 3),
            "growth_adequacy": round(growth_adequacy, 3),
            "heterogeneity_flag": spatial_heterogeneity,
            "current_ndvi": ndvi,
            "current_stage": stage_lower,
            # User soil analysis
            "soil_n_status": soil_n_status,
            "soil_p_status": soil_p_status,
            "soil_k_status": soil_k_status,
            "soil_n_ppm": user_soil_n_ppm,
            "soil_p_ppm": user_soil_p_ppm,
            "soil_k_ppm": user_soil_k_ppm,
            "ph_p_availability": ph_p_availability,
            "user_soil_ph": user_soil_ph,
        }
