"""
Crop Suitability Engine — FAO GAEZ-inspired multi-factor scoring
================================================================

Evaluates all 212 crops from ``CROP_REGISTRY`` for biophysical suitability
at a given plot location. Produces rainfed and irrigated rankings with
limiting factor analysis.

Scoring dimensions (each 0–100, weighted sum):
  Temperature suitability   20%   CropSpec optimal_temp_min/max
  GDD availability          10%   gdd_base_temp × frost-free days
  Season length              5%   growing_days vs frost-free window
  Rainfall adequacy         20%   ARIDITY_CROP_THRESHOLDS × annual rainfall
  Soil pH                   15%   pH optimum/tolerance by crop family
  Soil texture/AWC          10%   architecture defaults
  Salinity tolerance        10%   ec_threshold_ds_m, ec_slope_pct
  Slope/elevation            5%   architecture constraints
  Frost/heat risk            5%   extreme temperature penalties

References:
  - FAO GAEZ v4 methodology (IIASA 2021)
  - Allen et al. (1998) FAO-56 crop water requirements
  - Maas & Hoffman (1977) salt tolerance model
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


# ── Scoring weights ─────────────────────────────────────────────────────────
_WEIGHTS = {
    "temperature":   0.20,
    "gdd":           0.10,
    "season_length": 0.05,
    "rainfall":      0.20,
    "soil_ph":       0.15,
    "soil_texture":  0.10,
    "salinity":      0.10,
    "slope":         0.05,
    "frost_heat":    0.05,
}

# ── Soil pH optimum by botanical family (fallback per architecture) ─────────
# Source: FAO Soils Bulletin 73, Brady & Weil (2017)
_PH_OPTIMAL: Dict[str, tuple] = {
    # Family-level
    "Poaceae":        (5.5, 7.5),
    "Fabaceae":       (6.0, 7.5),
    "Solanaceae":     (5.5, 7.0),
    "Cucurbitaceae":  (6.0, 7.0),
    "Brassicaceae":   (6.0, 7.5),
    "Rosaceae":       (6.0, 7.5),
    "Rutaceae":       (5.5, 7.0),
    "Oleaceae":       (6.5, 8.5),   # Olive tolerates alkaline
    "Arecaceae":      (6.0, 8.0),   # Date palm tolerates alkaline
    "Vitaceae":       (5.5, 7.5),
    "Asteraceae":     (6.0, 7.5),
    "Amaranthaceae":  (6.0, 7.5),
    "Malvaceae":      (6.0, 7.5),
    "Apiaceae":       (6.0, 7.0),
    "Moraceae":       (6.0, 7.5),
    "Lythraceae":     (5.5, 7.5),   # Pomegranate
    "Linaceae":       (5.5, 7.0),
    "Amaryllidaceae": (6.0, 7.0),
    # Architecture-level fallbacks
    "cereal":         (5.5, 7.5),
    "legume":         (6.0, 7.5),
    "vegetable":      (6.0, 7.0),
    "perennial":      (5.5, 8.0),
    "tropical_tree":  (5.5, 7.0),
    "rice":           (5.0, 7.0),
    "cotton":         (6.0, 7.5),
    "maize":          (5.5, 7.5),
}

# ── Soil texture suitability by architecture ────────────────────────────────
# Score [0-100] for each USDA texture class
_TEXTURE_SUITABILITY: Dict[str, Dict[str, int]] = {
    "cereal":    {"clay": 60, "clay_loam": 80, "loam": 100, "sandy_loam": 85, "sand": 50},
    "legume":    {"clay": 55, "clay_loam": 75, "loam": 100, "sandy_loam": 90, "sand": 60},
    "vegetable": {"clay": 40, "clay_loam": 70, "loam": 100, "sandy_loam": 90, "sand": 55},
    "perennial": {"clay": 45, "clay_loam": 75, "loam": 100, "sandy_loam": 85, "sand": 55},
    "tropical_tree": {"clay": 50, "clay_loam": 80, "loam": 100, "sandy_loam": 80, "sand": 45},
    "rice":      {"clay": 100, "clay_loam": 90, "loam": 70, "sandy_loam": 40, "sand": 20},
    "cotton":    {"clay": 50, "clay_loam": 85, "loam": 100, "sandy_loam": 80, "sand": 45},
    "maize":     {"clay": 55, "clay_loam": 80, "loam": 100, "sandy_loam": 85, "sand": 50},
}

# ── Slope limits by architecture (max tolerable slope %) ────────────────────
_SLOPE_MAX: Dict[str, float] = {
    "cereal": 15.0, "legume": 15.0, "vegetable": 10.0, "perennial": 30.0,
    "tropical_tree": 25.0, "rice": 3.0, "cotton": 10.0, "maize": 12.0,
}


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class LimitingFactor:
    """A single factor limiting a crop's suitability."""
    factor: str
    severity: str        # "low" | "medium" | "high" | "critical"
    message: str
    score_impact: float  # how many points lost (0-100)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CropSuitabilityCandidate:
    """One crop's suitability evaluation."""
    code: str
    name: str
    name_ar: str
    score: int                        # 0-100
    suitability_class: str            # S1 | S2 | S3 | N
    limiting_factors: List[LimitingFactor] = field(default_factory=list)
    data_quality_tier: str = "curated"
    dimension_scores: Dict[str, int] = field(default_factory=dict)

    # Economic placeholders (P2 — not evaluated in P0)
    economic_score: Optional[float] = None
    water_productivity_score: Optional[float] = None
    economic_status: str = "not_evaluated"

    def to_dict(self) -> dict:
        d = {
            "code": self.code,
            "name": self.name,
            "name_ar": self.name_ar,
            "score": self.score,
            "suitability_class": self.suitability_class,
            "limiting_factors": [lf.to_dict() for lf in self.limiting_factors],
            "data_quality_tier": self.data_quality_tier,
            "dimension_scores": self.dimension_scores,
            "economic_score": self.economic_score,
            "water_productivity_score": self.water_productivity_score,
            "economic_status": self.economic_status,
        }
        return d


