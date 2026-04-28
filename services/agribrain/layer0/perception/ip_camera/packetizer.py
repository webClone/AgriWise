from typing import List, Any
from datetime import datetime

from layer0.perception.common.contracts import PerceptionEngineFamily, PerceptionVariable
from layer0.perception.ip_camera.schemas import IPCameraEngineInput, IPCameraEngineOutput, IPCameraSceneContext, IPCameraQAResult
from layer0.observation_packet import ObservationPacket, ObservationSource, ObservationType, QAMetadata, UncertaintyModel, Provenance

class IPCameraPacketizer:
    """
    Wraps IP Camera inference results into the standardized Layer 0 PerceptionEngineOutput.
    """
    
    def packetize(
        self, 
        input_data: IPCameraEngineInput, 
        qa_result: IPCameraQAResult, 
        context: IPCameraSceneContext, 
        variables: List[PerceptionVariable],
        validation_checks: List[Any]
    ) -> IPCameraEngineOutput:
    
        output = IPCameraEngineOutput(
            engine_family=PerceptionEngineFamily.IP_CAMERA,
            plot_id=input_data.plot_id,
            timestamp=input_data.timestamp,
            qa_score=qa_result.qa_score,
            reliability_weight=qa_result.reliability_weight,
            sigma_inflation=qa_result.sigma_inflation,
            qa_flags=qa_result.flags,
            variables=variables,
            scene_context=context,
            validation_checks=validation_checks
        )
        
        # Add provenance, heavily tied to the calibration/registration used
        output.provenance_chain.append(f"camera_id:{input_data.camera_id}")
        if input_data.camera_registration_ref:
            output.provenance_chain.append(f"registration_ref:{input_data.camera_registration_ref}")
            
        return output
        
    def to_observation_packet(self, engine_output: IPCameraEngineOutput) -> ObservationPacket:
        """
        Converts the standard IPCameraEngineOutput into a universal ObservationPacket 
        ready for the Layer 0 Kalman Assimilator.
        """
        payload = {}
        sigmas = {}
        for var in engine_output.variables:
            payload[var.name] = var.value
            sigmas[var.name] = var.sigma
            
        # Include precomputed validations directly in the payload so the assimilator can route them
        if engine_output.validation_checks:
            payload["precomputed_validations"] = [
                {
                    "check_name": v.check_name,
                    "expected_signal": v.expected_signal,
                    "observed_signal": v.observed_signal,
                    "agreement": v.agreement,
                    "agreement_reason": v.agreement_reason,
                    "confidence": v.confidence,
                    "affected_upstream_source": v.affected_upstream_source
                } for v in engine_output.validation_checks
            ]
            
        qa = QAMetadata(
            scene_score=engine_output.qa_score
        )
        
        uncertainty = UncertaintyModel(
            sigmas=sigmas
        )
        
        provenance = Provenance(
            processing_chain=engine_output.provenance_chain
        )
        
        return ObservationPacket(
            source=ObservationSource.IP_CAMERA,
            obs_type=ObservationType.POINT_TIMESERIES, # IP Camera is a fixed point timeseries
            timestamp=engine_output.timestamp or datetime.now(),
            payload=payload,
            qa=qa,
            uncertainty=uncertainty,
            provenance=provenance,
            reliability_weight=engine_output.reliability_weight
        )
