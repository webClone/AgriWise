
"""
Layer 2.2: Phenology Inference Engine (v3.1)

Infers the biological stage of the crop using a Hidden Markov Model
with Viterbi decoding.

Enhancements over v3.0:
  - Crop-specific emission tuning from CROP_NDVI_SIGNATURES
  - Photoperiod-aware transition gating (latitude + DOY → day length)
  - Improved confidence calibration

Algorithm:
  - States: BARE_SOIL, EMERGENCE, VEGETATIVE, REPRODUCTIVE, SENESCENCE,
            HARVESTED, DORMANCY (perennials only)
  - Emissions: Multivariate Gaussian on (NDVI, velocity, GDD_frac, NDWI, photoperiod)
  - Transitions: GDD-gated probability matrix with min-duration penalty
  - Decoding: Viterbi (log-space) with O(n × S²) complexity

References:
  - Rabiner (1989) "A Tutorial on HMMs"
  - Wardlow & Egbert (2008) "Large-area crop mapping using MODIS"
  - Bolton & Friedl (2013) "Forecasting crop yield using MODIS EVI"
"""

import math
from typing import List, Dict, Optional, Tuple
from layer2_veg_int.schema import PhenologyStage


# =========================================================================
# Default Emission Parameters (per-stage Gaussian means and std devs)
# =========================================================================
# Each stage has expected (mean, sigma) for 5 features:
#   [NDVI, velocity, GDD_fraction, NDWI_proxy, photoperiod_hours]

_DEFAULT_EMISSION_PARAMS = {
    PhenologyStage.BARE_SOIL: {
        "ndvi": (0.12, 0.06), "velocity": (0.000, 0.005),
        "gdd_frac": (0.00, 0.05), "ndwi": (-0.30, 0.10),
        "photoperiod": (10.0, 3.0),
    },
    PhenologyStage.EMERGENCE: {
        "ndvi": (0.25, 0.08), "velocity": (0.010, 0.008),
        "gdd_frac": (0.08, 0.06), "ndwi": (-0.20, 0.10),
        "photoperiod": (11.0, 2.0),
    },
    PhenologyStage.VEGETATIVE: {
        "ndvi": (0.55, 0.12), "velocity": (0.008, 0.006),
        "gdd_frac": (0.30, 0.15), "ndwi": (-0.05, 0.12),
        "photoperiod": (13.0, 2.0),
    },
    PhenologyStage.REPRODUCTIVE: {
        "ndvi": (0.72, 0.10), "velocity": (0.000, 0.005),
        "gdd_frac": (0.55, 0.15), "ndwi": (0.05, 0.10),
        "photoperiod": (14.0, 2.0),
    },
    PhenologyStage.SENESCENCE: {
        "ndvi": (0.40, 0.12), "velocity": (-0.008, 0.006),
        "gdd_frac": (0.80, 0.15), "ndwi": (-0.15, 0.10),
        "photoperiod": (12.0, 2.0),
    },
    PhenologyStage.HARVESTED: {
        "ndvi": (0.15, 0.06), "velocity": (-0.002, 0.005),
        "gdd_frac": (0.95, 0.10), "ndwi": (-0.30, 0.10),
        "photoperiod": (11.0, 3.0),
    },
    PhenologyStage.DORMANCY: {
        "ndvi": (0.35, 0.10), "velocity": (0.000, 0.003),
        "gdd_frac": (0.00, 0.10), "ndwi": (-0.15, 0.10),
        "photoperiod": (9.5, 2.0),
    },
}


# =========================================================================
# State Lists
# =========================================================================
_ANNUAL_STATES = [
    PhenologyStage.BARE_SOIL,
    PhenologyStage.EMERGENCE,
    PhenologyStage.VEGETATIVE,
    PhenologyStage.REPRODUCTIVE,
    PhenologyStage.SENESCENCE,
    PhenologyStage.HARVESTED,
]


