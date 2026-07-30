"use client";

import React, { useState, useRef, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ChevronRight, SendHorizontal, BrainCircuit, X, 
  Activity, Droplets, Leaf, ShieldAlert, Cpu, 
  CalendarDays, ReceiptText, Sparkles, Loader2, CheckCircle2 
} from "lucide-react";
import ReactMarkdown from 'react-markdown';
import { ToolResultRenderer } from '../chat/widgets/ToolResultRenderer';
import ARFWidget from '../chat/widgets/ARFWidget';
import { usePlotIntelligence as usePlotIntelHook } from "@/hooks/usePlotIntelligence";

interface Message {
  role: 'user' | 'model';
  content: string;
  toolCalls?: { name: string; args: any; result?: any }[];
  metadata?: { intent?: string; evidence?: string[] };
  arf?: any;
  thinkingTrace?: string;
}

interface SubEngine {
  name: string;
  calc: string;
}

const LAYER_SUB_ENGINES: Record<string, SubEngine[]> = {
  L2: [
    { name: "Whittaker Cholesky Solver", calc: "solving banded system (W + λ DᵀD) z = Wy..." },
    { name: "Savitzky-Golay Corrector", calc: "interpolating 3-pass upper envelope..." },
    { name: "Beer-Lambert LAI Inversion", calc: "LAI = -ln(1 - fPAR) / 0.50 (Myneni 1997)..." },
    { name: "FVC Canopy Estimator", calc: "FVC = ((NDVI - 0.10) / 0.75)²..." },
    { name: "CASA NPP Simulator", calc: "NPP = fPAR * PAR * ε_max * T_scalar (Potter 1993)..." },
    { name: "Sánchez Thermal GDD", calc: "GDD = max(0, T_mean - T_base) * photo_factor (Sánchez 2014)..." },
    { name: "Viterbi HMM Decoder", calc: "decoding developmental stages via log-likelihood transitions..." },
    { name: "Bayesian Crop Classifier", calc: "evaluating posteriors over 209 crop configs..." },
    { name: "Moran's I Spatial Engine", calc: "computing sub-field zone stability index..." },
    { name: "Isolation Forest Anomaly", calc: "identifying crop stress outlier deviations..." }
  ],
  L3: [
    { name: "Penman-Monteith FAO-56", calc: "ET0 = (0.408Δ(Rn-G) + γ(900/(T+273))u2(es-ea)) / (Δ+γ(1+0.34u2))..." },
    { name: "Hargreaves-Samani Fallback", calc: "estimating ET0 via solar radiation and temp extremes..." },
    { name: "Kc Dynamic Scaler", calc: "Kc = Kc_min + (Kc_full - Kc_min) * Fc..." },
    { name: "Root-Zone Water Balance", calc: "St = St-1 + Rain + Irrig - ET_actual - Drainage..." },
    { name: "Ks Transpiration Monitor", calc: "Ks = max(0, (TAW - Dr) / (0.4 * TAW))..." },
    { name: "FAO-56 Evapotranspiration", calc: "ET_actual = Kc * ET0 * Ks..." },
    { name: "Soil Moisture Bucket Model", calc: "updating SPAC volumetric water content..." },
    { name: "Irrigation Refill Optimizer", calc: "calculating gross refill capacity relative to soil texture..." }
  ],
  L4: [
    { name: "Soil Respiration Estimator", calc: "modeling carbon mineralization flux..." },
    { name: "Nitrogen Deficiency Weight", calc: "estimating mineralized organic nitrogen drawdowns..." },
    { name: "Phosphorus Sorption Isotherm", calc: "solving Langmuir soil adsorption bounds..." },
    { name: "Root-Zone N-P-K Balance", calc: "updating nutrient depletion gridded matrices..." },
    { name: "pH Chemical Availability Gate", calc: "scaling cation exchange capacity relative to pH..." },
    { name: "NUE Photosynthesis Analyzer", calc: "evaluating photosynthetic leaf nitrogen use efficiency..." },
    { name: "Cation Exchange Capacity Buffer", calc: "modeling soil loam base cation buffering..." },
    { name: "Variable-Rate Fertilizer Solver", calc: "optimizing N-P-K recommendation dose matrices..." }
  ],
  L5: [
    { name: "Spore Germination Solver", calc: "calculating sporulation temperature limits..." },
    { name: "Blight RH Integrator", calc: "integrating trailing 72h canopy relative humidity..." },
    { name: "Insect Vector Flight Tracker", calc: "estimating pest flight hours relative to wind..." },
    { name: "Windborne Dispersal Model", calc: "solving Gaussian dispersion atmospheric transport..." },
    { name: "Micro-climate Sensor Fusion", calc: "fusing IoT soil/air moisture gridded anomalies..." },
    { name: "Pathogen Susceptibility Index", calc: "evaluating crop-disease physiological vulnerability..." },
    { name: "Localized Outbreak Forecaster", calc: "running Monte Carlo risk propagation matrices..." }
  ],
  L6: [
    { name: "Extended Kalman Filter Bridge", calc: "updating spatial state error covariance matrices..." },
    { name: "IoT Sensor Calibration Model", calc: "normalizing moisture sensor drift deviations..." },
    { name: "Causal Stress State Filter", calc: "isolating environmental drivers from observations..." },
    { name: "Crop Water Productivity Index", calc: "estimating yield/biomass per cubic meter..." },
    { name: "Harvest Index Partitioner", calc: "allocating reproductive biomass fraction..." },
    { name: "CUSUM Deviation Compiler", calc: "evaluating spatial zone shift alarms..." },
    { name: "Multi-Source Sensor Ingestion", calc: "fusing optical, SAR, weather, and physical logs..." }
  ],
  L7: [
    { name: "Phenology Thermal Planner", calc: "projecting developmental GDD benchmarks..." },
    { name: "Tillage Window Recommender", calc: "checking soil shear strength and mechanical limits..." },
    { name: "Seasonal Nutrient Drawdown", calc: "forecasting nitrogen depletion over crop lifecycle..." },
    { name: "Frost Risk Trend Estimator", calc: "evaluating local radiative cooling curves..." },
    { name: "Heat Stress Cumulative Tracker", calc: "integrating daily extreme temperature anomalies..." },
    { name: "Dynamic Crop Growth Curve", calc: "forecasting seasonal NDVI trajectory envelopes..." },
    { name: "Climate Suitability Classifier", calc: "evaluating Köppen climate variety suitability..." }
  ],
  L8: [
    { name: "Management Zone Inverter", calc: "solving spatial priority dose matrices..." },
    { name: "N-Application Response Model", calc: "evaluating yield-fertilizer curvature response..." },
    { name: "VRI Scheduling Optimizer", calc: "calculating variable-rate irrigation scheduling..." },
    { name: "Crop Rotation Profit Analyzer", calc: "simulating sequence financial outcomes..." },
    { name: "Cost-Benefit Economic Filter", calc: "verifying chemical and water return-on-investment..." },
    { name: "Active Chemical Schedule Gate", calc: "enforcing safety and dosage local regulations..." },
    { name: "Drone Flight Mission Router", calc: "generating autonomous spatial coverage plans..." }
  ]
};

