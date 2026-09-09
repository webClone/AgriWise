"""MESIA Evidence Tier & Truth Hierarchy Contracts — R6 §8.1 / P-08.

Establishes a four-tier evidence typing model:
  Tier 0: NativeRFCapture (Raw I/Q bytes, raw CSI matrix, uncalibrated SNR).
  Tier 1: CalibratedRFFeature (Phase-sanitized CSI, multipath metric, excess attenuation).
  Tier 2: BiologicalInference (Canopy water index, dielectric permittivity, GUM uncertainty).
  Tier 3: ASMAEInnovationProposal (Belief state innovation targeted to an ASMAE variable).

Guarantees:
  - Forbids labeling Tier 2 (model-inverted biological predictions) or Tier 3 as MEASURED_NATIVE.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional, Tuple


class TruthTier(str, Enum):
    """Four-tier evidence hierarchy for opportunistic RF sensing."""

    NATIVE_RF_CAPTURE = "NATIVE_RF_CAPTURE"
    """Tier 0: Raw physical waveform samples, uncalibrated IQ or complex CSI matrix."""

    CALIBRATED_RF_FEATURE = "CALIBRATED_RF_FEATURE"
    """Tier 1: Instrument-calibrated radio metrics (excess attenuation dB, phase slope, multipath index)."""

    BIOLOGICAL_INFERENCE = "BIOLOGICAL_INFERENCE"
    """Tier 2: Agronomic model inversion (canopy water index, soil dielectric permittivity)."""

    ASMAE_INNOVATION_PROPOSAL = "ASMAE_INNOVATION_PROPOSAL"
    """Tier 3: State innovation proposal submitted to Layer 0.5 EnKF assimilation."""


class TruthClass(str, Enum):
    """Epistemic truth classification."""

    MEASURED_NATIVE = "MEASURED_NATIVE"
    """Raw physical observation directly registered by an in-situ sensor."""

    CALIBRATED_FEATURE = "CALIBRATED_FEATURE"
    """Engineered feature computed via established electromagnetic calibration."""

    DERIVED_MODEL_INFERRED = "DERIVED_MODEL_INFERRED"
    """Agronomic property inferred through empirical inversion or biophysical model."""

    SIMULATED = "SIMULATED"
    """Synthetic, proxy, or simulation-generated values."""


def classify_proposal_truth(feature_name: str, has_real_sensor: bool) -> Dict[str, Any]:
    """Determine the correct TruthTier, TruthClass, and evidence classification for a proposal."""
    if not has_real_sensor:
        return {
            "truth_tier": TruthTier.ASMAE_INNOVATION_PROPOSAL.value,
            "truth_class": TruthClass.SIMULATED.value,
            "is_derived_model_inference": True,
            "presentation_state": "SIMULATION",
        }

    # Biological features (canopy water, root-zone moisture, foliar attenuation)
    biological_keywords = ("canopy", "foliar", "vwc", "water", "soil", "biomass")
    if any(kw in feature_name.lower() for kw in biological_keywords):
        return {
            "truth_tier": TruthTier.BIOLOGICAL_INFERENCE.value,
            "truth_class": TruthClass.DERIVED_MODEL_INFERRED.value,
            "is_derived_model_inference": True,
            "presentation_state": "LIVE",
        }

    # Raw radio features (csi matrix, snr, phase, rssi)
    return {
        "truth_tier": TruthTier.NATIVE_RF_CAPTURE.value,
        "truth_class": TruthClass.MEASURED_NATIVE.value,
        "is_derived_model_inference": False,
        "presentation_state": "LIVE",
    }
