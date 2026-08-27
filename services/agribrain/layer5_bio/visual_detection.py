"""Layer 5 visual-detection boundary.

The former implementation used deterministic random CNN weights and could
promote their output into disease evidence.  No trained, versioned and
validated visual model currently ships with this service, so the production
boundary abstains explicitly.
"""

from __future__ import annotations

from typing import Any, Dict


class VisualDetectionEngine:
    """Fail-closed adapter reserved for a future validated vision model."""

    classes = (
        "healthy",
        "early_blight",
        "late_blight",
        "septoria",
        "nitrogen_def",
        "drought_stress",
    )

    def __init__(self) -> None:
        self.validation_status = "DISABLED_UNVALIDATED_MODEL"

    def analyze_image(
        self,
        image_tensor: Any,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        del image_tensor, context
        return {
            "status": "unavailable",
            "reason": "No validated Layer 5 vision model is installed",
            "authority": "VISUALIZATION_ONLY_NO_DIAGNOSIS",
            "engine": "disabled_unvalidated_vision",
        }


visual_engine = VisualDetectionEngine()
