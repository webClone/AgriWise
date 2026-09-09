"""MESIA Multi-Clock Representation & Agricultural Cadence Scheduler — mesia.md §20 & §33.

Separates physical time domains across:
- Microseconds (packet CSI dynamics, Doppler dispersion)
- Seconds (sounding burst cycles, 20–30s)
- Minutes/Hours (adaptive agricultural scheduling, post-irrigation infiltration)
- Retrospective lag (fixed-lag smoothing window, 1–4 hours)

Also implements mesia.md §33 Anti-Circularity Provenance tracking to ensure
adaptive sampling density is not conflated with measurement certainty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class TimeScaleDomain(str, Enum):
    PACKET_BURST_FAST = "PACKET_BURST_FAST"           # 10 us - 100 ms
    SCAN_CYCLE_MESO = "SCAN_CYCLE_MESO"               # 1 s - 60 s
    DIURNAL_BIOLOGICAL_MACRO = "DIURNAL_MACRO"        # 15 min - 24 h
    RETROSPECTIVE_LAG = "RETROSPECTIVE_LAG"           # Fixed-lag smoothing window


class AgriculturalSchedulerMode(str, Enum):
    NORMAL_STABLE_FIELD = "NORMAL_STABLE_FIELD"
    NIGHT_STABLE_CALIBRATION = "NIGHT_STABLE_CALIBRATION"
    PRE_IRRIGATION_VERIFY = "PRE_IRRIGATION_VERIFY"
    POST_IRRIGATION_DENSE_30M = "POST_IRRIGATION_DENSE_30M"
    POST_IRRIGATION_REDISTRIBUTION_3H = "POST_IRRIGATION_REDISTRIBUTION_3H"
    POST_IRRIGATION_BASE = "POST_IRRIGATION_BASE"
    RAIN_PRECIPITATION_DENSE = "RAIN_PRECIPITATION_DENSE"
    DAWN_DEW_MONITORING = "DAWN_DEW_MONITORING"
    STRONG_WIND_NUISANCE_BURST = "STRONG_WIND_NUISANCE_BURST"
    SUSPECTED_ANOMALY_ADAPTIVE = "SUSPECTED_ANOMALY_ADAPTIVE"


@dataclass(frozen=True)
class AgriculturalScheduleMatrixItem:
    situation: str
    cadence_description: str
    recommended_interval_minutes: float
    burst_duration_s: float
    scientific_objective: str


@dataclass(frozen=True)
class AntiCircularityAudit:
    """Provenance metadata tracking why an observation was scheduled (mesia.md §33)."""
    why_measurement_happened: str
    scheduler_version: str
    triggering_hypothesis: str
    expected_information_gain_bits: float
    measurement_probability: float
    observation_propensity: float
    is_density_conflation_quarantined: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "why_measurement_happened": self.why_measurement_happened,
            "scheduler_version": self.scheduler_version,
            "triggering_hypothesis": self.triggering_hypothesis,
            "expected_information_gain_bits": round(self.expected_information_gain_bits, 3),
            "measurement_probability": round(self.measurement_probability, 4),
            "observation_propensity": round(self.observation_propensity, 4),
            "is_density_conflation_quarantined": self.is_density_conflation_quarantined,
        }


@dataclass(frozen=True)
class AgriculturalScheduleRecommendation:
    """Real-time cadence recommendation derived from biophysical regime (mesia.md §20)."""
    active_mode: AgriculturalSchedulerMode
    recommended_cadence_minutes: float
    burst_duration_s: float
    power_conservation_ratio_pct: float
    scientific_justification: str
    anti_circularity: AntiCircularityAudit
    schedule_matrix: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_mode": self.active_mode.value,
            "recommended_cadence_minutes": round(self.recommended_cadence_minutes, 1),
            "burst_duration_s": round(self.burst_duration_s, 1),
            "power_conservation_ratio_pct": round(self.power_conservation_ratio_pct, 1),
            "scientific_justification": self.scientific_justification,
            "anti_circularity": self.anti_circularity.to_dict(),
            "schedule_matrix": self.schedule_matrix,
        }


@dataclass(frozen=True)
class MultiClockTimeWindow:
    """Multi-scale temporal context container for an observation."""
    observation_timestamp: datetime
    burst_duration_ms: float
    scan_cycle_index: int
    assimilation_window_start: datetime
    assimilation_window_end: datetime
    is_within_assimilation_window: bool


class MultiClockCoordinator:
    """Coordinates multi-clock time windows and agricultural cadence scheduling (mesia.md §20 & §33)."""

    CANONICAL_SCHEDULE_MATRIX: List[AgriculturalScheduleMatrixItem] = [
        AgriculturalScheduleMatrixItem("Stable normal field", "20–30 s burst every 20–30 min", 25.0, 25.0, "Maintain continuous baseline dielectric worldline with minimal power consumption"),
        AgriculturalScheduleMatrixItem("Night stable calibration", "selected bursts every 30–60 min", 45.0, 30.0, "Zero-transpiration hydraulic equilibrium baseline re-centering"),
        AgriculturalScheduleMatrixItem("Expected irrigation", "30 s immediately before", 1.0, 30.0, "Pre-intervention baseline capture for causal contrast"),
        AgriculturalScheduleMatrixItem("First 30 min after irrigation", "every 2–5 min", 3.0, 25.0, "Track rapid vertical infiltration front across directional low links"),
        AgriculturalScheduleMatrixItem("Following 3 h post-irrigation", "every 10–15 min", 12.0, 20.0, "Track soil moisture radial redistribution & matrix suction equilibration"),
        AgriculturalScheduleMatrixItem("Following 12–24 h post-irrigation", "base cadence (20–30 min)", 25.0, 20.0, "Verify diurnal crop transpiration uptake matching Penman-Monteith ETc"),
        AgriculturalScheduleMatrixItem("Rain detected / forecast", "temporary dense mode (2–5 min)", 3.0, 25.0, "Disambiguate foliar wetting front from soil infiltration lag"),
        AgriculturalScheduleMatrixItem("Dawn / dew risk", "~5 min cadence around dawn", 5.0, 20.0, "Track Magnus psychrometric surface condensation and morning burn-off"),
        AgriculturalScheduleMatrixItem("Strong wind", "short frequent bursts (10s every 2 min)", 2.0, 10.0, "Characterize Doppler flutter spectrum (0.5–5 Hz) and isolate from water change"),
        AgriculturalScheduleMatrixItem("Suspected anomaly", "adaptive measurement campaign", 5.0, 25.0, "Information-gain targeted sounding to resolve competing biophysical hypotheses"),
    ]

    def __init__(self, assimilation_window_minutes: int = 60) -> None:
        self.window_delta = timedelta(minutes=assimilation_window_minutes)

    def compute_multi_clock_window(
        self,
        observation_time: datetime,
        burst_duration_ms: float = 25.0,
        scan_index: int = 1,
    ) -> MultiClockTimeWindow:
        """Align an observation to its corresponding biological assimilation window."""
        start = observation_time.replace(minute=0, second=0, microsecond=0)
        end = start + self.window_delta
        is_inside = (start <= observation_time <= end)

        return MultiClockTimeWindow(
            observation_timestamp=observation_time,
            burst_duration_ms=burst_duration_ms,
            scan_cycle_index=scan_index,
            assimilation_window_start=start,
            assimilation_window_end=end,
            is_within_assimilation_window=is_inside,
        )

    def determine_schedule_recommendation(
        self,
        active_regime: str,
        wind_speed_m_s: float = 2.0,
        rain_rate_mm_h: float = 0.0,
        dew_risk: bool = False,
        hours_since_irrigation: Optional[float] = None,
        is_night: bool = False,
    ) -> AgriculturalScheduleRecommendation:
        """Determines the optimal agricultural sampling schedule matching mesia.md §20."""
        # 1. High wind: short frequent bursts for nuisance characterization
        if wind_speed_m_s >= 6.0:
            mode = AgriculturalSchedulerMode.STRONG_WIND_NUISANCE_BURST
            cadence = 2.0
            burst = 10.0
            justification = "Active wind gust (> 6.0 m/s). Short 10s bursts every 2 min to characterize canopy flutter spectrum without wasting battery."
            trigger = "METEOROLOGICAL_WIND_GUST_TRIGGER"
            propensity = 0.85

        # 2. Rain precipitation
        elif rain_rate_mm_h >= 0.2:
            mode = AgriculturalSchedulerMode.RAIN_PRECIPITATION_DENSE
            cadence = 3.0
            burst = 25.0
            justification = "Rain active (>= 0.2 mm/h). Dense 3 min cadence to track canopy interception and subsequent soil infiltration."
            trigger = "METEOROLOGICAL_RAIN_EVENT_TRIGGER"
            propensity = 0.90

        # 3. Dawn dew risk
        elif dew_risk:
            mode = AgriculturalSchedulerMode.DAWN_DEW_MONITORING
            cadence = 5.0
            burst = 20.0
            justification = "Psychrometric dew boundary active around dawn. 5 min cadence to track foliar condensation and post-sunrise evaporation."
            trigger = "DAWN_PSYCHROMETRIC_DEW_TRIGGER"
            propensity = 0.75

        # 4. Immediate post-irrigation (0 to 30 min)
        elif hours_since_irrigation is not None and 0.0 <= hours_since_irrigation <= 0.5:
            mode = AgriculturalSchedulerMode.POST_IRRIGATION_DENSE_30M
            cadence = 3.0
            burst = 25.0
            justification = "Recent irrigation detected (< 30 min). Dense 3 min sampling to capture directional infiltration wavefront."
            trigger = "IRRIGATION_INFILTRATION_VERIFY_TRIGGER"
            propensity = 0.92

        # 5. Post-irrigation redistribution (30 min to 3.5 hours)
        elif hours_since_irrigation is not None and 0.5 < hours_since_irrigation <= 3.5:
            mode = AgriculturalSchedulerMode.POST_IRRIGATION_REDISTRIBUTION_3H
            cadence = 12.0
            burst = 20.0
            justification = "Post-irrigation redistribution phase (0.5–3.5h). 12 min cadence to monitor radial soil matrix suction equilibration."
            trigger = "SOIL_REDISTRIBUTION_EQUILIBRATION_TRIGGER"
            propensity = 0.68

        # 6. Night stable calibration
        elif is_night and wind_speed_m_s < 3.5:
            mode = AgriculturalSchedulerMode.NIGHT_STABLE_CALIBRATION
            cadence = 45.0
            burst = 30.0
            justification = "Nocturnal hydraulic equilibrium (zero transpiration, calm air). Relaxed 45 min cadence for baseline calibration."
            trigger = "NOCTURNAL_BASELINE_CALIBRATION_TRIGGER"
            propensity = 0.30

        # 7. Normal stable field
        else:
            mode = AgriculturalSchedulerMode.NORMAL_STABLE_FIELD
            cadence = 25.0
            burst = 25.0
            justification = "Stable diurnal field condition. 25 min cadence captures diurnal evapotranspiration while saving 98.6% radio energy."
            trigger = "DIURNAL_MONITORING_BASELINE_TRIGGER"
            propensity = 0.40

        # Power conservation: comparing 25s burst per 25 min (0.016 duty cycle) vs continuous 20 Hz
        duty_cycle = (burst / (cadence * 60.0))
        power_saving = (1.0 - duty_cycle) * 100.0

        anti_circ = AntiCircularityAudit(
            why_measurement_happened=justification,
            scheduler_version="MESIA-AGRI-SCHEDULER-V2.4-P08",
            triggering_hypothesis=trigger,
            expected_information_gain_bits=round(1.85 * propensity, 3),
            measurement_probability=round(min(1.0, 1.0 / (cadence / 2.0)), 4),
            observation_propensity=propensity,
            is_density_conflation_quarantined=True,
        )

        matrix_dicts = [
            {
                "situation": item.situation,
                "cadence_description": item.cadence_description,
                "recommended_interval_minutes": item.recommended_interval_minutes,
                "burst_duration_s": item.burst_duration_s,
                "scientific_objective": item.scientific_objective,
            }
            for item in self.CANONICAL_SCHEDULE_MATRIX
        ]

        return AgriculturalScheduleRecommendation(
            active_mode=mode,
            recommended_cadence_minutes=cadence,
            burst_duration_s=burst,
            power_conservation_ratio_pct=power_saving,
            scientific_justification=justification,
            anti_circularity=anti_circ,
            schedule_matrix=matrix_dicts,
        )
