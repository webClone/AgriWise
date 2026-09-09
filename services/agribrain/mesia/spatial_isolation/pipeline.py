"""MESIA Master Spatial Isolation Pipeline & Observation Gating Engine.

Coordinates geodetic ENU mapping, inward polygon erosion, physical footprint evaluation,
spatial sensitivity quadrature, 5-tier classification, and multi-hypothesis attribution.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .attribution import MultiHypothesisAttributionEngine
from .classifier import SpatialGatingClassifier
from .footprints import (
    BroadcastUhfFootprint,
    CellularForwardScatterFootprint,
    GnssReflectometryFootprint,
    SarRadarFootprint,
    WifiMultipathFootprint,
)
from .geometry import (
    compute_dynamic_buffer_width,
    erode_polygon_inward,
    geodetic_to_local_enu,
    polygon_area,
)
from .integrator import SpatialSensitivityIntegrator
from .models import (
    ContainmentInterval,
    ExternalAttributionVector,
    PlotSpatialIsolationSummary,
    SpatialAuditRecord,
    SpatialClassificationTier,
    StateSpecificSensitivity,
)


class SpatialIsolationPipeline:
    """Master pipeline executing spatial isolation and cadastral protection for MESIA observables."""

    @classmethod
    def evaluate_plot_spatial_isolation(
        cls,
        plot_id: str,
        plot_coordinates: List[List[float]],  # [[lon, lat], ...] or [[lat, lon], ...]
        observables: Optional[List[Dict[str, Any]]] = None,
        environmental_context: Optional[Dict[str, Any]] = None,
    ) -> PlotSpatialIsolationSummary:
        """Runs complete spatial gating and boundary isolation on a target parcel."""
        env = environmental_context or {}

        # 1. Geodetic Projection to local ENU
        # Normalize coordinates: ensure list of (lat, lon)
        raw_coords: List[Tuple[float, float]] = []
        for pt in plot_coordinates:
            if len(pt) >= 2:
                # If first element is lon (e.g. GeoJSON format [-0.5, 35.5]), check range
                c0, c1 = float(pt[0]), float(pt[1])
                if abs(c0) <= 180.0 and abs(c1) <= 90.0:
                    if abs(c0) < 15.0 and abs(c1) > 25.0:  # lon, lat typical of Algeria
                        lon, lat = c0, c1
                    else:
                        lat, lon = c0, c1
                else:
                    lat, lon = c0, c1
                raw_coords.append((lat, lon))

        if len(raw_coords) < 3:
            raise ValueError(
                f"Plot boundary requires at least 3 geodetic vertices for spatial isolation analysis, got {len(raw_coords)}"
            )

        origin_lat = sum(p[0] for p in raw_coords) / len(raw_coords)
        origin_lon = sum(p[1] for p in raw_coords) / len(raw_coords)
        plot_enu = [
            geodetic_to_local_enu(p[0], p[1], origin_lat, origin_lon) for p in raw_coords
        ]

        plot_area_m2 = polygon_area(plot_enu)

        # 2. Inward Erosion: Calculate Dynamic Buffer and P_core
        # Assume typical GNSS-R ground footprint minor axis ~ 6.0 m
        buffer_width_m = compute_dynamic_buffer_width(
            footprint_minor_axis_m=6.0,
            sigma_cadastre_m=float(env.get("sigma_cadastre_m", 0.5)),
            sigma_receiver_m=float(env.get("sigma_receiver_m", 0.2)),
            min_guard_m=4.0,
        )
        core_enu = erode_polygon_inward(plot_enu, buffer_width_m)
        core_area_m2 = polygon_area(core_enu)

        # 3. Process Observables (Principle P-01: No fabricated or unobserved apertures)
        candidate_obs = observables or []
        if not candidate_obs:
            return PlotSpatialIsolationSummary(
                plot_id=plot_id,
                origin_geodetic=(origin_lat, origin_lon),
                plot_area_m2=float(round(plot_area_m2, 1)),
                core_area_m2=float(round(core_area_m2, 1)),
                buffer_width_m=float(round(buffer_width_m, 2)),
                overall_isolation_status="AWAITING_ACTIVE_OBSERVABLES",
                mean_plot_containment=0.0,
                mean_external_leakage=0.0,
                zero_external_leakage_verified=False,
                total_observables_evaluated=0,
                classification_breakdown={},
                audit_records=[],
                recommended_action="DEFER_UNTIL_OBSERVABLES_AVAILABLE",
            )

        audit_records: List[SpatialAuditRecord] = []

        total_containment_sum = 0.0
        total_external_leakage_sum = 0.0

        for idx, obs in enumerate(candidate_obs):
            modality = obs.get("modality", "GNSS_R")
            obs_id = obs.get("observation_id", f"obs-{idx:03d}")

            record = cls._evaluate_single_observable(
                obs_id=obs_id,
                obs_data=obs,
                plot_enu=plot_enu,
                core_enu=core_enu,
                env=env,
            )
            audit_records.append(record)
            total_containment_sum += record.containment_plot.eta_hat
            total_external_leakage_sum += record.eta_external_leakage

        num_records = max(1, len(audit_records))
        mean_containment = total_containment_sum / num_records
        mean_leakage = total_external_leakage_sum / num_records

        # Classification breakdown counts
        breakdown: Dict[str, int] = {}
        for r in audit_records:
            tier_str = r.classification_tier.value
            breakdown[tier_str] = breakdown.get(tier_str, 0) + 1

        # Determine overall parcel spatial health
        is_safe = breakdown.get(SpatialClassificationTier.EXT_QUARANTINED.value, 0) == 0 and mean_containment >= 0.85

        if mean_containment >= 0.92:
            status = "OPTIMAL_CADASTRAL_ISOLATION"
            rec_action = "ADMIT_CORE_STATE_UPDATE"
        elif mean_containment >= 0.80:
            status = "MARGINAL_PERIMETER_SENSITIVITY"
            rec_action = "APPLY_MARGIN_COVARIANCE_INFLATION"
        else:
            status = "ELEVATED_EXTERNAL_RISK"
            rec_action = "QUARANTINE_EXTERNAL_OBSERVATIONS"

        return PlotSpatialIsolationSummary(
            plot_id=plot_id,
            origin_geodetic=(origin_lat, origin_lon),
            plot_area_m2=float(round(plot_area_m2, 1)),
            core_area_m2=float(round(core_area_m2, 1)),
            buffer_width_m=float(round(buffer_width_m, 2)),
            overall_isolation_status=status,
            mean_plot_containment=float(round(mean_containment, 4)),
            mean_external_leakage=float(round(mean_leakage, 4)),
            zero_external_leakage_verified=is_safe,
            total_observables_evaluated=len(audit_records),
            classification_breakdown=breakdown,
            audit_records=audit_records,
            recommended_action=rec_action,
        )

    @classmethod
    def _evaluate_single_observable(
        cls,
        obs_id: str,
        obs_data: Dict[str, Any],
        plot_enu: List[Tuple[float, float]],
        core_enu: List[Tuple[float, float]],
        env: Dict[str, Any],
    ) -> SpatialAuditRecord:
        """Evaluates spatial integration and classification for one radio observable."""
        modality = obs_data.get("modality", "GNSS_R")
        carrier_freq = float(obs_data.get("carrier_freq_hz", 1575.42e6))

        # Determine footprint geometry and sensitivity evaluator based on modality
        if modality == "GNSS_R":
            rx_enu = obs_data.get("receiver_enu_m", (0.0, 0.0, 2.5))
            elev = float(obs_data.get("elevation_deg", 48.0))
            az = float(obs_data.get("azimuth_deg", 135.0))
            is_spaceborne = bool(obs_data.get("is_spaceborne", False))

            fp = GnssReflectometryFootprint.compute_ground_footprint(
                rx_enu_m=rx_enu,
                elev_deg=elev,
                az_deg=az,
                carrier_freq_hz=carrier_freq,
                is_spaceborne=is_spaceborne,
            )
            sp_x, sp_y = fp["specular_point_enu_m"]
            semi_a = fp["semi_major_m"]
            semi_b = fp["semi_minor_m"]
            fp_az = fp["ellipse_azimuth_deg"]

            def evaluator(x: float, y: float, state_var: str) -> float:
                return GnssReflectometryFootprint.evaluate_sensitivity_at_point(
                    x=x,
                    y=y,
                    sp_x=sp_x,
                    sp_y=sp_y,
                    semi_major_m=semi_a,
                    semi_minor_m=semi_b,
                    ellipse_azimuth_deg=fp_az,
                    state_variable=state_var,
                )

            centroid = (sp_x, sp_y)
            footprint_shape = "ELLIPSE"
            major_dim = fp["major_axis_m"]
            minor_dim = fp["minor_axis_m"]
            bbox = (sp_x - semi_a * 1.5, sp_y - semi_a * 1.5), (sp_x + semi_a * 1.5, sp_y + semi_a * 1.5)

        elif modality == "CELLULAR":
            tower_enu = obs_data.get("tower_enu_m", (-80.0, -120.0, 25.0))
            rx_enu = obs_data.get("receiver_enu_m", (10.0, 15.0, 1.8))
            chord = CellularForwardScatterFootprint.compute_bistatic_chord(
                tower_enu_m=tower_enu,
                receiver_enu_m=rx_enu,
                carrier_freq_hz=carrier_freq,
            )
            r_fresnel = chord["max_fresnel_radius_m"]

            def evaluator(x: float, y: float, state_var: str) -> float:
                return CellularForwardScatterFootprint.evaluate_sensitivity_at_point(
                    x=x,
                    y=y,
                    tower_enu_m=tower_enu,
                    receiver_enu_m=rx_enu,
                    max_fresnel_radius_m=r_fresnel,
                    state_variable=state_var,
                )

            mid_x = (tower_enu[0] + rx_enu[0]) * 0.5
            mid_y = (tower_enu[1] + rx_enu[1]) * 0.5
            centroid = (mid_x, mid_y)
            footprint_shape = "CYLINDER"
            major_dim = chord["total_distance_m"]
            minor_dim = r_fresnel * 2.0
            min_x = min(tower_enu[0], rx_enu[0]) - r_fresnel * 2.0
            min_y = min(tower_enu[1], rx_enu[1]) - r_fresnel * 2.0
            max_x = max(tower_enu[0], rx_enu[0]) + r_fresnel * 2.0
            max_y = max(tower_enu[1], rx_enu[1]) + r_fresnel * 2.0
            bbox = ((min_x, min_y), (max_x, max_y))

        elif modality == "WIFI_CSI":
            tx_enu = obs_data.get("tx_enu_m", (-15.0, -10.0, 1.2))
            rx_enu = obs_data.get("rx_enu_m", (15.0, 10.0, 1.2))
            link = WifiMultipathFootprint.compute_link_geometry(
                tx_node_enu_m=tx_enu,
                rx_node_enu_m=rx_enu,
                carrier_freq_hz=carrier_freq,
            )
            r_fresnel = link["max_fresnel_radius_m"]

            def evaluator(x: float, y: float, state_var: str) -> float:
                return WifiMultipathFootprint.evaluate_sensitivity_at_point(
                    x=x,
                    y=y,
                    tx_node_enu_m=tx_enu,
                    rx_node_enu_m=rx_enu,
                    max_fresnel_radius_m=r_fresnel,
                    state_variable=state_var,
                )

            centroid = link["midpoint_enu_m"]
            footprint_shape = "CYLINDER"
            major_dim = link["baseline_distance_m"]
            minor_dim = r_fresnel * 2.0
            min_x = min(tx_enu[0], rx_enu[0]) - r_fresnel * 3.0
            min_y = min(tx_enu[1], rx_enu[1]) - r_fresnel * 3.0
            max_x = max(tx_enu[0], rx_enu[0]) + r_fresnel * 3.0
            max_y = max(tx_enu[1], rx_enu[1]) + r_fresnel * 3.0
            bbox = ((min_x, min_y), (max_x, max_y))

        elif modality == "SAR":
            pixel_center = obs_data.get("pixel_center_enu_m", (5.0, -5.0))
            heading = float(obs_data.get("flight_heading_deg", 192.0))

            def evaluator(x: float, y: float, state_var: str) -> float:
                return SarRadarFootprint.evaluate_pixel_point_spread(
                    x=x,
                    y=y,
                    pixel_center_enu_m=pixel_center,
                    flight_heading_deg=heading,
                    state_variable=state_var,
                )

            centroid = pixel_center
            footprint_shape = "RASTER_PIXEL"
            major_dim = 14.0
            minor_dim = 14.0
            px, py = pixel_center
            bbox = ((px - 20.0, py - 20.0), (px + 20.0, py + 20.0))

        else:  # BROADCAST_UHF
            rx_enu = obs_data.get("receiver_enu_m", (0.0, 0.0, 2.5))
            tx_az = float(obs_data.get("tx_azimuth_deg", 60.0))
            uhf_fp = BroadcastUhfFootprint.compute_scattering_footprint(
                tx_azimuth_deg=tx_az,
                rx_enu_m=rx_enu,
                carrier_freq_hz=carrier_freq,
            )
            cx, cy = uhf_fp["center_enu_m"]
            s_maj = uhf_fp["semi_major_m"]
            s_min = uhf_fp["semi_minor_m"]

            def evaluator(x: float, y: float, state_var: str) -> float:
                return BroadcastUhfFootprint.evaluate_sensitivity_at_point(
                    x=x,
                    y=y,
                    center_enu_m=(cx, cy),
                    semi_major_m=s_maj,
                    semi_minor_m=s_min,
                    tx_azimuth_deg=tx_az,
                    state_variable=state_var,
                )

            centroid = (cx, cy)
            footprint_shape = "ELLIPSE"
            major_dim = s_maj * 2.0
            minor_dim = s_min * 2.0
            bbox = ((cx - s_maj * 1.5, cy - s_maj * 1.5), (cx + s_maj * 1.5, cy + s_maj * 1.5))

        # Numerical integration of spatial sensitivity W_m,q(r)
        integration_results = SpatialSensitivityIntegrator.integrate_sensitivity(
            sensitivity_evaluator=evaluator,
            polygon_plot_enu=plot_enu,
            polygon_core_enu=core_enu,
            bbox_min_xy=bbox[0],
            bbox_max_xy=bbox[1],
            grid_resolution_m=1.5,
            sigma_cadastre_m=float(env.get("sigma_cadastre_m", 0.5)),
            sigma_receiver_m=float(env.get("sigma_receiver_m", 0.2)),
        )

        cont_plot: ContainmentInterval = integration_results["containment_plot"]
        cont_core: ContainmentInterval = integration_results["containment_core"]
        eta_ext_leakage: float = integration_results["eta_external_leakage"]
        eta_geom: float = integration_results["eta_geometric_diagnostic"]
        state_sens: StateSpecificSensitivity = integration_results["state_sensitivities"]

        # 5-Tier Classification
        tier, cov_scale, safe_root, safe_canopy, q_reason, justification = (
            SpatialGatingClassifier.classify(
                containment_plot=cont_plot,
                containment_core=cont_core,
                modality=modality,
                has_external_active_nuisance=bool(obs_data.get("external_nuisance_detected", False)),
            )
        )

        # Multi-hypothesis attribution
        delta_db = float(obs_data.get("observed_delta_db", 0.2))
        attribution = MultiHypothesisAttributionEngine.evaluate_external_causes(
            eta_hat_plot=cont_plot.eta_hat,
            eta_lower_plot=cont_plot.eta_lower,
            bearing_deg=float(obs_data.get("azimuth_deg", 90.0)),
            footprint_centroid_enu_m=centroid,
            classification_tier=tier,
            observed_delta_db=delta_db,
            rh_air_pct=float(env.get("rh_percent", 65.0)),
            hour_of_day=float(env.get("hour_of_day", 14.0)),
        )

        return SpatialAuditRecord(
            observation_id=obs_id,
            modality=modality,
            carrier_freq_hz=carrier_freq,
            footprint_shape=footprint_shape,
            footprint_centroid_enu_m=(round(centroid[0], 2), round(centroid[1], 2)),
            footprint_major_axis_m=round(major_dim, 2),
            footprint_minor_axis_m=round(minor_dim, 2),
            containment_plot=cont_plot,
            containment_core=cont_core,
            eta_external_leakage=round(eta_ext_leakage, 4),
            eta_geometric_diagnostic=round(eta_geom, 4),
            state_specific_sensitivities=state_sens,
            classification_tier=tier,
            covariance_scale_factor=round(cov_scale, 2),
            is_safe_for_root_zone_update=safe_root,
            is_safe_for_canopy_update=safe_canopy,
            quarantine_reason=q_reason,
            scientific_justification=justification,
            external_attribution=attribution,
        )
