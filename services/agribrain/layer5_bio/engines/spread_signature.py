"""
Layer 5 Spread Signature Engine — Spatial Pattern + Spore Dispersal Vectors

Part 1 (Original): Infer spread pattern from L2 stability outputs.
Part 2 (New Science): Gaussian plume spore dispersal model.

The New Science: Wind-Vector Spore Dispersal
==============================================
Fungal spores (e.g., Puccinia, Phytophthora) are physically transported by wind.
If Farm A has confirmed blight, the spores blow downwind in a Gaussian plume:
  - Concentration decays with distance (1/r²) and lateral spread (σ_y)
  - Wind direction determines the primary dispersal axis
  - Calm winds → local spread only; strong winds → long-range transport

Simplified Gaussian Plume Model:
  C(x,y) = (Q / (2π · σ_y · σ_z · u)) · exp(-y² / (2·σ_y²)) · exp(-z² / (2·σ_z²))

For field-level risk assessment, we simplify to:
  risk(r, θ) = Q · exp(-r / λ) · max(0, cos(θ - θ_wind))²
  where:
    r = distance to infection source
    θ = bearing from source to target field
    θ_wind = wind direction (meteorological convention: direction wind blows FROM)
    λ = decay length scale (depends on spore type)
    Q = source strength (infection severity at source farm)

Reference: Aylor (2003), Gregory (1973), Isard et al. (2011)
"""

from typing import Dict, Any, List, Optional, Tuple
import math

from layer5_bio.schema import SpreadPattern


# ── Part 1: Spatial Pattern Inference (from L2 stability) ────────────────

def infer_spread_signature(
    field_tensor,
    veg_output,
    plot_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Infer the spatial spread pattern from L2 vegetation stability outputs."""
    spread = SpreadPattern.UNKNOWN
    strength = 0.3

    stability = getattr(veg_output, "stability", None)
    if stability:
        cls = getattr(stability, "class_label", None) or getattr(stability, "stability_class", None)
        mean_var = getattr(stability, "mean_spatial_variance", None)
        std_var = getattr(stability, "std_spatial_variance", None)

        if cls and str(cls).upper().find("HETER") >= 0:
            spread = SpreadPattern.PATCHY
            strength = 0.75
        elif cls and str(cls).upper().find("TRANS") >= 0:
            spread = SpreadPattern.PATCHY
            strength = 0.65
        elif cls and str(cls).upper().find("STABLE") >= 0:
            spread = SpreadPattern.UNIFORM
            strength = 0.55

        if mean_var is not None and std_var is not None:
            if float(mean_var) > 0.25 and float(std_var) > 0.10:
                spread = SpreadPattern.PATCHY
                strength = max(strength, 0.8)

    return {"pattern": spread, "strength": float(strength)}


# ── Part 2: Gaussian Plume Spore Dispersal Model ────────────────────────

# Spore decay length scales by pathogen type (km)
SPORE_DECAY_SCALES = {
    "FUNGAL_RUST": 10.0,       # Rust urediniospores: long-range (can travel 100s of km)
    "FUNGAL_LEAF_SPOT": 3.0,   # Moderate range
    "DOWNY_MILDEW": 5.0,       # Oomycete sporangia: moderate-long range
    "POWDERY_MILDEW": 2.0,     # Conidia: shorter range
    "BACTERIAL_BLIGHT": 1.5,   # Bacteria: rain-splash + short wind
    "DEFAULT": 3.0,
}


def _bearing_between_points(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute bearing (degrees, meteorological) from point 1 to point 2.
    
    Returns bearing in degrees [0, 360), where 0=North, 90=East.
    """
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    
    x = math.sin(dlon) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon)
    
    bearing = math.degrees(math.atan2(x, y))
    return bearing % 360.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two lat/lon points in km."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_spore_dispersal_risk(
    source_lat: float,
    source_lon: float,
    source_severity: float,
    target_lat: float,
    target_lon: float,
    wind_direction_deg: float,
    wind_speed_ms: float,
    threat_type: str = "DEFAULT",
) -> Dict[str, Any]:
    """Compute downwind spore dispersal risk from an infected source field.
    
    Parameters
    ----------
    source_lat, source_lon : coordinates of infected farm
    source_severity        : infection severity at source [0, 1]
    target_lat, target_lon : coordinates of target farm
    wind_direction_deg     : meteorological wind direction (degrees, where wind blows FROM)
    wind_speed_ms          : wind speed in m/s
    threat_type            : pathogen type for decay scale lookup
    
    Returns
    -------
    Dict with:
      - dispersal_risk: [0, 1] probability modifier for the target farm
      - distance_km: distance between farms
      - alignment_score: how well the target aligns with the downwind vector
      - is_downwind: True if target is in the downwind cone
    """
    # Distance between farms
    distance = _haversine_km(source_lat, source_lon, target_lat, target_lon)
    
    # Bearing from source to target
    bearing = _bearing_between_points(source_lat, source_lon, target_lat, target_lon)
    
    # Wind blows FROM wind_direction_deg, so spores travel in the OPPOSITE direction
    # downwind_direction = direction spores travel TO
    downwind_dir = (wind_direction_deg + 180.0) % 360.0
    
    # Angular alignment: how well does the source→target vector align with downwind?
    angle_diff = abs(bearing - downwind_dir)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff
    
    # Cosine-squared alignment (tight downwind cone, ~90° half-width)
    if angle_diff <= 90:
        alignment = math.cos(math.radians(angle_diff)) ** 2
        is_downwind = True
    else:
        alignment = 0.0
        is_downwind = False
    
    # Distance decay (exponential)
    decay_scale = SPORE_DECAY_SCALES.get(threat_type, SPORE_DECAY_SCALES["DEFAULT"])
    
    # Wind speed amplification: stronger wind → longer effective range
    # Calm wind (<1 m/s) → local spread only; strong wind (>5 m/s) → extended range
    wind_factor = max(0.2, min(2.5, wind_speed_ms / 3.0))
    effective_scale = decay_scale * wind_factor
    
    distance_decay = math.exp(-distance / effective_scale) if effective_scale > 0 else 0.0
    
    # Final dispersal risk
    dispersal_risk = source_severity * distance_decay * alignment
    dispersal_risk = max(0.0, min(1.0, dispersal_risk))
    
    return {
        "dispersal_risk": round(dispersal_risk, 4),
        "distance_km": round(distance, 2),
        "alignment_score": round(alignment, 3),
        "is_downwind": is_downwind,
        "downwind_direction": round(downwind_dir, 1),
        "bearing_to_target": round(bearing, 1),
        "effective_range_km": round(effective_scale, 1),
    }


