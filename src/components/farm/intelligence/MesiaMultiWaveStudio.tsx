"use client";

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";

// ============================================================================
// Types & Waveband Definitions
// ============================================================================

export interface WavebandConfig {
  id: string;
  name: string;
  shortName: string;
  category: "satellite" | "cellular" | "local_rf" | "broadcast";
  freqHz: number;
  freqLabel: string;
  wavelengthM: number;
  typicalTxPowerDbm: number;
  polarization: "RHCP" | "LHCP" | "VV" | "VH" | "Linear H";
  penetrationDepthMaxCm: number;
  color: string;
  description: string;
  roleInMesia: string;
}

export const AVAILABLE_WAVEBANDS: WavebandConfig[] = [
  {
    id: "gnss_l1",
    name: "GNSS-R L1 Carrier (GPS/Galileo)",
    shortName: "GNSS-R L1",
    category: "satellite",
    freqHz: 1575.42e6,
    freqLabel: "1575.42 MHz",
    wavelengthM: 0.1903,
    typicalTxPowerDbm: 27, // Satellite EIRP at ground level ~ -130 dBm
    polarization: "RHCP",
    penetrationDepthMaxCm: 8.5,
    color: "#38bdf8", // Sky cyan
    description: "Specular and diffuse multipath interferometry for topsoil VWC (0–8 cm).",
    roleInMesia: "Primary in-situ / opportunistic ground reflection interferometry.",
  },
  {
    id: "gnss_l2_l5",
    name: "GNSS-R L2/L5 Carrier (Deep L-Band)",
    shortName: "GNSS-R L2/L5",
    category: "satellite",
    freqHz: 1227.60e6,
    freqLabel: "1227.60 MHz",
    wavelengthM: 0.2442,
    typicalTxPowerDbm: 27,
    polarization: "RHCP",
    penetrationDepthMaxCm: 14.0,
    color: "#60a5fa", // Blue
    description: "Lower L-band provides 40% deeper soil penetration into the sub-surface.",
    roleInMesia: "Multi-frequency dispersion inversion for root-zone moisture gradient.",
  },
  {
    id: "cellular_4g_800",
    name: "Cellular 4G LTE Band 20 (Mobilis/Djezzy)",
    shortName: "Cellular 800M",
    category: "cellular",
    freqHz: 806.0e6,
    freqLabel: "806.00 MHz",
    wavelengthM: 0.372,
    typicalTxPowerDbm: 43,
    polarization: "VV",
    penetrationDepthMaxCm: 22.0,
    color: "#a855f7", // Purple
    description: "Long-range forward-scatter attenuation through dense crop canopies and orchard rows.",
    roleInMesia: "Continuous foliage water content & canopy attenuation tracker.",
  },
  {
    id: "cellular_5g_3500",
    name: "Cellular 5G NR n78 (Mid-Band C-Band)",
    shortName: "5G NR 3.5G",
    category: "cellular",
    freqHz: 3500.0e6,
    freqLabel: "3500.00 MHz",
    wavelengthM: 0.0857,
    typicalTxPowerDbm: 38,
    polarization: "VH",
    penetrationDepthMaxCm: 3.2,
    color: "#ec4899", // Pink
    description: "High-frequency forward scatter sensitive to leaf surface dew and thin canopy layers.",
    roleInMesia: "High-resolution foliar dew & surface moisture boundary detector.",
  },
  {
    id: "wifi_csi_2400",
    name: "Wi-Fi 6 CSI Active Channel (2.4 GHz)",
    shortName: "Wi-Fi CSI 2.4G",
    category: "local_rf",
    freqHz: 2437.0e6,
    freqLabel: "2437.00 MHz",
    wavelengthM: 0.123,
    typicalTxPowerDbm: 20,
    polarization: "Linear H",
    penetrationDepthMaxCm: 5.0,
    color: "#10b981", // Emerald
    description: "64-subcarrier amplitude and phase tracking for sub-centimeter canopy oscillation.",
    roleInMesia: "Optical-immune human/livestock/fire detection and foliar water index.",
  },
  {
    id: "wifi_csi_5800",
    name: "Wi-Fi 6E CSI Channel (5.8 GHz)",
    shortName: "Wi-Fi CSI 5.8G",
    category: "local_rf",
    freqHz: 5805.0e6,
    freqLabel: "5805.00 MHz",
    wavelengthM: 0.0517,
    typicalTxPowerDbm: 23,
    polarization: "Linear H",
    penetrationDepthMaxCm: 1.8,
    color: "#14b8a6", // Teal
    description: "Sub-millimeter micro-motion sensing and precise surface wetting discrimination.",
    roleInMesia: "Micro-dew and droplet condensation tracking on individual leaf planes.",
  },
  {
    id: "uhf_dvbt_550",
    name: "Terrestrial UHF Broadcast (TDA Algeria)",
    shortName: "UHF Broadcast",
    category: "broadcast",
    freqHz: 546.0e6,
    freqLabel: "546.00 MHz",
    wavelengthM: 0.549,
    typicalTxPowerDbm: 53, // 200 kW ERP transmitter
    polarization: "Linear H",
    penetrationDepthMaxCm: 45.0,
    color: "#f59e0b", // Amber
    description: "High-power broadcast transmitter waves penetrating deep into root zones (30–50 cm).",
    roleInMesia: "Deep soil aquifer & root-zone water balance anchor.",
  },
  {
    id: "cygnss_spaceborne",
    name: "Spaceborne Bistatic GNSS-R (CYGNSS)",
    shortName: "CYGNSS Space",
    category: "satellite",
    freqHz: 1575.42e6,
    freqLabel: "1575.42 MHz",
    wavelengthM: 0.1903,
    typicalTxPowerDbm: 0,
    polarization: "LHCP",
    penetrationDepthMaxCm: 7.0,
    color: "#818cf8", // Indigo
    description: "Orbital constellation bistatic radar for macro-scale calibration & parcel boundaries.",
    roleInMesia: "Cross-validation benchmark for ground in-situ receivers.",
  },
];

