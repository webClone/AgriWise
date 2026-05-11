"""
Layer 8 Engine: IPM Cascade v8.2.0
===================================
Integrated Pest Management escalation with economic thresholds.

Scientific basis:
  - FAO IPM Guidelines: MONITOR -> SCOUT -> BIOLOGICAL -> CHEMICAL
  - Economic Injury Level (EIL) = cost_of_control / (crop_value * damage_per_pest)
  - Action Threshold (AT) = EIL * safety_factor (typically 0.75)
  - Spray only when pest_pressure > AT (prevents prophylactic spraying)
  - Pre-harvest intervals (PHI) from EPA/PMRA registrations
  - Resistance management: rotate mode-of-action groups
"""
import logging
from typing import Dict, List, Optional
from layer8_prescriptive.schema import (
    ActionCard, ActionType, IPMDecision, IPMLevel,
    PrescriptiveEvidence, PrescriptiveDegradation,
)

logger = logging.getLogger(__name__)

# Economic Injury Levels by pest class (normalized 0-1)
# Real EIL depends on crop value, control cost, and damage coefficient
_EIL_TABLE = {
    "FUNGAL":     0.35,  # fungal pathogens need moderate pressure to justify spray
    "RUST":       0.30,  # rusts spread fast - lower threshold
    "MILDEW":     0.40,  # powdery mildew - moderate threshold
    "BACTERIAL":  0.45,  # harder to control chemically
    "BLIGHT":     0.25,  # blights can be devastating - lower threshold
    "INSECT":     0.35,  # general insect pressure
    "BORER":      0.30,  # borers cause structural damage
    "CHEWING":    0.40,  # leaf-chewing insects
    "SUCKING":    0.45,  # aphids/whitefly - tolerance is higher
    "WEED":       0.50,  # weeds compete slowly - higher threshold
    "NEMATODE":   0.55,  # soil nematodes - difficult to assess
}

# Mode-of-action groups for resistance management
_MOA_GROUPS = {
    "FUNGAL":    ["FRAC_3_DMI", "FRAC_7_SDHI", "FRAC_11_QoI", "FRAC_M_MULTI"],
    "INSECT":    ["IRAC_1A_OP", "IRAC_3A_PYRETHROID", "IRAC_4A_NEONICOTINOID", "IRAC_28_DIAMIDE"],
    "WEED":      ["HRAC_A_ACCASE", "HRAC_B_ALS", "HRAC_G_EPSPS", "HRAC_K1_DNANILINE"],
}

# Pre-harvest intervals (days) by pest class
_PHI_DAYS = {
    "FUNGAL": 14, "RUST": 14, "MILDEW": 7, "BACTERIAL": 21,
    "BLIGHT": 14, "INSECT": 7, "BORER": 14, "CHEWING": 7,
    "SUCKING": 3, "WEED": 30, "NEMATODE": 60,
}

_SAFETY_FACTOR = 0.75


