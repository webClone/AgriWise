"""
Archive Support Summary Provider (V90.10)
========================================

Extracts explicit diagnostic metrics from the Sentinel historical archive.
"""

from typing import Dict, Any
from layer05_asmae.history.archive_metrics_store import ArchiveMetricsStore

def get_archive_support_summary(plot_id: str) -> Dict[str, Any]:
    """Reads latest archive metrics for plot_id and returns a standardized support summary."""
    store = ArchiveMetricsStore()
    
    try:
        metrics_info = store.get_latest_metrics_info(plot_id)
    except Exception:
        metrics_info = None

    if not metrics_info:
        return {
            "archive_support_available": False,
            "retrovalidation_score": 0.0,
            "bma_disagreement": 0.0,
            "baseline_available": False,
            "can_certify_alone": False,
            "can_support_v90_review": False,
            "required_missing_items": [
                "approved_external_validation",
                "manual_admin_approval",
                "v90_certification_record"
            ]
        }

    data = metrics_info.get("data", {})
    hist_data = data.get("historical_metrics", {})
    retro_data = data.get("retrovalidation_metrics", {})
    bma_data = data.get("archive_bma_metrics", {})
    base_data = data.get("baseline_metrics", {})

    # Extract retrovalidation score (RMSE)
    retro_val = retro_data.get("rmse") or retro_data.get("retrovalidation_score")
    if retro_val is not None:
        retro_val = float(retro_val)
    else:
        retro_val = float(hist_data.get("retrovalidation_score", 0.0))

    # Extract BMA disagreement
    bma_val = bma_data.get("bma_disagreement")
    if bma_val is not None:
        bma_val = float(bma_val)
    else:
        bma_val = float(hist_data.get("bma_disagreement", 0.0))

    # Baseline check
    baseline_available = bool(base_data or hist_data.get("baseline_doy_mean"))

    return {
        "archive_support_available": True,
        "retrovalidation_score": retro_val,
        "bma_disagreement": bma_val,
        "baseline_available": baseline_available,
        "can_certify_alone": False,
        "can_support_v90_review": True,
        "required_missing_items": [
            "approved_external_validation",
            "manual_admin_approval",
            "v90_certification_record"
        ]
    }
