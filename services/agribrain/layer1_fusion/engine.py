"""
Layer 1 Fusion Context Engine V1.

21-step deterministic pipeline:
  1. Validate input bundle
  2. Build source envelopes
  3. Run adapters -> EvidenceItems
  4. Validate units/scopes/provenance
  5. Quarantine invalid evidence
  6. Build EvidenceLedger
  7. Run temporal alignment
  8. Run spatial alignment
  8.5 Raster grid ingestion (optional -- if composites provided)
  8.6 EO Foundation Model embedding (optional -- multi-spectral bands)
  8.7 Zone segmentation (optional -- if rasters have >=16 valid NDVI pixels)
  9. Compute freshness
  10. Run conflict resolver
  11. Run gap analyzer
  12. Apply confidence model (conflict-adjusted)
  13. Run fusion rules (on confidence-adjusted evidence)
  14. Build fused feature groups
  15. Build Layer2 input payload (real adapter)
  16. Build Layer10 spatial payload (real adapter)
  17. Build diagnostics/provenance (computed prohibitions)
  17.5 Enforce context invariants (runtime safety)
  18. Record audit log
  19. Return Layer1ContextPackage (with evidence_items)

Layer 1 never performs live data acquisition.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

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
    CORE_SOURCE_FAMILIES,
    OPTIONAL_SOURCE_FAMILIES,
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
from .adapters.sentinel5p import Sentinel5PAdapter
from .adapters.drone import DroneStructuralAdapter
from .adapters.l0_state import Layer0StateAdapter
from .adapters.microzone import MicroZoneAdapter
from .adapters.asmae_adapter import ASMAEAdapter
from .evidence_ledger import EvidenceLedger
from .evidence_validation import validate_evidence, quarantine_evidence
from .truth_bridge import normalize_evidence_truth
from .temporal_alignment import assign_temporal_window, compute_stale_flags, is_available_at_cutoff
from .spatial_alignment import build_spatial_index
from .freshness import compute_freshness_batch
from .source_family import normalize_source_family
from .conflict_resolver import detect_conflicts_with_diagnostics
from .gap_analyzer import detect_gaps
from .confidence_model import compute_confidence_batch
from .fusion_rules import fuse_features
from .diagnostics import build_diagnostics, validate_covariance_matrix, extract_covariance_matrices_recursive
from .context_invariants import (
    enforce_context_invariants,
    compute_spatial_fidelity,
    compute_provenance_completeness,
    compute_spatial_fidelity_from_evidence,
    compute_provenance_completeness_from_evidence,
)
from .raster_ingest import ingest_raster_composites
from .eo_foundation_model import EOFoundationModel, EmbeddingResult
from .outputs.layer2_adapter import build_layer2_context
from .outputs.layer10_adapter import build_layer10_payload


class Layer1FusionEngine:
    """Deterministic multi-source fusion context engine.

    Same inputs → identical Layer1ContextPackage.
    """

    def __init__(self) -> None:
        self._registry = SourceRegistry()
        self._register_adapters()
        self._eo_model: Optional[EOFoundationModel] = None  # Lazy-loaded

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
        self._registry.register(Sentinel5PAdapter())
        self._registry.register(DroneStructuralAdapter())
        self._registry.register(Layer0StateAdapter())
        self._registry.register(MicroZoneAdapter())
        self._registry.register(ASMAEAdapter())

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

        as_of_cutoff = (
            getattr(bundle, "as_of_cutoff", None)
            or getattr(bundle, "as_of", None)
            or bundle.window_end
            or bundle.run_timestamp
        )
        is_historical_replay = bool(
            getattr(bundle, "is_historical_replay", False)
            or (getattr(bundle, "as_of_cutoff", None) is not None)
            or (getattr(bundle, "as_of", None) is not None)
        )

        disabled_sources: Set[str] = set()

        def _check_and_validate_covariances(pkg_data: Any, source_name: str) -> None:
            if pkg_data is None:
                return
            matrices = extract_covariance_matrices_recursive(pkg_data)
            for cov_name, mat in matrices:
                if isinstance(mat, str):
                    all_quarantined.append(
                        QuarantinedEvidence(
                            evidence_id=f"{source_name}_{cov_name}",
                            reason_codes=[f"INVALID_COVARIANCE:{mat}"],
                            original_source_family=source_name,
                            variable="covariance",
                            severity="error",
                        )
                    )
                    disabled_sources.add(source_name)
                    break
                is_psd, cov_reason = validate_covariance_matrix(mat)
                if not is_psd:
                    all_quarantined.append(
                        QuarantinedEvidence(
                            evidence_id=f"{source_name}_{cov_name}",
                            reason_codes=[f"INVALID_COVARIANCE:{cov_reason}"],
                            original_source_family=source_name,
                            variable="covariance",
                            severity="error",
                        )
                    )
                    disabled_sources.add(source_name)
                    break

        if bundle.layer0_state_package:
            _check_and_validate_covariances(bundle.layer0_state_package, "l0_state")

        if bundle.asmae_output:
            _check_and_validate_covariances(bundle.asmae_output, "asmae")

        # 2–3. Build source envelopes and run adapters (immutable bundle handling)
        source_packages = self._gather_packages(bundle, disabled_sources=disabled_sources, all_quarantined=all_quarantined)

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
                    for item in items:
                        normalize_evidence_truth(item, source_context=pkg)
                    all_evidence.extend(items)

        # 4–5. Validate evidence and quarantine invalid
        valid_evidence: List[EvidenceItem] = []
        for item in all_evidence:
            # SPEC-B / PR28-01: Universal cutoff enforcement at primary engine intake
            is_avail, avail_reason = is_available_at_cutoff(item, as_of_cutoff, is_historical_replay=is_historical_replay)
            if not is_avail:
                all_quarantined.append(
                    quarantine_evidence(item, [f"HISTORICAL_CUTOFF_VIOLATION:{avail_reason}"])
                )
                continue

            # SPEC-C / PR28-03: Plot namespace validation
            violations = validate_evidence(item, expected_plot_id=bundle.plot_id)
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

        # 8. Spatial alignment (enriched with L0 WSR data if available; R9-04: disabled sources excluded)
        l0_spatial = bundle.layer0_state_package if "l0_state" not in disabled_sources else None
        spatial_index = build_spatial_index(
            ledger.all_items, bundle.plot_id,
            layer0_state=l0_spatial,
        )

        # 8.5 Raster grid ingestion (optional — pixel-level fidelity)
        raster_audit_count = 0
        if bundle.raster_composites:
            raster_evidence, raster_refs = ingest_raster_composites(
                bundle.raster_composites, bundle.plot_id, bundle.run_timestamp,
            )
            admitted_raster_vars = set()
            for re in raster_evidence:
                is_avail, avail_reason = is_available_at_cutoff(re, as_of_cutoff, is_historical_replay=is_historical_replay)
                if not is_avail:
                    all_quarantined.append(
                        quarantine_evidence(re, [f"HISTORICAL_CUTOFF_VIOLATION:{avail_reason}"])
                    )
                    continue

                # ingest_raster_composites normalized this item against the
                # individual raster, not the multi-raster wrapper.
                violations = validate_evidence(re, expected_plot_id=bundle.plot_id)
                if violations:
                    all_quarantined.append(quarantine_evidence(re, violations))
                else:
                    rejected_re = ledger.add(re)
                    if rejected_re:
                        all_quarantined.append(quarantine_evidence(re, rejected_re))
                    else:
                        admitted_raster_vars.add(re.variable)
            # R9-05: Only admit raster references whose evidence was admitted (not quarantined)
            for rr in raster_refs:
                if rr.variable in admitted_raster_vars:
                    spatial_index.raster_refs.append(rr)
            raster_audit_count = len(raster_evidence)

        # 8.5.1 ASMAE Raster Ingestion (R8-01: block raster export when ASMAE covariance is invalid; R9-05: check cutoff)
        if bundle.asmae_output and "asmae" not in disabled_sources:
            asmae_prov = bundle.asmae_output.get("provenance") or {}
            asmae_ts = asmae_prov.get("published_at") or asmae_prov.get("timestamp") or bundle.asmae_output.get("timestamp")
            asmae_cutoff_violation = False
            if is_historical_replay and asmae_ts:
                try:
                    from .temporal_alignment import ensure_utc
                    asmae_dt = ensure_utc(datetime.fromisoformat(str(asmae_ts)))
                    if asmae_dt > as_of_cutoff:
                        asmae_cutoff_violation = True
                        all_quarantined.append(
                            QuarantinedEvidence(
                                evidence_id="asmae_raster_output",
                                reason_codes=[f"HISTORICAL_CUTOFF_VIOLATION: asmae {asmae_dt} > cutoff {as_of_cutoff}"],
                                original_source_family="asmae",
                                variable="asmae_raster",
                                severity="error",
                            )
                        )
                except Exception:
                    pass

            if not asmae_cutoff_violation:
                from .raster_ingest import ingest_asmae_raster_refs
                asmae_raster_refs = ingest_asmae_raster_refs(
                    bundle.asmae_output, bundle.plot_id,
                )
                for rr in asmae_raster_refs:
                    spatial_index.raster_refs.append(rr)

        # 8.7 Zone segmentation (optional — when NDVI rasters have ≥16 valid cells)
        zone_seg_audit = None
        eo_embedding_audit = None
        if bundle.raster_composites:
            # 8.6 EO Foundation Model embedding
            eo_embedding_audit = self._try_eo_embedding(
                bundle, ledger, all_quarantined, as_of_cutoff=as_of_cutoff,
            )

            # 8.7 Zone segmentation
            zone_seg_audit = self._try_zone_segmentation(
                bundle, ledger, spatial_index, all_quarantined, as_of_cutoff=as_of_cutoff,
            )

        # 9. Freshness
        compute_freshness_batch(ledger.all_items, bundle.run_timestamp)

        # 10. Conflict resolution (with diagnostics for no_conflict_suppression proof)
        conflicts, resolver_diag = detect_conflicts_with_diagnostics(ledger.all_items)

        # 11. Gap analysis
        gaps = detect_gaps(ledger.all_items, all_envelopes, reference_time=bundle.run_timestamp)

        # 12. Apply confidence model (conflict-adjusted, before fusion)
        compute_confidence_batch(ledger.all_items, conflicts)

        # 13. Fuse features (on confidence-adjusted evidence; Fix #3: pass run_id)
        fused = fuse_features(ledger.all_items, run_id=bundle.run_id)

        # 17. Build diagnostics and provenance (Fix #2: pass fused for computed prohibitions)
        # Pre-compute health scores to pass into diagnostics (Fix F16: no hardcoded 1.0)
        _pre_spatial = compute_spatial_fidelity_from_evidence(ledger.all_items, spatial_index)
        _pre_provenance = compute_provenance_completeness_from_evidence(ledger.all_items)
        diagnostics = build_diagnostics(
            ledger.all_items, all_envelopes, conflicts, gaps, all_quarantined,
            fused=fused,
            resolver_diag=resolver_diag,
            spatial_fidelity=_pre_spatial,
            provenance_completeness=_pre_provenance,
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
            plot_geometry=bundle.plot_geometry,
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

        # 17.5 Enforce context invariants (runtime safety — modeled on L0)
        ctx_violations = enforce_context_invariants(pkg)
        pkg.provenance.invariant_violations = [
            v.to_dict() for v in ctx_violations
        ]

        # Final data health update from full package (post-build invariants)
        pkg.diagnostics.data_health.spatial_fidelity = compute_spatial_fidelity(pkg)
        pkg.diagnostics.data_health.provenance_completeness = compute_provenance_completeness(pkg)

        # 15–16. Build downstream payloads using REAL output adapters (Fix #8)
        # Moved after data health updates so layer2_input receives final, fresh health score.
        pkg.layer2_input = build_layer2_context(pkg)
        pkg.layer10_payload = build_layer10_payload(pkg)

        # 18. Record audit log
        audit: list = []
        if all_quarantined:
            audit.append({
                "step": "quarantine",
                "count": len(all_quarantined),
                "detail": [q.evidence_id for q in all_quarantined],
            })
        if conflicts:
            audit.append({
                "step": "conflict_resolution",
                "count": len(conflicts),
                "detail": [c.conflict_type for c in conflicts],
            })
        if gaps:
            audit.append({
                "step": "gap_detection",
                "count": len(gaps),
                "detail": [g.gap_type for g in gaps],
            })
        if ctx_violations:
            audit.append({
                "step": "invariant_enforcement",
                "count": len(ctx_violations),
                "auto_fixed": sum(1 for v in ctx_violations if v.auto_fixed),
            })
        if raster_audit_count > 0:
            audit.append({
                "step": "raster_grid_ingestion",
                "count": raster_audit_count,
                "composites": list(bundle.raster_composites.keys()),
            })
        if zone_seg_audit is not None:
            audit.append(zone_seg_audit)
        if eo_embedding_audit is not None:
            audit.append(eo_embedding_audit)
        pkg.audit_log = audit

        # 19. Return context package
        return pkg

    def _gather_packages(
        self,
        bundle: Layer1InputBundle,
        disabled_sources: Optional[Set[str]] = None,
        all_quarantined: Optional[List[QuarantinedEvidence]] = None,
    ) -> Dict[str, List[Any]]:
        """Map Layer 0 data packages to source families for adapter dispatch.

        Source hierarchy (by agronomic measurement fidelity):
        ─────────────────────────────────────────────────────

        TIER 1 — HIGH-FIDELITY DIRECT OBSERVATION:
          sentinel2   ← Optical multispectral (NDVI, NDMI, EVI) — crop canopy
                        state, chlorophyll proxy, 5-day revisit, 10m resolution.
                        Gold standard for vegetation monitoring.
          sentinel1   ← C-band SAR backscatter — soil moisture proxy via
                        dielectric constant, all-weather/all-light, 6-day revisit.
                        Critical for water balance during cloudy seasons.
          sensor      ← In-situ IoT probes (soil VWC, temperature, rain gauge,
                        flow meters) — sub-hourly, point-scope, highest temporal
                        resolution. Calibrated instruments provide ground truth.
          drone       ← RGB/multispectral UAV imagery — tree-level structural
                        analysis (tree count, row geometry, weed coverage,
                        canopy density). Sub-meter resolution.

        TIER 2 — MODELED / CONTEXTUAL:
          environment ← Gridded reanalysis (ERA5, Open-Meteo) — temperature,
                        humidity, wind, precipitation, VPD, ET₀. ~0.25° resolution.
                        Provides atmospheric context, not crop state.
          weather_forecast ← NWP model output (GFS, ECMWF) — 7-day precipitation,
                        temperature, frost risk. Skill degrades with lead time.
          geo_context ← Static geospatial layers (DEM elevation/slope, soil maps,
                        WaPOR ET, land cover classification). 250m+ resolution.
                        Contextual only — never drives crop state.

        TIER 3 — USER / HISTORICAL / DERIVED:
          user_event  ← Farmer-reported management actions (irrigation dates,
                        fertilizer applications, planting/harvest records).
                        High agronomic value but subjective timing accuracy.
          history     ← Previous-season Layer 1 packages for inter-annual trend
                        analysis and baseline comparison. Always marked stale.
          perception  ← Computer vision outputs (disease risk probability, pest
                        detection confidence). Model-dependent, flagged accordingly.
          sentinel5p  ← TROPOMI Solar-Induced Fluorescence (SIF) — direct proxy
                        for photosynthetic electron transport. Coarse resolution
                        (3.5×7 km) but unique photosynthesis signal.
          l0_state    ← Layer 0 Kalman-filtered state vectors + ValidationGraph
                        reliability weights. Carries upstream uncertainty.

        Missing sources emit [None] so adapters still generate health envelopes,
        which feed the gap analyzer for data completeness assessment.
        """
        if bundle.layer0_source_packages:
            # Canonical Layer 0 path: route only through canonical packages.
            packages: Dict[str, List[Any]] = {}
            for source_family, pkgs in bundle.layer0_source_packages.items():
                if pkgs is None:
                    continue
                if not isinstance(pkgs, list):
                    pkgs = [pkgs]
                canonical_family = normalize_source_family(source_family)
                actual_pkgs = [p for p in pkgs if p is not None]
                if actual_pkgs:
                    admitted_pkgs = []
                    for pkg in actual_pkgs:
                        pkg_plot = getattr(pkg, "plot_id", None)
                        # R8-04 / R8-G06: Missing package plot identity must fail closed
                        if not pkg_plot or not str(pkg_plot).strip():
                            if all_quarantined is not None:
                                all_quarantined.append(
                                    QuarantinedEvidence(
                                        evidence_id=getattr(pkg, "package_id", f"{canonical_family}_pkg"),
                                        reason_codes=["MISSING_SOURCE_PACKAGE_PLOT_SCOPE: package has no plot_id"],
                                        original_source_family=canonical_family,
                                        variable="package",
                                        severity="error",
                                    )
                                )
                            continue
                        if bundle.plot_id and pkg_plot != bundle.plot_id:
                            if all_quarantined is not None:
                                all_quarantined.append(
                                    QuarantinedEvidence(
                                        evidence_id=getattr(pkg, "package_id", f"{canonical_family}_pkg"),
                                        reason_codes=[f"FOREIGN_PLOT_SCOPE_MISMATCH: package plot {pkg_plot} != bundle {bundle.plot_id}"],
                                        original_source_family=canonical_family,
                                        variable="package",
                                        severity="error",
                                    )
                                )
                            continue
                        # R8-05 / R8-G07: Preserve input package immutability; never mutate pkg.source_family in-place
                        admitted_pkgs.append(pkg)
                    if admitted_pkgs:
                        packages.setdefault(canonical_family, []).extend(admitted_pkgs)

            l0_state_pkg = bundle.layer0_state_package if (disabled_sources is None or "l0_state" not in disabled_sources) else None
            packages["l0_state"] = [l0_state_pkg] if l0_state_pkg else [None]

            asmae_pkg = bundle.asmae_output if (disabled_sources is None or "asmae" not in disabled_sources) else None
            packages["asmae"] = [asmae_pkg] if asmae_pkg else [None]
            
            if bundle.user_events:
                packages["user_event"] = [bundle.user_events]
            else:
                packages["user_event"] = [[]]
                
            if bundle.historical_layer1_package is not None:
                packages["history"] = [bundle.historical_layer1_package]
            else:
                packages["history"] = [None]
                
            # Fill missing core/optional source families with [None] or [[]] placeholders
            for family in CORE_SOURCE_FAMILIES:
                if family not in packages:
                    packages[family] = [None]
            for family in OPTIONAL_SOURCE_FAMILIES:
                if family not in packages:
                    if family == "user_event":
                        packages[family] = [[]]
                    else:
                        packages[family] = [None]
        else:
            packages: Dict[str, List[Any]] = {}

            # TIER 1: High-fidelity direct observation
            packages["sentinel2"] = bundle.sentinel2_packages or []
            packages["sentinel1"] = bundle.sentinel1_packages or []

            if bundle.sensor_context_package is not None:
                packages["sensor"] = [bundle.sensor_context_package]
            else:
                packages["sensor"] = [None]

            packages["drone_structural"] = bundle.drone_structural_packages or []

            # TIER 2: Modeled / contextual
            if bundle.environment_package is not None:
                packages["environment"] = [bundle.environment_package]
            else:
                packages["environment"] = [None]

            if bundle.weather_forecast_package is not None:
                packages["weather_forecast"] = [bundle.weather_forecast_package]
            elif bundle.environment_package is not None:
                packages["weather_forecast"] = [bundle.environment_package]
            else:
                packages["weather_forecast"] = [None]

            if bundle.geo_context_package is not None:
                packages["geo_context"] = [bundle.geo_context_package]
            else:
                packages["geo_context"] = [None]

            # TIER 3: User / historical / derived
            packages["perception"] = bundle.perception_packages or []

            if bundle.user_events:
                packages["user_event"] = [bundle.user_events]
            else:
                packages["user_event"] = [[]]

            if bundle.historical_layer1_package is not None:
                packages["history"] = [bundle.historical_layer1_package]
            else:
                packages["history"] = [None]

            packages["sentinel5p"] = bundle.sentinel5p_packages or []

            l0_state_pkg = bundle.layer0_state_package if (disabled_sources is None or "l0_state" not in disabled_sources) else None
            packages["l0_state"] = [l0_state_pkg] if l0_state_pkg else [None]

            asmae_pkg = bundle.asmae_output if (disabled_sources is None or "asmae" not in disabled_sources) else None
            packages["asmae"] = [asmae_pkg] if asmae_pkg else [None]

        # Final safety cleanup: wrap non-list in lists, filter out None
        for k in list(packages.keys()):
            v = packages[k]
            if v is None:
                packages[k] = []
            elif not isinstance(v, list):
                packages[k] = [v]
            
            if k == "user_event":
                packages[k] = [p for p in packages[k] if p is not None]
                if not packages[k]:
                    packages[k] = [[]]
            else:
                packages[k] = [p for p in packages[k] if p is not None]
                if not packages[k]:
                    if k in CORE_SOURCE_FAMILIES or k in OPTIONAL_SOURCE_FAMILIES:
                        packages[k] = [None]

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

    def _try_zone_segmentation(
        self,
        bundle: Layer1InputBundle,
        ledger: EvidenceLedger,
        spatial_index,
        all_quarantined: list,
        as_of_cutoff: Optional[datetime] = None,
    ) -> Optional[Dict]:
        """Conditionally run zone segmentation from NDVI rasters.

        Fires only when NDVI composite has ≥16 valid pixels.
        Uses the pure-python quantile-based engine (no numpy required).
        Returns an audit dict if segmentation ran, else None.
        """
        ndvi_composite = bundle.raster_composites.get("NDVI")
        if not ndvi_composite or not isinstance(ndvi_composite, dict):
            return None

        pixel_array = ndvi_composite.get("pixel_array")
        if not pixel_array or not pixel_array[0]:
            return None

        valid_count = ndvi_composite.get("valid_pixel_count", 0)
        if valid_count < 16:
            return None

        try:
            from .zone_engine import generate_management_zones_pure_python

            H = len(pixel_array)
            W = len(pixel_array[0]) if H > 0 else 0
            grid_spec = {"height": H, "width": W, "resolution": ndvi_composite.get("resolution_m", 10.0)}

            # Zone engine expects [T, H, W] — wrap single composite as T=1
            ndvi_stack = [pixel_array]
            sar_stack = []
            sar_composite = bundle.raster_composites.get("SAR")
            if sar_composite and isinstance(sar_composite, dict):
                sar_array = sar_composite.get("pixel_array")
                if sar_array:
                    sar_stack = [sar_array]

            zones = generate_management_zones_pure_python(
                bundle.plot_id, ndvi_stack, sar_stack, grid_spec,
            )

            # Convert zone output to SpatialIndex ZoneRefs
            from .schemas import ZoneRef
            for z_id, z_data in zones.items():
                area_frac = z_data.get("area_pct", 0.0) / 100.0
                if z_id not in {z.zone_id for z in spatial_index.zones}:
                    spatial_index.zones.append(ZoneRef(
                        zone_id=z_id,
                        label=z_data.get("label", z_id),
                        area_fraction=area_frac,
                    ))

            # V92.4-BC.10.5 Truth Governance
            from layer05_asmae.truth_contract import classify_raster_truth
            ndvi_truth = classify_raster_truth(ndvi_composite)

            zone_conf = 0.7
            diagnostic_only = False
            state_update_allowed = True
            flags = []

            if ndvi_truth.truth_class not in ("provider_observation", "assimilated_state"):
                zone_conf = min(zone_conf, 0.30)
                diagnostic_only = True
                state_update_allowed = False
                flags.append("DERIVED_FROM_NON_PROVIDER_RASTER")

            # Create zone-scoped evidence from zone signatures
            for z_id, z_data in zones.items():
                sig = z_data.get("signature", {})
                ndvi_med = sig.get("ndvi_median")
                if ndvi_med is not None:
                    from .schemas import EvidenceItem as _EI
                    self._admit_evidence_or_quarantine(
                        _EI(
                            evidence_id=f"zone_seg_{z_id}_ndvi",
                            plot_id=bundle.plot_id,
                            variable="ndvi",
                            value=ndvi_med,
                            unit="index",
                            source_family="zone_segmentation",
                            source_id=f"zone_seg_{bundle.run_id}",
                            observation_type="derived",
                            spatial_scope="zone",
                            scope_id=z_id,
                            observed_at=bundle.run_timestamp,
                            confidence=zone_conf,
                            reliability=zone_conf,
                            freshness_score=1.0,
                            provenance_ref=f"zone_seg_{bundle.run_id}_{z_id}",
                            diagnostic_only=diagnostic_only,
                            state_update_allowed=state_update_allowed,
                            flags=flags,
                            parent_truth_class=ndvi_truth.truth_class,
                            parent_source_reality=ndvi_truth.source_reality,
                            truth_class="derived_zone",
                            data_status="estimated" if not diagnostic_only else "fallback",
                        ),
                        ledger,
                        all_quarantined,
                        bundle=bundle,
                        as_of_cutoff=as_of_cutoff,
                        source_context=bundle.raster_composites,
                    )

            return {
                "step": "zone_segmentation",
                "zone_count": len(zones),
                "method": "quantile_pure_python",
                "zones": list(zones.keys()),
            }
        except Exception:
            return None

    def _try_eo_embedding(
        self,
        bundle: Layer1InputBundle,
        ledger: EvidenceLedger,
        all_quarantined: list,
        as_of_cutoff: Optional[datetime] = None,
    ) -> Optional[Dict]:
        """Run EO Foundation Model embedding on multi-spectral rasters.

        Fires when raster composites contain spectral band data.
        Creates evidence items for anomaly_score and anomaly_embedding.
        Returns an audit dict if embedding ran, else None.
        """
        # Check for multi-spectral band data in raster composites
        band_mapping = {
            "B2": "B2", "B3": "B3", "B4": "B4",
            "B8": "B8", "B11": "B11", "B12": "B12",
            # Also accept uppercase index names from some pipelines
            "BLUE": "B2", "GREEN": "B3", "RED": "B4",
            "NIR": "B8", "SWIR1": "B11", "SWIR2": "B12",
        }

        band_arrays: Dict[str, Any] = {}
        ref_shape = None
        validated_crs: Optional[str] = None
        validated_transform: Optional[Tuple[float, ...]] = None
        grid_mismatch = False

        top_grid = bundle.raster_composites.get("grid_spec") if isinstance(bundle.raster_composites.get("grid_spec"), dict) else {}
        default_crs = bundle.raster_composites.get("crs") or top_grid.get("crs")
        default_tf = bundle.raster_composites.get("transform") or bundle.raster_composites.get("affine") or top_grid.get("transform") or top_grid.get("affine")

        for key, raster_data in bundle.raster_composites.items():
            mapped = band_mapping.get(key.upper())
            if mapped and isinstance(raster_data, dict):
                pixel_array = raster_data.get("pixel_array")
                if pixel_array and isinstance(pixel_array, list) and len(pixel_array) > 0 and isinstance(pixel_array[0], list):
                    band_arrays[mapped] = pixel_array
                    h = len(pixel_array)
                    w = len(pixel_array[0])
                    if any(not isinstance(r, list) or len(r) != w for r in pixel_array):
                        grid_mismatch = True
                    if ref_shape is None:
                        ref_shape = (h, w)
                    elif ref_shape != (h, w):
                        grid_mismatch = True

                    r_grid = raster_data.get("grid_spec") if isinstance(raster_data.get("grid_spec"), dict) else {}
                    b_crs = raster_data.get("crs") or r_grid.get("crs") or default_crs
                    if b_crs and isinstance(b_crs, str) and b_crs.strip():
                        b_crs_clean = b_crs.strip()
                        if validated_crs is None:
                            validated_crs = b_crs_clean
                        elif validated_crs.upper() != b_crs_clean.upper():
                            grid_mismatch = True
                    else:
                        grid_mismatch = True

                    b_tf = raster_data.get("transform") or raster_data.get("affine") or r_grid.get("transform") or r_grid.get("affine") or default_tf
                    if b_tf and isinstance(b_tf, (list, tuple)) and len(b_tf) == 6:
                        try:
                            tf_tuple = tuple(float(x) for x in b_tf)
                            from .eo_foundation_model import validate_spatial_grid
                            if not validate_spatial_grid(b_crs, tf_tuple, (h, w)):
                                grid_mismatch = True
                            elif validated_transform is None:
                                validated_transform = tf_tuple
                            elif validated_transform != tf_tuple:
                                grid_mismatch = True
                        except (ValueError, TypeError):
                            grid_mismatch = True
                    else:
                        grid_mismatch = True

        if len(band_arrays) < 3:
            return None  # Not enough spectral bands

        if grid_mismatch:
            validated_crs = None
            validated_transform = None

        cm_data = bundle.raster_composites.get("cloud_mask") or bundle.raster_composites.get("CLOUD_MASK") or bundle.raster_composites.get("QUALITY")
        cloud_mask = cm_data.get("pixel_array") if isinstance(cm_data, dict) else None
        if cloud_mask and (not isinstance(cloud_mask, list) or len(cloud_mask) == 0):
            cloud_mask = None

        try:
            # Lazy-load the model
            if self._eo_model is None:
                self._eo_model = EOFoundationModel(
                    model_path=bundle.eo_model_path,
                )

            result = self._eo_model.infer(
                band_arrays,
                cloud_mask=cloud_mask,
                crs=validated_crs,
                transform=validated_transform,
            )
            if result is None:
                return None

            eo_flags = [f"MODEL_{result.model_id.upper()}"]
            is_spat_qual = getattr(result, "is_spatial_qualified", True)
            if not is_spat_qual:
                eo_flags.append("UNQUALIFIED_SPATIAL_IDENTITY")

            # Create anomaly_score evidence
            # Spatial qualification verifies geometric bounds, but model output is an
            # estimated_model feature, NOT observed ground truth. Deny state updates.
            self._admit_evidence_or_quarantine(
                EvidenceItem(
                    evidence_id=f"eo_anomaly_score_{result.tile_hash[:8]}",
                    plot_id=bundle.plot_id,
                    variable="anomaly_score",
                    value=result.anomaly_score,
                    unit="score",
                    source_family="eo_foundation",
                    source_id=f"eo_{result.model_id}",
                    observation_type="derived_feature",
                    spatial_scope="plot",
                    observed_at=bundle.run_timestamp,
                    confidence=result.confidence,
                    reliability=min(0.75, result.confidence),
                    freshness_score=1.0,
                    provenance_ref=f"eo_foundation_{result.tile_hash}",
                    flags=list(eo_flags),
                    diagnostic_only=True,
                    state_update_allowed=False,
                    truth_class="estimated_model",
                    source_reality="provider_model_feed",
                    production_usable=is_spat_qual,
                    real_provider_product=False,
                ),
                ledger,
                all_quarantined,
                bundle=bundle,
                as_of_cutoff=as_of_cutoff,
                source_context=bundle.raster_composites,
            )

            # Create anomaly_embedding evidence (embedding as value)
            self._admit_evidence_or_quarantine(
                EvidenceItem(
                    evidence_id=f"eo_anomaly_embedding_{result.tile_hash[:8]}",
                    plot_id=bundle.plot_id,
                    variable="anomaly_embedding",
                    value=result.embedding,
                    unit="index",
                    source_family="eo_foundation",
                    source_id=f"eo_{result.model_id}",
                    observation_type="derived_feature",
                    spatial_scope="plot",
                    observed_at=bundle.run_timestamp,
                    confidence=result.confidence,
                    reliability=min(0.75, result.confidence),
                    freshness_score=1.0,
                    provenance_ref=f"eo_foundation_{result.tile_hash}",
                    flags=list(eo_flags) + [f"DIM_{len(result.embedding)}"],
                    # Embedding is informational — downstream uses anomaly_score for decisions
                    diagnostic_only=True,
                    state_update_allowed=False,
                    truth_class="estimated_model",
                    source_reality="estimated_model",
                    production_usable=False,
                    real_provider_product=False,
                ),
                ledger,
                all_quarantined,
                bundle=bundle,
                as_of_cutoff=as_of_cutoff,
                source_context=bundle.raster_composites,
            )

            return {
                "step": "eo_foundation_embedding",
                "model_id": result.model_id,
                "mode": self._eo_model.mode,
                "embedding_dim": len(result.embedding),
                "anomaly_score": result.anomaly_score,
                "confidence": result.confidence,
                "bands_used": result.band_count,
                "valid_pixels": result.valid_pixels,
                "tile_hash": result.tile_hash,
            }
        except Exception:
            return None

    def _admit_evidence_or_quarantine(
        self,
        item: EvidenceItem,
        ledger: EvidenceLedger,
        all_quarantined: list,
        bundle: Optional[Layer1InputBundle] = None,
        as_of_cutoff: Optional[datetime] = None,
        source_context: Any = None,
    ):
        from .evidence_validation import validate_evidence, quarantine_evidence
        from .truth_bridge import normalize_evidence_truth
        from .temporal_alignment import is_available_at_cutoff
        
        if "UNQUALIFIED_SPATIAL_IDENTITY" in getattr(item, "flags", []):
            item.state_update_allowed = False
            item.production_usable = False
            item.diagnostic_only = True

        normalized_item = normalize_evidence_truth(item, source_context=source_context)
        if "UNQUALIFIED_SPATIAL_IDENTITY" in getattr(normalized_item, "flags", []):
            normalized_item.state_update_allowed = False
            normalized_item.production_usable = False
            normalized_item.diagnostic_only = True

        # SPEC-B / Gate 12: Universal cutoff check on secondary evidence intake
        eff_cutoff = as_of_cutoff or (getattr(bundle, "as_of_cutoff", None) if bundle else None) or (getattr(bundle, "as_of", None) if bundle else None) or (bundle.window_end if bundle else None) or (bundle.run_timestamp if bundle else None)
        is_replay = bool(
            (bundle and getattr(bundle, "is_historical_replay", False))
            or (bundle and getattr(bundle, "as_of_cutoff", None) is not None)
            or (bundle and getattr(bundle, "as_of", None) is not None)
        )
        if eff_cutoff is not None:
            is_avail, avail_reason = is_available_at_cutoff(normalized_item, eff_cutoff, is_historical_replay=is_replay)
            if not is_avail:
                all_quarantined.append(
                    quarantine_evidence(normalized_item, [f"HISTORICAL_CUTOFF_VIOLATION:{avail_reason}"])
                )
                return

        # SPEC-C / Gate 12: Plot namespace isolation against bundle.plot_id
        expected_plot = bundle.plot_id if bundle else getattr(normalized_item, "plot_id", None)
        violations = validate_evidence(normalized_item, expected_plot_id=expected_plot)
        if violations:
            all_quarantined.append(quarantine_evidence(normalized_item, violations))
        else:
            rejected = ledger.add(normalized_item)
            if rejected:
                all_quarantined.append(quarantine_evidence(normalized_item, rejected))
