"""
One-Meter Status Snapshot Provider (V90.10)
===========================================

Computes the definitive status of 1m resolution inferences, certified display records,
and archive support validation for a specific plot.
"""

import os
import json
from typing import Optional, List, Dict, Any
from certification.v90_storage import V90Storage
from certification.v90_resolver import verify_v90_certification_record
from certification.archive_support_summary import get_archive_support_summary

def build_one_meter_status_snapshot(
    plot_id: str,
    surfaces: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Builds a definitive snapshot indicating how much 1m inferred detail is accepted
    for state updates, training, or prescriptions, and lists available archive support.
    """
    # 1. Fetch archive support summary
    support = get_archive_support_summary(plot_id)

    # 2. Count V90 records from directory
    storage = V90Storage()
    cert_dir = storage.cert_root / "records"
    v90_record_count = 0
    v90_approved_count = 0

    if cert_dir.exists():
        for filename in os.listdir(cert_dir):
            if filename.endswith(".json"):
                try:
                    with open(cert_dir / filename, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("plot_id") == plot_id:
                            v90_record_count += 1
                            res = verify_v90_certification_record(
                                certification_id=data.get("certification_id"),
                                plot_id=plot_id,
                                variable=data.get("variable"),
                                geometry_hash=data.get("geometry_hash"),
                                crop_season_id=data.get("crop_season_id")
                            )
                            if res.approved:
                                v90_approved_count += 1
                except Exception:
                    pass

    # 3. Determine counts source and compile results
    if surfaces is not None:
        display_certified_count = 0
        visual_only_count = 0
        
        for s in surfaces:
            # Determine native/provenance resolution
            res = getattr(s, "native_resolution_m", 10.0)
            provenance = getattr(s, "provenance", {}) or {}
            res_prov = provenance.get("resolution_m", res)
            
            if res_prov <= 1.0:
                if provenance.get("display_certified", False):
                    display_certified_count += 1
                if provenance.get("visual_only", False):
                    visual_only_count += 1
                    
        return {
            "plot_id": plot_id,
            "one_meter_state_update_accepted": 0,
            "one_meter_training_accepted": 0,
            "one_meter_prescription_accepted": 0,
            "one_meter_display_certified_count": display_certified_count,
            "one_meter_visual_only_count": visual_only_count,
            "v90_certification_record_count": v90_record_count,
            "archive_can_certify_alone": False,
            "archive_support_available": support["archive_support_available"],
            "final_policy": "display_only_unless_v90_record",
            "archive_support": support,
            "count_source": "layer10_surfaces"
        }
    else:
        return {
            "plot_id": plot_id,
            "one_meter_state_update_accepted": 0,
            "one_meter_training_accepted": 0,
            "one_meter_prescription_accepted": 0,
            "one_meter_display_certified_count": v90_approved_count,
            "one_meter_visual_only_count": None,
            "v90_certification_record_count": v90_record_count,
            "archive_can_certify_alone": False,
            "archive_support_available": support["archive_support_available"],
            "final_policy": "display_only_unless_v90_record",
            "archive_support": support,
            "count_source": "certification_records_only"
        }
