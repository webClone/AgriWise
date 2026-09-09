"""MESIA 5-Tier Spatial Gating Classifier & Covariance Inflation Rules.

Implements the 5-tier classification hierarchy:
- CORE_PROTECTED
- PLOT_ADMITTED_GUARDED
- BOUNDARY_AMBIGUOUS
- EXTERNAL_DOMINANT_CANDIDATE
- EXT_QUARANTINED
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from .models import ContainmentInterval, SpatialClassificationTier


class SpatialGatingClassifier:
    """Classifies radio observations and computes boundary covariance inflation factors."""

    @staticmethod
    def classify(
        containment_plot: ContainmentInterval,
        containment_core: ContainmentInterval,
        modality: str = "GNSS_R",
        has_external_active_nuisance: bool = False,
    ) -> Tuple[SpatialClassificationTier, float, bool, bool, Optional[str], str]:
        """Evaluates 5-tier classification and covariance penalty.

        Returns:
            (tier, cov_scale, safe_root_zone, safe_canopy, quarantine_reason, justification)
        """
        eta_lower_plot = containment_plot.eta_lower
        eta_lower_core = containment_core.eta_lower

        if eta_lower_plot >= 0.95 and eta_lower_core >= 0.80:
            tier = SpatialClassificationTier.CORE_PROTECTED
            cov_scale = 1.0
            safe_root = True
            safe_canopy = True
            reason = None
            justification = (
                f"Footprint sensitivity is strictly contained within protected plot core "
                f"(eta_lower,plot={eta_lower_plot:.3f} >= 0.95, eta_lower,core={eta_lower_core:.3f} >= 0.80). "
                f"Admitted with zero covariance inflation."
            )

        elif eta_lower_plot >= 0.80:
            tier = SpatialClassificationTier.PLOT_ADMITTED_GUARDED
            # Boundary inflation equation: R_scale = 1.0 + 15.0 * (1 - eta_lower)^2
            cov_scale = 1.0 + 15.0 * ((1.0 - eta_lower_plot) ** 2)
            safe_root = bool(eta_lower_plot >= 0.85 and not has_external_active_nuisance)
            safe_canopy = True
            reason = None if safe_root else "PERIMETER_MARGIN_INFLATION"
            justification = (
                f"Footprint sensitivity meets plot boundary threshold (eta_lower,plot={eta_lower_plot:.3f} >= 0.80) "
                f"but grazes perimeter buffer margin. Covariance scaled by {cov_scale:.2f}x to safeguard against edge leakage."
            )

        elif eta_lower_plot >= 0.60:
            tier = SpatialClassificationTier.BOUNDARY_AMBIGUOUS
            cov_scale = 10.0
            safe_root = False
            safe_canopy = False
            reason = "BOUNDARY_STRADDLING_AMBIGUOUS"
            justification = (
                f"Ambiguous boundary straddling detected (0.60 <= eta_lower,plot={eta_lower_plot:.3f} < 0.80). "
                f"Observation quarantined from root-zone soil and foliar canopy state updates."
            )

        elif eta_lower_plot >= 0.50:
            tier = SpatialClassificationTier.EXTERNAL_DOMINANT_CANDIDATE
            cov_scale = 25.0
            safe_root = False
            safe_canopy = False
            reason = "EXTERNAL_DOMINANT_ENERGY"
            justification = (
                f"External surroundings dominate sensitivity (0.50 <= eta_lower,plot={eta_lower_plot:.3f} < 0.60). "
                f"Candidate for external nuisance vector attribution x_ext. State updates locked."
            )

        else:
            tier = SpatialClassificationTier.EXT_QUARANTINED
            cov_scale = 100.0
            safe_root = False
            safe_canopy = False
            reason = "IMPOSSIBLE_EXTERNAL_CONTAMINATION"
            justification = (
                f"Conservative plot containment lower bound failed (eta_lower,plot={eta_lower_plot:.3f} < 0.50). "
                f"Over {((1.0 - containment_plot.eta_hat) * 100):.1f}% of electromagnetic sensitivity originates outside plot. Strictly quarantined."
            )

        return tier, float(cov_scale), safe_root, safe_canopy, reason, justification
