export interface OpenMeteoData {
  current: {
    temperature_2m: number;
    relative_humidity_2m: number;
    rain: number;
    soil_temperature_0cm: number;
    soil_moisture_0_to_1cm: number;
    soil_moisture_3_to_9cm: number;
    soil_moisture_27_to_81cm: number;
    soil_temperature_18cm: number;
    soil_temperature_54cm: number;
    wind_speed_10m: number;
    wind_direction_10m: number;
    wind_gusts_10m: number;
    shortwave_radiation: number;
    diffuse_radiation: number;
    direct_normal_irradiance: number;
    cloud_cover: number;
    surface_pressure: number;
    vapor_pressure_deficit?: number;
    leaf_wetness_probability?: number;
    uv_index?: number;
    freezing_level_height?: number;
    visibility?: number;
  };
  elevation?: number; // Root level property
  hourly: {
    vapor_pressure_deficit: number[];
    leaf_wetness_probability: number[];
    uv_index: number[];
    freezing_level_height: number[];
    visibility: number[];
  };
  daily: {
    et0_fao_evapotranspiration: number[];
  };
}

export async function fetchOpenMeteoAgriData(lat: number, lng: number): Promise<OpenMeteoData | null> {
  console.warn("[FAO Service] Direct Next.js fetch to Open-Meteo is disabled. Route via Python backend Layer 0 instead.");
  return null;
}
