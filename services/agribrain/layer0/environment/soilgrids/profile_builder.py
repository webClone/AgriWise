"""
SoilGrids Profile Builder.

Computes derived hydraulic properties from a SoilGridsProfile:
- AWC proxy (volumetric and mm, with coarse-fragment correction)
- Texture class (USDA triangle)
- Root-zone AWC aggregates
- Risk/capacity indicators
"""

from __future__ import annotations

from typing import Dict, Optional

from layer0.environment.soilgrids.schemas import (
    SOILGRIDS_DEPTH_LABELS,
    SOILGRIDS_DEPTH_THICKNESS_MM,
    SoilGridsDerivedHydraulics,
    SoilGridsProfile,
)


def classify_texture_usda(clay_pct: float, silt_pct: float, sand_pct: float) -> str:
    """Classify soil texture using simplified USDA texture triangle."""
    if clay_pct >= 40:
        if silt_pct >= 40:
            return "silty_clay"
        if sand_pct >= 45:
            return "sandy_clay"
        return "clay"
    if clay_pct >= 27:
        if sand_pct >= 20 and sand_pct <= 45:
            return "clay_loam"
        if silt_pct >= 40:
            return "silty_clay_loam"
        return "sandy_clay_loam"
    if silt_pct >= 50:
        if clay_pct >= 12:
            return "silt_loam"
        return "silt"
    if sand_pct >= 85:
        return "sand"
    if sand_pct >= 70:
        return "loamy_sand"
    if clay_pct >= 7 and clay_pct < 20 and sand_pct > 52:
        return "sandy_loam"
    return "loam"


def build_derived_hydraulics(profile: SoilGridsProfile) -> SoilGridsDerivedHydraulics:
    """Compute derived hydraulic properties from SoilGrids profile."""
    awc_volumetric: Dict[str, float] = {}
    awc_mm: Dict[str, float] = {}

    # Depth ranges for root-zone aggregation (cumulative bottom in cm)
    depth_bottom_cm = {
        "0-5cm": 5, "5-15cm": 15, "15-30cm": 30,
        "30-60cm": 60, "60-100cm": 100, "100-200cm": 200,
    }

    rz_awc_30 = 0.0
    rz_awc_60 = 0.0
    rz_awc_100 = 0.0
    coarse_corrected = False

    # Representative topsoil values for texture/risk classification
    topsoil_clay: Optional[float] = None
    topsoil_silt: Optional[float] = None
    topsoil_sand: Optional[float] = None
    topsoil_bdod: Optional[float] = None
    topsoil_phh2o: Optional[float] = None
    topsoil_cec: Optional[float] = None
    topsoil_soc: Optional[float] = None

    for depth_label in SOILGRIDS_DEPTH_LABELS:
        layer = profile.depth_layers.get(depth_label)
        if layer is None:
            continue

        wv003 = layer.get("wv003")
        wv1500 = layer.get("wv1500")
        cfvo = layer.get("cfvo")
        thickness_mm = SOILGRIDS_DEPTH_THICKNESS_MM.get(depth_label, 0)

        # AWC volumetric proxy
        if wv003 is not None and wv1500 is not None:
            awc_vol = max(0.0, wv003 - wv1500)
            awc_volumetric[depth_label] = round(awc_vol, 2)

            # AWC in mm with coarse-fragment correction
            fine_earth_fraction = 1.0
            if cfvo is not None and cfvo > 0:
                fine_earth_fraction = max(0.0, 1.0 - cfvo / 100.0)
                coarse_corrected = True

            awc_mm_val = (awc_vol / 100.0) * thickness_mm * fine_earth_fraction
            awc_mm[depth_label] = round(awc_mm_val, 2)

            # Root-zone aggregation
            bottom = depth_bottom_cm.get(depth_label, 0)
            if bottom <= 30:
                rz_awc_30 += awc_mm_val
            if bottom <= 60:
                rz_awc_60 += awc_mm_val
            if bottom <= 100:
                rz_awc_100 += awc_mm_val

        # Capture topsoil values (use 0-5cm, fallback to 5-15cm)
        if topsoil_clay is None:
            topsoil_clay = layer.get("clay")
            topsoil_silt = layer.get("silt")
            topsoil_sand = layer.get("sand")
            topsoil_bdod = layer.get("bdod")
            topsoil_phh2o = layer.get("phh2o")
            topsoil_cec = layer.get("cec")
            topsoil_soc = layer.get("soc")

    # Texture class
    texture_class = ""
    if topsoil_clay is not None and topsoil_silt is not None and topsoil_sand is not None:
        texture_class = classify_texture_usda(topsoil_clay, topsoil_silt, topsoil_sand)

    # Risk/capacity indicators
    drainage_risk = _classify_drainage(topsoil_sand, topsoil_clay)
    whc_class = _classify_whc(rz_awc_60)
    infiltration_risk = _classify_infiltration(topsoil_sand, topsoil_clay)
    compaction_risk = _classify_compaction(topsoil_bdod, topsoil_clay)
    nutrient_buffering = _classify_nutrient_buffering(topsoil_cec, topsoil_soc)
    lime_ph_risk = _classify_ph_risk(topsoil_phh2o)

    return SoilGridsDerivedHydraulics(
        awc_volumetric_proxy_by_depth=awc_volumetric,
        awc_mm_by_layer=awc_mm,
        coarse_fragment_correction_applied=coarse_corrected,
        root_zone_awc_mm_0_30=round(rz_awc_30, 2) if awc_mm else None,
        root_zone_awc_mm_0_60=round(rz_awc_60, 2) if awc_mm else None,
        root_zone_awc_mm_0_100=round(rz_awc_100, 2) if awc_mm else None,
        texture_class=texture_class,
        drainage_risk=drainage_risk,
        water_holding_capacity_class=whc_class,
        infiltration_risk_class=infiltration_risk,
        compaction_risk_proxy=compaction_risk,
        nutrient_buffering_proxy=nutrient_buffering,
        lime_ph_risk_proxy=lime_ph_risk,
    )


def _classify_drainage(sand: Optional[float], clay: Optional[float]) -> str:
    if sand is None or clay is None:
        return "unknown"
    if sand > 70:
        return "high"
    if clay > 40:
        return "low"
    return "medium"


def _classify_whc(awc_60_mm: float) -> str:
    if awc_60_mm <= 0:
        return "unknown"
    if awc_60_mm < 40:
        return "low"
    if awc_60_mm < 80:
        return "medium"
    return "high"


def _classify_infiltration(sand: Optional[float], clay: Optional[float]) -> str:
    if sand is None or clay is None:
        return "unknown"
    if sand > 70:
        return "high"
    if clay > 50:
        return "low"
    return "medium"


def _classify_compaction(bdod: Optional[float], clay: Optional[float]) -> str:
    if bdod is None:
        return "unknown"
    if bdod > 1.6:
        return "high"
    if bdod > 1.4 and clay is not None and clay > 30:
        return "high"
    if bdod < 1.2:
        return "low"
    return "medium"


def _classify_nutrient_buffering(cec: Optional[float], soc: Optional[float]) -> str:
    if cec is None:
        return "unknown"
    if cec > 25:
        return "high"
    if cec < 10:
        return "low"
    return "medium"


def _classify_ph_risk(ph: Optional[float]) -> str:
    if ph is None:
        return "unknown"
    if ph < 5.5:
        return "acidic"
    if ph > 7.5:
        return "alkaline"
    return "neutral"
