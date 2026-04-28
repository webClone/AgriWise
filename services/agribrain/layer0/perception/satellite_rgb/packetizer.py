"""
Satellite RGB Packetizer — Inference -> PerceptionEngineOutput -> ObservationPackets.

Converts SatelliteRGBInferenceResult into a PerceptionEngineOutput that the
shared packet_adapter can then convert into ObservationPackets.

This is the bridge between engine-specific inference and the universal
Layer 0 observation schema.

Responsibilities:
  - Map inference outputs to PerceptionVariables
  - Apply feasibility gates (row detection suppressed in V1)
  - Collect artifacts (vegetation mask, anomaly map, confidence map)
  - Build zone-level outputs
  - Call packet_adapter for final ObservationPacket creation
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from layer0.perception.satellite_rgb.inference import SatelliteRGBInferenceResult
from layer0.perception.satellite_rgb.qa import SatelliteRGBQAResult
from layer0.perception.satellite_rgb.schemas import SatelliteRGBEngineInput, SatelliteRGBEngineOutput
from layer0.perception.common.contracts import (
    PerceptionEngineFamily,
    PerceptionEngineOutput,
    PerceptionVariable,
    PerceptionArtifact,
    ZoneOutput,
)
from layer0.perception.common.packet_adapter import to_observation_packets
from layer0.perception.common.provenance import build_provenance
from layer0.observation_packet import ObservationPacket


def packetize(
    inference_result: SatelliteRGBInferenceResult,
    qa_result: SatelliteRGBQAResult,
    engine_input: SatelliteRGBEngineInput,
    processing_steps: List[str],
) -> List[ObservationPacket]:
    """
    Convert satellite RGB inference results into ObservationPackets.
    
    Pipeline:
      1. Build PerceptionVariables from inference output
      2. Apply feasibility gates
      3. Collect artifacts
      4. Build PerceptionEngineOutput
      5. Call shared packet_adapter.to_observation_packets()
    
    Args:
        inference_result: from SatelliteRGBInference.run()
        qa_result: from SatelliteRGBQA.assess()
        engine_input: original input for provenance
        processing_steps: ordered list of steps taken
    
    Returns:
        List of ObservationPackets ready for Layer 0 assimilation.
    """
    # --- 1. Build PerceptionVariables ---
    variables = []

    # Vegetation fraction -> maps to canopy_cover / LAI proxy
    variables.append(PerceptionVariable(
        name="vegetation_fraction",
        value=round(inference_result.vegetation_fraction, 4),
        sigma=inference_result.vegetation_sigma,
        confidence=inference_result.overall_confidence,
        unit="fraction",
        details={
            "canopy_density_class": inference_result.canopy_density_class,
        },
    ))

    # Bare soil fraction -> auxiliary, no Kalman state mapping in V1
    variables.append(PerceptionVariable(
        name="bare_soil_fraction",
        value=round(inference_result.bare_soil_fraction, 4),
        sigma=inference_result.bare_soil_sigma,
        confidence=inference_result.overall_confidence,
        unit="fraction",
    ))

    # RGB anomaly score -> weak canopy stress proxy
    variables.append(PerceptionVariable(
        name="rgb_anomaly_score",
        value=round(inference_result.anomaly_fraction, 4),
        sigma=inference_result.anomaly_sigma,
        confidence=min(inference_result.overall_confidence, 0.6),  # moderate ceiling
        unit="score",
        details={
            "is_weak_proxy": True,
            "proxy_type": "structural_stress",
        },
    ))

    # Coarse phenology stage
    variables.append(PerceptionVariable(
        name="coarse_phenology_stage",
        value=round(inference_result.coarse_phenology_stage, 1),
        sigma=inference_result.phenology_sigma,
        confidence=min(inference_result.overall_confidence, 0.4),  # low confidence
        unit="stage_float",
    ))

    # Boundary contamination score
    variables.append(PerceptionVariable(
        name="boundary_contamination_score",
        value=round(inference_result.boundary_contamination_score, 4),
        sigma=0.05,  # Low uncertainty on a geometric measurement
        confidence=0.9,
        unit="fraction",
    ))

    # --- 2. Apply feasibility gates ---
    for gate in inference_result.feasibility_gates:
        for var in variables:
            if var.name == gate.feature_name:
                var.feasibility_gated = True
                var.feasible = gate.is_feasible

    # --- 3. Collect artifacts ---
    artifacts = []
    if inference_result.vegetation_mask is not None:
        artifacts.append(PerceptionArtifact(
            artifact_type="vegetation_mask",
            data_ref="inline:vegetation_mask",
            mime_type="application/json",
            metadata={"format": "grid_float_0_1"},
        ))
    if inference_result.anomaly_heatmap is not None:
        artifacts.append(PerceptionArtifact(
            artifact_type="anomaly_map",
            data_ref="inline:anomaly_heatmap",
            mime_type="application/json",
            metadata={"format": "grid_float_0_1"},
        ))
    if inference_result.confidence_map is not None:
        artifacts.append(PerceptionArtifact(
            artifact_type="confidence_map",
            data_ref="inline:confidence_map",
            mime_type="application/json",
            metadata={"format": "grid_float_0_1"},
        ))

    # --- 4. Build zone outputs ---
    zone_outputs = []
    for zone in inference_result.zone_results:
        zone_outputs.append(ZoneOutput(
            zone_id=zone.zone_id,
            variables={
                "canopy_fraction": zone.canopy_fraction,
                "anomaly_score": zone.anomaly_score,
                "structural_uniformity": zone.structural_uniformity,
            },
            confidence=zone.confidence,
        ))

    # --- 5. Build PerceptionEngineOutput ---
    output = PerceptionEngineOutput(
        engine_family=PerceptionEngineFamily.SATELLITE_RGB,
        plot_id=engine_input.plot_id,
        timestamp=engine_input.timestamp or datetime.now(),
        geometry_scope=engine_input.geometry_scope,
        qa_score=qa_result.qa_score,
        reliability_weight=qa_result.reliability_weight,
        sigma_inflation=qa_result.sigma_inflation,
        variables=variables,
        zone_outputs=zone_outputs,
        artifacts=artifacts,
        provenance_chain=processing_steps,
        model_versions={
            "segmentation": "exg_threshold_v1",
            "anomaly": "heterogeneity_v1",
            "phenology": "green_ratio_v1",
        },
        image_content_hash=engine_input.image_content_hash,
    )

    # --- 6. Convert to ObservationPackets via shared adapter ---
    packets = to_observation_packets(
        output=output,
        bbox=engine_input.bbox,
    )

    return packets


def build_engine_output(
    inference_result: SatelliteRGBInferenceResult,
    qa_result: SatelliteRGBQAResult,
    engine_input: SatelliteRGBEngineInput,
    processing_steps: List[str],
) -> SatelliteRGBEngineOutput:
    """
    Build a typed SatelliteRGBEngineOutput (for API responses / UI).
    
    This is a richer output than ObservationPackets — includes
    plot-level summaries and all zone data for display.
    """
    result = SatelliteRGBEngineOutput(
        engine_family=PerceptionEngineFamily.SATELLITE_RGB,
        plot_id=engine_input.plot_id,
        timestamp=engine_input.timestamp or datetime.now(),
        geometry_scope=engine_input.geometry_scope,
        qa_score=qa_result.qa_score,
        reliability_weight=qa_result.reliability_weight,
        sigma_inflation=qa_result.sigma_inflation,
        plot_visibility_score=qa_result.qa_score,
        plot_coverage_fraction=qa_result.coverage_score,
        vegetation_fraction=inference_result.vegetation_fraction,
        bare_soil_fraction=inference_result.bare_soil_fraction,
        anomaly_fraction=inference_result.anomaly_fraction,
        coarse_phenology_stage=inference_result.coarse_phenology_stage,
        boundary_contamination_score=inference_result.boundary_contamination_score,
        canopy_density_class=inference_result.canopy_density_class,
        row_detection_feasible=qa_result.resolution_sufficient_for_rows,
        image_content_hash=engine_input.image_content_hash,
        provenance_chain=processing_steps,
        model_versions={
            "segmentation": "exg_threshold_v1",
            "anomaly": "heterogeneity_v1",
            "phenology": "green_ratio_v1",
        },
    )

    # Add zone outputs
    for zone in inference_result.zone_results:
        result.zone_outputs.append(ZoneOutput(
            zone_id=zone.zone_id,
            variables={
                "canopy_fraction": zone.canopy_fraction,
                "anomaly_score": zone.anomaly_score,
                "structural_uniformity": zone.structural_uniformity,
            },
            confidence=zone.confidence,
        ))

    return result
