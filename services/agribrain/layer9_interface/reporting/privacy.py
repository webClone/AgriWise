import os
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class PrivacyDecision:
    allowed: bool
    suppressed: bool
    plot_count: int
    owner_count: int
    crop_diversity: int
    reason: Optional[str] = None

def get_privacy_salt() -> str:
    env = os.environ.get("ENVIRONMENT", "development")
    salt = os.environ.get("REPORTING_PRIVACY_SALT")
    if not salt:
        if env == "production":
            raise RuntimeError("REPORTING_PRIVACY_SALT is required in production environment.")
        else:
            salt = "deterministic_test_salt_123"
    return salt

def hash_plot_id(plot_id: str, salt: Optional[str] = None) -> str:
    if not plot_id or plot_id == "UNKNOWN":
        return "UNKNOWN"
    if not salt:
        salt = get_privacy_salt()
    
    payload = f"{plot_id}:{salt}"
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"plot_hash_{h}"

def coarsen_coordinates(lat: Optional[float], lon: Optional[float]) -> dict:
    if lat is None or lon is None:
        return {"latitude": None, "longitude": None, "coordinate_policy": "removed"}
    # Round to 1 decimal place (approx 11.1km grid) to coarsen
    return {
        "latitude": round(lat, 1),
        "longitude": round(lon, 1),
        "coordinate_policy": "coarse"
    }

def remove_owner_identity(record: Dict[str, Any]) -> Dict[str, Any]:
    copy_rec = dict(record)
    copy_rec.pop("owner_id", None)
    copy_rec.pop("owner_name", None)
    copy_rec.pop("grower_id", None)
    copy_rec.pop("grower_name", None)
    copy_rec["owner_identity_removed"] = True
    return copy_rec

def check_k_anonymity(
    records: List[Dict[str, Any]],
    min_plots: int = 5,
    min_owners: int = 3,
    min_crop_diversity: int = 2
) -> PrivacyDecision:
    if not records:
        return PrivacyDecision(
            allowed=False, suppressed=True, plot_count=0, owner_count=0, crop_diversity=0,
            reason="No records available for k-anonymity validation."
        )

    # Count distinct values
    plot_ids = {r.get("plot_id") for r in records if r.get("plot_id")}
    owner_ids = {r.get("owner_id") or r.get("grower_id") for r in records if r.get("owner_id") or r.get("grower_id")}
    crops = {r.get("crop") for r in records if r.get("crop")}

    plot_count = len(plot_ids)
    owner_count = len(owner_ids)
    crop_diversity = len(crops)

    # Suppression checks
    if plot_count < min_plots:
        return PrivacyDecision(
            allowed=False, suppressed=True, plot_count=plot_count, owner_count=owner_count, crop_diversity=crop_diversity,
            reason=f"Cohort too small (plots: {plot_count} < {min_plots})."
        )
    if owner_count < min_owners:
        return PrivacyDecision(
            allowed=False, suppressed=True, plot_count=plot_count, owner_count=owner_count, crop_diversity=crop_diversity,
            reason=f"Insufficient distinct owners (owners: {owner_count} < {min_owners})."
        )
    if crop_diversity < min_crop_diversity:
        return PrivacyDecision(
            allowed=False, suppressed=True, plot_count=plot_count, owner_count=owner_count, crop_diversity=crop_diversity,
            reason=f"Insufficient crop diversity (crops: {crop_diversity} < {min_crop_diversity})."
        )

    # Concentration check (l-diversity style protection)
    # If one owner dominates > 70% of the cohort, suppress
    owner_frequencies = {}
    for r in records:
        o = r.get("owner_id") or r.get("grower_id")
        if o:
            owner_frequencies[o] = owner_frequencies.get(o, 0) + 1
            
    if owner_frequencies:
        max_owner_plots = max(owner_frequencies.values())
        if max_owner_plots / len(records) > 0.70:
            return PrivacyDecision(
                allowed=False, suppressed=True, plot_count=plot_count, owner_count=owner_count, crop_diversity=crop_diversity,
                reason="Single owner owns more than 70% of cohort plots."
            )

    return PrivacyDecision(
        allowed=True, suppressed=False, plot_count=plot_count, owner_count=owner_count, crop_diversity=crop_diversity
    )

def suppress_small_cohort(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Sets metrics values to zero/None to suppress data."""
    suppressed = {}
    for k, v in metrics.items():
        if isinstance(v, dict):
            suppressed[k] = suppress_small_cohort(v)
        elif isinstance(v, (int, float)):
            suppressed[k] = 0.0
        else:
            suppressed[k] = None
    return suppressed
