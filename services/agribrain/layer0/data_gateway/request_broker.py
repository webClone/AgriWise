"""
DataRequestBroker — The SINGLE entry point for ALL data in AgriBrain.

Every data request from every layer goes through this broker.
No layer, no engine, no runtime may fetch data independently.

The broker:
  1. Checks the StorageManager (MongoDB → filesystem fallback)
  2. If miss: checks RequestConsolidator for spatial batching
  3. Fetches via FetchRegistry (the ONLY place with eo.* imports)
  4. Stores result with adaptive TTL
  5. Promotes to observation archive (warm tier)
  6. Records metrics (hit/miss/latency)
  7. Routes user data through UserDataEngine

Usage from ANY layer:
    from services.agribrain.layer0.data_gateway import broker

    # Single source
    weather = broker.get("openweather_current", plot_id="abc", lat=33.5, lng=-7.6)

    # Bulk fetch (parallel)
    data = broker.get_bulk(["openweather_current", "sentinel2_indices", "soilgrids"],
                           plot_id="abc", lat=33.5, lng=-7.6)

    # User data
    broker.ingest_user_data("user_irrigation_event", "abc", 33.5, -7.6,
                            {"amount_mm": 25, "method": "drip"})

    # Freshness check
    report = broker.freshness("abc")

    # Admin
    stats = broker.stats()
"""

from __future__ import annotations

import time
import logging
import copy
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from services.agribrain.layer0.data_gateway.storage_manager import StorageManager
from services.agribrain.layer0.data_gateway.fetch_registry import get_fetch_fn, is_fetchable
from services.agribrain.layer0.data_gateway.request_consolidator import RequestConsolidator
from services.agribrain.layer0.data_gateway.user_data_engine import UserDataEngine
from services.agribrain.layer0.data_gateway.metrics import metrics
from services.agribrain.layer0.data_gateway.network_circuit_breaker import (
    ExternalProviderCircuitOpen,
    external_provider_circuit,
)

from services.agribrain.layer0.spatial_tenant_contract import (
    AuthenticatedPrincipal, ScopedPlotRequest, SpatialTenantDenied,
    authorize_plot_scope,
)
from services.agribrain.layer0.plot_ownership_store import PlotOwnershipStore

logger = logging.getLogger("agribrain.gateway.broker")

# Thread pool for parallel bulk fetches
_POOL_TIMEOUT = 35  # seconds (matches pi_helpers)
_MAX_WORKERS = 8


def _has_usable_provider_data(result: Any) -> bool:
    if result is None:
        return False
    if isinstance(result, dict):
        if not result:
            return False
        collection_keys = ("data", "timeseries", "records", "series", "values")
        present_collections = [result.get(key) for key in collection_keys if key in result]
        if present_collections and not any(bool(value) for value in present_collections):
            return False
    return True


def _temporal_candidate_valid(result: Any, expected_contract: str) -> bool:
    return bool(
        isinstance(result, dict)
        and result.get("temporal_evidence_contract_version") == expected_contract
        and _has_usable_provider_data(result)
    )


def _raster_candidate_valid(result: Any, expected_contract: str) -> bool:
    """Require a complete, explicitly authorized provider-raster contract.

    Raster composites are allowed to drive browser pixels only when their
    provider reality survived acquisition and cache rehydration.  Treating an
    old cache object with missing authority fields as current would silently
    turn a real raster into an unrenderable, unknown-grounding surface.
    """
    if not isinstance(result, dict):
        return False
    values = result.get("values")
    valid_mask = result.get("valid_mask")
    if not isinstance(values, list) or not values:
        return False
    if not isinstance(valid_mask, list) or len(valid_mask) != len(values):
        return False
    width = result.get("width")
    height = result.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return False
    if height != len(values) or height <= 0 or width <= 0:
        return False
    if any(not isinstance(row, list) or len(row) != width for row in values):
        return False
    if any(not isinstance(row, list) or len(row) != width for row in valid_mask):
        return False
    return bool(
        result.get("raster_contract_version") == expected_contract
        and result.get("truth_class") == "provider_derived_composite"
        and result.get("source_reality") == "provider_temporal_composite_raster"
        and result.get("real_provider_product") is True
        and result.get("production_usable") is True
        and result.get("diagnostic_only") is False
        and int(result.get("valid_pixel_count") or 0) > 0
        and isinstance(result.get("grid_spec"), dict)
    )


