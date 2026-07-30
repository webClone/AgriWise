from typing import Any, Dict, Optional

class SceneTruth:
    def __init__(
        self,
        truth_class: str,
        source_reality: str,
        real_provider_product: bool,
        production_usable: bool,
        diagnostic_only: bool,
        state_update_allowed: bool,
        visualization_allowed: bool,
        experimental_visual_allowed: bool,
        composite_advisory_allowed: bool,
        scientific_surface_allowed: bool,
        prescription_driver_allowed: bool,
        current_1m_approval_allowed: bool,
    ):
        self.truth_class = truth_class
        self.source_reality = source_reality
        self.real_provider_product = real_provider_product
        self.production_usable = production_usable
        self.diagnostic_only = diagnostic_only
        self.state_update_allowed = state_update_allowed
        self.visualization_allowed = visualization_allowed
        self.experimental_visual_allowed = experimental_visual_allowed
        self.composite_advisory_allowed = composite_advisory_allowed
        self.scientific_surface_allowed = scientific_surface_allowed
        self.prescription_driver_allowed = prescription_driver_allowed
        self.current_1m_approval_allowed = current_1m_approval_allowed

def classify_asmae_scene_reality(scene: Any) -> SceneTruth:
    if isinstance(scene, dict):
        runtime = scene.get("runtime") or scene
    else:
        runtime = getattr(scene, "runtime", scene)

    source_reality = "unknown"
    real_provider = False
    production_usable = False
    diagnostic_only = True
    test_override = False

    if isinstance(runtime, dict):
        source_reality = runtime.get("source_reality", "unknown")
        real_provider = runtime.get("real_provider_product", False)
        production_usable = runtime.get("production_usable", False)
        diagnostic_only = runtime.get("diagnostic_only", True)
        test_override = runtime.get("test_override", False)
    elif runtime is not None:
        source_reality = getattr(runtime, "source_reality", "unknown")
        real_provider = getattr(runtime, "real_provider_product", False)
        production_usable = getattr(runtime, "production_usable", False)
        diagnostic_only = getattr(runtime, "diagnostic_only", True)
        test_override = getattr(runtime, "test_override", False)

    # Check if scene has bands array
    has_array = False
    if isinstance(scene, dict):
        bands = scene.get("bands") or {}
        has_array = len(bands) > 0
    elif hasattr(scene, "bands"):
        has_array = len(scene.bands or {}) > 0

    if (
        has_array
        and source_reality == "real_raster"
        and real_provider is True
        and production_usable is True
        and diagnostic_only is False
        and test_override is False
    ):
        return SceneTruth(
            truth_class="provider_real_raster",
            source_reality="real_raster",
            real_provider_product=True,
            production_usable=True,
            diagnostic_only=False,
            state_update_allowed=True,
            visualization_allowed=True,
            experimental_visual_allowed=True,
            composite_advisory_allowed=True,
            scientific_surface_allowed=True,
            prescription_driver_allowed=True,
            current_1m_approval_allowed=True,
        )

    if has_array and source_reality == "raster_composite_proxy":
        return SceneTruth(
            truth_class="raster_composite_proxy",
            source_reality="raster_composite_proxy",
            real_provider_product=False,
            production_usable=False,
            diagnostic_only=True,
            state_update_allowed=False,
            visualization_allowed=True,
            experimental_visual_allowed=True,
            composite_advisory_allowed=True,
            scientific_surface_allowed=False,
            prescription_driver_allowed=False,
            current_1m_approval_allowed=False,
        )

    return SceneTruth(
        truth_class="diagnostic_only" if diagnostic_only else "unknown",
        source_reality=source_reality,
        real_provider_product=real_provider,
        production_usable=production_usable,
        diagnostic_only=True,
        state_update_allowed=False,
        visualization_allowed=True,
        experimental_visual_allowed=True,
        composite_advisory_allowed=True,
        scientific_surface_allowed=False,
        prescription_driver_allowed=False,
        current_1m_approval_allowed=False,
    )

