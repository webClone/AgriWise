"""
Layer 4.4: Nutrient Inference Engine — Full N/P/K Bayesian with tillage-adjusted SOC.

Replaces the v4.0 placeholder inference with real Bayesian log-odds
estimation for N, P, and K using:
  - Spectral evidence (NDVI-Z, NDRE-Z, growth adequacy)
  - User soil analysis (lab N/P/K ppm) as strong priors
  - SAR-derived tillage → N mineralization adjustment
  - Confounder gating (water stress, disease, salinity, pH lockout)
  - L3 structural diagnostics (weed competition, mechanical damage)
  - Multi-nutrient interactions (K↔N, pH→P availability)

Probability = Belief from Evidence (Logits)
Confidence = Trust from Data Quality (Penalties)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from layer4_nutrients.schema import (
    NutrientState, NutrientBudget, Severity, EvidenceLogit,
    Nutrient, Confounder, Driver, MACRO_NUTRIENTS,
    TillageDetection, SOCDynamics,
)


def _sigmoid(logit: float) -> float:
    logit = max(-20.0, min(20.0, logit))
    return 1.0 / (1.0 + math.exp(-logit))


def _severity_from_prob(prob: float) -> Severity:
    if prob > 0.85:
        return Severity.CRITICAL
    if prob > 0.65:
        return Severity.HIGH
    if prob > 0.40:
        return Severity.MODERATE
    return Severity.LOW


class NutrientInferenceEngine:
    """Research-grade N/P/K inference with Bayesian log-odds."""

    def infer_states(
        self,
        evidence: Dict[str, Any],
        swb: Any,
        demands: Any,
        l3_decision: Any,
        soc: Optional[SOCDynamics] = None,
        tillage: Optional[TillageDetection] = None,
    ) -> Dict[Nutrient, NutrientState]:
        """Infer deficiency states for N, P, K, and S."""
        states = {}
        states[Nutrient.N] = self._infer_nitrogen(evidence, swb, demands, l3_decision, soc, tillage)
        states[Nutrient.P] = self._infer_phosphorus(evidence, swb, l3_decision)
        states[Nutrient.K] = self._infer_potassium(evidence, swb, l3_decision)
        states[Nutrient.S] = self._infer_sulfur(evidence, swb, l3_decision)
        return states

    # ------------------------------------------------------------------
    # Nitrogen
    # ------------------------------------------------------------------
    def _infer_nitrogen(
        self, evidence: Dict, swb: Any, demands: Any,
        l3_decision: Any, soc: Optional[SOCDynamics],
        tillage: Optional[TillageDetection],
    ) -> NutrientState:
        logit = -2.0  # Prior: N deficiency is uncommon
        trace = []
        drivers = []

        # Evidence 1: NDVI Z-Score (vigor proxy)
        ndvi_z = evidence.get("ndvi_z", 0.0)
        drivers.append(Driver.NDVI)
        if ndvi_z < -3.0:
            delta = 3.5
        elif ndvi_z < -1.5:
            delta = 2.0
        elif ndvi_z < -0.5:
            delta = 0.8
        elif ndvi_z > 1.0:
            delta = -1.5
        else:
            delta = 0.0
        if delta != 0:
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.N, f"NDVI Z={ndvi_z:.2f}", delta, 1.5,
                {"feature": "ndvi_z", "value": ndvi_z}))

        # Evidence 2: NDRE Z-Score (chlorophyll/N-specific)
        ndre_z = evidence.get("ndre_z", 0.0)
        if ndre_z != 0:
            if ndre_z < -2.0:
                delta = 2.5  # NDRE is more N-specific than NDVI
            elif ndre_z < -1.0:
                delta = 1.5
            elif ndre_z > 0.5:
                delta = -1.0
            else:
                delta = 0.0
            if delta != 0:
                logit += delta
                trace.append(EvidenceLogit(
                    Driver.NDVI, Nutrient.N, f"NDRE Z={ndre_z:.2f}", delta, 2.0,
                    {"feature": "ndre_z", "value": ndre_z}))

        # ASMAE Chlorophyll log-odds adjustment for N deficiency
        asmae_chloro = evidence.get("asmae_chlorophyll")
        if asmae_chloro is not None:
            if asmae_chloro < 0.45:
                delta = 3.0 + max(0.0, (0.45 - asmae_chloro) * 1.5)
            elif asmae_chloro > 0.65:
                delta = -1.5
            else:
                delta = 0.0
            if delta != 0.0:
                logit += delta
                trace.append(EvidenceLogit(
                    Driver.NDVI, Nutrient.N, f"ASMAE Chlorophyll={asmae_chloro:.2f}", delta, 1.8,
                    {"feature": "asmae_chlorophyll", "value": asmae_chloro}))

        # Evidence 3: Growth stall
        growth = evidence.get("growth_adequacy", 1.0)
        if growth < 0.5:
            delta = 1.5
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.N, f"Growth stalled {growth:.2f}", delta, 1.2,
                {"feature": "growth_adequacy", "value": growth}))

        # Evidence 4: User soil lab N (strongest evidence)
        soil_n_status = evidence.get("soil_n_status")
        soil_n_ppm = evidence.get("soil_n_ppm")
        if soil_n_status is not None:
            if soil_n_status == "deficient":
                delta = 3.0  # Near ground truth
            elif soil_n_status == "adequate":
                delta = -2.0
            elif soil_n_status == "high":
                delta = -3.5
            else:
                delta = 0.0
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.N,
                f"Soil lab N={soil_n_ppm}ppm ({soil_n_status})",
                delta, 3.0,
                {"feature": "soil_n_ppm", "value": soil_n_ppm}))

        # Evidence 5: N leaching from SWB
        leaching = getattr(swb, "leaching_risk_index", 0.0) if swb else 0.0
        if leaching > 0.5:
            delta = 1.0
            logit += delta
            trace.append(EvidenceLogit(
                Driver.RAIN, Nutrient.N, f"Leaching risk {leaching:.2f}", delta, 1.0,
                {"feature": "leaching_risk_index", "value": leaching}))
            drivers.append(Driver.RAIN)

        # Evidence 6: SOC/tillage-adjusted mineralization supply
        if soc and soc.tillage_adjusted_mineralization > 0:
            # Continuous: higher mineralization → less likely deficient
            # Linear scale: 0 kg → +1.0 logit, 30 kg → 0 logit, 60 kg → -1.0 logit
            min_val = soc.tillage_adjusted_mineralization
            delta = -((min_val - 30.0) / 30.0)  # Centered at 30 kg/ha/yr
            delta = max(-1.5, min(1.5, delta))  # Clamp
            if abs(delta) > 0.05:  # Only log meaningful deltas
                logit += delta
                trace.append(EvidenceLogit(
                    Driver.SAR_VV, Nutrient.N,
                    f"SOC mineralization {min_val:.1f} kg/ha/yr "
                    f"(tillage: {soc.tillage_history.tillage_class.value})",
                    delta, 1.0,
                    {"feature": "soc_mineralization", "value": min_val}))
                drivers.append(Driver.SAR_VV)

        # Evidence 7: L3 weed competition → increases N deficiency probability
        # Science: weeds compete for soil N, depleting available supply.
        # Higher weed pressure → more likely the crop is N-starved.
        l3_weed_prob = self._get_l3_diagnosis_prob(l3_decision, "WEED_PRESSURE")
        if l3_weed_prob > 0.3:
            # Weed competition steals N → increase deficiency belief
            delta = min(1.5, l3_weed_prob * 1.8)
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.N,
                f"L3 weed competition (p={l3_weed_prob:.2f}) depleting soil N",
                delta, 1.2,
                {"feature": "l3_weed_pressure", "value": l3_weed_prob}))

        # Final probability
        prob = _sigmoid(logit)

        # Confidence (Trust) — separate from probability
        conf = 1.0
        confounders = []

        # Confounder: Water stress
        water_stress = getattr(swb, "water_stress_index", 0.0) if swb else 0.0
        l3_water = self._get_l3_water_prob(l3_decision)
        eff_water = max(water_stress, l3_water)
        if eff_water > 0.4:
            conf -= 0.35
            confounders.append(Confounder.WATER_STRESS)

        # Confounder: Spatial heterogeneity
        if evidence.get("heterogeneity_flag"):
            conf -= 0.10
            confounders.append(Confounder.SPATIAL_HETEROGENEITY)

        # Confounder: Recent tillage disturbance (spectral noise)
        if tillage and tillage.detected and tillage.days_since_detection < 14:
            conf -= 0.15
            confounders.append(Confounder.TILLAGE_DISTURBANCE)

        # Confounder: Weed competition confounds spectral N signals
        # Weeds produce green pixels → NDVI may not accurately reflect crop N status
        if l3_weed_prob > 0.4:
            conf -= 0.20
            confounders.append(Confounder.WEED_COMPETITION)

        # Confounder: Mechanical damage confounds spectral interpretation
        # Damaged vegetation produces misleading spectral signatures
        l3_mech_prob = self._get_l3_diagnosis_prob(l3_decision, "MECHANICAL_DAMAGE")
        if l3_mech_prob > 0.4:
            conf -= 0.25
            confounders.append(Confounder.MECHANICAL_DAMAGE)

        # ASMAE confounders
        asmae_water = evidence.get("asmae_water_stress")
        if asmae_water is not None and asmae_water > 0.4:
            conf -= 0.20
            if Confounder.WATER_STRESS not in confounders:
                confounders.append(Confounder.WATER_STRESS)

        asmae_salinity = evidence.get("inferred_salinity_pressure")
        if asmae_salinity is not None and asmae_salinity > 0.4:
            conf -= 0.20
            if Confounder.SALINITY not in confounders:
                confounders.append(Confounder.SALINITY)

        asmae_biotic = evidence.get("asmae_biotic_risk")
        if asmae_biotic is not None and asmae_biotic > 0.4:
            conf -= 0.20
            if Confounder.DISEASE_RISK not in confounders:
                confounders.append(Confounder.DISEASE_RISK)

        # Gate low chlorophyll when water stress is present (lower confidence)
        has_water_stress = (eff_water > 0.4) or (asmae_water is not None and asmae_water > 0.4)
        has_low_chlorophyll = (ndre_z < -1.0) or (asmae_chloro is not None and asmae_chloro < 0.45)
        if has_water_stress and has_low_chlorophyll:
            conf -= 0.15
            if Confounder.WATER_STRESS not in confounders:
                confounders.append(Confounder.WATER_STRESS)

        conf = max(0.10, conf)

        # Budget (if demands available)
        budget = None
        if demands and hasattr(demands, "total_demand"):
            n_demand = demands.total_demand.get("N", 0)
            n_supply = soc.tillage_adjusted_mineralization if soc else 0
            budget = NutrientBudget(
                nutrient=Nutrient.N,
                crop_removal=n_demand,
                mineralization=n_supply,
                atmospheric_deposition=8.0,
                leaching_loss=getattr(swb, "n_leaching_kg_ha", 0) if swb else 0,
                soil_test_available=soil_n_ppm * 3.0 if soil_n_ppm else 0,
            )

        return NutrientState(
            nutrient=Nutrient.N,
            state_index=round(-prob, 4),
            probability_deficient=round(prob, 4),
            confidence=round(conf, 4),
            severity=_severity_from_prob(prob),
            drivers_used=drivers,
            evidence_trace=trace,
            confounders=confounders,
            notes="Bayesian log-odds with NDVI/NDRE/soil-lab/SOC evidence",
            estimated_available_kg_ha=budget.total_supply if budget else None,
            estimated_demand_kg_ha=budget.crop_removal if budget else None,
            balance_kg_ha=budget.balance if budget else None,
        )

    # ------------------------------------------------------------------
    # Phosphorus
    # ------------------------------------------------------------------
    def _infer_phosphorus(
        self, evidence: Dict, swb: Any, l3_decision: Any,
    ) -> NutrientState:
        logit = -2.5  # Prior: P deficiency less common than N
        trace = []
        drivers = [Driver.NDVI]
        confounders = []

        # Evidence 1: NDVI — P deficiency shows stunted growth, purple tinting
        ndvi_z = evidence.get("ndvi_z", 0.0)
        if ndvi_z < -2.0:
            delta = 1.5  # Weaker signal than N (less specific)
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.P, f"Low NDVI Z={ndvi_z:.2f} (P-related stunting?)",
                delta, 1.0, {"feature": "ndvi_z", "value": ndvi_z}))

        # Evidence 2: User soil lab P (strongest)
        soil_p_status = evidence.get("soil_p_status")
        soil_p_ppm = evidence.get("soil_p_ppm")
        if soil_p_status is not None:
            if soil_p_status == "deficient":
                delta = 3.5
            elif soil_p_status == "adequate":
                delta = -2.5
            elif soil_p_status == "high":
                delta = -4.0
            else:
                delta = 0.0
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.P,
                f"Soil lab P={soil_p_ppm}ppm ({soil_p_status})",
                delta, 3.0, {"feature": "soil_p_ppm", "value": soil_p_ppm}))

        # Evidence 3: pH-dependent availability
        ph_avail = evidence.get("ph_p_availability", 1.0)
        if ph_avail < 0.7:
            delta = 1.0  # Low pH or high pH locks P
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.P,
                f"pH locks P availability ({ph_avail:.2f})",
                delta, 1.0, {"feature": "ph_p_availability", "value": ph_avail}))
            confounders.append(Confounder.PH_LOCKOUT)

        # ASMAE Chlorophyll integration (smaller effect than N)
        asmae_chloro = evidence.get("asmae_chlorophyll")
        if asmae_chloro is not None and asmae_chloro < 0.45:
            delta = 0.5
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.P, f"ASMAE Chlorophyll={asmae_chloro:.2f} (P-related chlorosis)",
                delta, 0.5, {"feature": "asmae_chlorophyll", "value": asmae_chloro}))

        prob = _sigmoid(logit)

        # Confidence
        conf = 0.70  # P inference is inherently less precise without tissue test
        if soil_p_status is not None:
            conf = 0.90  # Lab data boosts confidence
        if evidence.get("heterogeneity_flag"):
            conf -= 0.10
            confounders.append(Confounder.SPATIAL_HETEROGENEITY)

        # L3 structural confounders
        l3_mech_prob = self._get_l3_diagnosis_prob(l3_decision, "MECHANICAL_DAMAGE")
        if l3_mech_prob > 0.4:
            conf -= 0.20
            confounders.append(Confounder.MECHANICAL_DAMAGE)

        l3_weed_prob = self._get_l3_diagnosis_prob(l3_decision, "WEED_PRESSURE")
        if l3_weed_prob > 0.4:
            conf -= 0.15
            confounders.append(Confounder.WEED_COMPETITION)

        # CONTRACT-2 FIX: Disease confounder for P
        # Fungal root disease (e.g. Pythium, Phytophthora) impairs P uptake
        # even when soil P is adequate — confounds spectral interpretation.
        l3_disease_prob = self._get_l3_diagnosis_prob(l3_decision, "FUNGAL_DISEASE_RISK")
        if l3_disease_prob > 0.4:
            conf -= 0.20
            confounders.append(Confounder.DISEASE_RISK)

        # CONTRACT-2 FIX: Salinity confounder for P
        # High EC reduces P availability via ionic competition.
        l3_salinity_prob = self._get_l3_diagnosis_prob(l3_decision, "SALINITY_RISK")
        if l3_salinity_prob > 0.3:
            conf -= 0.15
            confounders.append(Confounder.SALINITY)

        # ASMAE confounders
        asmae_water = evidence.get("asmae_water_stress")
        if asmae_water is not None and asmae_water > 0.4:
            conf -= 0.20
            if Confounder.WATER_STRESS not in confounders:
                confounders.append(Confounder.WATER_STRESS)

        asmae_salinity = evidence.get("inferred_salinity_pressure")
        if asmae_salinity is not None and asmae_salinity > 0.4:
            conf -= 0.15
            if Confounder.SALINITY not in confounders:
                confounders.append(Confounder.SALINITY)

        asmae_biotic = evidence.get("asmae_biotic_risk")
        if asmae_biotic is not None and asmae_biotic > 0.4:
            conf -= 0.15
            if Confounder.DISEASE_RISK not in confounders:
                confounders.append(Confounder.DISEASE_RISK)

        conf = max(0.10, conf)

        return NutrientState(
            nutrient=Nutrient.P,
            state_index=round(-prob, 4),
            probability_deficient=round(prob, 4),
            confidence=round(conf, 4),
            severity=_severity_from_prob(prob),
            drivers_used=drivers,
            evidence_trace=trace,
            confounders=confounders,
            notes="P: soil lab + NDVI + pH availability",
        )

    # ------------------------------------------------------------------
    # Potassium
    # ------------------------------------------------------------------
    def _infer_potassium(
        self, evidence: Dict, swb: Any, l3_decision: Any,
    ) -> NutrientState:
        logit = -2.0  # Prior
        trace = []
        drivers = [Driver.NDVI]
        confounders = []

        # Evidence 1: Spatial heterogeneity (K deficiency → patchy leaf margins)
        if evidence.get("heterogeneity_flag"):
            delta = 1.0
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.K,
                "Spatial heterogeneity (K → patchy leaf margin scorch)",
                delta, 0.8, {"feature": "heterogeneity_flag", "value": True}))

        # Evidence 2: User soil lab K
        soil_k_status = evidence.get("soil_k_status")
        soil_k_ppm = evidence.get("soil_k_ppm")
        if soil_k_status is not None:
            if soil_k_status == "deficient":
                delta = 3.5
            elif soil_k_status == "adequate":
                delta = -2.0
            elif soil_k_status == "high":
                delta = -3.5
            else:
                delta = 0.0
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.K,
                f"Soil lab K={soil_k_ppm}ppm ({soil_k_status})",
                delta, 3.0, {"feature": "soil_k_ppm", "value": soil_k_ppm}))

        # ASMAE Chlorophyll integration (smaller effect than N)
        asmae_chloro = evidence.get("asmae_chlorophyll")
        if asmae_chloro is not None and asmae_chloro < 0.45:
            delta = 0.5
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.K, f"ASMAE Chlorophyll={asmae_chloro:.2f} (K-related chlorosis)",
                delta, 0.5, {"feature": "asmae_chlorophyll", "value": asmae_chloro}))

        # Evidence 3: Growth stall + no N deficiency → maybe K
        growth = evidence.get("growth_adequacy", 1.0)
        ndvi_z = evidence.get("ndvi_z", 0.0)
        if growth < 0.6 and ndvi_z > -1.0:
            delta = 0.8
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.K,
                f"Growth stall ({growth:.2f}) without NDVI drop (possible K limitation)",
                delta, 0.6, {"feature": "growth_adequacy", "value": growth}))

        # LOGIC-3 FIX: Expanded K evidence channels
        # Evidence 4: NDRE relationship to K
        # K deficiency reduces chlorophyll synthesis indirectly via Mg uptake
        # NDRE is sensitive to chlorophyll, so low NDRE + adequate soil K suggests
        # K is NOT the issue. Low NDRE + low soil K is confirmatory.
        ndre_z = evidence.get("ndre_z", 0.0)
        if ndre_z < -1.5 and soil_k_status == "deficient":
            delta = 1.2  # NDRE corroborates K deficiency
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.K,
                f"NDRE Z={ndre_z:.2f} corroborates K deficiency (chlorophyll via Mg uptake)",
                delta, 1.0, {"feature": "ndre_z", "value": ndre_z}))
        elif ndre_z > 0.5 and soil_k_status != "deficient":
            delta = -0.8  # Good NDRE + adequate K = likely not K-limited
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.K,
                f"NDRE Z={ndre_z:.2f} suggests adequate K (chlorophyll intact)",
                delta, 0.8, {"feature": "ndre_z", "value": ndre_z}))

        # LOGIC-3 FIX: Water stress interaction with K
        # K deficiency impairs stomatal regulation → crop is more drought-sensitive.
        # If SWB shows water stress AND K is low, K deficiency is more likely
        # the root cause than pure water deficit.
        water_stress = getattr(swb, "water_stress_index", 0.0) if swb else 0.0
        if water_stress > 0.3 and soil_k_status == "deficient":
            delta = 0.8
            logit += delta
            trace.append(EvidenceLogit(
                Driver.RAIN, Nutrient.K,
                f"Water stress ({water_stress:.2f}) + low soil K suggests K-impaired stomata",
                delta, 0.8, {"feature": "water_stress_x_k", "value": water_stress}))

        prob = _sigmoid(logit)

        # Confidence
        conf = 0.65  # K is hardest to diagnose remotely
        if soil_k_status is not None:
            conf = 0.88

        # L3 structural confounders
        l3_mech_prob = self._get_l3_diagnosis_prob(l3_decision, "MECHANICAL_DAMAGE")
        if l3_mech_prob > 0.4:
            conf -= 0.20
            confounders.append(Confounder.MECHANICAL_DAMAGE)

        l3_weed_prob = self._get_l3_diagnosis_prob(l3_decision, "WEED_PRESSURE")
        if l3_weed_prob > 0.4:
            conf -= 0.10
            confounders.append(Confounder.WEED_COMPETITION)

        # CONTRACT-2 FIX: Salinity confounder for K
        # High soil salinity disrupts K+ uptake via Na+/K+ competition.
        l3_salinity_prob = self._get_l3_diagnosis_prob(l3_decision, "SALINITY_RISK")
        if l3_salinity_prob > 0.3:
            conf -= 0.20
            confounders.append(Confounder.SALINITY)

        # ASMAE confounders
        asmae_water = evidence.get("asmae_water_stress")
        if asmae_water is not None and asmae_water > 0.4:
            conf -= 0.20
            if Confounder.WATER_STRESS not in confounders:
                confounders.append(Confounder.WATER_STRESS)

        asmae_salinity = evidence.get("inferred_salinity_pressure")
        if asmae_salinity is not None and asmae_salinity > 0.4:
            conf -= 0.20
            if Confounder.SALINITY not in confounders:
                confounders.append(Confounder.SALINITY)

        asmae_biotic = evidence.get("asmae_biotic_risk")
        if asmae_biotic is not None and asmae_biotic > 0.4:
            conf -= 0.20
            if Confounder.DISEASE_RISK not in confounders:
                confounders.append(Confounder.DISEASE_RISK)

        conf = max(0.10, conf)

        return NutrientState(
            nutrient=Nutrient.K,
            state_index=round(-prob, 4),
            probability_deficient=round(prob, 4),
            confidence=round(conf, 4),
            severity=_severity_from_prob(prob),
            drivers_used=drivers,
            evidence_trace=trace,
            confounders=confounders,
            notes="K: soil lab + spatial heterogeneity + growth stall + NDRE + water interaction",
        )

    # ------------------------------------------------------------------
    # Sulfur (SCI-1 FIX: New inference path)
    # ------------------------------------------------------------------
    def _infer_sulfur(
        self, evidence: Dict, swb: Any, l3_decision: Any,
    ) -> NutrientState:
        """Infer sulfur deficiency state.

        SCI-1 FIX: Sulfur is increasingly limiting in modern agriculture
        due to reduced atmospheric deposition (Clean Air Act). Critical for:
          - Canola/rapeseed: high S demand (15-25 kg S/ha)
          - Brassicas: glucosinolate synthesis requires S
          - Corn/wheat: S:N ratio affects protein quality

        Evidence channels:
          - NDVI yellowing pattern (S looks like N deficiency but on young leaves)
          - Soil pH (S is less available at high pH due to sulfate adsorption)
          - Leaching history (sulfate is mobile, like nitrate)
          - Crop type sensitivity

        References:
          - Scherer (2001): Sulphur in crop production
          - Grant et al. (2012): Sulfur response in canola
        """
        logit = -3.0  # Prior: S deficiency is relatively uncommon
        trace = []
        drivers = [Driver.NDVI]
        confounders = []

        # Evidence 1: NDVI Z-Score (S deficiency causes uniform chlorosis)
        # S deficiency yellows YOUNG leaves (unlike N which yellows old leaves)
        # Remotely, this is difficult to distinguish, so weaker signal than N.
        ndvi_z = evidence.get("ndvi_z", 0.0)
        if ndvi_z < -1.5:
            delta = 1.0  # Weaker than N (less specific)
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.S, f"Low NDVI Z={ndvi_z:.2f} (possible S chlorosis)",
                delta, 0.8, {"feature": "ndvi_z", "value": ndvi_z}))

        # Evidence 2: High leaching history (sulfate is mobile)
        leaching = getattr(swb, "leaching_risk_index", 0.0) if swb else 0.0
        if leaching > 0.4:
            delta = 1.2
            logit += delta
            trace.append(EvidenceLogit(
                Driver.RAIN, Nutrient.S, f"High leaching risk ({leaching:.2f}) — sulfate loss likely",
                delta, 1.0, {"feature": "leaching_risk_index", "value": leaching}))
            drivers.append(Driver.RAIN)

        # Evidence 3: Crop sensitivity
        # Canola/brassicas are the most S-demanding crops
        crop_stage = evidence.get("current_stage", "vegetative")
        # S demand peaks during reproductive stage
        if crop_stage in ("reproductive", "flowering"):
            delta = 0.5
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.S,
                f"Reproductive stage: peak S demand for protein/oil synthesis",
                delta, 0.6, {"feature": "stage_s_demand", "value": crop_stage}))

        # Evidence 4: Soil pH interaction
        # S availability decreases at very high pH (>8.0) and very low pH (<5.0)
        ph = evidence.get("user_soil_ph")
        if ph is not None:
            if ph > 8.0:
                delta = 0.6
                logit += delta
                trace.append(EvidenceLogit(
                    Driver.NDVI, Nutrient.S,
                    f"pH={ph:.1f}: sulfate adsorption increases at high pH",
                    delta, 0.5, {"feature": "ph_s_effect", "value": ph}))

        # Evidence 5: N:S ratio imbalance (if both N and S data available)
        # Optimal grain N:S ratio is ~15:1 for wheat, 10:1 for canola
        # If N is high but S is low, S becomes limiting
        soil_n_status = evidence.get("soil_n_status")
        if soil_n_status in ("adequate", "high"):
            delta = 0.5  # High N makes S more likely to be limiting
            logit += delta
            trace.append(EvidenceLogit(
                Driver.NDVI, Nutrient.S,
                f"High soil N ({soil_n_status}) shifts limitation toward S",
                delta, 0.6, {"feature": "n_s_ratio", "value": soil_n_status}))

        prob = _sigmoid(logit)

        # Confidence
        conf = 0.50  # S inference is inherently uncertain without tissue test
        if evidence.get("heterogeneity_flag"):
            conf -= 0.10
            confounders.append(Confounder.SPATIAL_HETEROGENEITY)

        # Water stress confounder
        water_stress = getattr(swb, "water_stress_index", 0.0) if swb else 0.0
        if water_stress > 0.4:
            conf -= 0.20
            confounders.append(Confounder.WATER_STRESS)

        conf = max(0.10, conf)

        return NutrientState(
            nutrient=Nutrient.S,
            state_index=round(-prob, 4),
            probability_deficient=round(prob, 4),
            confidence=round(conf, 4),
            severity=_severity_from_prob(prob),
            drivers_used=drivers,
            evidence_trace=trace,
            confounders=confounders,
            notes="S: leaching history + crop stage + pH + N:S ratio",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_l3_water_prob(l3_decision: Any) -> float:
        """Extract water stress probability from L3 decision output."""
        return NutrientInferenceEngine._get_l3_diagnosis_prob(l3_decision, "WATER_STRESS")

    @staticmethod
    def _get_l3_diagnosis_prob(l3_decision: Any, problem_id: str) -> float:
        """Extract probability of any L3 diagnosis by problem_id.

        Used to condition L4 inference on L3 structural diagnostics:
          - WATER_STRESS → water confounder
          - WEED_PRESSURE → weed competition confounder + N demand shift
          - MECHANICAL_DAMAGE → structural confounder
          - FUNGAL_DISEASE_RISK → root disease confounder (P/K uptake)
          - SALINITY_RISK → osmotic/ionic confounder (K uptake)
        """
        if l3_decision and hasattr(l3_decision, "diagnoses"):
            for d in l3_decision.diagnoses:
                if hasattr(d, "problem_id") and d.problem_id == problem_id:
                    return getattr(d, "probability", 0.0)
        return 0.0