def _latest_observation_at(result: Dict[str, Any]) -> Optional[str]:
    records = result.get("data") or result.get("timeseries") or result.get("records") or []
    if not isinstance(records, list):
        return None
    timestamps = []
    for record in records:
        if not isinstance(record, dict):
            continue
        value = record.get("acquired_at") or record.get("timestamp") or record.get("date")
        if value:
            timestamps.append(str(value))
    return max(timestamps) if timestamps else None


def _source_snapshot_id(source: str, result: Dict[str, Any]) -> str:
    try:
        canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        canonical = repr(result)
    return f"{source}:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:20]}"


def _with_refresh_state(
    result: Dict[str, Any],
    *,
    source: str,
    status: str,
    refresh_attempted_at: str,
    refresh_failure: Optional[str] = None,
) -> Dict[str, Any]:
    annotated = copy.deepcopy(result)
    last_observation = _latest_observation_at(annotated)
    age_seconds: Optional[float] = None
    if last_observation:
        try:
            parsed = datetime.fromisoformat(last_observation.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age_seconds = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())
        except ValueError:
            pass
    snapshot_id = _source_snapshot_id(source, annotated)
    gateway_state = {
        "status": status,
        "source_snapshot_id": snapshot_id,
        "last_successful_observation_at": last_observation,
        "refresh_attempted_at": refresh_attempted_at,
        "refresh_status": "failed" if refresh_failure else "succeeded",
        "refresh_failed": bool(refresh_failure),
        "refresh_failure": refresh_failure,
        "served_from": "last_known_good" if status == "stale_available" else "live_provider",
        "data_age_seconds": age_seconds,
        "data_age_days": (age_seconds / 86400.0) if age_seconds is not None else None,
        **external_provider_circuit.state(),
    }
    annotated["gateway_evidence_state"] = gateway_state
    annotated["source_snapshot_id"] = snapshot_id
    annotated["last_successful_observation_at"] = last_observation
    annotated["refresh_attempted_at"] = refresh_attempted_at
    annotated["refresh_status"] = gateway_state["refresh_status"]
    annotated["data_age"] = gateway_state["data_age_seconds"]
    return annotated


