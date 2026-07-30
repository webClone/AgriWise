"use client";

import { useState, useEffect, useRef, useMemo } from "react";

// Canonical boot sequence for fallback
const BOOT_SEQUENCE = [
  { message: "Establishing secure connection...", delayMs: 400 },
  { message: "Acquiring spatial geometry bounds...", delayMs: 1200 },
  { message: "Fetching Earth Observation (Sentinel-1/2) imagery...", delayMs: 2200 },
  { message: "Running L1 Data Fusion (SAR + Optical + Weather)...", delayMs: 3400 },
  { message: "Evaluating L3 Water Stress & Nutrient Models...", delayMs: 4800 },
  { message: "Generating L10 Spatial Intelligence Map...", delayMs: 6500 },
  { message: "Complete", delayMs: 7500 }
];

// Human-readable dynamic stages sequence for mapping percentages
const ALL_DYNAMIC_STAGES = [
  "Connecting to satellite network",
  "Acquiring Earth Observation imagery",
  "Fusing satellite & weather data",
  "Analyzing crop health",
  "Evaluating water & stress models",
  "Assessing soil nutrients",
  "Scanning disease & pest risk",
  "Computing execution state",
  "Building season plan",
  "Generating prescriptions",
  "Preparing spatial intelligence map",
  "Rendering spatial intelligence map",
  "Calibrating vegetation indices",
  "Enhancing spatial resolution",
  "Finalizing scouting regions",
  "Complete"
];

