"""
Layer 1.1: Multi-Source Data Fusion Engine (Production Spec)
Implements the 8-Step Fusion Pipeline with Evidence Validation.
Supports degradation to Pure Python if Pandas/Numpy are missing.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import sys
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
    from eo.sentinel import (
        fetch_ndvi_timeseries,  # Updated import
        fetch_sar_timeseries,
        fetch_historical_weather,
        fetch_soil_properties
    )
    from layer1_fusion.corrections import correction_engine
    from layer1_fusion.schema import (
        FieldTensor, EvidenceItem, EvidenceSourceType,
        ValidationStatus, FusionOutput, FieldTensorChannels
    )
    from services.agribrain.layer1_fusion.raster_backend import TileStoreBackend, RasterioBackend
    from services.agribrain.layer1_fusion.validation.validator import trust_system
except ImportError:
    # Fallback for linting/mocking
    fetch_ndvi_timeseries = lambda *args, **kwargs: {}
    fetch_sar_timeseries = lambda *args, **kwargs: {}
    fetch_historical_weather = lambda *args, **kwargs: {}
    fetch_soil_properties = lambda *args, **kwargs: {}
    correction_engine = None
    trust_system = None


class DataFusionEngine:
    """
    Production Pipeline with Fallback.
    """

    def __init__(self):
        # NOTE: resolution must be produced by backend in meters (projected CRS).
        # Keep attribute for backwards compatibility, but we don't use it as a CRS unit anymore.
        self.DEFAULT_GRID_RES = None

    def fuse_data(
        self,
        plot_id: str,
        lat: float,
        lng: float,
        start_date: str,
        end_date: str
    ) -> FusionOutput:

        # --- Step 0: Initialize Provenance ---
        # Deterministic Run ID
        from services.agribrain.layer1_fusion.provenance import ProvenanceTracker, generate_run_id

        # Hash params + inputs (simplification for MVP: just timestamps)
        run_id = generate_run_id(plot_id, start_date, end_date, "params_v1", "code_v2.0.0")

        tracker = ProvenanceTracker(run_id)
        tracker.log_event("START_RUN", metadata={"plot_id": plot_id, "start": start_date, "end": end_date})

        mode = "Pandas" if HAS_PANDAS else "PurePython"
        print(f"🔄 [Layer 1] Starting Production Fusion Run: {run_id} ({mode} Mode)")

        # --- Step 1: Acquire Evidence (Catalog) ---
        evidence_pool, acquisition_snapshot = self._acquire_all_evidence(lat, lng, start_date, end_date)

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

        # Attach plot timeseries
        tensor.plot_timeseries = daily_records

        # 5. Spatial Fusion (build tensor.data from daily_records — now includes rain)
        self._perform_spatial_fusion(tensor, daily_records, run_id=run_id)

        # 7. Static Layers
        self._merge_static(tensor, valid_evidence)

        # --- Step 8: Finalize Artifacts ---
        summary = [e.to_dict() for e in evidence_pool]
        report = self._generate_health_report(evidence_pool, daily_records)

        tracker.log_event(
            "GENERATED_TENSOR",
            inputs=[e.id for e in valid_evidence],
            metadata={"shape": tensor.get_shape()}
        )

        # Attach Provenance (Now includes GENERATED_TENSOR)
        tensor.provenance = {
            "run_id": run_id,
            "lineage": tracker.export_lineage(),
            "acquisition_diagnostics": acquisition_snapshot,
            "tracker_stats": {
                "events_count": len(tracker.events),
                "duration_ms": 0.0
            }
        }

        print(f"✅ [Layer 1] Fusion Complete. Run ID: {run_id}")

        return FusionOutput(
            tensor=tensor,
            evidence_summary=summary,
            validation_report=report,
            logs=tracker.export_lineage()
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

    def _acquire_all_evidence(self, lat: float, lng: float, start: str, end: str) -> tuple[List["EvidenceItem"], Dict[str, Any]]:
        pool: List[EvidenceItem] = []
        snapshot: Dict[str, Any] = {"sar": {}, "optical": {}, "weather": {}}

        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")

        # 1. Optical (Sentinel-2)
        try:
            opt_resp = fetch_ndvi_timeseries(lat, lng)
            opt_raw = opt_resp.get("data", []) or []
            snapshot["optical"] = {
                "status": "OK",
                "count": len(opt_raw),
                "keys_seen": list(opt_resp.keys()) if isinstance(opt_resp, dict) else [],
                "sample_keys": list(opt_raw[0].keys()) if opt_raw else []
            }
        except Exception as e:
            opt_raw = []
            snapshot["optical"] = {"status": "ERROR", "error": str(e)}

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

        # 2. SAR (Sentinel-1) — respect requested window
        sar_days = max(1, (end_dt - start_dt).days + 1)
        
        try:
            sar_resp = fetch_sar_timeseries(lat, lng, days=sar_days) or {}
            sar_raw = sar_resp.get("timeseries", []) or sar_resp.get("data", []) or []  # accept both shapes
            
            snapshot["sar"] = {
                "status": "OK",
                "count": len(sar_raw),
                "keys_seen": list(sar_resp.keys()) if isinstance(sar_resp, dict) else [],
                "params": {"lat": lat, "lng": lng, "days": sar_days},
                "provider": "earthengine-api" # Assumption
            }
            if not sar_raw and "error" in sar_resp:
                 snapshot["sar"]["provider_error"] = sar_resp["error"]

        except Exception as e:
            sar_raw = []
            snapshot["sar"] = {"status": "ERROR", "error": str(e)}

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

        # 3. Weather (modeled)
        try:
            wx_raw = fetch_historical_weather(lat, lng, start, end)
            snapshot["weather"] = {"status": "OK", "keys": list(wx_raw.keys()) if isinstance(wx_raw, dict) else []}
        except Exception as e:
            wx_raw = {}
            snapshot["weather"] = {"status": "ERROR", "error": str(e)}

        if wx_raw:
            # New schema: "records"
            if "records" in wx_raw:
                for rec in wx_raw.get("records", []):
                    t = rec.get("date")
                    ts = self._safe_parse_date(t)
                    if not self._in_range(ts, start_dt, end_dt):
                        continue

                    payload = {
                        "date": t,
                        "temperature_mean": rec.get("temp_mean"),
                        "precipitation": rec.get("precipitation"),
                        "rain": rec.get("rain"),
                        "et0": rec.get("et0"),
                    }

                    pool.append(EvidenceItem(
                        id=f"wx_{t}",
                        source_type=EvidenceSourceType.WEATHER,
                        timestamp=ts,
                        location_scope="point",
                        payload=payload
                    ))

            # Old schema support (if "daily")
            elif "daily" in wx_raw:
                d = wx_raw.get("daily", {}) or {}
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

        # 4. Soil (Static)
        try:
            soil_raw = fetch_soil_properties(lat, lng)
        except Exception:
            soil_raw = {}
            
        if soil_raw:
            pool.append(EvidenceItem(
                id=f"soil_grids_static_{self._hash_payload(soil_raw)}",
                source_type=EvidenceSourceType.SOIL,
                timestamp=datetime.now(),
                location_scope="point",
                payload=soil_raw
            ))

        return pool, snapshot

    def _perform_temporal_fusion_pandas(self, date_strs: List[str], evidence: List["EvidenceItem"]) -> List[Dict]:
        """High-Performance implementation using Pandas. Fuses optical + SAR (plot-level)."""
        idx = pd.to_datetime(date_strs)
        df = pd.DataFrame(index=idx)
        df.index.name = "date"

        # --- Optical (NDVI) ---
        opt_items = [e for e in evidence if e.source_type == EvidenceSourceType.SATELLITE_OPTICAL]
        opt_data = {}
        for item in opt_items:
            dt = pd.to_datetime(item.timestamp)
            if dt in df.index:
                opt_data[dt] = {
                    "ndvi_mean": item.payload.get("ndvi", np.nan),
                    "coverage": (100 - item.payload.get("cloud_cover", 0)) / 100.0
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
                    "vv": item.payload.get("vv", np.nan),
                    "vh": item.payload.get("vh", np.nan)
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

        # Prepare records
        df = df.reset_index()
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        return df.to_dict("records")

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
                        "vv": e.payload.get("vv"),
                        "vh": e.payload.get("vh")
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

    def _perform_spatial_fusion(self, tensor: "FieldTensor", daily_records: List[Dict], run_id: str):
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
            print("🗺️ [Spatial] Using RasterioBackend (Scientific Mode)")
        except ImportError:
            backend = TileStoreBackend()
            print("⚠️ [Spatial] Rasterio not found. Using TileStoreBackend (Restricted Mode)")

        # Create GridSpec from Plot Geometry (still mocked here; replace with real polygon by plot_id in your repo)
        mock_polygon = [
            (3.05, 36.75), (3.051, 36.75), (3.051, 36.751), (3.05, 36.751), (3.05, 36.75)
        ]
        tensor.grid_spec = backend.create_grid(mock_polygon, resolution_m=10.0)

        w = tensor.grid_spec.width
        h = tensor.grid_spec.height

        channels = tensor.channels
        c_map = {c: i for i, c in enumerate(channels)}

        # Deterministic "noise" (optional) based on run_id/date/x/y so it is reproducible
        def deterministic_noise(day: str, x: int, y: int) -> float:
            seed_raw = f"{run_id}|{day}|{x}|{y}".encode("utf-8")
            hv = hashlib.sha256(seed_raw).digest()
            # map first byte to [-0.05, +0.05]
            return ((hv[0] / 255.0) - 0.5) * 0.1

        tensor_data: List[Any] = []  # [T][H][W][C]

        for row in daily_records:
            day = row.get("date", "")
            t_grid = []  # [H][W][C]

            ndvi = row.get("ndvi_smoothed", 0.0) or 0.0
            vv = row.get("vv_interpolated", row.get("vv", 0.0)) or 0.0
            vh = row.get("vh_interpolated", row.get("vh", 0.0)) or 0.0
            rain = row.get("rain", 0.0) or 0.0
            unc = row.get("uncertainty", 0.5) if row.get("uncertainty") is not None else 0.5

            for y in range(h):
                row_grid = []
                for x in range(w):
                    pixel = [0.0] * len(channels)

                    n = deterministic_noise(day, x, y)

                    if FieldTensorChannels.NDVI in c_map:
                        pixel[c_map[FieldTensorChannels.NDVI]] = max(-1.0, min(1.0, float(ndvi) + n))

                    if FieldTensorChannels.NDVI_UNC in c_map:
                        pixel[c_map[FieldTensorChannels.NDVI_UNC]] = float(unc)

                    if FieldTensorChannels.PRECIPITATION in c_map:
                        pixel[c_map[FieldTensorChannels.PRECIPITATION]] = float(rain)

                    # Populate SAR channels if present in enum
                    if hasattr(FieldTensorChannels, "VV") and FieldTensorChannels.VV in c_map:
                        pixel[c_map[FieldTensorChannels.VV]] = float(vv)
                    if hasattr(FieldTensorChannels, "VH") and FieldTensorChannels.VH in c_map:
                        pixel[c_map[FieldTensorChannels.VH]] = float(vh)

                    row_grid.append(pixel)
                t_grid.append(row_grid)
            tensor_data.append(t_grid)

        tensor.data = tensor_data

    def _merge_weather_into_records(self, records: List[Dict], evidence: List["EvidenceItem"]):
        """Step 6: Weather Fusion into daily records BEFORE tensor build."""
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
                row["rain"] = float(rain) if rain is not None else 0.0
                row["tmean"] = float(tmean) if tmean is not None else 20.0
                # Pure Python GDD (base 10C default; crop-specific base can be added later)
                row["gdd"] = max(0.0, row["tmean"] - 10.0)
            else:
                # Ensure keys exist for downstream consumers
                row.setdefault("rain", 0.0)
                row.setdefault("tmean", 20.0)
                row.setdefault("gdd", max(0.0, row["tmean"] - 10.0))

    def _merge_static(self, tensor: "FieldTensor", evidence: List["EvidenceItem"]):
        """Step 7: Static Layers"""
        soil_items = [e for e in evidence if e.source_type == EvidenceSourceType.SOIL]
        if soil_items:
            best = soil_items[0]
            raw = best.payload or {}
            tensor.static = {
                "soil_clay_mean": raw.get("clay", 20),
                "soil_ph_mean": raw.get("ph", 6.5),
                "soil_org_c_mean": raw.get("organic_carbon", 10),
                "texture_class": raw.get("texture_class", "unknown")
            }

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
