/**
 * P02: discoverability preview for the 94 P00 *product concepts*.
 * These are NOT 94 verified implementations, a capability/permission registry,
 * nor evidence that the corresponding sensors, rasters or radios are present.
 * P04 will replace this read-only catalog with the canonical Tool Registry.
 */
export interface ToolConceptFamily {
  id: string;
  label: string;
  description: string;
  relatedEntry: string;
  concepts: readonly string[];
}
export const TOOL_CONCEPT_FAMILIES: readonly ToolConceptFamily[] = [
  {
    id: "spatial", label: "Spatial & remote sensing",
    description: "Imagery, indices, terrain, spatial evidence, masks and attribution.",
    relatedEntry: "raw-data",
    concepts: [
      "True Color RGB Basemap", "False Color Infrared (CIR)",
      "Sentinel-2 NDVI Surface", "EVI Enhanced Vegetation",
      "NDRE Red-Edge Chlorophyll", "NDWI / NDMI Water Index",
      "SAVI Soil-Adjusted Index", "Sentinel-1 SAR Backscatter",
      "SAR VV/VH Ratio", "Surface Roughness Estimate",
      "Thermal Inversion (TIRS)", "Evaporative Stress Fraction",
      "Cloud & Shadow Mask", "Atmospheric Penumbra Filter",
      "S2 Pixel Quality QA60/SCL", "Ground Sample Resolution",
      "Multi-Temporal Composite", "Zonal Contours",
      "Topographic Elevation", "Slope & Aspect",
      "Micro-Zone Polygons", "Zonal Variance & Outliers",
      "Pixel Inspection", "Surface Attribution & License",
    ],
  },
  {
    id: "sensors", label: "In-situ sensors & ground evidence",
    description: "Registered devices, readings, calibration and physical ground evidence.",
    relatedEntry: "sensors",
    concepts: [
      "Soil Moisture 0–10 cm", "Soil Moisture 10–40 cm",
      "Soil Moisture 40–100 cm", "Soil Temperature Profile",
      "Soil Electrical Conductivity", "Soil pH Station",
      "Air Temperature", "Relative Humidity",
      "Canopy Infrared Radiometer", "Rain Gauge",
      "Pyranometer", "Anemometer",
      "IP Camera Hub", "LoRaWAN Signal & Battery",
      "Drift & Recalibration", "Field NPK Laboratory Import",
    ],
  },
  {
    id: "drone", label: "Drones & aerial photogrammetry",
    description: "Mission plans, flight telemetry, coverage and qualified aerial products.",
    relatedEntry: "drone",
    concepts: [
      "Flight Path Planner", "Autonomous Waypoint Dispatch",
      "Return-to-Launch & Geofence", "Live UAV Telemetry",
      "High-Resolution Orthomosaic", "3D Canopy DSM",
      "Five-Band Multispectral", "Tree Canopy Extraction",
      "Canopy Gap Detection", "Thermal Orthomosaic",
      "Weed Patch Density", "Emergence Stand Count",
      "Battery & Coverage", "Photogrammetry QA",
    ],
  },
  {
    id: "mesia", label: "MESIA radio & electromagnetic research",
    description: "Receiver observability, wave interactions, dielectric hypotheses and trials.",
    relatedEntry: "mesia",
    concepts: [
      "Soil Complex Permittivity", "L-Band Penetration",
      "C-Band Scattering", "Multipath Attenuation",
      "RF Spectrogram", "SDR Receiver Status",
      "Antenna Azimuth & Polarization", "Phase Interferometry",
      "Permittivity Calibration", "RF Frequency Sweep",
      "Foliage Absorption", "Subsurface Layer Model",
    ],
  },
  {
    id: "simulation", label: "Simulation & agronomic decisions",
    description: "Water, nitrogen, biology, phenology, planning and hypothetical scenarios.",
    relatedEntry: "analysis",
    concepts: [
      "FAO-56 Single Crop", "Dual Crop Coefficient",
      "Daily Soil Water Balance", "Deficit Irrigation Window",
      "Irrigation Event Scheduler", "Rainfall What-If",
      "Heatwave What-If", "Yield Potential Estimator",
      "Degree-Day Progress", "Crop Growth Projection",
      "Salinity Leaching Estimate", "Nitrogen Uptake Curve",
      "Pest Risk Degree-Day", "Disease Infection Hours",
      "Harvest Window Index", "Economic Sensitivity",
    ],
  },
  {
    id: "temporal", label: "4D timeline & correlation",
    description: "Acquisition history, temporal comparison, provenance and replay.",
    relatedEntry: "analysis",
    concepts: [
      "Acquisition Time Scrub", "Dual-Epoch Comparison",
      "Temporal Delta Heatmap", "Ingest vs Acquisition QA",
      "Multi-Year Phenology", "Event Annotation",
      "Satellite Pass Forecast", "Time-Series Trends",
      "Raster Playback", "Anomaly Spike Detection",
      "Historical Replay", "Immutable Ledger Export",
    ],
  },
] as const;

export const TOOL_CONCEPT_COUNT = TOOL_CONCEPT_FAMILIES.reduce(
  (count, family) => count + family.concepts.length, 0,
);
