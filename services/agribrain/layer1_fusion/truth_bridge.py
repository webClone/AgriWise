import math
from typing import Any, Optional
from dataclasses import dataclass

from layer1_fusion.schemas import EvidenceItem
from layer0.observation_packet import ObservationPacket

try:
    from scientific_contracts.numeric import finite_real
except ImportError:
    from services.agribrain.scientific_contracts.numeric import finite_real

@dataclass
class EvidenceTruth:
    data_status: str
    truth_class: str
    source_reality: str
    real_provider_product: bool
    production_usable: bool
    diagnostic_only: bool
    state_update_allowed: bool
    grounding_class: Optional[str] = None
    visualization_allowed: bool = True
    experimental_visual_allowed: bool = True
    composite_advisory_allowed: bool = False
    scientific_surface_allowed: bool = False
    prescription_driver_allowed: bool = False
    current_1m_approval_allowed: bool = False


def _context_value(source_context: Any, key: str, default: Any = None) -> Any:
    """Read truth/grid metadata without confusing a composite wrapper for a raster."""
    if source_context is None:
        return default
    if isinstance(source_context, dict):
        if source_context.get(key) is not None:
            return source_context[key]
        grid_spec = source_context.get("grid_spec")
        if isinstance(grid_spec, dict) and grid_spec.get(key) is not None:
            return grid_spec[key]
        provenance = source_context.get("provenance")
        if isinstance(provenance, dict) and provenance.get(key) is not None:
            return provenance[key]
        return default

    metadata = getattr(source_context, "metadata", None)
    if metadata is not None and getattr(metadata, key, None) is not None:
        return getattr(metadata, key)
    return getattr(source_context, key, default)


def _has_valid_geospatial_grid(source_context: Any) -> bool:
    """Require positive-area bounds and an invertible six-value transform."""
    crs = _context_value(source_context, "crs")
    bounds = _context_value(source_context, "bounds")
    transform = _context_value(source_context, "transform")
    if transform is None:
        transform = _context_value(source_context, "affine")
    if not isinstance(crs, str) or not crs.strip():
        return False
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        return False
    if not isinstance(transform, (list, tuple)) or len(transform) != 6:
        return False
    try:
        bounds_values = tuple(float(value) for value in bounds)
        transform_values = tuple(float(value) for value in transform)
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(value) for value in bounds_values + transform_values):
        return False
    if bounds_values[2] <= bounds_values[0] or bounds_values[3] <= bounds_values[1]:
        return False
    gdal_determinant = (
        transform_values[1] * transform_values[5]
        - transform_values[2] * transform_values[4]
    )
    affine_determinant = (
        transform_values[0] * transform_values[4]
        - transform_values[1] * transform_values[3]
    )
    return abs(gdal_determinant) > 1e-15 or abs(affine_determinant) > 1e-15