def classify_raster_truth(raster_data: Any) -> SceneTruth:
    source_reality = "unknown"
    real_provider = False
    production_usable = False
    diagnostic_only = True

    if isinstance(raster_data, dict):
        provenance = raster_data.get("provenance", {}) or {}
        source_reality = raster_data.get("source_reality") or provenance.get("source_reality", "unknown")
        real_provider = (
            raster_data["real_provider_product"]
            if "real_provider_product" in raster_data
            else provenance.get("real_provider_product", False)
        )
        production_usable = (
            raster_data["production_usable"]
            if "production_usable" in raster_data
            else provenance.get("production_usable", False)
        )
        diagnostic_only = raster_data.get("diagnostic_only", True)
    elif raster_data is not None:
        prov = getattr(raster_data, "provenance", {}) or {}
        if isinstance(prov, dict):
            source_reality = getattr(raster_data, "source_reality", None) or prov.get("source_reality", "unknown")
            real_provider = (
                getattr(raster_data, "real_provider_product")
                if hasattr(raster_data, "real_provider_product")
                else prov.get("real_provider_product", False)
            )
            production_usable = (
                getattr(raster_data, "production_usable")
                if hasattr(raster_data, "production_usable")
                else prov.get("production_usable", False)
            )
            diagnostic_only = prov.get("diagnostic_only", getattr(raster_data, "diagnostic_only", True))
        else:
            source_reality = getattr(raster_data, "source_reality", "unknown")
            real_provider = getattr(raster_data, "real_provider_product", False)
            production_usable = getattr(raster_data, "production_usable", False)
            diagnostic_only = getattr(raster_data, "diagnostic_only", True)

    is_real = (
        real_provider is True
        and production_usable is True
        and diagnostic_only is False
        and source_reality in {"real_raster", "real_provider_raster", "provider_observation"}
    )

    is_provider_temporal_composite = (
        real_provider is True
        and production_usable is True
        and diagnostic_only is False
        and source_reality == "provider_temporal_composite_raster"
    )

    if is_provider_temporal_composite:
        return SceneTruth(
            truth_class="provider_derived_composite",
            source_reality="provider_temporal_composite_raster",
            real_provider_product=True,
            production_usable=True,
            diagnostic_only=False,
            state_update_allowed=False,
            visualization_allowed=True,
            experimental_visual_allowed=True,
            composite_advisory_allowed=True,
            scientific_surface_allowed=True,
            prescription_driver_allowed=False,
            current_1m_approval_allowed=False,
        )

    if is_real:
        return SceneTruth(
            truth_class="provider_observation",
            source_reality=source_reality,
            real_provider_product=True,
            production_usable=True,
            diagnostic_only=False,
            state_update_allowed=True,
            visualization_allowed=True,
            experimental_visual_allowed=True,
            composite_advisory_allowed=True,
            scientific_surface_allowed=True,
            prescription_driver_allowed=True,
            current_1m_approval_allowed=True,
        )

    if source_reality == "raster_composite_proxy":
        return SceneTruth(
            truth_class="raster_composite_proxy",
            source_reality="raster_composite_proxy",
            real_provider_product=False,
            production_usable=False,
            diagnostic_only=True,
            state_update_allowed=False,
            visualization_allowed=True,
            experimental_visual_allowed=True,
            composite_advisory_allowed=True,
            scientific_surface_allowed=False,
            prescription_driver_allowed=False,
            current_1m_approval_allowed=False,
        )

    return SceneTruth(
        truth_class="fallback_default",
        source_reality=source_reality,
        real_provider_product=real_provider,
        production_usable=production_usable,
        diagnostic_only=True,
        state_update_allowed=False,
        visualization_allowed=True,
        experimental_visual_allowed=True,
        composite_advisory_allowed=True,
        scientific_surface_allowed=False,
        prescription_driver_allowed=False,
        current_1m_approval_allowed=False,
    )

def normalize_asmae_runtime(runtime: Any) -> Any:
    if runtime is None:
        return runtime

    source_reality = getattr(runtime, "source_reality", "unknown")
    real_provider = getattr(runtime, "real_provider_product", False)
    test_override = getattr(runtime, "test_override", False)

    if source_reality == "raster_composite_proxy" or test_override or not real_provider:
        if hasattr(runtime, "real_provider_product"):
            runtime.real_provider_product = False
        if hasattr(runtime, "production_usable"):
            runtime.production_usable = False
        if hasattr(runtime, "diagnostic_only"):
            runtime.diagnostic_only = True
        if hasattr(runtime, "state_update_allowed"):
            runtime.state_update_allowed = False
        if hasattr(runtime, "scientific_surface_allowed"):
            runtime.scientific_surface_allowed = False
        if hasattr(runtime, "prescription_driver_allowed"):
            runtime.prescription_driver_allowed = False
        if hasattr(runtime, "current_1m_approval_allowed"):
            runtime.current_1m_approval_allowed = False
        if hasattr(runtime, "visualization_allowed"):
            runtime.visualization_allowed = True
        if hasattr(runtime, "experimental_visual_allowed"):
            runtime.experimental_visual_allowed = True
        if hasattr(runtime, "composite_advisory_allowed"):
            runtime.composite_advisory_allowed = True
    return runtime

def truth_to_evidence_fields(truth: SceneTruth) -> dict:
    return {
        "truth_class": truth.truth_class,
        "source_reality": truth.source_reality,
        "real_provider_product": truth.real_provider_product,
        "production_usable": truth.production_usable,
        "diagnostic_only": truth.diagnostic_only,
        "state_update_allowed": truth.state_update_allowed,
        "visualization_allowed": truth.visualization_allowed,
        "experimental_visual_allowed": truth.experimental_visual_allowed,
        "composite_advisory_allowed": truth.composite_advisory_allowed,
        "scientific_surface_allowed": truth.scientific_surface_allowed,
        "prescription_driver_allowed": truth.prescription_driver_allowed,
        "current_1m_approval_allowed": truth.current_1m_approval_allowed,
        "data_status": "observed" if (truth.real_provider_product and truth.production_usable and not truth.diagnostic_only) else "estimated",
    }


def truth_to_surface_provenance(truth: SceneTruth) -> dict:
    return {
        "truth_class": truth.truth_class,
        "source_reality": truth.source_reality,
        "real_provider_product": truth.real_provider_product,
        "production_usable": truth.production_usable,
        "diagnostic_only": truth.diagnostic_only,
        "state_update_allowed": truth.state_update_allowed,
        "scientific_surface_allowed": truth.scientific_surface_allowed,
        "prescription_driver_allowed": truth.prescription_driver_allowed,
        "current_1m_approval_allowed": truth.current_1m_approval_allowed,
        "visualization_allowed": truth.visualization_allowed,
        "experimental_visual_allowed": truth.experimental_visual_allowed,
        "composite_advisory_allowed": truth.composite_advisory_allowed,
    }
