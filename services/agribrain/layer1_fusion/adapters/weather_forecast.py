"""
Weather forecast source adapter.

Extracts 7-day forecast process forcing, risk windows, and
forecast-derived summaries from the environment package.

Rules:
- Forecast evidence is NEVER marked as observation
- observation_type = "forecast" always
- Temporal scope = "forecast_day_N"
- Confidence decays with forecast horizon
"""

from __future__ import annotations

from typing import Any, List

from layer1_fusion.schemas import EvidenceItem, Layer1InputBundle, SourceEnvelope


# Confidence decay per forecast day
_FORECAST_CONFIDENCE = {
    0: 0.80, 1: 0.75, 2: 0.65, 3: 0.55, 4: 0.45, 5: 0.35, 6: 0.30,
}


class WeatherForecastAdapter:
    source_family = "weather_forecast"

    def can_read(self, package: Any) -> bool:
        return package is not None and (
            getattr(package, "forecast_process_forcing", None) is not None
            or getattr(package, "forecast_consensus", None) is not None
        )

    def extract_evidence(
        self, package: Any, context: Layer1InputBundle
    ) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if package is None:
            return items

        plot_id = context.plot_id

        # --- Forecast process forcing ---
        for i, fpf in enumerate(getattr(package, "forecast_process_forcing", [])):
            day = min(i, 6)
            conf = _FORECAST_CONFIDENCE.get(day, 0.25)
            date = getattr(fpf, "date", f"day_{day}")

            for attr, var, unit in [
                ("precipitation_mm", "forecast_precip", "mm"),
                ("et0_mm", "forecast_et0", "mm"),
                ("temp_max", "forecast_temp_max", "degC"),
                ("temp_min", "forecast_temp_min", "degC"),
            ]:
                val = getattr(fpf, attr, None)
                if val is not None:
                    items.append(EvidenceItem(
                        evidence_id=f"fc_{date}_{var}",
                        plot_id=plot_id,
                        variable=var,
                        value=val,
                        unit=unit,
                        source_family="weather_forecast",
                        source_id="weather_forecast",
                        observation_type="forecast",  # NEVER "measurement"
                        spatial_scope="plot",
                        confidence=conf,
                        reliability=conf,
                        freshness_score=conf,
                        provenance_ref=f"forecast_{plot_id}_{date}",
                        flags=[f"FORECAST_DAY_{day}"],
                    ))

        # --- Risk windows ---
        for rw in getattr(package, "risk_windows", []):
            risk_type = getattr(rw, "risk_type", "unknown")
            items.append(EvidenceItem(
                evidence_id=f"fc_risk_{risk_type}_{getattr(rw, 'start_day', 0)}",
                plot_id=plot_id,
                variable=f"forecast_risk_{risk_type}",
                value=getattr(rw, "severity", "unknown"),
                unit=None,
                source_family="weather_forecast",
                source_id="weather_forecast",
                observation_type="forecast",
                spatial_scope="plot",
                confidence=0.50,
                reliability=0.50,
                freshness_score=0.50,
                provenance_ref=f"forecast_risk_{plot_id}",
                flags=["FORECAST_RISK_WINDOW"],
                diagnostic_only=True,
                state_update_allowed=False,
            ))

        return items

    def source_health(self, package: Any) -> SourceEnvelope:
        if package is None:
            return SourceEnvelope(
                source_id="forecast_missing", source_family="weather_forecast",
                source_name="Weather Forecast", package_id="", package_version="",
                source_status="missing",
            )
        has_forcing = bool(getattr(package, "forecast_process_forcing", []))
        return SourceEnvelope(
            source_id="weather_forecast",
            source_family="weather_forecast",
            source_name="Weather Forecast V1.1",
            package_id=f"fc_{getattr(package, 'plot_id', '')}",
            package_version="fc_v1.1",
            spatial_scope="plot",
            temporal_scope="7d",
            trust_score=0.65 if has_forcing else 0.0,
            source_status="ok" if has_forcing else "missing",
        )
