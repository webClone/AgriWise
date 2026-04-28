
from typing import Optional
from layer1_fusion.schema import FieldTensor

from orchestrator_v2.schema import OrchestratorInput

# New Layer 1 Fusion Engine (V1 deterministic context engine)
from layer1_fusion.engine import Layer1FusionEngine
from layer1_fusion.schemas import Layer1InputBundle, Layer1ContextPackage
from layer1_fusion.outputs.legacy_compat import build_legacy_fieldtensor

from datetime import datetime, timezone


# Singleton V1 engine
_v1_engine = Layer1FusionEngine()


def run_layer1_fusion(inputs: OrchestratorInput) -> FieldTensor:
    """
    Standard Entry Point for Layer 1.

    Now routes through the V1 deterministic engine and returns
    a backward-compatible FieldTensor via the legacy compatibility adapter.
    For the canonical V1 output, use run_layer1_fusion_v1() directly.
    """
    pkg = run_layer1_fusion_v1(inputs)
    return build_legacy_fieldtensor(pkg)


def run_layer1_fusion_legacy(inputs: OrchestratorInput) -> FieldTensor:
    """
    DEPRECATED Legacy Entry Point for Layer 1 (pre-V1 data_fusion path).

    Retained only for emergency fallback. Should NOT be used in production.
    """
    from layer1_fusion.data_fusion import fusion_engine  # lazy import

    plot_id = inputs.plot_id
    lat = float(inputs.operational_context.get("lat", 0.0))
    lng = float(inputs.operational_context.get("lng", 0.0))
    polygon_coords = inputs.operational_context.get("polygon_coords")
    start_date = inputs.date_range.get("start", "")
    end_date = inputs.date_range.get("end", "")
    user_evidence = inputs.operational_context.get("user_evidence", [])

    output = fusion_engine.fuse_data(
        plot_id=plot_id,
        lat=lat,
        lng=lng,
        start_date=start_date,
        end_date=end_date,
        polygon_coords=polygon_coords,
        user_evidence=user_evidence
    )

    tensor = output.tensor
    if output.raster_composites:
        tensor.raster_composites = output.raster_composites
    if output.observation_products:
        tensor.observation_products = output.observation_products
    return tensor


def run_layer1_fusion_v1(
    inputs: OrchestratorInput,
    layer0_packages: Optional[dict] = None,
    run_id: Optional[str] = None,
    run_timestamp: Optional[datetime] = None,
) -> Layer1ContextPackage:
    """
    V1 Entry Point for the deterministic Layer 1 Fusion Context Engine.

    This is the PREFERRED path. Legacy run_layer1_fusion() exists only
    for backward compatibility during migration. New orchestrator code
    should call this directly.

    Returns Layer1ContextPackage — the new canonical output.

    Args:
        inputs: OrchestratorInput from the V2 orchestrator.
        layer0_packages: Optional dict of pre-fetched Layer 0 packages.
            Keys: sentinel2_packages, sentinel1_packages, environment_package,
                  geo_context_package, sensor_context_package, etc.
        run_id: Explicit run ID for deterministic replay. If None, auto-generated.
        run_timestamp: Explicit timestamp for deterministic replay. If None, uses UTC now.
    """
    ts = run_timestamp or datetime.now(timezone.utc)
    rid = run_id or f"l1_run_{inputs.plot_id}_{ts.strftime('%Y%m%d%H%M%S')}"
    l0 = layer0_packages or {}

    bundle = Layer1InputBundle(
        plot_id=inputs.plot_id,
        run_id=rid,
        run_timestamp=ts,
        window_start=_parse_date(inputs.date_range.get("start", ""), ts),
        window_end=_parse_date(inputs.date_range.get("end", ""), ts),
        sentinel2_packages=l0.get("sentinel2_packages", []),
        sentinel1_packages=l0.get("sentinel1_packages", []),
        environment_package=l0.get("environment_package"),
        weather_forecast_package=l0.get("weather_forecast_package"),
        geo_context_package=l0.get("geo_context_package"),
        sensor_context_package=l0.get("sensor_context_package"),
        perception_packages=l0.get("perception_packages", []),
        user_events=l0.get("user_events", []),
        historical_layer1_package=l0.get("historical_layer1_package"),
    )

    return _v1_engine.fuse(bundle)


def _parse_date(date_str: str, fallback: datetime) -> datetime:
    """Parse date string to datetime.

    Falls back to the provided timestamp (not datetime.now) so that
    deterministic replay with explicit run_timestamp stays deterministic.
    """
    if not date_str:
        return fallback
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return fallback
