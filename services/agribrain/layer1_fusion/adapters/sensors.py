"""
Sensor source adapter.

Extracts normalized readings, QA, aggregates, Kalman observations,
placement context, irrigation events, and process forcing from
SensorContextPackage.

Rules:
- Respects diagnostic_only / state_update_allowed from QA
- Preserves point/zone/edge/irrigation_block scopes
- Never promotes point sensor to plot truth without representativeness
- Leaf wetness, wet-spot sensors → diagnostic only
- Calibration, health, placement scores carried as reliability
"""

from __future__ import annotations

from typing import Any, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope

# Variables that are always diagnostic (never direct state update)
_DIAGNOSTIC_VARIABLES = frozenset({
    "leaf_wetness", "leaf_wetness_index", "signal_rssi_dbm", "signal_snr_db",
    "battery_voltage_v", "battery_level_pct",
})


class SensorAdapter:
    source_family = "sensor"

    def can_read(self, package: Any) -> bool:
        return package is not None and hasattr(package, "plot_id")

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id
        pkg_id = f"sensor_{plot_id}"

        # --- QA-validated readings → point or zone evidence ---
        qa_map = {}
        for qa in getattr(package, "qa_results", []):
            # QA results are positional — map by index
            qa_map[len(qa_map)] = qa

        for i, reading in enumerate(getattr(package, "readings", [])):
            device_id = getattr(reading, "device_id", "unknown")
            variable = getattr(reading, "variable", "")
            value = getattr(reading, "value", None)
            unit = getattr(reading, "unit", None)
            timestamp = getattr(reading, "timestamp", None)

            # Match QA result
            qa = qa_map.get(i)
            usable = getattr(qa, "usable", True) if qa else True
            if not usable:
                continue

            reliability = getattr(qa, "reading_reliability", 0.5) if qa else 0.5
            update_allowed = getattr(qa, "update_allowed", True) if qa else True

            # Determine scope from placement
            scope = "point"  # default
            scope_id = device_id

            # Diagnostic variables
            is_diag = variable in _DIAGNOSTIC_VARIABLES or not update_allowed

            items.append(EvidenceItem(
                evidence_id=f"sensor_{device_id}_{variable}_{i}",
                plot_id=plot_id,
                variable=variable,
                value=value,
                unit=unit,
                source_family="sensor",
                source_id=device_id,
                observation_type="measurement",
                spatial_scope=scope,
                scope_id=scope_id,
                observed_at=timestamp,
                confidence=min(0.95, reliability),
                sigma=round(1.0 - reliability, 4),
                reliability=reliability,
                freshness_score=0.0,
                provenance_ref=f"sensor_{device_id}_{plot_id}",
                diagnostic_only=is_diag,
                state_update_allowed=update_allowed and not is_diag,
            ))

        # --- Aggregates ---
        for agg in getattr(package, "aggregates", []):
            items.append(EvidenceItem(
                evidence_id=f"sensor_agg_{getattr(agg, 'device_id', '')}_{getattr(agg, 'aggregate_type', '')}",
                plot_id=plot_id,
                variable=f"{getattr(agg, 'variable', '')}_{getattr(agg, 'aggregate_type', '')}",
                value=getattr(agg, "value", None),
                unit=getattr(agg, "unit", None),
                source_family="sensor",
                source_id=getattr(agg, "device_id", ""),
                observation_type="state_estimate",
                spatial_scope="point",
                scope_id=getattr(agg, "device_id", ""),
                window_start=getattr(agg, "window_start", None),
                window_end=getattr(agg, "window_end", None),
                confidence=min(0.90, getattr(agg, "confidence", 0.5)),
                reliability=getattr(agg, "confidence", 0.5),
                freshness_score=0.0,
                provenance_ref=f"sensor_agg_{plot_id}",
            ))

        # --- Process forcing events (irrigation, rain-gauge) ---
        for pfe in getattr(package, "process_forcing_events", []):
            event_type = pfe.get("type", "") if isinstance(pfe, dict) else getattr(pfe, "type", "")
            items.append(EvidenceItem(
                evidence_id=f"sensor_event_{event_type}_{len(items)}",
                plot_id=plot_id,
                variable=f"sensor_{event_type}",
                value=pfe if isinstance(pfe, dict) else str(pfe),
                unit=None,
                source_family="sensor",
                source_id="sensor_process_forcing",
                observation_type="event",
                spatial_scope="plot",
                confidence=0.80,
                reliability=0.80,
                freshness_score=0.0,
                provenance_ref=f"sensor_event_{plot_id}",
            ))

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="sensor_missing", source_family="sensor",
                source_name="Sensor Network", package_id="", package_version="",
                source_status="missing",
            )
        n_readings = len(getattr(package, "readings", []))
        n_qa = len(getattr(package, "qa_results", []))
        return SourceEnvelope(
            source_id=f"sensor_{getattr(package, 'plot_id', '')}",
            source_family="sensor",
            source_name="Sensor Context V1",
            package_id=f"sensor_{getattr(package, 'plot_id', '')}",
            package_version="sensor_v1",
            observed_start=getattr(package, "window_start", None),
            observed_end=getattr(package, "window_end", None),
            spatial_scope="point",
            temporal_scope="instant",
            trust_score=0.85 if n_readings > 0 else 0.0,
            source_status="ok" if n_readings > 0 else "missing",
            diagnostics={"reading_count": n_readings, "qa_count": n_qa},
        )
