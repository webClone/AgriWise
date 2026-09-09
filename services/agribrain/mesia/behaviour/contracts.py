"""MESIA Radio Behaviour Contracts Catalogue — R6 §9.1 / P7.1.

Defines source-specific measurement primitives, stable features, calibration
requirements, nuisance variables, and prohibited inferences for all radio families.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from ..contracts.behaviour import RadioBehaviourContract
from ..radio_families.registry import RadioFamily


BEHAVIOUR_CONTRACT_REGISTRY: Dict[str, RadioBehaviourContract] = {
    RadioFamily.WIFI_CSI.value: RadioBehaviourContract(
        contract_id="contract-wifi-csi-v1",
        radio_family=RadioFamily.WIFI_CSI.value,
        profile_version="1.0.0",
        physical_primitive="complex_subcarrier_channel_matrix",
        controlled_actions=["channel_switch", "bandwidth_selection", "sounding_rate"],
        stable_features=["subcarrier_amplitude_profile", "relative_subcarrier_phase", "delay_spread"],
        invalid_states=["agc_saturation", "unsynchronized_mimo_stream", "unknown_packet_payload"],
        nuisance_variables=["human_motion", "ap_power_control_jump", "temperature_drift", "foliage_wind_motion"],
        valid_domain={"max_range_m": 50.0, "frequency_ghz_bands": [2.4, 5.0, 6.0]},
        calibration_requirements=["cable_loopback_gain_phase", "noise_floor_baseline"],
        uncertainty_model="unc-model-wifi-v1",
        allowed_outputs=["canopy_water_index", "soil_surface_relative_permittivity"],
        prohibited_inferences=["deep_root_zone_salinity", "exact_subsurface_bulk_density"],
    ),
    RadioFamily.LORA_CONTROLLED.value: RadioBehaviourContract(
        contract_id="contract-lora-subghz-v1",
        radio_family=RadioFamily.LORA_CONTROLLED.value,
        profile_version="1.0.0",
        physical_primitive="chirp_rssi_snr_attenuation_threshold",
        controlled_actions=["tx_power_sweep", "spreading_factor_step", "frequency_hop"],
        stable_features=["path_loss_attenuation_db", "snr_margin_db", "packet_reception_rate"],
        invalid_states=["duty_cycle_exhausted", "crc_failure", "cochannel_collision"],
        nuisance_variables=["antenna_burial_depth_uncertainty", "surface_puddling", "gateway_lna_gain_drift"],
        valid_domain={"burial_depth_cm_range": [5.0, 100.0], "path_length_m": [10.0, 2000.0]},
        calibration_requirements=["free_space_link_reference", "rssi_linearity_curve"],
        uncertainty_model="unc-model-lora-v1",
        allowed_outputs=["root_zone_attenuation_trend", "integrated_column_loss"],
        prohibited_inferences=["high_resolution_layer_stratification", "phase_coherence"],
    ),
    RadioFamily.GNSS_REFLECTOMETRY.value: RadioBehaviourContract(
        contract_id="contract-gnss-reflectometry-v1",
        radio_family=RadioFamily.GNSS_REFLECTOMETRY.value,
        profile_version="1.0.0",
        physical_primitive="bistatic_multipath_snr_interference_pattern",
        controlled_actions=["elevation_mask_filtering", "satellite_prn_selection"],
        stable_features=["snr_oscillation_frequency", "snr_oscillation_amplitude", "phase_notch_depth"],
        invalid_states=["low_elevation_below_5deg", "satellite_maneuver", "heavy_ionospheric_scintillation"],
        nuisance_variables=["canopy_bistatics", "terrain_slope", "surface_roughness"],
        valid_domain={"elevation_deg_range": [5.0, 30.0], "fresnel_zone_radius_m": [5.0, 50.0]},
        calibration_requirements=["direct_rhcp_antenna_gain_pattern", "dual_polarisation_isolation"],
        uncertainty_model="unc-model-gnss-v1",
        allowed_outputs=["field_scale_topsoil_moisture_0_5cm"],
        prohibited_inferences=["deep_strata_root_zone", "real_time_rapid_transients_under_1min"],
    ),
    RadioFamily.GPR.value: RadioBehaviourContract(
        contract_id="contract-uwb-gpr-v1",
        radio_family=RadioFamily.GPR.value,
        profile_version="1.0.0",
        physical_primitive="subsurface_impulse_time_of_flight_radargram",
        controlled_actions=["time_window_length", "pulse_repetition_rate", "stacking_count"],
        stable_features=["two_way_travel_time_to_reflector", "layer_interface_reflection_amplitude", "soil_wave_velocity"],
        invalid_states=["ground_coupling_loss", "direct_antenna_short", "adc_clipping"],
        nuisance_variables=["antenna_elevation_wobble", "buried_stones", "clay_conductivity_attenuation"],
        valid_domain={"depth_cm_range": [0.0, 200.0], "permittivity_range": [3.0, 45.0]},
        calibration_requirements=["metal_plate_surface_reflection", "air_calibration_trace"],
        uncertainty_model="unc-model-gpr-v1",
        allowed_outputs=["stratified_soil_moisture_layers", "water_table_depth"],
        prohibited_inferences=["uncalibrated_nutrient_speciation"],
    ),
}


def get_behaviour_contract(radio_family: str) -> Optional[RadioBehaviourContract]:
    """Retrieve behaviour contract for a given radio family."""
    return BEHAVIOUR_CONTRACT_REGISTRY.get(radio_family)