class DataRequestBroker:
    """The centralized data request broker for AgriBrain.

    This is the public API that all layers use to get data.
    It orchestrates the full data flow:

        Request → Cache check → Consolidate → Fetch → Store → Promote → Return

    Universal guarantee: no external API call is made if fresh data exists.
    """

    def __init__(self):
        self._storage = StorageManager()
        self._consolidator = RequestConsolidator()
        self._user_engine = UserDataEngine(self._storage)
        self._plot_ownership_store: Optional[PlotOwnershipStore] = None
        self._principal_provider: Optional[Callable[[], AuthenticatedPrincipal]] = None
        logger.info("[BROKER] DataRequestBroker initialized")

    def configure_plot_authority(
        self,
        store: PlotOwnershipStore,
        principal_provider: Callable[[], AuthenticatedPrincipal],
    ) -> None:
        """Install a trusted datastore and middleware-authenticated identity."""
        if not callable(getattr(store, "get_active_plot", None)) or not callable(principal_provider):
            raise TypeError("trusted_plot_authority_provider_required")
        self._plot_ownership_store = store
        self._principal_provider = principal_provider

    def _admit_scoped_plot(
        self, plot_id: str, lat: float, lng: float,
        plot_scope: Optional[ScopedPlotRequest],
    ):
        """Enforce positive plot authorization BEFORE any cache or provider call."""
        strict = os.getenv("AKALORIS_LAYER0_REQUIRE_PLOT_SCOPE", "").lower() in ("1", "true", "yes")
        if not strict and plot_scope is None:
            return None  # Legacy compatibility. NEVER a scoped grant.
        store = getattr(self, "_plot_ownership_store", None)
        provider = getattr(self, "_principal_provider", None)
        if (
            not isinstance(plot_scope, ScopedPlotRequest)
            or plot_scope.plot_id != plot_id
            or not callable(getattr(store, "get_active_plot", None))
            or not callable(provider)
        ):
            raise SpatialTenantDenied("plot_scope_required")
        try:
            scope = authorize_plot_scope(provider(), plot_scope, store.get_active_plot)
            from shapely.geometry import Point, shape
            import math
            if (
                isinstance(lat, bool) or isinstance(lng, bool)
                or not math.isfinite(float(lat)) or not math.isfinite(float(lng))
                or not shape(json.loads(scope.geometry_json)).covers(Point(float(lng), float(lat)))
            ):
                raise SpatialTenantDenied("request_coordinate_outside_plot")
            return scope
        except SpatialTenantDenied:
            raise
        except Exception:
            raise SpatialTenantDenied("plot_scope_denied") from None

    # ── Primary API ────────────────────────────────────────────────

    def get(
        self,
        source: str,
        plot_id: str,
        lat: float,
        lng: float,
        force_refresh: bool = False,
        context: Optional[Dict] = None,
        *,
        plot_scope: Optional[ScopedPlotRequest] = None,
        **kwargs,
    ) -> Optional[Any]:
        """Get data for a single source.

        This is the main entry point. Layers call this instead of
        importing fetch functions directly.

        Args:
            source: Source identifier (e.g., "openweather_current")
            plot_id: Plot identifier
            lat, lng: Coordinates
            force_refresh: Skip cache
            context: TTL context (phenology_stage, anomaly_score, etc.)
            **kwargs: Extra args passed to fetch function

        Returns:
            Data dict or None on failure.
        """
        try:
            verified_scope = self._admit_scoped_plot(plot_id, lat, lng, plot_scope)
        except SpatialTenantDenied:
            logger.warning("[BROKER] Scoped plot admission denied")
            return None
        storage_plot_id = "b2b05_" + verified_scope.scope_hash if verified_scope else plot_id

        # Get the fetch function from the registry
        fetch_fn = get_fetch_fn(source)
        if fetch_fn is None:
            logger.warning("[BROKER] No fetch function for source: %s", source)
            return None

        # W4-07: In strict native weather mode, check evidence root at broker entry BEFORE storage lookup
        strict_native = os.getenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "").lower() in ("1", "true", "yes")
        weather_root = (
            os.getenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", "").strip()
            or os.getenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", "").strip()
        )
        if source == "open_meteo_archive" and strict_native and not weather_root:
            logger.warning("[BROKER] Strict native weather mode enabled but evidence root missing at entry")
            return None

        # Compute a deterministic param_hash from extra kwargs to differentiate cache keys
        param_hash = ""
        if kwargs:
            try:
                # Handle nested dicts/lists safely
                def serialize(v):
                    if isinstance(v, dict):
                        return sorted((k, serialize(val)) for k, val in v.items())
                    elif isinstance(v, list):
                        return [serialize(x) for x in v]
                    return v
                raw = repr(serialize(kwargs)).encode("utf-8")
                param_hash = hashlib.sha256(raw).hexdigest()[:12]
            except Exception:
                try:
                    raw = repr(sorted(kwargs.items())).encode("utf-8")
                    param_hash = hashlib.sha256(raw).hexdigest()[:12]
                except Exception:
                    pass

        if verified_scope is not None:
            # Tenant, plot and exact geometry epoch isolate both cache tiers
            # and spatial request consolidation, even at identical coordinates.
            param_hash = hashlib.sha256(
                (param_hash + "|" + verified_scope.scope_hash).encode("utf-8")
            ).hexdigest()

        # Build a fetch wrapper that handles consolidation
        call_kwargs = {"plot_id": plot_id, **kwargs}
        if self._consolidator.should_consolidate(source) and not force_refresh:
            consolidated_fn = self._make_consolidated_fetch(
                source, fetch_fn, lat, lng, storage_plot_id, param_hash=param_hash, **kwargs
            )
        else:
            # Direct fetch (fine-resolution or force refresh)
            def consolidated_fn(lat_arg, lng_arg, **kw):
                return fetch_fn(lat_arg, lng_arg, **{**call_kwargs, **kw})

        temporal_contracts = {
            "sentinel2_ndvi_ts": "s2_daily_plot_statistic_v1",
            "sentinel1_sar_ts": "s1_daily_plot_statistic_v1",
        }
        expected_contract = temporal_contracts.get(source)
        expected_raster_contract = (
            str(kwargs.get("raster_contract_version") or "")
            if source in {
                "raster_composite_ndvi",
                "raster_composite_ndmi",
                "raster_composite_sar",
                "raster_quality_mask",
            }
            else ""
        )
        retained_evidence = None
        refresh_attempted_at = None
        if expected_contract:
            # Capture even an expired record before the normal TTL read. This
            # prevents a failed provider refresh from erasing the rollback
            # source on disk or making it unreachable in MongoDB.
            retained_evidence = self._storage.get_cached_evidence(
                source, storage_plot_id, lat, lng, param_hash,
            )
            if retained_evidence is not None:
                external_provider_circuit.record_cache_available()
            if force_refresh:
                refresh_attempted_at = datetime.now(timezone.utc).isoformat()

        provider_fetch = consolidated_fn

        def guarded_fetch(lat_arg, lng_arg, **kw):
            external_provider_circuit.before_request(source)
            try:
                fetched = provider_fetch(lat_arg, lng_arg, **kw)
            except ExternalProviderCircuitOpen:
                raise
            except Exception as error:
                external_provider_circuit.record_failure(error, source)
                raise
            if _has_usable_provider_data(fetched):
                external_provider_circuit.record_success(source)
            return fetched

        # Use StorageManager for cache-through
        result = self._storage.get_or_fetch(
            source=source,
            plot_id=storage_plot_id,
            lat=lat,
            lng=lng,
            fetch_fn=guarded_fetch,
            force_refresh=force_refresh,
            context=context,
            param_hash=param_hash,
            candidate_validator=(
                (lambda value: _temporal_candidate_valid(value, expected_contract))
                if expected_contract
                else (
                    lambda value: _raster_candidate_valid(
                        value, expected_raster_contract
                    )
                )
                if expected_raster_contract
                else None
            ),
        )

        # Native weather cache items must re-verify their CAS parent before
        # return. Old EO cache records or arbitrary ID strings cannot inherit
        # native weather provenance merely because they are cached.
        weather_root = (
            os.getenv("AKALORIS_LAYER0_NATIVE_WEATHER_EVIDENCE_ROOT", "").strip()
            or os.getenv("AKALORIS_LAYER0_NATIVE_EVIDENCE_ROOT", "").strip()
        )
        strict_native = os.getenv("AKALORIS_LAYER0_REQUIRE_NATIVE_EVIDENCE", "").lower() in ("1", "true", "yes")

        if source == "open_meteo_archive":
            if strict_native and not weather_root:
                # In strict mode, absence of evidence root fails closed across cache and provider
                return None

            if weather_root:
                from services.agribrain.layer0.native_issuer.weather_native_pipeline import (
                    resolve_verified_open_meteo_payload,
                )

                def native_candidate_valid(value):
                    if not isinstance(value, dict):
                        return False
                    try:
                        resolve_verified_open_meteo_payload(
                            value, latitude=lat, longitude=lng,
                        )
                        return True
                    except (ValueError, TypeError, OSError, KeyError):
                        return False

                if not native_candidate_valid(result):
                    if result is not None and not force_refresh:
                        result = self._storage.get_or_fetch(
                            source=source, plot_id=storage_plot_id, lat=lat, lng=lng,
                            fetch_fn=guarded_fetch, force_refresh=True,
                            context=context, param_hash=param_hash,
                            candidate_validator=native_candidate_valid,
                        )
                    if not native_candidate_valid(result):
                        return None

            if strict_native:
                # Enforce strict-native verification at the broker boundary:
                # Cache hits must be verified native QA, never unattested legacy.
                if not isinstance(result, dict) or result.get("native_capture_status") != "screened_native_qa":
                    return None

        # Storage validators protect fetched candidates, but cache reads occur
        # before candidate validation.  Refresh metadata-poor legacy raster
        # entries once and fail closed if the provider cannot produce a valid
        # replacement; never return them as current-contract evidence.
        if (
            expected_raster_contract
            and not _raster_candidate_valid(result, expected_raster_contract)
        ):
            if result is not None and not force_refresh:
                logger.info(
                    "[BROKER] Refreshing stale raster authority contract for %s/%s",
                    plot_id[:8],
                    source,
                )
                result = self._storage.get_or_fetch(
                    source=source,
                    plot_id=plot_id,
                    lat=lat,
                    lng=lng,
                    fetch_fn=guarded_fetch,
                    force_refresh=True,
                    context=context,
                    param_hash=param_hash,
                    candidate_validator=lambda value: _raster_candidate_valid(
                        value, expected_raster_contract
                    ),
                )
            if not _raster_candidate_valid(result, expected_raster_contract):
                return None

        if expected_contract and result is None and isinstance(retained_evidence, dict):
            circuit_state = external_provider_circuit.state()
            return _with_refresh_state(
                retained_evidence,
                source=source,
                status="stale_available",
                refresh_attempted_at=refresh_attempted_at or datetime.now(timezone.utc).isoformat(),
                refresh_failure=(
                    "network_dns_unavailable"
                    if circuit_state.get("circuit_open")
                    else "provider_refresh_failed_or_candidate_invalid"
                ),
            )
        if (
            expected_contract
            and not force_refresh
            and isinstance(result, dict)
            and result.get("temporal_evidence_contract_version") != expected_contract
        ):
            stale_result = result
            refresh_attempted_at = datetime.now(timezone.utc).isoformat()
            external_provider_circuit.record_cache_available()
            logger.info(
                "[BROKER] Refreshing stale temporal contract non-destructively for %s/%s",
                plot_id[:8],
                source,
            )
            candidate = self._storage.get_or_fetch(
                source=source,
                plot_id=plot_id,
                lat=lat,
                lng=lng,
                fetch_fn=guarded_fetch,
                force_refresh=True,
                context=context,
                param_hash=param_hash,
                candidate_validator=lambda value: _temporal_candidate_valid(value, expected_contract),
            )
            if _temporal_candidate_valid(candidate, expected_contract):
                result = _with_refresh_state(
                    candidate,
                    source=source,
                    status="live",
                    refresh_attempted_at=refresh_attempted_at,
                )
            else:
                circuit_state = external_provider_circuit.state()
                failure = (
                    "network_dns_unavailable"
                    if circuit_state.get("circuit_open")
                    else "provider_refresh_failed_or_candidate_invalid"
                )
                logger.warning(
                    "[BROKER] Temporal refresh failed for %s/%s; serving last-known-good evidence",
                    plot_id[:8],
                    source,
                )
                result = _with_refresh_state(
                    stale_result,
                    source=source,
                    status="stale_available",
                    refresh_attempted_at=refresh_attempted_at,
                    refresh_failure=failure,
                )
        return result

    def get_bulk(
        self,
        sources: List[str],
        plot_id: str,
        lat: float,
        lng: float,
        force_refresh: bool = False,
        context: Optional[Dict] = None,
        extra_args: Optional[Dict[str, Dict]] = None,
        *,
        plot_scope: Optional[ScopedPlotRequest] = None,
    ) -> Dict[str, Any]:
        """Get data for multiple sources in parallel.

        Replaces the parallel ThreadPoolExecutor pattern in pi_helpers.
        Each source is fetched through get() with cache-through.

        Args:
            sources: List of source identifiers
            plot_id: Plot identifier
            lat, lng: Coordinates
            force_refresh: Skip cache for all sources
            context: TTL context
            extra_args: Per-source extra kwargs, e.g., {"sentinel2_ndvi_ts": {"days": 180}}

        Returns:
            Dict[source_name, data_or_None]
        """
        extra = extra_args or {}
        results: Dict[str, Any] = {}

        def _fetch_one(src: str) -> tuple:
            try:
                kw = extra.get(src, {})
                data = self.get(
                    source=src,
                    plot_id=plot_id,
                    lat=lat,
                    lng=lng,
                    force_refresh=force_refresh,
                    context=context,
                    plot_scope=plot_scope,
                    **kw,
                )
                return src, data
            except Exception as e:
                logger.error("[BROKER] Bulk fetch error for %s: %s", src, e)
                return src, None

        # Run in parallel
        pool = ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(sources)))
        futures = {pool.submit(copy_context().run, _fetch_one, s): s for s in sources}

        try:
            for fut in as_completed(futures, timeout=_POOL_TIMEOUT):
                src, data = fut.result()
                results[src] = data
        except TimeoutError:
            # Collect what we have, None for the rest
            for f in futures:
                src = futures[f]
                if src not in results:
                    if f.done():
                        try:
                            s, d = f.result(timeout=0)
                            results[s] = d
                        except Exception:
                            results[src] = None
                    else:
                        results[src] = None
            logger.warning(
                "[BROKER] Bulk timeout: %d/%d sources returned",
                sum(1 for v in results.values() if v is not None),
                len(sources),
            )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        return results

    # ── User Data API ──────────────────────────────────────────────

    def ingest_user_data(
        self,
        source_type: str,
        plot_id: str,
        lat: float,
        lng: float,
        data: Dict,
    ) -> bool:
        """Ingest user-contributed data through the gateway.

        Dispatches to the appropriate UserDataEngine method.
        """
        method_map = {
            "user_soil_analysis": self._user_engine.ingest_soil_analysis,
            "user_irrigation_event": self._user_engine.ingest_irrigation,
            "user_fertilization_event": self._user_engine.ingest_fertilization,
            "user_planting_event": self._user_engine.ingest_planting,
            "user_harvest_event": self._user_engine.ingest_harvest,
            "user_yield_report": self._user_engine.ingest_yield_report,
            "user_photo": self._user_engine.ingest_photo,
            "user_agronomist_note": self._user_engine.ingest_agronomist_note,
            "user_lab_result": self._user_engine.ingest_lab_result,
            "user_management_event": self._user_engine.ingest_management_event,
            "sensor_reading": self._user_engine.ingest_sensor_reading,
            "drone_survey": self._user_engine.ingest_drone_data,
            "camera_capture": self._user_engine.ingest_camera_capture,
        }

        handler = method_map.get(source_type)
        if handler is None:
            logger.warning("[BROKER] Unknown user data type: %s", source_type)
            return False

        return handler(plot_id, lat, lng, data)

    # ── Freshness API ──────────────────────────────────────────────

    def freshness(
        self, plot_id: str, sources: Optional[List[str]] = None,
    ) -> Dict:
        """Get per-source freshness report for a plot.

        Returns cache age, TTL remaining, and freshness % for each source.
        No fetching is triggered.
        """
        report = self._storage.get_freshness_report(plot_id, sources)
        return {name: entry.to_dict() for name, entry in report.items()}

    # ── Cache Management ───────────────────────────────────────────

    def invalidate(self, plot_id: str, source: Optional[str] = None) -> int:
        """Force-invalidate cache entries for a plot."""
        return self._storage.invalidate(plot_id, source)

    def invalidate_all_plots(self, source: str) -> int:
        """Invalidate all cache entries for a specific source across all plots."""
        # This is a broader invalidation — useful for API key changes etc.
        return self._storage._fs_fallback.invalidate(source)

    # ── Archive Query ──────────────────────────────────────────────

    def query_archive(
        self,
        plot_id: str,
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict]:
        """Query the warm-tier observation archive.

        Used by ML patterns, DNA recalibration, and yield analysis.
        """
        return self._storage.query_archive(
            plot_id, source=source,
            start_date=start_date, end_date=end_date,
            limit=limit,
        )

    # ── Admin / Diagnostics ────────────────────────────────────────

    def stats(self) -> Dict:
        """Get comprehensive gateway statistics."""
        return {
            "broker": "active",
            "storage": self._storage.get_stats(),
            "consolidator": self._consolidator.get_stats(),
            "user_data": self._user_engine.get_stats(),
            "source_metrics": metrics.get_all_source_stats(),
            "global_metrics": metrics.get_global_summary(),
            "external_provider_circuit": external_provider_circuit.state(),
        }

    def ttl_breakdown(
        self, source: str, plot_id: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Get detailed TTL factor breakdown for a source + plot."""
        return self._storage.ttl_engine.get_factor_breakdown(
            source, plot_id, context
        )

    @property
    def storage(self) -> StorageManager:
        """Direct access to storage manager for advanced queries."""
        return self._storage

    @property
    def consolidator(self) -> RequestConsolidator:
        """Direct access to consolidator for tuning."""
        return self._consolidator

    @property
    def user_engine(self) -> UserDataEngine:
        """Direct access to user data engine."""
        return self._user_engine

    # ── Internal: Consolidated Fetch ───────────────────────────────

    def _make_consolidated_fetch(
        self,
        source: str,
        fetch_fn: Callable,
        lat: float,
        lng: float,
        plot_id: str,
        param_hash: str = "",
        **kwargs,
    ) -> Callable:
        """Create a fetch function that uses spatial batching.

        If another plot in the same ~5km grid cell already fetched
        this source recently, return the cached batch result.
        """
        batch = self._consolidator.get_or_create_batch(
            source, lat, lng, plot_id, param_hash=param_hash, **kwargs
        )

        def _consolidated_fetch(lat_arg, lng_arg, **kw):
            # If batch already has result, return it
            if batch.is_fetched and batch.result is not None:
                return batch.result

            # This request is the first — do the actual fetch
            if not batch.is_fetching:
                batch.is_fetching = True
                try:
                    result = fetch_fn(lat_arg, lng_arg, **{**kwargs, **kw})
                    self._consolidator.complete_batch(batch, result)
                    return result
                except Exception as e:
                    self._consolidator.complete_batch(batch, None, str(e))
                    raise
            else:
                # Another thread is fetching — wait briefly, then return
                # whatever is available (or None)
                import time as _time
                for _ in range(10):
                    _time.sleep(0.1)
                    if batch.is_fetched:
                        return batch.result
                return batch.result

        return _consolidated_fetch
