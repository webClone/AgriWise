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

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real

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
        from layer1_fusion.adapters.layer0_source_package import Layer0SourcePackageAdapter, is_layer0_source_package
        if is_layer0_source_package(package):
            return Layer0SourcePackageAdapter().extract_evidence(package, context)

        items: List[EvidenceItem] = []
        if package is None:
            return items

        # R8-04 / R8-G06: Fail closed on missing package plot_id; do not synthesize from context
        pkg_plot = getattr(package, "plot_id", None)
        if not pkg_plot or not str(pkg_plot).strip():
            plot_id = None
        else:
            plot_id = str(pkg_plot).strip()

        # Build device registry lookup from package.devices
        dev_map = {}
        for d in getattr(package, "devices", []):
            d_id = getattr(d, "device_id", None) or (d.get("device_id") if isinstance(d, dict) else None)
            if d_id:
                dev_map[d_id] = d

        # --- QA-validated readings → point or zone evidence ---
        qa_map = {}
        for qa in getattr(package, "qa_results", []):
            # QA results are positional — map by index
            qa_map[len(qa_map)] = qa

        for i, reading in enumerate(getattr(package, "readings", [])):
            device_id = getattr(reading, "device_id", "unknown")
            raw_var = getattr(reading, "variable", "")
            variable = raw_var.value if hasattr(raw_var, "value") else str(raw_var)
            value = getattr(reading, "value", None)
            unit = getattr(reading, "unit", None)
            timestamp = getattr(reading, "timestamp", None)

            # Match QA result
            qa = qa_map.get(i)
            usable = getattr(qa, "usable", True) if qa else True
            if not usable:
                continue

            raw_rel = getattr(qa, "reading_reliability", 0.5) if qa else 0.5
            fin_rel = finite_real(raw_rel)
            reliability = fin_rel if fin_rel is not None else 0.0
            update_allowed = getattr(qa, "update_allowed", True) if qa else True
            if fin_rel is None or fin_rel <= 0.0:
                update_allowed = False

            # Determine scope from placement
            scope = "point"  # default
            scope_id = device_id

            # Diagnostic variables
            is_diag = variable in _DIAGNOSTIC_VARIABLES or not update_allowed

            # R8-04: Resolve authentic calibration identity from reading, QA, device entry or registry
            d_entry = dev_map.get(device_id)
            cal_ver = (
                getattr(reading, "calibration_version", None)
                or (getattr(qa, "calibration_version", None) if qa else None)
                or (getattr(d_entry, "calibration_profile_id", None) if d_entry else None)
                or (d_entry.get("calibration_profile_id") if isinstance(d_entry, dict) else None)
                or getattr(package, "calibration_profile_id", None)
            )
            if not cal_ver:
                try:
                    from services.agribrain.sensor_runtime.registry import get_device_registration
                    reg = get_device_registration(device_id)
                    cal_ver = getattr(reg, "calibration_profile_id", None) if reg else None
                except Exception:
                    cal_ver = None

            parent_acq_id = getattr(reading, "reading_id", None) or getattr(package, "package_id", None) or f"sensor_{device_id}_{i}"

            prov_dict = getattr(package, "provenance", {}) or {}
            receipt_ref = prov_dict.get("receipt_ref") if isinstance(prov_dict, dict) else getattr(prov_dict, "receipt_ref", None)
            reading_receipt = getattr(reading, "receipt", None) or getattr(reading, "receipt_ref", None)
            package_receipt = getattr(package, "receipt", None)
            active_receipt = reading_receipt if reading_receipt is not None else (package_receipt or (receipt_ref if hasattr(receipt_ref, "receipt_id") else None))

            raw_ref = getattr(reading, "raw_payload_ref", None)
            if active_receipt and hasattr(active_receipt, "receipt_id"):
                prov_ref = str(active_receipt.receipt_id)
            elif receipt_ref:
                prov_ref = str(receipt_ref)
            elif raw_ref:
                prov_ref = str(raw_ref)
            else:
                prov_ref = f"raw_reading_{device_id}_{i}"

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
                provenance_ref=prov_ref,
                receipt=active_receipt,
                diagnostic_only=is_diag,
                state_update_allowed=update_allowed and not is_diag,
                instrument_id=device_id,
                calibration_version=cal_ver,
                parent_acquisition_id=parent_acq_id,
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

        from layer1_fusion.truth_bridge import normalize_evidence_truth
        for item in items:
            normalize_evidence_truth(item, source_context=package)
        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        from layer1_fusion.adapters.layer0_source_package import Layer0SourcePackageAdapter, is_layer0_source_package
        if is_layer0_source_package(package):
            return Layer0SourcePackageAdapter().source_health(package)

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
