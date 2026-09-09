import { TruthEnvelopeData } from "../TruthEnvelopeRenderer";

export interface MesiaParameters {
  soilTexture: "Clay Loam" | "Sandy Loam" | "Silty Clay" | "Sand" | "Clay";
  bulkDensity: number; // 1.0 - 1.8 g/cm³
  dielectricModel: "dobson" | "topp" | "mironov";
  antennaHeightM: number; // 1.0 - 5.0 m
  elevationMaskDeg: number; // 5 - 30 deg
  activeBands: string[]; // ["GNSS", "CELL", "UHF", "SAR", "WIFI"]
  provenanceFilter: "all" | "measured_only";
  viewDensity: "compact" | "engineering";
  expertPersona: "all" | "agronomist" | "rf_engineer" | "auditor";
}

export interface SatelliteIlluminator {
  name: string;
  constellation: string;
  freq_hz: number;
  elev_deg: number;
  az_deg: number;
  slant_km: number;
}

export interface CellularMast {
  osm_id?: number | string;
  operator: string;
  band: string;
  dist_m: number;
  bearing_deg: number;
  rx_rsrp_dbm: number | null;
  excess_canopy_loss_db: number;
  canopy_water_index: number;
  source_class?: string;
  identity_state?: string;
}

export interface FleetNodeTelemetry {
  node_id: string;
  role: string;
  battery_pct: number;
  solar_input_watts: number;
  temperature_celsius: number;
  packet_loss_pct: number;
  calibration_age_days: number;
  is_healthy: boolean;
  requires_maintenance: boolean;
  sentinel_drift_db: number;
  requires_calibration_demotion: boolean;
  demotion_reason?: string;
}

export interface InvariantCheckItem {
  invariant_name: string;
  status: "SATISFIED" | "WARNING" | "VIOLATED";
  description: string;
  physical_limit: string;
  observed_rate_or_value: string;
  impact_on_admission: string;
}