class PhenologyEngine:

    def __init__(self, crop_config: Optional[Dict] = None, is_perennial: bool = False,
                 crop_ndvi_signature: Optional[Dict] = None,
                 latitude: Optional[float] = None):
        """Initialize the phenology engine.

        Args:
            crop_config: GDD transition thresholds.
            is_perennial: Whether the crop cycles through DORMANCY.
            crop_ndvi_signature: NDVI signature dict (peak_ndvi, trough_ndvi, etc.)
                from CROP_NDVI_SIGNATURES for crop-specific emission tuning.
            latitude: Field latitude in degrees for photoperiod computation.
        """
        # Default Wheat/Barley Priors (Generic Cereal)
        self.crop_priors = crop_config or {
            "name": "Generic Cereal",
            "gdd_base_temp": 0.0,
            "transitions": {
                "emergence_min_gdd": 100,
                "vegetative_min_gdd": 300,
                "reproductive_min_gdd": 800,
                "senescence_min_gdd": 1400,
                "harvest_min_gdd": 1800,
            },
        }
        self.is_perennial = is_perennial
        self.latitude = latitude

        # State list
        self.states = list(_ANNUAL_STATES)
        if is_perennial:
            # Replace BARE_SOIL with DORMANCY, remove HARVESTED
            self.states = [
                PhenologyStage.DORMANCY,
                PhenologyStage.EMERGENCE,
                PhenologyStage.VEGETATIVE,
                PhenologyStage.REPRODUCTIVE,
                PhenologyStage.SENESCENCE,
            ]

        self.n_states = len(self.states)
        self.state_idx = {s: i for i, s in enumerate(self.states)}

        # Build emission parameters (crop-specific or default)
        self._emission_params = self._build_emission_params(crop_ndvi_signature)

        # Build transition matrix
        self._build_transition_matrix()

        # Minimum duration per state (in timesteps, ~days)
        self.min_duration = {
            PhenologyStage.BARE_SOIL: 5,
            PhenologyStage.EMERGENCE: 7,
            PhenologyStage.VEGETATIVE: 14,
            PhenologyStage.REPRODUCTIVE: 10,
            PhenologyStage.SENESCENCE: 7,
            PhenologyStage.HARVESTED: 5,
            PhenologyStage.DORMANCY: 14,
        }

    def _build_emission_params(self, crop_sig: Optional[Dict]) -> Dict:
        """Build crop-specific emission parameters from NDVI signature.

        Uses CROP_NDVI_SIGNATURES (peak_ndvi, trough_ndvi) to adapt the
        HMM emission means so that the phenology detection is crop-aware.

        For example, olive at NDVI=0.55 is REPRODUCTIVE (peak), but wheat
        at NDVI=0.55 is only VEGETATIVE (growing phase).
        """
        params = {}
        for stage, defaults in _DEFAULT_EMISSION_PARAMS.items():
            params[stage] = dict(defaults)  # Shallow copy

        if not crop_sig:
            return params

        peak = crop_sig.get("peak_ndvi")
        trough = crop_sig.get("trough_ndvi")

        if peak is None or trough is None:
            return params

        # Adapt NDVI emission means to crop-specific ranges
        mid = (peak + trough) / 2.0
        sigma_scale = max(0.06, (peak - trough) * 0.15)

        params[PhenologyStage.BARE_SOIL]["ndvi"] = (trough, 0.06)
        params[PhenologyStage.EMERGENCE]["ndvi"] = (trough + 0.3 * (peak - trough), sigma_scale)
        params[PhenologyStage.VEGETATIVE]["ndvi"] = (mid, sigma_scale * 1.2)
        params[PhenologyStage.REPRODUCTIVE]["ndvi"] = (peak, sigma_scale)
        params[PhenologyStage.SENESCENCE]["ndvi"] = (mid, sigma_scale * 1.2)
        params[PhenologyStage.HARVESTED]["ndvi"] = (trough + 0.05, 0.06)
        params[PhenologyStage.DORMANCY]["ndvi"] = (trough + 0.5 * (peak - trough), sigma_scale)

        # Adapt velocity based on greenup_rate if available
        gr = crop_sig.get("greenup_rate", 0.006)
        params[PhenologyStage.EMERGENCE]["velocity"] = (gr, gr * 0.8)
        params[PhenologyStage.VEGETATIVE]["velocity"] = (gr * 0.8, gr * 0.6)
        params[PhenologyStage.SENESCENCE]["velocity"] = (-gr, gr * 0.6)

        return params

    def _build_transition_matrix(self):
        """Build log-space transition probability matrix.

        Enforces monotonic progression (no skipping stages) with
        high self-loop probability (crops stay in each stage for
        many timesteps).
        """
        S = self.n_states
        # Initialize with very low probability (log space)
        self.log_trans = [[-20.0] * S for _ in range(S)]

        for i in range(S):
            # Self-loop: high probability (crop stays in current stage)
            self.log_trans[i][i] = math.log(0.92)

            # Forward transition: moderate probability
            if i + 1 < S:
                self.log_trans[i][i + 1] = math.log(0.08)

        # Perennial: allow cycle back from SENESCENCE to DORMANCY
        if self.is_perennial:
            sen_idx = self.state_idx.get(PhenologyStage.SENESCENCE)
            dor_idx = self.state_idx.get(PhenologyStage.DORMANCY)
            if sen_idx is not None and dor_idx is not None:
                self.log_trans[sen_idx][dor_idx] = math.log(0.06)
                self.log_trans[sen_idx][sen_idx] = math.log(0.86)
        else:
            # Annual: HARVESTED can go to BARE_SOIL
            harv_idx = self.state_idx.get(PhenologyStage.HARVESTED)
            bare_idx = self.state_idx.get(PhenologyStage.BARE_SOIL)
            if harv_idx is not None and bare_idx is not None:
                self.log_trans[harv_idx][bare_idx] = math.log(0.05)
                self.log_trans[harv_idx][harv_idx] = math.log(0.87)

    # =====================================================================
    # Photoperiod Computation
    # =====================================================================

    def _compute_photoperiod(self, date_str: str) -> Optional[float]:
        """Compute day length (hours) from latitude and date.

        Uses simplified astronomical formula (Brock 1981).
        """
        if self.latitude is None:
            return None
        try:
            # Extract DOY from date string
            parts = date_str.split("-")
            if len(parts) >= 3:
                from datetime import date as dt_date
                d = dt_date(int(parts[0]), int(parts[1]), int(parts[2]))
                doy = d.timetuple().tm_yday
            else:
                doy = 172  # Default to summer solstice
        except Exception:
            doy = 172

        lat_rad = math.radians(self.latitude)
        # Solar declination
        decl = 0.4093 * math.sin(2 * math.pi * (284 + doy) / 365)
        # Hour angle at sunrise/sunset
        cos_ha = -math.tan(lat_rad) * math.tan(decl)
        cos_ha = max(-1.0, min(1.0, cos_ha))
        day_length = 24.0 * math.acos(cos_ha) / math.pi
        return day_length

    # =====================================================================
    # Viterbi Decoding
    # =====================================================================

    def infer_daily_stages(
        self,
        modeled_ndvi: List[float],
        velocity: List[float],
        dates: List[str],
        cumulative_gdd: List[float],
        uncertainty: List[float] = None,
        high_res_visual_check: List[bool] = None,
        initial_stage: Optional[str] = None,
        initial_gdd: float = 0.0,
        ndwi_series: Optional[List[Optional[float]]] = None,
    ) -> Tuple[List[PhenologyStage], List[float]]:
        """
        Infers phenological stage using Viterbi decoding on the HMM.

        Multivariate emission features: (NDVI, velocity, GDD_frac, NDWI, photoperiod)
        """
        T = len(modeled_ndvi)
        if T == 0:
            return [], []

        S = self.n_states
        priors = self.crop_priors["transitions"]
        total_gdd = priors.get("harvest_min_gdd", 1800)

        # ── Compute emission log-likelihoods ──
        log_emit = []  # T x S
        for t in range(T):
            ndvi = modeled_ndvi[t]
            vel = velocity[t] if t < len(velocity) else 0.0
            gdd_frac = min(2.0, cumulative_gdd[t] / max(1, total_gdd)) if t < len(cumulative_gdd) else 0.0
            sigma = uncertainty[t] if uncertainty and t < len(uncertainty) else 0.05
            ndwi = ndwi_series[t] if ndwi_series and t < len(ndwi_series) and ndwi_series[t] is not None else (ndvi * 0.5 - 0.3)

            # Photoperiod (day length)
            date_str = dates[t] if t < len(dates) else ""
            photoperiod = self._compute_photoperiod(date_str)

            row = []
            for s in self.states:
                ep = self._emission_params[s]
                # Multivariate log-likelihood (diagonal covariance — features independent)
                ll = 0.0
                ll += _log_gaussian(ndvi, ep["ndvi"][0], max(sigma, ep["ndvi"][1]))
                ll += _log_gaussian(vel, ep["velocity"][0], ep["velocity"][1])
                ll += _log_gaussian(gdd_frac, ep["gdd_frac"][0], ep["gdd_frac"][1])
                ll += _log_gaussian(ndwi, ep["ndwi"][0], ep["ndwi"][1])

                # Photoperiod emission (soft feature, lower weight via wider sigma)
                if photoperiod is not None:
                    ll += 0.5 * _log_gaussian(
                        photoperiod,
                        ep["photoperiod"][0],
                        ep["photoperiod"][1],
                    )

                # GDD gate: penalize states that are chronologically impossible
                ll += self._gdd_gate_penalty(s, cumulative_gdd[t] if t < len(cumulative_gdd) else 0, priors)

                # Visual emergence boost
                if high_res_visual_check and t < len(high_res_visual_check) and high_res_visual_check[t]:
                    if s == PhenologyStage.EMERGENCE:
                        ll += 2.0  # Strong boost

                row.append(ll)
            log_emit.append(row)

        # ── Initial state distribution ──
        log_pi = [-10.0] * S
        start_state = PhenologyStage.BARE_SOIL
        if self.is_perennial:
            start_state = PhenologyStage.DORMANCY
        if initial_stage:
            try:
                start_state = PhenologyStage(initial_stage.upper())
            except (ValueError, AttributeError):
                pass

        if start_state in self.state_idx:
            log_pi[self.state_idx[start_state]] = 0.0  # log(1.0)
        else:
            log_pi[0] = 0.0

        # ── Viterbi forward pass ──
        V = [[0.0] * S for _ in range(T)]
        backptr = [[0] * S for _ in range(T)]
        duration = [[0] * S for _ in range(T)]

        # Initialize
        for s in range(S):
            V[0][s] = log_pi[s] + log_emit[0][s]
            duration[0][s] = 1

        # Forward
        for t in range(1, T):
            for s in range(S):
                best_val = -1e30
                best_prev = 0
                for s_prev in range(S):
                    trans = self.log_trans[s_prev][s]

                    # Min-duration penalty
                    if s != s_prev:
                        min_dur = self.min_duration.get(self.states[s_prev], 7)
                        if duration[t-1][s_prev] < min_dur:
                            trans -= 5.0  # Strong penalty for premature transition

                    val = V[t-1][s_prev] + trans
                    if val > best_val:
                        best_val = val
                        best_prev = s_prev

                V[t][s] = best_val + log_emit[t][s]
                backptr[t][s] = best_prev

                if best_prev == s:
                    duration[t][s] = duration[t-1][s] + 1
                else:
                    duration[t][s] = 1

        # ── Viterbi backtracking ──
        best_final = 0
        best_val = V[T-1][0]
        for s in range(1, S):
            if V[T-1][s] > best_val:
                best_val = V[T-1][s]
                best_final = s

        path_idx = [0] * T
        path_idx[T-1] = best_final
        for t in range(T-2, -1, -1):
            path_idx[t] = backptr[t+1][path_idx[t+1]]

        stages = [self.states[i] for i in path_idx]

        # ── Confidence computation ──
        confidences = []
        for t in range(T):
            sorted_v = sorted(V[t], reverse=True)
            if len(sorted_v) >= 2:
                margin = sorted_v[0] - sorted_v[1]
                conf = 1.0 / (1.0 + math.exp(-margin))
            else:
                conf = 1.0
            confidences.append(max(0.5, min(1.0, conf)))

        return stages, confidences

    def _gdd_gate_penalty(
        self,
        state: PhenologyStage,
        current_gdd: float,
        priors: Dict,
    ) -> float:
        """Penalize states that are chronologically impossible given GDD."""
        if state == PhenologyStage.BARE_SOIL or state == PhenologyStage.DORMANCY:
            return 0.0

        gdd_thresholds = {
            PhenologyStage.EMERGENCE: priors.get("emergence_min_gdd", 100),
            PhenologyStage.VEGETATIVE: priors.get("vegetative_min_gdd", 300),
            PhenologyStage.REPRODUCTIVE: priors.get("reproductive_min_gdd", 800),
            PhenologyStage.SENESCENCE: priors.get("senescence_min_gdd", 1400),
            PhenologyStage.HARVESTED: priors.get("harvest_min_gdd", 1800),
        }

        min_gdd = gdd_thresholds.get(state)
        if min_gdd is None:
            return 0.0

        if current_gdd < min_gdd * 0.5:
            return -10.0
        elif current_gdd < min_gdd:
            frac = current_gdd / max(1, min_gdd)
            return -5.0 * (1.0 - frac)
        else:
            return 0.0

    # =====================================================================
    # Transition Extraction
    # =====================================================================

    def extract_transitions(self, dates: List[str], stages: List[PhenologyStage]) -> Dict[str, str]:
        """Returns {Stage -> Date} for the first occurrence of each stage."""
        transitions = {}
        for date, stage in zip(dates, stages):
            if stage.value not in transitions:
                transitions[stage.value] = date
        return transitions


