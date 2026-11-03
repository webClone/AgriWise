from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

@dataclass
class SceneProduct:
    scene_id: str
    sensor: str  # "S2" or "S1"
    acquisition_datetime: datetime
    crs: str
    transform: Tuple[float, float, float, float, float, float]
    width: int
    height: int
    band_refs: Dict[str, str] = field(default_factory=dict)
    mask_refs: Dict[str, str] = field(default_factory=dict)
    # Physical units of provider bands.  Feature/display rasters must never
    # be inferred as calibrated measurements from their numeric range.
    band_units: Dict[str, str] = field(default_factory=dict)
    quality: Dict[str, Any] = field(default_factory=dict)
    # Authority fields are deliberately fail-closed.  Every provider adapter
    # must opt in after it proves product identity, units, masks and geometry.
    source_reality: str = "unknown"
    test_override: bool = False
    production_usable: bool = False
    diagnostic_only: bool = True
    real_provider_product: bool = False
    usable_for_1m_approval: bool = False
    usable_for_advisory: bool = False
    excluded_from_archive_metrics: bool = False
    excluded_from_retrovalidation_holdouts: bool = False
    excluded_from_bma_holdout_performance: bool = False
    provider_product_id: Optional[str] = None
    # Exact acquisition lineage. catalog_item_id is selected by Catalog;
    # provider_product_id is matched against Sentinel Hub tile.productId.
    catalog_item_id: Optional[str] = None
    provider_tile_id: Optional[str] = None
    provider_orbit_id: Optional[str] = None
    provider_orbit_pass: Optional[str] = None
    provider_relative_orbit: Optional[str] = None
    provider_absolute_orbit: Optional[str] = None
    process_metadata: Dict[str, Any] = field(default_factory=dict)
    catalog_metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: Optional[str] = None
    process_request_hash: Optional[str] = None
    provider_response_hash: Optional[str] = None
    # B2B-01 acquisition TRACE ONLY. The underlying native response is
    # unqualified and cannot mint a state-input receipt from this metadata.
    native_catalog_acquisition_id: Optional[str] = None
    native_process_acquisition_id: Optional[str] = None
    native_evidence_status: str = "UNATTESTED"
    product_binding: str = "unknown"
    binding_proof: Dict[str, Any] = field(default_factory=dict)
    duplicate_of_content_hash: Optional[str] = None
    temporal_basis: str = "instant"
    independent_observation_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "sensor": self.sensor,
            "acquisition_datetime": self.acquisition_datetime.isoformat(),
            "crs": self.crs,
            "transform": list(self.transform),
            "width": self.width,
            "height": self.height,
            "band_refs": self.band_refs,
            "mask_refs": self.mask_refs,
            "band_units": self.band_units,
            "quality": self.quality,
            "source_reality": self.source_reality,
            "test_override": self.test_override,
            "production_usable": self.production_usable,
            "diagnostic_only": self.diagnostic_only,
            "real_provider_product": self.real_provider_product,
            "usable_for_1m_approval": self.usable_for_1m_approval,
            "usable_for_advisory": self.usable_for_advisory,
            "excluded_from_archive_metrics": self.excluded_from_archive_metrics,
            "excluded_from_retrovalidation_holdouts": self.excluded_from_retrovalidation_holdouts,
            "excluded_from_bma_holdout_performance": self.excluded_from_bma_holdout_performance,
            "provider_product_id": self.provider_product_id,
            "catalog_item_id": self.catalog_item_id,
            "provider_tile_id": self.provider_tile_id,
            "provider_orbit_id": self.provider_orbit_id,
            "provider_orbit_pass": self.provider_orbit_pass,
            "provider_relative_orbit": self.provider_relative_orbit,
            "provider_absolute_orbit": self.provider_absolute_orbit,
            "process_metadata": self.process_metadata,
            "catalog_metadata": self.catalog_metadata,
            "content_hash": self.content_hash,
            "process_request_hash": self.process_request_hash,
            "provider_response_hash": self.provider_response_hash,
            "native_catalog_acquisition_id": self.native_catalog_acquisition_id,
            "native_process_acquisition_id": self.native_process_acquisition_id,
            "native_evidence_status": self.native_evidence_status,
            "product_binding": self.product_binding,
            "binding_proof": self.binding_proof,
            "duplicate_of_content_hash": self.duplicate_of_content_hash,
            "temporal_basis": self.temporal_basis,
            "independent_observation_count": self.independent_observation_count,
        }