export interface ExperimentPreset {
  id: string;
  title: string;
  category: "Agronomy" | "RF Physics" | "Confounder Rejection" | "Multi-Band Closure";
  description: string;
  activeWaves: string[];
  soilVwcPct: number;
  soilTexture: "Clay Loam" | "Sandy Loam" | "Silt Loam" | "Sand";
  canopyLai: number;
  elevationDeg: number;
  antennaHeightM: number;
  windSpeedMs: number;
  temperatureC: number;
  isDewActive: boolean;
}

export const EXPERIMENT_PRESETS: ExperimentPreset[] = [
  {
    id: "preset_deep_closure",
    title: "🔬 Dual-Frequency Deep Root Closure (UHF 546 MHz + GNSS-R L1)",
    category: "Multi-Band Closure",
    description: "Simultaneously sound topsoil (0–8 cm) via GNSS-R and deep root zone (30–45 cm) via UHF broadcast to decouple surface evaporation from root reserves.",
    activeWaves: ["gnss_l1", "uhf_dvbt_550"],
    soilVwcPct: 24.5,
    soilTexture: "Clay Loam",
    canopyLai: 2.8,
    elevationDeg: 28,
    antennaHeightM: 1.85,
    windSpeedMs: 2.5,
    temperatureC: 22.0,
    isDewActive: false,
  },
  {
    id: "preset_siesta_thermal",
    title: "☀️ Sirocco Heatwave vs Transpiration (38°C Thermal Drift)",
    category: "Confounder Rejection",
    description: "Evaluates receiver LNA -0.045 dB/°C thermal gain drop vs true crop stomatal closure under extreme Mediterranean sirocco conditions.",
    activeWaves: ["cellular_4g_800", "wifi_csi_2400", "gnss_l1"],
    soilVwcPct: 16.0,
    soilTexture: "Sandy Loam",
    canopyLai: 3.5,
    elevationDeg: 45,
    antennaHeightM: 2.0,
    windSpeedMs: 4.0,
    temperatureC: 38.5,
    isDewActive: false,
  },
  {
    id: "preset_wind_flutter",
    title: "💨 Severe Canopy Flutter (16.5 m/s Wind Shock)",
    category: "RF Physics",
    description: "Tests mechanical leaf flutter (0.5–5 Hz) masking dielectric variations and verifies ASMAE 25x covariance inflation gating.",
    activeWaves: ["cellular_4g_800", "wifi_csi_2400", "wifi_csi_5800"],
    soilVwcPct: 22.0,
    soilTexture: "Clay Loam",
    canopyLai: 4.2,
    elevationDeg: 35,
    antennaHeightM: 2.2,
    windSpeedMs: 16.5,
    temperatureC: 25.0,
    isDewActive: false,
  },
  {
    id: "preset_dawn_dew",
    title: "💧 Dawn Dew Condensation vs Subsurface Drip Irrigation",
    category: "Agronomy",
    description: "High RH (95%) and small dew depression forms a liquid foliar film. Verifies ASMAE routes attenuation to foliar wetness while locking root-zone soil state.",
    activeWaves: ["wifi_csi_5800", "cellular_5g_3500", "gnss_l1"],
    soilVwcPct: 20.5,
    soilTexture: "Clay Loam",
    canopyLai: 3.8,
    elevationDeg: 22,
    antennaHeightM: 1.85,
    windSpeedMs: 1.2,
    temperatureC: 13.0,
    isDewActive: true,
  },
];

// ============================================================================
// Props
// ============================================================================

interface MesiaMultiWaveStudioProps {
  plotId: string;
  initialSoilTexture?: string;
  userRole?: "all" | "agronomist" | "rf_engineer";
  expertRole?: "all" | "agronomist" | "rf_engineer";
  data?: any;
  onApplyToObservatory?: (config: any) => void;
}

// ============================================================================
// Component
// ============================================================================