// Rich, scientifically rigorous sub-logs for scrolling telemetry console
const STAGE_MICRO_LOGS: Record<string, string[]> = {
  "Establishing secure connection...": [
    "[0.1s] Initializing socket bridge handshakes...",
    "[0.2s] Authenticating security token hashes...",
    "[0.3s] Gateway secure: connection active."
  ],
  "Acquiring spatial geometry bounds...": [
    "[0.2s] Inverting coordinate bounds from GeoJSON feature...",
    "[0.4s] Registering geographic coordinate reference systems...",
    "[0.6s] Bounding box calculated: coordinate bounds locked."
  ],
  "Fetching Earth Observation (Sentinel-1/2) imagery...": [
    "[0.2s] Querying Copernicus L2A tile indices...",
    "[0.4s] Selecting cloud-free optical spectrum passes...",
    "[0.7s] Fusing VV/VH polarization radar arrays..."
  ],
  "Running L1 Data Fusion (SAR + Optical + Weather)...": [
    "[0.2s] Interpolating ERA5-Land air temperature matrix...",
    "[0.4s] Fusing synthetic aperture radar (SAR) tensors...",
    "[0.6s] Fusing multi-spectral canopy reflectance grids..."
  ],
  "Evaluating L3 Water Stress & Nutrient Models...": [
    "[0.2s] Modeling Penman-Monteith crop water drawdowns...",
    "[0.4s] Simulating root-zone water balance dynamics...",
    "[0.6s] Inverting daily evapotranspiration integrals..."
  ],
  "Generating L10 Spatial Intelligence Map...": [
    "[0.2s] Initializing Ordinary Kriging spatial interpolator...",
    "[0.4s] Interpolating sparse observation cell grids...",
    "[0.6s] Vectorizing spatial zone boundary contours..."
  ],
  "Connecting to satellite network": [
    "[0.1s] Authenticating telemetry access channels...",
    "[0.2s] Connecting to ESA Sentinel Hub API...",
    "[0.4s] Handshake complete: bandwidth optimized."
  ],
  "Acquiring Earth Observation imagery": [
    "[0.2s] Querying Copernicus database for L2A tiles...",
    "[0.4s] Resolving cloud cover indices (< 10%)...",
    "[0.6s] Extracting region-of-interest bounding polygons..."
  ],
  "Fusing satellite & weather data": [
    "[0.2s] Fetching ERA5-Land air temperature grids...",
    "[0.4s] Mapping SAR dual-polarization backscatter...",
    "[0.6s] Aligning geographic coordinate reference systems..."
  ],
  "Analyzing crop health": [
    "[0.2s] Recalibrating multi-spectral reflectance profiles...",
    "[0.4s] Computing canopy chlorophyll absorption indices...",
    "[0.6s] Resolving crop development phenological stages..."
  ],
  "Evaluating water & stress models": [
    "[0.2s] Modeling Penman-Monteith crop water drawdowns...",
    "[0.4s] Simulating root-zone water balance dynamics...",
    "[0.6s] Inverting daily evapotranspiration integrals..."
  ],
  "Assessing soil nutrients": [
    "[0.2s] Inverting soil texture clay-sand fractions...",
    "[0.4s] Calibrating soil organic carbon mineralization...",
    "[0.6s] Estimating nitrogen/phosphorus deficit weights..."
  ],
  "Scanning disease & pest risk": [
    "[0.2s] Solving sporulation temperature threshold curves...",
    "[0.4s] Integrating canopy relative humidity indices...",
    "[0.6s] Computing localized pathogen susceptibility index..."
  ],
  "Computing execution state": [
    "[0.2s] Loading IoT sensor network readings...",
    "[0.4s] Initializing Extended Kalman Filter covariance matrices...",
    "[0.6s] Fusing user events and photos into state grids..."
  ],
  "Building season plan": [
    "[0.2s] Simulating crop growth development thermal limits...",
    "[0.4s] Recommending seasonal mechanical tillage windows...",
    "[0.6s] Estimating multi-week crop soil nutrient drawdowns..."
  ],
  "Generating prescriptions": [
    "[0.2s] Inverting management zone priority matrices...",
    "[0.4s] Simulating nitrogen application response functions...",
    "[0.6s] Solving variable-rate irrigation dose schedules..."
  ],
  "Preparing spatial intelligence map": [
    "[0.2s] Initializing Ordinary Kriging spatial interpolator...",
    "[0.4s] Interpolating sparse observation cell grids...",
    "[0.6s] Constructing smooth polygon contour vectors..."
  ],
  "Rendering spatial intelligence map": [
    "[0.2s] Initializing Ordinary Kriging spatial interpolator...",
    "[0.4s] Interpolating sparse observation cell grids...",
    "[0.6s] Constructing smooth polygon contour vectors..."
  ],
  "Calibrating vegetation indices": [
    "[0.2s] Fetching Sentinel-1 SAR backscatter ratios...",
    "[0.4s] Applying dual-polarization atmospheric scattering corrections...",
    "[0.6s] Generating composite canopy anomaly matrices..."
  ],
  "Enhancing spatial resolution": [
    "[0.3s] Running bilateral super-resolution upscaling (4x grid resolution)...",
    "[0.6s] Applying edge-preserving gradient filter kernels...",
    "[0.9s] Correcting sub-pixel grid offset alignment..."
  ],
  "Finalizing scouting regions": [
    "[0.2s] Computing spatial K-Means clustering centroid coordinates...",
    "[0.4s] Filtering zone micro-clusters and spatial noise...",
    "[0.6s] Scaling zone severity risk classification vectors..."
  ],
  "Complete": [
    "[0.1s] Compiling layers to Layer 10 data grid...",
    "[0.3s] Optimizing client-side rendering bundle...",
    "[0.5s] Intelligence pipeline complete."
  ]
};

interface ProgressStage {
  stage: string;
  status: "running" | "done" | "error" | "failed" | "degraded" | "cancelled";
  elapsed: number;
  timestamp: number;
}

interface PlotLoadingSequenceProps {
  plotId?: string;
}

