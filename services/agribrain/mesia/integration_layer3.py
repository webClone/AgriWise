"""MESIA to Layer 3 (Water & Hydrological Modeling) Integration Bridge.

Bridges MESIA's multi-strata soil moisture likelihoods (0-5cm, 5-30cm, 30-60cm)
into AgriBrain Layer 3's multi-layer soil water balance and stress estimation engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .contracts.behaviour import BehaviourLikelihood
from .assimilation.spatial_lattice import LatticeStrata


@dataclass(frozen=True)
class MesiaHydrologicalComparison:
    """Comparison between MESIA multi-radio VWC estimate and Layer 3 hydrological model."""

    plot_id: str
    stratum: LatticeStrata
    mesia_observed_vwc: float
    model_predicted_vwc: float
    residual_error_vwc: float
    is_hydrologically_consistent: bool


class MesiaLayer3WaterBridge:
    """Integrates MESIA soil moisture proposals into Layer 3 water balance."""

    @staticmethod
    def compare_with_hydrological_model(
        plot_id: str,
        stratum: LatticeStrata,
        mesia_likelihood: BehaviourLikelihood,
        layer3_model_vwc: float,
        tolerance_vwc: float = 0.05,
    ) -> MesiaHydrologicalComparison:
        """Evaluate consistency between radio sensing and physical water balance."""
        observed_vwc = mesia_likelihood.likelihood_value if mesia_likelihood.likelihood_value is not None else 0.20
        residual = abs(observed_vwc - layer3_model_vwc)
        is_consistent = residual <= tolerance_vwc

        return MesiaHydrologicalComparison(
            plot_id=plot_id,
            stratum=stratum,
            mesia_observed_vwc=observed_vwc,
            model_predicted_vwc=layer3_model_vwc,
            residual_error_vwc=residual,
            is_hydrologically_consistent=is_consistent,
        )