def normalize_evidence_truth(item: EvidenceItem, source_context: Optional[Any] = None, source_family: Optional[str] = None) -> EvidenceItem:
    # A context-free pass is allowed to classify a fresh/unknown item, but it
    # must never erase a source-aware classification that already succeeded.
    # Evidence validation is responsible for checking the preserved fields.
    if (
        source_context is None
        and source_family is None
        and item.truth_class not in (None, "", "unknown")
        and item.source_reality not in (None, "", "unknown")
        and item.source_family != "sensor"
    ):
        return item
    if source_family is not None:
        item.source_family = source_family
    is_proxy = False

    prior_status = getattr(item, "data_status", None)
    prior_diagnostic_only = bool(getattr(item, "diagnostic_only", False))
    prior_state_update_allowed = bool(getattr(item, "state_update_allowed", True))

    # 1. Sentinel-2 / Sentinel-1 provider raster
    if item.source_family in ("sentinel1", "sentinel2"):
        if item.data_status == "reconstruction":
            item.truth_class = "reconstruction_proxy"
            item.production_usable = True
            item.real_provider_product = False
            item.diagnostic_only = True
            item.state_update_allowed = False
            item.scientific_surface_allowed = False
            item.visualization_allowed = True
            item.experimental_visual_allowed = True
            item.composite_advisory_allowed = True
            item.prescription_driver_allowed = False
            item.current_1m_approval_allowed = False
            item.grounding_class = None
            return item

        is_daily_plot_statistic = (
            item.spatial_scope == "plot"
            and item.temporal_basis == "daily_plot_statistic"
            and bool(item.content_hash)
            and bool(item.provider_product_id or item.source_id)
            and item.data_status not in ("fallback", "reconstruction", "simulated", "unavailable", "estimated")
            and item.source_reality == "provider_daily_statistical_aggregate"
        )
        if is_daily_plot_statistic:
            item.data_status = "observed"
            item.truth_class = "provider_plot_timeseries"
            item.production_usable = True
            item.real_provider_product = False
            item.diagnostic_only = False
            item.state_update_allowed = True
            item.scientific_surface_allowed = False
            item.visualization_allowed = True
            item.experimental_visual_allowed = True
            item.composite_advisory_allowed = True
            item.prescription_driver_allowed = False
            item.current_1m_approval_allowed = False
            item.grounding_class = None
            return item

        is_real_temporal = (
            item.spatial_scope == "plot"
            and item.temporal_basis == "scene_observation"
            and bool(item.content_hash)
            and bool(item.provider_product_id or item.source_id)
            and item.data_status not in ("fallback", "reconstruction", "simulated", "unavailable", "estimated")
            and item.source_reality in {
                "provider_scene_observation",
                "provider_temporal_observation",
                "real_provider_raster",
                "provider_observation",
                "real_raster",
            }
        )
        if is_real_temporal:
            item.data_status = "observed"
            item.truth_class = "provider_plot_timeseries"
            item.source_reality = "provider_temporal_observation"
            item.production_usable = True
            item.real_provider_product = True
            item.diagnostic_only = False
            item.state_update_allowed = True
            item.scientific_surface_allowed = True
            item.visualization_allowed = True
            item.experimental_visual_allowed = True
            item.composite_advisory_allowed = True
            item.prescription_driver_allowed = False
            item.current_1m_approval_allowed = False
            item.grounding_class = "UNIFORM"
            return item

        if source_context is not None:
            if isinstance(source_context, dict):
                is_proxy = (
                    source_context.get("source_reality") == "raster_composite_proxy"
                    or source_context.get("production_usable") is False
                    or source_context.get("real_provider_product") is False
                    or source_context.get("diagnostic_only") is True
                )
            else:
                meta = getattr(source_context, "metadata", None)
                if meta is not None:
                    is_proxy = (
                        getattr(meta, "source_reality", None) == "raster_composite_proxy"
                        or getattr(meta, "production_usable", True) is False
                        or getattr(meta, "real_provider_product", True) is False
                        or getattr(meta, "diagnostic_only", False) is True
                    )
                else:
                    is_proxy = (
                        getattr(source_context, "source_reality", None) == "raster_composite_proxy"
                        or getattr(source_context, "production_usable", True) is False
                        or getattr(source_context, "real_provider_product", True) is False
                        or getattr(source_context, "diagnostic_only", False) is True
                    )
        
        has_crs_proof = False
        if source_context is not None:
            if isinstance(source_context, dict):
                has_crs_proof = (
                    source_context.get("crs") is not None 
                    and (source_context.get("transform") is not None or source_context.get("affine") is not None)
                )
            else:
                meta = getattr(source_context, "metadata", None)
                if meta is not None:
                    has_crs_proof = (
                        getattr(meta, "crs", None) is not None 
                        and (getattr(meta, "transform", None) is not None or getattr(meta, "affine", None) is not None)
                    )
                else:
                    has_crs_proof = (
                        getattr(source_context, "crs", None) is not None 
                        and (getattr(source_context, "transform", None) is not None or getattr(source_context, "affine", None) is not None)
                    )

        if not has_crs_proof:
            is_proxy = True

        if not is_proxy:
            is_proxy = (
                item.source_reality == "raster_composite_proxy"
                or item.data_status == "fallback"
                or any("PROXY" in str(f).upper() for f in (item.flags or []))
            )

        if is_proxy:
            item.data_status = "fallback"
            item.truth_class = "raster_composite_proxy"
            item.source_reality = "raster_composite_proxy"
            item.production_usable = False
            item.real_provider_product = False
            item.diagnostic_only = True
            item.state_update_allowed = False
            item.visualization_allowed = True
            item.composite_advisory_allowed = True
            item.experimental_visual_allowed = True
            item.scientific_surface_allowed = False
            item.prescription_driver_allowed = False
            item.current_1m_approval_allowed = False
            item.grounding_class = "PROXY_SPATIAL"
        else:
            item.data_status = "observed"
            item.truth_class = "observed_provider"
            item.source_reality = "real_provider_raster"
            item.production_usable = True
            item.real_provider_product = True
            item.diagnostic_only = False
            item.state_update_allowed = True
            item.scientific_surface_allowed = True
            item.visualization_allowed = True
            item.experimental_visual_allowed = True
            item.composite_advisory_allowed = True
            item.prescription_driver_allowed = True
            item.current_1m_approval_allowed = True
            item.grounding_class = "RASTER_GROUNDED"

    # 2. Weather or forecast
    elif item.source_family == "weather_forecast":
        # Keep data_status if set, default to estimated. Must not be "partial"
        if item.data_status not in ("observed", "estimated", "interpolated", "assimilated", "fallback", "simulated", "unavailable"):
            item.data_status = "estimated"
        
        if item.data_status == "observed":
            item.truth_class = "observed_provider_weather"
        else:
            item.truth_class = "provider_forecast_model"
            
        item.source_reality = "provider_model_feed"
        item.production_usable = True
        item.real_provider_product = True
        item.diagnostic_only = False
        
        # state_update_allowed only for approved forecast variables
        approved_vars = ("forecast_precip", "forecast_et0", "forecast_temp_max", "forecast_temp_min", "precipitation", "temp_max", "temp_min", "et0")
        item.state_update_allowed = item.variable in approved_vars
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = False
        item.composite_advisory_allowed = False

    elif item.source_family == "environment":
        is_soil = "soil" in str(item.variable) or "static" in str(item.observation_type)
        if item.data_status not in ("observed", "estimated", "interpolated", "assimilated", "fallback", "simulated", "unavailable"):
            item.data_status = "observed" if is_soil else "estimated"
        item.truth_class = "geo_provider_context" if is_soil else "observed_provider_weather"
        item.source_reality = "provider_geo_context" if is_soil else "provider_model_feed"
        item.production_usable = True
        item.real_provider_product = True
        item.diagnostic_only = False
        item.state_update_allowed = True
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = False
        item.composite_advisory_allowed = False

    # 3. User Event or Observation
    elif item.source_family in ("user_event", "user_observation") or item.observation_type == "event":
        item.data_status = "observed"
        item.truth_class = "observed_user"
        item.source_reality = "user_observation"
        item.production_usable = True
        item.real_provider_product = False
        item.diagnostic_only = False
        is_validated = "VALIDATED" in [str(f).upper() for f in (item.flags or [])] or "CALIBRATED" in [str(f).upper() for f in (item.flags or [])]
        item.state_update_allowed = True if is_validated else False
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 4. Geo context
    elif item.source_family in ("geo_context", "soilgrids", "fao"):
        is_static = "static" in str(item.observation_type) or "static" in str(item.temporal_scope)
        item.data_status = "observed" if is_static else "estimated"
        item.truth_class = "geo_provider_context" if is_static else "estimated_geo_context"
        item.source_reality = "provider_geo_context"
        item.production_usable = True
        item.real_provider_product = True
        item.diagnostic_only = False
        
        # state_update_allowed only for stable context variables
        stable_context_vars = ("clay", "sand", "silt", "ph", "soil_type", "organic_matter", "bulk_density", "cec")
        item.state_update_allowed = item.variable in stable_context_vars
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 5. ASMAE composite / advisory
    elif item.source_family in ("asmae", "asmae_composite"):
        is_comp = "COMPOSITE" in str(item.variable).upper()
        item.data_status = "fallback" if is_comp else "assimilated"
        item.truth_class = "raster_composite_proxy" if is_comp else "estimated_model"
        item.source_reality = "raster_composite_proxy" if is_comp else "provider_model_feed"
        item.production_usable = False
        item.real_provider_product = False
        item.diagnostic_only = True
        item.state_update_allowed = False
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.composite_advisory_allowed = True
        item.experimental_visual_allowed = True

    # 6. Sensor/IoT
    elif item.source_family == "sensor":
        has_instrument = bool(getattr(item, "instrument_id", None))
        has_calibration = bool(getattr(item, "calibration_version", None))
        has_valid_provenance = bool(item.provenance_ref and item.source_id)
        
        prov_str = str(item.provenance_ref or "").lower()
        inst_str = str(getattr(item, "instrument_id", "") or "").lower()
        cal_str = str(getattr(item, "calibration_version", "") or "").lower()
        
        is_unattested = (
            not has_valid_provenance
            or not has_instrument
            or not has_calibration
            or any(s in prov_str for s in ("user-supplied", "unverified", "fake", "unattested", "dummy", "spoofed", "forged"))
            or any(s in inst_str for s in ("fake", "dummy", "unattested", "spoofed", "unverified", "forged"))
            or any(s in cal_str for s in ("fake", "dummy", "unattested", "spoofed", "unverified", "forged"))
        )
        
        # Revocation check across flags
        is_revoked = any("REVOKED" in str(f).upper() for f in (getattr(item, "flags", []) or []))
        
        # Check registered device status & plot scope fail-closed (L1-R7-01 / R7-G01 / R7-G02 / R7-G09)
        reg = None
        registry_error = None
        try:
            from services.agribrain.sensor_runtime.registry import get_device_registration
            dev_key = item.instrument_id or item.source_id
            reg = get_device_registration(dev_key) if dev_key else None
        except Exception as ex:
            registry_error = str(ex)
            reg = None

        if reg is None or registry_error is not None:
            is_unattested = True
        else:
            if getattr(reg, "status", None) != "active":
                is_unattested = True
            if reg.plot_id and item.plot_id and reg.plot_id != item.plot_id:
                is_unattested = True
            if item.variable and reg.variables and item.variable not in reg.variables:
                is_unattested = True
            if getattr(reg, "calibration_profile_id", None) and item.calibration_version:
                if reg.calibration_profile_id != item.calibration_version:
                    is_unattested = True

        is_synthetic = getattr(item, "data_status", "") in ("synthetic", "simulated", "fallback")
        if is_unattested or is_revoked or is_synthetic:
            item.data_status = "synthetic" if is_synthetic else getattr(item, "data_status", "unverified")
            item.truth_class = "unverified_sensor"
            item.source_reality = "synthetic_or_uncalibrated"
            item.production_usable = False
            item.real_provider_product = False
            item.diagnostic_only = True
            item.state_update_allowed = False
        else:
            existing_diagnostic_only = bool(getattr(item, "diagnostic_only", False))
            existing_state_update_allowed = bool(getattr(item, "state_update_allowed", True))
            item.data_status = "observed"
            item.truth_class = "observed_sensor"
            item.source_reality = "sensor_physical"
            item.production_usable = True
            item.real_provider_product = True
            item.diagnostic_only = existing_diagnostic_only
            item.state_update_allowed = existing_state_update_allowed and not existing_diagnostic_only
        
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.composite_advisory_allowed = True
        item.experimental_visual_allowed = True

    # 6a. Sentinel-5P
    elif item.source_family == "sentinel5p":
        item.data_status = "observed"
        item.truth_class = "provider_observation"
        item.source_reality = "real_provider_raster"
        item.production_usable = True
        item.real_provider_product = True
        item.diagnostic_only = False
        item.state_update_allowed = True
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6b. Drone
    elif item.source_family in ("drone_structural", "drone"):
        is_restricted = prior_status in ("simulated", "estimated", "fallback", "unavailable", "reconstruction")
        if is_restricted:
            item.data_status = prior_status
            item.truth_class = f"{prior_status}_proxy" if prior_status != "unavailable" else "unavailable"
            item.source_reality = "user_observation"
            item.production_usable = prior_status != "unavailable"
            item.real_provider_product = False
            item.diagnostic_only = True
            item.state_update_allowed = False
        else:
            item.data_status = "observed"
            item.truth_class = "provider_observation"
            item.source_reality = "user_observation"
            item.production_usable = True
            item.real_provider_product = True
            item.diagnostic_only = prior_diagnostic_only
            item.state_update_allowed = prior_state_update_allowed and not prior_diagnostic_only
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6c. History
    elif item.source_family == "history":
        item.data_status = "observed"
        item.truth_class = "observed_provider"
        item.source_reality = "real_provider_raster"
        item.production_usable = True
        item.real_provider_product = True
        item.diagnostic_only = False
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6d. Level 0 State (assimilated model state, NOT raw provider measurement - E-04/T15)
    elif item.source_family == "l0_state":
        item.data_status = "assimilated"
        item.truth_class = "model_state"
        item.source_reality = "model_derived"
        item.production_usable = True
        item.real_provider_product = False
        item.diagnostic_only = False
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6e. EO Foundation
    elif item.source_family == "eo_foundation":
        is_unqualified = "UNQUALIFIED_SPATIAL_IDENTITY" in (getattr(item, "flags", None) or []) or getattr(item, "is_spatial_qualified", True) is False
        item.data_status = "estimated"
        item.truth_class = "estimated_model"
        item.source_reality = "provider_model_feed"
        item.production_usable = not is_unqualified
        item.real_provider_product = False
        item.diagnostic_only = True
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6f. Perception
    elif item.source_family == "perception":
        item.data_status = "estimated"
        item.truth_class = "estimated_model"
        item.source_reality = "provider_model_feed"
        item.production_usable = True
        item.real_provider_product = False
        item.diagnostic_only = False
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 6g. Raster Composite
    elif item.source_family == "raster_composite":
        # Enforce proxy default
        is_proxy = True
        has_geospatial_proof = _has_valid_geospatial_grid(source_context)
        if source_context is not None:
            is_real = (
                _context_value(source_context, "real_provider_product", False) is True
                and _context_value(source_context, "production_usable", False) is True
                and _context_value(source_context, "diagnostic_only", True) is False
                and has_geospatial_proof
            )
            if is_real:
                is_proxy = False

        if is_proxy:
            item.data_status = "fallback"
            item.truth_class = "raster_composite_proxy"
            item.source_reality = "raster_composite_proxy"
            item.production_usable = False
            item.real_provider_product = False
            item.diagnostic_only = True
            item.state_update_allowed = False
            item.visualization_allowed = True
            item.composite_advisory_allowed = True
            item.experimental_visual_allowed = True
            item.scientific_surface_allowed = False
            item.prescription_driver_allowed = False
            item.current_1m_approval_allowed = False
            item.grounding_class = "PROXY_SPATIAL" if has_geospatial_proof else "UNIFORM"
        else:
            item.data_status = "observed"
            item.truth_class = "observed_provider"
            item.source_reality = "real_provider_raster"
            item.production_usable = True
            item.real_provider_product = True
            item.diagnostic_only = False
            item.state_update_allowed = True
            item.scientific_surface_allowed = True
            item.visualization_allowed = True
            item.experimental_visual_allowed = True
            item.composite_advisory_allowed = True
            item.prescription_driver_allowed = True
            item.current_1m_approval_allowed = True
            item.grounding_class = "RASTER_GROUNDED"

    # 6h. Zone Segmentation / Microzone
    elif item.source_family in ("zone_segmentation", "microzone"):
        item.data_status = "estimated"
        item.truth_class = "derived_zone"
        item.source_reality = "provider_model_feed"
        item.production_usable = True
        item.real_provider_product = False
        item.diagnostic_only = False
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False
        item.visualization_allowed = True
        item.experimental_visual_allowed = True
        item.composite_advisory_allowed = True

    # 7. Fallback Default (If we cannot classify, let's keep it unknown so it gets quarantined!)
    else:
        item.data_status = "unknown"
        item.truth_class = "unknown"
        item.source_reality = "unknown"
        item.production_usable = False
        item.real_provider_product = False
        item.diagnostic_only = True
        item.state_update_allowed = False
        item.scientific_surface_allowed = False
        item.prescription_driver_allowed = False
        item.current_1m_approval_allowed = False

    # Monotone role and permission preservation: restrictive status cannot be promoted
    if prior_status in ("unavailable", "simulated", "fallback", "reconstruction"):
        item.data_status = prior_status
        item.diagnostic_only = True
        item.state_update_allowed = False
    elif prior_status == "estimated":
        if item.data_status == "observed":
            item.data_status = "estimated"
        item.state_update_allowed = False if not prior_state_update_allowed else item.state_update_allowed
    elif prior_diagnostic_only:
        item.diagnostic_only = True
        item.state_update_allowed = False

    # Enforce status-based confidence ceilings
    from .schemas import DATA_STATUS_CEILING
    if item.data_status in DATA_STATUS_CEILING:
        ceil_val = DATA_STATUS_CEILING[item.data_status]
        if item.confidence is not None:
            fin_c = finite_real(item.confidence)
            if fin_c is not None:
                item.confidence = min(fin_c, ceil_val)

    return item

