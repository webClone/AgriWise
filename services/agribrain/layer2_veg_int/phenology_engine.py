"""
Layer 2.2: Phenology Inference Engine (v3.2)

Infers the biological stage of the crop using a Hidden Markov Model
with Viterbi decoding.

Enhancements:
  - Development rate explicit decomposition: GDD, photoperiod, thermal stress (Phase 3)
  - Semi-Markov duration penalties on HMM transitions (Phase 3)
  - Crop-specific emission tuning from CROP_NDVI_SIGNATURES
  - Photoperiod-aware transition gating (latitude + DOY → day length)
  - Calibrated vernalization gating (Richardson 1974)

Algorithm:
  - States: BARE_SOIL, EMERGENCE, VEGETATIVE, REPRODUCTIVE, SENESCENCE,
            HARVESTED, DORMANCY (perennials only)
  - Emissions: Multivariate Gaussian on (NDVI, velocity, GDD_frac, NDWI, photoperiod)
  - Transitions: GDD-gated probability matrix with semi-Markov duration penalties
  - Decoding: Viterbi (log-space) with O(n × S²) complexity

References:
  - Rabiner (1989) "A Tutorial on HMMs"
  - Wardlow & Egbert (2008) "Large-area crop mapping using MODIS"
  - Bolton & Friedl (2013) "Forecasting crop yield using MODIS EVI"
"""

import math
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
from layer2_veg_int.schema import PhenologyStage


