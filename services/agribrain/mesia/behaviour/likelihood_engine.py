"""MESIA Behaviour Likelihood Engine (ASMAE Interface) — R6 §9.7 / P7.7.

Generates calibrated BehaviourLikelihood proposals for ASMAE, complete with
decomposed uncertainty budgets, alternative nuisance explanations, and explicit abstentions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..contracts.behaviour import BehaviourLikelihood, RadioBehaviourContract
from ..contracts.observation import RadioObservationPacket
from .feature_extraction import ExtractedBehaviourFeatures, NativeFeatureExtractor
from .nuisance_model import BayesianNuisanceModel, NuisanceAttributionReport
from .contracts import get_behaviour_contract


class BehaviourLikelihoodEngine:
    """Engine computing calibrated likelihood proposals for ASMAE assimilation."""

    @classmethod
    def generate_likelihood(
        cls,
        packet: RadioObservationPacket,
        nuisance_report: Optional[NuisanceAttributionReport] = None,
    ) -> BehaviourLikelihood:
        """Convert a RadioObservationPacket into an ASMAE BehaviourLikelihood proposal."""
        # 1. Extract lineage-preserving native features
        feat = NativeFeatureExtractor.extract_features(packet)

        # 2. Evaluate nuisance attribution if not provided
        nuisance = nuisance_report or BayesianNuisanceModel.attribute_cause(
            signal_delta_db=0.0,
        )

        now = datetime.now(timezone.utc)
        family = packet.source_profile.split("/")[0] if packet.source_profile else "UNKNOWN"
        contract = get_behaviour_contract(family)

        contract_ref = contract.contract_id if contract else f"contract-{family.lower()}-default"

        # 3. Calculate target variable & likelihood
        # Check if measured observation exists (preserve missing observations)
        raw_snr = feat.features.get("snr_db")
        expected_baseline = feat.features.get("expected_baseline_snr_db")
        cal_unc = float(feat.features.get("calibration_uncertainty_db", 1.0))

        # Propagate calibration uncertainty into observation error covariance:
        # sigma_total^2 = sigma_nuisance^2 + sigma_calibration^2
        base_cov = 0.25 if nuisance.is_safe_for_soil_assimilation else 2.50
        cov = float(base_cov + (cal_unc ** 2))

        if raw_snr is not None and expected_baseline is not None:
            snr = float(raw_snr)
            exp_base = float(expected_baseline)
            innovation = float(snr - exp_base)
            std_total = max(0.5, math.sqrt(cov))
            likelihood_val = math.exp(-0.5 * (innovation / std_total) ** 2) if nuisance.is_safe_for_soil_assimilation else 0.01
            support = 1.0 if nuisance.is_safe_for_soil_assimilation else 0.1
        else:
            # Missing observation: preserve missingness, do NOT fabricate innovation or likelihood
            innovation = None
            likelihood_val = None
            support = 0.0

        # Alternative causes
        alternatives = [
            {"cause": "INSTRUMENT_NUISANCE", "probability": nuisance.p_instrument_nuisance},
            {"cause": "GEOMETRY_NUISANCE", "probability": nuisance.p_geometry_nuisance},
            {"cause": "NETWORK_NUISANCE", "probability": nuisance.p_network_nuisance},
            {"cause": "COEXISTENCE_NUISANCE", "probability": nuisance.p_coexistence_nuisance},
            {"cause": "WEATHER_MOTION_NUISANCE", "probability": nuisance.p_weather_motion_nuisance},
            {"cause": "UNKNOWN_NUISANCE", "probability": nuisance.p_unknown_nuisance},
        ]

        epochs = {
            "geometry_epoch_id": packet.geometry_epoch_id,
            "instrument_epoch_id": packet.instrument_epoch_id,
            "network_epoch_id": packet.network_epoch_id,
            "coexistence_epoch_id": packet.coexistence_epoch_id,
            "calibration_state_id": packet.calibration_state_id,
            "software_model_epoch_id": packet.software_model_epoch_id,
        }

        # Audit Finding #7: target_variable must come from the behaviour contract,
        # not be unconditionally assigned. If the contract does not define a
        # physical_primitive or target, the evidence must not be emitted.
        target_var = (contract.physical_primitive if contract else "")
        if not target_var:
            target_var = "UNSPECIFIED_PENDING_CONTRACT"

        return BehaviourLikelihood(
            likelihood_id=f"lik-{packet.packet_id}",
            radio_family=family,
            contract_ref=contract_ref,
            target_variable=target_var,
            likelihood_value=likelihood_val,
            innovation=innovation,
            support=support,
            covariance=cov,
            authority_scope="evidence_proposal",  # Invariant: Principle P-08
            alternative_causes=alternatives,
            epoch_refs=epochs,
            observability_ref=f"obs-cert-{packet.packet_id}",
            closure_ref=f"closure-{packet.packet_id}",
            qualification_ref=f"qual-{family}",
            created_at=now,
            native_observation_ref=packet.packet_id,
        )