# =========================================================================
# Utility Functions
# =========================================================================

def _log_gaussian(x: float, mu: float, sigma: float) -> float:
    """Log probability of x under N(mu, sigma²)."""
    if sigma < 1e-8:
        return 0.0 if abs(x - mu) < 1e-6 else -50.0
    return -0.5 * ((x - mu) / sigma) ** 2 - math.log(sigma) - 0.9189  # -0.5*log(2π)


# ═══════════════════════════════════════════════════════════════════════════════
# v3.2: Vernalization Chill Unit Tracker (Richardson 1974)
# ═══════════════════════════════════════════════════════════════════════════════

# Chill unit requirements by architecture class
# Source: Chuine (2000), FAO wheat guidelines, Richardson et al. (1974)
_VERNALIZATION_REQUIREMENTS = {
    "cereal":   {"chill_min": 0.0, "chill_max": 7.2, "cu_required": 40, "obligate": True},
    "maize":    {"chill_min": -999, "chill_max": -999, "cu_required": 0, "obligate": False},
    "rice":     {"chill_min": -999, "chill_max": -999, "cu_required": 0, "obligate": False},
    "legume":   {"chill_min": -999, "chill_max": -999, "cu_required": 0, "obligate": False},
    "vegetable": {"chill_min": -999, "chill_max": -999, "cu_required": 0, "obligate": False},
    "perennial": {"chill_min": 0.0, "chill_max": 7.2, "cu_required": 50, "obligate": False},
    "cotton":   {"chill_min": -999, "chill_max": -999, "cu_required": 0, "obligate": False},
    "tropical_tree": {"chill_min": -999, "chill_max": -999, "cu_required": 0, "obligate": False},
}


