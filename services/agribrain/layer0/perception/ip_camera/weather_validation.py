from typing import Any, List

from layer0.perception.ip_camera.schemas import IPCameraEngineInput, CameraValidationResult
from layer0.perception.common.contracts import PerceptionVariable

class CameraWeatherValidator:
    """
    Validates crop response to conditions (phenology vs GDD, heat stress, wind).
    """
    
    def validate(
        self, 
        input_data: IPCameraEngineInput, 
        variables: List[PerceptionVariable]
    ) -> List[CameraValidationResult]:
        
        results = []
        
        # Example validation check
        phenology_var = next((v for v in variables if v.name == "phenology_stage_est"), None)
        
        if phenology_var and "gdd_stage" in input_data.weather_context:
            gdd_stage = input_data.weather_context["gdd_stage"]
            cam_stage = phenology_var.value
            
            # Simple threshold check for example
            agreement = abs(gdd_stage - cam_stage) < 1.0
            
            results.append(
                CameraValidationResult(
                    check_name="camera_vs_weather_phenology",
                    expected_signal=f"GDD stage {gdd_stage:.1f}",
                    observed_signal=f"Camera stage {cam_stage:.1f}",
                    agreement=agreement,
                    agreement_reason="Camera phenology matches GDD expectation" if agreement else "Camera shows lag/lead vs GDD",
                    confidence=0.8,
                    affected_upstream_source="weather-driven-phenology"
                )
            )
            
        # Heat stress validation
        stress_var = next((v for v in variables if v.name == "visible_stress_prob"), None)
        if stress_var and "max_temp_c" in input_data.weather_context:
            max_temp = input_data.weather_context["max_temp_c"]
            stress = stress_var.value
            
            if max_temp > 35.0 and stress > 0.4:
                results.append(
                    CameraValidationResult(
                        check_name="camera_vs_weather_heat",
                        expected_signal=f"Heat stress expected (>35C)",
                        observed_signal=f"Visible stress {stress:.2f}",
                        agreement=True,
                        agreement_reason="Camera confirms weather-induced heat stress",
                        confidence=0.8,
                        affected_upstream_source="weather-temp"
                    )
                )
                
        # Rain recovery validation
        if stress_var and "recent_rain_mm" in input_data.weather_context:
            rain_mm = input_data.weather_context["recent_rain_mm"]
            stress = stress_var.value
            
            if rain_mm > 10.0 and stress < 0.2:
                results.append(
                    CameraValidationResult(
                        check_name="camera_vs_weather_recovery",
                        expected_signal="Stress relief expected after >10mm rain",
                        observed_signal=f"Visible stress {stress:.2f} (low)",
                        agreement=True,
                        agreement_reason="Camera confirms rain-induced recovery",
                        confidence=0.8,
                        affected_upstream_source="weather-precip"
                    )
                )
            
        return results