def compute_regional_spore_risk(
    target_lat: float,
    target_lon: float,
    nearby_infections: List[Dict[str, Any]],
    wind_direction_deg: float,
    wind_speed_ms: float,
) -> Dict[str, float]:
    """Aggregate spore dispersal risk from ALL nearby infected farms.
    
    Parameters
    ----------
    target_lat, target_lon : coordinates of the farm being assessed
    nearby_infections      : list of dicts with keys:
                             {lat, lon, severity, threat_type, farm_id}
    wind_direction_deg     : current wind direction
    wind_speed_ms          : current wind speed
    
    Returns
    -------
    Dict[threat_type, aggregated_risk] — max risk per threat type from all sources
    """
    if not nearby_infections:
        return {}
    
    risk_by_threat: Dict[str, float] = {}
    
    for infection in nearby_infections:
        src_lat = infection.get("lat", 0.0)
        src_lon = infection.get("lon", 0.0)
        severity = infection.get("severity", 0.0)
        threat_type = infection.get("threat_type", "DEFAULT")
        
        if severity < 0.1:
            continue  # Below threshold, ignore
        
        result = compute_spore_dispersal_risk(
            source_lat=src_lat,
            source_lon=src_lon,
            source_severity=severity,
            target_lat=target_lat,
            target_lon=target_lon,
            wind_direction_deg=wind_direction_deg,
            wind_speed_ms=wind_speed_ms,
            threat_type=threat_type,
        )
        
        current = risk_by_threat.get(threat_type, 0.0)
        # Take maximum risk from any source (conservative: worst-case exposure)
        risk_by_threat[threat_type] = max(current, result["dispersal_risk"])
    
    return risk_by_threat
