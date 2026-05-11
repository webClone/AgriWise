"""
Layer 0: User Input Adapter — Normalizes farmer-declared data into ObservationPackets.

Converts PlotRegistration, SoilAnalysis, IrrigationEvent, and ManagementEvent
into standard ObservationPackets with proper QA metadata, uncertainty models,
and provenance chains.

Also produces:
  - soil_props dict for StateVector.initial() seeding
  - crop_params overrides for ProcessModel (crop-specific GDD thresholds, Kc)
  - process_forcing_events list for Kalman predict() step

Uncertainty philosophy: all inputs carry uncertainty but near ground truth.
  - Lab soil: high confidence (0.90), small sigma per variable
  - Irrigation: moderate-high confidence (0.85), σ = 10% of amount
  - Crop/dates: near-ground-truth confidence (0.95)
  - Geometry: ground truth (1.0)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from layer0.observation_packet import (
    ObservationPacket, ObservationSource, ObservationType,
    QAMetadata, QAFlag, UncertaintyModel, Provenance,
    ObservationRegistry,
)
from layer0.user_input_schema import (
    UserInputPackage, PlotRegistration, SoilAnalysis,
    IrrigationEvent, ManagementEvent, SOIL_LAB_SIGMA,
    IRRIGATION_SIGMA_FRACTION,
)


# ============================================================================
# Crop Parameter Library (crop_type → ProcessModel overrides)
# ============================================================================

CROP_PARAMS_LIBRARY = {
    "corn": {
        "t_base": 10.0, "t_opt": 30.0, "t_max": 38.0,
        "gdd_vegetative": 250, "gdd_flowering": 900,
        "gdd_ripening": 1400, "gdd_senescence": 1800,
        "lai_max": 6.0, "kc_mid": 1.20,
        "lai_growth_rate": 0.05, "lai_decay_rate": 0.025,
    },
    "wheat": {
        "t_base": 0.0, "t_opt": 22.0, "t_max": 32.0,
        "gdd_vegetative": 150, "gdd_flowering": 700,
        "gdd_ripening": 1100, "gdd_senescence": 1500,
        "lai_max": 5.0, "kc_mid": 1.15,
        "lai_growth_rate": 0.04, "lai_decay_rate": 0.02,
    },
    "soybean": {
        "t_base": 10.0, "t_opt": 28.0, "t_max": 35.0,
        "gdd_vegetative": 200, "gdd_flowering": 750,
        "gdd_ripening": 1200, "gdd_senescence": 1600,
        "lai_max": 5.5, "kc_mid": 1.15,
        "lai_growth_rate": 0.045, "lai_decay_rate": 0.02,
    },
    "rice": {
        "t_base": 10.0, "t_opt": 30.0, "t_max": 40.0,
        "gdd_vegetative": 300, "gdd_flowering": 1000,
        "gdd_ripening": 1500, "gdd_senescence": 1900,
        "lai_max": 6.0, "kc_mid": 1.20,
        "lai_growth_rate": 0.04, "lai_decay_rate": 0.02,
    },
    "cotton": {
        "t_base": 15.0, "t_opt": 30.0, "t_max": 38.0,
        "gdd_vegetative": 300, "gdd_flowering": 1000,
        "gdd_ripening": 1500, "gdd_senescence": 2000,
        "lai_max": 4.5, "kc_mid": 1.15,
        "lai_growth_rate": 0.035, "lai_decay_rate": 0.02,
    },
    "barley": {
        "t_base": 0.0, "t_opt": 20.0, "t_max": 30.0,
        "gdd_vegetative": 120, "gdd_flowering": 600,
        "gdd_ripening": 1000, "gdd_senescence": 1300,
        "lai_max": 4.5, "kc_mid": 1.10,
        "lai_growth_rate": 0.04, "lai_decay_rate": 0.025,
    },
    "potato": {
        "t_base": 5.0, "t_opt": 20.0, "t_max": 30.0,
        "gdd_vegetative": 150, "gdd_flowering": 600,
        "gdd_ripening": 1000, "gdd_senescence": 1400,
        "lai_max": 4.0, "kc_mid": 1.10,
        "lai_growth_rate": 0.04, "lai_decay_rate": 0.03,
    },
    "sorghum": {
        "t_base": 10.0, "t_opt": 32.0, "t_max": 42.0,
        "gdd_vegetative": 250, "gdd_flowering": 900,
        "gdd_ripening": 1400, "gdd_senescence": 1800,
        "lai_max": 5.0, "kc_mid": 1.10,
        "lai_growth_rate": 0.04, "lai_decay_rate": 0.02,
    },
    "alfalfa": {
        "t_base": 5.0, "t_opt": 25.0, "t_max": 35.0,
        "gdd_vegetative": 100, "gdd_flowering": 500,
        "gdd_ripening": 800, "gdd_senescence": 1200,
        "lai_max": 5.5, "kc_mid": 1.20,
        "lai_growth_rate": 0.05, "lai_decay_rate": 0.01,
    },
    "canola": {
        "t_base": 0.0, "t_opt": 20.0, "t_max": 30.0,
        "gdd_vegetative": 150, "gdd_flowering": 650,
        "gdd_ripening": 1050, "gdd_senescence": 1400,
        "lai_max": 4.5, "kc_mid": 1.10,
        "lai_growth_rate": 0.04, "lai_decay_rate": 0.025,
    },
    "sunflower": {
        "t_base": 6.0, "t_opt": 28.0, "t_max": 36.0,
        "gdd_vegetative": 200, "gdd_flowering": 800,
        "gdd_ripening": 1200, "gdd_senescence": 1600,
        "lai_max": 4.0, "kc_mid": 1.05,
        "lai_growth_rate": 0.04, "lai_decay_rate": 0.025,
    },
}

# Texture → water holding capacity (mm/m depth)
TEXTURE_WHC = {
    "sand": 80.0,
    "sandy_loam": 120.0,
    "loam": 150.0,
    "silt_loam": 180.0,
    "clay_loam": 170.0,
    "silty_clay": 160.0,
    "clay": 140.0,
}


# ============================================================================
# User Input Adapter
# ============================================================================

class UserInputAdapter:
    """Converts UserInputPackage → ObservationPackets + derived products.

    Every user input is normalized into the same ObservationPacket format
    used by satellite, weather, and sensor data — with proper QA metadata,
    uncertainty models, and provenance chains.
    """

    def __init__(self):
        self._packets: List[ObservationPacket] = []
        self._diagnostics: Dict[str, Any] = {}

    def ingest(self, package: UserInputPackage) -> "UserInputAdapterOutput":
        """Process a complete UserInputPackage.

        Returns a UserInputAdapterOutput with:
          - observation_packets: List[ObservationPacket]
          - soil_props: Dict for StateVector.initial()
          - crop_params: Dict overrides for ProcessModel
          - process_events: List[Dict] for ProcessModel.predict()
          - diagnostics: Dict
        """
        self._packets = []
        self._diagnostics = {"warnings": [], "packet_count": 0}

        reg = package.plot_registration

        # 1. Plot Registration → ObservationPacket
        self._ingest_registration(reg)

        # 2. Soil Analyses → ObservationPackets
        for sa in package.soil_analyses:
            self._ingest_soil_analysis(sa)

        # 3. Irrigation Events → ObservationPackets
        for ie in package.irrigation_events:
            self._ingest_irrigation_event(ie)

        # 4. Management Events → ObservationPackets
        for me in package.management_events:
            self._ingest_management_event(me)

        # Derive products
        soil_props = self._derive_soil_props(package.soil_analyses)
        crop_params = self._derive_crop_params(reg.crop_type, soil_props)
        process_events = self._derive_process_events(package)

        self._diagnostics["packet_count"] = len(self._packets)

        return UserInputAdapterOutput(
            observation_packets=list(self._packets),
            soil_props=soil_props,
            crop_params=crop_params,
            process_events=process_events,
            diagnostics=dict(self._diagnostics),
            plot_context_overrides=self._derive_plot_context(reg, package.soil_analyses),
        )

    # ------------------------------------------------------------------
    # Packet builders
    # ------------------------------------------------------------------

    def _ingest_registration(self, reg: PlotRegistration) -> None:
        """Plot registration → VECTOR packet."""
        ts = reg.registered_at or datetime.now(timezone.utc)

        packet = ObservationPacket(
            source=ObservationSource.USER_EVENT,
            obs_type=ObservationType.VECTOR,
            timestamp=ts,
            geometry_type="polygon",
            polygon_wkt=reg.polygon_wkt,
            payload={
                "event_type": "plot_registration",
                "crop_type": reg.crop_type,
                "variety": reg.variety,
                "planting_date": reg.planting_date,
                "expected_harvest_date": reg.expected_harvest_date,
                "irrigation_type": reg.irrigation_type,
                "area_ha": reg.area_ha,
                "management_goal": reg.management_goal,
                "constraints": reg.constraints,
            },
            qa=QAMetadata(
                flags=[QAFlag.CLEAN],
                scene_score=0.95,  # Near ground truth
            ),
            uncertainty=UncertaintyModel(
                sigmas={"area_ha": max(0.01, reg.area_ha * 0.02)},  # 2% area uncertainty
                error_model="gaussian",
            ),
            provenance=Provenance(
                processing_chain=["user_declared", "plot_registration"],
                software_version="agriwise-user-adapter-v1",
                license="user_owned",
            ),
            reliability_weight=0.95,
        )
        self._packets.append(packet)

    def _ingest_soil_analysis(self, sa: SoilAnalysis) -> None:
        """Soil analysis → TABULAR packet with per-variable sigma."""
        ts = datetime.fromisoformat(sa.sample_date) if sa.sample_date else datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Build payload from non-None values
        payload = {"event_type": "soil_analysis", "depth_cm": sa.depth_cm}
        sigmas = {}

        for var_name in ["clay_pct", "sand_pct", "silt_pct", "organic_matter_pct",
                         "ph", "ec_ds_m", "nitrogen_ppm", "phosphorus_ppm",
                         "potassium_ppm", "cec"]:
            val = getattr(sa, var_name, None)
            if val is not None:
                payload[var_name] = val
                sigmas[var_name] = sa.get_sigma(var_name)

        # Texture class derivation
        texture = sa.texture_class()
        if texture:
            payload["texture_class"] = texture

        # QA: completeness drives scene score
        completeness = sa.completeness_score()
        qa_score = 0.85 + 0.10 * completeness  # 0.85 – 0.95

        # Lab method affects confidence
        if sa.analysis_method == "field_kit":
            qa_score *= 0.8
            self._diagnostics["warnings"].append(
                f"Soil analysis from field kit — higher uncertainty applied"
            )

        packet = ObservationPacket(
            source=ObservationSource.USER_OBSERVATION,
            obs_type=ObservationType.TABULAR,
            timestamp=ts,
            payload=payload,
            qa=QAMetadata(
                flags=[QAFlag.CLEAN] if completeness > 0.5 else [QAFlag.LOW_CONFIDENCE],
                scene_score=qa_score,
            ),
            uncertainty=UncertaintyModel(
                sigmas=sigmas,
                error_model="gaussian",
            ),
            provenance=Provenance(
                processing_chain=["user_declared", "soil_lab_analysis"],
                software_version="agriwise-user-adapter-v1",
                license="user_owned",
            ),
            reliability_weight=min(0.95, qa_score),
        )
        self._packets.append(packet)

    def _ingest_irrigation_event(self, ie: IrrigationEvent) -> None:
        """Irrigation event → VECTOR packet."""
        ts = ie.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        packet = ObservationPacket(
            source=ObservationSource.USER_EVENT,
            obs_type=ObservationType.VECTOR,
            timestamp=ts,
            payload={
                "event_type": "irrigation",
                "amount_mm": ie.amount_mm,
                "method": ie.method,
                "duration_hours": ie.duration_hours,
                "zone_id": ie.zone_id,
            },
            qa=QAMetadata(
                flags=[QAFlag.CLEAN],
                scene_score=0.85,  # Self-reported → slightly lower
            ),
            uncertainty=UncertaintyModel(
                sigmas={"amount_mm": ie.sigma_mm},
                error_model="gaussian",
            ),
            provenance=Provenance(
                processing_chain=["user_declared", "irrigation_event"],
                software_version="agriwise-user-adapter-v1",
                license="user_owned",
            ),
            reliability_weight=0.85,
        )
        self._packets.append(packet)

    def _ingest_management_event(self, me: ManagementEvent) -> None:
        """Management event → VECTOR packet."""
        ts = me.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Validate
        warnings = me.validate()
        for w in warnings:
            self._diagnostics["warnings"].append(w)

        packet = ObservationPacket(
            source=ObservationSource.USER_EVENT,
            obs_type=ObservationType.VECTOR,
            timestamp=ts,
            payload={
                "event_type": me.event_type,
                "details": me.details,
                "notes": me.notes,
            },
            qa=QAMetadata(
                flags=[QAFlag.CLEAN] if not warnings else [QAFlag.LOW_CONFIDENCE],
                scene_score=0.90 if not warnings else 0.70,
            ),
            uncertainty=UncertaintyModel(
                sigmas={},
                error_model="gaussian",
            ),
            provenance=Provenance(
                processing_chain=["user_declared", f"management_{me.event_type}"],
                software_version="agriwise-user-adapter-v1",
                license="user_owned",
            ),
            reliability_weight=0.90,
        )
        self._packets.append(packet)

    # ------------------------------------------------------------------
    # Derived products
    # ------------------------------------------------------------------

    def _derive_soil_props(self, analyses: List[SoilAnalysis]) -> Dict[str, Any]:
        """Derive soil_props dict for StateVector.initial() from soil analyses."""
        if not analyses:
            return {}

        # Use the most recent analysis
        latest = analyses[-1]
        props: Dict[str, Any] = {}

        if latest.clay_pct is not None:
            props["clay_pct"] = latest.clay_pct
        if latest.sand_pct is not None:
            props["sand_pct"] = latest.sand_pct
        if latest.organic_matter_pct is not None:
            props["organic_matter_pct"] = latest.organic_matter_pct
        if latest.ph is not None:
            props["ph"] = latest.ph
        if latest.ec_ds_m is not None:
            props["ec_ds_m"] = latest.ec_ds_m

        # Derive WHC from texture
        texture = latest.texture_class()
        if texture:
            props["texture_class"] = texture
            props["whc_mm_per_m"] = TEXTURE_WHC.get(texture, 150.0)

        return props

    def _derive_crop_params(self, crop_type: str, soil_props: Dict) -> Dict[str, Any]:
        """Derive ProcessModel overrides from crop type + soil properties."""
        # Start from library defaults
        params = dict(CROP_PARAMS_LIBRARY.get(crop_type.lower(), {}))

        # Override WHC from soil analysis if available
        if "whc_mm_per_m" in soil_props:
            params["whc_mm_per_m"] = soil_props["whc_mm_per_m"]

        return params

    def _derive_process_events(self, package: UserInputPackage) -> List[Dict[str, Any]]:
        """Convert irrigation + management events into ProcessModel event format."""
        events = []

        for ie in package.irrigation_events:
            events.append({
                "event_type": "irrigation",
                "amount_mm": ie.amount_mm,
                "sigma_mm": ie.sigma_mm,
                "method": ie.method,
                "timestamp": ie.timestamp.isoformat() if ie.timestamp else None,
            })

        for me in package.management_events:
            events.append({
                "event_type": me.event_type,
                "details": me.details,
                "timestamp": me.timestamp.isoformat() if me.timestamp else None,
            })

        return events

    def _derive_plot_context(
        self, reg: PlotRegistration, analyses: List[SoilAnalysis]
    ) -> Dict[str, Any]:
        """Derive PlotContext overrides for Layer 3."""
        ctx: Dict[str, Any] = {
            "crop_type": reg.crop_type,
            "variety": reg.variety,
            "planting_date": reg.planting_date or "",
            "irrigation_type": reg.irrigation_type,
            "management_goal": reg.management_goal,
            "constraints": reg.constraints,
            "polygon_wkt": reg.polygon_wkt,
            "area_ha": reg.area_ha,
        }

        if analyses:
            latest = analyses[-1]
            ctx["soil_texture_class"] = latest.texture_class()
            if latest.clay_pct is not None:
                ctx["soil_clay_pct"] = latest.clay_pct
            if latest.organic_matter_pct is not None:
                ctx["soil_om_pct"] = latest.organic_matter_pct
            if latest.ph is not None:
                ctx["soil_ph"] = latest.ph
            if latest.ec_ds_m is not None:
                ctx["soil_ec_ds_m"] = latest.ec_ds_m

        return ctx

    def register_all(self, output: "UserInputAdapterOutput",
                     registry: ObservationRegistry) -> List[str]:
        """Register all output packets into an ObservationRegistry."""
        ids = []
        for pkt in output.observation_packets:
            pid = registry.register(pkt)
            ids.append(pid)
        return ids


# ============================================================================
# Adapter Output
# ============================================================================

@dataclass
class UserInputAdapterOutput:
    """Complete output of the UserInputAdapter."""
    observation_packets: List[ObservationPacket]
    soil_props: Dict[str, Any]
    crop_params: Dict[str, Any]
    process_events: List[Dict[str, Any]]
    plot_context_overrides: Dict[str, Any]
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        return {
            "packet_count": len(self.observation_packets),
            "soil_props_available": bool(self.soil_props),
            "crop_params_available": bool(self.crop_params),
            "process_events_count": len(self.process_events),
            "warnings": self.diagnostics.get("warnings", []),
        }