def accumulate_chill_units(
    temp_min_series: List[float],
    architecture: str = "cereal",
) -> dict:
    """Accumulate vernalization chill units using Richardson (1974) model.

    CU = count of days where chill_min < T_min < chill_max (°C)

    Returns:
        {
            "chill_units_accumulated": int,
            "chill_units_required": int,
            "vernalization_progress": float (0.0-1.0),
            "vernalization_complete": bool,
            "obligate_vernalization": bool,
        }
    """
    req = _VERNALIZATION_REQUIREMENTS.get(architecture, _VERNALIZATION_REQUIREMENTS["cereal"])

    if req["cu_required"] <= 0:
        return {
            "chill_units_accumulated": 0,
            "chill_units_required": 0,
            "vernalization_progress": 1.0,
            "vernalization_complete": True,
            "obligate_vernalization": False,
        }

    cu = 0
    for t_min in temp_min_series:
        if req["chill_min"] < t_min < req["chill_max"]:
            cu += 1

    progress = min(1.0, cu / max(1, req["cu_required"]))

    return {
        "chill_units_accumulated": cu,
        "chill_units_required": req["cu_required"],
        "vernalization_progress": round(progress, 3),
        "vernalization_complete": progress >= 0.8,
        "obligate_vernalization": req["obligate"],
    }


