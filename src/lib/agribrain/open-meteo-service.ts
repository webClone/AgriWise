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
  try {
    const params = new URLSearchParams({
      latitude: lat.toString(),
      longitude: lng.toString(),
      // Added: diffuse_radiation, direct_normal_irradiance, uv_index, soil_temperature_18cm, soil_temperature_54cm, freezing_level_height, visibility
      current: 'temperature_2m,relative_humidity_2m,rain,soil_temperature_0cm,soil_temperature_18cm,soil_temperature_54cm,soil_moisture_0_to_1cm,soil_moisture_3_to_9cm,soil_moisture_27_to_81cm,wind_speed_10m,wind_direction_10m,wind_gusts_10m,shortwave_radiation,diffuse_radiation,direct_normal_irradiance,cloud_cover,surface_pressure',
      hourly: 'vapor_pressure_deficit,leaf_wetness_probability,uv_index,freezing_level_height,visibility',
      daily: 'et0_fao_evapotranspiration',
      timezone: 'auto',
      forecast_days: '1'
    });

    const url = `https://api.open-meteo.com/v1/forecast?${params.toString()}`;
    console.log(`[Open-Meteo] Fetching: ${url}`);
    
    const response = await fetch(url);
    if (!response.ok) {
      console.error(`[Open-Meteo] Error: ${response.status} ${response.statusText}`);
      throw new Error(`Open-Meteo API error: ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`[Open-Meteo] Success:`, data.current);

    // Augment with current hour's hourly data 
    const currentHourIndex = new Date().getHours(); 
    
    const vpd = data.hourly.vapor_pressure_deficit[currentHourIndex] || 0;
    const leafWetness = data.hourly.leaf_wetness_probability[currentHourIndex] || 0;
    const uvIndex = data.hourly.uv_index[currentHourIndex] || 0;
    const freezingLevel = data.hourly.freezing_level_height[currentHourIndex] || 0;
    const visibility = data.hourly.visibility[currentHourIndex] || 0;

    return {
      ...data,
      current: {
        ...data.current,
        vapor_pressure_deficit: vpd,
        leaf_wetness_probability: leafWetness,
        uv_index: uvIndex,
        freezing_level_height: freezingLevel,
        visibility: visibility
      }
    };
  } catch (error) {
    console.warn("Failed to fetch Open-Meteo data:", error);
    return null;
  }
}