@dataclass
class DevelopmentIncrement:
    """Explicit decomposition of daily biological development."""
    raw_gdd: float           # max(0, T_mean - T_base)
    photo_factor: float      # Photoperiod scaling [0.1, 1.0]
    heat_penalty: float      # Thermal stress inhibition [0.0, 1.0]
    delta_development: float # Product: raw_gdd * photo_factor * heat_penalty


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
                 latitude: Optional[float] = None,
                 requires_vernalization: bool = True,
                 stage_graph: Optional[Any] = None):
        """Initialize the phenology engine.

        Args:
            crop_config: GDD transition thresholds.
            is_perennial: Whether the crop cycles through DORMANCY.
            crop_ndvi_signature: NDVI signature dict (peak_ndvi, trough_ndvi, etc.)
                from CROP_NDVI_SIGNATURES for crop-specific emission tuning.
            latitude: Field latitude in degrees for photoperiod computation.
            requires_vernalization: Whether the crop has an obligate chill unit requirement.
            stage_graph: Optional CropStageGraph for biological sub-stage decoding.
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
        self.requires_vernalization = requires_vernalization
        self.stage_graph = stage_graph

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

        # Minimum and expected duration per state (in timesteps, ~days)
        self.min_duration = {
            PhenologyStage.BARE_SOIL: 5,
            PhenologyStage.EMERGENCE: 7,
            PhenologyStage.VEGETATIVE: 14,
            PhenologyStage.REPRODUCTIVE: 10,
            PhenologyStage.SENESCENCE: 7,
            PhenologyStage.HARVESTED: 5,
            PhenologyStage.DORMANCY: 14,
        }
        self.expected_duration = {
            PhenologyStage.BARE_SOIL: 20,
            PhenologyStage.EMERGENCE: 14,
            PhenologyStage.VEGETATIVE: 45,
            PhenologyStage.REPRODUCTIVE: 35,
            PhenologyStage.SENESCENCE: 25,
            PhenologyStage.HARVESTED: 20,
            PhenologyStage.DORMANCY: 60,
        }

    def _build_emission_params(self, crop_sig: Optional[Dict]) -> Dict:
        """Build crop-specific emission parameters from NDVI signature.

        Uses CROP_NDVI_SIGNATURES (peak_ndvi, trough_ndvi) to adapt the
        HMM emission means so that the phenology detection is crop-aware.
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
                # P0 FIX: Invalid date should not silently default to summer solstice.
                # Returning None causes photoperiod emission to be skipped (marginalized).
                return None
        except Exception:
            return None

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
        vernalization_progress: float = 1.0,
        vernalization_series: Optional[List[float]] = None,
    ) -> Tuple[List[PhenologyStage], List[float]]:
        """
        Infers phenological stage using Viterbi decoding on the HMM.

        Multivariate emission features: (NDVI, velocity, GDD_frac, NDWI, photoperiod)

        Args:
            vernalization_progress: Scalar vernalization fraction (fallback).
            vernalization_series: Daily cumulative vernalization fraction V_t. Gates
                the VEGETATIVE → REPRODUCTIVE transition causally per day.
        """
        T = len(modeled_ndvi)
        if T == 0:
            return [], []

        S = self.n_states
        priors = self.crop_priors.get("transitions", {}) if isinstance(self.crop_priors, dict) else {}
        total_gdd = priors.get("harvest_min_gdd", 1800)

        try:
            season_initial_gdd = max(0.0, float(initial_gdd))
            if not math.isfinite(season_initial_gdd):
                season_initial_gdd = 0.0
        except (TypeError, ValueError):
            season_initial_gdd = 0.0

        def _season_gdd(index: int) -> float:
            window_gdd = cumulative_gdd[index] if index < len(cumulative_gdd) else 0.0
            try:
                window_gdd = max(0.0, float(window_gdd))
            except (TypeError, ValueError):
                window_gdd = 0.0
            return season_initial_gdd + window_gdd

        # ── Compute emission log-likelihoods ──
        log_emit = []  # T x S
        for t in range(T):
            ndvi = modeled_ndvi[t]
            vel = velocity[t] if t < len(velocity) else 0.0
            gdd_at_t = _season_gdd(t)
            gdd_frac = min(2.0, gdd_at_t / max(1, total_gdd))
            sigma = uncertainty[t] if uncertainty and t < len(uncertainty) else 0.05
            
            # P0 FIX: When NDWI is missing, do NOT fabricate a pseudo-value.
            # Instead, skip the NDWI emission term (marginalize over missing modality).
            ndwi = ndwi_series[t] if ndwi_series and t < len(ndwi_series) and ndwi_series[t] is not None else None

            # Photoperiod (day length)
            date_str = dates[t] if t < len(dates) else ""
            photoperiod = self._compute_photoperiod(date_str)

            row = []
            for s in self.states:
                ep = self._emission_params[s]
                # Multivariate log-likelihood on physical/spectral observations ONLY
                # (Thermal/photoperiod forcing is moved strictly into Markov transition dynamics)
                ll = 0.0
                ll += _log_gaussian(ndvi, ep["ndvi"][0], max(sigma, ep["ndvi"][1]))
                ll += _log_gaussian(vel, ep["velocity"][0], ep["velocity"][1])
                
                # Only include NDWI emission when data is present (marginalize when missing)
                if ndwi is not None:
                    ll += _log_gaussian(ndwi, ep["ndwi"][0], ep["ndwi"][1])

                # Visual emergence boost (independent physical evidence)
                if high_res_visual_check and t < len(high_res_visual_check) and high_res_visual_check[t]:
                    if s == PhenologyStage.EMERGENCE:
                        ll += 2.0

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

        gdd_0 = _season_gdd(0)
        for s in range(S):
            penalty = self._gdd_gate_penalty(self.states[s], gdd_0, priors)
            if self.states[s] == start_state:
                log_pi[s] = penalty
            else:
                log_pi[s] = -10.0 + penalty

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
            gdd_at_t = _season_gdd(t)
            v_t = (
                vernalization_series[t]
                if vernalization_series and t < len(vernalization_series) and vernalization_series[t] is not None
                else vernalization_progress
            )
            for s in range(S):
                best_val = -1e30
                best_prev = 0
                for s_prev in range(S):
                    trans = self.log_trans[s_prev][s]

                    # GDD transition dynamics (developmental readiness in transition model)
                    gdd_thresholds = {
                        PhenologyStage.EMERGENCE: priors.get("emergence_min_gdd", 100),
                        PhenologyStage.VEGETATIVE: priors.get("vegetative_min_gdd", 300),
                        PhenologyStage.REPRODUCTIVE: priors.get("reproductive_min_gdd", 800),
                        PhenologyStage.SENESCENCE: priors.get("senescence_min_gdd", 1400),
                        PhenologyStage.HARVESTED: priors.get("harvest_min_gdd", 1800),
                    }
                    target_gdd = gdd_thresholds.get(self.states[s], 0.0)
                    if s > s_prev:
                        if gdd_at_t >= target_gdd:
                            trans += min(3.5, 1.5 * (gdd_at_t - target_gdd) / max(50.0, target_gdd * 0.3))
                        else:
                            trans += self._gdd_gate_penalty(self.states[s], gdd_at_t, priors)
                    elif s == s_prev:
                        if target_gdd > 0.0 and gdd_at_t < target_gdd * 0.5:
                            trans += self._gdd_gate_penalty(self.states[s], gdd_at_t, priors)
                        elif s + 1 < S:
                            next_gdd = gdd_thresholds.get(self.states[s + 1], 99999.0)
                            if gdd_at_t > next_gdd * 1.1:
                                trans -= min(3.0, (gdd_at_t - next_gdd * 1.1) / max(50.0, next_gdd * 0.3))

                    # Vernalization transition gate (P0-1 FIX: completely bypassed for non-vernalizing crops)
                    if self.states[s] == PhenologyStage.REPRODUCTIVE and (self.states[s_prev] != PhenologyStage.REPRODUCTIVE or v_t < 0.5):
                        if self.requires_vernalization:
                            trans += compute_vernalization_gate(v_t)

                    # Min-duration penalty & duration constraint
                    if s != s_prev:
                        min_dur = self.min_duration.get(self.states[s_prev], 7)
                        if duration[t-1][s_prev] < min_dur:
                            trans -= 5.0  # Strong penalty for premature transition
                    else:
                        # Self-loop duration penalty if state exceeds 2.5x expected duration
                        exp_dur = self.expected_duration.get(self.states[s], 30)
                        if duration[t-1][s] > exp_dur * 2.5:
                            trans -= 0.1 * (duration[t-1][s] - exp_dur * 2.5)

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
                conf = 1.0 - math.exp(-max(0.0, margin))
            else:
                conf = 1.0
            confidences.append(max(0.0, min(1.0, conf)))

        return stages, confidences

    def decode_sub_stages(
        self,
        canonical_stages: List[PhenologyStage],
        cumulative_gdd: List[float],
        total_gdd: float = 1800.0,
    ) -> List[str]:
        """Decode fine-grained biological sub-stages using CropStageGraph."""
        if not self.stage_graph or not hasattr(self.stage_graph, "nodes"):
            return [s.value for s in canonical_stages]
        sub_stages = []
        nodes = self.stage_graph.nodes
        for idx, c_stage in enumerate(canonical_stages):
            gdd_frac = (cumulative_gdd[idx] / max(1.0, total_gdd)) if idx < len(cumulative_gdd) else 0.0
            matching_nodes = [n for n in nodes if n.canonical_stage == c_stage]
            if matching_nodes:
                best_node = min(matching_nodes, key=lambda n: abs(n.expected_gdd_fraction - gdd_frac))
                sub_stages.append(best_node.stage_id)
            else:
                sub_stages.append(c_stage.value)
        return sub_stages

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
            return -50.0  # Biologically impossible transition prior to minimal thermal competence
        elif current_gdd < min_gdd:
            frac = current_gdd / max(1, min_gdd)
            return -20.0 * (1.0 - frac)
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
        return -50.0  # Biologically impossible transition
    else:
        return -20.0 * (1.0 - vernalization_progress)


