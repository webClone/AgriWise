"""
Layer 8 Engine: Environmental Risk Scoring v8.2.0
=================================================
Leaching, runoff, and buffer zone compliance scoring.

Scientific basis:
  - Nitrate leaching index: f(soil_clay%, organic_matter, rain_forecast, rate)
    Sandy soils (clay<15%) have 3-5x higher leaching potential
  - Runoff potential: f(slope, soil_saturation, forecast_rain)
    EPA USLE-based estimation
  - Storm event rule: no fertilizer/spray application within 48h of >25mm rain
  - Buffer zones: minimum 10m from waterways (EU/EPA guideline)
"""
import logging
from typing import Dict, List, Optional
from layer8_prescriptive.schema import (
    ActionCard, ActionType, EnvironmentalRiskScore, RateRange,
)

logger = logging.getLogger(__name__)

# Action types that carry environmental risk
_RISK_ACTIONS = {ActionType.FERTILIZE, ActionType.SPRAY, ActionType.IRRIGATE}

# Storm threshold (mm in 48h forecast)
_STORM_THRESHOLD_MM = 25.0


class EnvironmentalRiskEngine:
    """
    Scores environmental risk for each actionable recommendation.

    Applies penalties to action priority scores and can block
    or delay applications when risk exceeds thresholds.
    """

    def score_risk(self,
                   card: ActionCard,
                   soil_clay_pct: float = 22.0,
                   soil_org_carbon: float = 1.8,
                   forecast_rain_48h: float = 0.0,
                   slope_pct: float = 2.0) -> EnvironmentalRiskScore:
        """Score environmental risk for a single action card."""
        risk_factors = []

        if card.action_type not in _RISK_ACTIONS:
            return EnvironmentalRiskScore(
                leaching_index=0.0, runoff_potential=0.0,
                buffer_compliance=True, storm_event_risk=False,
                environmental_penalty=0.0, risk_factors=[],
                recommendation="PROCEED",
            )

        # --- Leaching index ---
        # Sandy soil (low clay) + high rain + high rate = high leaching
        clay_factor = max(0, 1.0 - soil_clay_pct / 40.0)  # 0 at 40% clay, 1 at 0%
        rain_factor = min(1.0, forecast_rain_48h / 50.0)
        rate_factor = 0.0
        if card.rate:
            # Normalize rate: 200 kg_N/ha is high, 20mm irrigation is moderate
            if card.action_type == ActionType.FERTILIZE:
                rate_factor = min(1.0, card.rate.recommended / 200.0)
            elif card.action_type == ActionType.SPRAY:
                rate_factor = min(1.0, card.rate.recommended / 5.0)
            else:
                rate_factor = min(1.0, card.rate.recommended / 60.0)
        oc_protection = min(0.3, soil_org_carbon / 10.0)  # organic matter buffers leaching
        leaching = max(0, min(1.0, clay_factor * 0.4 + rain_factor * 0.35
                              + rate_factor * 0.25 - oc_protection))
        if leaching > 0.5:
            risk_factors.append("High leaching risk (sandy soil + rain forecast)")

        # --- Runoff potential ---
        slope_factor = min(1.0, slope_pct / 15.0)
        saturation_est = min(1.0, forecast_rain_48h / 40.0)
        runoff = max(0, min(1.0, slope_factor * 0.5 + saturation_est * 0.3
                            + rain_factor * 0.2))
        if runoff > 0.5:
            risk_factors.append("Runoff risk (slope={:.0f}%, rain forecast)".format(slope_pct))

        # --- Storm event ---
        storm_risk = forecast_rain_48h > _STORM_THRESHOLD_MM
        if storm_risk:
            risk_factors.append("Storm event >{}mm within 48h".format(_STORM_THRESHOLD_MM))

        # --- Buffer compliance (assumed True unless flagged) ---
        buffer_ok = True  # would check GIS distance to waterways

        # --- Environmental penalty ---
        penalty = max(0, min(0.8, leaching * 0.4 + runoff * 0.3 + (0.3 if storm_risk else 0)))

        # --- Recommendation ---
        if storm_risk and card.action_type in (ActionType.FERTILIZE, ActionType.SPRAY):
            recommendation = "DELAY"
        elif penalty > 0.6:
            recommendation = "REDUCE_RATE"
        elif penalty > 0.8:
            recommendation = "PROHIBIT"
        else:
            recommendation = "PROCEED"

        return EnvironmentalRiskScore(
            leaching_index=round(leaching, 3),
            runoff_potential=round(runoff, 3),
            buffer_compliance=buffer_ok,
            storm_event_risk=storm_risk,
            environmental_penalty=round(penalty, 3),
            risk_factors=risk_factors,
            recommendation=recommendation,
        )

    def apply_risk_scores(self,
                          action_cards: List[ActionCard],
                          soil_static: Dict,
                          forecast: List[Dict]) -> List[ActionCard]:
        """Apply environmental risk scoring to all action cards."""
        clay = soil_static.get("soil_clay", 22.0)
        oc = soil_static.get("soil_org_carbon", 1.8)

        # Estimate 48h total precipitation from forecast
        rain_48h = 0.0
        for day in forecast[:2]:
            rain_48h += day.get("precipitation", day.get("rain", day.get("rain_mm", 0)))

        for card in action_cards:
            risk = self.score_risk(card, clay, oc, rain_48h)
            card.env_risk = risk

            if risk.environmental_penalty > 0.05:
                # Apply penalty to cost_score (higher penalty = lower desirability)
                card.priority_breakdown.cost_score = max(
                    0, card.priority_breakdown.cost_score - risk.environmental_penalty * 0.5)

            if risk.recommendation == "DELAY" and card.action_type in _RISK_ACTIONS:
                card.explain += " [ENV: delay recommended - storm risk]"
            elif risk.recommendation == "REDUCE_RATE" and card.rate:
                orig = card.rate.recommended
                reduced = round(orig * 0.7, 1)
                card.rate = RateRange(
                    recommended=reduced,
                    min_safe=card.rate.min_safe,
                    max_safe=card.rate.max_safe,
                    unit=card.rate.unit,
                )
                card.explain += " [ENV: rate reduced {}->{} for leaching]".format(orig, reduced)

        logger.debug("Environmental risk: clay=%.0f%% OC=%.1f rain48h=%.0fmm",
                     clay, oc, rain_48h)
        return action_cards


env_risk_engine = EnvironmentalRiskEngine()