def compute_vernalization_gate(
    vernalization_progress: float,
    obligate: bool = True,
) -> float:
    """Compute transition penalty for reproductive stage if not vernalized.

    For obligate vernalizers (winter wheat, barley), the VEGETATIVE →
    REPRODUCTIVE transition is gated until vernalization ≥ 80%.

    Returns:
        Log-penalty to apply to the reproductive transition probability.
        0.0 if vernalization is not required or is complete.
    """
    if not obligate or vernalization_progress >= 0.8:
        return 0.0

    # Strong penalty if vernalization < 50%, moderate if 50-80%
    if vernalization_progress < 0.5:
        return -15.0  # Almost impossible
    else:
        return -8.0 * (1.0 - vernalization_progress)


# ═══════════════════════════════════════════════════════════════════════════════
# v3.2: Effective GDD with Stress Penalties
# ═══════════════════════════════════════════════════════════════════════════════

def compute_effective_gdd(
    t_mean: float,
    t_max: float,
    t_base: float = 10.0,
    t_opt_max: float = 35.0,
    day_length: Optional[float] = None,
    is_short_day: bool = False,
) -> float:
    """Compute stress-corrected GDD for a single day.

    Effective GDD = max(0, T_mean - T_base) × photoperiod_factor × heat_penalty

    Photoperiod factor:
        - Long-day crops: factor = 1.0 (always)
        - Short-day crops: factor = min(1.0, day_length / 14.0)

    Heat penalty (Sánchez et al. 2014):
        - If T_max > T_opt_max, penalty = max(0, 1 - (T_max - T_opt_max) / 10)
        - This reduces effective GDD when crops are heat-stressed

    Args:
        t_mean: Daily mean temperature (°C)
        t_max: Daily maximum temperature (°C)
        t_base: Crop-specific base temperature (°C)
        t_opt_max: Optimal maximum temperature (°C)
        day_length: Day length in hours
        is_short_day: True for short-day crops (rice, millet)

    Returns:
        Effective GDD for this day.
    """
    raw_gdd = max(0.0, t_mean - t_base)

    # Photoperiod factor
    if is_short_day and day_length is not None:
        photo_factor = min(1.0, day_length / 14.0)
    else:
        photo_factor = 1.0

    # Heat penalty
    if t_max > t_opt_max:
        heat_penalty = max(0.0, 1.0 - (t_max - t_opt_max) / 10.0)
    else:
        heat_penalty = 1.0

    return round(raw_gdd * photo_factor * heat_penalty, 2)
