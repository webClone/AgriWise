/**
 * Akaloris P04 draft manifest. Source: Pass 08 intended product tool list (94).
 * This registry is discovery-only until each capability's source, permission,
 * evidence, maturity, and actual action contract have been independently qualified.
 * P02's other 94 preview labels are NOT automatically equivalent; retain that
 * list until an explicitly reviewed alias/crosswalk migration exists.
 * Never authorize scientific evidence, hardware or server actions from this file.
 */
export const TOOL_MANIFEST_VERSION = "p04-candidate-01";
export const TOOL_FAMILIES = Object.freeze([
  {
    "id": "acquisition",
    "label": "Acquisition & observation",
    "description": "Satellite, weather, field sensors, and observation provenance",
    "count": 17
  },
  {
    "id": "asmae",
    "label": "AgriBrain & ASMAE",
    "description": "Scientific state, uncertainty, lineage and qualified interpretation",
    "count": 12
  },
  {
    "id": "drone",
    "label": "Drones & aerial imaging",
    "description": "Mission planning, flight evidence, and aerial products",
    "count": 13
  },
  {
    "id": "mesia",
    "label": "MESIA & RF research",
    "description": "Radio sensing, observability, calibration and research",
    "count": 15
  },
  {
    "id": "agronomy",
    "label": "Agronomy & biology",
    "description": "Crop, water, salinity, nutrient and biological investigations",
    "count": 19
  },
  {
    "id": "operations",
    "label": "Operations, AI & research",
    "description": "Tasks, trials, reports, recommendations, and future research",
    "count": 18
  }
]);
export const TOOL_MANIFEST = Object.freeze([
  {
    "id": "acquisition.satellite-scene-explorer",
    "sourceIndex": 1,
    "family": "acquisition",
    "title": {
      "en": "Satellite Scene Explorer",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.satellite-revisit-cloud-audit",
    "sourceIndex": 2,
    "family": "acquisition",
    "title": {
      "en": "Satellite Revisit & Cloud Audit",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.sentinel-1-sar-inspector",
    "sourceIndex": 3,
    "family": "acquisition",
    "title": {
      "en": "Sentinel-1 SAR Inspector",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.vegetation-spectral-index-lab",
    "sourceIndex": 4,
    "family": "acquisition",
    "title": {
      "en": "Vegetation Spectral Index Lab",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.weather-forecast-explorer",
    "sourceIndex": 5,
    "family": "acquisition",
    "title": {
      "en": "Weather & Forecast Explorer",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.soil-dem-landcover-context",
    "sourceIndex": 6,
    "family": "acquisition",
    "title": {
      "en": "Soil/DEM/Landcover Context",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.sensor-network-map",
    "sourceIndex": 7,
    "family": "acquisition",
    "title": {
      "en": "Sensor Network Map",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.live-observation-stream",
    "sourceIndex": 8,
    "family": "acquisition",
    "title": {
      "en": "Live Observation Stream",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.sensor-calibration-qa",
    "sourceIndex": 9,
    "family": "acquisition",
    "title": {
      "en": "Sensor Calibration & QA",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.sensor-health-alerts",
    "sourceIndex": 10,
    "family": "acquisition",
    "title": {
      "en": "Sensor Health & Alerts",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.soil-depth-profile",
    "sourceIndex": 11,
    "family": "acquisition",
    "title": {
      "en": "Soil Depth Profile",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.device-placement-gap-planner",
    "sourceIndex": 12,
    "family": "acquisition",
    "title": {
      "en": "Device Placement/Gap Planner",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.ip-camera-viewer",
    "sourceIndex": 13,
    "family": "acquisition",
    "title": {
      "en": "IP Camera Viewer",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.camera-ptz-simulator",
    "sourceIndex": 14,
    "family": "acquisition",
    "title": {
      "en": "Camera PTZ Simulator",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.farmer-photo-report",
    "sourceIndex": 15,
    "family": "acquisition",
    "title": {
      "en": "Farmer Photo/Report",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.ground-truth-sample-manager",
    "sourceIndex": 16,
    "family": "acquisition",
    "title": {
      "en": "Ground Truth & Sample Manager",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "acquisition.acquisition-conflict-reliability",
    "sourceIndex": 17,
    "family": "acquisition",
    "title": {
      "en": "Acquisition Conflict / Reliability",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.13-state-explorer",
    "sourceIndex": 18,
    "family": "asmae",
    "title": {
      "en": "13-State Explorer",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.state-uncertainty-inspector",
    "sourceIndex": 19,
    "family": "asmae",
    "title": {
      "en": "State Uncertainty Inspector",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.cross-state-correlation",
    "sourceIndex": 20,
    "family": "asmae",
    "title": {
      "en": "Cross-State Correlation",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.assimilation-ledger",
    "sourceIndex": 21,
    "family": "asmae",
    "title": {
      "en": "Assimilation Ledger",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.scene-data-lineage-viewer",
    "sourceIndex": 22,
    "family": "asmae",
    "title": {
      "en": "Scene & Data-Lineage Viewer",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.zone-laboratory",
    "sourceIndex": 23,
    "family": "asmae",
    "title": {
      "en": "Zone Laboratory",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.pixel-transect-inspector",
    "sourceIndex": 24,
    "family": "asmae",
    "title": {
      "en": "Pixel/Transect Inspector",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.temporal-time-peel",
    "sourceIndex": 25,
    "family": "asmae",
    "title": {
      "en": "Temporal Time-Peel",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.historical-events-stress-memory",
    "sourceIndex": 26,
    "family": "asmae",
    "title": {
      "en": "Historical Events & Stress Memory",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.state-retrovalidation",
    "sourceIndex": 27,
    "family": "asmae",
    "title": {
      "en": "State Retrovalidation",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.bma-model-disagreement",
    "sourceIndex": 28,
    "family": "asmae",
    "title": {
      "en": "BMA/Model Disagreement",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "asmae.scientific-provenance-export",
    "sourceIndex": 29,
    "family": "asmae",
    "title": {
      "en": "Scientific Provenance & Export",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.mission-planner",
    "sourceIndex": 30,
    "family": "drone",
    "title": {
      "en": "Mission Planner",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.coverage-overlap-designer",
    "sourceIndex": 31,
    "family": "drone",
    "title": {
      "en": "Coverage/Overlap Designer",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.targeted-hotspot-flight",
    "sourceIndex": 32,
    "family": "drone",
    "title": {
      "en": "Targeted Hotspot Flight",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.preflight-checklist",
    "sourceIndex": 33,
    "family": "drone",
    "title": {
      "en": "Preflight Checklist",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.drone-fleet-connectivity",
    "sourceIndex": 34,
    "family": "drone",
    "title": {
      "en": "Drone Fleet/Connectivity",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.planned-waypoint-preview",
    "sourceIndex": 35,
    "family": "drone",
    "title": {
      "en": "Planned Waypoint Preview",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.real-flight-tracker-hardware",
    "sourceIndex": 36,
    "family": "drone",
    "title": {
      "en": "Real Flight Tracker (hardware)",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.paused-rtl-abort-control-hardware-permissions",
    "sourceIndex": 37,
    "family": "drone",
    "title": {
      "en": "Paused/RTL/Abort Control (hardware/permissions)",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.mission-event-timeline",
    "sourceIndex": 38,
    "family": "drone",
    "title": {
      "en": "Mission Event Timeline",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.flight-history",
    "sourceIndex": 39,
    "family": "drone",
    "title": {
      "en": "Flight History",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.orthomosaic-builder",
    "sourceIndex": 40,
    "family": "drone",
    "title": {
      "en": "Orthomosaic Builder",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.drone-imagery-compare",
    "sourceIndex": 41,
    "family": "drone",
    "title": {
      "en": "Drone Imagery Compare",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "drone.refly-qa-revisit-planner",
    "sourceIndex": 42,
    "family": "drone",
    "title": {
      "en": "Refly/QA/Revisit Planner",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.receiver-network",
    "sourceIndex": 43,
    "family": "mesia",
    "title": {
      "en": "Receiver Network",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.observability-coverage-map",
    "sourceIndex": 44,
    "family": "mesia",
    "title": {
      "en": "Observability/Coverage Map",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.blind-sector-analyzer",
    "sourceIndex": 45,
    "family": "mesia",
    "title": {
      "en": "Blind-Sector Analyzer",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.spectrum-signal-viewer",
    "sourceIndex": 46,
    "family": "mesia",
    "title": {
      "en": "Spectrum/Signal Viewer",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.gnss-reflectometry",
    "sourceIndex": 47,
    "family": "mesia",
    "title": {
      "en": "GNSS Reflectometry",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.wi-fi-csi",
    "sourceIndex": 48,
    "family": "mesia",
    "title": {
      "en": "Wi-Fi CSI",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.cellular-link-analyzer",
    "sourceIndex": 49,
    "family": "mesia",
    "title": {
      "en": "Cellular Link Analyzer",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.lora-lpwan",
    "sourceIndex": 50,
    "family": "mesia",
    "title": {
      "en": "LoRa/LPWAN",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.rfid-backscatter",
    "sourceIndex": 51,
    "family": "mesia",
    "title": {
      "en": "RFID/Backscatter",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.radar-mmwave",
    "sourceIndex": 52,
    "family": "mesia",
    "title": {
      "en": "Radar/MmWave",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.uwb-gpr",
    "sourceIndex": 53,
    "family": "mesia",
    "title": {
      "en": "UWB/GPR",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.dielectric-inversion-lab",
    "sourceIndex": 54,
    "family": "mesia",
    "title": {
      "en": "Dielectric Inversion Lab",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.antenna-pose-calibration",
    "sourceIndex": 55,
    "family": "mesia",
    "title": {
      "en": "Antenna Pose/Calibration",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.asmae-supervisor",
    "sourceIndex": 56,
    "family": "mesia",
    "title": {
      "en": "ASMAE Supervisor",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "mesia.physical-experiment-campaign-hardware-gated",
    "sourceIndex": 57,
    "family": "mesia",
    "title": {
      "en": "Physical Experiment Campaign (hardware gated)",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.crop-identity",
    "sourceIndex": 58,
    "family": "agronomy",
    "title": {
      "en": "Crop Identity",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.phenology-calendar",
    "sourceIndex": 59,
    "family": "agronomy",
    "title": {
      "en": "Phenology Calendar",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.crop-soil-profile",
    "sourceIndex": 60,
    "family": "agronomy",
    "title": {
      "en": "Crop/Soil Profile",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.water-stress",
    "sourceIndex": 61,
    "family": "agronomy",
    "title": {
      "en": "Water Stress",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.root-zone-hydraulic-model",
    "sourceIndex": 62,
    "family": "agronomy",
    "title": {
      "en": "Root-Zone Hydraulic Model",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.irrigation-history",
    "sourceIndex": 63,
    "family": "agronomy",
    "title": {
      "en": "Irrigation History",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.irrigation-what-if-simulation",
    "sourceIndex": 64,
    "family": "agronomy",
    "title": {
      "en": "Irrigation What-if (simulation)",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.salinity-explorer",
    "sourceIndex": 65,
    "family": "agronomy",
    "title": {
      "en": "Salinity Explorer",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.nutrient-risk",
    "sourceIndex": 66,
    "family": "agronomy",
    "title": {
      "en": "Nutrient Risk",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.nutrient-demand-loss",
    "sourceIndex": 67,
    "family": "agronomy",
    "title": {
      "en": "Nutrient Demand/Loss",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.vra-rate-preview-not-authorized-dosage",
    "sourceIndex": 68,
    "family": "agronomy",
    "title": {
      "en": "VRA Rate Preview (not authorized dosage)",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.disease-biotic-pressure",
    "sourceIndex": 69,
    "family": "agronomy",
    "title": {
      "en": "Disease/Biotic Pressure",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.scouting-and-sampling",
    "sourceIndex": 70,
    "family": "agronomy",
    "title": {
      "en": "Scouting and Sampling",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.suitability-map",
    "sourceIndex": 71,
    "family": "agronomy",
    "title": {
      "en": "Suitability Map",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.planting-window",
    "sourceIndex": 72,
    "family": "agronomy",
    "title": {
      "en": "Planting Window",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.crop-rotation",
    "sourceIndex": 73,
    "family": "agronomy",
    "title": {
      "en": "Crop Rotation",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.yield-trajectory",
    "sourceIndex": 74,
    "family": "agronomy",
    "title": {
      "en": "Yield Trajectory",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.economic-scenario",
    "sourceIndex": 75,
    "family": "agronomy",
    "title": {
      "en": "Economic Scenario",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "agronomy.field-health-comparison",
    "sourceIndex": 76,
    "family": "agronomy",
    "title": {
      "en": "Field Health Comparison",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.field-event-ledger",
    "sourceIndex": 77,
    "family": "operations",
    "title": {
      "en": "Field Event Ledger",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.field-tasks",
    "sourceIndex": 78,
    "family": "operations",
    "title": {
      "en": "Field Tasks",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.operational-feasibility",
    "sourceIndex": 79,
    "family": "operations",
    "title": {
      "en": "Operational Feasibility",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.intervention-planning-read-only-authorization-bounded",
    "sourceIndex": 80,
    "family": "operations",
    "title": {
      "en": "Intervention Planning (read-only, authorization bounded)",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.equipment-simulator",
    "sourceIndex": 81,
    "family": "operations",
    "title": {
      "en": "Equipment Simulator",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.camera-review",
    "sourceIndex": 82,
    "family": "operations",
    "title": {
      "en": "Camera Review",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.expert-ai-investigator",
    "sourceIndex": 83,
    "family": "operations",
    "title": {
      "en": "Expert AI Investigator",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.farmer-explanation",
    "sourceIndex": 84,
    "family": "operations",
    "title": {
      "en": "Farmer Explanation",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.what-if-lab",
    "sourceIndex": 85,
    "family": "operations",
    "title": {
      "en": "What-if Lab",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.comparative-experiments",
    "sourceIndex": 86,
    "family": "operations",
    "title": {
      "en": "Comparative Experiments",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.controlled-field-trial-manager",
    "sourceIndex": 87,
    "family": "operations",
    "title": {
      "en": "Controlled Field Trial Manager",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.calibration-experiment",
    "sourceIndex": 88,
    "family": "operations",
    "title": {
      "en": "Calibration Experiment",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.hypothesis-notebook",
    "sourceIndex": 89,
    "family": "operations",
    "title": {
      "en": "Hypothesis Notebook",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.report-builder",
    "sourceIndex": 90,
    "family": "operations",
    "title": {
      "en": "Report Builder",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.evidence-export",
    "sourceIndex": 91,
    "family": "operations",
    "title": {
      "en": "Evidence Export",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.alert-follow-up-center",
    "sourceIndex": 92,
    "family": "operations",
    "title": {
      "en": "Alert & Follow-up Center",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.future-world-model-studio",
    "sourceIndex": 93,
    "family": "operations",
    "title": {
      "en": "Future World-Model Studio",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  },
  {
    "id": "operations.future-omega-research-console",
    "sourceIndex": 94,
    "family": "operations",
    "title": {
      "en": "Future Omega Research Console",
      "ar": null,
      "fr": null
    },
    "aliases": [],
    "maturity": "unreviewed",
    "capability": "read_only",
    "surface": "concept_preview",
    "openAction": "view",
    "permission": "not_qualified",
    "inputs": [],
    "accepts": [],
    "requiredEvidence": [],
    "reason": "The concept has not been independently qualified for execution. This is a design and discovery entry.",
    "source": "plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md"
  }
]);
export const TOOL_MANIFEST_COUNT = TOOL_MANIFEST.length;

const byId = new Map(TOOL_MANIFEST.map(item => [item.id, item]));
export function getToolConcept(id) {
  return typeof id === "string" ? byId.get(id) ?? null : null;
}
export function searchToolConcepts(query = "", family = "all") {
  const tokens = String(query).normalize("NFKD").toLowerCase().trim().split(/\s+/).filter(Boolean);
  return TOOL_MANIFEST.filter(tool => {
    if (family !== "all" && tool.family !== family) return false;
    if (!tokens.length) return true;
    const haystack = [tool.title.en, ...(tool.aliases || []), tool.family, tool.id].join(" ").normalize("NFKD").toLowerCase();
    return tokens.every(token => haystack.includes(token));
  });
}
/** Client-only discovery presentation; execution authority is never inferred. */
export function describeToolAvailability(id) {
  const tool = getToolConcept(id);
  if (!tool) return { discoverable: false, canOpen: false, canExecute: false, canDispatch: false, state: "unknown", reason: "Unknown tool concept" };
  return { discoverable: true, canOpen: true, canExecute: false, canDispatch: false, state: "read_only", reason: tool.reason };
}
