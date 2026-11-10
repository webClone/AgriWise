"""
Layer0SourcePackage Adapter.

Transforms the unified Layer0SourcePackage envelope and its contained packets into Layer 1 EvidenceItems.
"""

from __future__ import annotations

from typing import Any, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope
from layer1_fusion.adapters.observation_packet import observation_packet_to_evidence
from layer0.source_package import Layer0SourcePackage
from layer0.observation_packet import DataStatus
from layer1_fusion.source_family import normalize_source_family


def is_layer0_source_package(package: Any) -> bool:
    """Recognize canonical Layer 0 envelopes across contract revisions/import roots."""
    version = str(getattr(package, "contract_version", "") or "")
    return isinstance(package, Layer0SourcePackage) or version.startswith(
        "layer0-source-package-v"
    )


class Layer0SourcePackageAdapter:
    """Adapter to extract evidence from a canonical Layer0SourcePackage wrapper."""

    def can_read(self, package: Any) -> bool:
        return package is not None and is_layer0_source_package(package)

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        # L1-R7-06 / R7-G07: Validate canonical package plot identity against context bundle
        pkg_plot = getattr(package, "plot_id", None)
        if pkg_plot and context.plot_id and pkg_plot != context.plot_id:
            # Foreign package must not have its packets rebound to context plot!
            # Exclude package before packet extraction.
            return []

        canonical_package_family = normalize_source_family(getattr(package, "source_family", "environment"))

        # Transform packets to EvidenceItems using the observation packet bridge
        for pkt in getattr(package, "packets", []):
            pkt_items = observation_packet_to_evidence(
                packet=pkt,
                bundle=context,
                source_package=package,
                fallback_source_family=canonical_package_family,
            )
            if not getattr(package, "is_available", True):
                for item in pkt_items:
                    item.diagnostic_only = True
                    item.state_update_allowed = False
                    item.confidence = min(item.confidence, 0.05)
                    item.data_status = "unavailable"
            items.extend(pkt_items)

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="layer0_missing",
                source_family="geo_context",
                source_name="Canonical Layer 0 Envelope",
                package_id="",
                package_version="",
                source_status="missing",
            )

        source_family = normalize_source_family(getattr(package, "source_family", "environment"))
        package_id = getattr(package, "package_id", "")
        package_hash = getattr(package, "package_hash", "")
        is_available = getattr(package, "is_available", True)
        data_status = getattr(package, "data_status", DataStatus.OBSERVED)

        # Map overall status
        status = "ok"
        if not is_available or data_status == DataStatus.UNAVAILABLE:
            status = "missing"
        elif data_status == DataStatus.FALLBACK:
            status = "stale"
        elif data_status == DataStatus.ESTIMATED:
            status = "degraded"

        time_window = getattr(package, "time_window", {})
        import datetime
        
        def parse_dt(s: str) -> datetime.datetime | None:
            if not s:
                return None
            try:
                return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
                return None

        obs_start = parse_dt(time_window.get("start") or time_window.get("acquisition") or "")
        obs_end = parse_dt(time_window.get("end") or time_window.get("acquisition") or "")

        return SourceEnvelope(
            source_id=f"{source_family}_{package_id[:8]}" if package_id else f"{source_family}_unknown",
            source_family=source_family,
            source_name=f"Layer 0 Source: {source_family.upper()}",
            package_id=package_id,
            package_version=getattr(package, "contract_version", "layer0-source-package-v1"),
            input_hash=package_hash,
            produced_at=datetime.datetime.now(datetime.timezone.utc),
            observed_start=obs_start,
            observed_end=obs_end,
            spatial_scope="plot",
            temporal_scope="daily",
            trust_score=0.8 if status == "ok" else (0.4 if status == "degraded" else 0.0),
            source_status=status,
            provenance=getattr(package, "provenance", {}),
            diagnostics=getattr(package, "diagnostics", {}),
        )