def truth_for_observation_packet(packet: ObservationPacket, package: Optional[Any] = None) -> EvidenceTruth:
    if packet is None:
        return EvidenceTruth(
            data_status="fallback",
            truth_class="fallback_default",
            source_reality="fallback_default",
            real_provider_product=False,
            production_usable=False,
            diagnostic_only=True,
            state_update_allowed=False,
        )
    payload = packet.payload if isinstance(packet.payload, dict) else {}
    declared_roles = [
        str(payload[k]).upper()
        for k in ("role", "source_role", "data_role", "status_role", "truth_class")
        if k in payload and payload[k] is not None
    ]
    is_excluded = (
        packet.data_status.value == "unavailable"
        or any(r in ("UNAVAILABLE", "EXCLUDED", "REJECTED") for r in declared_roles)
    )
    is_simulated = (
        packet.data_status.value == "simulated"
        or any(r in ("SIMULATED", "SYNTHETIC", "SCENARIO") for r in declared_roles)
        or payload.get("simulated") is True
    )
    is_fallback = (
        packet.data_status.value == "fallback"
        or any(r in ("FALLBACK", "PROXY") for r in declared_roles)
        or payload.get("source_reality") == "raster_composite_proxy"
        or payload.get("production_usable") is False
        or (
            payload.get("real_provider_product") is False
            and payload.get("source_reality") != "provider_daily_statistical_aggregate"
        )
        or payload.get("diagnostic_only") is True
    )
    is_reconstruction = (
        packet.data_status.value == "reconstruction"
        or any(r == "RECONSTRUCTION" for r in declared_roles)
    )
    is_estimated = (
        packet.data_status.value == "estimated"
        or any(r in ("FORECAST", "ESTIMATED", "DERIVED", "PREDICTION", "MODELLED", "PRIOR") for r in declared_roles)
    )

    if is_excluded:
        return EvidenceTruth(
            data_status="unavailable",
            truth_class="unavailable",
            source_reality="unavailable",
            real_provider_product=False,
            production_usable=False,
            diagnostic_only=True,
            state_update_allowed=False,
        )

    if is_simulated:
        return EvidenceTruth(
            data_status="simulated",
            truth_class="simulated_proxy",
            source_reality="simulated_proxy",
            real_provider_product=False,
            production_usable=False,
            diagnostic_only=True,
            state_update_allowed=False,
            visualization_allowed=True,
            composite_advisory_allowed=True,
            experimental_visual_allowed=True,
        )

    if is_fallback:
        return EvidenceTruth(
            data_status="fallback",
            truth_class="raster_composite_proxy",
            source_reality="raster_composite_proxy",
            production_usable=False,
            real_provider_product=False,
            diagnostic_only=True,
            state_update_allowed=False,
            visualization_allowed=True,
            composite_advisory_allowed=True,
            experimental_visual_allowed=True,
        )

    if is_reconstruction:
        return EvidenceTruth(
            data_status="reconstruction",
            truth_class="reconstruction_proxy",
            source_reality="reconstruction_proxy",
            production_usable=True,
            real_provider_product=False,
            diagnostic_only=True,
            state_update_allowed=False,
            visualization_allowed=True,
            composite_advisory_allowed=True,
            experimental_visual_allowed=True,
        )

    if is_estimated:
        return EvidenceTruth(
            data_status="estimated",
            truth_class="estimated_proxy",
            source_reality="estimated_proxy",
            production_usable=True,
            real_provider_product=False,
            diagnostic_only=False,
            state_update_allowed=False,
            visualization_allowed=True,
            composite_advisory_allowed=True,
            experimental_visual_allowed=True,
        )

    is_daily_plot_statistic = (
        payload.get("source_reality") == "provider_daily_statistical_aggregate"
        and payload.get("temporal_basis") == "daily_plot_statistic"
    )
    if is_daily_plot_statistic:
        from layer0.temporal_evidence import is_admitted_temporal_record
        if is_admitted_temporal_record(payload):
            return EvidenceTruth(
                data_status="observed",
                truth_class="provider_plot_timeseries",
                source_reality="provider_daily_statistical_aggregate",
                production_usable=True,
                real_provider_product=False,
                diagnostic_only=False,
                state_update_allowed=True,
                grounding_class=None,
                scientific_surface_allowed=False,
                visualization_allowed=True,
                experimental_visual_allowed=True,
                composite_advisory_allowed=True,
                prescription_driver_allowed=False,
                current_1m_approval_allowed=False,
            )

    if packet.source.value in ("user_observation", "user_event"):
        return EvidenceTruth(
            data_status=packet.data_status.value,
            truth_class="observed_user",
            source_reality="user_observation",
            production_usable=True,
            real_provider_product=False,
            diagnostic_only=False,
            state_update_allowed=False, # user observation state update is false unless validated
            visualization_allowed=True,
            composite_advisory_allowed=True,
            experimental_visual_allowed=True,
        )

    if packet.source.value in ("sensor", "sensor_iot", "soil_probe"):
        payload = packet.payload or {}
        has_inst = bool(payload.get("instrument_id") or payload.get("device_id") or getattr(packet, "instrument_id", None))
        has_cal = bool(payload.get("calibration_version") or (packet.qa and getattr(packet.qa, "calibration_version", None)))
        
        reg = None
        dev_key = payload.get("instrument_id") or payload.get("device_id") or getattr(packet, "instrument_id", None) or packet.packet_id
        try:
            from services.agribrain.sensor_runtime.registry import get_device_registration
            reg = get_device_registration(dev_key) if dev_key else None
        except Exception:
            reg = None

        is_valid_sensor = (
            packet.data_status.value == "observed"
            and has_inst
            and has_cal
            and reg is not None
            and getattr(reg, "status", None) == "active"
            and (not getattr(reg, "plot_id", None) or not packet.plot_id or reg.plot_id == packet.plot_id)
        )
        if is_valid_sensor:
            return EvidenceTruth(
                data_status="observed",
                truth_class="observed_sensor",
                source_reality="sensor_physical",
                production_usable=True,
                real_provider_product=True,
                diagnostic_only=False,
                state_update_allowed=True,
                visualization_allowed=True,
                experimental_visual_allowed=True,
                composite_advisory_allowed=True,
                scientific_surface_allowed=False,
                prescription_driver_allowed=False,
                current_1m_approval_allowed=False,
            )
        else:
            return EvidenceTruth(
                data_status="unverified" if packet.data_status.value == "observed" else packet.data_status.value,
                truth_class="unverified_sensor",
                source_reality="synthetic_or_uncalibrated",
                production_usable=False,
                real_provider_product=False,
                diagnostic_only=True,
                state_update_allowed=False,
                visualization_allowed=True,
                experimental_visual_allowed=True,
                composite_advisory_allowed=True,
                scientific_surface_allowed=False,
                prescription_driver_allowed=False,
                current_1m_approval_allowed=False,
            )
        
    if packet.data_status.value == "observed":
        is_sentinel = packet.source.value in ("sentinel1", "sentinel2")
        has_crs = False
        if is_sentinel:
            payload = packet.payload or {}
            has_crs = (
                payload.get("crs") is not None
                and (payload.get("transform") is not None or payload.get("affine") is not None)
            )

        if is_sentinel and not has_crs:
            return EvidenceTruth(
                data_status="fallback",
                truth_class="raster_composite_proxy",
                source_reality="raster_composite_proxy",
                production_usable=False,
                real_provider_product=False,
                diagnostic_only=True,
                state_update_allowed=False,
                visualization_allowed=True,
                composite_advisory_allowed=True,
                experimental_visual_allowed=True,
                grounding_class="PROXY_SPATIAL"
            )

        return EvidenceTruth(
            data_status="observed",
            truth_class="observed_provider",
            source_reality="real_provider_raster" if is_sentinel else "provider_observation",
            production_usable=True,
            real_provider_product=True,
            diagnostic_only=False,
            state_update_allowed=True,
            grounding_class="RASTER_GROUNDED" if is_sentinel else None,
            scientific_surface_allowed=True,
            visualization_allowed=True,
            experimental_visual_allowed=True,
            composite_advisory_allowed=True,
            prescription_driver_allowed=True,
            current_1m_approval_allowed=True,
        )
        
    return EvidenceTruth(
        data_status=packet.data_status.value,
        truth_class="estimated_model" if packet.data_status.value == "estimated" else "fallback_default",
        source_reality="provider_model_feed" if packet.data_status.value == "estimated" else "fallback_default",
        production_usable=True if packet.data_status.value == "estimated" else False,
        real_provider_product=True if packet.data_status.value == "estimated" else False,
        diagnostic_only=False if packet.data_status.value == "estimated" else True,
        state_update_allowed=True if packet.data_status.value == "estimated" else False,
        visualization_allowed=True,
        experimental_visual_allowed=True,
        composite_advisory_allowed=False if packet.data_status.value == "estimated" else True,
    )

