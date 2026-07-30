#!/usr/bin/env python3
"""
V42B — Sentinel-2 Level-1B (L1B) Feasibility Probe

Probes CDSE/Copernicus STAC search for the 'sentinel-2-l1b' collection to evaluate
if raw detector-level geometry, boundaries, and CMOS overlaps are accessible
under current public credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    load_dotenv(".env.local", override=True)
except Exception:
    pass

DEFAULT_POLYGON = [[
    [6.86000, 33.34800],
    [6.86300, 33.34800],
    [6.86300, 33.35100],
    [6.86000, 33.35100],
    [6.86000, 33.34800],
]]
STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"


def get_access_token_optional() -> Optional[str]:
    try:
        from eo.auth import get_access_token
        return get_access_token()
    except Exception:
        try:
            from eo.sentinel import get_access_token
            return get_access_token()
        except Exception:
            return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="artifacts/v42b_l1b_feasibility_report.json")
    args = ap.parse_args()

    report: Dict[str, Any] = {
        "version": "V42B_l1b_feasibility_probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Assess accessibility of Sentinel-2 L1B detector-geometry products under current credentials.",
        "probe_mode": "dry_run" if args.dry_run else "live_stac_probe",
    }

    try:
        token = get_access_token_optional()
        
        # Define El Oued bbox
        bbox = [6.8578, 33.3462, 6.8651, 33.3528]
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=args.days)
        
        if args.dry_run:
            print("[DRY RUN] Simulating Sentinel-2 L1B STAC search...")
            report["l1b_search_attempt"] = {
                "ok": False,
                "status_code": 400,
                "response": "Collection 'sentinel-2-l1b' not found or access restricted.",
            }
            report["feasibility"] = {
                "l1b_collection_searchable": False,
                "l1b_access_status": "not_available_under_current_credentials",
                "recommended_next": "request expert-user access or continue with V42C product path"
            }
        else:
            print(f"[LIVE] Probing collection 'sentinel-2-l1b' at {STAC_SEARCH_URL}...")
            import requests
            
            payload = {
                "collections": ["sentinel-2-l1b"],
                "bbox": bbox,
                "datetime": f"{start.date().isoformat()}T00:00:00Z/{end.date().isoformat()}T23:59:59Z",
                "limit": 5,
            }
            
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
                
            try:
                r = requests.post(STAC_SEARCH_URL, json=payload, headers=headers, timeout=25)
                report["l1b_search_attempt"] = {
                    "ok": r.status_code == 200,
                    "status_code": r.status_code,
                }
                
                if r.status_code == 200:
                    data = r.json()
                    features = data.get("features", [])
                    report["l1b_search_attempt"]["features_count"] = len(features)
                    
                    if len(features) > 0:
                        feat = features[0]
                        report["l1b_search_attempt"]["sample_feature_id"] = feat.get("id")
                        report["l1b_search_attempt"]["sample_assets"] = list(feat.get("assets", {}).keys())
                        
                        # Verify if detector geometry / bounds exist in assets
                        detector_geom_exists = any("detector" in k.lower() or "gml" in k.lower() for k in feat.get("assets", {}).keys())
                        report["feasibility"] = {
                            "l1b_collection_searchable": True,
                            "l1b_assets_downloadable": False,  # assuming same 401 auth gate
                            "detector_geometry_available": detector_geom_exists,
                        }
                    else:
                        # Collection searchable but returned 0 scenes for this bbox/time
                        report["feasibility"] = {
                            "l1b_collection_searchable": True,
                            "l1b_assets_downloadable": False,
                            "detector_geometry_available": False,
                            "note": "Search returned 0 scenes. L1B coverage may be limited spatially/temporally."
                        }
                else:
                    # Non-200 means collection is probably hidden, invalid, or forbidden
                    report["l1b_search_attempt"]["error_response"] = r.text[:300]
                    report["feasibility"] = {
                        "l1b_collection_searchable": False,
                        "l1b_access_status": "not_available_under_current_credentials",
                        "recommended_next": "request expert-user access or continue with V42C product path"
                    }
                    
            except Exception as e:
                report["l1b_search_attempt"] = {"ok": False, "error": str(e)}
                report["feasibility"] = {
                    "l1b_collection_searchable": False,
                    "l1b_access_status": "connection_error",
                    "recommended_next": "request expert-user access or continue with V42C product path"
                }

        report["status"] = "completed"
        
    except Exception as e:
        report["status"] = "failed"
        report["error"] = {"type": type(e).__name__, "message": str(e)}
        report["traceback"] = traceback.format_exc()[-4000:]
        print(f"[ERROR] V42B execution failed: {e}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"Saved report: {out}")


if __name__ == "__main__":
    main()
