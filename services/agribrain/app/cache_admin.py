"""
Cache Admin API — Observability endpoints for the AgriBrain Cortex.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends

from layer0.data_gateway.storage_manager import StorageManager
from layer0.learning.pattern_maturity import PatternMaturityEngine
from layer0.learning.dna_recalibration import DNARecalibrationScheduler
from services.agribrain.app.internal_service_auth import require_internal_service_request
from services.agribrain.common.plot_namespace import PlotNamespace

logger = logging.getLogger("agribrain.app.cache_admin")

router = APIRouter(prefix="/v2/gateway", tags=["Cortex Gateway Admin"])
storage_manager = StorageManager()
maturity_engine = PatternMaturityEngine()
dna_scheduler = DNARecalibrationScheduler()


@router.get("/stats")
def get_gateway_stats() -> Dict[str, Any]:
    """Get cache performance metrics, MongoDB status, and filesystem fallbacks."""
    try:
        return storage_manager.get_stats()
    except Exception as e:
        logger.error("[ADMIN_API] Failed to get gateway stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/freshness/{plot_id}")
def get_plot_freshness(
    plot_id: str,
    namespace: PlotNamespace = Depends(require_internal_service_request),
) -> Dict[str, Any]:
    """Get real-time TTL freshness and age status for every data source on a plot."""
    try:
        report = storage_manager.get_freshness_report(plot_id)
        return {source: entry.to_dict() for source, entry in report.items()}
    except Exception as e:
        logger.error("[ADMIN_API] Failed to get plot freshness: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invalidate/{plot_id}")
def invalidate_plot_cache(
    plot_id: str,
    source: Optional[str] = None,
    namespace: PlotNamespace = Depends(require_internal_service_request),
) -> Dict[str, Any]:
    """Force-invalidate cache entries (MongoDB + filesystem) for a specific plot."""
    try:
        count = storage_manager.invalidate(plot_id, source)
        return {
            "status": "success",
            "plot_id": plot_id,
            "source_invalidated": source or "all",
            "entries_cleared": count
        }
    except Exception as e:
        logger.error("[ADMIN_API] Failed to invalidate plot cache: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/maturity/{plot_id}")
def get_pattern_maturity(
    plot_id: str,
    namespace: PlotNamespace = Depends(require_internal_service_request),
) -> Dict[str, Any]:
    """Get the 12 ML pattern maturity activation and weight-blending report for a plot."""
    try:
        return maturity_engine.get_plot_maturity_report(plot_id)
    except Exception as e:
        logger.error("[ADMIN_API] Failed to get pattern maturity report: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evolution/{plot_id}")
def get_dna_evolution_history(
    plot_id: str,
    namespace: PlotNamespace = Depends(require_internal_service_request),
) -> List[Dict[str, Any]]:
    """Get the historical timeline of versioned biophysical PlotDNA snapshots."""
    try:
        return dna_scheduler.get_dna_evolution(plot_id)
    except Exception as e:
        logger.error("[ADMIN_API] Failed to get DNA evolution timeline: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
