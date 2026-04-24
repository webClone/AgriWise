"""
Zone-Aware Suitability — Per-Zone and Plot-Level Suitability Datatypes
======================================================================
Phase B+: Each zone gets an independent suitability score, confidence, and
limiting factors. The plot-level score is an area-weighted aggregate
that also accounts for weakest-zone sensitivity.

Institutional-Grade Features:
- Semantic zone labels (not Zone A/B/C)
- Multi-driver narrative tying DEM+SAR+NDVI+Soil+Forecast
- Spatially decomposed confidence (per-zone asymmetry)
- Risk Concentration Index (RCI)
- Intervention Efficiency Ranking (IER)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional


# ============================================================================
# SEMANTIC ZONE LABELS
# ============================================================================

def generate_semantic_label(
    zone_label: str,
    spatial_label: str,
    feature_means: Dict[str, float],
    limiting_factors: List[str],
) -> str:
    """
    Generate a descriptive semantic label for a zone.
    Instead of "Zone A", produce "South-West Low Moisture Zone" or "High Vigor Strip".
    
    Logic:
    1. Start with spatial position
    2. Add dominant characteristic (from feature means + limiting factors)
    3. Add morphological descriptor
    """
    # Spatial prefix
    spatial_map = {
        "north": "Northern",
        "south": "Southern",
        "east": "Eastern",
        "west": "Western",
        "north-east": "North-East",
        "north-west": "North-West",
        "south-east": "South-East",
        "south-west": "South-West",
        "center": "Central",
        "entire field": "Whole-Field",
    }
    spatial_prefix = spatial_map.get(spatial_label, spatial_label.title())
    
    # Characteristic from zone_label and features
    ndvi = feature_means.get("NDVI", 0)
    sar = feature_means.get("SAR_VV", None)
    
    if zone_label == "HIGH_VIGOR":
        if ndvi > 0.5:
            characteristic = "High Vigor"
        elif ndvi > 0.3:
            characteristic = "Moderate Vigor"
        else:
            characteristic = "Early Growth"
    elif zone_label == "LOW_VIGOR":
        # Diagnose WHY it's low vigor from limiting factors + features
        if any("water" in f.lower() for f in limiting_factors):
            characteristic = "Low Moisture"
        elif any("soil" in f.lower() for f in limiting_factors):
            characteristic = "Soil-Constrained"
        elif any("biotic" in f.lower() for f in limiting_factors):
            characteristic = "Disease-Risk"
        else:
            characteristic = "Stressed"
    elif zone_label == "MED_VIGOR":
        characteristic = "Transitional"
    elif zone_label == "WET_ZONE":
        characteristic = "Waterlogged"
    elif zone_label == "COMPACTED":
        characteristic = "Compacted"
    elif zone_label == "HOMOGENEOUS":
        characteristic = "Uniform"
    else:
        characteristic = "Mixed"
    
    # Morphological descriptor based on area
    # (will be set by caller, not computed here)
    return f"{spatial_prefix} {characteristic} Zone"


# ============================================================================
# MULTI-DRIVER NARRATIVE
# ============================================================================

def build_multi_driver_narrative(
    zone_stats: Dict[str, Any],
    driver_scores: Dict[str, float],
    limiting_factors: List[str],
) -> str:
    """
    Build a multi-driver narrative tying together all data sources.
    Instead of "water is the bottleneck", produce:
    "Low moisture (SAR VV: -12.3 dB) combined with moderate slope
    and clay-heavy soil (34%) limits drainage in this zone."
    """
    parts = []
    f_means = zone_stats.get("feature_means", {})
    f_p10 = zone_stats.get("feature_p10", {})
    f_p90 = zone_stats.get("feature_p90", {})
    valid_frac = zone_stats.get("valid_fraction", {})
    
    # NDVI signal
    ndvi = f_means.get("NDVI", None)
    if ndvi is not None:
        ndvi_range = f_p90.get("NDVI", 0) - f_p10.get("NDVI", 0)
        if ndvi < 0.15:
            parts.append(f"Very low vegetation (NDVI: {ndvi:.3f})")
        elif ndvi < 0.3:
            parts.append(f"Below-average canopy cover (NDVI: {ndvi:.3f})")
        else:
            parts.append(f"Adequate vegetation (NDVI: {ndvi:.3f})")
        if ndvi_range > 0.1:
            parts.append(f"high internal variability (p10-p90: {ndvi_range:.3f})")
    
    # SAR moisture proxy
    sar = f_means.get("SAR_VV", None)
    if sar is not None:
        if sar < -15:
            parts.append(f"dry surface (SAR VV: {sar:.1f} dB)")
        elif sar > -10:
            parts.append(f"wet/saturated surface (SAR VV: {sar:.1f} dB)")
        else:
            parts.append(f"moderate moisture (SAR VV: {sar:.1f} dB)")
    elif valid_frac.get("SAR_VV", 0) == 0:
        parts.append("no SAR coverage — moisture unverified")
    
    # Soil properties
    clay = f_means.get("SOIL_CLAY", None)
    if clay is not None:
        if clay > 40:
            parts.append(f"heavy clay soil ({clay:.0f}% clay, SoilGrids 250m proxy)")
        elif clay > 25:
            parts.append(f"moderate clay ({clay:.0f}%, SoilGrids 250m)")
        else:
            parts.append(f"light-textured soil ({clay:.0f}% clay)")
    
    soil_ph = f_means.get("SOIL_PH", None)
    if soil_ph is not None:
        if soil_ph < 5.5:
            parts.append(f"acidic soil (pH: {soil_ph:.1f})")
        elif soil_ph > 8.0:
            parts.append(f"alkaline soil (pH: {soil_ph:.1f})")
    
    # Driver bottleneck
    if driver_scores:
        worst_driver = min(driver_scores, key=driver_scores.get)
        worst_val = driver_scores[worst_driver]
        if worst_val < 0.6:
            parts.append(f"primary bottleneck: {worst_driver} ({worst_val:.0%})")
    
    if not parts:
        return "Insufficient data for multi-driver analysis."
    
    return "; ".join(parts) + "."


# ============================================================================
# CONFIDENCE NARRATIVE (Spatially Decomposed)
# ============================================================================

def build_confidence_narrative(
    zone_stats: Dict[str, Any],
    confidence: float,
) -> str:
    """
    Build a confidence narrative explaining WHY a zone has that confidence level,
    tied to specific data coverage gaps.
    """
    valid_frac = zone_stats.get("valid_fraction", {})
    parts = []
    
    badge = "HIGH" if confidence > 0.7 else ("MED" if confidence > 0.4 else "LOW")
    
    # Check each data source
    sar_vf = valid_frac.get("SAR_VV", 0)
    ndvi_vf = valid_frac.get("NDVI", 0)
    soil_vf = valid_frac.get("SOIL_CLAY", 0)
    
    if sar_vf < 0.3:
        parts.append("sparse SAR coverage in this quadrant")
    if ndvi_vf < 0.5:
        parts.append("limited NDVI observations")
    if soil_vf <= 0.5:
        parts.append("SoilGrids 250m proxy (not field-measured)")
    
    if not parts:
        return f"Confidence {badge} ({confidence:.2f}): good data coverage across all sources."
    
    return f"Confidence {badge} ({confidence:.2f}) due to: {', '.join(parts)}."


# ============================================================================
# CORE DATACLASSES
# ============================================================================

@dataclass
class ZoneSuitability:
    """Suitability evaluation for a single management zone."""
    zone_id: int
    zone_key: str               # "Zone A", "Zone B", etc. (internal)
    zone_label: str             # "HIGH_VIGOR", "LOW_VIGOR", etc.
    spatial_label: str          # "north-west", "south-east", etc.
    semantic_label: str = ""    # "South-West Low Moisture Zone" (human-facing)
    area_pct: float = 0.0

    # Core metrics
    suitability_pct: float = 0.0
    confidence: float = 0.0     # 0..1
    confidence_narrative: str = ""  # "LOW due to sparse SAR in this quadrant"

    # Per-driver probability scores
    driver_scores: Dict[str, float] = field(default_factory=dict)

    # Multi-driver narrative
    multi_driver_narrative: str = ""  # Full causal chain

    # Top limiting factors for this zone
    limiting_factors: List[str] = field(default_factory=list)

    # Evidence traces
    evidence_traces: List[str] = field(default_factory=list)

    # Zone-specific notes
    notes: List[str] = field(default_factory=list)
    
    # Intervention Efficiency: "If this zone is fixed, plot suit goes from X% → Y%"
    intervention_delta: float = 0.0  # how many % points plot suit improves if this zone reaches best-zone level

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_key": self.zone_key,
            "zone_label": self.zone_label,
            "spatial_label": self.spatial_label,
            "semantic_label": self.semantic_label,
            "area_pct": round(self.area_pct, 1),
            "suitability_pct": round(self.suitability_pct, 1),
            "confidence": round(self.confidence, 3),
            "confidence_narrative": self.confidence_narrative,
            "driver_scores": {k: round(v, 3) for k, v in self.driver_scores.items()},
            "multi_driver_narrative": self.multi_driver_narrative,
            "limiting_factors": self.limiting_factors,
            "evidence_traces": self.evidence_traces,
            "notes": self.notes,
            "intervention_delta": round(self.intervention_delta, 1),
        }


@dataclass
class PlotSuitability:
    """
    Aggregated plot-level suitability derived from zone-level analysis.
    
    Suitability is area-weighted:
        Suit(plot) = Σ (area_pct × Suit(zone)) / 100
    
    Confidence uses worst-zone sensitivity:
        Conf(plot) = 0.6 × mean(conf) + 0.4 × min(conf)
    """
    suitability_pct: float
    confidence: float
    zone_weighting: str     # "area-weighted", "risk-weighted"

    zone_breakdown: List[ZoneSuitability] = field(default_factory=list)

    # Plot-level derived fields
    plot_limiting_factors: List[str] = field(default_factory=list)
    weakest_zone_key: str = ""
    strongest_zone_key: str = ""
    
    # Risk Concentration Index
    risk_concentration_index: float = 0.0  # 0 = evenly distributed, 1 = concentrated
    risk_distribution: str = ""  # "Risk is concentrated in Zone C (south-west)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suitability_pct": round(self.suitability_pct, 1),
            "confidence": round(self.confidence, 3),
            "zone_weighting": self.zone_weighting,
            "weakest_zone_key": self.weakest_zone_key,
            "strongest_zone_key": self.strongest_zone_key,
            "plot_limiting_factors": self.plot_limiting_factors,
            "risk_concentration_index": round(self.risk_concentration_index, 3),
            "risk_distribution": self.risk_distribution,
            "zone_breakdown": [z.to_dict() for z in self.zone_breakdown],
        }


# ============================================================================
# CONFIDENCE FORMULA
# ============================================================================

def compute_zone_confidence(
    zone_stats: Dict[str, Any],
    driver_scores: Dict[str, float],
    w_missing: float = 0.3,
    w_res: float = 0.1,
    w_var: float = 0.2,
    w_disagree: float = 0.2,
) -> float:
    """
    Zone-level confidence formula.
    
    conf(zone) = clamp(
        1.0
        - w_missing × MissingPenalty
        - w_res × ResMismatchPenalty
        - w_var × SpatialVarPenalty
        - w_disagree × EngineDisagreement
    , 0, 1)
    """
    valid_frac = zone_stats.get("valid_fraction", {})
    feature_p10 = zone_stats.get("feature_p10", {})
    feature_p90 = zone_stats.get("feature_p90", {})

    # MissingPenalty: weighted mean of (1 - valid_fraction) across features
    feature_weights = {"NDVI": 0.4, "SAR_VV": 0.2, "SOIL_CLAY": 0.15, "SOIL_PH": 0.1, "SOIL_OC": 0.15}
    missing_penalty = 0.0
    total_fw = 0.0
    for feat, fw in feature_weights.items():
        vf = valid_frac.get(feat, 0.0)
        missing_penalty += fw * (1.0 - vf)
        total_fw += fw
    if total_fw > 0:
        missing_penalty /= total_fw

    # ResMismatchPenalty: penalize if soil is 250m and zone is 10m
    res_penalty = 0.0
    if "SOIL_CLAY" in valid_frac and valid_frac["SOIL_CLAY"] <= 0.5:
        res_penalty = 0.3  # coarse soil data

    # SpatialVarPenalty: if p90-p10 is high, zone is heterogeneous → reduce confidence
    var_penalty = 0.0
    ndvi_p10 = feature_p10.get("NDVI", 0)
    ndvi_p90 = feature_p90.get("NDVI", 0)
    ndvi_range = ndvi_p90 - ndvi_p10
    if ndvi_range > 0.15:
        var_penalty = min(ndvi_range / 0.3, 1.0)

    # EngineDisagreement: stddev of driver scores
    if driver_scores:
        scores = list(driver_scores.values())
        mean_s = sum(scores) / len(scores)
        disagree = (sum((s - mean_s) ** 2 for s in scores) / len(scores)) ** 0.5
    else:
        disagree = 0.3

    conf = 1.0 - (
        w_missing * missing_penalty +
        w_res * res_penalty +
        w_var * var_penalty +
        w_disagree * disagree
    )
    return max(0.05, min(1.0, conf))


# ============================================================================
# RISK CONCENTRATION INDEX
# ============================================================================

def compute_risk_concentration_index(zone_results: List[ZoneSuitability]) -> Tuple[float, str]:
    """
    Compute Risk Concentration Index (RCI).
    
    RCI = Σ(area_zone × risk_zone²) / Σ(area_zone × max_risk²)
    
    Where risk_zone = 1 - (suitability/100)
    
    RCI ≈ 0 → risk is evenly distributed across the plot
    RCI ≈ 1 → risk is concentrated in a small area
    
    Returns: (rci_value, narrative)
    """
    if not zone_results or len(zone_results) < 2:
        return (0.0, "Single zone — no spatial risk differentiation.")
    
    total_area = sum(z.area_pct for z in zone_results)
    if total_area == 0:
        return (0.0, "No area data.")
    
    # Compute weighted risk²
    weighted_risk_sq = sum(
        z.area_pct * ((100.0 - z.suitability_pct) / 100.0) ** 2
        for z in zone_results
    ) / total_area
    
    # Max possible concentration: all risk in smallest zone
    max_risk = max((100.0 - z.suitability_pct) / 100.0 for z in zone_results)
    mean_risk = sum(
        z.area_pct * ((100.0 - z.suitability_pct) / 100.0)
        for z in zone_results
    ) / total_area
    
    # Normalized: compare variance of risk distribution
    risk_values = [(100.0 - z.suitability_pct) / 100.0 for z in zone_results]
    risk_mean = sum(risk_values) / len(risk_values)
    risk_var = sum((r - risk_mean) ** 2 for r in risk_values) / len(risk_values)
    
    # RCI: normalized coefficient of variation
    rci = min(1.0, (risk_var ** 0.5) / max(risk_mean, 0.01))
    
    # Narrative
    worst = max(zone_results, key=lambda z: (100.0 - z.suitability_pct))
    if rci > 0.5:
        narrative = (f"Risk is concentrated in {worst.semantic_label or worst.zone_key} "
                    f"({worst.spatial_label}, {worst.area_pct:.0f}% of field). "
                    f"Targeted intervention is more efficient than blanket treatment.")
    elif rci > 0.2:
        narrative = (f"Risk is moderately spread but {worst.semantic_label or worst.zone_key} "
                    f"shows elevated stress. Consider zonal management.")
    else:
        narrative = "Risk is evenly distributed — blanket treatment may be appropriate."
    
    return (round(rci, 3), narrative)


# ============================================================================
# INTERVENTION EFFICIENCY RANKING
# ============================================================================

def compute_intervention_efficiency(
    zone_results: List[ZoneSuitability],
    plot_suitability: float,
) -> List[ZoneSuitability]:
    """
    For each zone, compute: "If this zone reaches the best zone's suitability,
    how much does the plot-level score improve?"
    
    This is the Intervention Efficiency Ranking (IER).
    
    Delta = (best_suit - zone_suit) × (zone_area / 100)
    """
    if not zone_results or len(zone_results) < 2:
        return zone_results
    
    best_suit = max(z.suitability_pct for z in zone_results)
    total_area = sum(z.area_pct for z in zone_results)
    if total_area == 0:
        total_area = 100.0
    
    for z in zone_results:
        delta = (best_suit - z.suitability_pct) * (z.area_pct / total_area)
        z.intervention_delta = round(delta, 1)
    
    return zone_results


# ============================================================================
# MAIN AGGREGATION
# ============================================================================

def aggregate_plot_suitability(
    zone_results: List[ZoneSuitability],
) -> PlotSuitability:
    """
    Aggregate zone-level suitability into plot-level score.
    
    Suit(plot) = Σ (area_pct × Suit(zone)) / 100
    Conf(plot) = 0.6 × mean(conf) + 0.4 × min(conf)
    """
    if not zone_results:
        return PlotSuitability(
            suitability_pct=0.0,
            confidence=0.0,
            zone_weighting="area-weighted",
        )

    total_area = sum(z.area_pct for z in zone_results)
    if total_area == 0:
        total_area = 100.0

    # Area-weighted suitability
    suit = sum(z.area_pct * z.suitability_pct for z in zone_results) / total_area

    # Confidence: weighted mean + worst-zone sensitivity
    conf_values = [z.confidence for z in zone_results]
    mean_conf = sum(z.area_pct * z.confidence for z in zone_results) / total_area
    min_conf = min(conf_values)
    plot_conf = 0.6 * mean_conf + 0.4 * min_conf

    # Identify weakest and strongest
    weakest = min(zone_results, key=lambda z: z.suitability_pct)
    strongest = max(zone_results, key=lambda z: z.suitability_pct)

    # Collect unique limiting factors from all zones
    all_factors = []
    for z in zone_results:
        for f in z.limiting_factors:
            if f not in all_factors:
                all_factors.append(f)
    
    # Intervention Efficiency
    zone_results = compute_intervention_efficiency(zone_results, suit)
    
    # Risk Concentration Index
    rci, rci_narrative = compute_risk_concentration_index(zone_results)

    return PlotSuitability(
        suitability_pct=round(suit, 1),
        confidence=round(plot_conf, 3),
        zone_weighting="area-weighted",
        zone_breakdown=zone_results,
        plot_limiting_factors=all_factors[:5],
        weakest_zone_key=weakest.zone_key,
        strongest_zone_key=strongest.zone_key,
        risk_concentration_index=rci,
        risk_distribution=rci_narrative,
    )
