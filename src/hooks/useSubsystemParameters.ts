"use client";

/**
 * useSubsystemParameters.ts
 *
 * Parametric Control Engine for AgriBrain & MESIA Subsystems (L0 through L10).
 * Empowers farmers and agronomists to:
 *   1. Inspect telemetry and provenance for every layer.
 *   2. Override generic fallbacks (e.g. replace regional soil profile with verified lab tests).
 *   3. Calibrate uncalibrated models (e.g. set crop type and target yield for L6).
 *   4. Dynamically simulate pipeline health and epistemic reliability in real time.
 *   5. Persist tuned parameters in localStorage per plot.
 */

import { useState, useEffect, useCallback, useMemo } from "react";

export interface L0Params {
  elevationOffset_m: number;
  heatThreshold_c: number;
  frostThreshold_c: number;
  forecastHorizon_days: number;
  radiationSource: "satellite" | "era5_climatology";
}

export interface L1Params {
  simulatedSensorActive: boolean;
  soilMoistureVwc_pct: number;
  soilTemp_c: number;
  soilEc_ds_m: number;
  sensorFusionWeight_pct: number;
}

export interface L2Params {
  cropStageOverride: "auto" | "emergence" | "vegetative" | "flowering" | "yield_formation" | "ripening" | "harvest";
  confirmedPlantingDate: string;
  ndviSensitivity: number;
  cloudFilterStrictness: "strict" | "standard" | "relaxed";
}

export interface L3Params {
  irrigationMethod: "drip" | "pivot" | "sprinkler" | "furrow";
  irrigationEfficiency_pct: number;
  rootDepth_cm: number;
  depletionTrigger_pct: number;
}

export interface L4Params {
  sourceMode: "regional_fallback" | "lab_test";
  textureClass: "loam" | "sandy_loam" | "clay_loam" | "clay" | "sand" | "silty_loam";
  sand_pct: number;
  clay_pct: number;
  silt_pct: number;
  ph: number;
  organicCarbon_g_kg: number;
  totalNitrogen_g_kg: number;
  cec_meq_100g: number;
  bulkDensity_g_cm3: number;
}

export interface L5Params {
  pathogenSusceptibility: "resistant" | "moderate" | "high" | "severe";
  sporeGerminationHours: number;
  sprayWindowWindCap_ms: number;
  relativeHumidityAlert_pct: number;
}

export interface L6Params {
  sourceMode: "uncalibrated" | "calibrated";
  cropType: "olive" | "citrus" | "wheat" | "tomato" | "barley" | "potato" | "maize" | "date_palm" | "other";
  targetYield_t_ha: number;
  cropCoefficientKc: number;
  historicalBenchmark_t_ha: number;
}

export interface L7Params {
  laborAvailable: boolean;
  machineryReady: boolean;
  prioritySorting: "urgency" | "economic_impact" | "water_saving";
  maxInterventionsPerWeek: number;
}

export interface L8Params {
  safetyMargin_pct: number;
  waterVolume_l_ha: number;
  nitrogenCap_kg_ha: number;
  variableRateResolution_m: number;
}

export interface L9Params {
  advisoryStrategy: "conservative" | "balanced" | "yield_maximizing";
  economicSensitivity: "low" | "medium" | "high";
  alertNotificationUrgency: "all" | "critical_only";
}

export interface L10Params {
  safetyStrictness: "strict" | "balanced" | "permissive";
  conflictResolution: "safety_first" | "yield_first" | "consensus";
  spatialRasterBlending: boolean;
}

export interface SubsystemParamsState {
  L0: L0Params;
  L1: L1Params;
  L2: L2Params;
  L3: L3Params;
  L4: L4Params;
  L5: L5Params;
  L6: L6Params;
  L7: L7Params;
  L8: L8Params;
  L9: L9Params;
  L10: L10Params;
}