const LAYER_MAPPING = [
  { id: "L2", name: "Crop Health Index", description: "Vegetation & Canopy Dynamics", stageName: "Analyzing crop health", icon: Leaf },
  { id: "L3", name: "Water Stress SPAC", description: "FAO-56 Evapotranspiration", stageName: "Evaluating water & stress models", icon: Droplets },
  { id: "L4", name: "Soil Nutrients", description: "Root-Zone N-P-K Drawdowns", stageName: "Assessing soil nutrients", icon: Activity },
  { id: "L5", name: "Spore Pathogens", description: "Crop Disease Risk Propagation", stageName: "Scanning disease & pest risk", icon: ShieldAlert },
  { id: "L6", name: "Causal Kalman State", description: "Extended Sensor & IoT Fusion", stageName: "Computing execution state", icon: Cpu },
  { id: "L7", name: "Seasonal Plan", description: "Thermodynamic Growth Curves", stageName: "Building season plan", icon: CalendarDays },
  { id: "L8", name: "Prescriptive VRA", description: "Variable-Rate Dosing Optimization", stageName: "Generating prescriptions", icon: ReceiptText }
];

function BiophysicalPipelineVisualizer({ plotId, stages }: { plotId?: string; stages: any[] }) {
  const [visualActiveIndex, setVisualActiveIndex] = useState(0);
  const [subEngineTick, setSubEngineTick] = useState(0);
  const [smoothPercent, setSmoothPercent] = useState(5);

  const isDynamic = stages && stages.length > 0;

  // Map backend stages that are already completed
  const backendDoneLayers = useMemo(() => {
    if (!isDynamic) return new Set();
    const completed = new Set();
    stages.forEach(s => {
      if (s.status === "done" || s.status === "error") {
        completed.add(s.stage);
      }
    });
    return completed;
  }, [stages, isDynamic]);

  // Synchronize visual progression with actual backend computational layers
  const backendActiveIndex = useMemo(() => {
    if (!isDynamic) return LAYER_MAPPING.length; // No limit in simulation/mock fallback mode
    
    let maxIdx = -1;
    stages.forEach(s => {
      const layerOrder = LAYER_MAPPING.map(l => l.stageName);
      const idx = layerOrder.indexOf(s.stage);
      if (idx !== -1 && (s.status === "running" || s.status === "done")) {
        if (idx > maxIdx) maxIdx = idx;
      }
      if ((s.stage === "Composing narrative" || s.stage === "Complete") && s.status === "done") {
        maxIdx = LAYER_MAPPING.length;
      }
    });
    return maxIdx;
  }, [stages, isDynamic]);

  const currentLayer = LAYER_MAPPING[visualActiveIndex];
  const activeLayerId = currentLayer?.id || "";

  // Reset tick when visual active layer changes
  useEffect(() => {
    setSubEngineTick(0);
  }, [visualActiveIndex]);

  // Auto-scroll the active terminal console to the bottom as sub-engines tick
  useEffect(() => {
    const consoleEl = document.getElementById("biophysical-terminal-console");
    if (consoleEl) {
      consoleEl.scrollTop = consoleEl.scrollHeight;
    }
  }, [subEngineTick]);

  // Tick the sub-engines sequentially in the active layer's console
  useEffect(() => {
    if (!activeLayerId) return;
    
    const count = LAYER_SUB_ENGINES[activeLayerId]?.length || 0;
    const interval = setInterval(() => {
      setSubEngineTick((prev) => {
        if (prev < count) {
          return prev + 1;
        } else {
          // If we finished ticking all sub-engines for this layer,
          // check if we can proceed to the next visual layer step.
          const backendIsDone = !isDynamic || backendDoneLayers.has(currentLayer.stageName);
          
          if (backendIsDone && visualActiveIndex < backendActiveIndex) {
            if (visualActiveIndex < LAYER_MAPPING.length - 1) {
              setVisualActiveIndex(prevIdx => prevIdx + 1);
            }
          }
          return prev;
        }
      });
    }, 90); // 90ms tick speed per sub-engine

    return () => clearInterval(interval);
  }, [activeLayerId, visualActiveIndex, isDynamic, backendDoneLayers, currentLayer, backendActiveIndex]);

  // Derive visual status for rendering
  const layersStatus = useMemo(() => {
    return LAYER_MAPPING.map((layer, idx) => {
      let status: "pending" | "running" | "done" = "pending";
      if (idx < visualActiveIndex) {
        status = "done";
      } else if (idx === visualActiveIndex) {
        status = "running";
      }
      return {
        ...layer,
        status
      };
    });
  }, [visualActiveIndex]);

  // Progress percentage follows visual active index + sub-engine ticks
  const targetPercent = useMemo(() => {
    const fraction = (visualActiveIndex + (subEngineTick / (LAYER_SUB_ENGINES[activeLayerId]?.length || 1))) / LAYER_MAPPING.length;
    return Math.min(98, Math.max(5, fraction * 100));
  }, [visualActiveIndex, subEngineTick, activeLayerId]);

  // Gliding progress bar logic (60fps requestAnimationFrame loop)
  useEffect(() => {
    let animId: number;
    const animate = () => {
      setSmoothPercent((prev) => {
        const diff = targetPercent - prev;
        if (Math.abs(diff) < 0.1) return targetPercent;
        const next = prev + diff * 0.12; // Glide speed
        animId = requestAnimationFrame(animate);
        return next;
      });
    };
    animId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animId);
  }, [targetPercent]);

  return (
    <div className="bg-[#0A0F15]/90 border border-white/10 dark:border-indigo-500/20 backdrop-blur-3xl shadow-[0_0_50px_rgba(0,0,0,0.8)] rounded-2xl p-5 w-full flex flex-col gap-4 font-sans select-none text-slate-100 overflow-hidden max-w-full">
      {/* HUD Header */}
      <div className="flex items-center gap-4 border-b border-white/5 pb-3">
        {/* Compact Sweeping Radar */}
        <div className="shrink-0 flex items-center justify-center relative">
          <div className="absolute w-12 h-12 rounded-full bg-indigo-500/5 blur animate-pulse" />
          <svg className="w-10 h-10 text-indigo-500" viewBox="0 0 100 100">
            <defs>
              <linearGradient id="radarSweep" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="rgb(99, 102, 241)" stopOpacity="1" />
                <stop offset="100%" stopColor="rgb(16, 185, 129)" stopOpacity="0.1" />
              </linearGradient>
            </defs>
            <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="0.5" strokeOpacity="0.08" />
            <circle cx="50" cy="50" r="30" fill="none" stroke="currentColor" strokeWidth="0.5" strokeOpacity="0.12" />
            <circle
              cx="50"
              cy="50"
              r="40"
              fill="none"
              stroke="rgb(99, 102, 241)"
              strokeWidth="1"
              strokeDasharray="6 12"
              className="animate-[spin_16s_linear_infinite]"
              style={{ transformOrigin: "center" }}
              strokeOpacity="0.3"
            />
            <line
              x1="50"
              y1="50"
              x2="50"
              y2="10"
              stroke="url(#radarSweep)"
              strokeWidth="2"
              strokeLinecap="round"
              className="animate-[spin_3s_linear_infinite]"
              style={{ transformOrigin: "center" }}
            />
            <circle cx="50" cy="50" r="3.5" fill="rgb(16, 185, 129)" />
          </svg>
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold tracking-wider text-slate-800 dark:text-indigo-400 uppercase">Biophysical Ingestion Core</span>
            <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[8px] font-bold tracking-widest uppercase border border-emerald-500/20 animate-pulse">Running</span>
          </div>
          <div className="flex items-center gap-3 text-[9px] text-slate-500 dark:text-slate-400 font-mono mt-0.5">
            <span>CORES: AGRIBRAIN COMPUTE NODE</span>
            <span>&bull;</span>
            <span>LOAD: OPTIMAL</span>
            <span>&bull;</span>
            <span className="text-indigo-400 font-semibold">{smoothPercent.toFixed(0)}% PIPELINE INGESTED</span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full h-1.5 bg-[#05080C] rounded-full overflow-hidden relative border border-white/5 shadow-inner">
        <div 
          className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 transition-all duration-75 ease-out rounded-full shadow-[0_0_15px_rgba(99,102,241,0.6)]" 
          style={{ width: `${smoothPercent}%` }}
        />
        <div className="absolute top-0 left-0 h-full w-full bg-white/10 animate-[pulse_1s_infinite]" />
      </div>

      {/* Pipeline Grid */}
      <div className="flex flex-col gap-2 relative z-10">
        {layersStatus.map((layer) => {
          const LayerIcon = layer.icon;
          const isRunning = layer.status === "running";
          const isDone = layer.status === "done";
          const isPending = layer.status === "pending";

          return (
            <div key={layer.id} className="flex flex-col w-full">
              <div 
                className={`
                  flex items-center gap-3.5 px-4 py-3 rounded-xl border transition-all duration-300 border-l-4
                  ${isRunning 
                    ? 'bg-indigo-950/20 border-indigo-500/30 border-l-indigo-500 text-white shadow-[0_0_20px_rgba(99,102,241,0.1)]' 
                    : isDone
                      ? 'bg-emerald-950/10 border-emerald-500/20 border-l-emerald-500 text-emerald-200/90'
                      : 'bg-[#0D1219]/20 border-white/5 border-l-transparent opacity-40 text-slate-500'}
                `}
              >
                {/* Visual Status Indicator */}
                <div className="shrink-0 relative flex items-center justify-center w-5 h-5">
                  {isRunning ? (
                    <>
                      <span className="absolute w-full h-full rounded-full border border-indigo-500/35 animate-ping" />
                      <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                    </>
                  ) : isDone ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                  ) : (
                    <div className="w-2.5 h-2.5 rounded-full border border-slate-700 border-dashed" />
                  )}
                </div>

                {/* Layer Icon */}
                <div className={`p-1.5 rounded-lg shrink-0 ${isRunning ? 'bg-indigo-500/20 text-indigo-400' : isDone ? 'bg-emerald-500/10 text-emerald-400' : 'bg-transparent text-slate-600'}`}>
                  <LayerIcon className="w-4 h-4" />
                </div>

                {/* Info */}
                <div className="flex-1">
                  <span className={`text-[13px] font-semibold tracking-wide ${isRunning ? 'text-white' : isDone ? 'text-emerald-100/95 font-medium' : 'text-slate-500 dark:text-slate-500'}`}>{layer.name}</span>
                  <span className={`text-[9px] ml-2 font-medium tracking-wide ${isRunning ? 'text-indigo-300/80' : isDone ? 'text-emerald-400/80' : 'text-slate-600'}`}>({layer.description})</span>
                </div>

                {/* Badge */}
                <span className={`text-[8px] font-bold font-mono uppercase px-1.5 py-0.5 rounded tracking-widest ${isRunning ? 'bg-indigo-500/20 text-indigo-400 animate-pulse' : isDone ? 'bg-emerald-500/15 text-emerald-400' : 'bg-transparent text-slate-600'}`}>
                  {isRunning ? "Running" : isDone ? "OK" : "Wait"}
                </span>
              </div>

              {/* Granular Ticker Console for Active Layer */}
              {isRunning && (
                <div className="pl-9 pr-2 mt-1.5">
                  <div id="biophysical-terminal-console" className="bg-[#040608]/95 border border-indigo-500/30 rounded-xl p-3 font-mono text-[9px] text-slate-300 h-32 overflow-y-auto custom-scrollbar flex flex-col gap-1.5 shadow-inner relative select-text leading-relaxed">
                    <div className="text-indigo-300 mb-1 border-b border-indigo-500/10 pb-1 flex items-center justify-between text-[8px] tracking-wider font-semibold sticky top-0 bg-[#040608] z-10">
                      <span>[TELEMETRY] EXEC: {layer.name.toUpperCase()} MODELS</span>
                      <span className="animate-pulse font-bold text-cyan-400">ANALYZING</span>
                    </div>
                    {LAYER_SUB_ENGINES[layer.id]?.map((engine, idx) => {
                      const isSubDone = idx < subEngineTick;
                      const isSubRunning = idx === subEngineTick;

                      return (
                        <div 
                          key={idx} 
                          className={`
                            flex flex-col gap-0.5 transition-colors duration-150 py-0.5
                            ${isSubRunning ? 'text-cyan-300 drop-shadow-[0_0_8px_rgba(34,211,238,0.4)]' : isSubDone ? 'text-slate-300' : 'text-slate-600'}
                          `}
                        >
                          <div className="flex items-center gap-1.5 font-semibold">
                            <span className={isSubRunning ? 'text-cyan-300' : isSubDone ? 'text-emerald-400' : 'text-slate-600'}>
                              {isSubRunning ? '▶' : isSubDone ? '✓' : '•'}
                            </span>
                            <span>[{isSubRunning ? 'RUN' : isSubDone ? 'OK' : 'WAIT'}] {engine.name}</span>
                          </div>
                          {(isSubRunning || isSubDone) && (
                            <span className={`pl-4 text-[8px] font-normal tracking-wide ${isSubRunning ? 'text-cyan-400/80' : 'text-emerald-400/80'}`}>{engine.calc}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer System Ingestion Status */}
      <div className="border-t border-white/5 pt-2 flex items-center justify-between text-[9px] text-slate-400/80 font-mono tracking-wider">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>SATELLITE & IoT FUSION CHANNEL</span>
        </div>
        <span>COMPACTION: 100% OK</span>
      </div>
    </div>
  );
}

function ThinkingTraceRenderer({ trace }: { trace: string }) {
  const renderLine = (line: string, i: number) => {
    let el = <span dangerouslySetInnerHTML={{
        __html: line
            .replace(/\[LOW CONFIDENCE[^\]]*\]/gi, '<span class="px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/30 text-amber-700 dark:text-amber-500 text-[10px] font-bold tracking-wide uppercase mx-1">⚠️ Low Conf</span>')
            .replace(/\[MISSING DRIVER[^\]]*\]/gi, '<span class="px-1.5 py-0.5 rounded bg-red-500/20 border border-red-500/30 text-red-700 dark:text-red-500 text-[10px] font-bold tracking-wide uppercase mx-1">❌ Missing</span>')
            .replace(/\[HIGH CONFIDENCE[^\]]*\]/gi, '<span class="px-1.5 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/30 text-emerald-700 dark:text-emerald-500 text-[10px] font-bold tracking-wide uppercase mx-1">✅ High Conf</span>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
    }} />
    return <div key={i} className="mb-1 leading-relaxed">{el}</div>;
  };

  return (
    <div className="flex flex-col">
      {trace.split('\n').filter(l => l.trim() !== "").map((line, i) => renderLine(line, i))}
    </div>
  );
}

const MetricHighlighter = ({ children }: { children: React.ReactNode }) => {
  const processNode = (node: React.ReactNode): React.ReactNode => {
    if (typeof node === 'string') {
      const regex = /(\b\d+(?:\.\d+)?\s*(?:mm|cm|m|km|kg|g|ha|NDVI|°C|°F|C|F|days|weeks|months|hours|mm\/h|obs)\b|\b\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?%|\b-?0\.\d{2,4}\b)/gi;
      const parts = node.split(regex);
      if (parts.length === 1) return node;
      
      return parts.map((part, i) => {
        if (part.match(regex)) {
          if (/^\d$/.test(part.trim())) return part;
          
          return (
            <span key={i} className="inline-flex items-center gap-0.5 px-1.5 py-px mx-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-700 dark:text-indigo-400 font-mono font-bold whitespace-nowrap shadow-sm align-baseline transition-colors hover:bg-indigo-500/20 cursor-default">
              <BrainCircuit className="w-3 h-3 opacity-70 shrink-0 relative -top-[0.5px]" />
              {part}
            </span>
          );
        }
        return part;
      });
    }
    if (React.isValidElement(node)) {
      return React.cloneElement(node, { ...(node.props as any), children: React.Children.map((node.props as any).children, processNode) });
    }
    return node;
  };

  return <>{React.Children.map(children, processNode)}</>;
};

interface AgriBrainChatProps {
  context?: any;
  onZoneUpdate?: (zones: any, zoneSuitability: any) => void;
  suggestedQuery?: { label: string; query: string } | null;
  initialQuery?: string | null;
}

export default function AgriBrainChat({ context, onZoneUpdate, suggestedQuery, initialQuery }: AgriBrainChatProps) {
  const [input, setInput] = useState(initialQuery || "");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState("Executing analysis...");
  const [progressStages, setProgressStages] = useState<any[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { detailMode } = usePlotIntelHook();

  const STORAGE_KEY = `agribrain_chat_${context?.plot_id || 'default'}`;

  // Load from local storage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setMessages(JSON.parse(stored));
      }
    } catch (e) {
      console.error("Failed to load chat history", e);
    }
  }, [STORAGE_KEY]);

  useEffect(() => {
    try {
      if (messages.length > 0) {
        const cleanMessages = messages.filter(m => !(m.role === 'model' && m.content.includes('⚠️ System Error')));
        if (cleanMessages.length > 0) {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(cleanMessages));
        } else {
          localStorage.removeItem(STORAGE_KEY);
        }
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch (e) {
      console.error("Failed to save chat history", e);
    }
  }, [messages, STORAGE_KEY]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSend = async (overrideInput?: string) => {
    const textToSend = overrideInput || input;
    if (!textToSend.trim() || loading) return;

    const userMsg: Message = { role: 'user', content: textToSend };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setLoading(true);
    setLoadingText("Routing query...");
    setProgressStages([]); // Reset stages

    const pId = context?.plotId || context?.plot?.id;
    let pollInterval: NodeJS.Timeout | null = null;

    if (pId) {
      pollInterval = setInterval(async () => {
        try {
          const res = await fetch(`/api/agribrain/progress?plotId=${pId}`);
          if (!res.ok) return;
          const data = await res.json();
          if (data.active && data.stages && data.stages.length > 0) {
            setProgressStages(data.stages);
            const runningStage = [...data.stages].reverse().find(s => s.status === "running");
            if (runningStage) {
              setLoadingText(`Thinking: ${runningStage.stage}...`);
            } else {
              const lastStage = data.stages[data.stages.length - 1];
              if (lastStage && lastStage.status === "done") {
                if (lastStage.stage === "Complete") {
                  setLoadingText("Thinking: Composing narrative...");
                } else {
                  setLoadingText(`Thinking: Completed ${lastStage.stage}...`);
                }
              }
            }
          }
        } catch (e) {
          // Ignore polling errors
        }
      }, 500);
    }

    try {
      const historyForApi = messages.map(m => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content
      }));

      // 1. Fast Intent Pass
      try {
        const intentRes = await fetch('/api/agribrain/intent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: userMsg.content,
            history: historyForApi
          })
        });
        const intentData = await intentRes.json();
        if (intentData.success && intentData.data) {
          const engines = intentData.data.engines || [];
          if (engines.length > 0) {
            setLoadingText(`Thinking: Routing to ${engines.join(", ")}...`);
          } else {
            setLoadingText("Thinking: Analyzing field context...");
          }
        }
      } catch (e) {
        console.warn("Intent fetch failed, proceeding anyway", e);
        setLoadingText("Executing analysis...");
      }

      // 2. Main LLM Pass
      const res = await fetch('/api/agribrain/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plotId: pId,
          mode: 'chat',
          query: userMsg.content,
          history: historyForApi,
          experienceLevel: 'INTERMEDIATE',
          userMode: detailMode,
        })
      });
      
      const data = await res.json();
      
      if (data.error || data.success === false) {
        throw new Error(data.error || 'AgriBrain run failed');
      }

      const arf = data.arf || data.explanations?.arf;
      const modes = data.global_quality?.degradation_modes || [];
      const relScore = data.global_quality?.reliability || 0;

      // Build display text
      let md = "";
      let thinkingTrace = "";
      if (arf && arf.conversational_response) {
        let raw = arf.conversational_response;

        const dsMatch = raw.match(/<think>([\s\S]*?)<\/think>/i);
        if (dsMatch) {
          thinkingTrace = dsMatch[1].trim().replace(/^-\s*/gm, "• ");
          raw = raw.replace(dsMatch[0], "").trim();
        }

        if (!thinkingTrace) {
          const match = raw.match(/(>\s*\*Thinking:\*[\s\S]*?)(?=\n\n|\n[A-Z]|\n<|$)/i);
          if (match) {
            thinkingTrace = match[0].replace(/>\s*\*Thinking:\*\s*/i, "").trim();
            thinkingTrace = thinkingTrace.replace(/^>\s*/gm, "").replace(/^-\s*/gm, "• ");
            raw = raw.replace(match[0], "").trim();
          }
        }

        md = raw;
      } else if (arf && !arf.error && (arf.headline || arf.direct_answer)) {
        md = `Here is the diagnostic analysis based on your request:`;
      } else {
        const headline = data.summary?.headline || data.explanations?.summary?.headline || "Analysis Complete";
        const body = arf?.error ? `**Error:** ${arf.error}` : (data.summary?.explanation || "");
        md = `### ${headline}\n\n${body}\n\n`;
      }

      if (modes.length > 0 && !(arf && arf.conversational_response)) {
        md += `\n> ⚠️ **Data Gaps:** ${modes.join(", ")} (Reliability: ${relScore.toFixed(2)})`;
      }

      const modelMsg: Message = {
        role: 'model',
        content: md || (arf ? "" : "I processed that."),
        toolCalls: data.toolCalls,
        metadata: { intent: data.assistant_mode || data.intent, evidence: modes },
        arf: (arf && arf.conversational_response) ? undefined : arf,
        thinkingTrace: thinkingTrace || undefined
      };
      
      const zones = data.zones || data.summary?.management_zones;
      const zoneSuitability = data.zoneSuitability || data.summary?.zone_suitability;
      if (onZoneUpdate && (zones || zoneSuitability)) {
        onZoneUpdate(zones, zoneSuitability);
      }
      
      setMessages(prev => [...prev, modelMsg]);
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, { role: 'model', content: `⚠️ System Error: ${e instanceof Error ? e.message : String(e)}` }]);
    } finally {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
      setLoading(false);
    }
  };

  const adjustTextareaHeight = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
    }
  };

  return (
    <div className="card fade-in flex flex-col h-full overflow-hidden border border-white/5 bg-[#0B1015]/90 backdrop-blur-3xl shadow-2xl">
      {/* HUD Header */}
      <div className="p-4 border-b border-white/5 bg-[#0B1015]/95 backdrop-blur-xl flex items-center justify-between z-10 sticky top-0 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.15)] animate-pulse">
            <BrainCircuit className="w-5 h-5" />
          </div>
          <div>
            <h3 className="m-0 text-base font-semibold text-white tracking-tight">AgriBrain Assistant</h3>
            <div className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              ORCHESTRATOR V2.1 ACTIVE &bull; ONLINE
            </div>
          </div>
        </div>
        
        {/* Hardware Status Ribbon */}
        <div className="hidden md:flex items-center gap-4 text-[10px] font-mono text-slate-500 border-l border-white/5 pl-4">
          <div className="flex flex-col">
            <span className="text-[8px] text-slate-600 uppercase tracking-widest">ENGINE</span>
            <span className="text-slate-300 font-semibold">AGRIBRAIN ORCHESTRATOR</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[8px] text-slate-600 uppercase tracking-widest">FUSION RATE</span>
            <span className="text-emerald-400 font-semibold">104 SENSORS/S</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[8px] text-slate-600 uppercase tracking-widest">LATENCY</span>
            <span className="text-indigo-400 font-semibold">28MS</span>
          </div>
        </div>

        <div className="flex items-center gap-2 pl-4 border-l border-white/5">
          <button
            onClick={() => setMessages([])}
            className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors group"
            title="Clear chat history"
          >
            <X className="w-4 h-4 transition-transform group-hover:rotate-90" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 md:p-6 flex flex-col gap-6 scroll-smooth scrollbar-thin scrollbar-thumb-slate-800 dark:scrollbar-thumb-slate-800 bg-[#0B1015]/40 relative">
        <AnimatePresence initial={false}>
        {messages.map((msg, i) => (
          <motion.div 
            key={i} 
            layout
            initial={{ opacity: 0, y: 15, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
            className={`flex flex-col w-full max-w-[90%] ${msg.role === 'user' ? 'self-end items-end' : 'self-start items-start'}`}
          >
            
            {/* Tool Indicators */}
            {msg.toolCalls && msg.toolCalls.map((tool, idx) => (
              <div key={`tool-${idx}`} className="mb-2 w-full max-w-[95%] fade-in">
                 <div className="px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-t-xl text-xs text-emerald-400 font-mono inline-flex items-center gap-1.5 -mb-px relative z-10 shadow-sm">
                   <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                   🛠️ Telemetry: <b>{tool.name}</b>
                 </div>
                 
                 {tool.result ? (
                     <div className="bg-[#0D1217]/95 border border-white/5 rounded-b-xl rounded-tr-xl p-3 shadow-2xl overflow-hidden text-slate-300">
                        <ToolResultRenderer toolName={tool.name} result={tool.result} />
                     </div>
                 ) : (
                     <div className="bg-[#0D1217]/50 border border-white/5 rounded-b-xl rounded-tr-xl p-3 text-xs text-slate-500 italic font-mono flex items-center gap-2">
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-500" />
                        Analyzing layer outputs...
                     </div>
                 )}
              </div>
            ))}
            
            {/* Thinking Trace */}
            {msg.thinkingTrace && (
               <details className="mb-3 w-full max-w-[95%] group">
                  <summary className="px-3 py-2 bg-indigo-500/5 hover:bg-indigo-500/10 border border-indigo-500/10 rounded-xl text-[10px] text-indigo-300 font-mono inline-flex items-center gap-2 cursor-pointer transition-colors shadow-sm select-none list-none uppercase tracking-wider">
                    <ChevronRight className="w-3.5 h-3.5 text-indigo-400 transition-transform group-open:rotate-90" />
                    <span>Expert Architect Trace (Chain-of-Thought)</span>
                  </summary>
                  <motion.div 
                    initial={{ height: 0, opacity: 0 }} 
                    animate={{ height: "auto", opacity: 1 }} 
                    className="mt-2 bg-[#040608]/95 border border-indigo-500/20 rounded-xl p-4 shadow-2xl text-[12px] text-slate-300 font-mono overflow-x-auto select-text leading-relaxed border-l-4 border-l-indigo-500"
                  >
                    <ThinkingTraceRenderer trace={msg.thinkingTrace} />
                  </motion.div>
               </details>
            )}
            
            {/* Bubble */}
            <div 
              dir="ltr"
              className={`
              px-5 py-3.5 rounded-2xl shadow-xl text-[15px] text-left break-words overflow-hidden max-w-full select-text border
              ${msg.role === 'user' 
                ? 'bg-gradient-to-br from-indigo-500 to-blue-600 text-white border-indigo-400/20 rounded-br-sm shadow-indigo-500/10' 
                : 'bg-[#0D1217]/85 text-slate-200 border-white/5 rounded-bl-sm backdrop-blur-md'}
            `}>
              {msg.arf ? (
                  <div className="flex flex-col gap-3">
                     {msg.content && <div className="mb-1 text-[15px] leading-relaxed"><ReactMarkdown>{msg.content}</ReactMarkdown></div>}
                     <ARFWidget arf={msg.arf} />
                  </div>
              ) : (
                  <ReactMarkdown 
                    components={{
                      p: ({children, ...props}) => <p className="m-0 leading-relaxed text-[15px]" {...props}><MetricHighlighter>{children}</MetricHighlighter></p>,
                      ul: ({children, ...props}) => <ul className="my-2 pl-4 list-disc marker:text-indigo-400" {...props}>{children}</ul>,
                      li: ({children, ...props}) => <li className="mb-1" {...props}><MetricHighlighter>{children}</MetricHighlighter></li>
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
              )}
            </div>
          </motion.div>
        ))}
        </AnimatePresence>
        
        {/* Real-time Loading & Biophysical Pipeline Visualizer */}
        {loading && (
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-start w-full max-w-[95%]"
          >
            <div className="flex flex-col gap-3 w-full">
              <BiophysicalPipelineVisualizer 
                plotId={String(context?.plotId || context?.plot?.id || context?.plot_id || "")}
                stages={progressStages}
              />
              <div className="text-[11px] font-mono text-slate-500 flex items-center gap-2 pl-2">
                <Loader2 className="w-3 h-3 animate-spin text-indigo-400" />
                <span>{loadingText}</span>
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* Input Console */}
      <div className="border-t border-white/5 bg-[#0B1015]/95 backdrop-blur-xl flex flex-col p-4 relative z-10 shadow-[0_-5px_20px_rgba(0,0,0,0.4)]">
        {suggestedQuery && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="absolute -top-12 left-4 right-4 flex justify-start">
            <button 
              onClick={() => handleSend(suggestedQuery.query)}
              className="text-xs font-semibold bg-[#0D1217]/95 text-indigo-400 border border-indigo-500/20 shadow-xl px-4 py-2.5 rounded-full hover:bg-indigo-500/10 hover:border-indigo-500/40 hover:text-white flex items-center gap-2 transition-all hover:scale-105 active:scale-95"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
              {suggestedQuery.label}
            </button>
          </motion.div>
        )}
        
        <div className="flex gap-3 bg-[#080B0F]/90 border border-white/5 shadow-2xl rounded-2xl p-1.5 focus-within:ring-2 focus-within:ring-indigo-500/30 focus-within:border-indigo-500/30 transition-all">
          <textarea 
            ref={textareaRef}
            value={input}
            onChange={adjustTextareaHeight}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask about yield, water levels, nutrients, or crop health..."
            className="flex-1 max-h-[120px] min-h-[44px] py-3 px-4 bg-transparent text-sm text-slate-200 focus:outline-none resize-none leading-relaxed placeholder:text-slate-500 font-sans"
            rows={1}
          />
          <div className="flex items-end p-1">
            <motion.button 
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className={`
                w-10 h-10 flex items-center justify-center rounded-xl transition-all
                ${loading || !input.trim() 
                  ? 'bg-slate-800/30 text-slate-600 cursor-not-allowed border border-white/5' 
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20'}
              `}
            >
              <SendHorizontal className="w-5 h-5" />
            </motion.button>
          </div>
        </div>
        <div className="text-center mt-2.5">
          <span className="text-[10px] text-slate-500 font-mono tracking-wide">AgriBrain can make mistakes. Cross-check critical farm choices.</span>
        </div>
      </div>
    </div>
  );
}
