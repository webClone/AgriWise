/**
 * Agribrain Physics Engine
 * Derived agronomic metrics from raw telemetry.
 */

/**
 * Calculates Delta-T (°C) - The critical indicator for spraying conditions.
 * Delta-T = Dry Bulb Temp - Wet Bulb Temp.
 * Optimal Spraying: 2°C - 8°C.
 */
export function calculateDeltaT(temp: number, humidity: number): number {
  const T = temp;
  const RH = Math.max(0.1, humidity); // Prevent log errors

  // Stull (2011) Wet Bulb Approximation
  // Tw = T * atan[0.151977 * (RH% + 8.313659)^1/2] + atan(T + RH%) - atan(RH% - 1.676331) + 0.00391838 * (RH%)^3/2 * atan(0.023101 * RH%) - 4.686035
  
  const term1 = 0.151977 * Math.pow(RH + 8.313659, 0.5);
  const term2 = T + RH;
  const term3 = RH - 1.676331;
  const term4 = 0.023101 * RH;
  
  const wetBulb = T * Math.atan(term1) 
                + Math.atan(term2) 
                - Math.atan(term3) 
                + 0.00391838 * Math.pow(RH, 1.5) * Math.atan(term4) 
                - 4.686035;

  return Number((T - wetBulb).toFixed(1));
}

/**
 * Calculates Dew Point (°C).
 * Magnus Formula.
 */
export function calculateDewPoint(temp: number, humidity: number): number {
  if (humidity <= 0) return -99;
  const a = 17.27;
  const b = 237.7;
  const alpha = ((a * temp) / (b + temp)) + Math.log(humidity / 100.0);
  const dewPoint = (b * alpha) / (a - alpha);
  return Number(dewPoint.toFixed(1));
}

/**
 * Calculates Soil Water Tension (kPa) (Suction).
 * Approximated using simplified Campbell/Saxton relationships based on texture.
 * 
 * @param vwc Volumetric Water Content (0.00 - 1.00)
 * @param clay Clay percentage (0-100)
 * @param sand Sand percentage (0-100)
 */
export function calculateSoilTension(vwc: number, clay: number, sand: number): number {
  // Clapp & Hornberger / Cosby approximations interpolated by Clay content
  // Clay % is the dominant factor in retention curve shape.
  const clayFrac = Math.min(100, Math.max(0, clay)) / 100;
  
  // Saturation Water Content (Porosity) - Theta_s
  // Sand ~ 0.39, Clay ~ 0.48
  const thetaS = 0.39 + (0.09 * clayFrac);
  
  // Air Entry Potential (Psi_e) - kPa (positive value for calculation)
  // Sand ~ 1.2, Clay ~ 4.8
  const psiE = 1.0 + (3.8 * clayFrac);
  
  // Pore Pore Size Distribution Index (b)
  // Sand ~ 4, Clay ~ 12
  const b = 4.0 + (8.0 * clayFrac);

  // VWC cannot exceed saturation or be 0
  const theta = Math.min(thetaS, Math.max(0.01, vwc));
  
  // Campbell Equation: Psi = Psi_e * (Theta / Theta_s)^-b
  const tension = psiE * Math.pow(theta / thetaS, -b);

  // Clamp to realistic agronomic bounds
  // 0 = Saturation
  // 1500 = Permanent Wilting Point
  // 3000 = Bone dry
  return Math.min(3000, Math.ceil(tension));
}