export const DEFAULT_SUBSYSTEM_PARAMS: SubsystemParamsState = {
  L0: {
    elevationOffset_m: 0,
    heatThreshold_c: 35.0,
    frostThreshold_c: 2.0,
    forecastHorizon_days: 7,
    radiationSource: "satellite",
  },
  L1: {
    simulatedSensorActive: false,
    soilMoistureVwc_pct: 28.5,
    soilTemp_c: 22.4,
    soilEc_ds_m: 1.2,
    sensorFusionWeight_pct: 70,
  },
  L2: {
    cropStageOverride: "auto",
    confirmedPlantingDate: "2026-03-15",
    ndviSensitivity: 1.0,
    cloudFilterStrictness: "standard",
  },
  L3: {
    irrigationMethod: "drip",
    irrigationEfficiency_pct: 85,
    rootDepth_cm: 65,
    depletionTrigger_pct: 50,
  },
  L4: {
    sourceMode: "regional_fallback",
    textureClass: "loam",
    sand_pct: 40,
    clay_pct: 25,
    silt_pct: 35,
    ph: 6.5,
    organicCarbon_g_kg: 20.0,
    totalNitrogen_g_kg: 1.5,
    cec_meq_100g: 15.0,
    bulkDensity_g_cm3: 1.30,
  },
  L5: {
    pathogenSusceptibility: "moderate",
    sporeGerminationHours: 6,
    sprayWindowWindCap_ms: 4.5,
    relativeHumidityAlert_pct: 85,
  },
  L6: {
    sourceMode: "uncalibrated",
    cropType: "olive",
    targetYield_t_ha: 6.5,
    cropCoefficientKc: 0.75,
    historicalBenchmark_t_ha: 5.8,
  },
  L7: {
    laborAvailable: true,
    machineryReady: true,
    prioritySorting: "urgency",
    maxInterventionsPerWeek: 4,
  },
  L8: {
    safetyMargin_pct: 100,
    waterVolume_l_ha: 300,
    nitrogenCap_kg_ha: 120,
    variableRateResolution_m: 10,
  },
  L9: {
    advisoryStrategy: "balanced",
    economicSensitivity: "medium",
    alertNotificationUrgency: "all",
  },
  L10: {
    safetyStrictness: "balanced",
    conflictResolution: "safety_first",
    spatialRasterBlending: true,
  },
};

const STORAGE_PREFIX = "agriwise_params_plot_";