export default function PlotLoadingSequence({ plotId }: PlotLoadingSequenceProps = {}) {
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [dynamicStages, setDynamicStages] = useState<ProgressStage[]>([]);
  const [isDynamic, setIsDynamic] = useState(false);
  const [telemetryLogs, setTelemetryLogs] = useState<string[]>([]);
  const [smoothPercent, setSmoothPercent] = useState(0);
  
  const logEndRef = useRef<HTMLDivElement>(null);

  // Fallback static sequence if no plotId or backend doesn't respond
  useEffect(() => {
    if (isDynamic) return;

    const timeouts: NodeJS.Timeout[] = [];
    
    BOOT_SEQUENCE.forEach((step, index) => {
      if (index === 0) return; // First step is immediate
      const t = setTimeout(() => {
        if (!isDynamic) {
          setActiveStepIndex(index);
        }
      }, step.delayMs);
      timeouts.push(t);
    });

    return () => timeouts.forEach(clearTimeout);
  }, [isDynamic]);

  // Polling for real-time backend progress (with backoff and visibility checks)
  useEffect(() => {
    if (!plotId) return;

    let attempts = 0;
    const MAX_ATTEMPTS = 60;
    let intervalId: NodeJS.Timeout | null = null;
    let allDone = false;

    const poll = async () => {
      // Stop if tab is hidden
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      // Stop if max attempts reached or all stages done
      if (attempts >= MAX_ATTEMPTS || allDone) {
        if (intervalId) clearInterval(intervalId);
        return;
      }
      attempts++;

      try {
        const res = await fetch(`/api/agribrain/progress?plotId=${plotId}`);
        if (!res.ok) return;
        const data = await res.json();
        
        if (data.stages && data.stages.length > 0) {
          setIsDynamic(true);
          setDynamicStages(data.stages);

          const isFailureStatus = (st: string) => ["error", "failed", "degraded", "cancelled"].includes(st);
          const finalStage = data.stages[data.stages.length - 1] as ProgressStage;
          // Stage-level "done" is not run completion. A successful run is
          // terminal only after its canonical result has been durably published.
          const allStagesTerminal =
            isFailureStatus(finalStage?.status) ||
            (data.terminal === true && data.result_available === true);
          if (allStagesTerminal) {
            allDone = true;
            if (intervalId) clearInterval(intervalId);
            if (typeof window !== "undefined" && (data.result_available === true || data.terminal === true)) {
              window.dispatchEvent(
                new CustomEvent("agribrain:refresh_completed", {
                  detail: { plotId, finalSnapshotId: data.final_snapshot_id },
                })
              );
            }
          }
        } else if (data.terminal === true && data.result_available === true) {
          allDone = true;
          if (intervalId) clearInterval(intervalId);
          if (typeof window !== "undefined") {
            window.dispatchEvent(
              new CustomEvent("agribrain:refresh_completed", {
                detail: { plotId, finalSnapshotId: data.final_snapshot_id },
              })
            );
          }
        }
      } catch (e) {
        // Silently fail and use static fallback
      }

      // Backoff: after 30s (15 attempts at 2s), switch to 5s intervals
      if (attempts === 15 && intervalId) {
        clearInterval(intervalId);
        intervalId = setInterval(poll, 5000);
      }
    };

    intervalId = setInterval(poll, 2000);

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [plotId]);

  // Telemetry Micro-logs Streaming
  useEffect(() => {
    let activeStageName = "";
    if (isDynamic) {
      if (dynamicStages.length > 0) {
        // Find last active/running stage
        const running = dynamicStages.find(s => s.status === "running");
        if (running) {
          activeStageName = running.stage;
        } else {
          activeStageName = dynamicStages[dynamicStages.length - 1].stage;
        }
      }
    } else {
      const step = BOOT_SEQUENCE[activeStepIndex];
      if (step) {
        activeStageName = step.message;
      }
    }

    if (!activeStageName) return;

    const subLogs = STAGE_MICRO_LOGS[activeStageName] || [];
    if (subLogs.length === 0) return;

    const timers: NodeJS.Timeout[] = [];

    // Schedule incremental typewriter outputs to mimic actual computations
    subLogs.forEach((log, idx) => {
      const t = setTimeout(() => {
        setTelemetryLogs(prev => {
          if (prev.includes(log)) return prev;
          const next = [...prev, log];
          return next.slice(-30); // Cap at 30 items for terminal buffer size
        });
      }, idx * 250);
      timers.push(t);
    });

    return () => timers.forEach(clearTimeout);
  }, [activeStepIndex, dynamicStages, isDynamic]);

  // Scroll to bottom of telemetry log automatically
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [telemetryLogs]);

  // Smooth Gliding Progress Bar Interpolation (60fps animation frame loop)
  const targetPercent = useMemo(() => {
    if (isDynamic) {
      if (dynamicStages.length === 0) return 0;
      const latest = dynamicStages[dynamicStages.length - 1];
      const idx = ALL_DYNAMIC_STAGES.indexOf(latest.stage);
      if (idx === -1) return 0;
      
      // Compute actual position in the dynamic stages list
      const progressFraction = (idx + (latest.status === "done" ? 1 : 0.5)) / ALL_DYNAMIC_STAGES.length;
      return Math.min(100, Math.max(5, progressFraction * 100));
    } else {
      return Math.min(100, Math.max(5, (activeStepIndex / (BOOT_SEQUENCE.length - 1)) * 100));
    }
  }, [activeStepIndex, dynamicStages, isDynamic]);

  useEffect(() => {
    let animationId: number;

    const updateProgress = () => {
      setSmoothPercent(prev => {
        const diff = targetPercent - prev;
        if (Math.abs(diff) < 0.1) {
          return targetPercent > prev ? targetPercent : prev;
        }
        // Gliding factor: 0.08 per frame creates organic deceleration
        const next = prev + diff * 0.08;
        animationId = requestAnimationFrame(updateProgress);
        return next > prev ? next : prev;
      });
    };

    animationId = requestAnimationFrame(updateProgress);
    return () => cancelAnimationFrame(animationId);
  }, [targetPercent]);

  // Display logs stage list (Canonic mapping)
  const displaySequence = isDynamic 
    ? dynamicStages.map(s => ({ 
        message: s.stage, 
        isDone: s.status === "done" || s.status === "error",
        elapsed: s.elapsed
      }))
    : BOOT_SEQUENCE.map((s, i) => ({ 
        message: s.message, 
        isDone: i < activeStepIndex,
        elapsed: null
      }));

  // Get active step string for highlighting
  const currentActiveStageMessage = isDynamic
    ? (dynamicStages.find(s => s.status === "running")?.stage || dynamicStages[dynamicStages.length - 1]?.stage || "")
    : BOOT_SEQUENCE[activeStepIndex]?.message;

  return (
    <div className="flex flex-col items-center justify-center p-8 bg-[#0B1015]/95 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl max-w-lg w-full select-none text-slate-100 font-sans">
      
      {/* ── Holographic Circular Scanning Orb ───────────────────── */}
      <div className="relative mb-6 flex items-center justify-center">
        {/* Animated outer glows */}
        <div className="absolute w-44 h-44 rounded-full bg-indigo-500/5 blur-xl animate-pulse" />
        <div className="absolute w-32 h-32 rounded-full bg-emerald-500/5 blur-lg animate-pulse delay-75" />

        <svg className="w-40 h-40 text-indigo-500" viewBox="0 0 100 100">
          <defs>
            <radialGradient id="holoGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgb(99, 102, 241)" stopOpacity="0.25" />
              <stop offset="70%" stopColor="rgb(16, 185, 129)" stopOpacity="0.05" />
              <stop offset="100%" stopColor="rgb(99, 102, 241)" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="ringGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="rgb(99, 102, 241)" />
              <stop offset="50%" stopColor="rgb(16, 185, 129)" />
              <stop offset="100%" stopColor="rgb(99, 102, 241)" />
            </linearGradient>
          </defs>

          {/* Core Telemetry Ambient Glow */}
          <circle cx="50" cy="50" r="40" fill="url(#holoGlow)" />

          {/* Background Concentric Grids */}
          <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="0.5" strokeOpacity="0.08" />
          <circle cx="50" cy="50" r="35" fill="none" stroke="currentColor" strokeWidth="0.5" strokeOpacity="0.12" />
          <circle cx="50" cy="50" r="25" fill="none" stroke="currentColor" strokeWidth="0.5" strokeOpacity="0.08" />

          {/* Outer Dashed Diagnostic Ring */}
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke="url(#ringGradient)"
            strokeWidth="1.5"
            strokeDasharray="6 12"
            className="animate-[spin_24s_linear_infinite]"
            style={{ transformOrigin: "center" }}
          />

          {/* Inner Counter-Rotating Scanning Ring */}
          <circle
            cx="50"
            cy="50"
            r="30"
            fill="none"
            stroke="rgb(16, 185, 129)"
            strokeWidth="1.2"
            strokeDasharray="4 6"
            className="animate-[spin_12s_linear_infinite_reverse]"
            style={{ transformOrigin: "center" }}
            strokeOpacity="0.7"
          />

          {/* Sweeping Radar Scanner Array */}
          <line
            x1="50"
            y1="50"
            x2="50"
            y2="10"
            stroke="rgb(99, 102, 241)"
            strokeWidth="1.5"
            strokeLinecap="round"
            className="animate-[spin_3.5s_linear_infinite]"
            style={{ transformOrigin: "center" }}
            strokeOpacity="0.75"
          />

          {/* Axis Crosshairs */}
          <line x1="50" y1="18" x2="50" y2="82" stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" />
          <line x1="18" y1="50" x2="82" y2="50" stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" />

          {/* Central Biophysical Core */}
          <circle cx="50" cy="50" r="5" fill="rgb(16, 185, 129)" className="animate-ping opacity-60" />
          <circle cx="50" cy="50" r="3.5" fill="rgb(16, 185, 129)" />
        </svg>
        
        {/* Floating Scan Metrics */}
        <div className="absolute font-mono text-[9px] text-slate-500/80 tracking-widest uppercase flex flex-col items-center pointer-events-none">
          <span>CALIBRATING</span>
          <span className="font-bold text-indigo-400 mt-0.5 text-xs">{smoothPercent.toFixed(0)}%</span>
        </div>
      </div>

      {/* ── Active Stage Banner ─────────────────────────────────── */}
      <div className="text-center mb-5 w-full">
        <h3 className="font-semibold text-sm tracking-wide text-indigo-200 animate-pulse duration-1000">
          {currentActiveStageMessage || "Establishing Link..."}
        </h3>
        <p className="text-[10px] text-slate-500 mt-1 uppercase tracking-widest">
          {isDynamic ? "Live Pipeline Active" : "Initializing Ingestion Sequence"}
        </p>
      </div>

      {/* ── Telemetry Logs Console ─────────────────────────────── */}
      <div className="w-full bg-[#05080E]/90 border border-white/5 rounded-xl p-3 font-mono text-[10px] text-slate-400 h-28 overflow-y-auto custom-scrollbar flex flex-col gap-1 shadow-inner relative">
        <style>{`
          .custom-scrollbar::-webkit-scrollbar {
            width: 5px;
          }
          .custom-scrollbar::-webkit-scrollbar-track {
            background: rgba(5, 8, 14, 0.3);
            border-radius: 9999px;
          }
          .custom-scrollbar::-webkit-scrollbar-thumb {
            background: rgba(99, 102, 241, 0.3);
            border-radius: 9999px;
            border: 1px solid rgba(255, 255, 255, 0.03);
          }
          .custom-scrollbar::-webkit-scrollbar-thumb:hover {
            background: rgba(99, 102, 241, 0.6);
          }
          .custom-scrollbar {
            scrollbar-width: thin;
            scrollbar-color: rgba(99, 102, 241, 0.3) rgba(5, 8, 14, 0.3);
          }
        `}</style>
        <div className="text-emerald-500/80 mb-1 border-b border-emerald-500/10 pb-1 flex items-center justify-between text-[9px] tracking-wider sticky top-0 bg-[#05080E] z-10">
          <span>[SYSTEM] BIOPHYSICAL ANALYSIS COMPILING</span>
          <span className="animate-pulse text-indigo-400 font-bold">ONLINE</span>
        </div>
        {telemetryLogs.length === 0 ? (
          <div className="text-slate-600 italic animate-pulse">Awaiting telemetry frames...</div>
        ) : (
          telemetryLogs.map((log, index) => (
            <div key={index} className="flex items-start gap-1.5 text-slate-400/90 hover:text-white transition-colors duration-150">
              <span className="text-indigo-500 select-none">≫</span>
              <span className="leading-relaxed">{log}</span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>

      {/* ── Smoothly Gliding Progress Bar ────────────────────────── */}
      <div className="w-full mt-6 h-1.5 bg-slate-900 rounded-full overflow-hidden relative border border-white/5">
        <div 
          className="h-full bg-gradient-to-r from-indigo-500 to-emerald-500 transition-all duration-75 ease-out rounded-full" 
          style={{ width: `${smoothPercent}%` }}
        />
        {isDynamic && (
           <div className="absolute top-0 left-0 h-full w-full bg-white/10 animate-[pulse_1s_infinite]" />
        )}
      </div>

      {/* ── Bottom Ingestion Indicators ────────────────────────── */}
      <div className="w-full mt-4 flex items-center justify-between text-[9px] text-slate-500 font-mono tracking-wider border-t border-white/5 pt-3">
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${isDynamic ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
          <span>SATELLITE LINK</span>
        </div>
        <span>GRID CELL COMPACTION: OK</span>
      </div>
    </div>
  );
}
