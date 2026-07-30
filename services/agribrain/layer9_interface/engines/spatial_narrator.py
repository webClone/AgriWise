"""
Engine 9: Spatial Narrator v9.6.0

Translates L10 zone packs into human-readable spatial stories.
"""
import logging
from typing import Dict, Any, List
from layer9_interface.schema import Layer9Input, PersonaConfig, ExpertiseLevel

logger = logging.getLogger(__name__)


class SpatialNarratorEngine:
    """Converts L10 spatial zones into persona-adaptive narratives."""

    def narrate(self, l9_input: Layer9Input, persona: PersonaConfig) -> Dict[str, Any]:
        exp = persona.expertise_level
        stories: List[str] = []
        zone_plan = l9_input.zone_plan if isinstance(l9_input.zone_plan, dict) else {}

        for zid, zdata in zone_plan.items():
            if not isinstance(zdata, dict):
                continue
            sev = zdata.get("spatial_severity", 0)
            conf = zdata.get("spatial_confidence", 0)
            ztype = zdata.get("zone_type", "")
            area = zdata.get("area_pct", 0)
            drivers = zdata.get("top_drivers", [])
            label = zdata.get("label", zid)
            desc = zdata.get("description", "")

            if sev > 0 or ztype:
                stories.append(self._narrate_zone(
                    zid, label, desc, sev, conf, area, ztype, drivers, exp
                ))

        if not stories:
            if exp == ExpertiseLevel.NOVICE:
                summary = "No spatial patterns detected — your field looks uniform! 🌾"
            else:
                summary = "No significant spatial heterogeneity detected."
        else:
            if exp == ExpertiseLevel.NOVICE:
                summary = f"We found {len(stories)} area(s) in your field that need attention 🗺️"
            else:
                summary = f"{len(stories)} heterogeneity zone(s) identified."

        return {
            "summary": summary,
            "zone_stories": stories,
            "n_zones": len(stories),
            "engine": "spatial_narrator",
        }

    def _narrate_zone(self, zid, label, desc, sev, conf, area, ztype, drivers, exp):
        if exp == ExpertiseLevel.NOVICE:
            sev_word = "stressed" if sev > 0.6 else "a bit different"
            return f"The '{label or zid}' area ({area:.0f}% of field) looks {sev_word}. {desc}"
        elif exp == ExpertiseLevel.FARMER:
            return f"Zone {zid}: {ztype}, severity {sev:.0%}, covers {area:.0f}% of field. {desc}"
        elif exp == ExpertiseLevel.TECHNICIAN:
            driver_str = ", ".join(str(d) for d in drivers[:3]) if drivers else "N/A"
            return f"Zone {zid} [{ztype}]: sev={sev:.2f}, conf={conf:.2f}, area={area:.1f}%. Drivers: {driver_str}"
        else:
            driver_str = ", ".join(str(d) for d in drivers[:5]) if drivers else "none"
            return f"{zid}|{ztype}|s={sev:.3f}|c={conf:.3f}|a={area:.2f}%|drivers=[{driver_str}]"


spatial_narrator = SpatialNarratorEngine()