export function useSubsystemParameters(plotId: string = "default") {
  const storageKey = `${STORAGE_PREFIX}${plotId}`;

  const [params, setParams] = useState<SubsystemParamsState>(() => {
    if (typeof window === "undefined") return DEFAULT_SUBSYSTEM_PARAMS;
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        return { ...DEFAULT_SUBSYSTEM_PARAMS, ...JSON.parse(stored) };
      }
    } catch {
      // Fallback
    }
    return DEFAULT_SUBSYSTEM_PARAMS;
  });

  const [activeDashboardLayer, setActiveDashboardLayer] = useState<string | null>(null);

  // Sync state if storageKey changes after hydration or plot change
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem(storageKey);
        if (stored) {
          setParams(prev => ({ ...DEFAULT_SUBSYSTEM_PARAMS, ...JSON.parse(stored) }));
        }
      } catch {}
    }
  }, [storageKey]);

  // Listen to cross-window or storage event updates
  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleStorage = (e: StorageEvent) => {
      if (e.key === storageKey && e.newValue) {
        try {
          setParams(prev => ({ ...DEFAULT_SUBSYSTEM_PARAMS, ...JSON.parse(e.newValue!) }));
        } catch {}
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [storageKey]);

  // Persist whenever params change
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(storageKey, JSON.stringify(params));
      } catch {
        // Storage quota full or unavailable
      }
    }
  }, [params, storageKey]);

  const updateLayer = useCallback(<K extends keyof SubsystemParamsState>(
    layerId: K,
    patch: Partial<SubsystemParamsState[K]>
  ) => {
    setParams(prev => ({
      ...prev,
      [layerId]: {
        ...prev[layerId],
        ...patch,
      },
    }));
  }, []);

  const resetLayer = useCallback((layerId: keyof SubsystemParamsState) => {
    setParams(prev => ({
      ...prev,
      [layerId]: DEFAULT_SUBSYSTEM_PARAMS[layerId],
    }));
  }, []);

  const resetAll = useCallback(() => {
    setParams(DEFAULT_SUBSYSTEM_PARAMS);
    if (typeof window !== "undefined") {
      try {
        localStorage.removeItem(storageKey);
      } catch {}
    }
  }, [storageKey]);

  // Derived layer overrides
  const isLayerOverridden = useCallback((layerId: string): boolean => {
    const key = layerId as keyof SubsystemParamsState;
    if (!params[key]) return false;
    if (layerId === "L4") return params.L4.sourceMode === "lab_test";
    if (layerId === "L6") return params.L6.sourceMode === "calibrated";
    if (layerId === "L1") return params.L1.simulatedSensorActive;
    if (layerId === "L2") return params.L2.cropStageOverride !== "auto";
    return JSON.stringify(params[key]) !== JSON.stringify(DEFAULT_SUBSYSTEM_PARAMS[key]);
  }, [params]);

  // Dynamic status evaluation
  const getSimulatedLayerStatus = useCallback((layerId: string, originalStatus: string): {
    status: "OK" | "DEGRADED" | "FAILED" | "UNAVAILABLE" | "SKIPPED";
    confidence: number;
    sourceTag: string;
    isOverridden: boolean;
    flags: string[];
  } => {
    if (layerId === "L4") {
      if (params.L4.sourceMode === "lab_test") {
        return {
          status: "OK",
          confidence: 0.95,
          sourceTag: "Verified Field Lab Test",
          isOverridden: true,
          flags: [],
        };
      }
      return {
        status: "DEGRADED",
        confidence: 0.04,
        sourceTag: "Regional Soil Survey (Generic Baseline)",
        isOverridden: false,
        flags: ["Assumed Baseline (Generic Fallback)"],
      };
    }

    if (layerId === "L6") {
      if (params.L6.sourceMode === "calibrated") {
        return {
          status: "OK",
          confidence: 0.90,
          sourceTag: `Calibrated ${params.L6.cropType.toUpperCase()} Model`,
          isOverridden: true,
          flags: [],
        };
      }
      return {
        status: "DEGRADED",
        confidence: 0.45,
        sourceTag: "Uncalibrated Satellite Estimate",
        isOverridden: false,
        flags: ["Unknown Crop Stage", "Insufficient Field Support"],
      };
    }

    if (layerId === "L1" && params.L1.simulatedSensorActive) {
      return {
        status: "OK",
        confidence: 0.92,
        sourceTag: "In-Situ Sensor + Satellite Fusion",
        isOverridden: true,
        flags: [],
      };
    }

    if (layerId === "L2" && params.L2.cropStageOverride !== "auto") {
      return {
        status: "OK",
        confidence: 0.88,
        sourceTag: `ASMAE (${params.L2.cropStageOverride.toUpperCase()})`,
        isOverridden: true,
        flags: [],
      };
    }

    // Default passthrough
    const normStatus = (originalStatus === "OK" || originalStatus === "COMPLETED") ? "OK"
      : originalStatus === "DEGRADED" ? "DEGRADED"
      : originalStatus === "FAILED" ? "FAILED" : "SKIPPED";

    return {
      status: normStatus as any,
      confidence: normStatus === "OK" ? 0.85 : 0.40,
      sourceTag: "Canonical Stream",
      isOverridden: isLayerOverridden(layerId),
      flags: [],
    };
  }, [params, isLayerOverridden]);

  // Overall simulated pipeline metrics
  const simulation = useMemo(() => {
    const layerIds = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10"];
    let okCount = 0;
    let confSum = 0;

    for (const lid of layerIds) {
      // Base status for L4 & L6 is DEGRADED, others are OK
      const baseStatus = (lid === "L4" || lid === "L6") ? "DEGRADED" : "OK";
      const sim = getSimulatedLayerStatus(lid, baseStatus);
      if (sim.status === "OK") okCount++;
      confSum += sim.confidence;
    }

    const total = layerIds.length;
    const healthPercent = Math.round((okCount / total) * 100);
    const reliabilityPercent = Math.round((confSum / total) * 100);
    const degradedCount = total - okCount;

    return {
      healthPercent,
      reliabilityPercent,
      okCount,
      degradedCount,
      total,
      isFullyHealthy: degradedCount === 0,
    };
  }, [getSimulatedLayerStatus]);

  return {
    params,
    updateLayer,
    resetLayer,
    resetAll,
    isLayerOverridden,
    getSimulatedLayerStatus,
    simulation,
    activeDashboardLayer,
    setActiveDashboardLayer,
  };
}
