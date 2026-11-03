"""
Layer 0 Source Package — Canonical output envelope for all Layer 0 engines.

Every source (S2, S1, Environment, GeoContext, Sensors, Perception, User)
returns a source-specific subclass or instance of Layer0SourcePackage.

Layer0StatePackage aggregates all source packages into a single object
consumed by Layer 1.

Contract version is embedded so downstream consumers can detect
schema changes across releases.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .observation_packet import DataStatus, ObservationPacket


def _canonical_process_forcing(value: Any) -> Any:
    """Canonicalize material forcing values for deterministic package identity.

    Dicts, sequences, dataclasses and temporal values cover both weather
    ProcessForcing and sensor IrrigationProcessForcing. Unknown object types
    fail closed rather than degrading to potentially unstable repr()/str().
    This establishes *content identity*, not observation admission,
    measurement authority, or a signed publication receipt.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite process-forcing value cannot be hashed")
        return value
    if isinstance(value, Enum):
        return _canonical_process_forcing(value.value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "__dataclass_type__": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                f.name: _canonical_process_forcing(getattr(value, f.name))
                for f in fields(value)
            },
        }
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("process-forcing mapping keys must be strings")
        return {
            key: _canonical_process_forcing(item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_process_forcing(item) for item in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _canonical_process_forcing(value.to_dict())
    raise TypeError(f"unsupported process-forcing identity type: {type(value).__name__}")


def _process_forcing_identity(records: List[Any]) -> str:
    # Array order matters for process forcing; the input is a time sequence.
    if not isinstance(records, (list, tuple)):
        raise TypeError("process forcing must be an ordered sequence")
    return json.dumps(
        {
            "domain": "akaloris/layer0/process-forcing-content/v1",
            "records": _canonical_process_forcing(records),
        },
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    )


# ============================================================================
# Source Package — one per source engine invocation
# ============================================================================

@dataclass
class Layer0SourcePackage:
    """Canonical output from a single Layer 0 source engine.

    Every Layer 0 engine (Sentinel-2, Sentinel-1, Environment, GeoContext,
    Sensors, Perception, User) must return an instance of this package,
    even when the source is unavailable or failed.

    Unavailable sources return:
        data_status = DataStatus.UNAVAILABLE
        packets = []
        is_available = False
        diagnostics = {"reason": "NOT_IMPLEMENTED" | "PROVIDER_ERROR" | ...}
    """

    # Contract identity
    contract_version: str = "layer0-source-package-v2"
    package_id: str = ""
    package_hash: str = ""

    # Source identity
    source_family: str = ""       # "sentinel2", "sentinel1", "environment", etc.
    plot_id: str = ""
    geometry_hash: str = ""
    geometry_version: Optional[int] = None
    time_window: Dict[str, str] = field(default_factory=dict)

    # Data status
    data_status: DataStatus = DataStatus.OBSERVED
    is_available: bool = True

    # Canonical outputs
    packets: List[ObservationPacket] = field(default_factory=list)
    kalman_observations: List[Any] = field(default_factory=list)
    process_forcing: List[Any] = field(default_factory=list)
    # Canonical, evidence-addressed records that downstream scientific layers
    # may consume without depending on a source engine's native dataclasses.
    # These records are part of package identity.
    evidence_records: List[Dict[str, Any]] = field(default_factory=list)

    # Diagnostics, errors, warnings
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)

    # Provenance and health
    provenance: Dict[str, Any] = field(default_factory=dict)
    health: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Derive is_available from data_status
        if self.data_status == DataStatus.UNAVAILABLE:
            self.is_available = False
        # Generate package_id if not provided
        if not self.package_id:
            self.package_id = self._generate_package_id()
        # Generate package_hash if not provided
        if not self.package_hash:
            self.package_hash = self._generate_package_hash()

    def _generate_package_id(self) -> str:
        """Deterministic package identity from source + plot + time window."""
        key = (
            f"{self.source_family}:{self.plot_id}:"
            f"{self.time_window.get('start', '')}:"
            f"{self.time_window.get('end', '')}"
        )
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _generate_package_hash(self) -> str:
        """Content-sensitive hash of the package outputs.
        
        Includes packet content hashes, kalman observation content,
        process forcing, errors, warnings, provenance, and health.
        """
        # Packet content hashes (the actual observation content)
        packet_hashes = sorted(p.content_hash for p in self.packets)
        
        # Stable hash of kalman observations
        kalman_strs = []
        for k in self.kalman_observations:
            if hasattr(k, 'obs_type') and hasattr(k, 'value'):
                kalman_strs.append(f"{k.obs_type}:{k.value}:{getattr(k, 'sigma', '')}")
            else:
                kalman_strs.append(str(k))
        
        parts = [
            self.source_family,
            self.plot_id,
            self.geometry_hash,
            str(self.geometry_version),
            self.data_status.value,
            # Packet content (not just count)
            "|".join(packet_hashes),
            # Kalman content
            "|".join(sorted(kalman_strs)),
            # Full typed forcing content; count-only hashing had collisions
            # (e.g. 1mm versus 9mm). Hash the ordered records fail-closed.
            _process_forcing_identity(self.process_forcing),
            json.dumps(self.evidence_records, sort_keys=True, default=str),
            # Errors and warnings
            json.dumps(self.errors, sort_keys=True, default=str),
            json.dumps(self.warnings, sort_keys=True, default=str),
            # Provenance and health
            json.dumps(self.provenance, sort_keys=True, default=str),
            json.dumps(self.health, sort_keys=True, default=str),
            # Diagnostics
            json.dumps(self.diagnostics, sort_keys=True, default=str),
        ]
        raw = "|".join(parts).encode()
        return hashlib.sha256(raw).hexdigest()[:20]

    @classmethod
    def unavailable(
        cls,
        source_family: str,
        plot_id: str = "",
        reason: str = "NOT_IMPLEMENTED",
        **kwargs,
    ) -> "Layer0SourcePackage":
        """Factory for unavailable/failed source packages.

        Usage:
            pkg = Layer0SourcePackage.unavailable("sentinel5p", reason="NOT_IMPLEMENTED")
        """
        return cls(
            source_family=source_family,
            plot_id=plot_id,
            data_status=DataStatus.UNAVAILABLE,
            is_available=False,
            packets=[],
            diagnostics={"reason": reason},
            health={"available": False},
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "package_id": self.package_id,
            "package_hash": self.package_hash,
            "source_family": self.source_family,
            "plot_id": self.plot_id,
            "geometry_hash": self.geometry_hash,
            "geometry_version": self.geometry_version,
            "time_window": self.time_window,
            "data_status": self.data_status.value,
            "is_available": self.is_available,
            "packet_count": len(self.packets),
            "kalman_observation_count": len(self.kalman_observations),
            "process_forcing_count": len(self.process_forcing),
            "evidence_records": self.evidence_records,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "diagnostics": self.diagnostics,
            "provenance": self.provenance,
            "health": self.health,
        }


# ============================================================================
# State Package — aggregated Layer 0 output for Layer 1
# ============================================================================

@dataclass
class Layer0StatePackage:
    """Aggregated output from the Layer 0 runner — consumed by Layer 1.

    Contains all source packages, the merged observation registry,
    daily state estimation output, and cross-source validation results.
    """

    # Contract identity
    contract_version: str = "layer0-state-package-v1"
    run_id: str = ""
    input_hash: str = ""
    output_hash: str = ""

    # Plot identity
    plot_id: str = ""
    geometry_hash: str = ""
    geometry_version: Optional[int] = None

    # Source packages (keyed by source_family)
    source_packages: Dict[str, Layer0SourcePackage] = field(default_factory=dict)

    # Flattened packet list (all packets from all sources)
    all_packets: List[ObservationPacket] = field(default_factory=list)

    # Observation registry summary
    observation_registry_summary: Dict[str, Any] = field(default_factory=dict)

    # Daily state estimation outputs (from Kalman engine)
    daily_state: Dict[str, Any] = field(default_factory=dict)
    state_uncertainty: Dict[str, Any] = field(default_factory=dict)

    # Cross-source validation
    validation_conflicts: List[Any] = field(default_factory=list)

    # Health and provenance
    health_report: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.output_hash:
            self.output_hash = self._generate_output_hash()

    def _generate_output_hash(self) -> str:
        """Content-sensitive hash including source package hashes and packet content."""
        # Helper for stable serialization
        def _stable_json(val: Any) -> str:
            def _convert(v: Any) -> Any:
                if isinstance(v, dict):
                    return {k: _convert(v2) for k, v2 in sorted(v.items())}
                elif isinstance(v, (list, tuple)):
                    return [_convert(x) for x in v]
                elif isinstance(v, float):
                    return format(v, ".12g")
                elif hasattr(v, "to_dict"):
                    return _convert(v.to_dict())
                elif hasattr(v, "__dict__"):
                    return _convert(v.__dict__)
                else:
                    return str(v) if not isinstance(v, (str, int, bool, type(None))) else v
            return json.dumps(_convert(val), sort_keys=True)

        # Include source package hashes (which include packet content hashes)
        pkg_hashes = sorted(
            f"{k}:{v.package_hash}" for k, v in self.source_packages.items()
        )
        # Include packet content hashes
        pkt_hashes = sorted(p.content_hash for p in self.all_packets)
        
        parts = [
            self.run_id,
            self.plot_id,
            self.geometry_hash,
            str(self.geometry_version),
            "|".join(pkg_hashes),
            "|".join(pkt_hashes),
            _stable_json(self.daily_state),
            _stable_json(self.state_uncertainty),
            _stable_json(self.health_report),
            _stable_json(self.provenance),
            _stable_json(self.observation_registry_summary),
            _stable_json(self.validation_conflicts),
        ]
        raw = "|".join(parts).encode()
        return hashlib.sha256(raw).hexdigest()[:20]

    @property
    def available_sources(self) -> List[str]:
        """Source families that produced data."""
        return [
            k for k, v in self.source_packages.items()
            if v.is_available
        ]

    @property
    def unavailable_sources(self) -> List[str]:
        """Source families that are unavailable or failed."""
        return [
            k for k, v in self.source_packages.items()
            if not v.is_available
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "run_id": self.run_id,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "plot_id": self.plot_id,
            "geometry_hash": self.geometry_hash,
            "geometry_version": self.geometry_version,
            "available_sources": self.available_sources,
            "unavailable_sources": self.unavailable_sources,
            "source_package_count": len(self.source_packages),
            "all_packet_count": len(self.all_packets),
            "daily_state_zones": list(self.daily_state.keys()),
            "validation_conflict_count": len(self.validation_conflicts),
            "health_report": self.health_report,
            "provenance": self.provenance,
        }
