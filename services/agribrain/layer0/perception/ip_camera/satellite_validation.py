from typing import Any, List

from layer0.perception.ip_camera.schemas import IPCameraEngineInput, CameraValidationResult
from layer0.perception.common.contracts import PerceptionVariable

class CameraSatelliteValidator:
    """
    Checks stable canopy against sudden NDVI drops and resolves stress conflicts.
    """
    
    def validate(
        self, 
        input_data: IPCameraEngineInput, 
        variables: List[PerceptionVariable]
    ) -> List[CameraValidationResult]:
        
        results = []
        
        # Example validation check: Cloud artifact vs real canopy drop
        canopy_var = next((v for v in variables if v.name == "canopy_cover"), None)
        
        if canopy_var and "recent_ndvi_drop" in input_data.satellite_context:
            ndvi_drop = input_data.satellite_context["recent_ndvi_drop"]
            
            # If camera shows stable high canopy but satellite dropped heavily
            if canopy_var.value > 0.8 and ndvi_drop > 0.3:
                results.append(
                    CameraValidationResult(
                        check_name="camera_vs_satellite_cloud_artifact",
                        expected_signal="Canopy drop corresponding to NDVI drop",
                        observed_signal="Stable high canopy in camera",
                        agreement=False,
                        agreement_reason="Likely satellite cloud shadow or atmospheric artifact",
                        confidence=0.9,
                        affected_upstream_source="satellite-ndvi"
                    )
                )
                
        return results
