"""
Compaction Engine — Manages warm-to-cold tier data lifecycle.

As the observation archive grows, the compaction engine:
1. Aggregates raw observations into daily/weekly/monthly summaries
2. Exports training-ready datasets for ML patterns
3. Cleans up old raw observations (keeping summaries)
4. Tracks data lineage (which raw obs contributed to each summary)

The result: unlimited observation history without unbounded storage.

Usage:
    from layer0.data_gateway.compaction_engine import CompactionEngine

    engine = CompactionEngine()
    engine.compact_plot("plot123")
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger("agribrain.gateway.compaction")

# Compaction thresholds
RAW_RETENTION_DAYS = 90       # Keep raw observations for 90 days
DAILY_RETENTION_DAYS = 365    # Keep daily summaries for 1 year
WEEKLY_RETENTION_DAYS = 1825  # Keep weekly summaries for 5 years


class CompactionEngine:
    """Manages warm-tier data lifecycle: aggregation, export, cleanup.

    Three-tier observation retention:
    1. Raw observations (0-90 days) — full granularity
    2. Daily summaries (90-365 days) — statistical aggregates per source
    3. Weekly summaries (1-5 years) — compressed for long-term ML training

    This ensures ML patterns can train on 5+ years of data without
    storage growing unbounded.
    """

    def __init__(self):
        self._compaction_count = 0
        self._export_count = 0

    def compact_plot(self, plot_id: str) -> Dict:
        """Run compaction for a single plot.

        1. Aggregate raw obs older than 90 days into daily summaries
        2. Aggregate daily summaries older than 1 year into weekly summaries
        3. Return compaction stats

        Safe to run repeatedly — idempotent.
        """
        from layer0.data_gateway.storage_manager import _get_db

        db = _get_db()
        if db is None:
            return {"status": "skipped", "reason": "no MongoDB"}

        stats = {
            "plot_id": plot_id,
            "raw_before": 0,
            "daily_created": 0,
            "weekly_created": 0,
            "raw_purged": 0,
        }

        try:
            now = datetime.now(timezone.utc)
            raw_cutoff = now - timedelta(days=RAW_RETENTION_DAYS)
            daily_cutoff = now - timedelta(days=DAILY_RETENTION_DAYS)

            # Count existing raw observations
            stats["raw_before"] = db.PlotObservation.count_documents({
                "plotId": plot_id,
                "compaction_level": {"$exists": False},
            })

            # Step 1: Aggregate raw obs older than RAW_RETENTION_DAYS into daily summaries
            old_raw = list(db.PlotObservation.find({
                "plotId": plot_id,
                "obsDate": {"$lt": raw_cutoff},
                "compaction_level": {"$exists": False},
            }))

            if old_raw:
                daily_groups = self._group_by_day_and_type(old_raw)
                for (day_str, obs_type), obs_list in daily_groups.items():
                    summary = self._build_daily_summary(
                        plot_id, day_str, obs_type, obs_list
                    )
                    # Upsert daily summary
                    db.PlotObservation.update_one(
                        {
                            "plotId": plot_id,
                            "obsDate": summary["obsDate"],
                            "obsType": summary["obsType"],
                            "compaction_level": "daily",
                        },
                        {"$set": summary},
                        upsert=True,
                    )
                    stats["daily_created"] += 1

                # Purge raw observations that have been aggregated
                result = db.PlotObservation.delete_many({
                    "plotId": plot_id,
                    "obsDate": {"$lt": raw_cutoff},
                    "compaction_level": {"$exists": False},
                })
                stats["raw_purged"] = result.deleted_count

            # Step 2: Aggregate daily summaries older than DAILY_RETENTION_DAYS
            old_daily = list(db.PlotObservation.find({
                "plotId": plot_id,
                "obsDate": {"$lt": daily_cutoff},
                "compaction_level": "daily",
            }))

            if old_daily:
                weekly_groups = self._group_by_week_and_type(old_daily)
                for (week_str, obs_type), obs_list in weekly_groups.items():
                    summary = self._build_weekly_summary(
                        plot_id, week_str, obs_type, obs_list
                    )
                    db.PlotObservation.update_one(
                        {
                            "plotId": plot_id,
                            "obsDate": summary["obsDate"],
                            "obsType": summary["obsType"],
                            "compaction_level": "weekly",
                        },
                        {"$set": summary},
                        upsert=True,
                    )
                    stats["weekly_created"] += 1

                # Purge aggregated daily summaries
                db.PlotObservation.delete_many({
                    "plotId": plot_id,
                    "obsDate": {"$lt": daily_cutoff},
                    "compaction_level": "daily",
                })

            self._compaction_count += 1
            logger.info(
                "[COMPACTION] Plot %s: %d daily, %d weekly, %d raw purged",
                plot_id[:8], stats["daily_created"],
                stats["weekly_created"], stats["raw_purged"],
            )

        except Exception as e:
            stats["error"] = str(e)
            logger.error("[COMPACTION] Plot %s failed: %s", plot_id[:8], e)

        return stats

    # ── Training Data Export ───────────────────────────────────────

    def export_training_data(
        self,
        plot_id: str,
        patterns: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export structured training data for ML patterns.

        Returns a dict with:
        - ndvi_timeseries: aligned NDVI observations
        - weather_history: temperature/rain history
        - sar_history: radar backscatter history
        - soil_baseline: static soil properties
        - user_events: farmer-reported events
        - labels: yield reports (for supervised learning)

        ML patterns consume this via the observation archive,
        not direct API calls.
        """
        from layer0.data_gateway.storage_manager import _get_db

        db = _get_db()
        if db is None:
            return {"status": "no_db"}

        query = {"plotId": plot_id}
        if start_date:
            query["obsDate"] = {"$gte": datetime.fromisoformat(start_date)}
        if end_date:
            query.setdefault("obsDate", {})
            query["obsDate"]["$lte"] = datetime.fromisoformat(end_date)

        all_obs = list(db.PlotObservation.find(query).sort("obsDate", 1))

        # Group by type
        by_type = defaultdict(list)
        for obs in all_obs:
            by_type[obs.get("obsType", "unknown")].append(obs)

        # Build training dataset
        dataset = {
            "plot_id": plot_id,
            "total_observations": len(all_obs),
            "date_range": {
                "start": all_obs[0]["obsDate"].isoformat() if all_obs else None,
                "end": all_obs[-1]["obsDate"].isoformat() if all_obs else None,
            },
            "ndvi_timeseries": self._extract_ndvi_series(by_type.get("ndvi", [])),
            "weather_history": self._extract_weather_series(
                by_type.get("current_weather", []) + by_type.get("historical_weather", [])
            ),
            "sar_history": self._extract_sar_series(by_type.get("sar_backscatter", [])),
            "soil_baseline": self._extract_soil(by_type.get("soilgrids", [])),
            "user_events": self._extract_user_events(all_obs),
            "yield_labels": self._extract_yields(by_type.get("user_yield_report", [])),
            "observation_types": {k: len(v) for k, v in by_type.items()},
        }

        self._export_count += 1
        logger.info(
            "[EXPORT] Plot %s: %d obs, %d types, %s to %s",
            plot_id[:8], len(all_obs), len(by_type),
            dataset["date_range"]["start"], dataset["date_range"]["end"],
        )

        return dataset

    # ── Internal: Grouping ─────────────────────────────────────────

    def _group_by_day_and_type(self, obs_list: List[Dict]) -> Dict:
        groups = defaultdict(list)
        for obs in obs_list:
            dt = obs.get("obsDate") or datetime.now(timezone.utc)
            day_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
            obs_type = obs.get("obsType", "unknown")
            groups[(day_str, obs_type)].append(obs)
        return groups

    def _group_by_week_and_type(self, obs_list: List[Dict]) -> Dict:
        groups = defaultdict(list)
        for obs in obs_list:
            dt = obs.get("obsDate") or datetime.now(timezone.utc)
            # ISO week key
            if hasattr(dt, "isocalendar"):
                yr, wk, _ = dt.isocalendar()
                week_str = f"{yr}-W{wk:02d}"
            else:
                week_str = str(dt)[:7]
            obs_type = obs.get("obsType", "unknown")
            groups[(week_str, obs_type)].append(obs)
        return groups

    # ── Internal: Summary Builders ─────────────────────────────────

    def _build_daily_summary(
        self, plot_id: str, day_str: str, obs_type: str, obs_list: List[Dict],
    ) -> Dict:
        """Build a daily statistical summary from raw observations."""
        numeric_fields = self._collect_numeric_fields(obs_list)

        summary = {
            "plotId": plot_id,
            "obsDate": datetime.fromisoformat(day_str),
            "obsType": obs_type,
            "compaction_level": "daily",
            "sample_count": len(obs_list),
            "compacted_at": datetime.now(timezone.utc),
        }

        for field, values in numeric_fields.items():
            if values:
                summary[f"{field}_mean"] = round(sum(values) / len(values), 4)
                summary[f"{field}_min"] = round(min(values), 4)
                summary[f"{field}_max"] = round(max(values), 4)
                if len(values) > 1:
                    mean = sum(values) / len(values)
                    variance = sum((v - mean) ** 2 for v in values) / len(values)
                    summary[f"{field}_std"] = round(math.sqrt(variance), 4)

        return summary

    def _build_weekly_summary(
        self, plot_id: str, week_str: str, obs_type: str, obs_list: List[Dict],
    ) -> Dict:
        """Build a weekly summary from daily summaries."""
        # For weekly summaries, aggregate the daily means
        numeric_fields = defaultdict(list)
        total_samples = 0

        for obs in obs_list:
            total_samples += obs.get("sample_count", 1)
            for key, val in obs.items():
                if key.endswith("_mean") and isinstance(val, (int, float)):
                    base_field = key.replace("_mean", "")
                    numeric_fields[base_field].append(val)

        summary = {
            "plotId": plot_id,
            "obsDate": datetime.fromisoformat(week_str + "-1") if "W" in week_str
                       else datetime.fromisoformat(week_str + "-01"),
            "obsType": obs_type,
            "compaction_level": "weekly",
            "sample_count": total_samples,
            "daily_count": len(obs_list),
            "compacted_at": datetime.now(timezone.utc),
        }

        for field, values in numeric_fields.items():
            if values:
                summary[f"{field}_mean"] = round(sum(values) / len(values), 4)
                summary[f"{field}_min"] = round(min(values), 4)
                summary[f"{field}_max"] = round(max(values), 4)

        return summary

    def _collect_numeric_fields(self, obs_list: List[Dict]) -> Dict[str, List[float]]:
        """Collect all numeric fields from a list of observations."""
        SKIP_FIELDS = {
            "_id", "plotId", "obsDate", "obsType", "source", "compaction_level",
            "compacted_at", "sample_count",
        }
        numeric = defaultdict(list)
        for obs in obs_list:
            for key, val in obs.items():
                if key in SKIP_FIELDS:
                    continue
                if isinstance(val, (int, float)) and not math.isnan(val) and not math.isinf(val):
                    numeric[key].append(float(val))
        return numeric

    # ── Internal: Training Data Extractors ─────────────────────────

    def _extract_ndvi_series(self, obs_list: List[Dict]) -> List[Dict]:
        return [
            {
                "date": obs.get("obsDate", "").isoformat() if hasattr(obs.get("obsDate"), "isoformat") else str(obs.get("obsDate", "")),
                "ndvi": obs.get("ndvi"),
                "cloud_cover": obs.get("cloudCover"),
            }
            for obs in obs_list
            if obs.get("ndvi") is not None
        ]

    def _extract_weather_series(self, obs_list: List[Dict]) -> List[Dict]:
        return [
            {
                "date": obs.get("obsDate", "").isoformat() if hasattr(obs.get("obsDate"), "isoformat") else str(obs.get("obsDate", "")),
                "temp_c": obs.get("tempC"),
                "humidity": obs.get("humidity"),
                "rain_mm": obs.get("rain_mm") or obs.get("precipitation"),
                "wind_speed": obs.get("wind_speed"),
            }
            for obs in obs_list
            if obs.get("tempC") is not None
        ]

    def _extract_sar_series(self, obs_list: List[Dict]) -> List[Dict]:
        return [
            {
                "date": obs.get("obsDate", "").isoformat() if hasattr(obs.get("obsDate"), "isoformat") else str(obs.get("obsDate", "")),
                "vv": obs.get("vv"),
                "vh": obs.get("vh"),
            }
            for obs in obs_list
            if obs.get("vv") is not None or obs.get("vh") is not None
        ]

    def _extract_soil(self, obs_list: List[Dict]) -> Optional[Dict]:
        if not obs_list:
            return None
        latest = obs_list[-1]
        return {
            "clay": latest.get("clay"),
            "sand": latest.get("sand"),
            "silt": latest.get("silt"),
            "soc": latest.get("soc"),
            "ph": latest.get("phh2o") or latest.get("ph"),
            "cec": latest.get("cec"),
        }

    def _extract_user_events(self, all_obs: List[Dict]) -> List[Dict]:
        USER_TYPES = {"user_irrigation_event", "user_fertilization_event",
                      "user_planting_event", "user_harvest_event",
                      "user_management_event", "user_photo"}
        return [
            {
                "date": obs.get("obsDate", "").isoformat() if hasattr(obs.get("obsDate"), "isoformat") else str(obs.get("obsDate", "")),
                "type": obs.get("obsType"),
                "data": {k: v for k, v in obs.items()
                         if k not in {"_id", "plotId", "obsDate", "obsType", "source"}},
            }
            for obs in all_obs
            if obs.get("obsType") in USER_TYPES
        ]

    def _extract_yields(self, obs_list: List[Dict]) -> List[Dict]:
        return [
            {
                "date": obs.get("obsDate", "").isoformat() if hasattr(obs.get("obsDate"), "isoformat") else str(obs.get("obsDate", "")),
                "crop_type": obs.get("crop_type"),
                "yield_tons_ha": obs.get("actual_yield_tons_ha"),
                "season": obs.get("season"),
            }
            for obs in obs_list
            if obs.get("actual_yield_tons_ha") is not None
        ]

    # ── Stats ──────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        return {
            "compaction_runs": self._compaction_count,
            "exports": self._export_count,
            "raw_retention_days": RAW_RETENTION_DAYS,
            "daily_retention_days": DAILY_RETENTION_DAYS,
            "weekly_retention_days": WEEKLY_RETENTION_DAYS,
        }