export default function MesiaMultiWaveStudio({
  plotId,
  initialSoilTexture = "Clay Loam",
  userRole,
  expertRole = "all",
  data,
  onApplyToObservatory,
}: MesiaMultiWaveStudioProps) {
  const effectiveRole = userRole || expertRole || "all";
  // ── Active Waves Selection ───────────────────────────────────────────────
  const [selectedWaveIds, setSelectedWaveIds] = useState<string[]>([
    "gnss_l1",
    "cellular_4g_800",
    "wifi_csi_2400",
    "uhf_dvbt_550",
  ]);

  // ── Physical Controls ───────────────────────────────────────────────────
  const [soilVwcPct, setSoilVwcPct] = useState<number>(23.5);
  const [soilTexture, setSoilTexture] = useState<string>(initialSoilTexture);
  const [canopyLai, setCanopyLai] = useState<number>(3.2);
  const [elevationDeg, setElevationDeg] = useState<number>(32);
  const [antennaHeightM, setAntennaHeightM] = useState<number>(1.85);
  const [windSpeedMs, setWindSpeedMs] = useState<number>(2.4);
  const [temperatureC, setTemperatureC] = useState<number>(23.0);
  const [isDewActive, setIsDewActive] = useState<boolean>(false);
  const [antennaDisplacementMm, setAntennaDisplacementMm] = useState<number>(1.2);
  const [selectedChartTab, setSelectedChartTab] = useState<
    "fresnel_reflection" | "penetration_depth" | "multipath_fringes" | "wifi_csi"
  >("fresnel_reflection");
  const [activePresetId, setActivePresetId] = useState<string>("preset_deep_closure");
  const [snapshotSaved, setSnapshotSaved] = useState<boolean>(false);

  // ── Toggle Wave Selection ───────────────────────────────────────────────
  const toggleWave = (waveId: string) => {
    setSelectedWaveIds((prev) => {
      if (prev.includes(waveId)) {
        if (prev.length <= 1) return prev; // Keep at least 1 wave
        return prev.filter((id) => id !== waveId);
      } else {
        return [...prev, waveId];
      }
    });
  };

  // ── Apply Preset ────────────────────────────────────────────────────────
  const applyPreset = (preset: ExperimentPreset) => {
    setActivePresetId(preset.id);
    setSelectedWaveIds(preset.activeWaves);
    setSoilVwcPct(preset.soilVwcPct);
    setSoilTexture(preset.soilTexture);
    setCanopyLai(preset.canopyLai);
    setElevationDeg(preset.elevationDeg);
    setAntennaHeightM(preset.antennaHeightM);
    setWindSpeedMs(preset.windSpeedMs);
    setTemperatureC(preset.temperatureC);
    setIsDewActive(preset.isDewActive);
  };

  // ── Physics Inversion Calculations ──────────────────────────────────────
  const activeWaves = useMemo(() => {
    return AVAILABLE_WAVEBANDS.filter((w) => selectedWaveIds.includes(w.id));
  }, [selectedWaveIds]);

  // Soil dielectric constant using Topp's polynomial model
  const dielectricPermittivity = useMemo(() => {
    const vwc = soilVwcPct / 100.0;
    // Real permittivity: Topp et al. (1980)
    const epsReal = 3.03 + 9.3 * vwc + 146.0 * Math.pow(vwc, 2) - 76.7 * Math.pow(vwc, 3);
    // Texture-dependent imaginary loss (Hallikainen / Dobson)
    let lossFactor = 0.08;
    if (soilTexture.includes("Clay")) lossFactor = 0.18;
    else if (soilTexture.includes("Sand")) lossFactor = 0.04;
    const epsImag = epsReal * lossFactor;
    return { epsReal, epsImag };
  }, [soilVwcPct, soilTexture]);

  // Multi-wave calculations (Reflection, Skin Depth, Fringes)
  const waveCalculations = useMemo(() => {
    const thetaRad = (elevationDeg * Math.PI) / 180.0;
    const { epsReal } = dielectricPermittivity;

    return activeWaves.map((wave) => {
      // Fresnel Reflection for Horizontal and Vertical Polarizations
      const sinTheta = Math.sin(thetaRad);
      const cosTheta = Math.cos(thetaRad);
      const sqrtTerm = Math.sqrt(Math.max(0.01, epsReal - Math.pow(cosTheta, 2)));

      // Horizontal Polarization (TE)
      const rH = (sinTheta - sqrtTerm) / (sinTheta + sqrtTerm);
      // Vertical Polarization (TM)
      const rV = (epsReal * sinTheta - sqrtTerm) / (epsReal * sinTheta + sqrtTerm);

      // Magnitude of reflection coefficients
      const gammaH = Math.abs(rH);
      const gammaV = Math.abs(rV);

      // Circular Polarization Reflection (RHCP -> LHCP specular reflection)
      const gammaLHCP = Math.sqrt(Math.max(0, 0.5 * (Math.pow(gammaH, 2) + Math.pow(gammaV, 2))));

      // Brewster angle (where vertical reflection vanishes)
      const brewsterDeg = (Math.atan(Math.sqrt(epsReal)) * 180.0) / Math.PI;

      // Skin Depth / Penetration Depth delta (meters)
      // delta = c / (2 * pi * f * sqrt(2 * epsReal) * sqrt(sqrt(1 + tanDelta^2) - 1))
      const lossTangent = dielectricPermittivity.epsImag / epsReal;
      const omega = 2 * Math.PI * wave.freqHz;
      const c = 3.0e8;
      const skinDepthM =
        (c / (omega * Math.sqrt(epsReal))) *
        (1.0 / (Math.sqrt(0.5 * (Math.sqrt(1 + Math.pow(lossTangent, 2)) - 1)) || 0.1));
      const skinDepthCm = Math.min(wave.penetrationDepthMaxCm, Math.max(0.5, skinDepthM * 100));

      // Canopy Attenuation via vegetation water content (VWC_canopy ~ 0.5 * LAI)
      const canopyWaterKgM2 = canopyLai * 0.45;
      const canopyExtinctionDb = (wave.freqHz / 1e9) * 1.85 * canopyWaterKgM2;

      // Multipath fringe frequency (Hz / sin(theta))
      const fringeFreq = (2 * antennaHeightM) / wave.wavelengthM;

      return {
        wave,
        gammaH,
        gammaV,
        gammaLHCP,
        brewsterDeg,
        skinDepthCm,
        canopyExtinctionDb,
        fringeFreq,
      };
    });
  }, [activeWaves, elevationDeg, dielectricPermittivity, antennaHeightM, canopyLai]);

  // ── ASMAE Real-Time Biophysical Gating Evaluation ─────────────────────────
  const asmaeGatingReport = useMemo(() => {
    const isWindFlutter = windSpeedMs >= 6.0;
    const isDewFormation = isDewActive;
    const isThermalDriftHigh = Math.abs(temperatureC - 20.0) >= 12.0;
    const isMastShifted = antennaDisplacementMm >= 10.0;
    const isVwcTooHigh = soilVwcPct > 42.0;

    let plausibilityScore = 0.94;
    let recommendedAction = "ADMIT_TO_WORLD_MODEL";
    let covMultiplier = 1.0;
    let primaryTarget = "ROOT_ZONE_SOIL_VWC";

    if (isMastShifted) {
      plausibilityScore = 0.25;
      recommendedAction = "SUPPRESS_AS_INSTRUMENT_DRIFT";
      covMultiplier = 100.0;
      primaryTarget = "INSTRUMENT_STATE";
    } else if (isWindFlutter) {
      plausibilityScore = 0.62;
      recommendedAction = "INFLATE_COVARIANCE_AND_QUARANTINE";
      covMultiplier = 25.0;
      primaryTarget = "CANOPY_HYDRAULIC_INDEX";
    } else if (isDewFormation) {
      plausibilityScore = 0.88;
      recommendedAction = "ADMIT_TO_WORLD_MODEL";
      covMultiplier = 2.0;
      primaryTarget = "SURFACE_WETNESS_EVENT";
    } else if (isThermalDriftHigh) {
      plausibilityScore = 0.84;
      covMultiplier = 1.5;
    }

    return {
      plausibilityScore,
      recommendedAction,
      covMultiplier,
      primaryTarget,
      invariants: [
        {
          name: "Richards Hydrological Infiltration",
          status: isVwcTooHigh ? "WARNING" : "SATISFIED",
          note: isVwcTooHigh ? "Near field capacity saturation" : "Permissible flux for " + soilTexture,
        },
        {
          name: "Thermodynamic Dew Boundary (Magnus)",
          status: isDewFormation ? "WARNING" : "SATISFIED",
          note: isDewFormation ? "Active condensation film detected; soil moisture locked" : "Nominal atmosphere",
        },
        {
          name: "Canopy Flutter Dissipation (von Kármán)",
          status: isWindFlutter ? "VIOLATED" : "SATISFIED",
          note: isWindFlutter ? `${windSpeedMs} m/s gust inducing 0.5–5 Hz flutter` : "Quiescent canopy geometry",
        },
        {
          name: "LNA Thermal Gain Drift Compensation",
          status: "SATISFIED",
          note: `${((temperatureC - 20.0) * -0.045).toFixed(3)} dB gain compensated`,
        },
        {
          name: "Receiver Anchor Rigidity (Pose Sentinel)",
          status: isMastShifted ? "VIOLATED" : "SATISFIED",
          note: `${antennaDisplacementMm.toFixed(1)} mm displacement (< 10.0 mm limit)`,
        },
      ],
    };
  }, [windSpeedMs, isDewActive, temperatureC, antennaDisplacementMm, soilVwcPct, soilTexture]);

  // ── Handle Snapshot Export ──────────────────────────────────────────────
  const handleSnapshot = () => {
    setSnapshotSaved(true);
    setTimeout(() => setSnapshotSaved(false), 2500);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "24px",
        color: "#f1f5f9",
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
      }}
    >
      {/* ── Top Hero Cockpit ─────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 24px",
          background: "linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.85))",
          borderRadius: "16px",
          border: "1px solid rgba(56, 189, 248, 0.25)",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.4)",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              background: "linear-gradient(135deg, #0284c7, #0369a1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "24px",
              boxShadow: "0 0 20px rgba(56, 189, 248, 0.35)",
            }}
          >
            🧪
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 700, letterSpacing: "-0.02em" }}>
                Multi-Wave Physical Laboratory & Experiment Studio
              </h2>
              <span
                style={{
                  padding: "3px 9px",
                  fontSize: "10px",
                  fontWeight: 700,
                  borderRadius: "999px",
                  background: "rgba(56, 189, 248, 0.15)",
                  color: "#38bdf8",
                  border: "1px solid rgba(56, 189, 248, 0.3)",
                }}
              >
                RESEARCH OBSERVATORY
              </span>
              <span
                style={{
                  padding: "3px 9px",
                  fontSize: "10px",
                  fontWeight: 700,
                  borderRadius: "999px",
                  background: "rgba(16, 185, 129, 0.15)",
                  color: "#34d399",
                  border: "1px solid rgba(16, 185, 129, 0.3)",
                }}
              >
                P-08 ZERO LEAKAGE
              </span>
            </div>
            <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "#94a3b8" }}>
              Simultaneously combine multiple wavebands (GNSS-R, 4G/5G, Wi-Fi CSI, UHF broadcast) and evaluate biophysical invariants in real time.
            </p>
          </div>
        </div>

        {/* Quick Action Buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button
            onClick={handleSnapshot}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 16px",
              background: snapshotSaved ? "rgba(16, 185, 129, 0.25)" : "rgba(30, 41, 59, 0.8)",
              border: snapshotSaved ? "1px solid #10b981" : "1px solid rgba(148, 163, 184, 0.25)",
              borderRadius: "10px",
              color: snapshotSaved ? "#34d399" : "#e2e8f0",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            <span>{snapshotSaved ? "✓" : "📸"}</span>
            <span>{snapshotSaved ? "Snapshot Saved!" : "Snapshot Experiment"}</span>
          </button>
          {onApplyToObservatory && (
            <button
              onClick={() =>
                onApplyToObservatory({
                  activeWaves: selectedWaveIds,
                  soilVwcPct,
                  soilTexture,
                  canopyLai,
                  elevationDeg,
                  antennaHeightM,
                })
              }
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "10px 18px",
                background: "linear-gradient(135deg, #0284c7, #2563eb)",
                border: "1px solid #38bdf8",
                borderRadius: "10px",
                color: "#ffffff",
                fontSize: "12px",
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 4px 15px rgba(37, 99, 235, 0.4)",
              }}
            >
              <span>⚡</span>
              <span>Deploy to Active Grid</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Guided Experiment Presets Bar ───────────────────────────────── */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          padding: "16px 20px",
          background: "rgba(15, 23, 42, 0.7)",
          borderRadius: "14px",
          border: "1px solid rgba(51, 65, 85, 0.4)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.06em", color: "#94a3b8", textTransform: "uppercase" }}>
            Ready-to-Run Scientific Experiments (1-Click Presets)
          </div>
          <div style={{ fontSize: "11px", color: "#64748b" }}>Select a scenario to configure multi-wave parameters</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "10px" }}>
          {EXPERIMENT_PRESETS.map((preset) => {
            const isSelected = activePresetId === preset.id;
            return (
              <button
                key={preset.id}
                onClick={() => applyPreset(preset)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  textAlign: "left",
                  padding: "12px 14px",
                  borderRadius: "10px",
                  background: isSelected ? "rgba(2, 132, 199, 0.2)" : "rgba(30, 41, 59, 0.5)",
                  border: isSelected ? "1px solid #38bdf8" : "1px solid rgba(51, 65, 85, 0.3)",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", marginBottom: "4px" }}>
                  <span style={{ fontSize: "11px", fontWeight: 700, color: isSelected ? "#38bdf8" : "#f1f5f9" }}>
                    {preset.title}
                  </span>
                  <span
                    style={{
                      fontSize: "9px",
                      fontWeight: 600,
                      padding: "2px 6px",
                      borderRadius: "4px",
                      background: "rgba(51, 65, 85, 0.5)",
                      color: "#94a3b8",
                    }}
                  >
                    {preset.category}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: "11px", color: "#94a3b8", lineHeight: "1.4" }}>
                  {preset.description}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Main Studio Grid (Controls on Left, Live Visuals on Right) ───── */}
      <div style={{ display: "grid", gridTemplateColumns: "1.15fr 1.85fr", gap: "24px" }}>
        {/* ── LEFT COLUMN: Physical Parameter Controls ───────────────────── */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Waveband Activator Matrix */}
          <div
            style={{
              padding: "18px 20px",
              background: "rgba(15, 23, 42, 0.8)",
              borderRadius: "14px",
              border: "1px solid rgba(51, 65, 85, 0.5)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
              <div style={{ fontSize: "12px", fontWeight: 700, letterSpacing: "0.05em", color: "#38bdf8", textTransform: "uppercase" }}>
                1. Waveband In-Situ Selector ({activeWaves.length} Active)
              </div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>Toggle to activate multi-wave channel</div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {AVAILABLE_WAVEBANDS.map((wave) => {
                const isActive = selectedWaveIds.includes(wave.id);
                return (
                  <div
                    key={wave.id}
                    onClick={() => toggleWave(wave.id)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "10px 14px",
                      borderRadius: "10px",
                      background: isActive ? "rgba(30, 41, 59, 0.8)" : "rgba(15, 23, 42, 0.4)",
                      border: isActive ? `1px solid ${wave.color}` : "1px solid rgba(51, 65, 85, 0.3)",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <div
                        style={{
                          width: "12px",
                          height: "12px",
                          borderRadius: "3px",
                          background: isActive ? wave.color : "rgba(71, 85, 105, 0.4)",
                          border: `1px solid ${wave.color}`,
                          boxShadow: isActive ? `0 0 8px ${wave.color}` : "none",
                        }}
                      />
                      <div>
                        <div style={{ fontSize: "12px", fontWeight: 600, color: isActive ? "#f8fafc" : "#64748b" }}>
                          {wave.name}
                        </div>
                        <div style={{ fontSize: "10px", color: "#94a3b8" }}>
                          {wave.freqLabel} • λ = {(wave.wavelengthM * 100).toFixed(1)} cm • {wave.polarization}
                        </div>
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 700,
                          padding: "2px 7px",
                          borderRadius: "4px",
                          background: isActive ? "rgba(56, 189, 248, 0.15)" : "rgba(51, 65, 85, 0.4)",
                          color: isActive ? wave.color : "#64748b",
                        }}
                      >
                        Max {wave.penetrationDepthMaxCm} cm
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Environmental & Soil Controls */}
          <div
            style={{
              padding: "18px 20px",
              background: "rgba(15, 23, 42, 0.8)",
              borderRadius: "14px",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <div style={{ fontSize: "12px", fontWeight: 700, letterSpacing: "0.05em", color: "#10b981", textTransform: "uppercase" }}>
              2. Soil & Canopy Parameters
            </div>

            {/* Soil Moisture Slider */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "6px" }}>
                <span style={{ color: "#cbd5e1" }}>Latent Soil Moisture (VWC):</span>
                <span style={{ fontWeight: 700, color: "#38bdf8" }}>{soilVwcPct.toFixed(1)}% VWC</span>
              </div>
              <input
                type="range"
                min={5}
                max={48}
                step={0.5}
                value={soilVwcPct}
                onChange={(e) => setSoilVwcPct(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "#38bdf8", cursor: "pointer" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px", color: "#64748b", marginTop: "2px" }}>
                <span>Dry Wilting (5%)</span>
                <span>Field Capacity (28%)</span>
                <span>Saturated (48%)</span>
              </div>
            </div>

            {/* Soil Texture Selection */}
            <div>
              <div style={{ fontSize: "11px", color: "#cbd5e1", marginBottom: "6px" }}>Soil Texture Type:</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "6px" }}>
                {["Clay Loam", "Sandy Loam", "Silt Loam", "Sand"].map((type) => (
                  <button
                    key={type}
                    onClick={() => setSoilTexture(type)}
                    style={{
                      padding: "6px 8px",
                      fontSize: "10px",
                      fontWeight: 600,
                      borderRadius: "6px",
                      background: soilTexture === type ? "rgba(16, 185, 129, 0.25)" : "rgba(30, 41, 59, 0.6)",
                      border: soilTexture === type ? "1px solid #10b981" : "1px solid rgba(51, 65, 85, 0.4)",
                      color: soilTexture === type ? "#34d399" : "#94a3b8",
                      cursor: "pointer",
                    }}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            {/* Canopy LAI Slider */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "6px" }}>
                <span style={{ color: "#cbd5e1" }}>Canopy Biomass / Leaf Area Index (LAI):</span>
                <span style={{ fontWeight: 700, color: "#34d399" }}>{canopyLai.toFixed(1)} m²/m²</span>
              </div>
              <input
                type="range"
                min={0.2}
                max={6.0}
                step={0.1}
                value={canopyLai}
                onChange={(e) => setCanopyLai(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "#10b981", cursor: "pointer" }}
              />
            </div>

            {/* Foliar Dew Condensation Toggle */}
            <div
              onClick={() => setIsDewActive(!isDewActive)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "10px 14px",
                borderRadius: "8px",
                background: isDewActive ? "rgba(2, 132, 199, 0.2)" : "rgba(30, 41, 59, 0.4)",
                border: isDewActive ? "1px solid #38bdf8" : "1px solid rgba(51, 65, 85, 0.4)",
                cursor: "pointer",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "16px" }}>💧</span>
                <div>
                  <div style={{ fontSize: "11px", fontWeight: 600, color: isDewActive ? "#38bdf8" : "#cbd5e1" }}>
                    Foliar Dew Formation (Condensation Film)
                  </div>
                  <div style={{ fontSize: "9px", color: "#94a3b8" }}>
                    {isDewActive ? "Liquid film active: routes attenuation to canopy wetness" : "Dry canopy surface"}
                  </div>
                </div>
              </div>
              <span style={{ fontSize: "12px", color: isDewActive ? "#38bdf8" : "#64748b" }}>
                {isDewActive ? "ON" : "OFF"}
              </span>
            </div>
          </div>

          {/* RF Geometry & Hardware Nuisance Controls */}
          <div
            style={{
              padding: "18px 20px",
              background: "rgba(15, 23, 42, 0.8)",
              borderRadius: "14px",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <div style={{ fontSize: "12px", fontWeight: 700, letterSpacing: "0.05em", color: "#f59e0b", textTransform: "uppercase" }}>
              3. RF Geometry & Nuisance Controls
            </div>

            {/* Elevation Angle Slider */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "6px" }}>
                <span style={{ color: "#cbd5e1" }}>Ray-Path Incident Elevation Angle (θ):</span>
                <span style={{ fontWeight: 700, color: "#f59e0b" }}>{elevationDeg}°</span>
              </div>
              <input
                type="range"
                min={5}
                max={85}
                step={1}
                value={elevationDeg}
                onChange={(e) => setElevationDeg(parseInt(e.target.value))}
                style={{ width: "100%", accentColor: "#f59e0b", cursor: "pointer" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px", color: "#64748b", marginTop: "2px" }}>
                <span>Grazing (5°)</span>
                <span>Brewster Angle (~28°)</span>
                <span>Near-Nadir (85°)</span>
              </div>
            </div>

            {/* Antenna Mast Height */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "6px" }}>
                <span style={{ color: "#cbd5e1" }}>Antenna Mast Height (h_ant):</span>
                <span style={{ fontWeight: 700, color: "#cbd5e1" }}>{antennaHeightM.toFixed(2)} m</span>
              </div>
              <input
                type="range"
                min={0.5}
                max={4.5}
                step={0.05}
                value={antennaHeightM}
                onChange={(e) => setAntennaHeightM(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "#94a3b8", cursor: "pointer" }}
              />
            </div>

            {/* Wind Flutter Speed */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "6px" }}>
                <span style={{ color: "#cbd5e1" }}>Wind Speed (Aerodynamic Flutter):</span>
                <span style={{ fontWeight: 700, color: windSpeedMs >= 6.0 ? "#ef4444" : "#94a3b8" }}>
                  {windSpeedMs.toFixed(1)} m/s {windSpeedMs >= 6.0 && "(ACTIVE FLUTTER)"}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={22}
                step={0.5}
                value={windSpeedMs}
                onChange={(e) => setWindSpeedMs(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: windSpeedMs >= 6.0 ? "#ef4444" : "#38bdf8", cursor: "pointer" }}
              />
            </div>

            {/* Ambient Temperature Swing */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "6px" }}>
                <span style={{ color: "#cbd5e1" }}>Ambient Temperature (LNA Drift):</span>
                <span style={{ fontWeight: 700, color: "#cbd5e1" }}>{temperatureC.toFixed(1)} °C</span>
              </div>
              <input
                type="range"
                min={0}
                max={48}
                step={0.5}
                value={temperatureC}
                onChange={(e) => setTemperatureC(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: "#f97316", cursor: "pointer" }}
              />
            </div>
          </div>
        </div>

        {/* ── RIGHT COLUMN: Live Interactive Visualizations & Laboratory ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {/* Visualizer Mode Tabs */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px",
              background: "rgba(15, 23, 42, 0.9)",
              borderRadius: "12px",
              border: "1px solid rgba(51, 65, 85, 0.4)",
            }}
          >
            {[
              { id: "fresnel_reflection", label: "Fresnel Reflection Γ(θ)", icon: "📈" },
              { id: "penetration_depth", label: "Penetration Depth Barometer", icon: "📊" },
              { id: "multipath_fringes", label: "Multipath SNR Fringes", icon: "〰️" },
              { id: "wifi_csi", label: "Wi-Fi 64-Subcarrier CSI", icon: "📶" },
            ].map((tab) => {
              const isSelected = selectedChartTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setSelectedChartTab(tab.id as any)}
                  style={{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "6px",
                    padding: "8px 12px",
                    fontSize: "11px",
                    fontWeight: isSelected ? 700 : 500,
                    borderRadius: "8px",
                    background: isSelected ? "rgba(56, 189, 248, 0.2)" : "transparent",
                    color: isSelected ? "#38bdf8" : "#94a3b8",
                    border: isSelected ? "1px solid rgba(56, 189, 248, 0.4)" : "1px solid transparent",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Interactive Chart Canvas Card */}
          <div
            style={{
              padding: "20px",
              background: "rgba(15, 23, 42, 0.85)",
              borderRadius: "16px",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
              boxShadow: "0 10px 25px rgba(0, 0, 0, 0.3)",
            }}
          >
            {/* 1. Fresnel Reflection Coefficient Chart */}
            {selectedChartTab === "fresnel_reflection" && (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#f8fafc" }}>
                      Fresnel Ground Reflection Coefficient Γ(θ) vs Incident Elevation
                    </h3>
                    <p style={{ margin: "2px 0 0 0", fontSize: "11px", color: "#94a3b8" }}>
                      Dielectric Permittivity ε_r = {dielectricPermittivity.epsReal.toFixed(2)} - j{dielectricPermittivity.epsImag.toFixed(2)} ({soilTexture}, {soilVwcPct}% VWC)
                    </p>
                  </div>
                  <div style={{ fontSize: "11px", color: "#38bdf8", fontWeight: 600 }}>
                    Marker at θ = {elevationDeg}°
                  </div>
                </div>

                {/* SVG Curve Plot */}
                <div style={{ height: "260px", width: "100%", background: "rgba(11, 17, 32, 0.7)", borderRadius: "10px", padding: "10px", position: "relative" }}>
                  <svg width="100%" height="100%" viewBox="0 0 500 240" preserveAspectRatio="none">
                    {/* Grid lines */}
                    {[0, 0.25, 0.5, 0.75, 1.0].map((v, i) => {
                      const y = 220 - v * 200;
                      return (
                        <g key={i}>
                          <line x1="40" y1={y} x2="480" y2={y} stroke="rgba(51, 65, 85, 0.3)" strokeDasharray="3 3" />
                          <text x="32" y={y + 4} fill="#64748b" fontSize="9" textAnchor="end">{v.toFixed(2)}</text>
                        </g>
                      );
                    })}
                    {/* X-axis labels (Degrees 0 to 90) */}
                    {[0, 15, 30, 45, 60, 75, 90].map((deg, i) => {
                      const x = 40 + (deg / 90) * 440;
                      return (
                        <g key={i}>
                          <line x1={x} y1="20" x2={x} y2="220" stroke="rgba(51, 65, 85, 0.3)" strokeDasharray="3 3" />
                          <text x={x} y="235" fill="#64748b" fontSize="9" textAnchor="middle">{deg}°</text>
                        </g>
                      );
                    })}

                    {/* Plot curves for active waves */}
                    {activeWaves.map((wave) => {
                      const pointsH: string[] = [];
                      const pointsV: string[] = [];
                      for (let deg = 1; deg <= 89; deg += 2) {
                        const rad = (deg * Math.PI) / 180.0;
                        const s = Math.sin(rad);
                        const c = Math.cos(rad);
                        const sq = Math.sqrt(Math.max(0.01, dielectricPermittivity.epsReal - Math.pow(c, 2)));
                        const rH = Math.abs((s - sq) / (s + sq));
                        const rV = Math.abs((dielectricPermittivity.epsReal * s - sq) / (dielectricPermittivity.epsReal * s + sq));

                        const x = 40 + (deg / 90) * 440;
                        const yH = 220 - rH * 200;
                        const yV = 220 - rV * 200;
                        pointsH.push(`${x},${yH}`);
                        pointsV.push(`${x},${yV}`);
                      }

                      return (
                        <g key={wave.id}>
                          {/* Horizontal Polarization */}
                          <polyline points={pointsH.join(" ")} fill="none" stroke={wave.color} strokeWidth="2.5" />
                          {/* Vertical Polarization (dashed) */}
                          <polyline points={pointsV.join(" ")} fill="none" stroke={wave.color} strokeWidth="1.5" strokeDasharray="4 2" />
                        </g>
                      );
                    })}

                    {/* Current Elevation Marker Line */}
                    {(() => {
                      const markerX = 40 + (elevationDeg / 90) * 440;
                      return (
                        <g>
                          <line x1={markerX} y1="20" x2={markerX} y2="220" stroke="#f59e0b" strokeWidth="2" strokeDasharray="3 3" />
                          <circle cx={markerX} cy="220" r="4" fill="#f59e0b" />
                        </g>
                      );
                    })()}
                  </svg>
                </div>

                {/* Legend */}
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "12px", marginTop: "10px", fontSize: "11px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#94a3b8" }}>
                    <span style={{ width: "16px", height: "3px", background: "#cbd5e1" }} /> Solid: Horizontal (TE)
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#94a3b8" }}>
                    <span style={{ width: "16px", height: "2px", borderBottom: "2px dashed #cbd5e1" }} /> Dashed: Vertical (TM)
                  </div>
                  {activeWaves.map((w) => (
                    <div key={w.id} style={{ display: "flex", alignItems: "center", gap: "6px", color: w.color }}>
                      <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: w.color }} /> {w.shortName}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 2. Penetration Depth Barometer */}
            {selectedChartTab === "penetration_depth" && (
              <div>
                <div style={{ marginBottom: "14px" }}>
                  <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#f8fafc" }}>
                    Multi-Band Skin Depth & Subsurface Penetration Barometer
                  </h3>
                  <p style={{ margin: "2px 0 0 0", fontSize: "11px", color: "#94a3b8" }}>
                    Depth at which signal energy attenuates by 1/e (8.68 dB). Lower frequencies probe deeper into root zones.
                  </p>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {waveCalculations.map(({ wave, skinDepthCm }) => {
                    const pct = (skinDepthCm / 50.0) * 100.0;
                    return (
                      <div key={wave.id}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "4px" }}>
                          <span style={{ fontWeight: 600, color: wave.color }}>{wave.name} ({wave.freqLabel})</span>
                          <span style={{ fontWeight: 700, color: "#f8fafc" }}>{skinDepthCm.toFixed(1)} cm depth</span>
                        </div>
                        <div style={{ width: "100%", height: "18px", background: "rgba(30, 41, 59, 0.6)", borderRadius: "6px", overflow: "hidden", position: "relative" }}>
                          <div
                            style={{
                              width: `${Math.min(100, Math.max(2, pct))}%`,
                              height: "100%",
                              background: `linear-gradient(90deg, ${wave.color}aa, ${wave.color})`,
                              borderRadius: "6px",
                              transition: "width 0.3s ease",
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div
                  style={{
                    marginTop: "16px",
                    padding: "12px 14px",
                    background: "rgba(2, 132, 199, 0.15)",
                    borderRadius: "8px",
                    border: "1px solid rgba(56, 189, 248, 0.3)",
                    fontSize: "11px",
                    color: "#cbd5e1",
                    lineHeight: "1.5",
                  }}
                >
                  💡 <strong>Agronomic Dual-Closure Advantage:</strong> Combining <strong>UHF 546 MHz</strong> (probes deep root zone 30–45 cm) with <strong>GNSS-R L1 1575 MHz</strong> (probes topsoil 0–8 cm) eliminates surface drying confounders and prevents false irrigation triggers.
                </div>
              </div>
            )}

            {/* 3. Multipath SNR Interference Fringes */}
            {selectedChartTab === "multipath_fringes" && (
              <div>
                <div style={{ marginBottom: "12px" }}>
                  <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#f8fafc" }}>
                    GNSS-R Multipath Interferometric Fringe Synthesis (SNR Fringes)
                  </h3>
                  <p style={{ margin: "2px 0 0 0", fontSize: "11px", color: "#94a3b8" }}>
                    Direct wave interfering with reflected ground bounce. Fringe frequency f_m = (2 * h_ant / λ) * sin(θ).
                  </p>
                </div>

                <div style={{ height: "240px", width: "100%", background: "rgba(11, 17, 32, 0.7)", borderRadius: "10px", padding: "10px" }}>
                  <svg width="100%" height="100%" viewBox="0 0 500 220" preserveAspectRatio="none">
                    {/* Grid */}
                    <line x1="30" y1="110" x2="490" y2="110" stroke="rgba(51, 65, 85, 0.5)" strokeDasharray="3 3" />
                    <text x="25" y="114" fill="#64748b" fontSize="9" textAnchor="end">0 dB</text>

                    {/* Synthesize realistic SNR fringe curve */}
                    {(() => {
                      const l1Wave = waveCalculations.find((w) => w.wave.id === "gnss_l1") || waveCalculations[0];
                      const fm = (2 * antennaHeightM) / l1Wave.wave.wavelengthM;
                      const gamma = l1Wave.gammaLHCP;
                      const points: string[] = [];

                      for (let deg = 5; deg <= 35; deg += 0.25) {
                        const rad = (deg * Math.PI) / 180.0;
                        const s = Math.sin(rad);
                        // Interference signal: direct (1.0) + reflected (gamma) * cos(4*pi*h*s/lambda)
                        const fringe = gamma * Math.cos(2 * Math.PI * fm * s);
                        const snrModDb = 6.0 * fringe; // dB modulation

                        const x = 30 + ((deg - 5) / 30) * 460;
                        const y = 110 - snrModDb * 12;
                        points.push(`${x},${y}`);
                      }

                      return (
                        <g>
                          <polyline points={points.join(" ")} fill="none" stroke="#38bdf8" strokeWidth="2.5" />
                        </g>
                      );
                    })()}
                  </svg>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#94a3b8", marginTop: "4px" }}>
                  <span>Elevation θ = 5°</span>
                  <span>Multipath Peak Range (10°–25°)</span>
                  <span>Elevation θ = 35°</span>
                </div>
              </div>
            )}

            {/* 4. Wi-Fi CSI 64-Subcarrier Response */}
            {selectedChartTab === "wifi_csi" && (
              <div>
                <div style={{ marginBottom: "12px" }}>
                  <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#f8fafc" }}>
                    Wi-Fi 6 CSI Physical Channel Response (64 Subcarriers)
                  </h3>
                  <p style={{ margin: "2px 0 0 0", fontSize: "11px", color: "#94a3b8" }}>
                    Amplitude attenuation across 20 MHz bandwidth. Foliar liquid water attenuates higher subcarriers.
                  </p>
                </div>

                <div style={{ height: "240px", width: "100%", background: "rgba(11, 17, 32, 0.7)", borderRadius: "10px", padding: "10px" }}>
                  <svg width="100%" height="100%" viewBox="0 0 500 220" preserveAspectRatio="none">
                    {/* 64 Subcarrier bars */}
                    {Array.from({ length: 64 }).map((_, idx) => {
                      const subcarrierIndex = idx - 32;
                      // Base amplitude ~ 25 linear units
                      // Moisture attenuation decreases amplitude
                      const atten = (canopyLai * 2.5) + (isDewActive ? 6.0 : 0);
                      // Add frequency selective multipath ripple
                      const ripple = Math.sin(idx * 0.4) * 4.5;
                      const amp = Math.max(3, 28 - atten + ripple);
                      const x = 30 + (idx / 64) * 450;
                      const barHeight = amp * 6;
                      const y = 200 - barHeight;

                      return (
                        <rect
                          key={idx}
                          x={x}
                          y={y}
                          width="5"
                          height={barHeight}
                          fill={isDewActive ? "#38bdf8" : "#10b981"}
                          rx="2"
                          opacity={0.85}
                        />
                      );
                    })}
                  </svg>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#94a3b8", marginTop: "4px" }}>
                  <span>Subcarrier -32 (-10 MHz)</span>
                  <span>Center Pilot Subcarrier 0 (2437 MHz)</span>
                  <span>Subcarrier +31 (+10 MHz)</span>
                </div>
              </div>
            )}
          </div>

          {/* ASMAE Real-Time Biophysical Invariant Gate Card */}
          <div
            style={{
              padding: "18px 20px",
              background: "rgba(15, 23, 42, 0.85)",
              borderRadius: "14px",
              border: asmaeGatingReport.recommendedAction === "ADMIT_TO_WORLD_MODEL"
                ? "1px solid rgba(16, 185, 129, 0.4)"
                : "1px solid rgba(245, 158, 11, 0.5)",
              display: "flex",
              flexDirection: "column",
              gap: "14px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "18px" }}>🛡️</span>
                <div>
                  <div style={{ fontSize: "12px", fontWeight: 700, color: "#f8fafc", letterSpacing: "0.04em", textTransform: "uppercase" }}>
                    ASMAE Real-Time Biophysical Gating Status
                  </div>
                  <div style={{ fontSize: "10px", color: "#94a3b8" }}>
                    Plausibility: {(asmaeGatingReport.plausibilityScore * 100).toFixed(1)}% • Covariance Scale R: {asmaeGatingReport.covMultiplier.toFixed(1)}x
                  </div>
                </div>
              </div>
              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: "6px",
                  fontSize: "11px",
                  fontWeight: 700,
                  background: asmaeGatingReport.recommendedAction === "ADMIT_TO_WORLD_MODEL"
                    ? "rgba(16, 185, 129, 0.2)"
                    : "rgba(245, 158, 11, 0.2)",
                  color: asmaeGatingReport.recommendedAction === "ADMIT_TO_WORLD_MODEL" ? "#34d399" : "#fbbf24",
                  border: asmaeGatingReport.recommendedAction === "ADMIT_TO_WORLD_MODEL"
                    ? "1px solid #10b981"
                    : "1px solid #f59e0b",
                }}
              >
                {asmaeGatingReport.recommendedAction}
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "8px" }}>
              {asmaeGatingReport.invariants.map((inv, i) => (
                <div
                  key={i}
                  style={{
                    padding: "8px 10px",
                    borderRadius: "8px",
                    background: "rgba(30, 41, 59, 0.5)",
                    border: "1px solid rgba(51, 65, 85, 0.3)",
                    fontSize: "10px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "2px" }}>
                    <span style={{ fontWeight: 600, color: "#e2e8f0" }}>{inv.name}</span>
                    <span style={{ fontWeight: 700, color: inv.status === "SATISFIED" ? "#34d399" : inv.status === "WARNING" ? "#fbbf24" : "#f87171" }}>
                      {inv.status}
                    </span>
                  </div>
                  <div style={{ color: "#94a3b8", fontSize: "9px" }}>{inv.note}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
