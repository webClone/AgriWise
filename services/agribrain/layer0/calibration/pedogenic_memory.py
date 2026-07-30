"""
Module 1: Pedogenic Memory Engine
Derives soil intelligence from SoilGrids data using Saxton-Rawls pedotransfer functions.

Data Integrity Notes:
  - Checks `is_generic_fallback` flag from SoilGrids to detect generic loam profiles.
  - Tracks per-field default usage so the UI can warn when specific properties are missing.
"""
import math
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("agribrain.pedogenic")

# USDA Soil Texture Triangle thresholds
TEXTURE_CLASSES = [
    ("Clay", lambda c,si,sa: c >= 40),
    ("Silty Clay", lambda c,si,sa: c >= 40 and si >= 40),
    ("Sandy Clay", lambda c,si,sa: c >= 35 and sa >= 45),
    ("Silty Clay Loam", lambda c,si,sa: 27 <= c < 40 and si >= 40),
    ("Clay Loam", lambda c,si,sa: 27 <= c < 40 and 20 <= sa < 45),
    ("Sandy Clay Loam", lambda c,si,sa: 20 <= c < 35 and sa >= 45),
    ("Silt Loam", lambda c,si,sa: c < 27 and si >= 50),
    ("Silt", lambda c,si,sa: c < 12 and si >= 80),
    ("Loam", lambda c,si,sa: 7 <= c < 27 and 28 <= si < 50 and sa <= 52),
    ("Sandy Loam", lambda c,si,sa: c < 20 and si < 50 and sa >= 43),
    ("Loamy Sand", lambda c,si,sa: c < 15 and si < 30 and sa >= 70),
    ("Sand", lambda c,si,sa: c < 10 and si < 15 and sa >= 85),
]

def classify_texture(clay: float, silt: float, sand: float) -> str:
    for name, test in TEXTURE_CLASSES:
        if test(clay, silt, sand):
            return name
    return "Loam"

def saxton_rawls_pawc(clay: float, sand: float, soc: float) -> float:
    """
    Saxton & Rawls (2006) pedotransfer: Plant-Available Water Capacity (mm/m).
    Inputs in fractions (0-1 scale for clay/sand, g/kg for SOC).
    """
    c = clay / 100.0
    s = sand / 100.0
    om = soc * 0.1  # SOC g/kg -> approximate OM%

    # Field capacity (theta_33)
    t33_b = -0.251 * s + 0.195 * c + 0.011 * om + 0.006 * (s * om)
    t33_b += -0.027 * (c * om) + 0.452 * (s * c) + 0.299
    theta_33 = t33_b + (1.283 * t33_b * t33_b - 0.374 * t33_b - 0.015)

    # Wilting point (theta_1500)
    t1500_b = -0.024 * s + 0.487 * c + 0.006 * om + 0.005 * (s * om)
    t1500_b += -0.013 * (c * om) + 0.068 * (s * c) + 0.031
    theta_1500 = t1500_b + (0.14 * t1500_b - 0.02)

    pawc = max(0, (theta_33 - theta_1500)) * 1000  # Convert to mm/m
    return round(pawc, 1)

def compute_biological_activity(soc: float, nitrogen: float) -> Dict:
    """C:N ratio and microbial activity index from SoilGrids data."""
    if nitrogen <= 0 or soc <= 0:
        return {"cn_ratio": None, "activity_score": 0, "label": "Unknown"}

    cn = soc / nitrogen
    # Optimal C:N for microbial activity is 10-15
    if cn < 10:
        score = 0.7  # N-rich, possible denitrification
        label = "N-Saturated"
    elif cn <= 15:
        score = 1.0
        label = "Optimal Cycling"
    elif cn <= 25:
        score = 0.6
        label = "Moderate Immobilization"
    else:
        score = 0.3
        label = "Severe N Lock-up"

    return {"cn_ratio": round(cn, 1), "activity_score": round(score, 2), "label": label}

def compute_cec_adequacy(cec: float, clay: float) -> Dict:
    """CEC adequacy relative to clay content."""
    if cec <= 0 or clay <= 0:
        return {"cec_per_clay": None, "adequacy": "Unknown"}
    ratio = cec / clay
    if ratio > 0.6:
        return {"cec_per_clay": round(ratio, 2), "adequacy": "High"}
    elif ratio > 0.3:
        return {"cec_per_clay": round(ratio, 2), "adequacy": "Moderate"}
    else:
        return {"cec_per_clay": round(ratio, 2), "adequacy": "Low"}

