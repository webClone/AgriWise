/* ═══ Evidence Source Taxonomy ══════════════════════════════════
   Types and families of evidence that AgriBrain ingests.
   Used by: EvidenceGraphStory, AgriBrainStory, and audience cards.
   ═══════════════════════════════════════════════════════════════ */

export interface EvidenceSource {
  id: string;
  label: string;
  family: EvidenceFamily;
  description: string;
  icon: string;
  color: string;
  /** Whether this source provides continuous spatial coverage */
  spatialCoverage: "global" | "regional" | "field" | "point";
  /** Approximate temporal frequency */
  temporalNote: string;
}

export type EvidenceFamily =
  | "earth-observation"
  | "atmospheric"
  | "subsurface"
  | "in-situ"
  | "operational"
  | "economic"
  | "outcome";

export const EVIDENCE_FAMILIES: Record<
  EvidenceFamily,
  { label: string; color: string }
> = {
  "earth-observation": { label: "Earth Observation", color: "#22d3ee" },
  atmospheric: { label: "Atmospheric", color: "#60a5fa" },
  subsurface: { label: "Subsurface", color: "#818cf8" },
  "in-situ": { label: "In-Situ", color: "#fbbf24" },
  operational: { label: "Operational", color: "#4ade80" },
  economic: { label: "Economic", color: "#fb923c" },
  outcome: { label: "Outcome", color: "#f87171" },
};

export const EVIDENCE_SOURCES: EvidenceSource[] = [
  {
    id: "satellite-optical",
    label: "Satellite Optical",
    family: "earth-observation",
    description:
      "Multispectral imagery from Sentinel-2 and similar platforms. Vegetation indices, land cover, phenology.",
    icon: "🛰️",
    color: "#4ade80",
    spatialCoverage: "global",
    temporalNote: "5-day revisit",
  },
  {
    id: "satellite-sar",
    label: "Satellite SAR",
    family: "earth-observation",
    description:
      "Synthetic Aperture Radar from Sentinel-1. Surface moisture, crop structure, all-weather capability.",
    icon: "📡",
    color: "#22d3ee",
    spatialCoverage: "global",
    temporalNote: "6–12 day revisit",
  },
  {
    id: "weather",
    label: "Weather",
    family: "atmospheric",
    description:
      "Station observations, reanalysis grids, forecasts. Temperature, precipitation, humidity, wind, radiation.",
    icon: "🌤️",
    color: "#60a5fa",
    spatialCoverage: "regional",
    temporalNote: "Hourly to daily",
  },
  {
    id: "soil-sensor",
    label: "Soil Sensors",
    family: "subsurface",
    description:
      "IoT soil moisture, temperature, EC probes at multiple depths. Continuous root-zone monitoring.",
    icon: "📡",
    color: "#818cf8",
    spatialCoverage: "point",
    temporalNote: "Real-time",
  },
  {
    id: "farmer-photo",
    label: "Field Photographs",
    family: "in-situ",
    description:
      "GPS-tagged photographs with visual evidence. Disease symptoms, growth stage, damage, pest presence.",
    icon: "📸",
    color: "#fbbf24",
    spatialCoverage: "point",
    temporalNote: "Event-driven",
  },
  {
    id: "farmer-event",
    label: "Farmer Operations",
    family: "operational",
    description:
      "Sowing, irrigation, fertilisation, spraying, harvest events recorded by the farmer or integrated from equipment.",
    icon: "🌾",
    color: "#4ade80",
    spatialCoverage: "field",
    temporalNote: "Event-driven",
  },
  {
    id: "drone",
    label: "Drone Imagery",
    family: "earth-observation",
    description:
      "High-resolution RGB, multispectral or thermal imagery from UAV flights. Sub-meter plant-level detail.",
    icon: "🚁",
    color: "#34d399",
    spatialCoverage: "field",
    temporalNote: "On-demand",
  },
  {
    id: "lab-analysis",
    label: "Laboratory Analysis",
    family: "in-situ",
    description:
      "Soil chemistry, tissue analysis, water quality, pathogen identification from laboratory testing.",
    icon: "🧪",
    color: "#e879f9",
    spatialCoverage: "point",
    temporalNote: "Seasonal / event-driven",
  },
  {
    id: "irrigation-controller",
    label: "Irrigation Systems",
    family: "operational",
    description:
      "Flow meters, valve state, scheduling data from connected irrigation infrastructure.",
    icon: "💧",
    color: "#06b6d4",
    spatialCoverage: "field",
    temporalNote: "Real-time",
  },
  {
    id: "management-history",
    label: "Management History",
    family: "operational",
    description:
      "Historical field operations, crop rotations, intervention records and seasonal outcomes.",
    icon: "📋",
    color: "#94a3b8",
    spatialCoverage: "field",
    temporalNote: "Longitudinal",
  },
  {
    id: "market-data",
    label: "Market Data",
    family: "economic",
    description:
      "Commodity prices, input costs, regional trade flows, supply/demand indicators.",
    icon: "📈",
    color: "#fb923c",
    spatialCoverage: "regional",
    temporalNote: "Daily to weekly",
  },
  {
    id: "measured-outcomes",
    label: "Measured Outcomes",
    family: "outcome",
    description:
      "Actual yield, quality metrics, harvest timing. Ground truth for model calibration and learning.",
    icon: "📊",
    color: "#f87171",
    spatialCoverage: "field",
    temporalNote: "Seasonal",
  },
];
