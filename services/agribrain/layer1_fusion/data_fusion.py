"""
Layer 1.1: Multi-Source Data Fusion Engine (Production Spec)
Implements the 8-Step Fusion Pipeline with Evidence Validation.
Supports degradation to Pure Python if Pandas/Numpy are missing.

.. deprecated::
    This module is DEPRECATED. Use `layer1_fusion.engine.Layer1FusionEngine`
    (the V1 contract-driven pipeline) instead. This legacy engine remains for
    backward compatibility only and will be removed in a future release.
"""

import warnings
warnings.warn(
    "layer1_fusion.data_fusion is DEPRECATED. "
    "Use layer1_fusion.engine.Layer1FusionEngine instead. "
    "This legacy module will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path
import hashlib  # deterministic IDs / noise
import random  # kept, but we will make spatial noise deterministic

# Fix path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try imports
try:
    import numpy as np
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    np = None
    pd = None

try:
    # Data fetching now goes through the Data Gateway broker
    from layer0.data_gateway import broker as _gateway_broker
    def fetch_ndvi_timeseries(lat, lng, days=180, **kw):
        return _gateway_broker.get("sentinel2_ndvi_ts", "", lat, lng, days=days) or {}
    def fetch_sar_timeseries(lat, lng, days=30, **kw):
        return _gateway_broker.get("sentinel1_sar_ts", "", lat, lng, days=days) or {}
    def fetch_historical_weather(lat, lng, start_date="", end_date="", **kw):
        return _gateway_broker.get("open_meteo_archive", "", lat, lng, start_date=start_date, end_date=end_date) or {}
    def fetch_soil_properties(lat, lng, **kw):
        return _gateway_broker.get("soilgrids", "", lat, lng) or {}
    def fetch_openweather_forecast(lat, lng, **kw):
        return _gateway_broker.get("openweather_forecast", "", lat, lng) or {}
    from layer1_fusion.corrections import correction_engine
    from layer1_fusion.schema import (
        FieldTensor, EvidenceItem, EvidenceSourceType,
        ValidationStatus, FusionOutput, FieldTensorChannels
    )
    from layer1_fusion.raster_backend import TileStoreBackend, RasterioBackend
    from layer1_fusion.validation.validator import trust_system
except ImportError:
    # Fallback for linting or missing optional modules
    fetch_ndvi_timeseries = lambda *args, **kwargs: {}
    fetch_sar_timeseries = lambda *args, **kwargs: {}
    fetch_historical_weather = lambda *args, **kwargs: {}
    fetch_soil_properties = lambda *args, **kwargs: {}
    fetch_openweather_forecast = lambda *args, **kwargs: {}
    correction_engine = None
    trust_system = None

# Layer 0: Data Assimilation Engine
try:
    from layer0.kalman_engine import (
        DailyAssimilationEngine, KalmanObservation
    )
    from layer0.validation_graph import ValidationGraph
    from layer0.monitoring import run_audit as layer0_audit
    from layer0.invariants import enforce_all_invariants
    from layer0.state_persistence import save_engine_state
    HAS_LAYER0 = True
except ImportError:
    HAS_LAYER0 = False


class DataFusionEngine:
    """
    Production Pipeline with Fallback.
    """

    def __init__(self, use_modern_layer0_state_engine: bool = True, allow_legacy_layer0_fallback: bool = True):
        # NOTE: resolution must be produced by backend in meters (projected CRS).
        # Keep attribute for backwards compatibility, but we don't use it as a CRS unit anymore.
        self.DEFAULT_GRID_RES = None
        self.use_modern_layer0_state_engine = use_modern_layer0_state_engine
        self.allow_legacy_layer0_fallback = allow_legacy_layer0_fallback

    def fuse_data(
        self,
        plot_id: str,
        lat: float,
        lng: float,
        start_date: str,
        end_date: str,
        polygon_coords: Optional[list] = None,
        user_evidence: Optional[list] = None
    ) -> FusionOutput:

        # --- Step 0: Initialize Provenance ---
        # Deterministic Run ID
        from layer1_fusion.provenance import ProvenanceTracker, generate_run_id

        # Hash params + inputs (simplification for MVP: just timestamps)
        run_id = generate_run_id(plot_id, start_date, end_date, "params_v1", "code_v2.0.0")

        tracker = ProvenanceTracker(run_id)
        tracker.log_event("START_RUN", metadata={"plot_id": plot_id, "start": start_date, "end": end_date})

        mode = "Pandas" if HAS_PANDAS else "PurePython"
        print(f"[SYNC] [Layer 1] Starting Production Fusion Run: {run_id} ({mode} Mode)")

        # --- Step 1: Acquire Evidence (Catalog) ---
        evidence_pool, acquisition_snapshot = self._acquire_all_evidence(lat, lng, start_date, end_date, polygon_coords)
        
        # --- Step 1.5: Perception Adapter (Layer 0 Handoff) ---
        perception_bundle = None
        try:
            from layer1_fusion.perception_adapter import build_perception_bundle, ObservationSourceType as PObsSource
            
            # Separate user evidence into typed buckets for the perception adapter
            raw_photos = []
            raw_soil = []
            raw_sensors = []
            for item in (user_evidence or []):
                src = (item.get("source_type") or "").lower()
                if src in ("photo", "drone", "ip_camera", "camera", "image"):
                    raw_photos.append(item.get("payload", item))
                elif src in ("soil_analysis", "soil", "lab"):
                    raw_soil.append(item.get("payload", item))
                elif src in ("sensor", "iot", "weather_station"):
                    raw_sensors.append(item.get("payload", item))
            
            perception_bundle = build_perception_bundle(
                photos=raw_photos or None,
                soil_analyses=raw_soil or None,
                sensors=raw_sensors or None,
            )
            
            obs_count = len(perception_bundle.observation_products)
            spatial_count = len(perception_bundle.spatially_supported_observations)
            print(f"[SCOPE] [Layer 0] Perception bundle: {obs_count} observations ({spatial_count} spatially supported)")
        except Exception as e:
            print(f"[WARN] [Layer 0] Perception adapter skipped: {e}")
        
        # Merge structured user evidence down from Orchestrator Layer
        if user_evidence:
            from layer1_fusion.schema import EvidenceItem, EvidenceSourceType
            from datetime import datetime
            for item in user_evidence:
                try:
                    ts_str = item.get("timestamp")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except:
                        # Fallback to analysis window end for deterministic replay
                        ts = datetime.strptime(end_date, "%Y-%m-%d")
                    
                    evidence_pool.append(EvidenceItem(
                        id=str(item.get("id")),
                        source_type=EvidenceSourceType(item.get("source_type")),
                        timestamp=ts,
                        location_scope=item.get("location_scope", "point"),
                        payload=item.get("payload", {})
                    ))
                except Exception as e:
                    print(f"[WARN] Failed to parse user evidence item: {e}")

        tracker.log_event(
            "ACQUIRED_EVIDENCE",
            outputs=[e.id for e in evidence_pool],
            metadata={"count": len(evidence_pool)}
        )

        # --- Step 2: Validation & Trust ---
        if trust_system:
            evidence_pool = trust_system.validate_batch(evidence_pool)

        # Filter accepted/flagged (reject rejected)
        valid_evidence = [e for e in evidence_pool if e.status != ValidationStatus.REJECTED]
        rejected_evidence = [e for e in evidence_pool if e.status == ValidationStatus.REJECTED]

        tracker.log_event(
            "VALIDATED_EVIDENCE",
            inputs=[e.id for e in evidence_pool],
            outputs=[e.id for e in valid_evidence],
            metadata={"valid_count": len(valid_evidence), "rejected_count": len(rejected_evidence)}
        )

        # --- Step 3-7: Fusion Pipeline ---
        tensor = FieldTensor(plot_id=plot_id, run_id=run_id)

        # Initialize Time
        date_strs = self._generate_date_range(start_date, end_date)
        tensor.time_index = date_strs

        # 4. Temporal Fusion (optical + SAR into a daily aligned record set)
        if HAS_PANDAS:
            daily_records = self._perform_temporal_fusion_pandas(date_strs, valid_evidence)
        else:
            daily_records = self._perform_temporal_fusion_pure(date_strs, valid_evidence)

        # 6. Weather Fusion MUST occur before spatial tensor building so precip exists in tensor channels
        self._merge_weather_into_records(daily_records, valid_evidence)

        # =====================================================================
        # LAYER 0: Daily State Assimilation (Kalman Engine)
        # Replaces "interpolated indices" with uncertainty-aware daily states.
        # Runs AFTER evidence collection & weather merge, BEFORE spatial fusion.
        # =====================================================================
        if HAS_LAYER0:
            try:
                self._run_layer0_assimilation(
                    tensor, valid_evidence, daily_records,
                    start_date, end_date, tracker
                )
                print(f"[OK] [Layer 0] Daily state assimilation complete: "
                      f"{len(tensor.daily_state)} zones")
            except Exception as e:
                print(f"[WARN] [Layer 0] Assimilation failed, falling back to interpolation: {e}")
        # =====================================================================

        # Attach plot timeseries
        tensor.plot_timeseries = daily_records

        # --- Step 4.5: Raster Composites (Spatial Surfaces Patch 2) ---
        # Fetch real pixel grids here so Step 5 can inject them into the tensor.
        # PERF: All 4 raster fetches run concurrently (was sequential, ~20-40s → ~5-10s)
        # NOTE: All diagnostics go to stderr because run_surfaces_mode wraps L1
        # in redirect_stdout, which swallows print() calls.
        import sys as _sys
        import time as _rc_time
        raster_composites = None
        _rc_t0 = _rc_time.perf_counter()
        _poly_type = type(polygon_coords).__name__ if polygon_coords else "None"
        _poly_keys = list(polygon_coords.keys()) if isinstance(polygon_coords, dict) else "N/A"
        print(f"[DIAG] [Raster] polygon_coords type={_poly_type}, keys={_poly_keys}, lat={lat}, lng={lng}, plot={plot_id}", file=_sys.stderr, flush=True)
        if polygon_coords or (lat and lng):
            try:
                from layer0.data_gateway import broker as _raster_broker

                raster_sources = [
                    "raster_composite_ndvi",
                    "raster_composite_ndmi",
                    "raster_composite_sar",
                    "raster_quality_mask",
                ]
                extra_args = {
                    src: {
                        "start_date": start_date,
                        "end_date": end_date,
                        "polygon_coords": polygon_coords
                    }
                    for src in raster_sources
                }
                raw = _raster_broker.get_bulk(
                    raster_sources, plot_id or "", lat, lng,
                    extra_args=extra_args,
                )

                source_to_key = {
                    "raster_composite_ndvi": "NDVI",
                    "raster_composite_ndmi": "NDMI",
                    "raster_composite_sar": "SAR",
                    "raster_quality_mask": "QUALITY",
                }
                composites = {}
                for src, key in source_to_key.items():
                    result = raw.get(src)
                    if result and result.get("valid_pixel_count", 0) > 0:
                        composites[key] = result
                        vpc = result.get("valid_pixel_count", 0)
                        dims = f"{result.get('height', '?')}x{result.get('width', '?')}"
                        print(f"[DIAG] [Raster] {key}: dims={dims}, valid_pixels={vpc}", file=_sys.stderr, flush=True)

                _rc_elapsed = _rc_time.perf_counter() - _rc_t0
                if composites:
                    raster_composites = composites
                    self._pending_raster_composites = composites  # Hand off to _perform_spatial_fusion
                    print(f"[SAT] [Layer 1] Raster composites acquired via Gateway: {list(composites.keys())} ({_rc_elapsed:.1f}s)", file=_sys.stderr, flush=True)
                    print(f"[SAT] [Layer 1] Raster composites acquired: {list(composites.keys())}")
                else:
                    print(f"[WARN] [Layer 1] No valid raster composites for this window ({_rc_elapsed:.1f}s)", file=_sys.stderr, flush=True)
                    print(f"[WARN] [Layer 1] No valid raster composites for this window")
            except Exception as e:
                print(f"[WARN] [Layer 1] Raster composite acquisition skipped: {e}", file=_sys.stderr, flush=True)
                print(f"[WARN] [Layer 1] Raster composite acquisition skipped: {e}")
        else:
            print(f"[DIAG] [Raster] SKIPPED: no polygon_coords and no lat/lng", file=_sys.stderr, flush=True)

        # 5. Spatial Fusion (build tensor.data from daily_records — now includes rain)
        self._perform_spatial_fusion(
            tensor=tensor, 
            daily_records=daily_records, 
            lat=lat, 
            lng=lng, 
            polygon_coords=polygon_coords, 
            run_id=run_id
        )

        # 7. Static Layers
        self._merge_static(tensor, valid_evidence)

        # 8. Forecast 7D (Forward-looking models)
        self._merge_forecast_7d(tensor, valid_evidence)

        # --- Step 8: Finalize Artifacts ---
        summary = [e.to_dict() for e in evidence_pool]
        report = self._generate_health_report(evidence_pool, daily_records)

        tracker.log_event(
            "GENERATED_TENSOR",
            inputs=[e.id for e in valid_evidence],
            metadata={"shape": tensor.get_shape()}
        )

        # Attach Provenance (Now includes GENERATED_TENSOR)
        existing_prov = tensor.provenance or {}
        tensor.provenance = {
            **existing_prov,
            "run_id": run_id,
            "lineage": tracker.export_lineage(),
            "acquisition_diagnostics": acquisition_snapshot,
            "tracker_stats": {
                "events_count": len(tracker.events),
                "duration_ms": 0.0
            }
        }

        print(f"[OK] [Layer 1] Fusion Complete. Run ID: {run_id}")

        # Serialize perception bundle for downstream layers
        obs_products = None
        if perception_bundle:
            from dataclasses import asdict
            try:
                obs_products = {
                    "plot_level": [asdict(o) for o in perception_bundle.plot_level_observations],
                    "spatially_supported": [asdict(o) for o in perception_bundle.spatially_supported_observations],
                    "total_count": len(perception_bundle.observation_products),
                    "has_row_features": perception_bundle.row_features is not None and perception_bundle.row_features.confidence > 0,
                }
            except Exception as e:
                print(f"[WARN] [Layer 0] Observation product serialization failed: {e}")

        return FusionOutput(
            tensor=tensor,
            evidence_summary=summary,
            validation_report=report,
            logs=tracker.export_lineage(),
            observation_products=obs_products,
            raster_composites=raster_composites,
        )

    # ------------------------------------------------------------------------
    # Pipeline Step Implementations
    # ------------------------------------------------------------------------

    def _generate_date_range(self, start: str, end: str) -> List[str]:
        """Pure Python date range (Inclusive)"""
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
        delta = e - s
        dates = []
        for i in range(delta.days + 1):
            day = s + timedelta(days=i)
            dates.append(day.strftime("%Y-%m-%d"))
        return dates

    def _safe_parse_date(self, d: Any) -> Optional[datetime]:
        if d is None:
            return None
        if HAS_PANDAS:
            try:
                return pd.to_datetime(d).to_pydatetime()
            except Exception:
                return None
        if isinstance(d, datetime):
            return d
        if isinstance(d, str):
            try:
                return datetime.strptime(d[:10], "%Y-%m-%d")
            except Exception:
                return None
        return None

    def _in_range(self, ts: Optional[datetime], start_dt: datetime, end_dt: datetime) -> bool:
        if ts is None:
            return False
        # inclusive of start/end by day
        return start_dt <= ts <= end_dt

    def _hash_payload(self, payload: Dict[str, Any]) -> str:
        try:
            raw = repr(sorted(payload.items())).encode("utf-8")
        except Exception:
            raw = repr(payload).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:12]

    def _acquire_all_evidence(self, lat: float, lng: float, start: str, end: str, polygon_coords: Optional[list] = None) -> tuple[List["EvidenceItem"], Dict[str, Any]]:
        pool: List[EvidenceItem] = []
        snapshot: Dict[str, Any] = {"sar": {}, "optical": {}, "weather": {}, "forecast": {}}

        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        sar_days = max(1, (end_dt - start_dt).days + 1)

        from concurrent.futures import ThreadPoolExecutor

        def _fetch_opt():
            try:
                opt_resp = fetch_ndvi_timeseries(lat, lng, polygon_coords=polygon_coords)
                return "opt", opt_resp, None
            except Exception as e:
                return "opt", None, str(e)
                
        def _fetch_sar():
            try:
                sar_resp = fetch_sar_timeseries(lat, lng, days=sar_days, polygon_coords=polygon_coords) or {}
                return "sar", sar_resp, None
            except Exception as e:
                return "sar", None, str(e)
                
        def _fetch_wx():
            try:
                wx_raw = fetch_historical_weather(lat, lng, start, end)
                return "wx", wx_raw, None
            except Exception as e:
                return "wx", None, str(e)
                
        def _fetch_fc():
            try:
                forecast_raw = fetch_openweather_forecast(lat, lng)
                return "fc", forecast_raw, None
            except Exception as e:
                return "fc", None, str(e)
                
        def _fetch_soil():
            try:
                soil_raw = fetch_soil_properties(lat, lng)
                return "soil", soil_raw, None
            except Exception as e:
                return "soil", None, str(e)

        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_fetch_opt),
                executor.submit(_fetch_sar),
                executor.submit(_fetch_wx),
                executor.submit(_fetch_fc),
                executor.submit(_fetch_soil),
            ]
            for future in futures:
                k, data, err = future.result()
                results[k] = (data, err)

        # 1. Optical
        opt_data, opt_err = results["opt"]
        opt_raw = []
        if opt_err:
            snapshot["optical"] = {"status": "ERROR", "error": opt_err}
        else:
            opt_raw = opt_data.get("data", []) or []
            snapshot["optical"] = {
                "status": "OK",
                "count": len(opt_raw),
                "keys_seen": list(opt_data.keys()) if isinstance(opt_data, dict) else [],
                "sample_keys": list(opt_raw[0].keys()) if opt_raw else []
            }
        
        for rec in opt_raw:
            ts = self._safe_parse_date(rec.get("date"))
            if not self._in_range(ts, start_dt, end_dt):
                continue
            scene_id = rec.get("scene_id") or rec.get("id") or self._hash_payload(rec)
            pool.append(EvidenceItem(
                id=f"s2_{ts.strftime('%Y-%m-%d')}_{scene_id}",
                source_type=EvidenceSourceType.SATELLITE_OPTICAL,
                timestamp=ts,
                location_scope="plot",
                payload=rec
            ))

        # 2. SAR
        sar_data, sar_err = results["sar"]
        sar_raw = []
        if sar_err:
            snapshot["sar"] = {"status": "ERROR", "error": sar_err}
        else:
            sar_raw = sar_data.get("timeseries", []) or sar_data.get("data", []) or []
            snapshot["sar"] = {
                "status": "OK",
                "count": len(sar_raw),
                "keys_seen": list(sar_data.keys()) if isinstance(sar_data, dict) else [],
                "params": {"lat": lat, "lng": lng, "days": sar_days},
                "provider": "earthengine-api"
            }
            if not sar_raw and "error" in sar_data:
                 snapshot["sar"]["provider_error"] = sar_data["error"]
                 
        for rec in sar_raw:
            ts = self._safe_parse_date(rec.get("date"))
            if not self._in_range(ts, start_dt, end_dt):
                continue
            scene_id = rec.get("scene_id") or rec.get("id") or self._hash_payload(rec)
            pool.append(EvidenceItem(
                id=f"s1_{ts.strftime('%Y-%m-%d')}_{scene_id}",
                source_type=EvidenceSourceType.SATELLITE_SAR,
                timestamp=ts,
                location_scope="plot",
                payload=rec
            ))

        # 3. Weather
        wx_data, wx_err = results["wx"]
        if wx_err:
            snapshot["weather"] = {"status": "ERROR", "error": wx_err}
        else:
            snapshot["weather"] = {"status": "OK", "keys": list(wx_data.keys()) if isinstance(wx_data, dict) else []}
            if wx_data:
                if "records" in wx_data:
                    for rec in wx_data.get("records", []):
                        t = rec.get("date")
                        ts = self._safe_parse_date(t)
                        if not self._in_range(ts, start_dt, end_dt):
                            continue
                        payload = {
                            "date": t,
                            "temperature_mean": rec.get("temp_mean"),
                            "temperature_max": rec.get("temp_max"),
                            "temperature_min": rec.get("temp_min"),
                            "precipitation": rec.get("precipitation"),
                            "rain": rec.get("rain"),
                            "et0": rec.get("et0"),
                            "wind_max": rec.get("wind_max"),
                            "solar_radiation": rec.get("solar_radiation"),
                        }
                        pool.append(EvidenceItem(
                            id=f"wx_{t}",
                            source_type=EvidenceSourceType.WEATHER,
                            timestamp=ts,
                            location_scope="point",
                            payload=payload
                        ))
                elif "daily" in wx_data:
                    d = wx_data.get("daily", {}) or {}
                    times = d.get("time", []) or []
                    for i, t in enumerate(times):
                        ts = self._safe_parse_date(t)
                        if not self._in_range(ts, start_dt, end_dt):
                            continue
                        payload = {
                            "date": t,
                            "temperature_mean": (d.get("temperature_2m_mean", [None]) or [None])[i],
                            "precipitation": (d.get("precipitation_sum", [None]) or [None])[i],
                            "rain": (d.get("rain_sum", [None]) or [None])[i] if "rain_sum" in d else None,
                            "et0": (d.get("et0_fao_evapotranspiration", [None]) or [None])[i] if "et0_fao_evapotranspiration" in d else None,
                        }
                        pool.append(EvidenceItem(
                            id=f"wx_{t}",
                            source_type=EvidenceSourceType.WEATHER,
                            timestamp=ts,
                            location_scope="point",
                            payload=payload
                        ))

        # 4. Forecast
        fc_data, fc_err = results["fc"]
        if fc_err:
            snapshot["forecast"] = {"status": "ERROR", "error": fc_err}
        else:
            fc_list = fc_data.get("forecast", []) if fc_data else []
            snapshot["forecast"] = {"status": "OK", "count": len(fc_list)} if fc_list else {"status": "EMPTY"}
            if fc_list:
                for i, day_fc in enumerate(fc_list):
                    # Use end_dt (not datetime.now()) for deterministic replay
                    fc_date = self._safe_parse_date(day_fc.get('date'))
                    pool.append(EvidenceItem(
                        id=f"wx_fc_{day_fc.get('date', i)}",
                        source_type=EvidenceSourceType.WEATHER_FORECAST,
                        timestamp=fc_date or end_dt,
                        location_scope="point",
                        payload=day_fc
                    ))

        # 5. Soil
        soil_data, soil_err = results["soil"]
        if soil_data and not soil_err:
            # Use end_dt (not datetime.now()) for deterministic replay.
            # SoilGrids is time-invariant; timestamp is provenance only.
            pool.append(EvidenceItem(
                id=f"soil_grids_static_{self._hash_payload(soil_data)}",
                source_type=EvidenceSourceType.SOIL,
                timestamp=end_dt,
                location_scope="point",
                payload=soil_data
            ))

        return pool, snapshot

    def _perform_temporal_fusion_pandas(self, date_strs: List[str], evidence: List["EvidenceItem"]) -> List[Dict]:
        """High-Performance implementation using Pandas. Fuses optical + SAR (plot-level)."""
        idx = pd.to_datetime(date_strs)
        df = pd.DataFrame(index=idx)
        df.index.name = "date"

        def _safe_float(val, default=np.nan):
            if val is None:
                return default
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        # --- Optical (NDVI) ---
        opt_items = [e for e in evidence if e.source_type == EvidenceSourceType.SATELLITE_OPTICAL]
        opt_data = {}
        for item in opt_items:
            dt = pd.to_datetime(item.timestamp)
            if dt in df.index:
                opt_data[dt] = {
                    "ndvi_mean": _safe_float(item.payload.get("ndvi")),
                    "coverage": _safe_float((100 - _safe_float(item.payload.get("cloud_cover", 0), 0)) / 100.0)
                }
        opt_df = pd.DataFrame.from_dict(opt_data, orient="index")
        if not opt_df.empty:
            df = df.join(opt_df)
        else:
            df["ndvi_mean"] = np.nan
            df["coverage"] = np.nan

        # --- SAR (VV/VH) ---
        sar_items = [e for e in evidence if e.source_type == EvidenceSourceType.SATELLITE_SAR]
        sar_data = {}
        for item in sar_items:
            dt = pd.to_datetime(item.timestamp)
            if dt in df.index:
                sar_data[dt] = {
                    "vv": _safe_float(item.payload.get("vv_db", item.payload.get("vv"))),
                    "vh": _safe_float(item.payload.get("vh_db", item.payload.get("vh")))
                }
        sar_df = pd.DataFrame.from_dict(sar_data, orient="index")
        if not sar_df.empty:
            df = df.join(sar_df)
        else:
            df["vv"] = np.nan
            df["vh"] = np.nan

        # --- Interpolation ---
        df["is_observed"] = df["ndvi_mean"].notna()

        df["ndvi_interpolated"] = (
            df["ndvi_mean"]
            .interpolate(method="linear")
            .bfill()
            .ffill()
        )

        # SAR interpolation (keep simple: linear + fill)
        df["vv_interpolated"] = df["vv"].interpolate(method="linear").bfill().ffill()
        df["vh_interpolated"] = df["vh"].interpolate(method="linear").bfill().ffill()

        # --- Corrections / Smoothing ---
        if correction_engine:
            recs = df.reset_index().to_dict("records")
            smoothed = correction_engine.apply_smoothing(recs, "ndvi_interpolated")
            s_df = pd.DataFrame(smoothed)
            if "date" in s_df.columns:
                s_df = s_df.set_index("date")
            if "ndvi_interpolated_smoothed" in s_df.columns:
                df["ndvi_smoothed"] = s_df["ndvi_interpolated_smoothed"]
            else:
                df["ndvi_smoothed"] = df["ndvi_interpolated"]
        else:
            df["ndvi_smoothed"] = df["ndvi_interpolated"]

        # --- Uncertainty ---
        # Basic: observed NDVI days lower uncertainty; interpolated days higher.
        df["uncertainty"] = 0.1
        df.loc[~df["is_observed"], "uncertainty"] = 0.5

        # Prepare records — sanitize any remaining NaN before serialization
        # After interpolation + bfill/ffill, NaN only persists when an entire column
        # has zero observations. Replace those with safe defaults (0.0).
        nan_cols = ["ndvi_mean", "ndvi_interpolated", "ndvi_smoothed",
                    "vv", "vh", "vv_interpolated", "vh_interpolated", "coverage"]
        for col in nan_cols:
            if col in df.columns:
                df[col] = df[col].fillna(0.0)

        df = df.reset_index()
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        # Final defense: convert any straggling NaN/NaT to None for JSON safety
        records = df.where(df.notna(), None).to_dict("records")
        return records

    def _perform_temporal_fusion_pure(self, date_strs: List[str], evidence: List["EvidenceItem"]) -> List[Dict]:
        """Pure Python implementation using lists. Fuses optical + SAR (plot-level)."""
        # Optical map
        opt_map: Dict[str, Dict[str, Any]] = {}
        for e in evidence:
            if e.source_type == EvidenceSourceType.SATELLITE_OPTICAL and e.timestamp:
                d_str = e.timestamp.strftime("%Y-%m-%d")
                if d_str in date_strs:
                    opt_map[d_str] = {
                        "ndvi_mean": e.payload.get("ndvi"),
                        "coverage": (100 - e.payload.get("cloud_cover", 0)) / 100.0
                    }

        # SAR map
        sar_map: Dict[str, Dict[str, Any]] = {}
        for e in evidence:
            if e.source_type == EvidenceSourceType.SATELLITE_SAR and e.timestamp:
                d_str = e.timestamp.strftime("%Y-%m-%d")
                if d_str in date_strs:
                    sar_map[d_str] = {
                        "vv": e.payload.get("vv_db", e.payload.get("vv")),
                        "vh": e.payload.get("vh_db", e.payload.get("vh"))
                    }

        # Build daily records and sequences for interpolation
        records: List[Dict[str, Any]] = []
        ndvi_values: List[Optional[float]] = []
        vv_values: List[Optional[float]] = []
        vh_values: List[Optional[float]] = []

        for d in date_strs:
            rec: Dict[str, Any] = {"date": d, "is_observed": False, "uncertainty": 0.5}

            # NDVI
            if d in opt_map and opt_map[d].get("ndvi_mean") is not None:
                rec["ndvi_mean"] = opt_map[d]["ndvi_mean"]
                rec["coverage"] = opt_map[d].get("coverage")
                rec["is_observed"] = True
                rec["uncertainty"] = 0.1
                ndvi_values.append(rec["ndvi_mean"])
            else:
                rec["ndvi_mean"] = None
                ndvi_values.append(None)

            # SAR
            vv = sar_map.get(d, {}).get("vv")
            vh = sar_map.get(d, {}).get("vh")
            rec["vv"] = vv
            rec["vh"] = vh
            vv_values.append(vv if vv is not None else None)
            vh_values.append(vh if vh is not None else None)

            records.append(rec)

        # Fill gaps (linear) + smoothing (moving average) even without correction_engine
        def fill_linear(vals: List[Optional[float]]) -> List[Optional[float]]:
            # If correction_engine has a helper, use it; else implement basic linear interpolation.
            if correction_engine and hasattr(correction_engine, "_fill_gaps_linear"):
                return correction_engine._fill_gaps_linear(vals)

            # basic pure python interpolation with ffill/bfill
            out = vals[:]
            # forward fill
            last = None
            for i in range(len(out)):
                if out[i] is None:
                    out[i] = last
                else:
                    last = out[i]
            # back fill for leading Nones
            nextv = None
            for i in reversed(range(len(out))):
                if out[i] is None:
                    out[i] = nextv
                else:
                    nextv = out[i]
            # if still all None, set zeros
            if all(v is None for v in out):
                return [0.0 for _ in out]

            # linear interpolate runs of None between two known points (now none should exist, but keep safe)
            # (we already filled; keep as-is)
            return out  # type: ignore

        def moving_average(vals: List[float], window: int = 5) -> List[float]:
            if window <= 1:
                return vals
            out: List[float] = []
            half = window // 2
            n = len(vals)
            for i in range(n):
                a = max(0, i - half)
                b = min(n, i + half + 1)
                chunk = vals[a:b]
                out.append(sum(chunk) / max(1, len(chunk)))
            return out

        filled_ndvi = fill_linear(ndvi_values)
        filled_vv = fill_linear(vv_values)
        filled_vh = fill_linear(vh_values)

        # Ensure numeric
        ndvi_num = [float(v) if v is not None else 0.0 for v in filled_ndvi]
        vv_num = [float(v) if v is not None else 0.0 for v in filled_vv]
        vh_num = [float(v) if v is not None else 0.0 for v in filled_vh]

        # Apply correction_engine smoothing if present; else moving average
        if correction_engine:
            for i, val in enumerate(ndvi_num):
                records[i]["ndvi_interpolated"] = val
            records = correction_engine.apply_smoothing(records, "ndvi_interpolated")
            for r in records:
                r["ndvi_smoothed"] = r.get("ndvi_interpolated_smoothed", r.get("ndvi_interpolated", 0.0))
        else:
            sm = moving_average(ndvi_num, window=5)
            for i in range(len(records)):
                records[i]["ndvi_interpolated"] = ndvi_num[i]
                records[i]["ndvi_smoothed"] = sm[i]

        # Store SAR interpolated (no smoothing needed here)
        for i in range(len(records)):
            records[i]["vv_interpolated"] = vv_num[i]
            records[i]["vh_interpolated"] = vh_num[i]

        return records

    def _perform_spatial_fusion(self, tensor: "FieldTensor", daily_records: List[Dict], lat: float, lng: float, polygon_coords: Optional[list] = None, run_id: str = ""):
        """
        Step 5: Generate 4D Tensor Data [T, H, W, C] using Raster Backend.

        NOTE:
        - This function currently paints per-pixel values from plot-level signals (ndvi_smoothed, vv/vh, rain).
        - It is deterministic (no non-deterministic random noise).
        - In full production, this should be replaced by reading real raster composites and warping/masking them
          using the backend, but naming and API remain unchanged.
        """
        # Initialize Backend (Try Scientific, Fallback to Pure Python)
        try:
            backend = RasterioBackend()
            print("[MAP] [Spatial] Using RasterioBackend (Scientific Mode)")
        except ImportError:
            backend = TileStoreBackend()
            print("[WARN] [Spatial] Rasterio not found. Using TileStoreBackend (Restricted Mode)")

        # Create GridSpec from Plot Geometry or generate a fallback bbox
        target_polygon = None
        if polygon_coords and isinstance(polygon_coords, list) and isinstance(polygon_coords[0], list):
            print("[MAP] [Spatial] Using real polygon coordinates from caller")
            target_polygon = polygon_coords
        elif polygon_coords and isinstance(polygon_coords, dict):
             if "features" in polygon_coords:
                 print("[MAP] [Spatial] Using real GeoJSON FeatureCollection from caller")
                 target_polygon = polygon_coords["features"][0]["geometry"]["coordinates"][0] # simple extractor
             elif polygon_coords.get("type") == "Feature":
                 print("[MAP] [Spatial] Using real GeoJSON Feature from caller")
                 target_polygon = polygon_coords["geometry"]["coordinates"][0]
             else:
                 print("[WARN] [Spatial] Unknown polygon dict format")
        
        if not polygon_coords or target_polygon is None:
            print("[WARN] [Spatial] No polygon provided. Generating 100x100m fallback bbox around centroid.")
            offset = 0.00045 # roughly 50m
            target_polygon = [
                (lng - offset, lat + offset),
                (lng + offset, lat + offset),
                (lng + offset, lat - offset),
                (lng - offset, lat - offset),
                (lng - offset, lat + offset)
            ]
            
        tensor.grid_spec = backend.create_grid(target_polygon, resolution_m=10.0)
        
        # Save polygon to static metadata so downstream layers (like Layer 10) can use it for exact masking
        if not hasattr(tensor, 'static') or tensor.static is None:
            tensor.static = {}
        tensor.static["polygon_coords"] = target_polygon

        w = tensor.grid_spec.width
        h = tensor.grid_spec.height

        channels = tensor.channels
        c_map = {c: i for i, c in enumerate(channels)}

        # Generate uniform raster base from plot-level signals.
        # In the future, this is where pixel-level satellite data is queried and aligned.
        tensor_data: List[Any] = []  # [T][H][W][C]

        for row in daily_records:
            day = row.get("date", "")
            t_grid = []  # [H][W][C]

            import math
            ndvi_raw = row.get("ndvi_smoothed")
            if ndvi_raw is None or (isinstance(ndvi_raw, float) and math.isnan(ndvi_raw)):
                ndvi = None
            else:
                ndvi = ndvi_raw

            vv = row.get("vv_interpolated", row.get("vv", 0.0)) or 0.0
            vh = row.get("vh_interpolated", row.get("vh", 0.0)) or 0.0
            rain = row.get("rain", 0.0) or 0.0
            unc = row.get("uncertainty", 0.5) if row.get("uncertainty") is not None else 0.5

            for y in range(h):
                row_grid = []
                for x in range(w):
                    pixel = [0.0] * len(channels)

                    # The assimilation system provides physically correct assimilated data at the plot level.
                    # We no longer add artificial deterministic noise (checkerboard patterns) because it misrepresents the agronomic reality.
                    variation = 0.0

                    if FieldTensorChannels.NDVI in c_map:
                        if ndvi is not None:
                            pixel[c_map[FieldTensorChannels.NDVI]] = max(0.0, min(1.0, ndvi + variation))
                        else:
                            pixel[c_map[FieldTensorChannels.NDVI]] = None

                    if FieldTensorChannels.NDVI_UNC in c_map:
                        pixel[c_map[FieldTensorChannels.NDVI_UNC]] = float(unc)

                    if FieldTensorChannels.PRECIPITATION in c_map:
                        pixel[c_map[FieldTensorChannels.PRECIPITATION]] = float(rain)

                    if hasattr(FieldTensorChannels, "VV") and FieldTensorChannels.VV in c_map:
                        pixel[c_map[FieldTensorChannels.VV]] = vv + variation * 2
                    if hasattr(FieldTensorChannels, "VH") and FieldTensorChannels.VH in c_map:
                        pixel[c_map[FieldTensorChannels.VH]] = vh + variation * 2

                    row_grid.append(pixel)
                t_grid.append(row_grid)
            tensor_data.append(t_grid)

        tensor.data = tensor_data

        # --- Fix B: Inject real raster composites into spatial channels ---
        # If raster composites were acquired (Step 9), write them into the
        # last time step and into tensor.maps so L10 sees real pixel data.
        raster_composites = getattr(self, '_pending_raster_composites', None)
        if raster_composites and tensor_data:
            last_t_idx = len(tensor_data) - 1

            # NDVI raster → NDVI channel + maps["ndvi"]
            ndvi_rc = raster_composites.get("NDVI")
            if ndvi_rc and FieldTensorChannels.NDVI in c_map:
                ci = c_map[FieldTensorChannels.NDVI]
                rc_h, rc_w = ndvi_rc["height"], ndvi_rc["width"]
                ndvi_map = [[None] * w for _ in range(h)]
                for r in range(min(h, rc_h)):
                    for c in range(min(w, rc_w)):
                        v = ndvi_rc["values"][r][c]
                        if v is not None:
                            tensor_data[last_t_idx][r][c][ci] = v
                            ndvi_map[r][c] = v
                if not hasattr(tensor, 'maps') or tensor.maps is None:
                    tensor.maps = {}
                tensor.maps["ndvi"] = ndvi_map
                print(f"[SAT] [Spatial] NDVI raster injected: {rc_h}×{rc_w}")

            # NDMI raster → maps["ndmi"]
            ndmi_rc = raster_composites.get("NDMI")
            if ndmi_rc:
                ndmi_map = [[None] * w for _ in range(h)]
                for r in range(min(h, ndmi_rc["height"])):
                    for c in range(min(w, ndmi_rc["width"])):
                        ndmi_map[r][c] = ndmi_rc["values"][r][c]
                if not hasattr(tensor, 'maps') or tensor.maps is None:
                    tensor.maps = {}
                tensor.maps["ndmi"] = ndmi_map

            # SAR raster → VV/VH channels + maps["vv"], maps["vh"]
            sar_rc = raster_composites.get("SAR")
            if sar_rc:
                rc_h, rc_w = sar_rc["height"], sar_rc["width"]
                vv_map = [[None] * w for _ in range(h)]
                vh_map = [[None] * w for _ in range(h)]
                for r in range(min(h, rc_h)):
                    for c in range(min(w, rc_w)):
                        v = sar_rc["values"][r][c]
                        if v is not None:
                            vv_map[r][c] = v
                            # Write into tensor channels if available
                            if hasattr(FieldTensorChannels, "VV") and FieldTensorChannels.VV in c_map:
                                tensor_data[last_t_idx][r][c][c_map[FieldTensorChannels.VV]] = v
                if not hasattr(tensor, 'maps') or tensor.maps is None:
                    tensor.maps = {}
                tensor.maps["vv"] = vv_map
                tensor.maps["vh"] = vh_map

            # Quality mask → maps["quality_mask"]
            qm_rc = raster_composites.get("QUALITY")
            if qm_rc:
                qm_map = [[None] * w for _ in range(h)]
                for r in range(min(h, qm_rc["height"])):
                    for c in range(min(w, qm_rc["width"])):
                        qm_map[r][c] = qm_rc["values"][r][c]
                if not hasattr(tensor, 'maps') or tensor.maps is None:
                    tensor.maps = {}
                tensor.maps["quality_mask"] = qm_map

            # --- Fix D: Apply quality mask to NDVI raster (Hampel Robust Outlier Detector) ---
            #
            # Scientific basis (Hampel identifier — Pearson 2002, RStat; Huete et al. 2002):
            #   The Hampel identifier is the standard robust outlier detection method for
            #   contaminated distributions. Unlike a hard threshold (which zeros all pixels
            #   in dust-prone Algeria) or a naive %-of-median approach (which misses outliers
            #   when median is moderate), it detects pixels that deviate beyond 3 × scaled-MAD
            #   from the field median. MAD = median(|x - median(x)|).
            #   Scaled MAD = 1.4826 × MAD ≈ σ for Gaussian distributions.
            #   This is the same method used in MODIS MOD13 QA filtering.
            #
            # Absolute floor:
            #   Quality < 0.10 = fewer than 10% of scenes were clear-sky (SCL 4/5).
            #   Such pixels have NDVI medians dominated by cloud/aerosol contamination.
            #   This is an absolute veto regardless of field distribution.
            #
            # Skip condition:
            #   If field median quality < 0.15, the SCL filter already rejected the worst
            #   scenes at evalscript level. Blanket nulling would remove all spatial variation.
            qm = tensor.maps.get("quality_mask") if hasattr(tensor, 'maps') and tensor.maps else None
            ndvi_m = tensor.maps.get("ndvi") if hasattr(tensor, 'maps') and tensor.maps else None
            if qm and ndvi_m:
                # Step 1: Collect all valid quality values
                qm_vals = []
                for r in range(min(h, len(qm))):
                    for c in range(min(w, len(qm[r]) if qm[r] else 0)):
                        q = qm[r][c]
                        if q is not None and q > 0:
                            qm_vals.append(q)

                masked_count = 0
                adaptive_thresh = 0.0
                field_median_q = 0.0

                if qm_vals:
                    qm_vals_sorted = sorted(qm_vals)
                    n = len(qm_vals_sorted)
                    field_median_q = qm_vals_sorted[n // 2]

                    if field_median_q >= 0.15:
                        # Hampel identifier: compute MAD = median(|x - median|)
                        deviations = sorted(abs(q - field_median_q) for q in qm_vals)
                        mad = deviations[len(deviations) // 2]
                        # Scaled MAD (consistent estimator of σ under Gaussian): 1.4826 × MAD
                        scaled_mad = 1.4826 * mad

                        # Hampel lower bound: mask pixels more than 3σ below median
                        hampel_thresh = field_median_q - 3.0 * scaled_mad

                        # Absolute floor: never trust pixels with <10% clear scenes,
                        # even if they happen to pass the Hampel test on a bad-quality field
                        adaptive_thresh = max(0.10, hampel_thresh)

                        # Safety cap: don't over-mask — if threshold would exceed 50% of
                        # median, cap it. Prevents over-aggressive masking on high-quality fields.
                        adaptive_thresh = min(adaptive_thresh, field_median_q * 0.50)
                    else:
                        # Uniformly poor quality — SCL filter already handles worst scenes
                        adaptive_thresh = 0.0

                    if adaptive_thresh > 0:
                        for r in range(min(h, len(qm))):
                            for c in range(min(w, len(qm[r]) if qm[r] else 0)):
                                q = qm[r][c]
                                if q is not None and q < adaptive_thresh and r < len(ndvi_m) and c < len(ndvi_m[r]):
                                    if ndvi_m[r][c] is not None:
                                        ndvi_m[r][c] = None
                                        masked_count += 1
                                        if FieldTensorChannels.NDVI in c_map:
                                            ci = c_map[FieldTensorChannels.NDVI]
                                            tensor_data[last_t_idx][r][c][ci] = None

                import sys as _sys_qm
                _q_pct = (masked_count / len(qm_vals) * 100) if qm_vals else 0
                print(
                    f"[SAT] [Spatial] Quality mask (Hampel): median={field_median_q:.2f} "
                    f"thresh={adaptive_thresh:.3f} nulled={masked_count}/{len(qm_vals)} ({_q_pct:.0f}%)",
                    file=_sys_qm.stderr, flush=True
                )



        # --- SPATIAL EXTENSIONS (Phase 11): Zone Generation ---
        # Extract [T, H, W] stacks for NDVI and SAR_VV (needed by both numpy and pure python engines)
        if FieldTensorChannels.NDVI in c_map:
            c_idx = c_map[FieldTensorChannels.NDVI]
            ndvi_stack = [[[pixel[c_idx] for pixel in row] for row in t_grid] for t_grid in tensor_data]
        else:
            ndvi_stack = []
            
        if hasattr(FieldTensorChannels, "VV") and FieldTensorChannels.VV in c_map:
            c_idx_vv = c_map[FieldTensorChannels.VV]
            sar_stack = [[[pixel[c_idx_vv] for pixel in row] for row in t_grid] for t_grid in tensor_data]
        else:
            sar_stack = []
        
        # Try numpy-based engine first, fallback to Pure Python
        try:
            from layer1_fusion.zone_engine import generate_management_zones, compute_zone_stats
            tensor.zones = generate_management_zones(tensor.plot_id, ndvi_stack, sar_stack, tensor.grid_spec.to_dict())
            tensor.zone_stats = compute_zone_stats(ndvi_stack, sar_stack, tensor.zones, tensor.time_index)
        except Exception as e:
            print(f"[WARN] [Spatial] Numpy zone engine failed: {e}. Using Pure Python fallback.")
            try:
                from layer1_fusion.zone_engine import generate_management_zones_pure_python, compute_zone_stats_pure_python
                tensor.zones = generate_management_zones_pure_python(tensor.plot_id, ndvi_stack, sar_stack, tensor.grid_spec.to_dict())
                tensor.zone_stats = compute_zone_stats_pure_python(ndvi_stack, sar_stack, tensor.zones, tensor.time_index)
            except Exception as e2:
                print(f"[WARN] [Spatial] Pure Python zone engine also failed: {e2}")
        
        # Phase A: Build Research-Grade ZoneStats (p10/p90, uncertainty, polygon-aware labels)
        try:
            from layer1_fusion.zone_engine import build_spatial_zone_stats
            soil_static = tensor.static if hasattr(tensor, 'static') else {}
            tensor.spatial_zone_stats = build_spatial_zone_stats(
                zones=tensor.zones,
                ndvi_stack=ndvi_stack,
                sar_vv_stack=sar_stack,
                grid_spec=tensor.grid_spec.to_dict(),
                polygon_coords=polygon_coords,
                soil_static=soil_static
            )
        except Exception as e:
            print(f"[WARN] [Spatial] ZoneStats builder failed: {e}")
            tensor.spatial_zone_stats = []

        # Phase A.1: Inject GeoJSON geometries into zones (mask → lat/lng polygons)
        try:
            from layer1_fusion.zone_engine import inject_zone_geometries
            # Prefer the real polygon; fall back to grid_spec bounds only if absent
            if polygon_coords:
                zone_polygon = polygon_coords
                print(f"[OK] [Spatial] Zone geometries injected from real plot polygon")
            else:
                gs = tensor.grid_spec.to_dict()
                bounds = gs.get("bounds", ())
                if bounds and len(bounds) == 4:
                    min_lng, min_lat, max_lng, max_lat = bounds
                    zone_polygon = [
                        [min_lng, max_lat],  # NW
                        [max_lng, max_lat],  # NE
                        [max_lng, min_lat],  # SE
                        [min_lng, min_lat],  # SW
                        [min_lng, max_lat],  # close ring
                    ]
                    print(f"[WARN] [Spatial] Zone geometries injected from grid_spec bounds (no real polygon)")
                else:
                    zone_polygon = None
                    print(f"[WARN] [Spatial] No bounds in grid_spec — zone geometries skipped")

            if zone_polygon:
                tensor.zones = inject_zone_geometries(tensor.zones, zone_polygon)
        except Exception as e:
            print(f"[WARN] [Spatial] Zone geometry injection failed: {e}")

    def _merge_weather_into_records(self, records: List[Dict], evidence: List["EvidenceItem"]):
        """Step 6: Weather Fusion into daily records BEFORE tensor build.
        
        Now propagates real temp_max/temp_min instead of just temp_mean,
        so downstream Kalman drivers and L4 SWB receive accurate diurnal range.
        """
        wx_items = [e for e in evidence if e.source_type == EvidenceSourceType.WEATHER and e.timestamp]
        wx_map = {e.timestamp.strftime("%Y-%m-%d"): e.payload for e in wx_items}

        for row in records:
            d = row.get("date")
            if not d:
                continue
            if d in wx_map:
                w = wx_map[d] or {}
                rain = w.get("precipitation", 0.0)
                tmean = w.get("temperature_mean", 20.0)
                tmax = w.get("temperature_max")
                tmin = w.get("temperature_min")
                et0 = w.get("et0")
                row["rain"] = float(rain) if rain is not None else 0.0
                row["tmean"] = float(tmean) if tmean is not None else 20.0
                # Propagate real temp extremes (no synthetic ±5°C)
                row["temp_max"] = float(tmax) if tmax is not None else None
                row["temp_min"] = float(tmin) if tmin is not None else None
                row["et0"] = float(et0) if et0 is not None else None
                row["wind_speed"] = float(w.get("wind_max", 0.0) or 0.0)
                # Pure Python GDD (base 10C default; crop-specific base can be added later)
                row["gdd"] = max(0.0, row["tmean"] - 10.0)
            else:
                # Ensure keys exist for downstream consumers
                row.setdefault("rain", 0.0)
                row.setdefault("tmean", 20.0)
                row.setdefault("temp_max", None)
                row.setdefault("temp_min", None)
                row.setdefault("et0", None)
                row.setdefault("gdd", max(0.0, row["tmean"] - 10.0))

    def _merge_static(self, tensor: "FieldTensor", evidence: List["EvidenceItem"]):
        """Step 7: Static Layers (Robust against missing data)"""
        soil_items = [e for e in evidence if e.source_type == EvidenceSourceType.SOIL]
        
        # Start with safe defaults
        clay = 20.0
        sand = 40.0
        silt = 40.0
        ph = 6.5
        org_c = 10.0
        texture_class = "unknown"

        data_source = "defaults_no_data"

        if soil_items:
            best = soil_items[0]
            raw = best.payload or {}
            data_source = "soil_evidence"
            
            try:
                raw_clay = raw.get("clay")
                if raw_clay is not None:
                    clay = float(raw_clay)
                    
                raw_sand = raw.get("sand", raw.get("sand_percent"))
                if raw_sand is not None:
                    sand = float(raw_sand)
                    
                silt = round(100.0 - clay - sand, 1)
                
                raw_ph = raw.get("ph")
                if raw_ph is not None:
                    ph = float(raw_ph)
                    
                raw_org_c = raw.get("organic_carbon")
                if raw_org_c is not None:
                    org_c = float(raw_org_c)
                    
                texture_class = str(raw.get("texture_class", "unknown"))
            except (ValueError, TypeError) as e:
                print(f"[WARN] [Spatial] Error parsing static soil data: {e}")
                data_source = "defaults_parse_error"

        tensor.static = {
            "soil_clay_mean": clay,
            "soil_sand_mean": sand,
            "soil_silt_mean": silt,
            "soil_ph_mean": ph,
            "soil_org_c_mean": org_c,
            "texture_class": texture_class,
            "data_source": data_source
        }

    def _merge_forecast_7d(self, tensor: "FieldTensor", evidence: List["EvidenceItem"]):
        """Step 8: Weather forecast mapping"""
        fc_items = [e for e in evidence if e.source_type == EvidenceSourceType.WEATHER_FORECAST]
        for e in fc_items:
            tensor.forecast_7d.append(e.payload)

    # ==================================================================
    # LAYER 0: Daily State Assimilation (Kalman Engine Integration)
    # ==================================================================

    def _run_layer0_assimilation(
        self,
        tensor: "FieldTensor",
        evidence: list,
        daily_records: list,
        start_date: str,
        end_date: str,
        tracker=None
    ) -> None:
        """
        Orchestrates daily state assimilation.
        If `self.use_modern_layer0_state_engine` is True, uses the modern `Layer0StateEngine`.
        Otherwise, or upon failure, falls back to the legacy Kalman-based DailyAssimilationEngine.
        """
        if self.use_modern_layer0_state_engine:
            try:
                print("[Layer 0] Delegating daily state assimilation to Layer0StateEngine (Modern)")
                from layer0.state_engine import Layer0StateEngine
                state_engine = Layer0StateEngine()
                
                # 1. Build daily weather dict from daily_records + evidence
                daily_weather = {}
                for rec in daily_records:
                    d = rec.get("date")
                    if not d:
                        continue
                    tmean = rec.get("tmean", 20.0)
                    rain = rec.get("rain", 0.0)
                    et0 = rec.get("et0", 3.0)
                    tmax = rec.get("temp_max")
                    tmin = rec.get("temp_min")
                    daily_weather[d] = {
                        "temp_max": float(tmax) if tmax is not None else tmean + 5.0,
                        "temp_min": float(tmin) if tmin is not None else tmean - 5.0,
                        "precipitation": rain,
                        "et0": float(et0) if et0 is not None else 3.0,
                    }
                
                for e in evidence:
                    if e.source_type == EvidenceSourceType.WEATHER and e.timestamp:
                        d = e.timestamp.strftime("%Y-%m-%d")
                        p = e.payload or {}
                        if d in daily_weather:
                            if p.get("temperature_max") is not None:
                                daily_weather[d]["temp_max"] = float(p["temperature_max"])
                            if p.get("temperature_min") is not None:
                                daily_weather[d]["temp_min"] = float(p["temperature_min"])
                            if p.get("et0") is not None:
                                daily_weather[d]["et0"] = float(p["et0"])
                
                # 2. Build events from user evidence
                events_by_day = {}
                for e in evidence:
                    if e.source_type == EvidenceSourceType.USER_EVENT and e.timestamp:
                        d = e.timestamp.strftime("%Y-%m-%d")
                        if d not in events_by_day:
                            events_by_day[d] = []
                        events_by_day[d].append(e.payload or {})
                
                # 3. Build observations per zone per day
                zone_id = "plot"
                all_observations = {}
                for e in evidence:
                    if e.source_type == EvidenceSourceType.SATELLITE_OPTICAL and e.timestamp:
                        d = e.timestamp.strftime("%Y-%m-%d")
                        ndvi = e.payload.get("ndvi")
                        if ndvi is not None:
                            try:
                                ndvi_val = float(ndvi)
                            except (TypeError, ValueError):
                                continue
                            if d not in all_observations:
                                all_observations[d] = {}
                            if zone_id not in all_observations[d]:
                                all_observations[d][zone_id] = []
                            cloud = e.payload.get("cloud_cover", 0)
                            reliability = max(0.1, 1.0 - float(cloud or 0) / 100.0)
                            all_observations[d][zone_id].append(
                                KalmanObservation(
                                    obs_type="ndvi",
                                    value=ndvi_val,
                                    sigma=0.02,
                                    reliability=reliability,
                                    source="sentinel2",
                                )
                            )
                            ndmi = e.payload.get("ndmi")
                            if ndmi is not None:
                                try:
                                    all_observations[d][zone_id].append(
                                        KalmanObservation(
                                            obs_type="ndmi",
                                            value=float(ndmi),
                                            sigma=0.04,
                                            reliability=reliability,
                                            source="sentinel2",
                                        )
                                    )
                                except (TypeError, ValueError):
                                    pass
                for e in evidence:
                    if e.source_type == EvidenceSourceType.SATELLITE_SAR and e.timestamp:
                        d = e.timestamp.strftime("%Y-%m-%d")
                        vv = e.payload.get("vv_db", e.payload.get("vv"))
                        vh = e.payload.get("vh_db", e.payload.get("vh"))
                        if d not in all_observations:
                            all_observations[d] = {}
                        if zone_id not in all_observations[d]:
                            all_observations[d][zone_id] = []
                        if vv is not None:
                            try:
                                all_observations[d][zone_id].append(
                                    KalmanObservation(
                                        obs_type="vv",
                                        value=float(vv),
                                        sigma=1.5,
                                        reliability=1.0,
                                        source="sentinel1",
                                    )
                                )
                            except (TypeError, ValueError):
                                pass
                        if vh is not None:
                            try:
                                all_observations[d][zone_id].append(
                                    KalmanObservation(
                                        obs_type="vh",
                                        value=float(vh),
                                        sigma=2.0,
                                        reliability=1.0,
                                        source="sentinel1",
                                    )
                                )
                            except (TypeError, ValueError):
                                pass
                
                # 4. Extract soil priors
                soil_props = None
                for e in evidence:
                    if e.source_type == EvidenceSourceType.SOIL:
                        raw = e.payload or {}
                        soil_props = {
                            "clay_pct": raw.get("clay", 25),
                            "sand_pct": raw.get("sand", raw.get("sand_percent", 40)),
                        }
                        break
                
                # 5. Extract extra zone IDs
                zone_ids = list(tensor.zones) if tensor.zones else []
                
                # 6. Run state engine with deterministic run_timestamp
                from datetime import datetime as _dt
                from datetime import timezone as _tz
                run_timestamp = _dt.now(_tz.utc)
                state_package = state_engine.run(
                    plot_id=tensor.plot_id,
                    start_date=start_date,
                    end_date=end_date,
                    daily_weather=daily_weather,
                    observations_by_day=all_observations,
                    events_by_day=events_by_day,
                    soil_props=soil_props,
                    zone_ids=zone_ids,
                    geometry_hash=tensor.boundary_info.get("geometry_hash", "") if tensor.boundary_info else "",
                    geometry_version=tensor.boundary_info.get("geometry_version") if tensor.boundary_info else None,
                    run_timestamp=run_timestamp,
                )
                
                # 7. Write outputs to tensor
                tensor.daily_state = state_package.daily_state
                tensor.state_uncertainty = state_package.state_uncertainty
                tensor.provenance_log = state_package.provenance.get("provenance_log", [])
                
                # Cross-source validation summary
                if state_package.validation_conflicts:
                    tensor.provenance["layer0_conflicts"] = state_package.validation_conflicts
                if state_package.health_report and "source_reliability" in state_package.health_report:
                    tensor.provenance["layer0_reliability"] = state_package.health_report["source_reliability"]
                
                # Re-run self audit and invariants locally or map audit report
                if state_package.health_report and "audit" in state_package.health_report:
                    tensor.provenance["audit"] = state_package.health_report["audit"]
                
                # Set boundary info placeholder
                tensor.boundary_info = {
                    "source": "user_drawn",
                    "confidence": 0.8,
                    "note": "PlotGrid fractional alpha available via layer0.plot_grid"
                }
                
                # Log event in tracker
                if tracker:
                    tracker.log_event(
                        "LAYER0_ASSIMILATION",
                        metadata={
                            "zones": list(state_package.daily_state.keys()),
                            "days": len(tensor.provenance_log),
                            "obs_days": state_package.health_report.get("obs_days", 0) if state_package.health_report else 0,
                        }
                    )
                
                # Run invariant checks
                try:
                    time_index = [d.get("day", "") for d in tensor.provenance_log]
                    violations = enforce_all_invariants(
                        tensor.daily_state,
                        tensor.state_uncertainty,
                        tensor.provenance_log,
                        time_index,
                        source_reliability=tensor.provenance.get("layer0_reliability"),
                        auto_fix=True,
                    )
                    if violations:
                        tensor.provenance["invariant_violations"] = [v.to_dict() for v in violations]
                        n_fixed = sum(1 for v in violations if v.auto_fixed)
                        print(f"[Layer 0] Invariants (Modern): {len(violations)} issues ({n_fixed} auto-fixed)")
                except Exception as ie:
                    print(f"[WARN] [Layer 0] Invariant check failed: {ie}")
                
                # Persist engine state for continuity
                try:
                    kalman_zones = {}
                    for z_id in tensor.daily_state:
                        kalman_zones[z_id] = {
                            "state_values": tensor.daily_state[z_id][-1] if tensor.daily_state[z_id] else {},
                            "last_day": end_date,
                        }
                    vg_state = {}
                    state_dir = os.path.join(os.path.dirname(__file__), "..", "layer0", ".state")
                    save_engine_state(
                        plot_id=tensor.plot_id,
                        state_dir=state_dir,
                        kalman_zones=kalman_zones,
                        validation_state=vg_state,
                    )
                except Exception as pe:
                    print(f"[WARN] [Layer 0] State persist failed: {pe}")
                
                print("[OK] [Layer 0] Daily state assimilation (Modern) complete")
                return
            except Exception as ex:
                import traceback
                print(f"[WARN] [Layer 0] Modern state engine failed: {ex}")
                traceback.print_exc()
                if self.allow_legacy_layer0_fallback:
                    print("[WARN] [Layer 0] Modern state engine failed. Falling back to legacy Kalman-based DailyAssimilationEngine...")
                else:
                    raise ex
        
        # Dispatch to legacy body
        self._run_layer0_assimilation_legacy(
            tensor, evidence, daily_records, start_date, end_date, tracker
        )

    def _run_layer0_assimilation_legacy(
        self,
        tensor: "FieldTensor",
        evidence: list,
        daily_records: list,
        start_date: str,
        end_date: str,
        tracker=None
    ) -> None:
        """
        Run Layer 0 Kalman-based daily state estimation.

        Converts EvidenceItems into:
          A) daily_weather  — plot-level drivers (NOT fake 10m weather)
          B) events_by_day  — user management events as state constraints
          C) zone_observations — per-zone KalmanObservations from S2/S1

        Then runs DailyAssimilationEngine and writes outputs
        (daily_state, state_uncertainty, provenance_log) into the tensor.
        """
        # ---- A) Build daily weather dict from weather evidence ----
        # Use real temp_max/temp_min from Open-Meteo (no synthetic ±5°C)
        daily_weather = {}
        for rec in daily_records:
            d = rec.get("date")
            if not d:
                continue
            tmean = rec.get("tmean", 20.0)
            rain = rec.get("rain", 0.0)
            et0 = rec.get("et0", 3.0)
            # Use real temp extremes if available, otherwise derive from tmean
            tmax = rec.get("temp_max")
            tmin = rec.get("temp_min")
            daily_weather[d] = {
                "temp_max": float(tmax) if tmax is not None else tmean + 5.0,
                "temp_min": float(tmin) if tmin is not None else tmean - 5.0,
                "precipitation": rain,
                "et0": float(et0) if et0 is not None else 3.0,
            }
        
        # If weather evidence has explicit temp_max/min, always prefer them
        for e in evidence:
            if e.source_type == EvidenceSourceType.WEATHER and e.timestamp:
                d = e.timestamp.strftime("%Y-%m-%d")
                p = e.payload or {}
                if d in daily_weather:
                    if p.get("temperature_max") is not None:
                        daily_weather[d]["temp_max"] = float(p["temperature_max"])
                    if p.get("temperature_min") is not None:
                        daily_weather[d]["temp_min"] = float(p["temperature_min"])
                    if p.get("et0") is not None:
                        daily_weather[d]["et0"] = float(p["et0"])

        # ---- B) Build events from user evidence ----
        events_by_day = {}
        for e in evidence:
            if e.source_type == EvidenceSourceType.USER_EVENT and e.timestamp:
                d = e.timestamp.strftime("%Y-%m-%d")
                if d not in events_by_day:
                    events_by_day[d] = []
                events_by_day[d].append(e.payload or {})

        # ---- C) Build observations per zone per day ----
        # For now: single-zone fallback ("plot") using plot-level means.
        # When zone segmentation exists, this expands to per-zone α-weighted means.
        zone_id = "plot"

        all_observations = {}  # {day: {zone_id: [KalmanObservation, ...]}}

        # C.1) Optical observations (S2 → NDVI)
        for e in evidence:
            if e.source_type == EvidenceSourceType.SATELLITE_OPTICAL and e.timestamp:
                d = e.timestamp.strftime("%Y-%m-%d")
                ndvi = e.payload.get("ndvi")
                if ndvi is not None:
                    try:
                        ndvi_val = float(ndvi)
                    except (TypeError, ValueError):
                        continue

                    if d not in all_observations:
                        all_observations[d] = {}
                    if zone_id not in all_observations[d]:
                        all_observations[d][zone_id] = []

                    # Cloud cover → reliability
                    cloud = e.payload.get("cloud_cover", 0)
                    reliability = max(0.1, 1.0 - float(cloud or 0) / 100.0)

                    all_observations[d][zone_id].append(
                        KalmanObservation(
                            obs_type="ndvi",
                            value=ndvi_val,
                            sigma=0.02,
                            reliability=reliability,
                            source="sentinel2",
                        )
                    )

                    # Also add NDMI if available
                    ndmi = e.payload.get("ndmi")
                    if ndmi is not None:
                        try:
                            all_observations[d][zone_id].append(
                                KalmanObservation(
                                    obs_type="ndmi",
                                    value=float(ndmi),
                                    sigma=0.04,
                                    reliability=reliability,
                                    source="sentinel2",
                                )
                            )
                        except (TypeError, ValueError):
                            pass

        # C.2) SAR observations (S1 → VV, VH)
        for e in evidence:
            if e.source_type == EvidenceSourceType.SATELLITE_SAR and e.timestamp:
                d = e.timestamp.strftime("%Y-%m-%d")
                vv = e.payload.get("vv_db", e.payload.get("vv"))
                vh = e.payload.get("vh_db", e.payload.get("vh"))

                if d not in all_observations:
                    all_observations[d] = {}
                if zone_id not in all_observations[d]:
                    all_observations[d][zone_id] = []

                if vv is not None:
                    try:
                        all_observations[d][zone_id].append(
                            KalmanObservation(
                                obs_type="vv",
                                value=float(vv),
                                sigma=1.5,
                                reliability=1.0,  # SAR is cloud-independent
                                source="sentinel1",
                            )
                        )
                    except (TypeError, ValueError):
                        pass

                if vh is not None:
                    try:
                        all_observations[d][zone_id].append(
                            KalmanObservation(
                                obs_type="vh",
                                value=float(vh),
                                sigma=2.0,
                                reliability=1.0,
                                source="sentinel1",
                            )
                        )
                    except (TypeError, ValueError):
                        pass

        # ---- D) Extract soil priors ----
        soil_props = None
        for e in evidence:
            if e.source_type == EvidenceSourceType.SOIL:
                raw = e.payload or {}
                soil_props = {
                    "clay_pct": raw.get("clay", 25),
                    "sand_pct": raw.get("sand", raw.get("sand_percent", 40)),
                }
                break

        # ---- E) Initialize and run assimilation ----
        engine = DailyAssimilationEngine()
        engine.add_zone(zone_id, soil_props=soil_props, start_day=start_date)

        # If existing zone segmentation exists in tensor, add those zones too
        if tensor.zones:
            for zid in tensor.zones:
                if zid != zone_id:
                    engine.add_zone(zid, soil_props=soil_props, start_day=start_date)
                    # Duplicate plot-level obs for each zone (until we have α-weighted per-zone)
                    for d, zone_obs in all_observations.items():
                        if zone_id in zone_obs and zid not in zone_obs:
                            zone_obs[zid] = zone_obs[zone_id]

        engine.run_period(
            start_date, end_date,
            daily_weather, all_observations, events_by_day
        )

        # ---- F) Write outputs into FieldTensor ----
        daily_state, state_uncertainty, provenance_log = engine.to_field_tensor_outputs()
        tensor.daily_state = daily_state
        tensor.state_uncertainty = state_uncertainty
        tensor.provenance_log = provenance_log

        # ---- G) Cross-source validation (closed loop) ----
        try:
            validator = ValidationGraph()
            for d_rec in provenance_log:
                day = d_rec.get("day", "")
                for zid, zdata in d_rec.get("zones", {}).items():
                    state_dict = zdata.get("state", {})
                    # Build obs dict for this day/zone
                    obs_dict = {}
                    day_obs = all_observations.get(day, {}).get(zid, [])
                    for o in day_obs:
                        obs_dict[o.obs_type] = o.value
                    wx = daily_weather.get(day, {})

                    validator.validate_day(
                        day, zid, state_dict, obs_dict, wx
                    )

            # Store conflict summary in provenance
            conflicts = validator.get_conflict_summary(last_n_days=len(provenance_log))
            if conflicts:
                tensor.provenance["layer0_conflicts"] = conflicts
                tensor.provenance["layer0_reliability"] = dict(validator.source_reliability)
        except Exception as ve:
            print(f"[WARN] [Layer 0] Validation graph failed: {ve}")

        # ---- H) Boundary info placeholder ----
        tensor.boundary_info = {
            "source": "user_drawn",
            "confidence": 0.8,
            "note": "PlotGrid fractional alpha available via layer0.plot_grid"
        }

        if tracker:
            tracker.log_event(
                "LAYER0_ASSIMILATION",
                metadata={
                    "zones": list(daily_state.keys()),
                    "days": len(provenance_log),
                    "obs_days": sum(
                        1 for d in provenance_log
                        for zd in d.get("zones", {}).values()
                        if zd.get("provenance", {}).get("n_obs", 0) > 0
                    ),
                }
            )

        # ---- I) Self-Audit: Trust Report + Structural Checks ----
        try:
            from datetime import datetime as _dt
            d1 = _dt.strptime(start_date, "%Y-%m-%d")
            d2 = _dt.strptime(end_date, "%Y-%m-%d")
            expected_days = (d2 - d1).days + 1

            audit_result = layer0_audit(
                plot_id=tensor.plot_id,
                tensor_daily_state=tensor.daily_state,
                tensor_state_uncertainty=tensor.state_uncertainty,
                tensor_provenance_log=tensor.provenance_log,
                tensor_boundary_info=tensor.boundary_info,
                source_reliability=tensor.provenance.get("layer0_reliability"),
                conflicts=tensor.provenance.get("layer0_conflicts"),
                expected_days=expected_days,
            )
            tensor.provenance["audit"] = audit_result

            grade = audit_result.get("trust_report", {}).get("health_grade", "?")
            score = audit_result.get("trust_report", {}).get("health_score", 0)
            alerts = audit_result.get("trust_report", {}).get("alerts", [])
            print(f"[Layer 0] Audit: Grade={grade} Score={score:.2f} Alerts={len(alerts)}")
        except Exception as ae:
            print(f"[WARN] [Layer 0] Audit failed: {ae}")

        # ---- J) Runtime Invariants — auto-clamp + log violations ----
        try:
            time_index = [d.get("day", "") for d in provenance_log]
            violations = enforce_all_invariants(
                tensor.daily_state,
                tensor.state_uncertainty,
                tensor.provenance_log,
                time_index,
                source_reliability=tensor.provenance.get("layer0_reliability"),
                auto_fix=True,
            )
            if violations:
                tensor.provenance["invariant_violations"] = [v.to_dict() for v in violations]
                n_fixed = sum(1 for v in violations if v.auto_fixed)
                print(f"[Layer 0] Invariants: {len(violations)} issues ({n_fixed} auto-fixed)")
        except Exception as ie:
            print(f"[WARN] [Layer 0] Invariant check failed: {ie}")

        # ---- K) Persist engine state for continuity ----
        try:
            kalman_zones = {}
            for z_id in daily_state:
                kalman_zones[z_id] = {
                    "state_values": daily_state[z_id][-1] if daily_state[z_id] else {},
                    "last_day": end_date,
                }
            vg_state = validator.to_state_dict() if validator else {}
            state_dir = os.path.join(os.path.dirname(__file__), "..", "layer0", ".state")
            save_engine_state(
                plot_id=tensor.plot_id,
                state_dir=state_dir,
                kalman_zones=kalman_zones,
                validation_state=vg_state,
            )
        except Exception as pe:
            print(f"[WARN] [Layer 0] State persist failed: {pe}")

    def _generate_health_report(self, evidence_pool: List["EvidenceItem"], records: List[Dict]) -> Dict:
        """Step 9: Monitoring & QA"""
        total_days = len(records)
        obs_days = sum(1 for r in records if r.get("is_observed"))

        flagged_cnt = sum(1 for e in evidence_pool if e.status == ValidationStatus.FLAGGED)
        rejected_cnt = sum(1 for e in evidence_pool if e.status == ValidationStatus.REJECTED)

        # Data completeness: observed fraction (optical)
        completeness = round(obs_days / total_days, 2) if total_days > 0 else 0.0

        return {
            "completeness_score": completeness,
            "optical_coverage_days": int(obs_days),
            "flagged_items": int(flagged_cnt),
            "rejected_items": int(rejected_cnt),
            "data_health_alert": "Low optical coverage" if obs_days < 2 else "Healthy"
        }


# Singleton
fusion_engine = DataFusionEngine()
