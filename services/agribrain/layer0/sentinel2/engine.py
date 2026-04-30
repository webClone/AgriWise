"""
Sentinel-2 Engine — Top-level orchestrator.

Single entry point: process_scene() wires alignment → masks → indices → QA
→ summaries → packets → Kalman observations → diagnostics.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from layer0.sentinel2.schemas import (
    Raster2D,
    Sentinel2SceneMetadata,
    Sentinel2ScenePackage,
)
from layer0.sentinel2.resolution import validate_band_alignment, AlignmentError


class ProvenanceError(Exception):
    """Raised when mandatory provenance fields are missing."""
    pass
from layer0.sentinel2.masks import compute_masks
from layer0.sentinel2.indices import (
    SUPPORTED_INDICES,
    RasterComputationDiagnostics,
    compute_index_raster,
)
from layer0.sentinel2.qa import compute_qa
from layer0.sentinel2.plot_extract import (
    extract_plot_summary,
    extract_zone_summaries,
    generate_quadrant_zones,
)
from layer0.sentinel2.packetizer import packetize
from layer0.sentinel2.kalman_adapter import create_kalman_observations
from layer0.sentinel2.provenance import validate_provenance
from layer0.sentinel2.diagnostics import build_diagnostics


class Sentinel2Engine:
    """
    Full Sentinel-2 perception pipeline for Layer 0.

    Accepts pre-fetched, PlotGrid-aligned band rasters.
    Does NOT call Sentinel Hub API.
    """

    def process_scene(
        self,
        bands: Dict[str, Raster2D],
        scl_raster: List[List[Optional[float]]],
        datamask_raster: Optional[List[List[int]]],
        metadata: Sentinel2SceneMetadata,
        alpha_mask: List[List[float]],
        zone_masks: Optional[Dict[str, List[List[float]]]] = None,
        age_days: int = 0,
        buffer_pixels: int = 2,
    ) -> Sentinel2ScenePackage:
        """
        Full pipeline: bands → alignment check → masks → indices → QA
        → summaries → diagnostics → ScenePackage.

        Args:
            bands: Pre-fetched, PlotGrid-aligned band rasters (B02, B04, etc.)
            scl_raster: Scene Classification Layer values
            datamask_raster: Data validity mask (optional)
            metadata: Scene-level provenance
            alpha_mask: PlotGrid fractional coverage mask
            zone_masks: Optional per-zone alpha masks (auto-generated if None)
            age_days: Scene age in days
            buffer_pixels: Buffer for boundary contamination
        """
        # 1. Validate alignment
        validate_band_alignment(bands, alpha_mask)

        # 2. Validate provenance (fatal — mandatory fields must be present)
        prov_errors = metadata.validate()
        if prov_errors:
            raise ProvenanceError(
                f"Missing mandatory Sentinel-2 provenance fields: {prov_errors}"
            )

        # 3. Compute masks from SCL
        mask_set = compute_masks(scl_raster, datamask_raster)

        # 4. Compute QA
        qa_result = compute_qa(mask_set, alpha_mask, age_days)

        # 5. Compute indices (even for UNUSABLE — diagnostics need them)
        index_rasters: Dict[str, Raster2D] = {}
        index_diags: Dict[str, RasterComputationDiagnostics] = {}
        valid_mask = mask_set.valid_for_index

        for idx_name in SUPPORTED_INDICES:
            # Check if required bands are available
            required = SUPPORTED_INDICES[idx_name]["required_bands"]
            if not all(b in bands for b in required):
                continue

            try:
                raster, diag = compute_index_raster(
                    idx_name,
                    bands,
                    valid_mask,
                    scale=bands[required[0]].value_scale if required[0] in bands else "reflectance_0_1",
                )
                # Compute content hash for raster refs
                raster.compute_content_hash()
                index_rasters[idx_name] = raster
                index_diags[idx_name] = diag
            except (ValueError, IndexError):
                pass

        # 6. Compute plot summary
        plot_summary = extract_plot_summary(
            index_rasters, qa_result, mask_set, alpha_mask, buffer_pixels
        )

        # 7. Generate or use zone masks
        if zone_masks is None:
            # Attempt data-driven zones from weakness raster
            if "NDVI" in index_rasters:
                from layer0.weakness_raster import (
                    compute_weakness_raster as _compute_wsr,
                    derive_zones_from_weakness as _derive_zones,
                )
                _wsr = _compute_wsr(
                    index_rasters["NDVI"], alpha_mask, valid_mask,
                    ndmi_raster=index_rasters.get("NDMI"),
                    evi_raster=index_rasters.get("EVI"),
                    buffer_pixels=buffer_pixels,
                )
                _zone_result = _derive_zones(_wsr, alpha_mask)
                zone_masks = _zone_result.zone_masks
                zone_source = _zone_result.zone_source
                zone_method = _zone_result.zone_method
                zone_confidence = _zone_result.zone_confidence
            else:
                # No NDVI — pure geometry fallback
                zone_masks = generate_quadrant_zones(alpha_mask)
                zone_source = "geometry_fallback"
                zone_method = "auto_quadrant_v1"
                zone_confidence = 0.25
        else:
            zone_source = "user_defined"
            zone_method = "user_provided"
            zone_confidence = 0.8

        zone_summaries = extract_zone_summaries(
            index_rasters, qa_result, mask_set, zone_masks,
            alpha_mask,
            zone_source, zone_method, zone_confidence,
        )

        # 8. Build Kalman observations for diagnostics count
        pkg = Sentinel2ScenePackage(
            plot_id=metadata.plot_geometry_hash,
            metadata=metadata,
            bands=bands,
            indices=index_rasters,
            qa=qa_result,
            plot_summary=plot_summary,
            zone_summaries=zone_summaries,
        )

        kalman_obs = create_kalman_observations(pkg)

        # 9. Build diagnostics
        skipped = []
        for idx_name in SUPPORTED_INDICES:
            mapping_type = {
                "NDVI": "ndvi", "EVI": "evi", "NDMI": "ndmi",
                "NDRE": "ndre", "BSI": "bare_soil_index",
            }.get(idx_name, idx_name.lower())
            if not any(o.obs_type == mapping_type for o in kalman_obs):
                if idx_name in index_rasters:
                    skipped.append(f"{idx_name}_no_kalman_value")

        pkg.diagnostics = build_diagnostics(
            pkg, index_diags, len(kalman_obs), skipped
        )

        return pkg
