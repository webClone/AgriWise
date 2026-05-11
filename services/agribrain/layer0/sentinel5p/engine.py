"""
Sentinel-5P SIF Acquisition Engine V1.

Top-level orchestrator. Pipeline:
  1. Validate scene metadata provenance
  2. Extract SIF data from provider response
  3. Run QA engine (cloud, solar zenith, valid fraction)
  4. Build Kalman observations (if usable)
  5. Build diagnostics
  6. Return Sentinel5PScenePackage

No live API calls — all data is pre-fetched and passed in.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from layer0.sentinel5p.schemas import (
    SIFData,
    SIFQualityClass,
    Sentinel5PQAResult,
    Sentinel5PSceneMetadata,
    Sentinel5PScenePackage,
)
from layer0.sentinel5p.qa import compute_qa
from layer0.sentinel5p.kalman_adapter import (
    Sentinel5PKalmanObservation,
    create_kalman_observations,
)


class Sentinel5PEngine:
    """Sentinel-5P SIF Acquisition Engine V1."""

    def process(
        self,
        plot_id: str,
        plot_geometry: Optional[Dict[str, Any]] = None,
        tropomi_data: Optional[Dict[str, Any]] = None,
        acquisition_datetime: Optional[datetime] = None,
        age_days: int = 0,
    ) -> Sentinel5PScenePackage:
        """
        Process a TROPOMI SIF scene for a given plot.

        Args:
            plot_id: Unique plot identifier.
            plot_geometry: GeoJSON-like dict for geometry hashing.
            tropomi_data: Pre-fetched TROPOMI response dict.
            acquisition_datetime: Scene acquisition timestamp.
            age_days: Days since acquisition.

        Returns:
            Sentinel5PScenePackage with QA verdict and optional Kalman obs.
        """
        # 1. Build metadata
        geometry_hash = ""
        if plot_geometry:
            raw = json.dumps(plot_geometry, sort_keys=True, default=str).encode()
            geometry_hash = hashlib.sha256(raw).hexdigest()[:16]

        metadata = Sentinel5PSceneMetadata(
            scene_id=self._extract_scene_id(tropomi_data),
            acquisition_datetime=acquisition_datetime,
            provider="TROPOMI",
            processing_level=self._extract_str(tropomi_data, "processing_level", "L2A"),
            orbit_number=self._extract_int(tropomi_data, "orbit_number"),
            footprint_km2=self._extract_float(tropomi_data, "footprint_km2"),
            spatial_resolution_km=self._extract_float(
                tropomi_data, "spatial_resolution_km", default=7.0
            ),
            cloud_fraction=self._extract_float(tropomi_data, "cloud_fraction"),
            solar_zenith_angle=self._extract_float(tropomi_data, "solar_zenith_angle"),
            sif_retrieval_method=self._extract_str(
                tropomi_data, "sif_retrieval_method", "TROPOSIF"
            ),
            plot_geometry_hash=geometry_hash,
        )

        # 2. Validate metadata
        validation_errors = metadata.validate()
        if validation_errors:
            return self._unusable_package(
                plot_id, metadata,
                reason=f"Metadata validation failed: {', '.join(validation_errors)}",
                flags=["METADATA_INVALID"],
            )

        # 3. Extract SIF data
        sif_data = self._extract_sif_data(tropomi_data)

        # 4. Run QA
        qa_result = compute_qa(
            sif_data=sif_data,
            cloud_fraction=metadata.cloud_fraction,
            solar_zenith=metadata.solar_zenith_angle,
            spatial_resolution_km=metadata.spatial_resolution_km,
            age_days=age_days,
        )

        # 5. Build Kalman observations
        pkg = Sentinel5PScenePackage(
            plot_id=plot_id,
            metadata=metadata,
            sif_data=sif_data,
            qa=qa_result,
        )

        kalman_obs = create_kalman_observations(pkg)

        # 6. Build diagnostics
        pkg.diagnostics = self._build_diagnostics(
            metadata, sif_data, qa_result, kalman_obs, validation_errors
        )

        return pkg

    # ================================================================
    # Extraction helpers
    # ================================================================

    def _extract_scene_id(self, data: Optional[Dict]) -> str:
        if not data:
            return ""
        return str(data.get("scene_id", data.get("granule_id", "")))

    def _extract_str(self, data: Optional[Dict], key: str, default: str = "") -> str:
        if not data:
            return default
        return str(data.get(key, default))

    def _extract_int(self, data: Optional[Dict], key: str, default: int = 0) -> int:
        if not data:
            return default
        try:
            return int(data.get(key, default))
        except (ValueError, TypeError):
            return default

    def _extract_float(
        self, data: Optional[Dict], key: str, default: float = 0.0
    ) -> float:
        if not data:
            return default
        try:
            return float(data.get(key, default))
        except (ValueError, TypeError):
            return default

    def _extract_sif_data(self, data: Optional[Dict]) -> SIFData:
        """Extract SIF measurements from provider response."""
        if not data:
            return SIFData()

        sif_block = data.get("sif", data)

        return SIFData(
            sif_daily_mean=self._safe_float(sif_block.get("sif_daily_mean")),
            sif_daily_std=self._safe_float(sif_block.get("sif_daily_std")),
            sif_instantaneous=self._safe_float(sif_block.get("sif_instantaneous")),
            sif_relative=self._safe_float(sif_block.get("sif_relative")),
            par_mean=self._safe_float(sif_block.get("par_mean")),
            valid_pixel_count=self._extract_int(sif_block, "valid_pixel_count"),
            total_pixel_count=self._extract_int(sif_block, "total_pixel_count"),
        )

    def _safe_float(self, val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    # ================================================================
    # Package builders
    # ================================================================

    def _unusable_package(
        self,
        plot_id: str,
        metadata: Sentinel5PSceneMetadata,
        reason: str,
        flags: List[str],
    ) -> Sentinel5PScenePackage:
        """Return an UNUSABLE package with diagnostics."""
        return Sentinel5PScenePackage(
            plot_id=plot_id,
            metadata=metadata,
            sif_data=SIFData(),
            qa=Sentinel5PQAResult(
                usable=False,
                quality_class=SIFQualityClass.UNUSABLE,
                overall_score=0.0,
                reliability_weight=0.0,
                reason=reason,
                flags=flags,
            ),
            diagnostics={
                "engine_version": "sentinel5p_sif_v1",
                "unusable_reason": reason,
                "kalman_observations_emitted": 0,
            },
        )

    def _build_diagnostics(
        self,
        metadata: Sentinel5PSceneMetadata,
        sif_data: SIFData,
        qa: Sentinel5PQAResult,
        kalman_obs: List[Sentinel5PKalmanObservation],
        validation_errors: List[str],
    ) -> Dict[str, Any]:
        """Build comprehensive diagnostics dict."""
        return {
            "engine_version": "sentinel5p_sif_v1",
            "scene_id": metadata.scene_id,
            "provider": metadata.provider,
            "retrieval_method": metadata.sif_retrieval_method,
            "spatial_resolution_km": metadata.spatial_resolution_km,
            "qa_quality_class": qa.quality_class.value,
            "qa_usable": qa.usable,
            "qa_reliability_weight": qa.reliability_weight,
            "qa_sigma_multiplier": qa.sigma_multiplier,
            "qa_flags": qa.flags,
            "sif_daily_mean": sif_data.sif_daily_mean,
            "sif_valid_fraction": sif_data.valid_fraction,
            "kalman_observations_emitted": len(kalman_obs),
            "kalman_obs_types": [o.obs_type for o in kalman_obs],
            "kalman_reliabilities": [o.reliability for o in kalman_obs],
            "metadata_validation_errors": validation_errors,
            "resolution_ceiling_note": (
                "Reliability capped at 0.45 due to TROPOMI ~7km spatial resolution. "
                "SIF signal is diluted by surrounding landscape."
            ),
        }