@dataclass
class CropSuitabilityResult:
    """Full suitability evaluation result."""
    rainfed: List[CropSuitabilityCandidate]   # Top 15 sorted by score
    irrigated: List[CropSuitabilityCandidate]  # Top 15 sorted by score
    limiting_factors_summary: List[str]        # Site-level limiting factors
    total_evaluated: int = 0

    def to_dict(self) -> dict:
        return {
            "rainfed": [c.to_dict() for c in self.rainfed],
            "irrigated": [c.to_dict() for c in self.irrigated],
            "limiting_factors_summary": self.limiting_factors_summary,
            "total_evaluated": self.total_evaluated,
        }


# ── Engine ──────────────────────────────────────────────────────────────────

class CropSuitabilityEngine:
    """FAO GAEZ-inspired multi-factor suitability scoring.

    Evaluates every crop in ``CROP_REGISTRY`` against the plot's biophysical
    conditions and returns ranked rainfed and irrigated candidates.
    """

    def evaluate(
        self,
        *,
        lat: float,
        lng: float,
        elevation_m: float = 0.0,
        mean_temp_c: float = 20.0,
        annual_rainfall_mm: float = 400.0,
        et0_mm: Optional[float] = None,
        soil_ph: float = 7.0,
        soil_texture: str = "loam",
        soil_awc: float = 0.15,
        soil_salinity_ds_m: float = 0.0,
        slope_pct: float = 0.0,
        irrigation_type: str = "rainfed",
        frost_days: Optional[int] = None,
        heat_days_above_35: Optional[int] = None,
        soil_depth_cm: float = 100.0,
        vpd_kpa: Optional[float] = None,
    ) -> CropSuitabilityResult:
        """Evaluate all crops and return suitability rankings."""
        try:
            from crop_database import CROP_REGISTRY
        except ImportError:
            return CropSuitabilityResult(
                rainfed=[], irrigated=[],
                limiting_factors_summary=["Crop registry unavailable"],
                total_evaluated=0,
            )

        # Import data quality tiers
        try:
            from layer2_veg_int.crop_science_data import (
                CROP_DATA_QUALITY, ARIDITY_CROP_THRESHOLDS,
                BOTANICAL_FAMILIES,
            )
        except ImportError:
            CROP_DATA_QUALITY = {}
            ARIDITY_CROP_THRESHOLDS = {}
            BOTANICAL_FAMILIES = {}

        # Normalize texture
        tex = soil_texture.strip().lower().replace(" ", "_").replace("-", "_")
        if tex not in ("clay", "clay_loam", "loam", "sandy_loam", "sand"):
            tex = "loam"

        # Compute frost-free days from frost_days if available
        frost_free_days = 365 - (frost_days or 0)

        # Site-level limiting factors
        site_limits = []
        if annual_rainfall_mm < 200:
            site_limits.append("Very low rainfall (<200 mm/yr)")
        if soil_salinity_ds_m > 4.0:
            site_limits.append(f"High soil salinity ({soil_salinity_ds_m:.1f} dS/m)")
        if slope_pct > 20:
            site_limits.append(f"Steep slope ({slope_pct:.0f}%)")
        if mean_temp_c < 5:
            site_limits.append(f"Cold climate ({mean_temp_c:.1f}°C)")

        rainfed_candidates = []
        irrigated_candidates = []

        for code, spec in CROP_REGISTRY.items():
            # Quality tier for this crop
            quality = CROP_DATA_QUALITY.get(code, {})
            # Determine overall data quality
            tier_values = list(quality.values()) if quality else []
            if all(t in ("curated_literature", "curated") for t in tier_values):
                overall_tier = "curated"
            elif any(t == "heuristic" for t in tier_values):
                overall_tier = "heuristic"
            else:
                overall_tier = "architecture_default"

            # Score each dimension
            dims_rainfed = {}
            dims_irrigated = {}
            lf_rainfed: List[LimitingFactor] = []
            lf_irrigated: List[LimitingFactor] = []

            # 1. Temperature suitability
            t_score = self._score_temperature(spec, mean_temp_c)
            dims_rainfed["temperature"] = t_score
            dims_irrigated["temperature"] = t_score
            if t_score < 30:
                msg = f"Mean temp {mean_temp_c:.0f}°C outside optimal range {spec.optimal_temp_min}-{spec.optimal_temp_max}°C"
                sev = "critical" if t_score < 10 else "high"
                lf = LimitingFactor("temperature", sev, msg, 100 - t_score)
                lf_rainfed.append(lf)
                lf_irrigated.append(lf)

            # 2. GDD availability
            gdd_score = self._score_gdd(spec, mean_temp_c, frost_free_days)
            dims_rainfed["gdd"] = gdd_score
            dims_irrigated["gdd"] = gdd_score

            # 3. Season length
            season_score = self._score_season_length(spec, frost_free_days)
            dims_rainfed["season_length"] = season_score
            dims_irrigated["season_length"] = season_score
            if season_score < 30:
                lf = LimitingFactor(
                    "season_length", "high",
                    f"Frost-free season ({frost_free_days}d) too short for {spec.growing_days}d crop",
                    100 - season_score,
                )
                lf_rainfed.append(lf)
                lf_irrigated.append(lf)

            # 4. Rainfall adequacy (rainfed vs irrigated)
            rain_score_rainfed = self._score_rainfall(
                spec, code, annual_rainfall_mm, mean_temp_c,
                ARIDITY_CROP_THRESHOLDS, irrigated=False,
            )
            rain_score_irrigated = self._score_rainfall(
                spec, code, annual_rainfall_mm, mean_temp_c,
                ARIDITY_CROP_THRESHOLDS, irrigated=True,
            )
            dims_rainfed["rainfall"] = rain_score_rainfed
            dims_irrigated["rainfall"] = rain_score_irrigated
            if rain_score_rainfed < 30:
                lf_rainfed.append(LimitingFactor(
                    "rainfall", "high" if rain_score_rainfed > 10 else "critical",
                    f"Rainfall ({annual_rainfall_mm:.0f} mm) below crop water requirement",
                    100 - rain_score_rainfed,
                ))

            # 5. Soil pH
            family = BOTANICAL_FAMILIES.get(code, "")
            ph_score = self._score_soil_ph(spec, soil_ph, family)
            dims_rainfed["soil_ph"] = ph_score
            dims_irrigated["soil_ph"] = ph_score
            if ph_score < 40:
                lf = LimitingFactor(
                    "soil_ph", "medium" if ph_score > 20 else "high",
                    f"Soil pH {soil_ph:.1f} suboptimal for this crop",
                    100 - ph_score,
                )
                lf_rainfed.append(lf)
                lf_irrigated.append(lf)

            # 6. Soil texture/AWC
            tex_score = self._score_soil_texture(spec, tex)
            dims_rainfed["soil_texture"] = tex_score
            dims_irrigated["soil_texture"] = tex_score

            # 7. Salinity tolerance
            sal_score = self._score_salinity(spec, soil_salinity_ds_m)
            dims_rainfed["salinity"] = sal_score
            dims_irrigated["salinity"] = sal_score
            if sal_score < 40:
                lf = LimitingFactor(
                    "salinity", "medium" if sal_score > 20 else "high",
                    f"Soil EC {soil_salinity_ds_m:.1f} dS/m near/above tolerance threshold",
                    100 - sal_score,
                )
                lf_rainfed.append(lf)
                lf_irrigated.append(lf)

            # 8. Slope
            slope_score = self._score_slope(spec, slope_pct)
            dims_rainfed["slope"] = slope_score
            dims_irrigated["slope"] = slope_score

            # 9. Frost/heat risk
            fh_score = self._score_frost_heat(
                spec, frost_days, heat_days_above_35,
            )
            dims_rainfed["frost_heat"] = fh_score
            dims_irrigated["frost_heat"] = fh_score
            if fh_score < 30:
                lf = LimitingFactor(
                    "frost_heat", "high",
                    "High frost/heat risk for this crop",
                    100 - fh_score,
                )
                lf_rainfed.append(lf)
                lf_irrigated.append(lf)

            # Weighted sum
            total_rainfed = sum(
                dims_rainfed.get(k, 50) * w for k, w in _WEIGHTS.items()
            )
            total_irrigated = sum(
                dims_irrigated.get(k, 50) * w for k, w in _WEIGHTS.items()
            )

            score_rainfed = int(round(max(0, min(100, total_rainfed))))
            score_irrigated = int(round(max(0, min(100, total_irrigated))))

            rainfed_candidates.append(CropSuitabilityCandidate(
                code=code,
                name=spec.name,
                name_ar=spec.name_ar or "",
                score=score_rainfed,
                suitability_class=self._classify(score_rainfed),
                limiting_factors=lf_rainfed,
                data_quality_tier=overall_tier,
                dimension_scores=dims_rainfed,
            ))
            irrigated_candidates.append(CropSuitabilityCandidate(
                code=code,
                name=spec.name,
                name_ar=spec.name_ar or "",
                score=score_irrigated,
                suitability_class=self._classify(score_irrigated),
                limiting_factors=lf_irrigated,
                data_quality_tier=overall_tier,
                dimension_scores=dims_irrigated,
            ))

        # Sort and return top 15
        rainfed_candidates.sort(key=lambda c: c.score, reverse=True)
        irrigated_candidates.sort(key=lambda c: c.score, reverse=True)

        return CropSuitabilityResult(
            rainfed=rainfed_candidates[:15],
            irrigated=irrigated_candidates[:15],
            limiting_factors_summary=site_limits,
            total_evaluated=len(CROP_REGISTRY),
        )

    # ── Dimension scorers (each returns 0-100) ──────────────────────────────

    @staticmethod
    def _score_temperature(spec, mean_temp_c: float) -> int:
        opt_min = spec.optimal_temp_min
        opt_max = spec.optimal_temp_max
        mid = (opt_min + opt_max) / 2.0

        if opt_min <= mean_temp_c <= opt_max:
            # Within optimal range — score by closeness to midpoint
            half_range = max(1, (opt_max - opt_min) / 2.0)
            closeness = 1.0 - abs(mean_temp_c - mid) / half_range
            return int(round(70 + 30 * max(0, closeness)))
        elif mean_temp_c < opt_min:
            deficit = opt_min - mean_temp_c
            return int(round(max(0, 70 - deficit * 7)))
        else:
            excess = mean_temp_c - opt_max
            return int(round(max(0, 70 - excess * 7)))

    @staticmethod
    def _score_gdd(spec, mean_temp_c: float, frost_free_days: int) -> int:
        base_temp = spec.gdd_base_temp
        daily_gdd = max(0, mean_temp_c - base_temp)
        available_gdd = daily_gdd * frost_free_days

        # Required GDD (approximate: growing_days * (optimal_mid - base_temp))
        opt_mid = (spec.optimal_temp_min + spec.optimal_temp_max) / 2.0
        required_gdd = spec.growing_days * max(1, opt_mid - base_temp)

        if required_gdd <= 0:
            return 80
        ratio = available_gdd / required_gdd
        if ratio >= 1.2:
            return 100
        elif ratio >= 1.0:
            return int(round(80 + 20 * (ratio - 1.0) / 0.2))
        elif ratio >= 0.7:
            return int(round(40 + 40 * (ratio - 0.7) / 0.3))
        else:
            return int(round(max(0, ratio / 0.7 * 40)))

    @staticmethod
    def _score_season_length(spec, frost_free_days: int) -> int:
        required = spec.growing_days
        if frost_free_days >= required * 1.1:
            return 100
        elif frost_free_days >= required:
            return 80
        elif frost_free_days >= required * 0.8:
            return int(round(40 + 40 * (frost_free_days - required * 0.8) / (required * 0.2)))
        else:
            return int(round(max(0, frost_free_days / (required * 0.8) * 40)))

    @staticmethod
    def _score_rainfall(
        spec, code: str, annual_rainfall_mm: float, mean_temp_c: float,
        aridity_thresholds: dict, irrigated: bool,
    ) -> int:
        if irrigated:
            # Under irrigation, assume water availability is adequate
            # Still penalize slightly for very high water-need crops in arid areas
            if spec.water_needs == "high" and annual_rainfall_mm < 100:
                return 80  # Some penalty — infrastructure cost implied
            return 95

        # De Martonne aridity index
        idm = annual_rainfall_mm / max(1, mean_temp_c + 10)

        # Check crop-specific thresholds
        thresholds = aridity_thresholds.get(code)
        if thresholds:
            min_idm, ideal_idm = thresholds
            if idm >= ideal_idm:
                return 100
            elif idm >= min_idm:
                return int(round(50 + 50 * (idm - min_idm) / max(1, ideal_idm - min_idm)))
            elif idm >= min_idm * 0.5:
                return int(round(20 + 30 * (idm - min_idm * 0.5) / max(1, min_idm * 0.5)))
            else:
                return int(round(max(0, idm / max(1, min_idm * 0.5) * 20)))

        # Fallback: use water_needs classification
        need_map = {"low": 8.0, "medium": 15.0, "high": 25.0}
        min_needed = need_map.get(spec.water_needs, 15.0)
        if idm >= min_needed * 1.5:
            return 100
        elif idm >= min_needed:
            return int(round(60 + 40 * (idm - min_needed) / max(1, min_needed * 0.5)))
        else:
            return int(round(max(0, idm / min_needed * 60)))

    @staticmethod
    def _score_soil_ph(spec, soil_ph: float, family: str) -> int:
        # Get pH range: family first, then architecture fallback
        ph_range = _PH_OPTIMAL.get(family)
        if not ph_range:
            ph_range = _PH_OPTIMAL.get(spec.architecture, (5.5, 7.5))

        ph_min, ph_max = ph_range
        mid = (ph_min + ph_max) / 2.0

        if ph_min <= soil_ph <= ph_max:
            half_range = max(0.1, (ph_max - ph_min) / 2.0)
            closeness = 1.0 - abs(soil_ph - mid) / half_range
            return int(round(70 + 30 * max(0, closeness)))
        else:
            if soil_ph < ph_min:
                deficit = ph_min - soil_ph
            else:
                deficit = soil_ph - ph_max
            return int(round(max(0, 70 - deficit * 25)))

    @staticmethod
    def _score_soil_texture(spec, texture: str) -> int:
        arch = spec.architecture
        tex_map = _TEXTURE_SUITABILITY.get(arch, _TEXTURE_SUITABILITY["cereal"])
        return tex_map.get(texture, 60)

    @staticmethod
    def _score_salinity(spec, soil_salinity_ds_m: float) -> int:
        ec_threshold = spec.ec_threshold_ds_m
        ec_slope = spec.ec_slope_pct

        if soil_salinity_ds_m <= ec_threshold * 0.5:
            return 100  # Well below threshold
        elif soil_salinity_ds_m <= ec_threshold:
            # Linear decline toward threshold
            ratio = (soil_salinity_ds_m - ec_threshold * 0.5) / max(0.1, ec_threshold * 0.5)
            return int(round(70 + 30 * (1 - ratio)))
        else:
            # Above threshold — Maas-Hoffman yield reduction
            excess = soil_salinity_ds_m - ec_threshold
            yield_reduction_pct = excess * ec_slope
            remaining = max(0, 100 - yield_reduction_pct)
            return int(round(remaining * 0.7))  # Scale to 0-70

    @staticmethod
    def _score_slope(spec, slope_pct: float) -> int:
        max_slope = _SLOPE_MAX.get(spec.architecture, 15.0)
        if slope_pct <= max_slope * 0.5:
            return 100
        elif slope_pct <= max_slope:
            ratio = (slope_pct - max_slope * 0.5) / max(0.1, max_slope * 0.5)
            return int(round(60 + 40 * (1 - ratio)))
        elif slope_pct <= max_slope * 1.5:
            ratio = (slope_pct - max_slope) / max(0.1, max_slope * 0.5)
            return int(round(max(0, 60 * (1 - ratio))))
        else:
            return 0

    @staticmethod
    def _score_frost_heat(
        spec, frost_days: Optional[int], heat_days_above_35: Optional[int],
    ) -> int:
        score = 100

        if frost_days is not None:
            # Penalize frost-sensitive crops
            if spec.optimal_temp_min > 10 and frost_days > 0:
                # Tropical/subtropical crop exposed to frost
                score -= min(60, frost_days * 5)
            elif spec.optimal_temp_min > 5 and frost_days > 30:
                score -= min(40, (frost_days - 30) * 2)

        if heat_days_above_35 is not None:
            # Penalize heat-sensitive crops
            if spec.optimal_temp_max < 30 and heat_days_above_35 > 10:
                score -= min(40, (heat_days_above_35 - 10) * 2)
            elif spec.optimal_temp_max < 35 and heat_days_above_35 > 30:
                score -= min(30, (heat_days_above_35 - 30))

        return max(0, score)

    @staticmethod
    def _classify(score: int) -> str:
        """FAO suitability classification."""
        if score >= 75:
            return "S1"   # Highly suitable
        elif score >= 50:
            return "S2"   # Moderately suitable
        elif score >= 25:
            return "S3"   # Marginally suitable
        else:
            return "N"    # Not suitable
