"""
Shared provenance builder for perception engines.

Standardizes provenance creation so all engines produce
consistent processing chain records.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from datetime import datetime

from layer0.observation_packet import Provenance


def build_provenance(
    engine_family: str,
    processing_steps: List[str],
    model_versions: Optional[Dict[str, str]] = None,
    source_url: Optional[str] = None,
    cache_hit: bool = False,
) -> Provenance:
    """
    Build a standardized Provenance object from engine execution context.
    
    Args:
        engine_family: e.g. "satellite_rgb", "farmer_photo"
        processing_steps: ordered list of processing stages applied
            e.g. ["preprocess_crop", "qa_satellite", "segmentation_v1", "anomaly_v1"]
        model_versions: {model_name: version_string}
        source_url: original data source URI
        cache_hit: whether the result was served from cache
    
    Returns:
        Provenance with standardized processing chain.
    """
    # Build processing chain with engine prefix
    chain = [f"engine:{engine_family}"]
    chain.extend(processing_steps)

    # Add model versions to chain
    if model_versions:
        for name, version in model_versions.items():
            chain.append(f"model:{name}:{version}")

    # Build software version string
    sw_version = f"agriwise-perception-{engine_family}-v1"

    return Provenance(
        processing_chain=chain,
        software_version=sw_version,
        source_url=source_url,
        download_timestamp=datetime.now(),
        cache_hit=cache_hit,
    )
