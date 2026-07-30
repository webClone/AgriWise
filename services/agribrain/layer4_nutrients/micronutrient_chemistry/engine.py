"""
Layer 4.19: Micronutrient Chemistry Engine — pH-Dependent Availability & Chelation.

Models availability of Fe, Zn, Mn, B, Cu as a function of soil pH,
organic matter, redox conditions, and nutrient interactions.

Science:
  Micronutrient availability is primarily governed by:
  1. pH-solubility: Fe, Zn, Mn solubility decreases ~100-fold per pH unit rise
     above pH 6.5 (Lindsay 1979). In calcareous soils, Fe chlorosis is the
     #1 micronutrient disorder worldwide.
  2. Redox: Mn and Fe shift between soluble (reduced) and insoluble (oxidized)
     forms. Waterlogging increases Mn²⁺ availability (sometimes to toxic levels).
  3. Organic complexation: Humic/fulvic acids chelate metals, keeping them
     soluble across a wide pH range.
  4. Antagonisms: P→Zn (phosphate-induced Zn deficiency), Ca→Fe (bicarbonate-
     induced Fe chlorosis), Mn↔Fe (competitive uptake).

References:
  - Lindsay (1979): Chemical Equilibria in Soils, Wiley
  - Rengel (2015): Marschner's Mineral Nutrition of Higher Plants, Ch. 7
  - Alloway (2008): Micronutrient Deficiencies in Global Crop Production, Springer
  - Mortvedt et al. (1991): Micronutrients in Agriculture, SSSA Book Series 4
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MicronutrientStatus:
    """Status for a single micronutrient."""
    nutrient: str = ""                    # Fe, Zn, Mn, B, Cu
    availability_index: float = 1.0       # [0-1], 1.0 = fully available
    status: str = "ADEQUATE"              # DEFICIENT, LOW, ADEQUATE, HIGH, TOXIC
    risk_probability: float = 0.0         # Probability of deficiency [0-1]

    # Controlling factors
    ph_factor: float = 1.0               # pH effect on availability
    redox_factor: float = 1.0            # Redox effect (Fe, Mn)
    om_chelation_factor: float = 1.0     # OM chelation effect
    antagonism_factor: float = 1.0       # Cross-nutrient antagonism

    # Recommendations
    recommendation: str = ""
    product: str = ""                     # Recommended product (e.g., "Fe-EDDHA")
    rate_kg_ha: float = 0.0


@dataclass
class MicronutrientResult:
    """Micronutrient chemistry assessment output."""
    statuses: Dict[str, MicronutrientStatus] = field(default_factory=dict)
    limiting_micronutrient: Optional[str] = None
    overall_risk: str = "LOW"             # LOW, MODERATE, HIGH
    notes: str = ""


# pH-availability curves for each micronutrient
# {nutrient: [(ph_breakpoint, availability_fraction), ...]}
# Interpolated linearly between breakpoints
_PH_CURVES = {
    "Fe": [(4.0, 1.0), (5.5, 0.9), (6.5, 0.6), (7.0, 0.3), (7.5, 0.15), (8.0, 0.05), (8.5, 0.02)],
    "Zn": [(4.0, 1.0), (5.0, 0.9), (6.0, 0.7), (6.5, 0.5), (7.0, 0.3), (7.5, 0.15), (8.0, 0.08)],
    "Mn": [(4.0, 1.0), (5.0, 0.95), (5.5, 0.8), (6.0, 0.6), (6.5, 0.4), (7.0, 0.25), (8.0, 0.10)],
    "B":  [(4.0, 0.4), (5.0, 0.6), (6.0, 0.9), (7.0, 1.0), (8.0, 0.7), (9.0, 0.3)],
    "Cu": [(4.0, 0.7), (5.0, 0.8), (5.5, 0.9), (6.5, 1.0), (7.5, 0.6), (8.0, 0.4), (8.5, 0.2)],
}

# Critical soil test levels (DTPA extraction, mg/kg)
_CRITICAL_LEVELS = {
    "Fe": {"deficient": 2.5, "low": 4.5, "adequate": 10.0, "high": 50.0},
    "Zn": {"deficient": 0.5, "low": 1.0, "adequate": 3.0,  "high": 10.0},
    "Mn": {"deficient": 1.0, "low": 2.0, "adequate": 5.0,  "high": 50.0, "toxic": 100.0},
    "B":  {"deficient": 0.1, "low": 0.5, "adequate": 1.0,  "high": 2.0,  "toxic": 5.0},
    "Cu": {"deficient": 0.2, "low": 0.5, "adequate": 2.0,  "high": 10.0},
}

# Chelation products by nutrient and pH
_CHELATION_PRODUCTS = {
    "Fe": {
        "acid":     ("FeSO4", "Ferrous sulfate (FeSO₄·7H₂O)", 10.0),
        "neutral":  ("Fe-EDTA", "Iron chelate EDTA", 3.0),
        "alkaline": ("Fe-EDDHA", "Iron chelate EDDHA (ortho-ortho)", 2.0),
    },
    "Zn": {
        "any": ("ZnSO4", "Zinc sulfate (ZnSO₄·7H₂O)", 5.0),
        "foliar": ("Zn-EDTA", "Zinc chelate EDTA foliar", 0.5),
    },
    "Mn": {
        "any": ("MnSO4", "Manganese sulfate", 5.0),
        "foliar": ("Mn-EDTA", "Manganese chelate foliar", 1.0),
    },
    "B": {
        "any": ("Borax", "Sodium tetraborate (Borax)", 1.0),
        "foliar": ("Solubor", "Sodium octaborate foliar", 0.5),
    },
    "Cu": {
        "any": ("CuSO4", "Copper sulfate", 2.0),
    },
}


class MicronutrientChemistryEngine:
    """Assesses micronutrient availability from soil chemistry."""

    def assess_availability(
        self,
        ph: float = 6.5,
        organic_matter_pct: float = 2.0,
        clay_pct: float = 22.0,
        water_stress_index: float = 0.0,
        p_applied_kg_ha: float = 0.0,
        soil_fe_ppm: Optional[float] = None,
        soil_zn_ppm: Optional[float] = None,
        soil_mn_ppm: Optional[float] = None,
        soil_b_ppm: Optional[float] = None,
        soil_cu_ppm: Optional[float] = None,
        crop_type: str = "wheat",
        bicarbonate_meq: Optional[float] = None,
    ) -> MicronutrientResult:
        """Full micronutrient availability assessment.

        Args:
            ph: Soil pH (water extraction)
            organic_matter_pct: Soil OM (%)
            clay_pct: Clay content (%)
            water_stress_index: 0=wet, 1=dry (affects Mn/Fe redox)
            p_applied_kg_ha: Applied P (affects Zn availability)
            soil_fe_ppm: DTPA-extractable Fe (mg/kg), optional
            soil_zn_ppm: DTPA-extractable Zn (mg/kg), optional
            soil_mn_ppm: DTPA-extractable Mn (mg/kg), optional
            soil_b_ppm: Hot-water extractable B (mg/kg), optional
            soil_cu_ppm: DTPA-extractable Cu (mg/kg), optional
            crop_type: Crop code
            bicarbonate_meq: Active CaCO₃ (meq/L), optional
        """
        soil_tests = {
            "Fe": soil_fe_ppm, "Zn": soil_zn_ppm, "Mn": soil_mn_ppm,
            "B": soil_b_ppm, "Cu": soil_cu_ppm,
        }

        statuses = {}
        worst_risk = 0.0
        limiting = None

        for nutrient in ["Fe", "Zn", "Mn", "B", "Cu"]:
            # 1. pH availability factor
            ph_f = self._ph_availability(nutrient, ph)

            # 2. Redox factor (Fe, Mn)
            redox_f = self._redox_factor(nutrient, water_stress_index)

            # 3. OM chelation factor
            om_f = self._om_chelation_factor(nutrient, organic_matter_pct, ph)

            # 4. Antagonism factors
            antag_f = self._antagonism_factor(nutrient, ph, p_applied_kg_ha, bicarbonate_meq)

            # 5. Combined availability index
            availability = ph_f * redox_f * om_f * antag_f
            availability = max(0.01, min(1.0, availability))

            # 6. Classify status using soil test or modeled availability
            soil_test = soil_tests.get(nutrient)
            status, risk_prob = self._classify_status(
                nutrient, soil_test, availability, ph,
            )

            # 7. Recommendation
            rec, product, rate = self._recommend_product(
                nutrient, status, ph, availability,
            )

            ms = MicronutrientStatus(
                nutrient=nutrient,
                availability_index=round(availability, 4),
                status=status,
                risk_probability=round(risk_prob, 4),
                ph_factor=round(ph_f, 4),
                redox_factor=round(redox_f, 4),
                om_chelation_factor=round(om_f, 4),
                antagonism_factor=round(antag_f, 4),
                recommendation=rec,
                product=product,
                rate_kg_ha=rate,
            )
            statuses[nutrient] = ms

            if risk_prob > worst_risk:
                worst_risk = risk_prob
                limiting = nutrient

        # Overall risk classification
        if worst_risk > 0.7:
            overall = "HIGH"
        elif worst_risk > 0.4:
            overall = "MODERATE"
        else:
            overall = "LOW"

        notes_parts = []
        for nut, st in statuses.items():
            if st.status in ("DEFICIENT", "LOW"):
                notes_parts.append(
                    f"{nut}: {st.status} (availability={st.availability_index:.2f}, "
                    f"pH effect={st.ph_factor:.2f})"
                )
            elif st.status == "TOXIC":
                notes_parts.append(f"{nut}: TOXIC risk — reduce inputs or lime")
        if not notes_parts:
            notes_parts.append("All micronutrients within adequate range")

        return MicronutrientResult(
            statuses=statuses,
            limiting_micronutrient=limiting if worst_risk > 0.3 else None,
            overall_risk=overall,
            notes="; ".join(notes_parts),
        )

    def _ph_availability(self, nutrient: str, ph: float) -> float:
        """Interpolate pH-availability curve for a nutrient."""
        curve = _PH_CURVES.get(nutrient, [(5.0, 0.8), (7.0, 0.5)])
        # Linear interpolation
        if ph <= curve[0][0]:
            return curve[0][1]
        if ph >= curve[-1][0]:
            return curve[-1][1]
        for i in range(len(curve) - 1):
            ph_lo, val_lo = curve[i]
            ph_hi, val_hi = curve[i + 1]
            if ph_lo <= ph <= ph_hi:
                frac = (ph - ph_lo) / (ph_hi - ph_lo)
                return val_lo + frac * (val_hi - val_lo)
        return 0.5

    def _redox_factor(self, nutrient: str, water_stress: float) -> float:
        """Redox-dependent availability for Fe and Mn.

        Waterlogging (low water_stress) → reducing conditions →
        Fe²⁺ and Mn²⁺ become soluble. Dry conditions → oxidized →
        insoluble Fe³⁺/Mn⁴⁺.

        For Mn in very wet soils, can reach toxic levels.
        """
        if nutrient not in ("Fe", "Mn"):
            return 1.0

        # water_stress: 0 = wet/saturated, 1 = dry
        # Wet conditions increase availability (reducing)
        if nutrient == "Fe":
            return max(0.3, 1.0 - water_stress * 0.4)
        else:  # Mn
            # Mn is very redox-sensitive: wet → very available, dry → low
            return max(0.2, 1.2 - water_stress * 0.8)

    def _om_chelation_factor(
        self, nutrient: str, om_pct: float, ph: float,
    ) -> float:
        """Organic matter chelation keeps metals soluble.

        Humic and fulvic acids form stable complexes with Fe, Zn, Cu, Mn.
        This is especially important in alkaline soils where inorganic
        forms are insoluble.

        Reference: Stevenson (1991), Humus Chemistry, Wiley.
        """
        if nutrient == "B":
            return 1.0  # B is not chelated by OM

        if om_pct < 1.0:
            return 0.8  # Low OM → poor chelation
        # Log relationship — diminishing returns
        chelation = 0.8 + 0.15 * math.log(om_pct)
        # More important in alkaline soils
        if ph > 7.0:
            chelation *= 1.2
        return max(0.7, min(1.5, chelation))

    def _antagonism_factor(
        self, nutrient: str, ph: float,
        p_applied: float, bicarbonate: Optional[float],
    ) -> float:
        """Cross-nutrient antagonism effects.

        Key antagonisms:
        - P → Zn: High P reduces Zn uptake (Loneragan et al. 1979)
        - Bicarbonate → Fe: Active CaCO₃ induces Fe chlorosis
        - Fe ↔ Mn: Competitive uptake at root surface
        """
        factor = 1.0

        if nutrient == "Zn" and p_applied > 40:
            # P-induced Zn deficiency: common in calcareous soils
            p_effect = 1.0 - min(0.4, (p_applied - 40) / 200)
            factor *= p_effect

        if nutrient == "Fe" and bicarbonate is not None and bicarbonate > 5:
            # Bicarbonate-induced Fe chlorosis (calcareous soils)
            bicarb_effect = max(0.2, 1.0 - (bicarbonate - 5) / 30)
            factor *= bicarb_effect

        return max(0.1, factor)

    def _classify_status(
        self, nutrient: str, soil_test: Optional[float],
        availability: float, ph: float,
    ) -> tuple:
        """Classify micronutrient status and risk probability."""
        levels = _CRITICAL_LEVELS.get(nutrient, {})

        if soil_test is not None:
            # Direct soil test classification
            if soil_test < levels.get("deficient", 0.5):
                return "DEFICIENT", 0.90
            elif soil_test < levels.get("low", 1.0):
                return "LOW", 0.65
            elif soil_test < levels.get("adequate", 3.0):
                return "ADEQUATE", 0.20
            elif soil_test < levels.get("high", 10.0):
                return "HIGH", 0.05
            elif "toxic" in levels and soil_test > levels["toxic"]:
                return "TOXIC", 0.10
            else:
                return "HIGH", 0.05
        else:
            # Model-based classification from availability index
            if availability < 0.15:
                return "DEFICIENT", 0.80
            elif availability < 0.30:
                return "LOW", 0.55
            elif availability < 0.60:
                return "ADEQUATE", 0.20
            else:
                return "ADEQUATE", 0.05

    def _recommend_product(
        self, nutrient: str, status: str, ph: float, availability: float,
    ) -> tuple:
        """Recommend correction product for deficient micronutrients."""
        if status not in ("DEFICIENT", "LOW"):
            return "", "", 0.0

        products = _CHELATION_PRODUCTS.get(nutrient, {})
        if nutrient == "Fe":
            if ph > 7.5:
                p = products.get("alkaline", ("Fe-EDDHA", "Iron chelate EDDHA", 2.0))
            elif ph > 6.5:
                p = products.get("neutral", ("Fe-EDTA", "Iron chelate EDTA", 3.0))
            else:
                p = products.get("acid", ("FeSO4", "Ferrous sulfate", 10.0))
            return f"Apply {p[1]} at {p[2]} kg/ha", p[0], p[2]
        else:
            # Use general product
            p = products.get("any", products.get("foliar", ("", "", 0.0)))
            rec = f"Apply {p[1]} at {p[2]} kg/ha"
            if status == "DEFICIENT" and "foliar" in products:
                fp = products["foliar"]
                rec += f" or foliar {fp[1]} at {fp[2]} kg/ha for rapid correction"
            return rec, p[0], p[2]
