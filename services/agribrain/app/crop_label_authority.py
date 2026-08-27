"""Server-side authority derivation for crop-label submissions."""

from __future__ import annotations

from typing import Any, Dict

from services.agribrain.common.plot_namespace import PlotNamespace


def derive_farmer_crop_label_authority(
    namespace: PlotNamespace,
) -> Dict[str, Any]:
    """Return the fixed authority of the authenticated browser write path.

    The browser route represents an ordinary user confirmation. Client fields
    such as ``label_source`` and ``created_by`` are therefore never authority
    inputs. Farmer confirmation is useful registry evidence, but remains
    unverified and cannot by itself become an eligible training label.
    """

    return {
        "label_source": "farmer_confirmed",
        "label_confidence": "LOW",
        "created_by": namespace.tenant_id,
        "verification_status": "unverified",
        "training_eligible": False,
    }

def assess_crop_dataset_release_readiness(
    eligible_sample_count: int,
    *,
    minimum_samples: int = 50,
) -> Dict[str, Any]:
    """Separate dataset volume readiness from production release authority."""

    count = max(0, int(eligible_sample_count))
    threshold = max(1, int(minimum_samples))
    return {
        "dataset_training_ready": count >= threshold,
        # A successful external, leakage-safe release evaluation must set
        # production eligibility in a separate governed workflow.
        "production_model_eligible": False,
        "production_release_validation": {
            "required": True,
            "status": "not_completed",
        },
    }


__all__ = [
    "assess_crop_dataset_release_readiness",
    "derive_farmer_crop_label_authority",
]
