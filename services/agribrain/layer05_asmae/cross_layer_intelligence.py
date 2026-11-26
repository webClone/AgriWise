"""ASMAE Cross-Layer Scientific Intelligence Bridge (Layers 2-8 <-> ASMAE).

Executes AgriBrain's real canonical domain engines across Layers 2-8 both in
operational orchestration (`orchestrator_v2`) and in chronological historical
reconstruction (`HistoricalStateReconstructor`):

  - Layer 2 (Vegetation & Retrieval Uncertainty): Phenology development rates,
    `TemporalAnomalyEngine` (EWMA changepoint / spectral z-scores),
    `NDMIWaterStressModel` & `TemperatureThermalStressModel` (Jacobian sigmas).
  - Layer 3 (Canonical Multi-Layer Hydrology): `PenmanMonteithET0`, `DualKcEngine`
    (transpiration vs evaporation partitioning), `SoilProfileDatabase`,
    `RootZoneAvailabilityEngine`, `LayeredWaterBalanceEngine` (5-layer soil cascade),
    and `WaterLimitationEngine`.
  - Layer 4 (Mechanistic Nutrient Cycle & Salinity): `SoilRespirationEngine`
    (Lloyd-Taylor/Moyano mineralization), `CropDemandUptakeEngine`,
    `PhotosynthesisNUEEngine` (NNI/dilution curve), `EnvironmentalLossEngine`
    (Burns/Sommer/DayCent losses), `NitrogenDeficiencyEngine`, `SalinityEngine`.
  - Layer 5 (Canopy Biophysical Microclimate & Bayesian Pathology):
    `BiophysicalCanopyEnergyBalanceSolver` (T_leaf vs T_dew), `compute_dynamic_priors`,
    `build_weather_pressure`, and `BioThreatInferenceEngine` (9-threat Bayesian log-odds).
  - Layer 6 (Yield Impact, Economics & Value of Information):
    `YieldForecastEngine`, `ProfitabilityCalculator`, and quantitative VoI ranking.
  - Layer 7 (Shock, Composite Risk & Cross-Layer Conflict Trust):
    `ClimateShockEngine`, `RiskCompositeEngine`, and `TrustMonitor`.
  - Layer 8 (Constraints ONLY — NEVER physical ground truth):
    `PhenologyDosingEngine`, `SprayDriftGateEngine`, `FrostSprinklingEngine`,
    `CropCoolingEngine`, `TillageCompactionEngine`, `VolatilizationInhibitorEngine`,
    and `SalinityLeachingEngine` evaluated strictly for safety/feasibility constraints.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

try:
    from services.agribrain.crop_database import get_crop
    from services.agribrain.layer2_uncertainty.retrieval_models import (
        NDMIWaterStressModel,
        SalinityECModel,
        TemperatureThermalStressModel,
    )
    from services.agribrain.layer2_veg_int.anomaly_engine import TemporalAnomalyEngine
    from services.agribrain.layer2_veg_int.phenology_engine import compute_development_rate
    from services.agribrain.layer3_water.contracts.atmospheric_state import (
        RadiationSourceType,
        TemperatureSourceType,
        WindSourceType,
    )
    from services.agribrain.layer3_water.contracts.water_state import (
        PotentialWaterFlux,
        RootZoneWaterState,
        SoilWaterState,
    )
    from services.agribrain.layer3_water.et.dual_kc import DualKcEngine
    from services.agribrain.layer3_water.et.penman_monteith import PenmanMonteithET0
    from services.agribrain.layer3_water.limitation.water_limitation_engine import (
        WaterLimitationEngine,
    )
    from services.agribrain.layer3_water.root_zone.availability import (
        RootZoneAvailabilityEngine,
    )
    from services.agribrain.layer3_water.soil.layered_water_balance import (
        LayeredWaterBalanceEngine,
    )
    from services.agribrain.layer3_water.soil.soil_profile import SoilProfileDatabase
    from services.agribrain.layer4_nutrients.crop_demand.engine import (
        CropDemandUptakeEngine,
    )
    from services.agribrain.layer4_nutrients.environmental_losses.engine import (
        EnvironmentalLossEngine,
    )
    from services.agribrain.layer4_nutrients.nitrogen_deficiency import (
        NitrogenDeficiencyEngine,
    )
    from services.agribrain.layer4_nutrients.photosynthesis_nue.engine import (
        PhotosynthesisNUEEngine,
    )
    from services.agribrain.layer4_nutrients.salinity.engine import SalinityEngine
    from services.agribrain.layer4_nutrients.soil_respiration.engine import (
        SoilRespirationEngine,
    )
    from services.agribrain.layer5_bio.engines.biophysical_engine import (
        BiophysicalCanopyEnergyBalanceSolver,
    )
    from services.agribrain.layer5_bio.engines.inference import BioThreatInferenceEngine
    from services.agribrain.layer5_bio.engines.weather_pressure import (
        build_weather_pressure,
    )
    from services.agribrain.layer5_bio.knowledge.dynamic_priors import (
        compute_dynamic_priors,
    )
    from services.agribrain.layer6_yield.profitability import ProfitabilityCalculator
    from services.agribrain.layer6_yield.yield_forecast import YieldForecastEngine
    from services.agribrain.layer7_risk.climate_shock import ClimateShockEngine
    from services.agribrain.layer7_risk.risk_composite import RiskCompositeEngine
    from services.agribrain.layer7_risk.trust_monitor import TrustMonitor
    from services.agribrain.layer8_prescriptive.engines.crop_cooling import (
        CropCoolingEngine,
    )
    from services.agribrain.layer8_prescriptive.engines.frost_sprinkling import (
        FrostSprinklingEngine,
    )
    from services.agribrain.layer8_prescriptive.engines.phenology_dosing import (
        PhenologyDosingEngine,
    )
    from services.agribrain.layer8_prescriptive.engines.salinity_leaching import (
        SalinityLeachingEngine,
    )
    from services.agribrain.layer8_prescriptive.engines.spray_drift_gate import (
        SprayDriftGateEngine,
    )
    from services.agribrain.layer8_prescriptive.engines.tillage_compaction import (
        TillageCompactionEngine,
    )
    from services.agribrain.layer8_prescriptive.engines.volatilization_inhibitor import (
        VolatilizationInhibitorEngine,
    )
    from services.agribrain.layer8_prescriptive.schema import (
        ActionCard,
        ActionType,
        ConfidenceLevel,
        PriorityBreakdown,
        RateRange,
    )
except ImportError:  # pragma: no cover - fallback when services/agribrain is sys.path root
    from crop_database import get_crop
    from layer2_uncertainty.retrieval_models import (
        NDMIWaterStressModel,
        SalinityECModel,
        TemperatureThermalStressModel,
    )
    from layer2_veg_int.anomaly_engine import TemporalAnomalyEngine
    from layer2_veg_int.phenology_engine import compute_development_rate
    from layer3_water.contracts.atmospheric_state import (
        RadiationSourceType,
        TemperatureSourceType,
        WindSourceType,
    )
    from layer3_water.contracts.water_state import (
        PotentialWaterFlux,
        RootZoneWaterState,
        SoilWaterState,
    )
    from layer3_water.et.dual_kc import DualKcEngine
    from layer3_water.et.penman_monteith import PenmanMonteithET0
    from layer3_water.limitation.water_limitation_engine import WaterLimitationEngine
    from layer3_water.root_zone.availability import RootZoneAvailabilityEngine
    from layer3_water.soil.layered_water_balance import LayeredWaterBalanceEngine
    from layer3_water.soil.soil_profile import SoilProfileDatabase
    from layer4_nutrients.crop_demand.engine import CropDemandUptakeEngine
    from layer4_nutrients.environmental_losses.engine import EnvironmentalLossEngine
    from layer4_nutrients.nitrogen_deficiency import NitrogenDeficiencyEngine
    from layer4_nutrients.photosynthesis_nue.engine import PhotosynthesisNUEEngine
    from layer4_nutrients.salinity.engine import SalinityEngine
    from layer4_nutrients.soil_respiration.engine import SoilRespirationEngine
    from layer5_bio.engines.biophysical_engine import BiophysicalCanopyEnergyBalanceSolver
    from layer5_bio.engines.inference import BioThreatInferenceEngine
    from layer5_bio.engines.weather_pressure import build_weather_pressure
    from layer5_bio.knowledge.dynamic_priors import compute_dynamic_priors
    from layer6_yield.profitability import ProfitabilityCalculator
    from layer6_yield.yield_forecast import YieldForecastEngine
    from layer7_risk.climate_shock import ClimateShockEngine
    from layer7_risk.risk_composite import RiskCompositeEngine
    from layer7_risk.trust_monitor import TrustMonitor
    from layer8_prescriptive.engines.crop_cooling import CropCoolingEngine
    from layer8_prescriptive.engines.frost_sprinkling import FrostSprinklingEngine
    from layer8_prescriptive.engines.phenology_dosing import PhenologyDosingEngine
    from layer8_prescriptive.engines.salinity_leaching import SalinityLeachingEngine
    from layer8_prescriptive.engines.spray_drift_gate import SprayDriftGateEngine
    from layer8_prescriptive.engines.tillage_compaction import TillageCompactionEngine
    from layer8_prescriptive.engines.volatilization_inhibitor import (
        VolatilizationInhibitorEngine,
    )
    from layer8_prescriptive.schema import (
        ActionCard,
        ActionType,
        ConfidenceLevel,
        PriorityBreakdown,
        RateRange,
    )


CROSS_LAYER_CONTRACT_VERSION = "asmae_cross_layer_v2"


def _finite(val: Any, default: Optional[float] = None) -> Optional[float]:
    if isinstance(val, bool) or val is None:
        return default
    try:
        out = float(val)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _extract_day_weather(w_day: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    if not isinstance(w_day, dict):
        return {
            "rain": None,
            "et0": None,
            "t_max": None,
            "t_min": None,
            "t_mean": None,
            "rh": None,
            "wind": None,
            "rad": None,
        }
    rain = _finite(
        w_day.get("precipitation_mm")
        if w_day.get("precipitation_mm") is not None
        else w_day.get("precipitation")
    )
    et0 = _finite(w_day.get("et0_mm") if w_day.get("et0_mm") is not None else w_day.get("et0"))
    t_max = _finite(
        w_day.get("temp_max_c") if w_day.get("temp_max_c") is not None else w_day.get("temp_max")
    )
    t_min = _finite(
        w_day.get("temp_min_c") if w_day.get("temp_min_c") is not None else w_day.get("temp_min")
    )
    t_mean = _finite(
        w_day.get("temp_mean_c") if w_day.get("temp_mean_c") is not None else w_day.get("temp_mean")
    )
    if t_mean is None and t_max is not None and t_min is not None:
        t_mean = 0.5 * (t_max + t_min)
    rh = _finite(
        w_day.get("humidity_mean_pct")
        if w_day.get("humidity_mean_pct") is not None
        else w_day.get("humidity")
    )
    wind = _finite(
        w_day.get("wind_speed")
        if w_day.get("wind_speed") is not None
        else w_day.get("wind_speed_max")
    )
    rad = _finite(
        w_day.get("solar_radiation_mj_m2")
        if w_day.get("solar_radiation_mj_m2") is not None
        else w_day.get("radiation")
    )
    return {
        "rain": rain,
        "et0": et0,
        "t_max": t_max,
        "t_min": t_min,
        "t_mean": t_mean,
        "rh": rh,
        "wind": wind,
        "rad": rad,
    }


def _safe_crop_profile(crop_type: str) -> Any:
    from dataclasses import replace as dc_replace
    from crop_database import get_crop_with_provenance
    raw = str(crop_type or "").strip().lower()
    if raw and raw not in {"unknown", "unverified", "fallow"}:
        try:
            spec, _, used_default = get_crop_with_provenance(raw)
            if not used_default:
                return spec
        except Exception:
            pass
    # Neutral generic prior when crop identity is unknown/fallow instead of inheriting wheat/citrus
    base = get_crop("wheat")
    try:
        return dc_replace(
            base,
            code=raw or "unknown",
            name="Unverified / Mixed Generic",
            architecture="mixed",
            gdd_base_temp=6.5,
            kc_init=0.35 if raw == "fallow" else 0.45,
            kc_mid=0.30 if raw == "fallow" else 0.82,
            kc_end=0.25 if raw == "fallow" else 0.50,
            max_root_depth_cm=35.0 if raw == "fallow" else 75.0,
        )
    except Exception:
        return base


def _stage_for_progress(progress: float, architecture: str) -> Tuple[str, float]:
    p = max(0.0, min(1.0, float(progress)))
    if architecture == "perennial":
        if p < 0.18:
            return "emergence", 0.72
        if p < 0.45:
            return "vegetative", 0.85
        if p < 0.72:
            return "reproductive", 0.80
        if p < 0.88:
            return "maturation", 0.72
        return "senescence", 0.65
    if p < 0.15:
        return "emergence", 0.45
    if p < 0.48:
        return "vegetative", 0.85
    if p < 0.78:
        return "reproductive", 1.10
    return "senescence", 0.60


@dataclass
class CrossLayerChronoState:
    """Deterministic multi-layer chronological specialist state stored across checkpoints."""

    gdd_cum: float = 0.0
    cycle_year: Optional[int] = None
    soil_type: str = "loam"
    root_depth_m: float = 1.2
    layer_depths_cm: List[float] = field(default_factory=list)
    layer_theta_profile: List[float] = field(default_factory=list)
    days_since_wetting: int = 0
    surface_evap_storage_mm: float = 6.0
    last_et0_mm: float = 3.0
    last_et0_sigma_mm: float = 0.08
    last_vpd_kpa: float = 1.0
    last_kcb: float = 0.7
    last_ke: float = 0.2
    last_t_act_mm: float = 2.0
    last_e_act_mm: float = 0.5
    last_deep_drainage_mm: float = 0.0
    last_runoff_mm: float = 0.0
    cumulative_water_stress_days: float = 0.0
    cumulative_heat_stress_days: float = 0.0
    cumulative_drainage_mm: float = 0.0
    recent_weather_window: List[Dict[str, Any]] = field(default_factory=list)
    recent_ndvi_window: List[Tuple[str, float, float]] = field(default_factory=list)  # (date, obs_ndvi, exp_ndvi)
    recent_ndmi_window: List[float] = field(default_factory=list)
    last_day: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gdd_cum": round(float(self.gdd_cum), 4),
            "cycle_year": self.cycle_year,
            "soil_type": self.soil_type,
            "root_depth_m": round(float(self.root_depth_m), 3),
            "layer_depths_cm": [round(float(x), 2) for x in self.layer_depths_cm],
            "layer_theta_profile": [round(float(x), 6) for x in self.layer_theta_profile],
            "days_since_wetting": int(self.days_since_wetting),
            "surface_evap_storage_mm": round(float(self.surface_evap_storage_mm), 4),
            "last_et0_mm": round(float(self.last_et0_mm), 4),
            "last_et0_sigma_mm": round(float(self.last_et0_sigma_mm), 4),
            "last_vpd_kpa": round(float(self.last_vpd_kpa), 4),
            "last_kcb": round(float(self.last_kcb), 4),
            "last_ke": round(float(self.last_ke), 4),
            "last_t_act_mm": round(float(self.last_t_act_mm), 4),
            "last_e_act_mm": round(float(self.last_e_act_mm), 4),
            "last_deep_drainage_mm": round(float(self.last_deep_drainage_mm), 4),
            "last_runoff_mm": round(float(self.last_runoff_mm), 4),
            "cumulative_water_stress_days": round(float(self.cumulative_water_stress_days), 4),
            "cumulative_heat_stress_days": round(float(self.cumulative_heat_stress_days), 4),
            "cumulative_drainage_mm": round(float(self.cumulative_drainage_mm), 3),
            "recent_weather_window": list(self.recent_weather_window[-7:]),
            "recent_ndvi_window": [[str(d), round(float(o), 5), round(float(e), 5)] for d, o, e in self.recent_ndvi_window[-10:]],
            "recent_ndmi_window": [round(float(x), 5) for x in self.recent_ndmi_window[-8:]],
            "last_day": self.last_day,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "CrossLayerChronoState":
        if not isinstance(data, dict):
            return cls()
        allowed = set(cls.__dataclass_fields__)
        clean = {k: v for k, v in data.items() if k in allowed}
        if "recent_ndvi_window" in clean:
            clean["recent_ndvi_window"] = [(str(x[0]), float(x[1]), float(x[2])) for x in (clean["recent_ndvi_window"] or [])]
        return cls(**clean)


class CrossLayerSpecialistBridge:
    """Executes real Layers 2-8 specialist engines before and after ASMAE assimilation."""

    def __init__(self) -> None:
        self._l2_anomaly = TemporalAnomalyEngine(z_threshold=1.8, persistence_days=2)
        self._n_def = NitrogenDeficiencyEngine()
        self._demand = CropDemandUptakeEngine()
        self._photo_nue = PhotosynthesisNUEEngine()
        self._env_loss = EnvironmentalLossEngine()
        self._salinity = SalinityEngine()
        self._soil_resp = SoilRespirationEngine()
        self._bio_energy = BiophysicalCanopyEnergyBalanceSolver()
        self._bio_inf = BioThreatInferenceEngine()
        self._yield_engine = YieldForecastEngine()
        self._profit_calc = ProfitabilityCalculator()
        self._climate_shock = ClimateShockEngine()
        self._risk_comp = RiskCompositeEngine()
        self._trust_mon = TrustMonitor()
        self._pheno_dosing = PhenologyDosingEngine()
        self._spray_gate = SprayDriftGateEngine()
        self._frost_gate = FrostSprinklingEngine()
        self._cool_gate = CropCoolingEngine()
        self._till_gate = TillageCompactionEngine()
        self._volat_gate = VolatilizationInhibitorEngine()
        self._sal_gate = SalinityLeachingEngine()

    def initialize_chrono_state(
        self,
        *,
        crop_context: Optional[Dict[str, Any]] = None,
        soil_context: Optional[Dict[str, Any]] = None,
    ) -> CrossLayerChronoState:
        crop = _safe_crop_profile((crop_context or {}).get("crop_type") or (crop_context or {}).get("crop") or "citrus")
        soil_type = str((soil_context or {}).get("soil_type") or "loam").lower()
        base_soil = SoilProfileDatabase.get_canonical_soil_profile(soil_type=soil_type, initial_saturation_fraction=0.65)
        root_depth = _finite(
            (soil_context or {}).get("rooting_depth_m"),
            min(1.5, float(getattr(crop, "max_root_depth_cm", 120) or 120) / 100.0),
        ) or 1.2
        return CrossLayerChronoState(
            soil_type=soil_type,
            root_depth_m=max(0.3, min(1.8, float(root_depth))),
            layer_depths_cm=[float(x) for x in base_soil.layer_depths_cm],
            layer_theta_profile=[float(x) for x in base_soil.theta_profile],
        )

    def _build_soil_state(self, state: CrossLayerChronoState) -> SoilWaterState:
        base_soil = SoilProfileDatabase.get_canonical_soil_profile(
            soil_type=state.soil_type,
            layer_depths_cm=state.layer_depths_cm or None,
            initial_saturation_fraction=0.65,
        )
        if state.layer_theta_profile and len(state.layer_theta_profile) == len(base_soil.theta_profile):
            base_soil = replace(base_soil, theta_profile=[float(x) for x in state.layer_theta_profile])
        return base_soil

    def advance_chrono_state(
        self,
        state: CrossLayerChronoState,
        *,
        start_time: Optional[datetime],
        end_time: datetime,
        weather_daily_series: Optional[Dict[str, Dict[str, Any]]] = None,
        crop_context: Optional[Dict[str, Any]] = None,
        soil_context: Optional[Dict[str, Any]] = None,
        management_events: Optional[List[Any]] = None,
        lat: float = 36.5,
    ) -> CrossLayerChronoState:
        """Advance multi-layer hydrological soil column + GDD + Dual-Kc strictly up to end_time."""
        crop_name = str((crop_context or {}).get("crop_type") or (crop_context or {}).get("crop") or "citrus").lower()
        crop = _safe_crop_profile(crop_name)
        t_base = float(getattr(crop, "gdd_base_temp", 10.0) or 10.0)
        t_opt_max = float(getattr(crop, "optimal_temp_max", 35.0) or 35.0)
        architecture = str(getattr(crop, "architecture", "perennial"))
        weather = weather_daily_series or {}

        if not state.layer_theta_profile:
            init_st = self.initialize_chrono_state(crop_context=crop_context, soil_context=soil_context)
            state.soil_type = init_st.soil_type
            state.root_depth_m = init_st.root_depth_m
            state.layer_depths_cm = list(init_st.layer_depths_cm)
            state.layer_theta_profile = list(init_st.layer_theta_profile)

        soil_state = self._build_soil_state(state)

        irrig_by_day: Dict[str, float] = {}
        for ev in management_events or []:
            if isinstance(ev, dict):
                status = str(ev.get("status") or "").lower()
                if status in {"planned", "cancelled", "canceled", "draft", "proposed", "pending"}:
                    continue
                etype = str(ev.get("type") or ev.get("event_type") or "").lower()
                if "irrig" in etype:
                    d_str = str(ev.get("date") or ev.get("timestamp") or "")[:10]
                    amt = _finite(ev.get("amount_mm") or ev.get("quantity") or 0.0, 0.0) or 0.0
                    if d_str:
                        irrig_by_day[d_str] = irrig_by_day.get(d_str, 0.0) + max(0.0, amt)

        start_day = (end_time.date() - timedelta(days=3)) if start_time is None else start_time.date()
        end_day = end_time.date()
        if end_day < start_day:
            start_day = end_day

        cur = start_day
        while cur <= end_day:
            d_str = cur.isoformat()
            if state.last_day == d_str:
                cur += timedelta(days=1)
                continue
            if state.cycle_year != cur.year:
                state.cycle_year = cur.year
                state.gdd_cum = 0.0
                state.cumulative_water_stress_days = 0.0
                state.cumulative_heat_stress_days = 0.0
                state.cumulative_drainage_mm = 0.0

            w = _extract_day_weather(weather.get(d_str))
            has_obs = d_str in weather
            t_mean = w["t_mean"] if w["t_mean"] is not None else 18.0
            t_max = w["t_max"] if w["t_max"] is not None else (t_mean + 5.0)
            t_min = w["t_min"] if w["t_min"] is not None else (t_mean - 5.0)
            rain = w["rain"] if w["rain"] is not None else 0.0
            rh = w["rh"] if w["rh"] is not None else 62.0
            wind_kmh = w["wind"] if w["wind"] is not None else 8.0
            wind_ms = max(0.3, wind_kmh / 3.6)
            solar_mj = w["rad"] if w["rad"] is not None else (16.5 - 5.5 * math.cos(2.0 * math.pi * (cur.timetuple().tm_yday / 365.0)))

            # Real L3 PenmanMonteithET0 with explicit source quality & uncertainty budget
            try:
                et0_res = PenmanMonteithET0.calculate_et0(
                    t_max_c=float(t_max),
                    t_min_c=float(t_min),
                    net_radiation_mj_m2=max(2.0, float(solar_mj)),
                    wind_speed_2m_m_s=wind_ms,
                    rh_mean_pct=float(rh),
                    radiation_source=(
                        RadiationSourceType.PYRANOMETER if w["rad"] is not None else RadiationSourceType.ESTIMATED_DEFAULT
                    ),
                    wind_source=(
                        WindSourceType.ANEMOMETER_2M if w["wind"] is not None else WindSourceType.ESTIMATED_DEFAULT
                    ),
                    temperature_source=(
                        TemperatureSourceType.CALIBRATED_STATION if has_obs else TemperatureSourceType.ESTIMATED_DEFAULT
                    ),
                )
                et0_day = float(w["et0"] if w["et0"] is not None else et0_res.et0_mm_day)
                et0_sig = float(et0_res.uncertainty.total_sigma)
                vpd_kpa = float(et0_res.vapor_pressure_deficit_kpa)
            except Exception:
                et0_day = float(w["et0"] if w["et0"] is not None else 3.2)
                et0_sig = 0.25
                vpd_kpa = 1.0

            # Real L2 Phenology development rate accumulation
            try:
                dev_inc = compute_development_rate(
                    t_mean=t_mean, t_max=t_max, t_base=t_base, t_opt_max=t_opt_max,
                    day_length=12.0 + 2.2 * math.sin(2.0 * math.pi * (cur.timetuple().tm_yday - 80) / 365.0),
                    is_short_day=False, p_critical=12.0,
                )
                dev_rate = float(getattr(dev_inc, "delta_development", dev_inc) or 0.0)
            except Exception:
                dev_rate = max(0.0, t_mean - t_base)
            state.gdd_cum += dev_rate
            doy_progress = (cur.timetuple().tm_yday - 1) / 365.0
            gdd_target = max(900.0, float(getattr(crop, "growing_days", 200)) * 8.5)
            progress = 0.55 * doy_progress + 0.45 * min(1.0, state.gdd_cum / gdd_target) if architecture == "perennial" else min(1.0, state.gdd_cum / gdd_target)
            _, _ = _stage_for_progress(progress, architecture)

            # Real L3 RootZoneAvailability + DualKcEngine + LayeredWaterBalanceEngine
            est_lai = 2.6 + 0.9 * math.sin(2.0 * math.pi * (doy_progress - 0.10)) if architecture == "perennial" else max(0.3, 4.0 * math.sin(math.pi * progress))
            fvc = min(0.90, max(0.15, 0.25 + 0.14 * est_lai))
            kcb = DualKcEngine.estimate_kcb_from_canopy(
                lai=est_lai, fvc=fvc,
                kcb_min=float(getattr(crop, "kcb_initial", 0.3) or 0.3),
                kcb_full=float(getattr(crop, "kcb_reproductive", 0.7) or 0.7),
                wind_speed_2m_m_s=wind_ms,
                rh_min_pct=max(20.0, min(90.0, rh - 10.0)),
            )
            kc_max = DualKcEngine.calculate_kc_max(kcb, wind_speed_2m_m_s=wind_ms)
            ke, _ = DualKcEngine.calculate_soil_evaporation_ke(
                kcb=kcb, kc_max=kc_max, fvc=fvc,
                surface_storage_mm=state.surface_evap_storage_mm,
                days_since_wetting=state.days_since_wetting,
            )
            rz_state = RootZoneAvailabilityEngine.evaluate_root_zone(
                soil_state,
                root_depth_m=state.root_depth_m,
                etp_mm_day=max(0.5, et0_day * (kcb + ke)),
                soil_uncertainty_sigma=0.05 if has_obs else 0.10,
            )
            irrig = irrig_by_day.get(d_str, 0.0)
            flux = DualKcEngine.partition_evapotranspiration(
                et0_mm=et0_day, kcb=kcb, ke=ke,
                ks=rz_state.stress_factor_ks,
                precipitation_mm=rain,
                irrigation_mm=irrig,
            )
            step_wb = LayeredWaterBalanceEngine.step_water_balance(
                prev_soil=soil_state,
                root_zone=rz_state,
                precipitation_mm=rain,
                irrigation_mm=irrig,
                actual_transpiration_mm=flux.actual.actual_transpiration_mm,
                actual_soil_evaporation_mm=flux.actual.actual_soil_evaporation_mm,
                days_since_wetting=state.days_since_wetting,
            )
            soil_state = step_wb.updated_soil
            state.layer_theta_profile = [float(x) for x in soil_state.theta_profile]

            if (rain + irrig) >= 2.0:
                state.days_since_wetting = 0
                state.surface_evap_storage_mm = min(12.0, state.surface_evap_storage_mm + 0.6 * (rain + irrig))
            else:
                state.days_since_wetting += 1
                state.surface_evap_storage_mm = max(0.0, state.surface_evap_storage_mm - flux.actual.actual_soil_evaporation_mm)

            if rz_state.stress_factor_ks < 0.75:
                state.cumulative_water_stress_days += (1.0 - rz_state.stress_factor_ks)
            if t_max > t_opt_max:
                state.cumulative_heat_stress_days += 1.0
            state.cumulative_drainage_mm += float(step_wb.deep_drainage)
            state.last_et0_mm = et0_day
            state.last_et0_sigma_mm = et0_sig
            state.last_vpd_kpa = vpd_kpa
            state.last_kcb = kcb
            state.last_ke = ke
            state.last_t_act_mm = float(flux.actual.actual_transpiration_mm)
            state.last_e_act_mm = float(flux.actual.actual_soil_evaporation_mm)
            state.last_deep_drainage_mm = float(step_wb.deep_drainage)
            state.last_runoff_mm = float(step_wb.runoff)

            state.recent_weather_window.append({
                "date": d_str,
                "temp_mean": round(float(t_mean), 2),
                "temp_max": round(float(t_max), 2),
                "temp_min": round(float(t_min), 2),
                "humidity_max": round(float(min(98.0, rh + 12.0)), 2),
                "humidity_mean": round(float(rh), 2),
                "precip": round(float(rain), 2),
                "precip_mm": round(float(rain), 2),
                "wind_speed": round(float(wind_kmh), 2),
                "solar_mj": round(float(solar_mj), 2),
                "et0_mm": round(float(et0_day), 3),
                "vpd_kpa": round(float(vpd_kpa), 3),
                "dev_rate": round(float(dev_rate), 4),
                "has_observed_weather": has_obs,
            })
            if len(state.recent_weather_window) > 10:
                state.recent_weather_window = state.recent_weather_window[-10:]
            state.last_day = d_str
            cur += timedelta(days=1)

        return state

    def _evaluate_layer8_safety_constraints(
        self,
        *,
        crop_name: str,
        stage_label: str,
        w_last: Dict[str, Any],
        recent_win: List[Dict[str, Any]],
        soil_theta_top: float,
        ec_meas: Optional[float],
        ec_thr: float,
        soil_type: str,
    ) -> Dict[str, Any]:
        """Run ALL Layer 8 physical safety/feasibility gate engines strictly as constraints-only."""
        pb = PriorityBreakdown(
            impact_score=0.5, urgency_score=0.5, risk_score=0.5, cost_score=0.5, confidence_score=0.6
        )
        cards = [
            ActionCard(
                action_id="l8_probe_spray", action_type=ActionType.SPRAY, priority_score=0.5,
                priority_breakdown=pb, zone_targets=["plot"], zone_allocation={"plot": 1.0},
                rate=RateRange(recommended=1.0, min_safe=0.5, max_safe=2.0, unit="L/ha"),
                confidence=ConfidenceLevel.MODERATE, explain="constraint_probe",
            ),
            ActionCard(
                action_id="l8_probe_irrig", action_type=ActionType.IRRIGATE, priority_score=0.5,
                priority_breakdown=pb, zone_targets=["plot"], zone_allocation={"plot": 1.0},
                rate=RateRange(recommended=18.0, min_safe=5.0, max_safe=35.0, unit="mm"),
                confidence=ConfidenceLevel.MODERATE, explain="constraint_probe",
            ),
            ActionCard(
                action_id="l8_probe_fert", action_type=ActionType.FERTILIZE, priority_score=0.5,
                priority_breakdown=pb, zone_targets=["plot"], zone_allocation={"plot": 1.0},
                rate=RateRange(recommended=40.0, min_safe=10.0, max_safe=80.0, unit="kg_ha"),
                confidence=ConfidenceLevel.MODERATE, explain="constraint_probe",
            ),
        ]
        fc_rows = [
            {
                "date": r.get("date"),
                "wind_speed": r.get("wind_speed", 8.0),
                "wind_gust": float(r.get("wind_speed", 8.0) or 8.0) * 1.25,
                "precip_mm": r.get("precip_mm", 0.0),
                "t_max_c": r.get("temp_max", 24.0),
                "t_min_c": r.get("temp_min", 14.0),
                "temp_max": r.get("temp_max", 24.0),
                "temp_min": r.get("temp_min", 14.0),
                "rh_min_pct": max(20.0, float(r.get("humidity_mean", 60.0) or 60.0) - 12.0),
            }
            for r in (recent_win[-3:] if recent_win else [w_last])
        ]
        cards = self._pheno_dosing.adjust_rates(cards, crop_name, stage_label)
        cards = self._spray_gate.enforce_drift_limits(cards, fc_rows)
        cards = self._frost_gate.evaluate_frost_risk(cards, fc_rows)
        cards = self._cool_gate.evaluate_cooling_need(cards, crop_name, stage_label, fc_rows)
        cards = self._till_gate.evaluate_compaction(cards, 1.35, soil_type, stage_label)
        cards = self._volat_gate.evaluate_volatilization(
            cards, 6.8, float(w_last.get("temp_mean", 20.0) or 20.0), soil_theta_top * 100.0
        )
        if ec_meas is not None:
            cards = self._sal_gate.adjust_irrigation_for_salinity(cards, crop_name, ec_meas)

        spray_card = next((c for c in cards if c.action_type == ActionType.SPRAY), None)
        irrig_card = next((c for c in cards if c.action_type == ActionType.IRRIGATE), None)
        fert_card = next((c for c in cards if c.action_type == ActionType.FERTILIZE), None)
        bbch = self._pheno_dosing.lookup_stage(crop_name, stage_label)
        return {
            "source_layer": "layer8_action",
            "engine_name": "PhenologyDosing+SprayDriftGate+Frost+Cooling+Compaction+Volatilization+SalinityLeaching",
            "model_version": "l8_constraints_suite_v2",
            "status": "available" if recent_win else "partial",
            "usable_as_prior": False,
            "is_constraint_only": True,
            "contains_recommendations": False,
            "never_physical_ground_truth": True,
            "action_feasibility": {
                "foliar_spray_allowed": bool(spray_card.is_allowed) if spray_card else True,
                "spray_block_reason": spray_card.blocked_reason if spray_card and not spray_card.is_allowed else None,
                "irrigation_allowed": bool(irrig_card.is_allowed) if irrig_card else True,
                "fertilization_allowed": bool(fert_card.is_allowed) if fert_card else True,
                "critical_phenology_period": bool(bbch.critical_period),
            },
            "constraint_flags": [
                str(c.blocked_reason or c.explain)
                for c in cards
                if (not c.is_allowed or "frost" in str(c.explain).lower() or "cool" in str(c.explain).lower() or "volatil" in str(c.explain).lower())
            ],
            "phenology_dosing_windows": [{
                "bbch_code": bbch.bbch_code,
                "stage_name": bbch.stage_name,
                "water_demand_factor": bbch.water_demand_factor,
                "absorption_coefficients": dict(bbch.absorption_coefficients),
            }],
            "salinity_leaching_windows": (
                [{"ec_ds_m": ec_meas, "threshold_ds_m": ec_thr, "leaching_advisory": True}]
                if (ec_meas is not None and ec_meas > ec_thr) else []
            ),
            "do_not_prescribe_zones": [],
        }

    def evaluate_step_priors(
        self,
        *,
        state: CrossLayerChronoState,
        timestamp: datetime,
        knowledge_cutoff: datetime,
        crop_context: Optional[Dict[str, Any]] = None,
        soil_context: Optional[Dict[str, Any]] = None,
        forecast_window_weather: Optional[List[Dict[str, Any]]] = None,
        lat: float = 36.5,
    ) -> Dict[str, Any]:
        """Execute Layers 2-7 specialist engines + Layer 8 safety constraints BEFORE ASMAE update."""
        crop_cfg = dict(crop_context or {})
        soil_cfg = dict(soil_context or {})
        crop_name = str(crop_cfg.get("crop_type") or crop_cfg.get("crop") or "citrus").lower()
        crop = _safe_crop_profile(crop_name)
        architecture = str(getattr(crop, "architecture", "perennial"))
        ts_iso = timestamp.isoformat()
        k_iso = knowledge_cutoff.isoformat()

        win = list(state.recent_weather_window or [])
        n_obs_w = sum(1 for r in win if r.get("has_observed_weather"))
        weather_ratio = n_obs_w / max(1, len(win))
        w_last = win[-1] if win else {
            "date": ts_iso[:10], "temp_mean": 18.0, "temp_max": 23.0, "temp_min": 13.0,
            "humidity_max": 72.0, "humidity_mean": 60.0, "precip": 0.0, "precip_mm": 0.0,
            "wind_speed": 8.0, "solar_mj": 14.0, "et0_mm": 3.0, "vpd_kpa": 1.0,
        }

        # ── Layer 2: Phenology, Growth Curve, TemporalAnomalyEngine & Retrieval Models ─
        doy_progress = (timestamp.timetuple().tm_yday - 1) / 365.0
        gdd_target = max(900.0, float(getattr(crop, "growing_days", 200)) * 8.5)
        growth_pos = (
            0.55 * doy_progress + 0.45 * min(1.0, state.gdd_cum / gdd_target)
            if architecture == "perennial" else min(1.0, state.gdd_cum / gdd_target)
        )
        growth_pos = max(0.0, min(1.0, growth_pos))
        stage_label, _ = _stage_for_progress(growth_pos, architecture)
        if architecture == "perennial":
            expected_vigor = 0.56 + 0.14 * math.sin(2.0 * math.pi * (doy_progress - 0.10))
            expected_lai = 2.6 + 1.0 * math.sin(2.0 * math.pi * (doy_progress - 0.10))
        else:
            expected_vigor = 0.25 + 0.55 * math.sin(math.pi * growth_pos)
            expected_lai = 0.4 + 4.2 * math.sin(math.pi * growth_pos)

        last_ndmi = state.recent_ndmi_window[-1] if state.recent_ndmi_window else None
        ndmi_stress, ndmi_sig = NDMIWaterStressModel.evaluate(last_ndmi)
        therm_stress, therm_sig = TemperatureThermalStressModel.evaluate(
            float(w_last.get("temp_max", 23.0) or 23.0),
            float(w_last.get("vpd_kpa", 1.0) or 1.0),
        )
        l2_anomalies: List[str] = []
        if len(state.recent_ndvi_window) >= 3:
            try:
                anoms = self._l2_anomaly.detect_anomalies(
                    dates=[x[0] for x in state.recent_ndvi_window],
                    observed_ndvi=[x[1] for x in state.recent_ndvi_window],
                    modeled_ndvi=[x[2] for x in state.recent_ndvi_window],
                    uncertainties=[0.06] * len(state.recent_ndvi_window),
                    crop_temp_max=float(getattr(crop, "optimal_temp_max", 35.0) or 35.0),
                )
                l2_anomalies = [str(a.anomaly_type.value if hasattr(a.anomaly_type, "value") else a.anomaly_type) for a in anoms[-3:]]
            except Exception:
                l2_anomalies = []
        l2_conf = round(0.45 + 0.40 * weather_ratio, 4)
        l2_out = {
            "source_layer": "layer2_intelligence",
            "engine_name": "PhenologyRate+TemporalAnomalyEngine+RetrievalModels",
            "model_version": "l2_specialist_v2",
            "status": "available" if n_obs_w > 0 else "partial",
            "usable_as_prior": True,
            "timestamp": ts_iso,
            "knowledge_cutoff": k_iso,
            "valid_window": f"{ts_iso[:10]}/{ts_iso[:10]}",
            "confidence": l2_conf,
            "uncertainty": round(max(0.04, 0.22 - 0.12 * weather_ratio + 0.3 * ndmi_sig), 4),
            "phenology_stage": stage_label,
            "growth_position": round(growth_pos, 4),
            "gdd_cumulative": round(float(state.gdd_cum), 2),
            "expected_vigor": round(float(max(0.1, min(0.95, expected_vigor))), 4),
            "expected_lai": round(float(max(0.2, min(7.0, expected_lai))), 4),
            "ndmi_water_stress_prior": ndmi_stress,
            "thermal_stress_prior": therm_stress,
            "thermal_stress_sigma": therm_sig,
            "detected_temporal_anomalies": l2_anomalies,
            "ndvi_trajectory_phase": stage_label,
            "ndvi_trajectory_position": round(growth_pos, 4),
            "missing_inputs": [] if n_obs_w > 0 else ["historical_weather_temperature"],
        }

        # ── Layer 3: Multi-Layer Hydrology (SoilProfile + DualKc + WaterLimitation) ─
        soil_state = self._build_soil_state(state)
        rz_state = RootZoneAvailabilityEngine.evaluate_root_zone(
            soil_state,
            root_depth_m=state.root_depth_m,
            etp_mm_day=max(0.5, state.last_et0_mm * (state.last_kcb + state.last_ke)),
            soil_uncertainty_sigma=0.05 if n_obs_w > 0 else 0.10,
        )
        pot_flux = PotentialWaterFlux(
            et0_mm=state.last_et0_mm,
            kcb=state.last_kcb,
            ke=state.last_ke,
        )
        lim_state = WaterLimitationEngine.evaluate_limitation(
            rz_state, pot_flux, et0_uncertainty_sigma=state.last_et0_sigma_mm
        )
        taw = max(1e-6, float(lim_state.total_available_water_mm))
        paw_frac = max(0.05, min(0.95, 1.0 - float(lim_state.root_zone_depletion_mm) / taw))
        rzw_mean_vwc = float(sum(soil_state.theta_profile) / max(1, len(soil_state.theta_profile)))
        l3_conf = round(0.40 + 0.45 * weather_ratio, 4)
        l3_out = {
            "source_layer": "layer3_water",
            "engine_name": "PenmanMonteithET0+DualKc+LayeredWaterBalance+WaterLimitation",
            "model_version": "l3_multilayer_hydrology_v2",
            "status": "available" if n_obs_w > 0 else "partial",
            "usable_as_prior": n_obs_w > 0,
            "timestamp": ts_iso,
            "knowledge_cutoff": k_iso,
            "valid_window": f"{ts_iso[:10]}/{ts_iso[:10]}",
            "confidence": l3_conf,
            "uncertainty": round(float(lim_state.transpiration_deficit_sigma_mm), 4),
            "et0": round(float(state.last_et0_mm), 4),
            "et0_sigma": round(float(state.last_et0_sigma_mm), 4),
            "vpd_kpa": round(float(state.last_vpd_kpa), 3),
            "kcb": round(float(state.last_kcb), 3),
            "ke": round(float(state.last_ke), 3),
            "actual_transpiration_mm": round(float(state.last_t_act_mm), 3),
            "actual_soil_evaporation_mm": round(float(state.last_e_act_mm), 3),
            "deep_drainage_mm": round(float(state.last_deep_drainage_mm), 3),
            "ks_factor": round(float(lim_state.stress_factor_ks), 4),
            "root_zone_depletion_mm": round(float(lim_state.root_zone_depletion_mm), 3),
            "taw_mm": round(float(taw), 2),
            "transpiration_deficit_mm": round(float(lim_state.transpiration_deficit_mm), 3),
            "water_limitation_probability": round(float(lim_state.water_limitation_probability), 4),
            "water_stress_prob_pct": round(float(lim_state.water_limitation_probability) * 100.0, 2),
            "root_zone_water_prior": round(float(max(0.08, min(0.50, rzw_mean_vwc))), 4),
            "paw_fraction": round(paw_frac, 4),
            "layer_theta_profile": [round(float(x), 4) for x in soil_state.theta_profile],
            "water_balance": round((float(w_last.get("precip_mm", 0.0)) - state.last_t_act_mm - state.last_e_act_mm), 3),
            "diagnostic_evidence": list(lim_state.diagnostic_evidence),
            "missing_inputs": ["in_situ_soil_moisture_probe"] + ([] if n_obs_w > 0 else ["weather_forcing"]),
        }

        # ── Layer 4: SoilRespiration + CropDemand + PhotosynthesisNUE + EnvLoss + Salinity ─
        ndvi_vals = [x[1] for x in state.recent_ndvi_window]
        if ndvi_vals:
            n_diag = self._n_def.detect_deficiency(
                pd.Series(ndvi_vals), stage_label, float(l3_out["water_stress_prob_pct"])
            )
            n_prob = round(float(n_diag.get("n_deficiency_prob", 0.0)) / 100.0, 4)
        else:
            n_diag = {"n_deficiency_prob": 0.0, "severity": "unknown", "water_gating_applied": False}
            n_prob = 0.0

        try:
            resp_res = self._soil_resp.compute_seasonal_mineralization(
                [{"temp_mean": r.get("temp_mean", 18.0), "precip": r.get("precip_mm", 0.0)} for r in (win if win else [w_last])]
            )
            min_n_kg_ha = float(getattr(resp_res, "cumulative_n_mineralization_kg_ha", 15.0) or 15.0)
        except Exception:
            min_n_kg_ha = 15.0

        try:
            dem_res = self._demand.compute_demand(crop_name, [stage_label] * 7)
            dem_n = float(getattr(dem_res, "total_n_kg_ha", getattr(dem_res, "n_demand_kg_ha", 40.0)) or 40.0)
        except Exception:
            dem_n = 40.0

        try:
            photo_nue = self._photo_nue.analyze(
                crop_type=crop_name,
                lai_current=max(0.4, float(l2_out["expected_lai"])),
                fpar_current=min(0.95, 0.25 + 0.15 * float(l2_out["expected_lai"])),
                soil_n_supply_kg_ha=max(10.0, 20.0 + min_n_kg_ha),
                growth_stage=stage_label,
                daily_par_mj_m2=max(4.0, 0.48 * float(w_last.get("solar_mj", 14.0) or 14.0)),
            )
            nni_val = float(getattr(photo_nue, "nni", 0.75) or 0.75)
            nni_status = str(getattr(photo_nue, "nni_status", "UNKNOWN"))
        except Exception:
            nni_val, nni_status = 0.75, "UNKNOWN"

        try:
            env_loss = self._env_loss.compute_all_losses(
                n_applied_kg_ha=40.0,
                temperature_c=float(w_last.get("temp_mean", 20.0) or 20.0),
                wind_speed_m_s=max(0.5, float(w_last.get("wind_speed", 8.0) or 8.0) / 3.6),
                total_drainage_mm=float(state.cumulative_drainage_mm),
                soil_moisture_vwc=rzw_mean_vwc,
            )
            n_loss_frac = float(getattr(env_loss, "total_loss_fraction", 0.05) or 0.05)
        except Exception:
            n_loss_frac = 0.05

        ec_meas = _finite(soil_cfg.get("ec_ds_m") if soil_cfg.get("ec_ds_m") is not None else soil_cfg.get("salinity"), None)
        ec_thr = float(getattr(crop, "ec_threshold_ds_m", 3.0) or 3.0)
        if ec_meas is not None:
            sal_res = self._salinity.assess_salinity_impact(ec_ds_m=ec_meas, crop_type=crop_name)
            salinity_risk = min(1.0, max(0.0, float(getattr(sal_res, "yield_loss_pct", 0.0) or 0.0) / 50.0))
            _, sal_sig = SalinityECModel.evaluate(ec_meas)
        else:
            salinity_risk = None
            sal_sig = 0.30

        l4_missing = (["soil_ec_ds_m"] if ec_meas is None else []) + ["leaf_tissue_n_assay"]
        l4_out = {
            "source_layer": "layer4_nutrients",
            "engine_name": "SoilRespiration+CropDemand+PhotosynthesisNUE+EnvironmentalLoss+Salinity+NDeficiency",
            "model_version": "l4_mechanistic_v2",
            "status": "partial" if (ndvi_vals or n_obs_w > 0) else "unavailable",
            "usable_as_prior": bool(ndvi_vals),
            "timestamp": ts_iso,
            "knowledge_cutoff": k_iso,
            "confidence": 0.50 if ndvi_vals else 0.22,
            "uncertainty": round(sal_sig, 4),
            "nutrient_demand": round(n_prob, 4),
            "n_deficiency_severity": n_diag.get("severity", "unknown"),
            "water_gating_applied": bool(n_diag.get("water_gating_applied", False)),
            "soil_n_mineralization_kg_ha": round(min_n_kg_ha, 2),
            "crop_n_demand_kg_ha": round(dem_n, 2),
            "nitrogen_nutrition_index": round(nni_val, 3),
            "nni_status": nni_status,
            "n_environmental_loss_fraction": round(n_loss_frac, 4),
            "chlorophyll_proxy": round(max(12.0, min(68.0, 22.0 + 42.0 * expected_vigor * min(1.0, 0.5 + 0.5 * nni_val))), 2),
            "salinity_risk": round(salinity_risk, 4) if salinity_risk is not None else None,
            "missing_inputs": l4_missing,
        }

        # ── Layer 5: BiophysicalCanopyEnergyBalance + DynamicPriors + BioThreatInference ─
        try:
            solar_wm2 = max(50.0, float(w_last.get("solar_mj", 14.0) or 14.0) * 11.57 * 2.2)
            bio_eb = self._bio_energy.solve(
                t_ambient=float(w_last.get("temp_mean", 20.0) or 20.0),
                rh_ambient=float(w_last.get("humidity_mean", 60.0) or 60.0),
                wind_speed=max(0.5, float(w_last.get("wind_speed", 8.0) or 8.0) / 3.6),
                lai=float(l2_out["expected_lai"]),
                solar_rad=solar_wm2,
                water_stress_prob=float(l3_out["water_limitation_probability"]),
            )
            t_leaf = float(bio_eb.get("t_leaf", w_last.get("temp_mean", 20.0)))
            t_dew_leaf = float(bio_eb.get("t_dew_leaf", 12.0))
            dew_margin = t_leaf - t_dew_leaf
            leaf_wet_factor = max(0.0, min(1.0, (4.0 - dew_margin) / 4.0))
        except Exception:
            bio_eb = {}
            t_leaf = float(w_last.get("temp_mean", 20.0) or 20.0)
            leaf_wet_factor = 0.15

        try:
            dyn_priors = compute_dynamic_priors(
                crop_type=crop_name,
                phenology_stage=stage_label,
                climate_indicators={
                    "rh_max": float(w_last.get("humidity_max", 72.0) or 72.0),
                    "temp_mean": float(w_last.get("temp_mean", 20.0) or 20.0),
                    "precip_mm": float(w_last.get("precip_mm", 0.0) or 0.0),
                },
                lat=lat,
            )
            bio_states = self._bio_inf.infer_states(
                evidence_by_threat={k: [] for k in dyn_priors},
                spread={"spread_probability": 0.15 * leaf_wet_factor},
                priors=dyn_priors,
                phenology_stage=stage_label,
                missing_drivers=["canopy_scouting_imagery", "pathology_assay"],
            )
            top_threat = max(bio_states.items(), key=lambda kv: float(kv[1].probability))
            top_threat_name = str(top_threat[0])
            top_threat_prob = round(float(top_threat[1].probability), 4)
            threat_probs = {k: round(float(v.probability), 4) for k, v in bio_states.items()}
        except Exception:
            top_threat_name, top_threat_prob, threat_probs = "NONE", 0.05, {}

        weather_bio_suit = round(max(top_threat_prob, 0.55 * leaf_wet_factor), 4)
        l5_out = {
            "source_layer": "layer5_biotic",
            "engine_name": "BiophysicalCanopyEnergyBalanceSolver+DynamicPriors+BioThreatInferenceEngine",
            "model_version": "l5_biophysical_bayesian_v2",
            "status": "partial" if n_obs_w > 0 else "unavailable",
            "usable_as_prior": False,  # Weather/microclimate suitability is never ground truth outbreak
            "timestamp": ts_iso,
            "knowledge_cutoff": k_iso,
            "confidence": 0.42 if n_obs_w > 0 else 0.12,
            "uncertainty": 0.42,
            "canopy_t_leaf_c": round(t_leaf, 2),
            "leaf_wetness_condensation_index": round(leaf_wet_factor, 4),
            "top_threat_hypothesis": top_threat_name,
            "top_threat_posterior_prob": top_threat_prob,
            "threat_probabilities": threat_probs,
            "biotic_threat_risk": weather_bio_suit,
            "weather_disease_suitability": weather_bio_suit,
            "outbreak_probability": round(0.40 * weather_bio_suit, 4),
            "is_unconfirmed_confounder_only": True,
            "missing_inputs": ["field_scouting_imagery", "leaf_pathology_confirmation"],
        }

        # ── Layer 7: ClimateShockEngine + RiskCompositeEngine ─────────────────────
        causal_shock_days = [
            {
                "temp_max": r.get("temp_max", 22.0),
                "temp_min": r.get("temp_min", 12.0),
                "precip_mm": r.get("precip_mm", 0.0),
                "wind_speed": r.get("wind_speed", 8.0),
            }
            for r in (forecast_window_weather if forecast_window_weather is not None else win[-3:])
        ]
        try:
            shock_res = self._climate_shock.detect_shocks(causal_shock_days)
        except Exception:
            shock_res = {"shock_prob": 0.0, "events": [], "is_severe": False}
        shock_prob = round(float(shock_res.get("shock_prob", 0.0) or 0.0) / 100.0, 4)
        try:
            comp_res = self._risk_comp.calculate_composite_risk(
                water_stress_prob=float(l3_out["water_stress_prob_pct"]),
                nutrient_stress_prob=round(n_prob * 100.0, 2),
                disease_risk_prob=round(weather_bio_suit * 100.0, 2),
                climate_shock_prob=float(shock_res.get("shock_prob", 0.0) or 0.0),
                stage_label=stage_label,
            )
        except Exception:
            comp_res = {"composite_risk_score": 0.0, "risk_level": "low"}

        l7_out = {
            "source_layer": "layer7_risk",
            "engine_name": "ClimateShockEngine+RiskCompositeEngine+TrustMonitor",
            "model_version": "l7_risk_v2",
            "status": "available" if n_obs_w > 0 else "partial",
            "usable_as_prior": n_obs_w > 0,
            "timestamp": ts_iso,
            "knowledge_cutoff": k_iso,
            "confidence": round(0.42 + 0.43 * weather_ratio, 4),
            "uncertainty": round(0.14 + 0.24 * (1.0 - weather_ratio) + 0.15 * shock_prob, 4),
            "climate_shock_risk": shock_prob,
            "shock_events": list(shock_res.get("events") or []),
            "composite_risk_score": round(float(comp_res.get("composite_risk_score", 0.0) or 0.0) / 100.0, 4),
            "risk_level": comp_res.get("risk_level", "low"),
            "forecast_uncertainty": round(1.0 + 0.45 * shock_prob + 0.25 * (1.0 - weather_ratio), 4),
            "future_stress_windows": list(shock_res.get("events") or []),
            "missing_inputs": [] if forecast_window_weather is not None else ["nwp_multi_day_forecast"],
        }

        # ── Layer 6: YieldForecastEngine + ProfitabilityCalculator ──────────────
        cum_water_pen = min(0.55, 0.015 * float(state.cumulative_water_stress_days))
        cum_heat_pen = min(0.35, 0.025 * float(state.cumulative_heat_stress_days))
        est_biomass = max(2500.0, 12000.0 + 18000.0 * max(0.1, expected_vigor))
        try:
            y_res = self._yield_engine.predict_yield(
                crop_type=crop_name,
                final_biomass_kg_ha=est_biomass,
                cumulative_stress={
                    "water_loss_factor": round(cum_water_pen, 4),
                    "nutrient_loss_factor": round(0.25 * n_prob, 4),
                    "disease_loss_factor": round(0.20 * float(l5_out["outbreak_probability"]), 4),
                },
                confidence_scores={"biomass": l2_conf, "stress": l3_conf},
            )
            y_mean = float(y_res.get("predicted_yield_t_ha") or 0.0)
            prof_res = self._profit_calc.calculate_profit(
                yield_mean_t_ha=y_mean,
                price_per_ton=float(getattr(crop, "price_usd_per_ton", 300) or 300),
                input_costs_per_ha=950.0,
            )
        except Exception:
            y_res = {"predicted_yield_t_ha": None, "yield_range_95": None}
            prof_res = {}

        l6_out = {
            "source_layer": "layer6_yield",
            "engine_name": "YieldForecastEngine+ProfitabilityCalculator",
            "model_version": "l6_yield_economics_v2",
            "status": "partial",
            "usable_as_prior": False,
            "timestamp": ts_iso,
            "knowledge_cutoff": k_iso,
            "confidence": round(0.35 + 0.30 * weather_ratio, 4),
            "uncertainty": round(max(0.15, 0.35 - 0.15 * weather_ratio), 4),
            "predicted_yield_t_ha": y_res.get("predicted_yield_t_ha"),
            "yield_range_95": y_res.get("yield_range_95"),
            "expected_profit_usd_ha": prof_res.get("profit_usd_ha"),
            "yield_sensitivity": round(min(1.0, 0.25 + cum_water_pen + cum_heat_pen), 4),
            "economic_value": round(float(getattr(crop, "price_usd_per_ton", 300) or 300) * (cum_water_pen + cum_heat_pen), 2),
            "missing_inputs": ["harvest_weight_calibration", "destructive_biomass_samples"],
        }

        # ── Layer 8: Full Safety/Feasibility Constraint Engines ONLY ──────────────
        l8_out = self._evaluate_layer8_safety_constraints(
            crop_name=crop_name,
            stage_label=stage_label,
            w_last=w_last,
            recent_win=win,
            soil_theta_top=float(soil_state.theta_profile[0]),
            ec_meas=ec_meas,
            ec_thr=ec_thr,
            soil_type=state.soil_type,
        )
        l8_out["timestamp"] = ts_iso
        l8_out["knowledge_cutoff"] = k_iso

        coarse_layer_outputs = {
            "layer2_intelligence": l2_out,
            "layer3_water": l3_out,
            "layer4_nutrients": l4_out,
            "layer5_biotic": l5_out,
            "layer6_yield": l6_out,
            "layer7_risk": l7_out,
            "layer8_action": l8_out,
        }
        return {
            "contract_version": CROSS_LAYER_CONTRACT_VERSION,
            "observation_time": ts_iso,
            "knowledge_cutoff": k_iso,
            "observation_role": "bounded_specialist_prior",
            "coarse_layer_outputs": coarse_layer_outputs,
            "priors": {
                "layer2": l2_out,
                "layer3": l3_out,
                "layer4": l4_out,
                "layer5": l5_out,
                "layer6": l6_out,
                "layer7": l7_out,
                "layer8": l8_out,
            },
        }

    def refine_after_asmae(
        self,
        *,
        pre_bundle: Dict[str, Any],
        posterior_means: Dict[str, float],
        posterior_stds: Dict[str, float],
        state_support_ledger: Optional[Dict[str, Dict[str, Any]]] = None,
        crop_context: Optional[Dict[str, Any]] = None,
        obs_channels: Optional[Dict[str, float]] = None,
        gap_days: float = 0.0,
    ) -> Dict[str, Any]:
        """Post-ASMAE Layers 2-7 refined specialist reasoning, contradictions, TrustMonitor & VoI.

        Anti-circularity invariant: refined outputs carry
        `observation_role="refined_specialist_output_non_assimilable"` and NEVER become
        new independent observations in ASMAE.
        """
        crop_name = str((crop_context or {}).get("crop_type") or (crop_context or {}).get("crop") or "citrus").lower()
        crop = _safe_crop_profile(crop_name)
        pre = pre_bundle.get("priors") or {}
        l2_pre = pre.get("layer2") or {}
        l3_pre = pre.get("layer3") or {}
        l4_pre = pre.get("layer4") or {}
        l5_pre = pre.get("layer5") or {}
        l7_pre = pre.get("layer7") or {}
        l8_pre = pre.get("layer8") or {}

        v_post = float(posterior_means.get("vigor", 0.5))
        lai_post = float(posterior_means.get("lai", 2.5))
        v_sig = float(posterior_stds.get("vigor", 0.1))
        cw_post = float(posterior_means.get("canopy_water", 0.35))
        rzw_post = float(posterior_means.get("root_zone_water", 0.25))
        rzw_sig = float(posterior_stds.get("root_zone_water", 0.08))
        sm_post = float(posterior_means.get("stress_memory", 0.15))

        exp_vigor = float(l2_pre.get("expected_vigor", 0.55) or 0.55)
        vigor_anom = round(v_post - exp_vigor, 4)
        l3_rzw = float(l3_pre.get("root_zone_water_prior", 0.25) or 0.25)
        l3_lim = float(l3_pre.get("water_limitation_probability", 0.0) or 0.0)
        refined_water_prob = round(min(1.0, max(0.0, 0.55 * l3_lim + 0.45 * max(0.0, (0.28 - rzw_post) / 0.18))), 4)

        ndvi_obs_val = (obs_channels or {}).get("ndvi", v_post)
        n_ref = self._n_def.detect_deficiency(
            pd.Series([v_post, ndvi_obs_val]),
            str(l2_pre.get("phenology_stage") or "vegetative"),
            refined_water_prob * 100.0,
        )
        n_prob_ref = round(float(n_ref.get("n_deficiency_prob", 0.0)) / 100.0, 4)

        # Refined L4 NUE conditioned on ASMAE posterior LAI + soil mineralization
        try:
            min_n = float(l4_pre.get("soil_n_mineralization_kg_ha") or 20.0)
            p_nue_ref = self._photo_nue.analyze(
                crop_type=crop_name,
                lai_current=max(0.2, lai_post),
                fpar_current=min(0.95, 0.25 + 0.14 * lai_post),
                soil_n_supply_kg_ha=max(10.0, 20.0 + min_n),
                growth_stage=str(l2_pre.get("phenology_stage") or "vegetative"),
            )
            nni_ref = round(float(getattr(p_nue_ref, "nni", 0.75) or 0.75), 3)
            rue_actual = round(float(getattr(p_nue_ref, "rue_actual", 0.5) or 0.5), 3)
        except Exception:
            nni_ref, rue_actual = l4_pre.get("nitrogen_nutrition_index"), None

        # Run canonical Layer 7 TrustMonitor + physical contradiction diagnostics
        trust_conflict = self._trust_mon.evaluate_cross_layer_conflict(
            asmae_features={"ASMAE_CANOPY_WATER": {"value": cw_post, "unit": "dimensionless_index"}},
            non_asmae_data={"soil_moisture_vwc": l3_rzw},
        )
        contradictions: List[Dict[str, Any]] = []
        if l3_lim >= 0.45 and cw_post >= 0.45:
            contradictions.append({
                "code": "l3_drought_vs_asmae_wet_canopy",
                "layers": ["layer3_water", "asmae_canopy_water"],
                "severity": "moderate",
                "detail": "Layer 3 multi-layer soil balance indicates transpiration limitation while ASMAE posterior canopy water remains high.",
            })
        elif l3_lim <= 0.15 and vigor_anom <= -0.14:
            contradictions.append({
                "code": "unexplained_vigor_deficit_under_adequate_water",
                "layers": ["layer2_vegetation", "layer3_water", "asmae_vigor"],
                "severity": "high",
                "detail": f"ASMAE vigor ({v_post:.2f}) trails Layer 2 phenological expectation ({exp_vigor:.2f}) despite adequate modeled L3 soil water — elevates nutrient/salinity/biotic hypotheses.",
            })
        if abs(l3_rzw - rzw_post) >= 0.18:
            contradictions.append({
                "code": "l3_bucket_vs_asmae_rzw_divergence",
                "layers": ["layer3_water", "asmae_root_zone_water"],
                "severity": "moderate",
                "detail": f"Layer 3 soil column VWC ({l3_rzw:.2f}) diverges from ASMAE SAR/optical-assimilated root-zone water ({rzw_post:.2f}).",
            })

        # Normalized 6-mechanism multi-layer competing explanations (explicitly separated from field verification)
        pheno_stage = str(l2_pre.get("phenology_stage") or "vegetative")
        phys_regime = str((crop_context or {}).get("physical_regime") or "")
        is_regime_transition = phys_regime in {
            "PRE_PLANTING_FALLOW_OR_PREP",
            "EARLY_ESTABLISHMENT",
            "POST_HARVEST_RESIDUE_OR_FALLOW",
        }
        pheno_score = (
            0.55
            if is_regime_transition or pheno_stage in ("senescence", "harvest", "maturation")
            else 0.12
        )
        water_score = max(0.08, 0.65 * refined_water_prob + 0.35 * sm_post)
        vpd_val = float(l3_pre.get("vpd_kpa") or 1.0)
        therm_prior = float(l2_pre.get("thermal_stress_prior") or 0.0)
        heat_vpd_score = max(0.04, 0.60 * therm_prior + 0.40 * max(0.0, min(1.0, (vpd_val - 1.8) / 2.5)))
        has_water_adequate_deficit = any(
            c.get("code") == "unexplained_vigor_deficit_under_adequate_water" for c in contradictions
        )
        n_score = max(0.06, n_prob_ref * (1.25 if has_water_adequate_deficit else 0.85))
        sal_raw = l4_pre.get("salinity_risk")
        sal_measured = sal_raw is not None
        sal_score = max(0.04, float(sal_raw)) if sal_measured else 0.06
        bio_score = max(
            0.05,
            float(l5_pre.get("weather_disease_suitability", 0.1) or 0.1) * 0.65
            + (0.14 if (vigor_anom <= -0.14 and refined_water_prob < 0.35) else 0.0),
        )
        mech_raw = {
            "water_deficit": (water_score, "L3 water balance + ASMAE root-zone water & stress memory", "satellite_model_hypothesis"),
            "heat_vpd": (heat_vpd_score, "L2 temperature thermal stress + L3 VPD atmospheric demand", "meteorological_forcing_hypothesis"),
            "nitrogen_limitation": (n_score, "L4 water-gated N-deficiency & Photosynthesis NUE NNI", "satellite_model_hypothesis" if not contradictions else "contradiction_elevated_hypothesis"),
            "salinity_osmotic_ec": (sal_score, "L4 SalinityEngine EC threshold risk", "measured_soil_ec" if sal_measured else "unverified_missing_input"),
            "phenological_stage_transition": (pheno_score, f"L2 crop phenology stage ({pheno_stage})", "phenology_model_prior"),
            "biotic_or_unobserved_management": (bio_score, "L5 biophysical canopy pathogen suitability + residual anomaly", "unverified_scouting_required"),
        }
        tot_sc = max(1e-8, sum(v[0] for v in mech_raw.values()))
        ranked_mechanisms = sorted(
            [
                {
                    "mechanism": m_name,
                    "weight": round(score / tot_sc, 4),
                    "raw_signal": round(score, 4),
                    "evidence_basis": basis,
                    "verification_status": v_stat,
                    "confirmed_ground_truth": v_stat == "measured_soil_ec",
                }
                for m_name, (score, basis, v_stat) in mech_raw.items()
            ],
            key=lambda row: row["weight"],
            reverse=True,
        )
        competing_attribution = {
            "phenological_stage_transition": round(pheno_score / tot_sc, 4),
            "root_zone_water_deficit": round(water_score / tot_sc, 4),
            "heat_vpd_stress": round(heat_vpd_score / tot_sc, 4),
            "nitrogen_limitation": round(n_score / tot_sc, 4),
            "salinity_osmotic_ec": round(sal_score / tot_sc, 4),
            "nutrient_or_salinity_limitation": round((n_score + sal_score) / tot_sc, 4),
            "biotic_or_canopy_confounder": round(bio_score / tot_sc, 4),
            "dominant_hypothesis": ranked_mechanisms[0]["mechanism"] if ranked_mechanisms else None,
            "ranked_mechanisms": ranked_mechanisms,
            "verification_note": "Satellite & atmospheric stress attributions remain hypotheses until verified by field scouting, tissue assay, soil EC, or calibrated in-situ probes.",
        }

        # Refined L6 Yield + Profitability conditioned on ASMAE posterior vigor & water
        est_bio_post = max(2500.0, 12000.0 + 18500.0 * v_post)
        try:
            y_ref = self._yield_engine.predict_yield(
                crop_type=crop_name,
                final_biomass_kg_ha=est_bio_post,
                cumulative_stress={
                    "water_loss_factor": round(min(0.55, 0.45 * refined_water_prob + 0.20 * sm_post), 4),
                    "nutrient_loss_factor": round(0.25 * n_prob_ref, 4),
                    "disease_loss_factor": round(0.15 * float(l5_pre.get("weather_disease_suitability", 0.0) or 0.0), 4),
                },
                confidence_scores={
                    "biomass": round(max(0.25, 1.0 - 2.0 * v_sig), 4),
                    "stress": round(max(0.25, 1.0 - 2.5 * rzw_sig), 4),
                },
            )
            p_ref = self._profit_calc.calculate_profit(
                yield_mean_t_ha=float(y_ref.get("predicted_yield_t_ha") or 0.0),
                price_per_ton=float(getattr(crop, "price_usd_per_ton", 300) or 300),
                input_costs_per_ha=950.0,
            )
        except Exception:
            y_ref = {"predicted_yield_t_ha": None, "yield_range_95": None}
            p_ref = {}

        # Quantitative Value of Information (VoI)
        support = state_support_ledger or {}
        thermal_withheld = (support.get("thermal_stress") or {}).get("support_status") == "unsupported"
        salinity_withheld = (support.get("salinity_stress") or {}).get("support_status") == "unsupported"
        biotic_withheld = (support.get("biotic_confounder_risk") or {}).get("support_status") == "unsupported"
        voi_candidates = [
            {
                "observation_type": "in_situ_soil_moisture_probe",
                "voi_score": round(min(1.0, 2.8 * rzw_sig + 0.35 * refined_water_prob + (0.20 if contradictions else 0.0)), 4),
                "reduces_uncertainty_for": ["root_zone_water", "layer3_water_balance"],
                "rationale": "Resolves L3 multi-layer soil balance vs SAR-inferred root-zone water ambiguity.",
            },
            {
                "observation_type": "leaf_tissue_and_soil_ec_lab_assay",
                "voi_score": round(min(1.0, (0.30 if salinity_withheld else 0.05) + 0.55 * n_prob_ref + (0.25 if vigor_anom < -0.10 else 0.0)), 4),
                "reduces_uncertainty_for": ["chlorophyll", "salinity_stress", "layer4_nutrients"],
                "rationale": "Separates nitrogen NNI limitation & soil salinity EC from drought stress.",
            },
            {
                "observation_type": "field_scouting_and_leaf_pathology",
                "voi_score": round(min(1.0, (0.20 if biotic_withheld else 0.05) + 0.65 * float(l5_pre.get("weather_disease_suitability", 0.0) or 0.0)), 4),
                "reduces_uncertainty_for": ["biotic_confounder_risk", "layer5_biotic"],
                "rationale": "Confirms or refutes weather/dew-suitable fungal or pest infection.",
            },
            {
                "observation_type": "drone_thermal_multispectral_flight",
                "voi_score": round(min(1.0, (0.25 if thermal_withheld else 0.05) + 0.015 * min(30.0, gap_days) + 1.5 * v_sig), 4),
                "reduces_uncertainty_for": ["thermal_stress", "vigor", "canopy_water"],
                "rationale": "Supplies sub-canopy thermal state and bridges satellite cloud gaps.",
            },
            {
                "observation_type": "crop_identity_and_cycle_confirmation",
                "voi_score": round(
                    min(
                        1.0,
                        0.15
                        + 0.70 * float((crop_context or {}).get("unknown_probability", 0.0) or 0.0)
                        + (0.20 if not (crop_context or {}).get("crop_identity_verified", False) else 0.0),
                    ),
                    4,
                ),
                "reduces_uncertainty_for": ["crop_identity", "phenology_progress", "layer2_vegetation"],
                "rationale": "Confirms active crop species, planting date, or rotation break to collapse crop-parameter mixture uncertainty.",
            },
        ]
        voi_candidates.sort(key=lambda item: item["voi_score"], reverse=True)

        try:
            comp_ref = self._risk_comp.calculate_composite_risk(
                water_stress_prob=round(refined_water_prob * 100.0, 2),
                nutrient_stress_prob=round(n_prob_ref * 100.0, 2),
                disease_risk_prob=round(float(l5_pre.get("weather_disease_suitability", 0.0) or 0.0) * 100.0, 2),
                climate_shock_prob=round(float(l7_pre.get("climate_shock_risk", 0.0) or 0.0) * 100.0, 2),
                stage_label=str(l2_pre.get("phenology_stage") or "UNKNOWN"),
            )
        except Exception:
            comp_ref = {"composite_risk_score": 0.0, "risk_level": "low"}

        return {
            "contract_version": CROSS_LAYER_CONTRACT_VERSION,
            "observation_role": "refined_specialist_output_non_assimilable",
            "eligible_for_asmae_assimilation": False,
            "layer8_constraints_only": True,
            "observation_time": pre_bundle.get("observation_time"),
            "knowledge_cutoff": pre_bundle.get("knowledge_cutoff"),
            "cross_layer_agreement": "contradiction_detected" if contradictions else "consistent",
            "contradictions": contradictions,
            "trust_monitor": trust_conflict,
            "competing_attribution": competing_attribution,
            "ranked_stress_mechanisms": ranked_mechanisms,
            "next_best_observation": voi_candidates[0],
            "value_of_information_ranking": voi_candidates,
            "engines_executed": [
                "PhenologyDevelopmentRate", "NDMIWaterStressModel", "TemperatureThermalStressModel",
                "TemporalAnomalyEngine", "PenmanMonteithET0", "DualKcEngine", "SoilProfileDatabase",
                "RootZoneAvailabilityEngine", "LayeredWaterBalanceEngine", "WaterLimitationEngine",
                "SoilRespirationEngine", "CropDemandUptakeEngine", "PhotosynthesisNUEEngine",
                "EnvironmentalLossEngine", "NitrogenDeficiencyEngine", "SalinityEngine",
                "BiophysicalCanopyEnergyBalanceSolver", "BioThreatInferenceEngine",
                "YieldForecastEngine", "ProfitabilityCalculator",
                "ClimateShockEngine", "RiskCompositeEngine", "TrustMonitor",
                "PhenologyDosingEngine", "SprayDriftGateEngine", "FrostSprinklingEngine",
                "CropCoolingEngine", "TillageCompactionEngine", "VolatilizationInhibitorEngine", "SalinityLeachingEngine",
            ],
            "layers_refined": {
                "layer2_vegetation": {
                    "phenology_stage": l2_pre.get("phenology_stage"),
                    "growth_position": l2_pre.get("growth_position"),
                    "expected_vigor": exp_vigor,
                    "posterior_vigor": round(v_post, 4),
                    "posterior_lai": round(lai_post, 4),
                    "vigor_anomaly_vs_phenology": vigor_anom,
                    "detected_temporal_anomalies": l2_pre.get("detected_temporal_anomalies", []),
                    "observation_role": "refined_specialist_output_non_assimilable",
                },
                "layer3_water": {
                    "et0": l3_pre.get("et0"),
                    "et0_sigma": l3_pre.get("et0_sigma"),
                    "vpd_kpa": l3_pre.get("vpd_kpa"),
                    "kcb": l3_pre.get("kcb"),
                    "ke": l3_pre.get("ke"),
                    "layer_theta_profile": l3_pre.get("layer_theta_profile"),
                    "pre_asmae_water_limitation_prob": l3_lim,
                    "refined_water_stress_prob": refined_water_prob,
                    "posterior_root_zone_water": round(rzw_post, 4),
                    "posterior_canopy_water": round(cw_post, 4),
                    "observation_role": "refined_specialist_output_non_assimilable",
                },
                "layer4_nutrients": {
                    "refined_n_deficiency_prob": n_prob_ref,
                    "severity": n_ref.get("severity"),
                    "water_gating_applied": n_ref.get("water_gating_applied"),
                    "nitrogen_nutrition_index": nni_ref,
                    "rue_actual": rue_actual,
                    "soil_n_mineralization_kg_ha": l4_pre.get("soil_n_mineralization_kg_ha"),
                    "n_environmental_loss_fraction": l4_pre.get("n_environmental_loss_fraction"),
                    "salinity_risk": l4_pre.get("salinity_risk"),
                    "missing_inputs": l4_pre.get("missing_inputs", []),
                    "observation_role": "refined_specialist_output_non_assimilable",
                },
                "layer5_biotic": {
                    "canopy_t_leaf_c": l5_pre.get("canopy_t_leaf_c"),
                    "leaf_wetness_condensation_index": l5_pre.get("leaf_wetness_condensation_index"),
                    "top_threat_hypothesis": l5_pre.get("top_threat_hypothesis"),
                    "top_threat_posterior_prob": l5_pre.get("top_threat_posterior_prob"),
                    "threat_probabilities": l5_pre.get("threat_probabilities", {}),
                    "weather_disease_suitability": l5_pre.get("weather_disease_suitability"),
                    "is_unconfirmed_confounder_only": True,
                    "missing_inputs": l5_pre.get("missing_inputs", []),
                    "observation_role": "refined_specialist_output_non_assimilable",
                },
                "layer6_yield": {
                    "predicted_yield_t_ha": y_ref.get("predicted_yield_t_ha"),
                    "yield_range_95": y_ref.get("yield_range_95"),
                    "expected_profit_usd_ha": p_ref.get("profit_usd_ha"),
                    "break_even_yield_t_ha": p_ref.get("break_even_yield"),
                    "observation_role": "refined_specialist_output_non_assimilable",
                },
                "layer7_risk": {
                    "climate_shock_risk": l7_pre.get("climate_shock_risk"),
                    "refined_composite_risk_score": round(float(comp_ref.get("composite_risk_score", 0.0) or 0.0) / 100.0, 4),
                    "risk_level": comp_ref.get("risk_level", "low"),
                    "observation_role": "refined_specialist_output_non_assimilable",
                },
                "layer8_constraints": {
                    **l8_pre,
                    "is_constraint_only": True,
                    "never_physical_ground_truth": True,
                    "contains_recommendations": False,
                },
            },
        }