export interface MesiaData {
  plot_id: string;
  timestamp: string;
  status: string;
  modality: string;
  hardware_bom_cost_usd: number;
  in_situ_sensors_required: number;
  geodetic_centroid: { lat: number; lng: number; alt_m: number };
  truth_envelopes?: Record<string, TruthEnvelopeData>;
  data_lineage?: {
    source_orbital_ephemeris: string;
    source_meteorology: string;
    source_spatial_raster: string;
    source_cellular_infrastructure: string;
    source_broadcast_infrastructure?: string;
    synthetic_math_status: string;
  };
  radio_wave_channels?: {
    spaceborne_active_radar: {
      channel_name: string;
      physical_waves_measured: boolean;
      receiver_location: string;
      polarizations: {
        vv_backscatter_db: number;
        vh_backscatter_db: number;
        cross_pol_ratio: number;
      };
      physical_interpretation: string;
    };
    in_situ_ground_receiver?: {
      status: string;
      physical_waves_measured: boolean;
      receiver_mount?: string;
      antenna_height_m?: number;
      rtk_fix_status?: string;
      log_source?: string;
      native_nmea_sentences_count?: number;
      sha256?: string;
      file_size_bytes?: number;
      source_class?: string;
      processing_level?: string;
      measured_satellites?: Array<{
        satellite_id?: string;
        prn: number;
        constellation: string;
        carrier_freq_hz: number;
        snr_min_db_hz: number;
        snr_max_db_hz: number;
        multipath_peak_elevation_deg?: number;
        effective_reflector_height_m: number;
        inferred_soil_vwc_pct?: number;
        rtk_fix_status?: string;
        source_class?: string;
        identity_state?: string;
      }>;
      ground_measured_vwc_pct?: number;
      message?: string;
    };
    in_situ_wifi_receiver?: {
      status: string;
      physical_waves_measured: boolean;
      receiver_mount?: string;
      antenna_height_m?: number;
      log_source?: string;
      sha256?: string;
      file_size_bytes?: number;
      source_class?: string;
      processing_level?: string;
      identity_state?: string;
      presentation_state?: string;
      num_subcarriers?: number;
      center_frequency_hz?: number;
      bandwidth_hz?: number;
      rssi_dbm?: number;
      noise_floor_dbm?: number;
      snr_db?: number;
      target_classification?: string;
      amplitude_variance?: number;
      phase_variance?: number;
      optical_immune?: boolean;
      confidence?: number;
      canopy_water_index?: number;
      excess_loss_db?: number;
      subcarriers?: Array<{
        subcarrier_index: number;
        amplitude_linear: number;
        phase_rad: number;
      }>;
      message?: string;
    };
  };
  signals_of_opportunity: {
    gnss_reflectometry: {
      satellites_overhead_count: number;
      primary_illuminators: SatelliteIlluminator[];
      inferred_subsurface_vwc_pct: number;
    };
    cellular_forward_scatter: {
      masts_tracked: CellularMast[];
      mean_excess_loss_db: number;
      canopy_water_index: number;
      oran_e2_telemetry?: {
        bundle_id: string;
        operator_name: string;
        cell_id: number;
        tracking_area_code?: number;
        plmn_id?: string;
        recorded_at: string;
        prb_utilization_pct: number;
        mean_tx_power_dbm: number;
        active_beam_index: number;
        scheduler_mode: string;
        anonymized_ue_count: number;
        is_consent_valid: boolean;
        evidence_tier: string;
        content_hash: string;
      } | null;
    };
    terrestrial_broadcast_uhf: {
      transmitter: string;
      grazing_angle_deg: number;
      inferred_root_zone_vwc_pct: number;
      skin_depth_cm: number;
    };
    spaceborne_cygnss: {
      mission: string;
      reflectivity_db: number;
      inferred_surface_vwc_pct: number;
    };
  };
  temporal_dynamics?: {
    local_solar_time: string;
    diurnal_phase: string;
    phase_description: string;
    transpiration_demand: string;
    solar_zenith_deg: number;
    drying_rate_pct_per_day: number;
    equivalent_water_flux_mm_day: number;
    hydrological_regime: string;
    elapsed_hours_since_last_scan: number;
  };
  dielectric_profile: {
    soil_texture: string;
    horizon_0_1cm_vwc_pct: number;
    horizon_1_3cm_vwc_pct: number;
    horizon_3_9cm_vwc_pct: number;
    horizon_9_27cm_vwc_pct: number;
    mean_dielectric_permittivity_eps_r: number;
    spatial_microzones: Array<{
      microzone_id: string;
      grid_x: number;
      grid_y: number;
      spatial_authority_class?: string;
      strata_2_5d?: {
        canopy_water_index: number;
        topsoil_0_5cm_vwc_pct: number;
        root_zone_5_30cm_vwc_pct: number;
        deep_subsoil_30_100cm_vwc_pct: number;
      };
      soil_vwc_pct: number;
      dielectric_eps_r: number;
      conductivity_s_m: number;
      status: string;
    }>;
    spatial_lattice_1m?: {
      dimensions: { rows: number; cols: number };
      pixel_resolution_m: number;
      spatial_authority_class: string;
      semantic_status: string;
      root_zone_vwc_grid: number[][];
      canopy_water_grid?: number[][] | null;
      stats: {
        min_root_vwc_pct: number;
        max_root_vwc_pct: number;
        mean_root_vwc_pct: number;
        total_1m_pixels: number;
      };
    };
  };
  closure_certificate?: {
    certificate_id: string;
    target_capability: string;
    status: string;
    closure_passed: boolean;
    review_comments?: string;
  };
  asmae_p08_proposals?: Array<{
    proposal_id: string;
    feature: string;
    depth_layer?: string;
    depth_stratum?: string;
    target_state?: string;
    carrier_frequency_hz?: number;
    diurnal_phase?: string;
    innovation_value: number;
    variance: number;
    confidence_support: number;
    authority_scope?: string;
    authority_state?: string;
    decision_eligible?: boolean;
    layer0_record_id?: string;
    admission_status?: string;
    admission_notes?: string;
    is_usable_for_assimilation?: boolean;
  }>;
  feasibility_gate?: {
    target_not_observable: boolean;
    overall_confidence: number;
    fail_closed_triggered: boolean;
    optical_immunity_verified: boolean;
  };
  fleet_health?: {
    plot_id: string;
    evaluated_at: string;
    telemetry_stream_type?: string;
    fleet_status: string;
    total_monitored_nodes: number;
    unhealthy_nodes_count: number;
    maintenance_alerts_count: number;
    calibration_demotions_count: number;
    nodes: FleetNodeTelemetry[];
  };
  two_state_separation?: {
    state_space_formulation: string;
    agronomic_state: {
      topsoil_vwc_pct: number;
      rootzone_vwc_pct: number;
      deep_subsoil_vwc_pct: number;
      canopy_water_index: number;
      leaf_surface_wetness_active: boolean;
      dew_condensation_probability: number;
      hydrological_regime: string;
      drying_rate_pct_day: number;
      equivalent_water_flux_mm_day: number;
    };
    instrument_state: {
      receiver_temperature_c: number;
      thermal_drift_db: number;
      antenna_displacement_m: number;
      antenna_pose_status: string;
      carrier_frequency_offset_ppm: number;
      cellular_cell_id: string | number | null;
      cell_handover_detected: boolean;
      radio_noise_floor_dbm: number;
      terminated_50ohm_load_detected: boolean;
      calibration_epoch_valid: boolean;
    };
    decoupling_audit: {
      cross_talk_leakage_coefficient: number;
      instrument_leakage_into_soil_detected: boolean;
      principle_p08_decoupling_enforced: boolean;
      dominant_cause: string;
      is_safe_for_agronomic_assimilation: boolean;
      rejection_reason: string | null;
      covariance_multiplier: number;
    };
  };
  nuisance_attribution?: {
    dominant_cause: string;
    is_safe_for_soil_assimilation: boolean;
    is_safe_for_agronomic_assimilation: boolean;
    recommended_covariance_multiplier: number;
    rejection_reason: string | null;
    p_soil_water_change: number;
    p_canopy_hydraulic_change?: number;
    p_dew_condensation: number;
    p_wind_aerodynamic_flutter?: number;
    p_instrument_thermal_drift?: number;
    p_geometry_displacement?: number;
    p_network_handover?: number;
    p_coexistence_interference?: number;
  };
  imm_regime_dynamics?: {
    active_regime: string;
    mode_probabilities: Record<string, number>;
    covariance_scaling_factor: number;
    is_soil_update_permitted: boolean;
    is_foliar_update_permitted: boolean;
    regime_explanation: string;
    online_posterior_vwc: number;
    retrospectively_smoothed_vwc: number;
    smoothing_lag_hours: number;
  };
  asmae_discrimination_guidance?: {
    supervision_active: boolean;
    agronomic_plausibility_score: number;
    hydrological_flux_consistent: boolean;
    diurnal_rhythm_concordance: number;
    thermodynamic_dew_risk: string;
    aerodynamic_wind_interference: string;
    thermal_gain_drift_compensated_db: number;
    cross_modal_agreement_score: number;
    recommended_action: string;
    recommended_covariance_multiplier: number;
    target_state_recommendation: string;
    invariants_checked: InvariantCheckItem[];
    scientific_justification: string;
    asmae_priors_used: Record<string, any>;
    timestamp: string;
  };
  diagnostic_layer_routing?: {
    architecture: string;
    active_supervision: boolean;
    agronomic_plausibility_score: number;
    recommended_action: string;
    layers: Record<
      string,
      {
        layer_name: string;
        role: string;
        subscribed_variable?: string;
        mesia_channel?: string;
        asmae_authority: string;
        action?: string;
        asmae_interaction?: string;
        discrimination_contribution?: string;
      }
    >;
  };
}