class IPMCascadeEngine:
    """
    5-level IPM escalation engine.

    Ladder: MONITOR -> SCOUT -> BIOLOGICAL -> CHEMICAL_TARGETED -> CHEMICAL_BROAD

    Each threat is evaluated against its Economic Injury Level.
    Actions are only escalated when pest_pressure exceeds the Action Threshold.
    """

    def evaluate_threat(self,
                        threat_id: str,
                        probability: float,
                        severity: float,
                        degradation: PrescriptiveDegradation,
                        days_to_harvest: int = 60) -> IPMDecision:
        """Evaluate a single threat through the IPM cascade."""
        pest_class = self._classify_pest(threat_id)
        eil = _EIL_TABLE.get(pest_class, 0.40)
        at = eil * _SAFETY_FACTOR
        pressure = probability * severity
        above_threshold = pressure > at
        phi = _PHI_DAYS.get(pest_class, 14)

        # Determine escalation level
        if degradation in (PrescriptiveDegradation.VERY_LOW_TRUST,
                           PrescriptiveDegradation.CONFLICT_FLAG):
            # Low trust: never escalate beyond SCOUT
            level = IPMLevel.SCOUT if pressure > 0.15 else IPMLevel.MONITOR
        elif not above_threshold:
            # Below AT: monitor or scout
            level = IPMLevel.SCOUT if pressure > at * 0.5 else IPMLevel.MONITOR
        elif days_to_harvest < phi:
            # Too close to harvest for chemical: use biological
            level = IPMLevel.BIOLOGICAL
        elif pressure > eil * 1.5:
            # Severe: targeted chemical
            level = IPMLevel.CHEMICAL_TARGETED
        elif pressure > eil * 2.5:
            # Emergency: broad-spectrum (last resort)
            level = IPMLevel.CHEMICAL_BROAD
        else:
            # Above AT but moderate: try biological first
            level = IPMLevel.BIOLOGICAL

        # Resistance risk based on repeated chemical use
        resistance = "LOW"
        if level in (IPMLevel.CHEMICAL_TARGETED, IPMLevel.CHEMICAL_BROAD):
            resistance = "MODERATE" if pressure < eil * 2.0 else "HIGH"

        # Recommended mode-of-action (rotate to prevent resistance)
        moa_groups = _MOA_GROUPS.get(pest_class, _MOA_GROUPS.get("INSECT", []))
        # Simple rotation: pick group based on hash of threat_id
        moa_idx = hash(threat_id) % max(1, len(moa_groups))
        moa = moa_groups[moa_idx] if moa_groups else "UNSPECIFIED"

        explain_parts = [
            "IPM: {} -> {}".format(pest_class, level.value),
            "pressure={:.2f} AT={:.2f} EIL={:.2f}".format(pressure, at, eil),
        ]
        if days_to_harvest < phi:
            explain_parts.append("PHI violation ({}d < {}d)".format(days_to_harvest, phi))

        return IPMDecision(
            threat_id=threat_id,
            escalation_level=level,
            economic_injury_level=round(eil, 3),
            action_threshold=round(at, 3),
            current_pressure=round(pressure, 3),
            above_threshold=above_threshold,
            pre_harvest_interval_days=phi,
            resistance_risk=resistance,
            recommended_mode_of_action=moa,
            explain="; ".join(explain_parts),
        )

    def apply_ipm_decisions(self,
                            action_cards: List[ActionCard],
                            bio_threats: Dict[str, dict],
                            degradation: PrescriptiveDegradation,
                            days_to_harvest: int = 60) -> List[ActionCard]:
        """Apply IPM cascade to all threat-derived action cards."""
        for card in action_cards:
            if card.action_type not in (ActionType.SPRAY, ActionType.SCOUT):
                continue

            # Find matching threat from evidence
            threat_id = None
            prob, sev = 0.3, 0.5
            for ev in card.evidence:
                if ev.source_layer == "L5" or ev.evidence_type == "threat":
                    threat_id = ev.reference_id
                    prob = max(0.1, ev.contribution)
                    break
                elif ev.source_layer == "L3":
                    # Diagnosis-derived pest action
                    pid = ev.reference_id.upper()
                    if any(k in pid for k in ("FUNGAL", "RUST", "INSECT", "BORER",
                                               "MILDEW", "BLIGHT", "WEED", "BACTERIAL")):
                        threat_id = ev.reference_id
                        prob = max(0.1, ev.contribution)
                        sev = min(1.0, ev.contribution * 1.5)
                        break

            if threat_id is None:
                continue

            ipm = self.evaluate_threat(threat_id, prob, sev, degradation, days_to_harvest)
            card.ipm_decision = ipm

            # Enforce IPM level -> ActionType mapping
            ipm_action_map = {
                IPMLevel.MONITOR: ActionType.MONITOR,
                IPMLevel.SCOUT: ActionType.SCOUT,
                IPMLevel.BIOLOGICAL: ActionType.SCOUT,  # biological mapped to scout for now
                IPMLevel.CHEMICAL_TARGETED: ActionType.SPRAY,
                IPMLevel.CHEMICAL_BROAD: ActionType.SPRAY,
            }
            correct_type = ipm_action_map.get(ipm.escalation_level, ActionType.SCOUT)

            if card.action_type == ActionType.SPRAY and correct_type != ActionType.SPRAY:
                # IPM says don't spray yet - downgrade
                card.action_type = correct_type
                card.rate = None  # no rate for scout/monitor
                card.explain += " [IPM: downgraded to {}]".format(correct_type.value)

            if not ipm.above_threshold:
                card.explain += " [below AT={:.2f}]".format(ipm.action_threshold)

        logger.debug("IPM cascade applied to %d cards", len(action_cards))
        return action_cards

    @staticmethod
    def _classify_pest(threat_id: str) -> str:
        tid = threat_id.upper()
        for cls in ("RUST", "MILDEW", "BLIGHT", "FUNGAL", "BACTERIAL",
                     "BORER", "CHEWING", "SUCKING", "INSECT", "WEED", "NEMATODE"):
            if cls in tid:
                return cls
        return "INSECT"


ipm_engine = IPMCascadeEngine()
