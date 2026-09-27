"""
Intra-Seasonal Multi-Event Detector for ASMAE.
Detects discrete agronomic events within a crop season envelope:
  - Irrigation Events (SAR backscatter / surface moisture surge without rain)
  - Rain Events (precipitation pulses with plot-wide surface wetting)
  - Drought / Water Deficit (cumulative ET0 deficit and root-zone moisture exhaustion)
  - Fertilization Application (rapid chlorophyll / NDRE increase with adequate moisture)
  - Nutrient Deficiency Stress (declining vigor despite sufficient water)
  - Disease Risk / Biotic Stress (pathogen incubation conditions + patchy decline)
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import numpy as np

@dataclass
class SeasonalEventRecord:
    event_id: str
    event_type: str            # "irrigation", "rain", "drought", "fertilization", "nutrient_deficiency", "disease_risk"
    start_date: datetime
    end_date: datetime
    peak_date: datetime
    severity: float            # 0.0 to 1.0
    confidence: float          # 0.0 to 1.0
    sensor_evidence: Dict[str, Any] = field(default_factory=dict)
    symptom_progression: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "peak_date": self.peak_date.isoformat(),
            "severity": round(float(self.severity), 4),
            "confidence": round(float(self.confidence), 4),
            "sensor_evidence": self.sensor_evidence,
            "symptom_progression": self.symptom_progression,
        }


class IntraSeasonalEventDetector:
    def __init__(
        self,
        irrigation_sar_threshold_db: float = 1.8,
        rain_threshold_mm: float = 5.0,
        drought_deficit_threshold_mm: float = 35.0,
        drought_min_days: int = 7,
    ):
        self.irrigation_sar_threshold_db = irrigation_sar_threshold_db
        self.rain_threshold_mm = rain_threshold_mm
        self.drought_deficit_threshold_mm = drought_deficit_threshold_mm
        self.drought_min_days = drought_min_days

    def detect_events(
        self,
        season_id: str,
        start_date: datetime,
        end_date: datetime,
        scenes: List[Dict[str, Any]],
        daily_weather: Dict[str, Dict[str, float]],
        soil_profile: Optional[Dict[str, Any]] = None,
        management_events: Optional[List[Any]] = None,
    ) -> List[SeasonalEventRecord]:
        """
        Detects all discrete events that occurred within the seasonal window.
        """
        events: List[SeasonalEventRecord] = []
        event_idx = 1

        # Sort scenes chronologically
        sorted_scenes = sorted(
            [s for s in scenes if isinstance(s, dict) and "runtime" in s],
            key=lambda s: s["runtime"].acquisition_time
        )

        # Track irrigation from management events (count only qualified delivered irrigation)
        irrigation_by_day: Dict[str, float] = {}
        if management_events:
            for ev in management_events:
                ev_type = str(
                    getattr(ev, "event_type", None)
                    or getattr(ev, "type", None)
                    or (ev.get("type") or ev.get("event_type") if isinstance(ev, dict) else "")
                    or ""
                ).lower()
                if "irrigation" not in ev_type:
                    continue

                ev_status = str(
                    getattr(ev, "status", None)
                    or (ev.get("status") if isinstance(ev, dict) else "applied")
                    or "applied"
                ).lower()
                if ev_status in {"planned", "cancelled", "canceled", "draft", "proposed", "pending", "failed"}:
                    continue

                dt = (
                    getattr(ev, "effective_start", None)
                    or getattr(ev, "timestamp", None)
                    or getattr(ev, "start_date", None)
                    or getattr(ev, "date", None)
                    if not isinstance(ev, dict)
                    else (
                        ev.get("effective_start")
                        or ev.get("timestamp")
                        or ev.get("start_date")
                        or ev.get("date")
                        or ev.get("time")
                    )
                )
                if isinstance(dt, datetime):
                    d_str = dt.strftime("%Y-%m-%d")
                elif isinstance(dt, str):
                    d_str = dt[:10]
                elif hasattr(dt, "strftime"):
                    d_str = dt.strftime("%Y-%m-%d")
                else:
                    continue

                amt = float(
                    getattr(ev, "amount_mm", 0.0)
                    or getattr(ev, "volume_mm", 0.0)
                    or (getattr(ev, "sensor_evidence", {}) or {}).get("irrigation_mm", 0.0)
                    if not isinstance(ev, dict)
                    else (
                        ev.get("amount_mm")
                        or ev.get("volume_mm")
                        or ev.get("depth_mm")
                        or (ev.get("sensor_evidence", {}) or {}).get("irrigation_mm")
                        or 0.0
                    )
                )
                irrigation_by_day[d_str] = irrigation_by_day.get(d_str, 0.0) + amt

        # 1. Weather Timeline & Cumulative Deficit (Drought & Rain Detection)
        weather_days: List[datetime] = []
        curr = start_date
        while curr.date() <= end_date.date():
            weather_days.append(curr)
            curr += timedelta(days=1)

        # Track Rain Events and Drought Windows
        consecutive_deficit_days = 0
        cum_deficit = 0.0
        drought_start_dt: Optional[datetime] = None

        for day_dt in weather_days:
            day_str = day_dt.strftime("%Y-%m-%d")
            w = daily_weather.get(day_str)

            # Preserve missing-weather status: absent weather must NOT be assumed to have zero precip and 3.5mm ET0
            if not w or not isinstance(w, dict):
                # Close any completed observed drought window prior to the missing interval
                if consecutive_deficit_days >= self.drought_min_days and cum_deficit >= self.drought_deficit_threshold_mm and drought_start_dt:
                    events.append(SeasonalEventRecord(
                        event_id=f"{season_id}_drought_{event_idx}",
                        event_type="drought",
                        start_date=drought_start_dt,
                        end_date=day_dt - timedelta(days=1),
                        peak_date=drought_start_dt + timedelta(days=consecutive_deficit_days // 2),
                        severity=min(1.0, cum_deficit / 80.0),
                        confidence=0.75,
                        sensor_evidence={
                            "duration_days": consecutive_deficit_days,
                            "cumulative_deficit_mm": round(cum_deficit, 1)
                        },
                        symptom_progression=[
                            "soil_moisture_depletion",
                            "stomatal_closure",
                        ]
                    ))
                    event_idx += 1
                consecutive_deficit_days = 0
                cum_deficit = 0.0
                drought_start_dt = None
                continue

            raw_precip = (
                w.get("precipitation")
                if w.get("precipitation") is not None
                else (
                    w.get("precip")
                    if w.get("precip") is not None
                    else (
                        w.get("rain")
                        if w.get("rain") is not None
                        else w.get("precipitation_mm")
                    )
                )
            )
            precip = float(raw_precip) if raw_precip is not None else None

            raw_et0 = w.get("et0")
            et0 = float(raw_et0) if raw_et0 is not None else None

            applied_irr = irrigation_by_day.get(day_str, 0.0)

            # Rain detection (only if precipitation is explicitly observed)
            if precip is not None and precip >= self.rain_threshold_mm:
                events.append(SeasonalEventRecord(
                    event_id=f"{season_id}_rain_{event_idx}",
                    event_type="rain",
                    start_date=day_dt,
                    end_date=day_dt + timedelta(days=1),
                    peak_date=day_dt,
                    severity=min(1.0, precip / 50.0),
                    confidence=0.95,
                    sensor_evidence={"precipitation_mm": precip, "et0_mm": et0 if et0 is not None else 0.0},
                    symptom_progression=["surface_saturation", "transpiration_recovery"]
                ))
                event_idx += 1
                # Reset drought accumulator on significant rain
                if precip > 15.0:
                    consecutive_deficit_days = 0
                    cum_deficit = 0.0
                    drought_start_dt = None

            # Reset drought accumulator on significant irrigation
            if applied_irr > 15.0:
                consecutive_deficit_days = 0
                cum_deficit = 0.0
                drought_start_dt = None

            # If either precipitation or ET0 is missing, atmospheric water balance cannot be asserted.
            # Preserve missing status and do not fabricate a drought deficit from unmeasured variables.
            if precip is None or et0 is None:
                if consecutive_deficit_days >= self.drought_min_days and cum_deficit >= self.drought_deficit_threshold_mm and drought_start_dt:
                    events.append(SeasonalEventRecord(
                        event_id=f"{season_id}_drought_{event_idx}",
                        event_type="drought",
                        start_date=drought_start_dt,
                        end_date=day_dt - timedelta(days=1),
                        peak_date=drought_start_dt + timedelta(days=consecutive_deficit_days // 2),
                        severity=min(1.0, cum_deficit / 80.0),
                        confidence=0.75,
                        sensor_evidence={
                            "duration_days": consecutive_deficit_days,
                            "cumulative_deficit_mm": round(cum_deficit, 1)
                        },
                        symptom_progression=[
                            "soil_moisture_depletion",
                            "stomatal_closure",
                        ]
                    ))
                    event_idx += 1
                consecutive_deficit_days = 0
                cum_deficit = 0.0
                drought_start_dt = None
                continue

            total_water_inflow = precip + applied_irr

            # Drought accumulation accounting for precipitation, irrigation, and valid zero ET0
            net_deficit = max(0.0, et0 - total_water_inflow)
            if net_deficit > 1.5:
                if consecutive_deficit_days == 0:
                    drought_start_dt = day_dt
                consecutive_deficit_days += 1
                cum_deficit += net_deficit
            else:
                if consecutive_deficit_days >= self.drought_min_days and cum_deficit >= self.drought_deficit_threshold_mm and drought_start_dt:
                    events.append(SeasonalEventRecord(
                        event_id=f"{season_id}_drought_{event_idx}",
                        event_type="drought",
                        start_date=drought_start_dt,
                        end_date=day_dt,
                        peak_date=drought_start_dt + timedelta(days=consecutive_deficit_days // 2),
                        severity=min(1.0, cum_deficit / 80.0),
                        confidence=0.75,
                        sensor_evidence={
                            "duration_days": consecutive_deficit_days,
                            "cumulative_deficit_mm": round(cum_deficit, 1)
                        },
                        symptom_progression=[
                            "soil_moisture_depletion",
                            "stomatal_closure",
                            "thermal_elevation",
                            "lai_stagnation"
                        ]
                    ))
                    event_idx += 1
                consecutive_deficit_days = 0
                cum_deficit = 0.0
                drought_start_dt = None

        # Check trailing drought at end of season
        if consecutive_deficit_days >= self.drought_min_days and cum_deficit >= self.drought_deficit_threshold_mm and drought_start_dt:
            events.append(SeasonalEventRecord(
                event_id=f"{season_id}_drought_{event_idx}",
                event_type="drought",
                start_date=drought_start_dt,
                end_date=weather_days[-1],
                peak_date=drought_start_dt + timedelta(days=consecutive_deficit_days // 2),
                severity=min(1.0, cum_deficit / 80.0),
                confidence=0.75,
                sensor_evidence={
                    "duration_days": consecutive_deficit_days,
                    "cumulative_deficit_mm": round(cum_deficit, 1)
                },
                symptom_progression=[
                    "soil_moisture_depletion",
                    "stomatal_closure",
                    "thermal_elevation",
                    "lai_stagnation"
                ]
            ))
            event_idx += 1

        # 2. SAR / Optical Multi-Sensor Analysis: Irrigation & Nutrient & Biotic Events
        s1_scenes = [s for s in sorted_scenes if s["runtime"].sensor in ("S1", "SENTINEL1")]
        s2_scenes = [s for s in sorted_scenes if s["runtime"].sensor in ("S2", "SENTINEL2")]

        # Irrigation Detection via SAR delta backscatter
        for i in range(1, len(s1_scenes)):
            prev_s = s1_scenes[i - 1]
            curr_s = s1_scenes[i]

            prev_vv = self._extract_scalar(prev_s["runtime"].bands.get("vv"))
            curr_vv = self._extract_scalar(curr_s["runtime"].bands.get("vv"))

            if prev_vv is not None and curr_vv is not None:
                delta_vv = curr_vv - prev_vv
                acq_dt = curr_s["runtime"].acquisition_time
                day_str = acq_dt.strftime("%Y-%m-%d")
                recent_precip = sum(
                    float(daily_weather.get((acq_dt - timedelta(days=d)).strftime("%Y-%m-%d"), {}).get("precipitation", 0.0) or 0.0)
                    for d in range(3)
                )

                # Significant backscatter surge without corresponding rain indicates irrigation
                if delta_vv >= self.irrigation_sar_threshold_db and recent_precip < 2.0:
                    events.append(SeasonalEventRecord(
                        event_id=f"{season_id}_irrigation_{event_idx}",
                        event_type="irrigation",
                        start_date=prev_s["runtime"].acquisition_time,
                        end_date=acq_dt + timedelta(days=2),
                        peak_date=acq_dt,
                        severity=min(1.0, delta_vv / 4.0),
                        confidence=0.85,
                        sensor_evidence={
                            "delta_vv_db": round(float(delta_vv), 2),
                            "recent_precip_mm": round(float(recent_precip), 1),
                            "source": "sentinel1_sar"
                        },
                        symptom_progression=[
                            "surface_wetting",
                            "root_zone_refill",
                            "transpiration_surge",
                            "vigor_acceleration"
                        ]
                    ))
                    event_idx += 1

        # Optical Trajectory: Fertilization vs Nutrient Deficiency vs Disease
        for i in range(1, len(s2_scenes)):
            prev_s = s2_scenes[i - 1]
            curr_s = s2_scenes[i]

            prev_ndvi = self._extract_scalar(prev_s["runtime"].bands.get("ndvi"))
            curr_ndvi = self._extract_scalar(curr_s["runtime"].bands.get("ndvi"))
            curr_ndre = self._extract_scalar(curr_s["runtime"].bands.get("ndre"))
            curr_ndmi = self._extract_scalar(curr_s["runtime"].bands.get("ndmi"))

            acq_dt = curr_s["runtime"].acquisition_time
            days_gap = max(1, (acq_dt - prev_s["runtime"].acquisition_time).days)

            if prev_ndvi is not None and curr_ndvi is not None:
                delta_ndvi = curr_ndvi - prev_ndvi

                # Rapid vigor acceleration during vegetative window with adequate moisture -> Fertilization
                if delta_ndvi >= 0.12 and days_gap <= 15:
                    events.append(SeasonalEventRecord(
                        event_id=f"{season_id}_fertilization_{event_idx}",
                        event_type="fertilization",
                        start_date=prev_s["runtime"].acquisition_time,
                        end_date=acq_dt + timedelta(days=5),
                        peak_date=acq_dt,
                        severity=min(1.0, delta_ndvi / 0.25),
                        confidence=0.80,
                        sensor_evidence={
                            "delta_ndvi": round(float(delta_ndvi), 3),
                            "days_gap": days_gap,
                            "source": "sentinel2_optical"
                        },
                        symptom_progression=[
                            "chlorophyll_surge",
                            "leaf_greenness_increase",
                            "biomass_rate_increase"
                        ]
                    ))
                    event_idx += 1

                # Drop in NDVI while moisture is adequate (NDMI > 0.05) -> Nutrient Deficiency
                elif delta_ndvi <= -0.10 and days_gap <= 20 and (curr_ndmi is None or curr_ndmi >= 0.05):
                    events.append(SeasonalEventRecord(
                        event_id=f"{season_id}_nutrient_def_{event_idx}",
                        event_type="nutrient_deficiency",
                        start_date=prev_s["runtime"].acquisition_time,
                        end_date=acq_dt + timedelta(days=7),
                        peak_date=acq_dt,
                        severity=min(1.0, abs(delta_ndvi) / 0.25),
                        confidence=0.75,
                        sensor_evidence={
                            "delta_ndvi": round(float(delta_ndvi), 3),
                            "ndmi_observed": round(float(curr_ndmi or 0.0), 3),
                            "water_stress_absent": True
                        },
                        symptom_progression=[
                            "leaf_yellowing",
                            "chlorophyll_breakdown",
                            "photosynthetic_rate_decline"
                        ]
                    ))
                    event_idx += 1

        # Disease Risk Pre-Conditions (Favorable Humidity & Wetness)
        high_humidity_streak = 0
        disease_start_dt: Optional[datetime] = None
        for day_dt in weather_days:
            day_str = day_dt.strftime("%Y-%m-%d")
            w = daily_weather.get(day_str, {})
            rh = float(w.get("rh_mean", 60.0) or 60.0)
            t_mean = (float(w.get("temp_max", 22.0) or 22.0) + float(w.get("temp_min", 14.0) or 14.0)) / 2.0
            precip = float(w.get("precipitation", 0.0) or 0.0)

            # High humidity (RH > 80% or continuous rain) + mild temperatures (15-26°C)
            if (rh >= 80.0 or precip >= 2.0) and (15.0 <= t_mean <= 26.0):
                if high_humidity_streak == 0:
                    disease_start_dt = day_dt
                high_humidity_streak += 1
            else:
                if high_humidity_streak >= 3 and disease_start_dt:
                    events.append(SeasonalEventRecord(
                        event_id=f"{season_id}_disease_risk_{event_idx}",
                        event_type="disease_risk",
                        start_date=disease_start_dt,
                        end_date=day_dt,
                        peak_date=disease_start_dt + timedelta(days=high_humidity_streak // 2),
                        severity=min(1.0, high_humidity_streak / 7.0),
                        confidence=0.70,
                        sensor_evidence={
                            "favorable_streak_days": high_humidity_streak,
                            "mean_temp_c": round(t_mean, 1)
                        },
                        symptom_progression=[
                            "canopy_wetness_incubation",
                            "localized_lesion_development",
                            "patchy_chlorosis"
                        ]
                    ))
                    event_idx += 1
                high_humidity_streak = 0
                disease_start_dt = None

        return events

    @staticmethod
    def _extract_scalar(val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            arr = np.asarray(val, dtype=float)
            finite = arr[np.isfinite(arr)]
            return float(np.mean(finite)) if finite.size else None
        except Exception:
            return None
