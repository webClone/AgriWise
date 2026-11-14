/** P04 historical crosswalk audit: proposals are NOT approved aliases or execution mappings.
 * P02's 94 preview labels and Pass 08's 94 canonical names differ in all 94 cases.
 * Lexical candidates are review hints only; a mismatch must never claim equivalence.
 */
export const P02_PREVIEW_CROSSWALK = Object.freeze([
  {
    "legacyId": "p02-preview-001",
    "legacyLabel": "True Color RGB Basemap",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-002",
    "legacyLabel": "False Color Infrared (CIR)",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-003",
    "legacyLabel": "Sentinel-2 NDVI Surface",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-004",
    "legacyLabel": "EVI Enhanced Vegetation",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-005",
    "legacyLabel": "NDRE Red-Edge Chlorophyll",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-006",
    "legacyLabel": "NDWI / NDMI Water Index",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.water-stress",
        "lexicalScore": 0.35
      }
    ]
  },
  {
    "legacyId": "p02-preview-007",
    "legacyLabel": "SAVI Soil-Adjusted Index",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-008",
    "legacyLabel": "Sentinel-1 SAR Backscatter",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.sentinel-1-sar-inspector",
        "lexicalScore": 0.67
      },
      {
        "id": "mesia.rfid-backscatter",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-009",
    "legacyLabel": "SAR VV/VH Ratio",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.sentinel-1-sar-inspector",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-010",
    "legacyLabel": "Surface Roughness Estimate",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-011",
    "legacyLabel": "Thermal Inversion (TIRS)",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-012",
    "legacyLabel": "Evaporative Stress Fraction",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.water-stress",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-013",
    "legacyLabel": "Cloud & Shadow Mask",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-014",
    "legacyLabel": "Atmospheric Penumbra Filter",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-015",
    "legacyLabel": "S2 Pixel Quality QA60/SCL",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-016",
    "legacyLabel": "Ground Sample Resolution",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.ground-truth-sample-manager",
        "lexicalScore": 0.58
      }
    ]
  },
  {
    "legacyId": "p02-preview-017",
    "legacyLabel": "Multi-Temporal Composite",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "asmae.temporal-time-peel",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-018",
    "legacyLabel": "Zonal Contours",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-019",
    "legacyLabel": "Topographic Elevation",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-020",
    "legacyLabel": "Slope & Aspect",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-021",
    "legacyLabel": "Micro-Zone Polygons",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "asmae.zone-laboratory",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-022",
    "legacyLabel": "Zonal Variance & Outliers",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-023",
    "legacyLabel": "Pixel Inspection",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "asmae.pixel-transect-inspector",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-024",
    "legacyLabel": "Surface Attribution & License",
    "previewFamily": "spatial",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-025",
    "legacyLabel": "Soil Moisture 0–10 cm",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.soil-depth-profile",
        "lexicalScore": 0.41
      },
      {
        "id": "agronomy.crop-soil-profile",
        "lexicalScore": 0.41
      },
      {
        "id": "acquisition.soil-dem-landcover-context",
        "lexicalScore": 0.35
      }
    ]
  },
  {
    "legacyId": "p02-preview-026",
    "legacyLabel": "Soil Moisture 10–40 cm",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.soil-depth-profile",
        "lexicalScore": 0.41
      },
      {
        "id": "agronomy.crop-soil-profile",
        "lexicalScore": 0.41
      },
      {
        "id": "acquisition.soil-dem-landcover-context",
        "lexicalScore": 0.35
      }
    ]
  },
  {
    "legacyId": "p02-preview-027",
    "legacyLabel": "Soil Moisture 40–100 cm",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-028",
    "legacyLabel": "Soil Temperature Profile",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.soil-depth-profile",
        "lexicalScore": 0.67
      },
      {
        "id": "agronomy.crop-soil-profile",
        "lexicalScore": 0.67
      }
    ]
  },
  {
    "legacyId": "p02-preview-029",
    "legacyLabel": "Soil Electrical Conductivity",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-030",
    "legacyLabel": "Soil pH Station",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.soil-depth-profile",
        "lexicalScore": 0.41
      },
      {
        "id": "agronomy.crop-soil-profile",
        "lexicalScore": 0.41
      },
      {
        "id": "acquisition.soil-dem-landcover-context",
        "lexicalScore": 0.35
      }
    ]
  },
  {
    "legacyId": "p02-preview-031",
    "legacyLabel": "Air Temperature",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-032",
    "legacyLabel": "Relative Humidity",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-033",
    "legacyLabel": "Canopy Infrared Radiometer",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-034",
    "legacyLabel": "Rain Gauge",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-035",
    "legacyLabel": "Pyranometer",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-036",
    "legacyLabel": "Anemometer",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-037",
    "legacyLabel": "IP Camera Hub",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.ip-camera-viewer",
        "lexicalScore": 0.5
      },
      {
        "id": "operations.camera-review",
        "lexicalScore": 0.5
      },
      {
        "id": "acquisition.camera-ptz-simulator",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-038",
    "legacyLabel": "LoRaWAN Signal & Battery",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-039",
    "legacyLabel": "Drift & Recalibration",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-040",
    "legacyLabel": "Field NPK Laboratory Import",
    "previewFamily": "sensors",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "asmae.zone-laboratory",
        "lexicalScore": 0.35
      },
      {
        "id": "operations.field-tasks",
        "lexicalScore": 0.35
      }
    ]
  },
  {
    "legacyId": "p02-preview-041",
    "legacyLabel": "Flight Path Planner",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "drone.mission-planner",
        "lexicalScore": 0.41
      },
      {
        "id": "drone.flight-history",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-042",
    "legacyLabel": "Autonomous Waypoint Dispatch",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-043",
    "legacyLabel": "Return-to-Launch & Geofence",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-044",
    "legacyLabel": "Live UAV Telemetry",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-045",
    "legacyLabel": "High-Resolution Orthomosaic",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "drone.orthomosaic-builder",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-046",
    "legacyLabel": "3D Canopy DSM",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-047",
    "legacyLabel": "Five-Band Multispectral",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-048",
    "legacyLabel": "Tree Canopy Extraction",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-049",
    "legacyLabel": "Canopy Gap Detection",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-050",
    "legacyLabel": "Thermal Orthomosaic",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "drone.orthomosaic-builder",
        "lexicalScore": 0.5
      }
    ]
  },
  {
    "legacyId": "p02-preview-051",
    "legacyLabel": "Weed Patch Density",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-052",
    "legacyLabel": "Emergence Stand Count",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-053",
    "legacyLabel": "Battery & Coverage",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "mesia.observability-coverage-map",
        "lexicalScore": 0.5
      },
      {
        "id": "drone.coverage-overlap-designer",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-054",
    "legacyLabel": "Photogrammetry QA",
    "previewFamily": "drone",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-055",
    "legacyLabel": "Soil Complex Permittivity",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-056",
    "legacyLabel": "L-Band Penetration",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-057",
    "legacyLabel": "C-Band Scattering",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-058",
    "legacyLabel": "Multipath Attenuation",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-059",
    "legacyLabel": "RF Spectrogram",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-060",
    "legacyLabel": "SDR Receiver Status",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "mesia.receiver-network",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-061",
    "legacyLabel": "Antenna Azimuth & Polarization",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-062",
    "legacyLabel": "Phase Interferometry",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-063",
    "legacyLabel": "Permittivity Calibration",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.sensor-calibration-qa",
        "lexicalScore": 0.71
      },
      {
        "id": "operations.calibration-experiment",
        "lexicalScore": 0.5
      },
      {
        "id": "mesia.antenna-pose-calibration",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-064",
    "legacyLabel": "RF Frequency Sweep",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-065",
    "legacyLabel": "Foliage Absorption",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-066",
    "legacyLabel": "Subsurface Layer Model",
    "previewFamily": "mesia",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-067",
    "legacyLabel": "FAO-56 Single Crop",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.crop-identity",
        "lexicalScore": 0.41
      },
      {
        "id": "agronomy.crop-rotation",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-068",
    "legacyLabel": "Dual Crop Coefficient",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.crop-identity",
        "lexicalScore": 0.41
      },
      {
        "id": "agronomy.crop-rotation",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-069",
    "legacyLabel": "Daily Soil Water Balance",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.water-stress",
        "lexicalScore": 0.35
      }
    ]
  },
  {
    "legacyId": "p02-preview-070",
    "legacyLabel": "Deficit Irrigation Window",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.irrigation-history",
        "lexicalScore": 0.41
      },
      {
        "id": "agronomy.planting-window",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-071",
    "legacyLabel": "Irrigation Event Scheduler",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.irrigation-history",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-072",
    "legacyLabel": "Rainfall What-If",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "operations.what-if-lab",
        "lexicalScore": 0.5
      },
      {
        "id": "agronomy.irrigation-what-if-simulation",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-073",
    "legacyLabel": "Heatwave What-If",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "operations.what-if-lab",
        "lexicalScore": 0.5
      },
      {
        "id": "agronomy.irrigation-what-if-simulation",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-074",
    "legacyLabel": "Yield Potential Estimator",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.yield-trajectory",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-075",
    "legacyLabel": "Degree-Day Progress",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-076",
    "legacyLabel": "Crop Growth Projection",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.crop-identity",
        "lexicalScore": 0.41
      },
      {
        "id": "agronomy.crop-rotation",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-077",
    "legacyLabel": "Salinity Leaching Estimate",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.salinity-explorer",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-078",
    "legacyLabel": "Nitrogen Uptake Curve",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-079",
    "legacyLabel": "Pest Risk Degree-Day",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.nutrient-risk",
        "lexicalScore": 0.35
      }
    ]
  },
  {
    "legacyId": "p02-preview-080",
    "legacyLabel": "Disease Infection Hours",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-081",
    "legacyLabel": "Harvest Window Index",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.planting-window",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-082",
    "legacyLabel": "Economic Sensitivity",
    "previewFamily": "simulation",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.economic-scenario",
        "lexicalScore": 0.5
      }
    ]
  },
  {
    "legacyId": "p02-preview-083",
    "legacyLabel": "Acquisition Time Scrub",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.acquisition-conflict-reliability",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-084",
    "legacyLabel": "Dual-Epoch Comparison",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-085",
    "legacyLabel": "Temporal Delta Heatmap",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "asmae.temporal-time-peel",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-086",
    "legacyLabel": "Ingest vs Acquisition QA",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "acquisition.acquisition-conflict-reliability",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-087",
    "legacyLabel": "Multi-Year Phenology",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "agronomy.phenology-calendar",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-088",
    "legacyLabel": "Event Annotation",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "drone.mission-event-timeline",
        "lexicalScore": 0.41
      },
      {
        "id": "operations.field-event-ledger",
        "lexicalScore": 0.41
      }
    ]
  },
  {
    "legacyId": "p02-preview-089",
    "legacyLabel": "Satellite Pass Forecast",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-090",
    "legacyLabel": "Time-Series Trends",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-091",
    "legacyLabel": "Raster Playback",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-092",
    "legacyLabel": "Anomaly Spike Detection",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": []
  },
  {
    "legacyId": "p02-preview-093",
    "legacyLabel": "Historical Replay",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "asmae.historical-events-stress-memory",
        "lexicalScore": 0.35
      }
    ]
  },
  {
    "legacyId": "p02-preview-094",
    "legacyLabel": "Immutable Ledger Export",
    "previewFamily": "temporal",
    "reviewStatus": "pending_human_review",
    "approvedCanonicalId": null,
    "proposedCandidates": [
      {
        "id": "asmae.assimilation-ledger",
        "lexicalScore": 0.41
      },
      {
        "id": "operations.evidence-export",
        "lexicalScore": 0.41
      }
    ]
  }
]);
export function getUnresolvedPreviewLabels() {
  return P02_PREVIEW_CROSSWALK.filter(entry => entry.approvedCanonicalId === null);
}