# ═══════════════════════════════════════════════════════════════════════════════
# v3.2: Effective GDD & Development Rate with Stress Penalties
# ═══════════════════════════════════════════════════════════════════════════════

def compute_development_rate(
    t_mean: float,
    t_max: float,
    t_base: float = 10.0,
    t_opt_max: float = 35.0,
    day_length: Optional[float] = None,
    is_short_day: bool = False,
    p_critical: float = 13.0,
) -> DevelopmentIncrement:
    """Compute biologically decomposed development rate increment.

    Separates thermal time (GDD) from photoperiodic and thermal stress forcing.

    Returns:
        DevelopmentIncrement dataclass with raw_gdd, photo_factor, heat_penalty,
        and delta_development.
    """
    raw_gdd = max(0.0, t_mean - t_base)

    # Photoperiod factor
    if is_short_day and day_length is not None:
        k = 1.5  # steepness parameter
        photo_factor = 1.0 / (1.0 + math.exp(k * (day_length - p_critical)))
        photo_factor = max(0.1, min(1.0, photo_factor))
    else:
        photo_factor = 1.0

    # Heat penalty (Sánchez et al. 2014)
    if t_max > t_opt_max:
        heat_penalty = max(0.0, 1.0 - (t_max - t_opt_max) / 10.0)
    else:
        heat_penalty = 1.0

    delta_dev = round(raw_gdd * photo_factor * heat_penalty, 2)
    return DevelopmentIncrement(
        raw_gdd=round(raw_gdd, 2),
        photo_factor=round(photo_factor, 3),
        heat_penalty=round(heat_penalty, 3),
        delta_development=delta_dev,
    )


def compute_effective_gdd(
    t_mean: float,
    t_max: float,
    t_base: float = 10.0,
    t_opt_max: float = 35.0,
    day_length: Optional[float] = None,
    is_short_day: bool = False,
) -> float:
    """Compute stress-corrected GDD for a single day (backward compatibility)."""
    inc = compute_development_rate(
        t_mean=t_mean,
        t_max=t_max,
        t_base=t_base,
        t_opt_max=t_opt_max,
        day_length=day_length,
        is_short_day=is_short_day,
    )
    return inc.delta_development
