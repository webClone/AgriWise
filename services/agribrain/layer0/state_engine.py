"""
Layer 0 State Engine — Standalone daily state assimilation.

Extracted from legacy Layer 1 ``data_fusion.py:_run_layer0_assimilation()``
so that Layer 0 owns its own state estimation lifecycle.

Entry point:
    Layer0StateEngine.run(plot_id, ...) -> Layer0StatePackage

Layer 1 (both legacy and modern) should call this instead of
manually building Kalman observations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from copy import deepcopy
import hashlib
import json
import math
import os

from services.agribrain.layer0.source_package import Layer0StatePackage, Layer0SourcePackage
from services.agribrain.layer0.observation_packet import DataStatus
from services.agribrain.layer0.production_admission import (
    Layer0AdmissionRequiredError, require_trusted_verifier,
    require_trusted_delivery_verifier, signed_inputs_required,
)
from services.agribrain.layer0.positive_observation_admission import (
    observation_packet_digest, PositiveObservationAdmissionVerifier,
    WEATHER_GRANT_PURPOSE, GRANT_PURPOSE, _canonical_bytes,
)


# Packet field -> (registered observation model, uncertainty sigma key).
# Preserve units and do not infer type or noise from unrelated variables.
_PACKET_KALMAN_FIELDS = {
    "ndvi_mean": ("ndvi", "ndvi"),
    "evi_mean": ("evi", "evi"),
    "ndmi_mean": ("ndmi", "ndmi"),
    "ndre_mean": ("ndre", "ndre"),
    "bsi_mean": ("bare_soil_index", "bsi"),
    "vv_db_mean": ("vv", "vv_db"),
    "vh_db_mean": ("vh", "vh_db"),
    "surface_wetness_proxy_mean": ("sar_moisture_proxy", "surface_wetness_proxy"),
    "soil_moisture_vwc": ("soil_moisture", "soil_moisture_vwc"),
    "vegetation_fraction": ("vegetation_fraction", "vegetation_fraction"),
}


@dataclass
class _WeatherDay:
    """Internal weather representation for a single day."""
    temp_max: float = 25.0
    temp_min: float = 15.0
    precipitation: float = 0.0
    et0: float = 3.0


class Layer0StateEngine:
    """Standalone Layer 0 state estimation engine.

    Accepts observation packets, weather, and user events, then runs
    the Kalman-based daily assimilation + validation graph + invariants.

    This is the canonical owner of Layer 0 state estimation.
    Legacy ``data_fusion.py`` should delegate here.
    """

    def __init__(
        self,
        positive_admission_verifier: Optional[PositiveObservationAdmissionVerifier] = None,
        plot_ownership_store: Any = None,
        principal_provider: Any = None,
        verified_delivery_verifier: Any = None,
    ):
        # Production/staging cannot silently opt out of cryptographic
        # input admission; explicit development mode remains legacy-compatible.
        require_trusted_verifier(positive_admission_verifier)
        allowed_verifiers = (PositiveObservationAdmissionVerifier,)
        try:
            from services.agribrain.layer0.v3_kms_signed_issuer import V3KmsGrantVerifier
            from services.agribrain.layer0.v3_state_admission import UnifiedAdmissionVerifier
            allowed_verifiers = (
                PositiveObservationAdmissionVerifier,
                V3KmsGrantVerifier,
                UnifiedAdmissionVerifier,
            )
        except ImportError:
            pass

        if (
            signed_inputs_required()
            and not isinstance(positive_admission_verifier, allowed_verifiers)
        ):
            raise Layer0AdmissionRequiredError(
                "Mandatory state admission requires a trusted verifier type"
            )
        self._positive_observation_admission_verifier = positive_admission_verifier
        # Trusted backend infrastructure only; never supplied by packet JSON.
        require_trusted_delivery_verifier(verified_delivery_verifier)
        self._plot_ownership_store = plot_ownership_store
        self._principal_provider = principal_provider
        self._verified_delivery_verifier = verified_delivery_verifier
        self._tenant_id = ""
        self.__packet_run_capability = object()
        self._has_kalman = False
        try:
            from services.agribrain.layer0.kalman_engine import (
                DailyAssimilationEngine, KalmanObservation
            )
            from services.agribrain.layer0.validation_graph import ValidationGraph
            from services.agribrain.layer0.monitoring import run_audit as layer0_audit
            from services.agribrain.layer0.invariants import enforce_all_invariants
            from services.agribrain.layer0.state_persistence import save_engine_state
            self._DailyAssimilationEngine = DailyAssimilationEngine
            self._KalmanObservation = KalmanObservation
            self._ValidationGraph = ValidationGraph
            self._layer0_audit = layer0_audit
            self._enforce_all_invariants = enforce_all_invariants
            self._save_engine_state = save_engine_state
            self._has_kalman = True
        except ImportError:
            pass

    def run(
        self,
        plot_id: str,
        start_date: str,
        end_date: str,
        daily_weather: Dict[str, Dict[str, Any]],
        observations_by_day: Dict[str, Dict[str, List[Any]]],
        events_by_day: Dict[str, List[Dict[str, Any]]],
        soil_props: Optional[Dict[str, Any]] = None,
        zone_ids: Optional[List[str]] = None,
        run_timestamp: Optional[datetime] = None,
        geometry_hash: str = "",
        geometry_version: Optional[int] = None,
        _packet_run_capability: Any = None,
    ) -> Layer0StatePackage:
        """Run daily state assimilation and return a Layer0StatePackage.

        Args:
            plot_id: Plot identifier.
            start_date: YYYY-MM-DD start of assimilation window.
            end_date: YYYY-MM-DD end of assimilation window.
            daily_weather: {date_str: {temp_max, temp_min, precipitation, et0}}.
            observations_by_day: {date_str: {zone_id: [KalmanObservation, ...]}}.
            events_by_day: {date_str: [event_payload, ...]}.
            soil_props: {clay_pct, sand_pct} or None.
            zone_ids: Extra zone IDs beyond "plot".
            run_timestamp: Injected timestamp for deterministic replay.

        Returns:
            Layer0StatePackage with daily_state, state_uncertainty, provenance,
            validation conflicts, and health report.
        """
        # Direct prebuilt KalmanObservation/weather dictionaries do not
        # carry independently verified packet receipts. For scientific
        # production use, only run_from_packets may provide the private
        # per-instance capability after it gates each input.
        require_trusted_delivery_verifier(self._verified_delivery_verifier)
        if (
            signed_inputs_required()
            or os.getenv("AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE", "").lower() in ("1", "true", "yes")
        ) and _packet_run_capability is not self.__packet_run_capability:
            raise Layer0AdmissionRequiredError(
                "Direct Layer0StateEngine.run inputs bypass signed packet admission"
            )
        if not self._has_kalman:
            return Layer0StatePackage(
                plot_id=plot_id,
                geometry_hash=geometry_hash,
                geometry_version=geometry_version,
                run_id=f"layer0_{plot_id}_{start_date}_{end_date}",
                scientific_publication_authorized=False,
                actuator_control_authorized=False,
                health_report={
                    "kalman_available": False,
                    "scientific_publication_authorized": False,
                    "actuator_control_authorized": False,
                },
                provenance={
                    "error": "Kalman engine not available",
                    "scientific_publication_authorized": False,
                    "actuator_control_authorized": False,
                },
            )

        now = run_timestamp or datetime.now(timezone.utc)

        # The initialization state is a prior. Its timestamp must precede
        # the first predicted day by exactly one UTC daily interval.
        # Previously it was stamped on start_date and then predicted for
        # that same date, disguising a zero-duration prediction.
        prior_date = (
            datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=1)
        ).strftime("%Y-%m-%d")
        engine = self._DailyAssimilationEngine()
        primary_zone = "plot"
        engine.add_zone(primary_zone, soil_props=soil_props, start_day=prior_date)

        # Stamp the caller-scoped run identity onto filters so the event
        # evidence router can reject foreign/unsupported event envelopes.
        for zone_filter in engine.filters.values():
            zone_filter.parent_plot_id = plot_id
            zone_filter.expected_geometry_hash = geometry_hash
            zone_filter.evidence_cutoff = now
            zone_filter.tenant_id = getattr(self, "_tenant_id", "") or ""
            zone_filter.geometry_version = geometry_version
            zone_filter.delivery_verifier = getattr(self, "_verified_delivery_verifier", None)

        # Add extra zones
        for zid in (zone_ids or []):
            if zid != primary_zone:
                engine.add_zone(zid, soil_props=soil_props, start_day=prior_date)
                engine.filters[zid].parent_plot_id = plot_id
                engine.filters[zid].expected_geometry_hash = geometry_hash
                engine.filters[zid].evidence_cutoff = now
                engine.filters[zid].tenant_id = getattr(self, "_tenant_id", "") or ""
                engine.filters[zid].geometry_version = geometry_version
                engine.filters[zid].delivery_verifier = getattr(self, "_verified_delivery_verifier", None)
                # A plot-level statistical observation is NOT an independent
                # zone-local measurement. Unobserved zones retain a prior
                # prediction; only explicitly assigned zone evidence can
                # update their own posterior. Spatial correlation/downscaling
                # belongs to a support-aware fusion operator, not list cloning.

        # Run assimilation
        engine.run_period(
            start_date, end_date,
            daily_weather, observations_by_day, events_by_day
        )

        # Extract outputs
        daily_state, state_uncertainty, provenance_log = engine.to_field_tensor_outputs()

        # Cross-source validation
        validation_conflicts = []
        source_reliability = {}
        try:
            validator = self._ValidationGraph()
            for d_rec in provenance_log:
                day = d_rec.get("day", "")
                for zid, zdata in d_rec.get("zones", {}).items():
                    state_dict = zdata.get("state", {})
                    obs_dict = {}
                    day_obs = observations_by_day.get(day, {}).get(zid, [])
                    for o in day_obs:
                        obs_dict[o.obs_type] = o.value
                    wx = daily_weather.get(day, {})
                    validator.validate_day(day, zid, state_dict, obs_dict, wx)

            conflicts = validator.get_conflict_summary(last_n_days=len(provenance_log))
            if conflicts:
                validation_conflicts = conflicts
                source_reliability = dict(validator.source_reliability)
        except Exception as ve:
            validation_conflicts = [{"error": str(ve)}]

        # Self-audit
        audit_report = {}
        try:
            boundary_info = {
                "source": "user_drawn",
                "confidence": 0.8,
                "geometry_hash": geometry_hash,
                "geometry_version": geometry_version,
            }
            audit_report = self._layer0_audit(
                plot_id=plot_id,
                tensor_daily_state=daily_state,
                tensor_state_uncertainty=state_uncertainty,
                tensor_provenance_log=provenance_log,
                tensor_boundary_info=boundary_info,
                source_reliability=source_reliability,
                conflicts=validation_conflicts,
                expected_days=len(provenance_log),
            )
        except Exception as ex_audit:
            print(f"[WARN] [Layer 0] StateEngine audit failed: {ex_audit}")

        # Build stable content-addressed run_id
        import hashlib
        run_key = f"{plot_id}:{geometry_hash}:{geometry_version}:{start_date}:{end_date}:{now.isoformat()}"
        run_id = f"layer0_{hashlib.sha256(run_key.encode()).hexdigest()[:16]}"

        return Layer0StatePackage(
            plot_id=plot_id,
            geometry_hash=geometry_hash,
            geometry_version=geometry_version,
            run_id=run_id,
            daily_state=daily_state,
            state_uncertainty=state_uncertainty,
            validation_conflicts=validation_conflicts,
            scientific_publication_authorized=False,
            actuator_control_authorized=False,
            health_report={
                "kalman_available": True,
                "zones": list(daily_state.keys()),
                "days": len(provenance_log),
                "obs_days": sum(
                    1 for d in provenance_log
                    for zd in d.get("zones", {}).values()
                    if zd.get("provenance", {}).get("n_obs", 0) > 0
                ),
                "source_reliability": source_reliability,
                "audit": audit_report,
                "scientific_publication_authorized": False,
                "actuator_control_authorized": False,
            },
            provenance={
                "run_id": run_id,
                "start_date": start_date,
                "end_date": end_date,
                "run_timestamp": now.isoformat(),
                "engine": "Layer0StateEngine",
                "provenance_log": provenance_log,
                "scientific_publication_authorized": False,
                "actuator_control_authorized": False,
            },
        )

    # ================================================================
    # Packet-driven entrypoint (canonical Layer 0 contract)
    # ================================================================

    def run_from_packets(
        self,
        plot_id: str,
        packets: List[Any],
        start_date: str,
        end_date: str,
        soil_props: Optional[Dict[str, Any]] = None,
        zone_ids: Optional[List[str]] = None,
        run_timestamp: Optional[datetime] = None,
        geometry_hash: str = "",
        geometry_version: Optional[int] = None,
        positive_admission_receipts: Optional[Dict[str, Dict[str, Any]]] = None,
        tenant_id: str = "",
        scope_hash: str = "",
    ) -> Layer0StatePackage:
        """Run assimilation from ObservationPacket[] — the canonical entrypoint.

        Internally converts packets into daily_weather, observations_by_day,
        and events_by_day, then delegates to self.run().

        Args:
            plot_id: Plot identifier.
            packets: List[ObservationPacket] from all Layer 0 sources.
            start_date: YYYY-MM-DD start.
            end_date: YYYY-MM-DD end.
            soil_props: Soil texture properties.
            zone_ids: Extra zone IDs.
            run_timestamp: Injected timestamp for replay.
            geometry_hash: Geometry identity hash.
            geometry_version: Geometry version number.

        Returns:
            Layer0StatePackage.
        """
        from services.agribrain.layer0.observation_packet import ObservationSource, ObservationType

        # Reevaluate the server policy at the sensitive entrypoint, not only
        # in __init__: long-lived workers can receive a hardened deployment
        # configuration after an estimator instance was constructed.
        require_trusted_verifier(self._positive_observation_admission_verifier)
        require_trusted_delivery_verifier(self._verified_delivery_verifier)
        # The production authority gate already enforces the exact trusted
        # asymmetric-v3 verifier or a strict unified dispatcher. Do not
        # regress here to the legacy-only HMAC class: that would reject the
        # qualified B2B-06 KMS verifier at the real packet entrypoint.
        if signed_inputs_required():
            from services.agribrain.layer0.v3_kms_signed_issuer import (
                V3KmsGrantVerifier,
            )
            from services.agribrain.layer0.v3_state_admission import (
                UnifiedAdmissionVerifier,
            )
            if not isinstance(
                self._positive_observation_admission_verifier,
                (
                    PositiveObservationAdmissionVerifier,
                    V3KmsGrantVerifier,
                    UnifiedAdmissionVerifier,
                ),
            ):
                raise Layer0AdmissionRequiredError(
                    "Mandatory packet admission requires a trusted verifier"
                )

        # Mandatory live admission has its own trusted UTC run timestamp.
        # Caller-controlled historical timestamps cannot backdate receipt
        # validity or state publication history. Explicit trusted replay
        # requires a future separately authorized pathway.
        if signed_inputs_required():
            run_timestamp = datetime.now(timezone.utc)

        # B2B-05: Resolve tenant + exact geometry epoch independently from
        # the current plot authority store, not from a packet or caller digest.
        self._tenant_id = tenant_id
        strict_scope = (
            os.getenv("AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE", "").lower()
            in ("1", "true", "yes")
        )
        scoped_run = strict_scope or bool(tenant_id or scope_hash)
        verified_scope = None

        def resolve_current_scope():
            from services.agribrain.layer0.spatial_tenant_contract import (
                AuthenticatedPrincipal, ScopedPlotRequest, SpatialTenantDenied,
                authorize_plot_scope,
            )
            store = self._plot_ownership_store
            principal_provider = self._principal_provider
            if (
                not isinstance(tenant_id, str) or not tenant_id
                or not isinstance(scope_hash, str) or not scope_hash
                or not isinstance(geometry_hash, str) or not geometry_hash
                or type(geometry_version) is not int or geometry_version <= 0
                or not callable(getattr(store, "get_active_plot", None))
                or not callable(principal_provider)
            ):
                raise Layer0AdmissionRequiredError("trusted_plot_scope_required")
            try:
                principal = principal_provider()
                if not isinstance(principal, AuthenticatedPrincipal):
                    raise SpatialTenantDenied("principal_not_authenticated")
                current = authorize_plot_scope(
                    principal,
                    ScopedPlotRequest(
                        tenant_id, plot_id, geometry_hash, geometry_version,
                    ),
                    store.get_active_plot,
                )
                if current.scope_hash != scope_hash:
                    raise SpatialTenantDenied("scope_identity_mismatch")
                return current
            except Exception:
                raise Layer0AdmissionRequiredError("trusted_plot_scope_denied") from None

        if scoped_run:
            verified_scope = resolve_current_scope()

        daily_weather: Dict[str, Dict[str, Any]] = {}
        observations_by_day: Dict[str, Dict[str, List[Any]]] = {}
        events_by_day: Dict[str, List[Dict[str, Any]]] = {}

        excluded_counts = {
            "unavailable": 0,
            "simulated": 0,
            "fallback": 0,
            "skipped_proxy": 0,
            "skipped_diagnostic_only": 0,
            "skipped_non_production": 0,
            "skipped_non_provider": 0,
            "skipped_state_update_prohibited": 0,
            "skipped_observation_no_sigma": 0,
            "skipped_observation_nonfinite": 0,
            "skipped_observation_low_effective_quality": 0,
            "skipped_foreign_plot": 0,
            "skipped_foreign_tenant": 0,
            "skipped_unverified_spatial_scope": 0,
            "skipped_foreign_geometry": 0,
            "skipped_foreign_geometry_version": 0,
            "skipped_missing_positive_source_grant": 0,
            "skipped_invalid_positive_source_grant": 0,
            "skipped_unsupported_zone_in_run": 0,
            "skipped_duplicate_observation": 0,
        }
        filtered_packets = []
        signed_admitted_observation_digests: set[str] = set()
        signed_admitted_weather_digests: set[str] = set()
        # Only signatures proven AND materially consumed in state estimation
        # contribute to the immutable input manifest.
        signed_receipts_used: Dict[str, Dict[str, Any]] = {}
        signed_packet_by_digest: Dict[str, Any] = {}
        weather_field_sources: Dict[str, Dict[str, str]] = {}
        # Do not let the Kalman filter consume a multiset while the signed
        # manifest claims a unique receipt set. Staging and hashing share a
        # single canonical, versioned observation execution plan.
        staged_observation_updates: list[tuple[tuple[str, ...], str, str, Any, Dict[str, Any]]] = []
        seen_observation_updates: set[tuple[str, str, str, str]] = set()
        signed_evidence_decisions: dict[tuple[str, str, str], str] = {}

        def check_positive_grant(pkt: Any, purpose: str) -> tuple[bool, Optional[str]]:
            if self._positive_observation_admission_verifier is None:
                return True, None  # Explicit LEGACY_UNVERIFIED mode
            try:
                digest = observation_packet_digest(pkt)
                receipt = (positive_admission_receipts or {}).get(digest)
            except (ValueError, TypeError, AttributeError, OverflowError):
                excluded_counts["skipped_invalid_positive_source_grant"] += 1
                return False, None
            if receipt is None:
                excluded_counts["skipped_missing_positive_source_grant"] += 1
                return False, None
            # A caller-controlled or historical replay timestamp is NOT
            # a live security clock. Mandatory mode always verifies receipt
            # expiry and issuance against the backend's trusted UTC clock.
            # Replay authorization must use a separate audited capability.
            verification_now = (
                datetime.now(timezone.utc)
                if signed_inputs_required()
                else (run_timestamp or datetime.now(timezone.utc))
            )
            valid, _reason = self._positive_observation_admission_verifier.verify(
                receipt, pkt, plot_id=plot_id, geometry_hash=geometry_hash,
                geometry_version=geometry_version,
                run_timestamp=verification_now,
                purpose=purpose,
            )
            if not valid:
                excluded_counts["skipped_invalid_positive_source_grant"] += 1
                return False, None
            signed_packet_by_digest[digest] = pkt
            return True, digest

        for pkt in packets:
            # Explicitly contradictory identities must never enter weather,
            # event evidence or observation state. For legacy unbound
            # identities, do NOT silently claim a positive geometry grant.
            packet_plot = getattr(pkt, "plot_id", "") or ""
            packet_geometry = getattr(pkt, "geometry_hash", "") or ""
            packet_version = getattr(pkt, "geometry_version", None)

            # Caller-provided scope strings are NEVER enough. For a scoped
            # state run a current DB-backed authority has already been checked.
            # All scoped packets must be bound in-process by the spatial
            # verification path; raw/deserialized dictionaries are rejected.
            packet_tenant = getattr(pkt, "tenant_id", "") or ""
            packet_scope = getattr(pkt, "scope_hash", "") or ""
            spatial = getattr(pkt, "spatial_provenance", None) or {}
            if scoped_run:
                if packet_tenant and packet_tenant != tenant_id:
                    excluded_counts["skipped_foreign_tenant"] += 1
                    continue
                if (
                    packet_tenant != tenant_id or packet_scope != scope_hash
                    or not isinstance(spatial, dict)
                    or spatial.get("tenant_id") != tenant_id
                    or spatial.get("plot_id") != plot_id
                    or spatial.get("scope_hash") != scope_hash
                    or spatial.get("geometry_hash") != geometry_hash
                    or spatial.get("geometry_version") != geometry_version
                    or spatial.get("spatial_classification") != "FULL_CONTAINED"
                    or spatial.get("geometry_support_verified") is not True
                    or spatial.get("source_qualified") is not False
                    or spatial.get("eligible_for_state_grant") is not False
                    or spatial.get("authority") != "spatial_diagnostic_only"
                    or getattr(pkt, "_spatial_binding_verified", False) is not True
                    or not isinstance(getattr(pkt, "content_hash", None), str)
                    or pkt.content_hash != pkt._generate_content_hash()
                ):
                    excluded_counts["skipped_unverified_spatial_scope"] += 1
                    continue
            elif packet_tenant or packet_scope or spatial:
                # Unscoped state calls may still process old legacy packets,
                # but never silently treat scoped/claimed data as legacy input.
                excluded_counts["skipped_unverified_spatial_scope"] += 1
                continue
            if packet_plot and packet_plot != plot_id:
                excluded_counts["skipped_foreign_plot"] += 1
                continue
            if geometry_hash and packet_geometry != geometry_hash:
                excluded_counts["skipped_foreign_geometry"] += 1
                continue
            if geometry_version is not None and (
                type(packet_version) is not int
                or type(geometry_version) is not int
                or packet_version != geometry_version
            ):
                excluded_counts["skipped_foreign_geometry_version"] += 1
                continue
            status = getattr(pkt, "data_status", None)
            if status in (DataStatus.UNAVAILABLE, DataStatus.SIMULATED, DataStatus.FALLBACK):
                if status == DataStatus.UNAVAILABLE:
                    excluded_counts["unavailable"] += 1
                elif status == DataStatus.SIMULATED:
                    excluded_counts["simulated"] += 1
                elif status == DataStatus.FALLBACK:
                    excluded_counts["fallback"] += 1
                continue
            
            payload = getattr(pkt, "payload", {}) or {}
            if payload.get("source_reality") == "raster_composite_proxy":
                excluded_counts["skipped_proxy"] += 1
                continue
            if payload.get("diagnostic_only") is True:
                excluded_counts["skipped_diagnostic_only"] += 1
                continue
            if payload.get("production_usable") is False:
                excluded_counts["skipped_non_production"] += 1
                continue
            
            source_type = payload.get("source_type") or getattr(getattr(pkt, "source", None), "value", None) or str(getattr(pkt, "source", ""))
            is_admitted_plot_statistic = False
            if payload.get("source_reality") == "provider_daily_statistical_aggregate":
                from services.agribrain.layer0.temporal_evidence import is_admitted_temporal_record
                is_admitted_plot_statistic = is_admitted_temporal_record(payload)
            if (
                payload.get("real_provider_product") is False
                and not is_admitted_plot_statistic
                and source_type != "user_observation"
                and source_type != "user_event"
            ):
                excluded_counts["skipped_non_provider"] += 1
                continue

            filtered_packets.append(pkt)

        for pkt in filtered_packets:
            day = pkt.timestamp.strftime("%Y-%m-%d") if pkt.timestamp else ""
            if not day or not (start_date <= day <= end_date):
                # Do not count or root out-of-window evidence that cannot
                # affect the requested state trajectory.
                continue

            payload = pkt.payload or {}
            packet_type = payload.get("packet_type", "")

            # Weather forecast packets -> do not mix forecast with historical truth
            if pkt.source == ObservationSource.WEATHER_FORECAST:
                continue

            # Weather packets → daily_weather
            if pkt.source in (
                ObservationSource.WEATHER_REANALYSIS,
                ObservationSource.WEATHER_STATION,
                ObservationSource.NASA_POWER,
            ):
                # State-changing environmental forcing needs its own
                # positive WEATHER purpose. A signed NDVI/observation
                # receipt cannot authorize temperature/rain/ET inputs.
                authorized, signed_weather_digest = check_positive_grant(
                    pkt, WEATHER_GRANT_PURPOSE
                )
                if not authorized:
                    continue
                if day not in daily_weather:
                    daily_weather[day] = {}
                # Normalize weather aliases
                weather_aliases = {
                    "temperature_2m_max": "temp_max",
                    "temperature_2m_min": "temp_min",
                    "precipitation_sum": "precipitation",
                    "et0_fao_penman": "et0",
                }
                for src_key, dst_key in weather_aliases.items():
                    if src_key in payload:
                        daily_weather[day][dst_key] = payload[src_key]
                        if signed_weather_digest is not None:
                            weather_field_sources.setdefault(day, {})[dst_key] = signed_weather_digest
                # Merge weather fields directly, tracking only the final
                # contributing receipt for each actually used variable.
                for k in ("temp_max", "temp_min", "precipitation", "et0"):
                    if k in payload:
                        daily_weather[day][k] = payload[k]
                        if signed_weather_digest is not None:
                            weather_field_sources.setdefault(day, {})[k] = signed_weather_digest
                continue

            # Event packets → events_by_day
            if pkt.source in (
                ObservationSource.USER_EVENT,
                ObservationSource.SENSOR_IOT,
            ) and payload.get("event_type"):
                if day not in events_by_day:
                    events_by_day[day] = []
                # Transport evidence identity, scope, and occurrence time,
                # not just the untrusted inner payload. Never promote an
                # asserted role into a verified physical delivery.
                events_by_day[day].append({
                    "payload": dict(payload),
                    "packet_id": pkt.packet_id,
                    "content_hash": pkt.content_hash,
                    "source": pkt.source.value,
                    "timestamp": pkt.timestamp,
                    "plot_id": pkt.plot_id,
                    "geometry_hash": pkt.geometry_hash,
                    "geometry_version": pkt.geometry_version,
                })
                continue

            # Observation packets → convert to KalmanObservation
            if self._has_kalman and pkt.obs_type in (
                ObservationType.TABULAR,
                ObservationType.RASTER,
            ):
                # Try to extract kalman-compatible values
                if pkt.spatial_scope == "zone":
                    zone_id = payload.get("zone_id") or payload.get("zone") or "zone_unknown"
                    if (
                        self._positive_observation_admission_verifier is not None
                        and (not isinstance(zone_id, str) or zone_id not in (zone_ids or []))
                    ):
                        # A zone must be explicitly part of this caller-scoped
                        # estimation run even if it is registered elsewhere.
                        excluded_counts["skipped_unsupported_zone_in_run"] += 1
                        continue
                else:
                    zone_id = "plot"
                if day not in observations_by_day:
                    observations_by_day[day] = {}
                if zone_id not in observations_by_day[day]:
                    observations_by_day[day][zone_id] = []

                # Only explicitly admitted finite values with their own positive
                # measurement sigma can enter the filter; no synthetic 0.05 noise.
                if payload.get("state_update_allowed") is False or payload.get("spatial_scope_blocked") is True:
                    excluded_counts["skipped_state_update_prohibited"] += 1
                    continue

                # Carry the packet's *effective* QA × reliability influence,
                # rather than dropping scene quality when building a scalar
                # KalmanObservation. A zero-quality packet must not update
                # state even if its declared reliability and grants are true.
                if not any(payload.get(k) is not None for k in _PACKET_KALMAN_FIELDS):
                    continue

                # Packet claims are not authoritative. In strict mode the
                # trusted verifier requires an exact, detached, purpose-bound
                # grant for this particular observation.
                authorized, signed_packet_digest = check_positive_grant(
                    pkt, "kalman_state_observation"
                )
                if not authorized:
                    continue

                try:
                    effective_reliability = pkt.effective_weight()
                    if (
                        isinstance(effective_reliability, bool)
                        or not math.isfinite(float(effective_reliability))
                        or not (0.05 <= float(effective_reliability) <= 1.0)
                    ):
                        raise ValueError("no qualified effective influence")
                    effective_reliability = float(effective_reliability)
                except (AttributeError, ValueError, TypeError, OverflowError):
                    excluded_counts["skipped_observation_low_effective_quality"] += 1
                    continue

                sigmas = getattr(getattr(pkt, "uncertainty", None), "sigmas", None) or {}
                for var_key, (obs_type, sigma_key) in _PACKET_KALMAN_FIELDS.items():
                    value = payload.get(var_key)
                    if value is None:
                        continue
                    sigma_raw = sigmas.get(sigma_key)
                    if sigma_raw is None:
                        excluded_counts["skipped_observation_no_sigma"] += 1
                        continue

                    try:
                        if any(isinstance(x, bool) for x in (value, sigma_raw)):
                            raise ValueError("boolean is not numeric evidence")
                        obs_value = float(value)
                        obs_sigma = float(sigma_raw)
                        if not (
                            math.isfinite(obs_value) and math.isfinite(obs_sigma)
                            and obs_sigma > 0.0
                        ):
                            raise ValueError("invalid observation or own-variable sigma")
                    except (ValueError, TypeError, OverflowError):
                        excluded_counts["skipped_observation_nonfinite"] += 1
                        continue

                    obs = self._KalmanObservation(
                        obs_type=obs_type,
                        value=obs_value,
                        sigma=obs_sigma,
                        reliability=effective_reliability,
                        source=pkt.source.value,
                    )
                    # Digest is the exact signed packet bytes; neither a
                    # source name nor packet_id alone denotes independent
                    # physical evidence (packet_id is partly time-derived).
                    pkt_digest = signed_packet_digest
                    if pkt_digest is None:
                        try:
                            pkt_digest = observation_packet_digest(pkt)
                        except (ValueError, TypeError, AttributeError, OverflowError):
                            excluded_counts["skipped_observation_nonfinite"] += 1
                            continue
                    update_identity = (pkt_digest, day, zone_id, var_key)
                    if update_identity in seen_observation_updates:
                        excluded_counts["skipped_duplicate_observation"] += 1
                        continue
                    seen_observation_updates.add(update_identity)

                    # Once a provider has an independently minted immutable
                    # decision ID, reusing it with different signed content
                    # for the same observation slot is a hard conflict.
                    decision_id = payload.get("qualification_decision_id")
                    if signed_packet_digest is not None and decision_id is not None:
                        if not isinstance(decision_id, str) or not decision_id:
                            raise Layer0AdmissionRequiredError(
                                "Malformed signed qualification decision identity"
                            )
                        decision_key = (pkt.source.value, decision_id, var_key)
                        previous = signed_evidence_decisions.setdefault(
                            decision_key, pkt_digest
                        )
                        if previous != pkt_digest:
                            raise Layer0AdmissionRequiredError(
                                "Conflicting signed qualification identity in Layer 0 observation input"
                            )

                    # Normalize aware acquisition time before ordering;
                    # lexical sorting of different local UTC offsets is not
                    # a canonical temporal order.
                    timestamp_utc = (
                        pkt.timestamp.astimezone(timezone.utc).isoformat()
                        if pkt.timestamp.tzinfo is not None
                        and pkt.timestamp.utcoffset() is not None
                        else pkt.timestamp.isoformat()
                    )
                    update_record = {
                        "packet_digest": pkt_digest,
                        "day": day,
                        "zone_id": zone_id,
                        "timestamp": timestamp_utc,
                        "source": pkt.source.value,
                        "packet_field": var_key,
                        "model_type": obs_type,
                        "value": obs_value,
                        "sigma": obs_sigma,
                        "effective_reliability": effective_reliability,
                    }
                    # Same canonical order drives both numerical assimilation
                    # and the ordered manifest, independent of transport order.
                    order_key = (
                        day, zone_id, timestamp_utc,
                        pkt.source.value, pkt_digest, var_key,
                    )
                    staged_observation_updates.append(
                        (order_key, day, zone_id, obs, update_record)
                    )
                    if signed_packet_digest is not None:
                        signed_admitted_observation_digests.add(signed_packet_digest)
                        signed_receipts_used[signed_packet_digest] = {
                            "purpose": GRANT_PURPOSE,
                            "receipt": deepcopy(
                                (positive_admission_receipts or {})[signed_packet_digest]
                            ),
                        }

        staged_observation_updates.sort(key=lambda item: item[0])
        consumed_observation_updates: list[Dict[str, Any]] = []
        for _order, day, zone_id, obs, record in staged_observation_updates:
            observations_by_day.setdefault(day, {}).setdefault(zone_id, []).append(obs)
            if self._positive_observation_admission_verifier is not None:
                consumed_observation_updates.append(record)

        # Only complete, physically admissible weather days reach the
        # process model. Bind the final effective field provenance, not an
        # overridden or incomplete signed packet. Missing weather may still
        # lead to explicitly degraded state estimation.
        if self._positive_observation_admission_verifier is not None:
            from services.agribrain.layer0.kalman_engine import (
                _qualified_weather_for_prediction,
            )
            for weather_day, effective_fields in daily_weather.items():
                if _qualified_weather_for_prediction(effective_fields) is None:
                    continue
                owners = weather_field_sources.get(weather_day, {})
                for variable in ("temp_max", "temp_min", "precipitation", "et0"):
                    digest = owners.get(variable)
                    if digest is None:
                        continue
                    signed_admitted_weather_digests.add(digest)
                    signed_receipts_used[digest] = {
                        "purpose": WEATHER_GRANT_PURPOSE,
                        "receipt": deepcopy(
                            (positive_admission_receipts or {})[digest]
                        ),
                    }

        # Revalidate effective signed inputs at the end of preparation.
        # If a trusted revocation snapshot flips during this run, reject the
        # entire state build rather than mixing two policy revisions.
        verifier = self._positive_observation_admission_verifier
        stable_revision = (
            verifier.revocation_revision
            if verifier is not None and verifier.revocation_enforced and signed_receipts_used
            else None
        )
        stable_snapshot = (
            verifier.revocation_snapshot_digest
            if stable_revision is not None else None
        )

        def ensure_current_revocation_snapshot() -> None:
            if stable_revision is None:
                return
            for digest, entry in sorted(signed_receipts_used.items()):
                valid, _reason = verifier.verify(
                    entry["receipt"], signed_packet_by_digest[digest],
                    plot_id=plot_id, geometry_hash=geometry_hash,
                    geometry_version=geometry_version,
                    run_timestamp=(
                        datetime.now(timezone.utc)
                        if signed_inputs_required()
                        else (run_timestamp or datetime.now(timezone.utc))
                    ),
                    purpose=entry["purpose"],
                )
                if not valid:
                    raise Layer0AdmissionRequiredError(
                        "Issuer revocation changed or cannot be verified during state admission"
                    )
            if (
                verifier.revocation_revision != stable_revision
                or verifier.revocation_snapshot_digest != stable_snapshot
            ):
                raise Layer0AdmissionRequiredError(
                    "Issuer revocation revision changed during state admission"
                )

        # Fence both source revocation and live plot ownership before the
        # potentially long state run. A changed owner or geometry epoch denies.
        ensure_current_revocation_snapshot()
        if scoped_run and resolve_current_scope() != verified_scope:
            raise Layer0AdmissionRequiredError("plot_scope_changed_before_state")

        # Build state using the private capability granted only by the
        # packet entrypoint; direct scalar state calls remain unavailable
        # under production policy.
        state_pkg = self.run(
            plot_id=plot_id,
            start_date=start_date,
            end_date=end_date,
            daily_weather=daily_weather,
            observations_by_day=observations_by_day,
            events_by_day=events_by_day,
            soil_props=soil_props,
            zone_ids=zone_ids,
            run_timestamp=run_timestamp,
            geometry_hash=geometry_hash,
            geometry_version=geometry_version,
            **(
                {"_packet_run_capability": self.__packet_run_capability}
                if (signed_inputs_required() or scoped_run) else {}
            ),
        )

        # A source could be revoked during a long Kalman trajectory; do not
        # release a new state root after that revocation. Publishing still
        # requires the separate pilot gate's transactional source check.
        ensure_current_revocation_snapshot()
        if scoped_run and resolve_current_scope() != verified_scope:
            raise Layer0AdmissionRequiredError("plot_scope_changed_during_state")

        # Attach the source packets to the state package
        state_pkg.all_packets = list(packets)

        # Add diagnostic count for excluded packets
        if state_pkg.health_report is None:
            state_pkg.health_report = {}
        state_pkg.health_report["state_packets_excluded_by_status"] = excluded_counts
        state_pkg.health_report["b2b05_scope_mode"] = (
            "TRUSTED_ACTIVE_PLOT_SCOPE" if scoped_run else "LEGACY_UNSCOPED"
        )
        if scoped_run:
            state_pkg.health_report["b2b05_scope_hash"] = verified_scope.scope_hash
        state_pkg.health_report["positive_source_admission_mode"] = (
            "MANDATORY_SIGNED_STATE_INPUTS"
            if signed_inputs_required()
            else (
                "SIGNED_STATE_INPUTS"
                if self._positive_observation_admission_verifier is not None
                else "LEGACY_UNVERIFIED"
            )
        )
        state_pkg.health_report["positive_admitted_observation_digests"] = sorted(
            signed_admitted_observation_digests
        )
        state_pkg.health_report["positive_admitted_weather_digests"] = sorted(
            signed_admitted_weather_digests
        )
        # Input signatures authenticate a source statement; they do not
        # authorize a prescription, physical execution or pilot publication.
        # In particular, a prior-only estimate with zero signed inputs cannot
        # masquerade as scientifically qualified by its mere existence.
        signed_count = (
            len(signed_admitted_observation_digests)
            + len(signed_admitted_weather_digests)
        )
        state_pkg.health_report["signed_state_input_count"] = signed_count
        state_pkg.health_report["signed_state_input_present"] = (
            signed_count > 0
            and self._positive_observation_admission_verifier is not None
        )
        state_pkg.health_report["state_output_role"] = "STATE_ESTIMATE"
        state_pkg.health_report["scientific_publication_authorized"] = False
        state_pkg.health_report["issuer_revocation_mode"] = (
            "TRUSTED_LIVE_SNAPSHOT"
            if verifier is not None and verifier.revocation_enforced
            else "UNMANAGED"
        )
        state_pkg.health_report["zone_authority_configured"] = bool(
            verifier is not None and verifier.zone_authority_configured
        )

        # Bind the exact admitted proof statements, never unverified received
        # packet claims. Do not include signing *secrets*; grant+MAC is a
        # public verifiable statement whose integrity is checked upstream.
        # This is not a signed pilot publication receipt and cannot by
        # itself authorize downstream prescriptions.
        if self._positive_observation_admission_verifier is not None:
            input_manifest = {
                "domain": "akaloris/layer0/verified-state-input-manifest/v2",
                "observation_execution_policy": "canonical-utc-source-digest-field/v1",
                "ordered_observation_updates": consumed_observation_updates,
                "plot_id": plot_id,
                "geometry_hash": geometry_hash,
                "geometry_version": geometry_version,
                "window": [start_date, end_date],
                "issuer_revocation_anchor": (
                    {
                        "revision": verifier.revocation_revision,
                        "snapshot_digest": verifier.revocation_snapshot_digest,
                    }
                    if verifier.revocation_enforced else None
                ),
                "admitted_receipts": [
                    {"packet_digest": digest, **signed_receipts_used[digest]}
                    for digest in sorted(signed_receipts_used)
                ],
                "effective_weather_field_sources": {
                    day: {field: digest for field, digest in sorted(owners.items())}
                    for day, owners in sorted(weather_field_sources.items())
                    if _qualified_weather_for_prediction(
                        daily_weather.get(day, {})
                    ) is not None
                },
            }
            if not isinstance(getattr(state_pkg, "provenance", None), dict):
                state_pkg.provenance = {}
            state_pkg.provenance["positive_state_input_manifest"] = input_manifest
            state_pkg.input_hash = hashlib.sha256(
                _canonical_bytes(input_manifest)
            ).hexdigest()
            state_pkg.health_report["signed_input_manifest_hash"] = (
                state_pkg.input_hash
            )

        # Sealing MUST follow every mutation of the material health report.
        # The earlier order recomputed output_hash before appending these
        # counts, so the published digest was stale even with no new data.
        state_pkg.output_hash = state_pkg._generate_output_hash()

        return state_pkg
