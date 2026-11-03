"""
Layer 0 Pipeline Orchestrator — Unified run lifecycle for Layer 0.

Coordinates the wrapping of all source engine packages and executes the
Layer0StateEngine daily state assimilation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.agribrain.layer0.source_package import Layer0SourcePackage, Layer0StatePackage
from services.agribrain.layer0.observation_packet import DataStatus, ObservationPacket
from services.agribrain.layer0.wrappers import (
    wrap_sentinel2,
    wrap_sentinel1,
    wrap_environment,
    wrap_sensors,
    wrap_geo_context,
    wrap_perception,
)
from services.agribrain.layer0.state_engine import Layer0StateEngine
from services.agribrain.layer0.positive_observation_admission import (
    PositiveObservationAdmissionVerifier, observation_packet_digest,
)


@dataclass
class Layer0RunnerInput:
    """The structured input contract for Layer0Runner."""
    plot_id: str
    geometry_hash: str = ""
    geometry_version: Optional[int] = None
    start_date: str = ""
    end_date: str = ""
    soil_props: Optional[Dict[str, Any]] = None
    zone_ids: List[str] = field(default_factory=list)

    sentinel2_packages: List[Any] = field(default_factory=list)
    sentinel1_packages: List[Any] = field(default_factory=list)
    environment_package: Optional[Any] = None
    sensor_package: Optional[Any] = None
    geo_context_packets: List[Any] = field(default_factory=list)
    perception_packets: List[Any] = field(default_factory=list)
    # Detached receipts are untrusted data until the runtime's protected
    # verifier validates the HMAC against its own server-side issuer keys.
    positive_admission_receipts: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class Layer0RunnerOutput:
    """The unified return contract of Layer0Runner."""
    plot_id: str
    geometry_hash: str
    geometry_version: Optional[int]

    layer0_source_packages: Dict[str, List[Layer0SourcePackage]]
    layer0_state_package: Optional[Layer0StatePackage]

    all_packets: List[ObservationPacket] = field(default_factory=list)
    health_report: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_layer1_bundle_kwargs(self) -> dict:
        """Helper to directly supply bundle kwargs for Layer1InputBundle."""
        return {
            "layer0_source_packages": self.layer0_source_packages,
            "layer0_state_package": self.layer0_state_package,
        }


class Layer0Runner:
    """Orchestrates all Layer 0 engines and wrappers, producing canonical outputs.

    Accepts mock/real native engine packages, normalizes and wraps them into
    canonical envelopes, drives the state engine, and generates detailed
    system-wide health audits.
    """

    EXPECTED_CORE_SOURCES = [
        "sentinel2",
        "sentinel1",
        "environment",
        "sensor",
        "geo_context",
        "perception",
    ]

    def __init__(
        self,
        positive_admission_verifier: Optional[PositiveObservationAdmissionVerifier] = None,
    ):
        # This must be provisioned from trusted server-side configuration.
        # A missing verifier means LEGACY_UNVERIFIED, never signed authority.
        self.state_engine = Layer0StateEngine(
            positive_admission_verifier=positive_admission_verifier
        )

    def run(
        self,
        run_input: Layer0RunnerInput,
        run_timestamp: Optional[datetime] = None,
    ) -> Layer0RunnerOutput:
        """Orchestrate wrappers, generate unavailable placeholders, and run state engine.

        Args:
            run_input: The structured Layer0RunnerInput holding inputs.
            run_timestamp: Injected timestamp for replay or test consistency.

        Returns:
            Layer0RunnerOutput holding all source packages, state, packets, and audits.
        """
        plot_id = run_input.plot_id
        geometry_hash = run_input.geometry_hash
        geometry_version = run_input.geometry_version
        start_date = run_input.start_date
        end_date = run_input.end_date

        source_packages: Dict[str, List[Layer0SourcePackage]] = {}

        # 1. Wrap Sentinel-2
        if run_input.sentinel2_packages:
            source_packages["sentinel2"] = [
                wrap_sentinel2(
                    pkg,
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    geometry_version=geometry_version,
                )
                for pkg in run_input.sentinel2_packages
            ]

        # 2. Wrap Sentinel-1
        if run_input.sentinel1_packages:
            source_packages["sentinel1"] = [
                wrap_sentinel1(
                    pkg,
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    geometry_version=geometry_version,
                )
                for pkg in run_input.sentinel1_packages
            ]

        # 3. Wrap Sensors
        if run_input.sensor_package is not None:
            source_packages["sensor"] = [
                wrap_sensors(
                    run_input.sensor_package,
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    geometry_version=geometry_version,
                )
            ]

        # 4. Wrap Environment
        if run_input.environment_package is not None:
            source_packages["environment"] = [
                wrap_environment(
                    run_input.environment_package,
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    geometry_version=geometry_version,
                )
            ]

        # 5. Wrap Geo Context
        if run_input.geo_context_packets:
            source_packages["geo_context"] = [
                wrap_geo_context(
                    run_input.geo_context_packets,
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    geometry_version=geometry_version,
                )
            ]

        # 6. Wrap Perception
        if run_input.perception_packets:
            source_packages["perception"] = [
                wrap_perception(
                    run_input.perception_packets,
                    plot_id=plot_id,
                    geometry_hash=geometry_hash,
                    geometry_version=geometry_version,
                )
            ]

        # 7. Generate structured unavailable placeholders for missing core expected sources
        time_window = {
            "start": start_date + "T00:00:00+00:00" if start_date else "",
            "end": end_date + "T23:59:59+00:00" if end_date else "",
        }
        for source in self.EXPECTED_CORE_SOURCES:
            if source not in source_packages:
                source_packages[source] = [
                    Layer0SourcePackage(
                        source_family=source,
                        plot_id=plot_id,
                        geometry_hash=geometry_hash,
                        geometry_version=geometry_version,
                        time_window=time_window,
                        data_status=DataStatus.UNAVAILABLE,
                        is_available=False,
                        diagnostics={"reason": "MISSING_NATIVE_PACKAGE"},
                    )
                ]

        # 8. Collect packets from all packages (both available and unavailable)
        all_packets = [
            pkt
            for pkgs in source_packages.values()
            for pkg in pkgs
            for pkt in pkg.packets
        ]

        # 9. Clean state packets for the Daily State Engine (exclude unavailable/simulated)
        state_packets = [
            p for p in all_packets
            if p.data_status in {
                DataStatus.OBSERVED,
                DataStatus.ESTIMATED,
                DataStatus.INTERPOLATED,
                DataStatus.ASSIMILATED,
            }
        ]

        # 10. Run State Assimilation
        state_package: Optional[Layer0StatePackage] = None
        if state_packets:
            state_package = self.state_engine.run_from_packets(
                plot_id=plot_id,
                packets=state_packets,
                start_date=start_date,
                end_date=end_date,
                soil_props=run_input.soil_props,
                zone_ids=run_input.zone_ids,
                run_timestamp=run_timestamp,
                geometry_hash=geometry_hash,
                geometry_version=geometry_version,
                positive_admission_receipts=run_input.positive_admission_receipts,
            )

        # 11. Build aggregated health report, diagnostics and provenance summaries
        status_counts = {
            "observed": 0,
            "estimated": 0,
            "interpolated": 0,
            "assimilated": 0,
            "fallback": 0,
            "simulated": 0,
            "unavailable": 0,
        }
        for pkt in all_packets:
            st = pkt.data_status.value if hasattr(pkt.data_status, "value") else str(pkt.data_status)
            status_counts[st] = status_counts.get(st, 0) + 1

        eligible_ids = {id(pkt) for pkt in state_packets}
        rejected_by_reason = {}
        for pkt in all_packets:
            if id(pkt) in eligible_ids:
                continue
            st = pkt.data_status.value if hasattr(pkt.data_status, "value") else str(pkt.data_status)
            rejected_by_reason[st] = rejected_by_reason.get(st, 0) + 1

        mode = (
            (state_package.health_report or {}).get(
                "positive_source_admission_mode", "LEGACY_UNVERIFIED"
            )
            if state_package else "NO_STATE_ESTIMATE"
        )
        signed_admitted = set(
            (state_package.health_report or {}).get(
                "positive_admitted_observation_digests", []
            )
            if state_package else []
        )

        sources_report = {}
        for sf, pkgs in source_packages.items():
            transport_received = any(bool(package.packets) for package in pkgs)
            quality_admitted = any(
                bool((package.health or {}).get("quality_admitted", (package.health or {}).get("usable", False)))
                for package in pkgs
            )
            state_eligible = any(
                id(packet) in eligible_ids
                for package in pkgs for packet in package.packets
            )
            authority_verified = False
            if mode == "SIGNED_SCOPE_BOUND":
                # Only count proof-bound, actually admitted observations.
                state_eligible = False
                for package in pkgs:
                    for packet in package.packets:
                        try:
                            if observation_packet_digest(packet) in signed_admitted:
                                state_eligible = True
                                authority_verified = True
                                break
                        except (ValueError, TypeError, AttributeError, OverflowError):
                            continue
                    if state_eligible:
                        break
            scientifically_healthy = quality_admitted and state_eligible
            sources_report[sf] = {
                "status": (
                    "healthy" if scientifically_healthy
                    else "degraded" if transport_received
                    else "unavailable"
                ),
                "transport_received": transport_received,
                "quality_admitted": quality_admitted,
                "state_eligible": state_eligible,
                "positive_source_authority_verified": authority_verified,
                "scientifically_healthy": scientifically_healthy,
                "packet_count": sum(len(p.packets) for p in pkgs),
            }

        health_report = {
            "sources": sources_report,
            "packet_status_counts": status_counts,
            "state_eligibility": {
                "all_packet_count": len(all_packets),
                "eligible_packet_count": len(state_packets),
                "rejected_packet_count": max(len(all_packets) - len(state_packets), 0),
                "rejected_by_reason": rejected_by_reason,
            },
            "state_package_generated": state_package is not None,
            "kalman_available": state_package is not None and state_package.health_report.get("kalman_available", False),
            "positive_source_admission_mode": mode,
        }

        diagnostics = {
            "overall_status": "ok" if all(s["status"] == "healthy" for s in sources_report.values()) else "degraded",
            "state_engine_alerts": state_package.health_report.get("audit", {}).get("trust_report", {}).get("alerts", []) if state_package else [],
        }

        provenance = {
            "runner": "Layer0Runner",
            "run_timestamp": (run_timestamp or datetime.now(timezone.utc)).isoformat(),
            "sources_run": list(source_packages.keys()),
        }

        return Layer0RunnerOutput(
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            geometry_version=geometry_version,
            layer0_source_packages=source_packages,
            layer0_state_package=state_package,
            all_packets=all_packets,
            health_report=health_report,
            diagnostics=diagnostics,
            provenance=provenance,
            metadata={},
        )
