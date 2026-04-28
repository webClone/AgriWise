"""
Layer 1 Fusion Context Engine V1.

18-step deterministic pipeline:
  1. Validate input bundle
  2. Build source envelopes
  3. Run adapters → EvidenceItems
  4. Validate units/scopes/provenance
  5. Quarantine invalid evidence
  6. Build EvidenceLedger
  7. Run temporal alignment
  8. Run spatial alignment
  9. Compute freshness
  10. Run conflict resolver
  11. Run gap analyzer
  12. Run fusion rules
  13. Apply confidence model
  14. Build fused feature groups
  15. Build Layer2 input payload (real adapter)
  16. Build Layer10 spatial payload (real adapter)
  17. Build diagnostics/provenance (computed prohibitions)
  18. Return Layer1ContextPackage (with evidence_items)

Layer 1 never performs live data acquisition.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .schemas import (
    EvidenceGap,
    EvidenceItem,
    FusedFeatureSet,
    Layer1ContextPackage,
    Layer1InputBundle,
    Layer1Provenance,
    Layer1StateSummary,
    QuarantinedEvidence,
    SourceEnvelope,
    SourceHealthReport,
    DataHealthScore,
    TimeWindow,
)
from .source_registry import SourceRegistry
from .adapters.sentinel2 import Sentinel2Adapter
from .adapters.sentinel1 import Sentinel1Adapter
from .adapters.environment import EnvironmentAdapter
from .adapters.weather_forecast import WeatherForecastAdapter
from .adapters.geo_context import GeoContextAdapter
from .adapters.sensors import SensorAdapter
from .adapters.perception import PerceptionAdapter
from .adapters.user_events import UserEventsAdapter
from .adapters.history import HistoryAdapter
from .evidence_ledger import EvidenceLedger
from .evidence_validation import validate_evidence, quarantine_evidence
from .temporal_alignment import assign_temporal_window, compute_stale_flags
from .spatial_alignment import build_spatial_index
from .freshness import compute_freshness_batch
from .conflict_resolver import detect_conflicts_with_diagnostics
from .gap_analyzer import detect_gaps
from .confidence_model import compute_confidence_batch
from .fusion_rules import fuse_features
from .diagnostics import build_diagnostics
from .outputs.layer2_adapter import build_layer2_context
from .outputs.layer10_adapter import build_layer10_payload


class Layer1FusionEngine:
    """Deterministic multi-source fusion context engine.

    Same inputs → identical Layer1ContextPackage.
    """

    def __init__(self) -> None:
        self._registry = SourceRegistry()
        self._register_adapters()

    def _register_adapters(self) -> None:
        self._registry.register(Sentinel2Adapter())
        self._registry.register(Sentinel1Adapter())
        self._registry.register(EnvironmentAdapter())
        self._registry.register(WeatherForecastAdapter())
        self._registry.register(GeoContextAdapter())
        self._registry.register(SensorAdapter())
        self._registry.register(PerceptionAdapter())
        self._registry.register(UserEventsAdapter())
        self._registry.register(HistoryAdapter())

    def fuse(self, bundle: Layer1InputBundle) -> Layer1ContextPackage:
        """Execute the 18-step fusion pipeline."""

        # 1. Validate input bundle
        if not bundle.plot_id:
            raise ValueError("Layer1InputBundle.plot_id is required")
        if not bundle.run_id:
            raise ValueError("Layer1InputBundle.run_id is required")

        all_evidence: List[EvidenceItem] = []
        all_envelopes: List[SourceEnvelope] = []
        all_quarantined: List[QuarantinedEvidence] = []

        # 2–3. Build source envelopes and run adapters
        source_packages = self._gather_packages(bundle)

        for family, packages in source_packages.items():
            adapter = self._registry.get_adapter(family)
            if adapter is None:
                continue

            for pkg in packages:
                # 2. Build source envelope
                envelope = adapter.source_health(pkg)
                violations = self._registry.validate_envelope(envelope)
                if violations and envelope.source_status != "missing":
                    all_quarantined.append(
                        self._registry.quarantine_envelope(envelope, violations)
                    )
                    continue
                all_envelopes.append(envelope)

                # 3. Run adapter → evidence
                if adapter.can_read(pkg):
                    items = adapter.extract_evidence(pkg, bundle)
                    all_evidence.extend(items)

        # 4–5. Validate evidence and quarantine invalid
        valid_evidence: List[EvidenceItem] = []
        for item in all_evidence:
            violations = validate_evidence(item)
            if violations:
                all_quarantined.append(quarantine_evidence(item, violations))
            else:
                valid_evidence.append(item)

        # 6. Build evidence ledger
        ledger = EvidenceLedger()
        rejected = ledger.add_batch(valid_evidence)
        for eid, violations in rejected.items():
            matching = [e for e in valid_evidence if e.evidence_id == eid]
            if matching:
                all_quarantined.append(quarantine_evidence(matching[0], violations))

        # 7. Temporal alignment — persist on each evidence item
        for item in ledger.all_items:
            item.temporal_scope = assign_temporal_window(item, bundle.run_timestamp)
        compute_stale_flags(ledger.all_items, bundle.run_timestamp)

        # 8. Spatial alignment
        spatial_index = build_spatial_index(ledger.all_items, bundle.plot_id)

        # 9. Freshness
        compute_freshness_batch(ledger.all_items, bundle.run_timestamp)

        # 10. Conflict resolution (with diagnostics for no_conflict_suppression proof)
        conflicts, resolver_diag = detect_conflicts_with_diagnostics(ledger.all_items)

        # 11. Gap analysis
        gaps = detect_gaps(ledger.all_items)

        # 12–13. Apply confidence model
        compute_confidence_batch(ledger.all_items, conflicts)

        # 14. Fuse features (Fix #3: pass run_id for data-quality provenance)
        fused = fuse_features(ledger.all_items, run_id=bundle.run_id)

        # 17. Build diagnostics and provenance (Fix #2: pass fused for computed prohibitions)
        diagnostics = build_diagnostics(
            ledger.all_items, all_envelopes, conflicts, gaps, all_quarantined,
            fused=fused,
            resolver_diag=resolver_diag,
        )

        # Fix #11: multi-package provenance
        input_package_ids: Dict[str, List[str]] = defaultdict(list)
        for env in all_envelopes:
            input_package_ids[env.source_family].append(env.package_id)

        # Fix #11: accurate source counts
        source_counts: Dict[str, int] = defaultdict(int)
        for env in all_envelopes:
            source_counts[env.source_family] += 1

        provenance = Layer1Provenance(
            run_id=bundle.run_id,
            engine_version="layer1_fusion_v1",
            contract_version="1.0.0",
            input_package_ids=dict(input_package_ids),
            evidence_count=ledger.count,
            fused_feature_count=self._count_fused(fused),
            conflicts_count=len(conflicts),
            gaps_count=len(gaps),
            quarantined_count=len(all_quarantined),
            generated_at=bundle.run_timestamp,
        )

        # State summary
        state_summary = self._build_state_summary(fused, diagnostics, conflicts, gaps)

        # Build the core package first (without downstream payloads)
        pkg = Layer1ContextPackage(
            plot_id=bundle.plot_id,
            run_id=bundle.run_id,
            generated_at=bundle.run_timestamp,
            time_window=TimeWindow(
                start=bundle.window_start,
                end=bundle.window_end,
                label="fusion_window",
            ),
            spatial_index=spatial_index,
            fused_features=fused,
            state_summary=state_summary,
            source_health=SourceHealthReport(
                envelopes=all_envelopes,
                source_counts=dict(source_counts),
                source_statuses={env.source_family: env.source_status for env in all_envelopes},
                missing_sources=[
                    env.source_family for env in all_envelopes
                    if env.source_status == "missing"
                ],
            ),
            conflicts=conflicts,
            gaps=gaps,
            # Fix #7: include evidence items from ledger
            evidence_items=ledger.all_items,
            provenance=provenance,
            diagnostics=diagnostics,
        )

        # 15–16. Build downstream payloads using REAL output adapters (Fix #8)
        pkg.layer2_input = build_layer2_context(pkg)
        pkg.layer10_payload = build_layer10_payload(pkg)

        # 18. Return context package
        return pkg

    def _gather_packages(self, bundle: Layer1InputBundle) -> Dict[str, List[Any]]:
        """Map bundle fields to source families."""
        packages: Dict[str, List[Any]] = {}

        # Sentinel-2 (list of scene packages)
        packages["sentinel2"] = bundle.sentinel2_packages or []

        # Sentinel-1
        packages["sentinel1"] = bundle.sentinel1_packages or []

        # Environment (single package)
        if bundle.environment_package is not None:
            packages["environment"] = [bundle.environment_package]
        else:
            packages["environment"] = [None]

        # Weather forecast (from environment package)
        if bundle.weather_forecast_package is not None:
            packages["weather_forecast"] = [bundle.weather_forecast_package]
        elif bundle.environment_package is not None:
            packages["weather_forecast"] = [bundle.environment_package]
        else:
            packages["weather_forecast"] = [None]

        # Geo context
        if bundle.geo_context_package is not None:
            packages["geo_context"] = [bundle.geo_context_package]
        else:
            packages["geo_context"] = [None]

        # Sensors
        if bundle.sensor_context_package is not None:
            packages["sensor"] = [bundle.sensor_context_package]
        else:
            packages["sensor"] = [None]

        # Perception
        packages["perception"] = bundle.perception_packages or []

        # User events
        if bundle.user_events:
            packages["user_event"] = [bundle.user_events]
        else:
            packages["user_event"] = [[]]

        # History
        if bundle.historical_layer1_package is not None:
            packages["history"] = [bundle.historical_layer1_package]
        else:
            packages["history"] = [None]

        return packages

    def _count_fused(self, fused: FusedFeatureSet) -> int:
        return sum(len(g) for g in [
            fused.water_context, fused.vegetation_context,
            fused.phenology_context, fused.stress_evidence_context,
            fused.soil_site_context, fused.operational_context,
            fused.data_quality_context,
        ])

    def _build_state_summary(self, fused, diagnostics, conflicts, gaps) -> Layer1StateSummary:
        has_water = len(fused.water_context) > 0
        has_veg = len(fused.vegetation_context) > 0

        blocking = [g.gap_type for g in gaps if g.severity == "blocking"]
        major_conflicts = [
            c.conflict_type for c in conflicts if c.severity == "major"
        ]

        usable = diagnostics.data_health.overall >= 0.25
        return Layer1StateSummary(
            water_context_status="available" if has_water else "missing",
            vegetation_context_status="available" if has_veg else "missing",
            phenology_context_status="available" if fused.phenology_context else "missing",
            soil_site_context_status="available" if fused.soil_site_context else "missing",
            operational_context_status="available" if fused.operational_context else "missing",
            data_health_status=diagnostics.data_health.status,
            usable_for_layer2=usable,
            usable_for_layer10=usable,
            confidence_ceiling=diagnostics.data_health.confidence_ceiling,
            blocking_gaps=blocking,
            unresolved_major_conflicts=major_conflicts,
            data_health=diagnostics.data_health,
        )
