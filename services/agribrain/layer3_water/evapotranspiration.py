"""
Layer 3.1: Evapotranspiration Engine
Computes Reference ET (ET0) and Crop ET (ETc).

Methods:
  - FAO-56 Penman-Monteith (primary — uses L0 et0 module)
  - Hargreaves-Samani (fallback when wind/RH missing)
  - Dynamic Kc from NDVI (canopy cover proxy)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple, Mapping
import math

# Re-export the canonical ET₀ calculators from L0
from layer0.environment.weather.et0 import (
    penman_monteith_et0,
    hargreaves_et0 as _hargreaves_scalar,
    select_et0 as _select_et0_scalar,
    wind_speed_at_2m,
    _extraterrestrial_radiation,
    _saturation_vapour_pressure,
)


@dataclass(frozen=True)
class KcPosteriorResult:
    """Crop-coefficient distribution bound to Layer 2 semantic receipts."""

    mean: pd.Series
    standard_deviation: pd.Series
    lower: pd.Series
    upper: pd.Series
    crop_posterior_hash: str
    phenology_posterior_hash: str
    crop_evidence_class: str
    phenology_evidence_class: str
    production_eligible: bool
    hypotheses: Tuple[str, ...]


class ETEngine:

    # ================================================================
    # SCI-7: Crop-Specific Kc Table (FAO-56 Table 12)
    # ================================================================
    # Source: Allen et al. (1998), FAO Irrigation and Drainage Paper 56,
    # Table 12 — Single crop coefficients Kc.
    #
    # Each crop has {initial, mid, end} Kc values.
    # The "initial" stage covers planting→~10% ground cover.
    # The "mid" stage covers effective full cover→start of maturity.
    # The "end" stage covers maturity→harvest/full senescence.
    #
    # These values assume sub-humid climate (RH_min ≈ 45%, u2 ≈ 2 m/s).
    # For arid conditions (MENA), Kc_mid is adjusted upward by
    # _advective_kc_adjustment() per FAO-56 Eq. 62.
    _KC_BY_CROP = {
        # Cereals (small grains)
        "wheat":    {"initial": 0.30, "mid": 1.15, "end": 0.25},
        "barley":   {"initial": 0.30, "mid": 1.15, "end": 0.25},
        # Cereals (tall grains)
        "maize":    {"initial": 0.30, "mid": 1.20, "end": 0.60},
        "corn":     {"initial": 0.30, "mid": 1.20, "end": 0.60},
        "rice":     {"initial": 1.05, "mid": 1.20, "end": 0.90},
        "sorghum":  {"initial": 0.30, "mid": 1.10, "end": 0.55},
        # Legumes
        "soybean":  {"initial": 0.40, "mid": 1.15, "end": 0.50},
        # Fibre
        "cotton":   {"initial": 0.35, "mid": 1.15, "end": 0.70},
        # Vegetables
        "tomato":   {"initial": 0.60, "mid": 1.15, "end": 0.80},
        "potato":   {"initial": 0.50, "mid": 1.15, "end": 0.75},
        "onion":    {"initial": 0.70, "mid": 1.05, "end": 0.75},
        # Tree crops (perennial)
        "citrus":   {"initial": 0.65, "mid": 0.65, "end": 0.65},
        "olive":    {"initial": 0.65, "mid": 0.70, "end": 0.70},
        "grape":    {"initial": 0.30, "mid": 0.85, "end": 0.45},
        "date_palm": {"initial": 0.90, "mid": 0.95, "end": 0.95},
        "almond":   {"initial": 0.40, "mid": 1.00, "end": 0.65},
        # Default (generic cereal, used as fallback)
        "_default": {"initial": 0.30, "mid": 1.15, "end": 0.40},
    }

    def __init__(self):
        # Legacy compatibility — generic Kc used when crop_type is unknown
        self.kc_defaults = self._KC_BY_CROP["_default"].copy()

    @classmethod
    def get_kc_for_crop(cls, crop_type: str, stage: str) -> float:
        """Get crop-specific Kc value by crop type and phenological stage.

        Args:
            crop_type: Crop name (case-insensitive). Falls back to generic cereal.
            stage: Growth stage label (initial/mid/end or aliases).

        Returns:
            Kc value from FAO-56 Table 12.
        """
        crop_key = crop_type.lower().strip() if crop_type else "_default"
        kc_table = cls._KC_BY_CROP.get(crop_key, cls._KC_BY_CROP["_default"])

        # Map phenology stage aliases to Kc stages
        stage_lower = stage.lower() if stage else "mid"
        if stage_lower in ("bare_soil", "emergence", "initial", "planting"):
            return kc_table["initial"]
        elif stage_lower in ("maturity", "senescence", "harvested", "end", "harvest"):
            return kc_table["end"]
        else:
            # vegetative, reproductive, mid, unknown → mid-season Kc
            return kc_table["mid"]

    @staticmethod
    def _advective_kc_adjustment(
        kc_mid: float, rh_min: float, u2: float, crop_height_m: float = 0.5
    ) -> float:
        """SCI-9: FAO-56 Eq. 62 — Kc adjustment for non-standard conditions.

        In arid zones (MENA), low RH and high wind increase crop ET demand
        beyond the standard sub-humid Kc values from Table 12.

        Adjustment: Kc_adj = Kc + [0.04·(u2−2) − 0.004·(RH_min−45)] × (h/3)^0.3

        Args:
            kc_mid: Base Kc_mid from FAO-56 Table 12
            rh_min: Minimum relative humidity (%). <45% triggers upward adjustment.
            u2: Wind speed at 2m (m/s). >2 m/s triggers upward adjustment.
            crop_height_m: Mean crop height (m). Taller crops = larger adjustment.

        Returns:
            Adjusted Kc value (clamped to [kc_mid, kc_mid + 0.20])
        """
        if rh_min >= 45.0 and u2 <= 2.0:
            return kc_mid  # Standard sub-humid conditions — no adjustment

        h_factor = max(0.1, min(crop_height_m, 10.0))
        adjustment = (
            0.04 * (u2 - 2.0) - 0.004 * (rh_min - 45.0)
        ) * (h_factor / 3.0) ** 0.3

        # Only allow upward adjustment (arid conditions increase ET demand)
        # Capped at +0.20 to prevent extreme values
        return kc_mid + max(0.0, min(0.20, adjustment))

    # ================================================================
    # Penman-Monteith (vectorized over a DataFrame)
    # ================================================================

    def calculate_et0_penman_monteith(
        self,
        t_min: pd.Series,
        t_max: pd.Series,
        rh_mean: pd.Series,
        wind_2m: pd.Series,
        lat_deg: float,
        dates: pd.DatetimeIndex,
        rs: Optional[pd.Series] = None,
        elevation_m: float = 100.0,
    ) -> Tuple[pd.Series, pd.Series]:
        """FAO-56 Penman-Monteith ET₀ — vectorized over a daily DataFrame.

        Args:
            t_min:        Daily minimum temperature (°C)
            t_max:        Daily maximum temperature (°C)
            rh_mean:      Mean relative humidity (%)
            wind_2m:      Wind speed at 2 m (m/s)
            lat_deg:      Latitude in degrees
            dates:        DatetimeIndex of the series
            rs:           Incoming shortwave radiation (MJ/m²/day).
                          If None, estimated from temperature range.
            elevation_m:  Station elevation (m)

        Returns:
            (et0_series, method_series) — ET₀ mm/day and method used per day
        """
        doy = dates.dayofyear
        T = (t_min + t_max) / 2.0

        # Atmospheric pressure (Eq. 7)
        P = 101.3 * ((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26
        gamma = 0.000665 * P  # Psychrometric constant

        # Saturation vapour pressure
        es_min = 0.6108 * np.exp((17.27 * t_min) / (t_min + 237.3))
        es_max = 0.6108 * np.exp((17.27 * t_max) / (t_max + 237.3))
        es = (es_min + es_max) / 2.0

        # Actual vapour pressure
        ea = es * (rh_mean / 100.0)

        # Slope of saturation curve
        es_T = 0.6108 * np.exp((17.27 * T) / (T + 237.3))
        delta = (4098.0 * es_T) / ((T + 237.3) ** 2)

        # Extraterrestrial radiation Ra
        lat_rad = math.radians(lat_deg)
        dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
        dec = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
        ws = np.arccos(
            np.clip(-np.tan(lat_rad) * np.tan(dec), -1.0, 1.0)
        )
        Ra = (24 * 60 / np.pi) * 0.0820 * dr * (
            ws * np.sin(lat_rad) * np.sin(dec) +
            np.cos(lat_rad) * np.cos(dec) * np.sin(ws)
        )
        Ra = Ra.clip(lower=0.0)

        # Incoming solar radiation Rs
        if rs is not None:
            Rs = rs.clip(lower=0.0)
            method = pd.Series("penman_monteith", index=dates)
        else:
            # Hargreaves radiation estimate (Eq. 50)
            kRs = 0.16
            Rs = kRs * np.sqrt((t_max - t_min).clip(lower=0.0)) * Ra
            method = pd.Series("penman_monteith_reduced", index=dates)

        # Clear-sky radiation Rso (Eq. 37)
        Rso = (0.75 + 2e-5 * elevation_m) * Ra
        Rso = Rso.clip(lower=0.001)

        # Net shortwave Rns (albedo = 0.23)
        Rns = 0.77 * Rs

        # Net longwave Rnl (Eq. 39)
        sigma = 4.903e-9
        Tmin_K4 = (t_min + 273.16) ** 4
        Tmax_K4 = (t_max + 273.16) ** 4

        Rs_Rso = (Rs / Rso).clip(0.25, 1.0)

        Rnl = sigma * ((Tmin_K4 + Tmax_K4) / 2.0) * \
            (0.34 - 0.14 * np.sqrt(ea.clip(lower=0.0))) * \
            (1.35 * Rs_Rso - 0.35)

        Rn = Rns - Rnl
        G = 0.0  # Negligible for daily steps

        # FAO-56 PM equation (Eq. 6)
        numerator = (0.408 * delta * (Rn - G) +
                     gamma * (900.0 / (T + 273.0)) * wind_2m * (es - ea))
        denominator = delta + gamma * (1.0 + 0.34 * wind_2m)

        et0 = (numerator / denominator).clip(lower=0.0).round(2)
        return et0, method

    # ================================================================
    # Hargreaves-Samani (vectorized)
    # ================================================================

    def calculate_et0_hargreaves(
        self,
        t_min: pd.Series,
        t_max: pd.Series,
        lat_deg: float,
        dates: pd.DatetimeIndex,
    ) -> pd.Series:
        """Hargreaves-Samani Method (Temperature + Lat only).

        Good fallback when Radiation/Wind/Humidity are missing.
        Formula: 0.0023 × Ra × (Tmean + 17.8) × √(Tmax − Tmin)
        """
        ra = self._calculate_ra(lat_deg, dates)
        t_mean = (t_max + t_min) / 2.0
        tr = (t_max - t_min).clip(lower=0)
        et0 = 0.0023 * ra * (t_mean + 17.8) * np.sqrt(tr)
        return et0

    def _calculate_ra(self, lat_deg: float, dates: pd.DatetimeIndex) -> pd.Series:
        """Extraterrestrial Radiation (Ra) [mm/day equivalent]."""
        lat_rad = math.radians(lat_deg)
        doy = dates.dayofyear

        dr = 1 + 0.033 * np.cos(2 * math.pi * doy / 365)
        dec = 0.409 * np.sin(2 * math.pi * doy / 365 - 1.39)
        ws = np.arccos(
            np.clip(-np.tan(lat_rad) * np.tan(dec), -1.0, 1.0)
        )

        # Ra in MJ/m²/day, then × 0.408 to convert to mm
        ra_mj = (24 * 60 / math.pi) * 0.0820 * dr * (
            ws * np.sin(lat_rad) * np.sin(dec) +
            np.cos(lat_rad) * np.cos(dec) * np.sin(ws)
        )
        return pd.Series(ra_mj * 0.408, index=dates)

    # ================================================================
    # Smart ET₀ Selection (auto-detects best method from available data)
    # ================================================================

    def calculate_et0_auto(
        self,
        df: pd.DataFrame,
        lat_deg: float,
        dates: pd.DatetimeIndex,
        elevation_m: float = 100.0,
    ) -> Tuple[pd.Series, pd.Series]:
        """Automatically select the best ET₀ method based on available columns.

        Expected columns (all optional, more = better):
            t_min, t_max          — Required (minimum)
            rh_mean               — Enables Penman-Monteith
            wind_speed_2m         — Enables full PM (estimated if missing)
            shortwave_radiation   — Enables full PM (estimated if missing)

        Returns:
            (et0_series, method_series)
        """
        t_min = df["t_min"]
        t_max = df["t_max"]
        has_rh = "rh_mean" in df.columns and df["rh_mean"].notna().any()
        has_wind = "wind_speed_2m" in df.columns and df["wind_speed_2m"].notna().any()
        has_rs = "shortwave_radiation" in df.columns and df["shortwave_radiation"].notna().any()

        if has_rh:
            rh = df["rh_mean"]
            wind = df["wind_speed_2m"] if has_wind else pd.Series(2.0, index=dates)
            rs = df["shortwave_radiation"] if has_rs else None
            return self.calculate_et0_penman_monteith(
                t_min, t_max, rh, wind, lat_deg, dates,
                rs=rs, elevation_m=elevation_m,
            )
        else:
            et0 = self.calculate_et0_hargreaves(t_min, t_max, lat_deg, dates)
            method = pd.Series("hargreaves", index=dates)
            return et0, method

    # ================================================================
    # Crop Coefficient Kc (NDVI-dynamic, Crop-Specific)
    # ================================================================

    def calculate_dynamic_kc(
        self,
        ndvi_series: pd.Series,
        stage_label: str = "vegetative",
        crop_type: str = "",
        rh_min: float = 45.0,
        wind_2m: float = 2.0,
        crop_height_m: float = 0.5,
    ) -> pd.Series:
        """Adjust Kc based on NDVI (Canopy Cover Proxy) and crop type.

        SCI-7: Now uses crop-specific Kc from FAO-56 Table 12.
        SCI-8: Uses Johnson & Trout (2012) Fc calibration:
               Fc = 1.26·NDVI − 0.18 (improved from generic 1.2·NDVI − 0.2)
        SCI-9: Applies FAO-56 Eq. 62 advective adjustment for arid zones.

        FAO-56 approach: Kc = Kc_min + (Kc_full − Kc_min) × Fc

        Args:
            ndvi_series: Vegetation index time series
            stage_label: Current growth stage (initial/vegetative/mid/maturity/end)
            crop_type: Crop name for crop-specific Kc lookup
            rh_min: Minimum relative humidity (%). Triggers arid adjustment <45%.
            wind_2m: Wind speed at 2m (m/s). Triggers arid adjustment >2 m/s.
            crop_height_m: Mean crop height (m) for advective correction.

        Returns:
            Dynamic Kc time series.
        """
        # SCI-7: Get crop-specific base Kc
        base_kc = self.get_kc_for_crop(crop_type, stage_label)

        # SCI-9: Advective adjustment for arid zones (FAO-56 Eq. 62)
        # Only applies to mid-season Kc (not initial or end)
        stage_lower = stage_label.lower() if stage_label else "mid"
        is_mid_stage = stage_lower not in (
            "bare_soil", "emergence", "initial", "planting",
            "maturity", "senescence", "harvested", "end", "harvest",
        )
        if is_mid_stage:
            base_kc = self._advective_kc_adjustment(
                base_kc, rh_min, wind_2m, crop_height_m
            )

        kc_min = 0.15  # Bare soil evaporation

        # SCI-8: Johnson & Trout (2012) improved Fc calibration
        # Original: Fc = 1.2·NDVI - 0.2
        # Updated:  Fc = 1.26·NDVI - 0.18  (better fit for row crops)
        fc = (1.26 * ndvi_series - 0.18).clip(0, 1)

        kc_dynamic = kc_min + (base_kc - kc_min) * fc
        return kc_dynamic

    def calculate_posterior_kc(
        self,
        ndvi_series: pd.Series,
        semantic_context: Any,
        *,
        rh_min: float = 45.0,
        wind_2m: float = 2.0,
        crop_height_m: float = 0.5,
    ) -> KcPosteriorResult:
        """Propagate canonical crop/stage uncertainty into Kc.

        The caller must pass the resolved Layer 2 crop/phenology context.  A
        declaration is never treated as a species observation.  Group-only
        context is expanded across compatible registry crops; missing context
        uses an intentionally broad generic crop/stage ensemble.
        """
        from crop_database import CROP_REGISTRY

        def norm(raw: Any) -> Dict[str, float]:
            if not isinstance(raw, Mapping):
                return {}
            clean = {}
            for key, value in raw.items():
                try:
                    probability = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(probability) and probability > 0.0:
                    clean[str(key).lower()] = probability
            total = sum(clean.values())
            return ({key: value / total for key, value in clean.items()}
                    if total > 0.0 else {})

        crop_mix = norm(getattr(semantic_context, "crop_mixture", {}))
        stage_mix = norm(getattr(semantic_context, "stage_posterior", {}))
        species_allowed = bool(
            getattr(semantic_context, "species_specific_allowed", False)
        )
        stage_allowed = bool(
            getattr(semantic_context, "stage_specific_allowed", False)
        )

        if species_allowed:
            selected = str(getattr(semantic_context, "selected_crop", "") or "").lower()
            if not crop_mix and selected:
                crop_mix = {selected: 1.0}
            crop_evidence = "species_posterior"
        elif str(getattr(semantic_context, "crop_resolution", "")) == "group_only":
            expanded: Dict[str, float] = {}
            for group, group_weight in crop_mix.items():
                compatible = [
                    code for code, spec in CROP_REGISTRY.items()
                    if str(getattr(spec, "architecture", "")).lower() == group
                ]
                for code in compatible:
                    expanded[code] = expanded.get(code, 0.0) + group_weight / max(1, len(compatible))
            crop_mix = norm(expanded)
            crop_evidence = "group_mixture"
        else:
            # Broad, bounded prior across supported agronomic architectures.
            representatives: Dict[str, str] = {}
            for code, spec in CROP_REGISTRY.items():
                representatives.setdefault(str(spec.architecture).lower(), code)
            crop_mix = norm({code: 1.0 for code in representatives.values()})
            crop_evidence = "generic_bounded_prior"

        if stage_allowed:
            if not stage_mix:
                stage = str(getattr(semantic_context, "phenology_stage", "UNKNOWN"))
                stage_mix = {stage.lower(): 1.0}
            phenology_evidence = "canonical_stage_posterior"
        else:
            stage_mix = {
                "initial": 0.20,
                "vegetative": 0.30,
                "reproductive": 0.30,
                "maturity": 0.20,
            }
            phenology_evidence = "generic_stage_prior"

        fc = (1.26 * ndvi_series.astype(float) - 0.18).clip(0, 1)
        values: List[pd.Series] = []
        weights: List[float] = []
        hypotheses: List[str] = []
        for crop_code, crop_weight in crop_mix.items():
            spec = CROP_REGISTRY.get(crop_code)
            if spec is None:
                continue
            for stage, stage_weight in stage_mix.items():
                stage_key = stage.lower()
                if stage_key in {"bare_soil", "emergence", "initial", "planting"}:
                    base = float(spec.kc_init)
                elif stage_key in {"maturity", "senescence", "harvested", "end", "harvest"}:
                    base = float(spec.kc_end)
                else:
                    base = self._advective_kc_adjustment(
                        float(spec.kc_mid), rh_min, wind_2m, crop_height_m,
                    )
                values.append(0.15 + (base - 0.15) * fc)
                weights.append(crop_weight * stage_weight)
                hypotheses.append(f"{crop_code}:{stage_key}")

        if not values:
            values = [pd.Series(0.85, index=ndvi_series.index, dtype=float)]
            weights = [1.0]
            hypotheses = ["generic:unknown"]
        total_weight = sum(weights) or 1.0
        normalised = np.asarray(weights, dtype=float) / total_weight
        matrix = np.vstack([series.to_numpy(dtype=float) for series in values])
        mean_values = np.average(matrix, axis=0, weights=normalised)
        variance = np.average((matrix - mean_values) ** 2, axis=0, weights=normalised)
        mean = pd.Series(mean_values, index=ndvi_series.index)
        std = pd.Series(np.sqrt(np.maximum(variance, 0.0)), index=ndvi_series.index)
        lower = pd.Series(np.min(matrix, axis=0), index=ndvi_series.index)
        upper = pd.Series(np.max(matrix, axis=0), index=ndvi_series.index)

        return KcPosteriorResult(
            mean=mean,
            standard_deviation=std,
            lower=lower,
            upper=upper,
            crop_posterior_hash=str(getattr(semantic_context, "crop_posterior_hash", "") or ""),
            phenology_posterior_hash=str(getattr(semantic_context, "phenology_posterior_hash", "") or ""),
            crop_evidence_class=crop_evidence,
            phenology_evidence_class=phenology_evidence,
            production_eligible=species_allowed and stage_allowed,
            hypotheses=tuple(hypotheses),
        )

    # ================================================================
    # Crop Evapotranspiration (ETc)
    # ================================================================

    def compute_etc(self, et0: pd.Series, kc: pd.Series) -> pd.Series:
        """ETc = ET₀ × Kc (FAO-56 Eq. 58)."""
        return et0 * kc


# Singleton
et_engine = ETEngine()


def compute_et0_penman_monteith(
    temp_mean: float,
    humidity: float,
    wind_speed: float,
    solar_rad: float,
    lat: float
) -> float:
    """Wrapper function for FAO-56 Penman-Monteith ET0 computation for test compatibility."""
    import datetime
    doy = datetime.datetime.now().timetuple().tm_yday
    return penman_monteith_et0(
        temp_min=temp_mean - 5.0,
        temp_max=temp_mean + 5.0,
        temp_mean=temp_mean,
        relative_humidity_mean=humidity,
        wind_speed_2m=wind_speed,
        shortwave_radiation_mj=solar_rad,
        latitude_deg=lat,
        day_of_year=doy
    )

