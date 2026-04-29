"""
Sentinel-1 SAR Observation Engine V1.

Top-level orchestrator. Strict, local, no API calls.
Expects pre-fetched, PlotGrid-aligned GRD rasters (VV/VH linear power).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from layer0.sentinel1.schemas import (
    SARRaster2D,
    SARQualityClass,
    Sentinel1SceneMetadata,
    Sentinel1ScenePackage,
)
from layer0.sentinel1.resolution import validate_sar_alignment
from layer0.sentinel1.masks import compute_sar_masks
from layer0.sentinel1.features import compute_feature_raster, SUPPORTED_FEATURES
from layer0.sentinel1.qa import compute_sar_qa
from layer0.sentinel1.plot_extract import (
    extract_sar_plot_summary,
    generate_quadrant_zones,
    extract_sar_zone_summaries,
)
from layer0.sentinel1.packetizer import emit_sar_packets
from layer0.sentinel1.kalman_adapter import create_sar_kalman_observations
from layer0.sentinel1.provenance import (
    SARProvenanceError,
    validate_sar_provenance,
    build_sar_trust_report,
)
from layer0.sentinel1.diagnostics import build_sar_diagnostics


class Sentinel1Engine:
    """Sentinel-1 SAR V1 Observation Engine."""

    def process_scene(
        self,
        rasters: Dict[str, SARRaster2D],
        metadata: Sentinel1SceneMetadata,
        alpha_mask: List[List[float]],
        datamask: Optional[List[List[int]]] = None,
        incidence_angle: Optional[List[List[Optional[float]]]] = None,
        zone_masks: Optional[Dict[str, List[List[float]]]] = None,
        context: Optional[Dict[str, Any]] = None,
        age_days: Optional[float] = None,
        baseline_orbit_direction: Optional[str] = None,
    ) -> Sentinel1ScenePackage:
        """
        Full SAR V1 pipeline:
        1. Validate provenance (fatal)
        2. Validate alignment
        3. Compute masks
        4. Compute QA
        5. Compute features
        6. Plot summary
        7. Zone summaries (with plot_alpha_mask)
        8. Build packets
        9. Create Kalman observations
        10. Build diagnostics + provenance
        11. Return Sentinel1ScenePackage

        Raises SARProvenanceError if mandatory metadata is missing.
        """
        # 1. Validate provenance (fatal)
        validate_sar_provenance(metadata)

        # 2. Validate alignment
        validate_sar_alignment(rasters, alpha_mask, metadata)

        vv = rasters["VV"]
        vh = rasters["VH"]
        h, w = vv.grid_shape

        # 3. Compute masks
        mask_set = compute_sar_masks(
            vv_linear=vv.values,
            vh_linear=vh.values,
            datamask=datamask,
            alpha_mask=alpha_mask,
        )

        # 4. Compute QA
        qa = compute_sar_qa(
            mask_set=mask_set,
            alpha_mask=alpha_mask,
            vv_linear=vv.values,
            incidence_angle=incidence_angle,
            age_days=age_days,
            orbit_direction=metadata.orbit_direction,
            baseline_orbit_direction=baseline_orbit_direction,
        )

        # 5. Compute features (with feature-specific masks)
        features: Dict[str, SARRaster2D] = {}
        feature_diags = {}

        if qa.usable:
            for feat_name in SUPPORTED_FEATURES:
                feature_mask = _choose_feature_mask(feat_name, mask_set)
                feat_raster, diag = compute_feature_raster(
                    feat_name, vv, vh,
                    valid_mask=feature_mask,
                    incidence_raster=incidence_angle,
                )
                features[feat_name] = feat_raster
                feature_diags[feat_name] = diag

        # 6. Plot summary
        plot_summary = extract_sar_plot_summary(features, qa, mask_set, alpha_mask)

        # 7. Zone summaries
        if zone_masks is None:
            # Attempt data-driven zones from SAR weakness raster
            if "VV_DB" in features:
                from layer0.weakness_raster import (
                    compute_weakness_raster_sar as _compute_wsr_sar,
                    derive_zones_from_weakness as _derive_zones,
                )
                _wsr = _compute_wsr_sar(
                    features["VV_DB"], alpha_mask,
                )
                _zone_result = _derive_zones(_wsr, alpha_mask)
                zone_masks = _zone_result.zone_masks
            else:
                zone_masks = generate_quadrant_zones(alpha_mask)
        zone_summaries = extract_sar_zone_summaries(
            features, qa, mask_set, zone_masks, alpha_mask,
        )

        # 8. Kalman observations
        kalman_obs = create_sar_kalman_observations(
            plot_summary, qa, metadata, context
        )

        # 9. Provenance / trust report
        provenance = build_sar_trust_report(metadata, qa, plot_summary)

        # 10. Diagnostics
        diagnostics = build_sar_diagnostics(
            metadata, qa, feature_diags, zone_summaries,
            kalman_count=len(kalman_obs),
        )

        # 11. Raster refs for packet
        raster_refs = {}
        for name, raster in features.items():
            h_val = raster.compute_content_hash()
            raster_refs[name] = h_val

        # 12. Packets
        packets = emit_sar_packets(
            metadata, qa, plot_summary, zone_summaries,
            feature_names_computed=list(features.keys()),
            raster_refs=raster_refs,
            provenance=provenance,
        )

        return Sentinel1ScenePackage(
            metadata=metadata,
            rasters=rasters,
            features=features,
            qa=qa,
            plot_summary=plot_summary,
            zone_summaries=zone_summaries,
            packets=packets,
            kalman_observations=kalman_obs,
            diagnostics=diagnostics,
            provenance=provenance,
        )


def _choose_feature_mask(feat_name: str, mask_set) -> List[List[int]]:
    """Select the appropriate mask for each feature type.

    - Moisture features use valid_for_moisture (excludes low signal)
    - Structure/vegetation features use valid_for_structure
    - All others use valid_for_backscatter
    """
    if feat_name == "SURFACE_WETNESS_PROXY":
        return mask_set.valid_for_moisture
    if feat_name in ("STRUCTURE_PROXY", "RVI", "CROSS_POL_FRACTION"):
        return mask_set.valid_for_structure
    return mask_set.valid_for_backscatter