def analyze_pedogenic_memory(lat: float, lng: float) -> Dict:
    """Full pedogenic analysis using SoilGrids."""
    try:
        from layer0.data_gateway import broker
        raw = broker.get("soilgrids", "", lat, lng)
    except Exception as e:
        logger.warning(f"SoilGrids fetch via Gateway failed: {e}")
        return {"status": "unavailable", "reason": str(e)}

    if not raw or not isinstance(raw, dict):
        return {"status": "unavailable", "reason": "No soil data"}

    # ---- P0 FIX: Check generic fallback flag ----
    is_generic_fallback = raw.get("is_generic_fallback", False)
    if is_generic_fallback:
        logger.warning("SoilGrids returned generic fallback profile — all values are estimated defaults, NOT real measurements.")

    props = raw.get("properties", raw)

    # Extract values with per-field default tracking
    defaulted_fields: List[str] = []
    clay = _extract_tracked(props, "clay", 20.0, defaulted_fields)
    sand = _extract_tracked(props, "sand", 40.0, defaulted_fields)
    silt = _extract_tracked(props, "silt", 40.0, defaulted_fields)
    soc = _extract_tracked(props, "soc", 15.0, defaulted_fields)        # g/kg
    nitrogen = _extract_tracked(props, "nitrogen", 1.5, defaulted_fields) # g/kg
    ph = _extract_tracked(props, "phh2o", 7.0, defaulted_fields)
    cec = _extract_tracked(props, "cec", 15.0, defaulted_fields)         # cmol/kg

    # Also check organic_carbon key (SoilGrids uses this alias)
    if "soc" in defaulted_fields and props.get("organic_carbon") is not None:
        try:
            soc = float(props["organic_carbon"])
            defaulted_fields.remove("soc")
        except (ValueError, TypeError):
            pass

    # Normalize to 100%
    total = clay + sand + silt
    if total > 0 and abs(total - 100) > 5:
        clay = clay / total * 100
        sand = sand / total * 100
        silt = silt / total * 100

    texture = classify_texture(clay, silt, sand)
    pawc = saxton_rawls_pawc(clay, sand, soc)
    bio = compute_biological_activity(soc, nitrogen)
    cec_info = compute_cec_adequacy(cec, clay)

    # pH interpretation
    if ph < 5.5:
        ph_label = "Strongly Acidic"
    elif ph < 6.5:
        ph_label = "Moderately Acidic"
    elif ph <= 7.5:
        ph_label = "Neutral"
    elif ph <= 8.5:
        ph_label = "Alkaline"
    else:
        ph_label = "Strongly Alkaline"

    # ---- P0 FIX: Determine data quality status ----
    if is_generic_fallback:
        status = "fallback"
        quality_note = "All soil properties are generic ISRIC estimates (no mapped pixel found for this location)."
    elif len(defaulted_fields) > 3:
        status = "partial"
        quality_note = f"Properties [{', '.join(defaulted_fields)}] used statistical defaults — interpret with caution."
    elif len(defaulted_fields) > 0:
        status = "ok"
        quality_note = f"Minor defaults used for: {', '.join(defaulted_fields)}"
    else:
        status = "ok"
        quality_note = None

    result = {
        "status": status,
        "is_generic_fallback": is_generic_fallback,
        "texture_class": texture,
        "clay_pct": round(clay, 1),
        "sand_pct": round(sand, 1),
        "silt_pct": round(silt, 1),
        "pawc_mm_per_m": pawc,
        "soc_g_per_kg": round(soc, 1),
        "ph": round(ph, 1),
        "ph_label": ph_label,
        "cec_cmol_kg": round(cec, 1),
        "cec_adequacy": cec_info,
        "biological_activity": bio,
        "nitrogen_g_per_kg": round(nitrogen, 2),
    }
    if defaulted_fields:
        result["defaulted_fields"] = defaulted_fields
    if quality_note:
        result["quality_note"] = quality_note
    return result

def _extract_tracked(props: dict, key: str, default: float, defaulted: List[str]) -> float:
    """Extract a numeric value from nested SoilGrids response, tracking defaults."""
    val = props.get(key)
    if val is None:
        defaulted.append(key)
        return default
    if isinstance(val, dict):
        # Try common SoilGrids nesting patterns
        for sub in ["mean", "value", "0-5cm", "5-15cm"]:
            if sub in val and val[sub] is not None:
                try:
                    return float(val[sub])
                except (ValueError, TypeError):
                    continue
        # Try first numeric value
        for v in val.values():
            if v is not None:
                try:
                    return float(v)
                except (ValueError, TypeError):
                    continue
        defaulted.append(key)
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        defaulted.append(key)
        return default

# Legacy alias for backward compatibility
_extract = lambda props, key, default: _extract_tracked(props, key, default, [])