def truth_for_raster_composite(raster_data: Any) -> EvidenceTruth:
    from layer05_asmae.truth_contract import classify_raster_truth
    truth = classify_raster_truth(raster_data)
    has_geospatial_proof = _has_valid_geospatial_grid(raster_data)
    is_authoritative = (
        has_geospatial_proof
        and truth.real_provider_product
        and truth.production_usable
        and not truth.diagnostic_only
    )
    if not is_authoritative:
        return EvidenceTruth(
            data_status="fallback",
            truth_class="raster_composite_proxy",
            source_reality="raster_composite_proxy",
            real_provider_product=False,
            production_usable=False,
            diagnostic_only=True,
            state_update_allowed=False,
            grounding_class="PROXY_SPATIAL" if has_geospatial_proof else "UNIFORM",
            visualization_allowed=True,
            experimental_visual_allowed=True,
            composite_advisory_allowed=True,
            scientific_surface_allowed=False,
            prescription_driver_allowed=False,
            current_1m_approval_allowed=False,
        )
    return EvidenceTruth(
        data_status="observed",
        truth_class=truth.truth_class,
        source_reality=truth.source_reality,
        real_provider_product=truth.real_provider_product,
        production_usable=truth.production_usable,
        diagnostic_only=truth.diagnostic_only,
        state_update_allowed=truth.state_update_allowed,
        grounding_class="RASTER_GROUNDED",
        visualization_allowed=truth.visualization_allowed,
        experimental_visual_allowed=truth.experimental_visual_allowed,
        composite_advisory_allowed=truth.composite_advisory_allowed,
        scientific_surface_allowed=truth.scientific_surface_allowed,
        prescription_driver_allowed=truth.prescription_driver_allowed,
        current_1m_approval_allowed=truth.current_1m_approval_allowed,
    )

def truth_for_weather_record(record: Any) -> EvidenceTruth:
    return EvidenceTruth(
        data_status="estimated",
        truth_class="estimated_model",
        source_reality="provider_model_feed",
        production_usable=True,
        real_provider_product=True,
        diagnostic_only=False,
        state_update_allowed=True,
        visualization_allowed=True,
        experimental_visual_allowed=True,
        composite_advisory_allowed=False,
    )

def truth_for_user_observation(record: Any) -> EvidenceTruth:
    return EvidenceTruth(
        data_status="observed",
        truth_class="observed_user",
        source_reality="user_observation",
        production_usable=True,
        real_provider_product=False,
        diagnostic_only=False,
        state_update_allowed=False,
        visualization_allowed=True,
        composite_advisory_allowed=True,
        experimental_visual_allowed=True,
    )

normalize_truth_from_packet = truth_for_observation_packet

def apply_truth_contract(item: EvidenceItem, source_package: Optional[Any] = None, packet: Optional[Any] = None) -> EvidenceItem:
    return normalize_evidence_truth(item, source_context=source_package or packet)
