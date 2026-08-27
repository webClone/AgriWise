"use client";

/**
 * CropIdentityBanner — Crop Intelligence FAB button + full-screen modal.
 *
 * Renders a 56×56 button above the Chat button. On click, opens a modal
 * (same style as AddEvidenceModal) showing crop intelligence results.
 *
 * Features:
 *  - Canonical crop identity: declarations, uncalibrated group support, abstention
 *  - Crop Suitability Engine: rainfed/irrigated rankings
 *  - Ambiguity disclosure and hierarchical crop groups
 *  - "Refresh" to reload the canonical posterior
 *  - "Declare Manually" to type a custom crop name
 *  - Declare a candidate without inventing a planting date
 */

import { useState, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sprout,
  Search,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Wheat,
  TreePine,
  Leaf,
  X,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  PenLine,
  Droplets,
  Sun,
  Mountain,
  HelpCircle,
} from "lucide-react";
import {
  buildCropLabelConfirmationPayload,
  getCropCandidateRankingShare,
  humanizeCropAuthority,
} from "@/lib/agribrain/crop-identity-contract.mjs";

interface CropCandidate {
  code: string;
  name: string;
  name_ar: string;
  architecture: string;
  score: number;
  ranking_share?: number | null;          // Ranking diagnostic, NOT probability
  crop_group?: string;
  data_quality_tier?: string;
  breakdown?: {
    temporal: number;
    phenological: number;
    sar: number;
    location: number;
    thermal: number;
  };
}

interface DeclaredCropIdentity {
  code: string;
  name: string;
  name_ar: string;
  architecture: string;
}

interface EoGroupSupport {
  available: boolean;
  code: string | null;
  label: string | null;
  ranking_share: number | null;
  calibrated: false;
  calibration_status: string;
  deepest_supported_level: string;
  status?: string;
  source_class?: string | null;
  admitted_physical_acquisition_count?: number;
  admitted_ndvi_count?: number;
  context_features_may_be_included?: boolean;
}

interface ContextConditionedGroupRanking {
  available: boolean;
  code: string | null;
  label: string | null;
  ranking_share: number | null;
  calibrated: false;
  includes_registry_declaration: boolean;
  includes_temporal_prior: boolean;
  role: string;
}

interface SpeciesConfirmation {
  available: boolean;
  code: string | null;
  reason: string;
}

interface AmbiguityInfo {
  is_ambiguous: boolean;
  between: string[];
  reason: string;
}

interface SuitabilityCandidate {
  code: string;
  name: string;
  name_ar: string;
  score: number;
  suitability_class: string;
  crop_group?: string;
  limiting_factors: Array<{
    factor: string;
    severity: string;
    message: string;
    score_impact: number;
  }>;
}

interface SuitabilityResult {
  rainfed: SuitabilityCandidate[];
  irrigated: SuitabilityCandidate[];
  total_evaluated: number;
  limiting_factors_summary: string[];
}

interface CropIdentityBannerProps {
  plotId: string;
  farmId: string;
  currentCropCode?: string | null;
  currentCropName?: string | null;
  onCropDeclared?: () => void;
}

const ARCH_ICONS: Record<string, typeof Wheat> = {
  cereal: Wheat, maize: Wheat, rice: Wheat,
  legume: Sprout, vegetable: Leaf,
  perennial: TreePine, tropical_tree: TreePine, cotton: Leaf,
};

const ARCH_COLORS: Record<string, string> = {
  cereal: "#f59e0b", maize: "#f59e0b", rice: "#06b6d4",
  legume: "#10b981", vegetable: "#22c55e",
  perennial: "#8b5cf6", tropical_tree: "#8b5cf6", cotton: "#f97316",
};

const BREAKDOWN_METRICS = [
  { key: "temporal", label: "Temporal", icon: "📈" },
  { key: "phenological", label: "Phenology", icon: "🌱" },
  { key: "sar", label: "SAR", icon: "📡" },
  { key: "location", label: "Location", icon: "📍" },
  { key: "thermal", label: "Thermal", icon: "🌡️" },
] as const;

export default function CropIdentityBanner({
  plotId,
  onCropDeclared,
}: CropIdentityBannerProps) {
  const [state, setState] = useState<"idle" | "detecting" | "detected" | "declaring">("idle");
  const [candidates, setCandidates] = useState<CropCandidate[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [manualCrop, setManualCrop] = useState("");
  const [error, setError] = useState("");
  const [mounted, setMounted] = useState(false);
  // Canonical crop-identity authority state
  const [evidenceStrength, setEvidenceStrength] = useState("");
  const [evidenceQualityScore, setEvidenceQualityScore] = useState<number | null>(null);
  const [identityAuthority, setIdentityAuthority] = useState("UNKNOWN");
  const [declaredCrop, setDeclaredCrop] = useState<DeclaredCropIdentity | null>(null);
  const [groupSupport, setGroupSupport] = useState<EoGroupSupport | null>(null);
  const [conditionedGroupRanking, setConditionedGroupRanking] = useState<ContextConditionedGroupRanking | null>(null);
  const [speciesConfirmation, setSpeciesConfirmation] = useState<SpeciesConfirmation | null>(null);
  const [identitySummary, setIdentitySummary] = useState("");
  const [confirmationNote, setConfirmationNote] = useState("");
  const [ambiguity, setAmbiguity] = useState<AmbiguityInfo>({ is_ambiguous: false, between: [], reason: "" });
  const [recommendation, setRecommendation] = useState("");
  // Suitability state
  const [showSuitability, setShowSuitability] = useState(false);
  const [suitabilityLoading, setSuitabilityLoading] = useState(false);
  const [suitability, setSuitability] = useState<SuitabilityResult | null>(null);
  const [suitabilityTab, setSuitabilityTab] = useState<"rainfed" | "irrigated">("rainfed");


  useEffect(() => {
    setMounted(true);
  }, []);

  // Load the canonical posterior for every plot.  A registry declaration must
  // still be shown separately from EO group support and species confirmation.
  useEffect(() => {
    if (plotId && state === "idle") {
      runDetection();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plotId]);

  const runDetection = useCallback(async () => {
    setState("detecting");
    setError("");
    try {
      const res = await fetch("/api/agribrain/crop-identify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plotId }),
      });
      const data = await res.json();
      if (data.success === false && data.error) {
        setError(data.error);
        setState("idle");
        return;
      }
      setCandidates(data.candidates || []);
      const qualityScore = Number(data.evidence_quality?.score);
      const finiteQuality = Number.isFinite(qualityScore) ? qualityScore : null;
      setEvidenceQualityScore(finiteQuality);
      setEvidenceStrength(
        finiteQuality == null ? "UNAVAILABLE"
          : finiteQuality >= 0.70 ? "HIGH"
          : finiteQuality >= 0.35 ? "MEDIUM"
          : "LOW",
      );
      setIdentityAuthority(data.identity_authority || data.authority || "UNKNOWN");
      setDeclaredCrop(data.declared_crop || null);
      setGroupSupport(data.eo_group_support || null);
      setConditionedGroupRanking(data.context_conditioned_group_ranking || null);
      setSpeciesConfirmation(data.independent_species_confirmation || null);
      setIdentitySummary(data.identity_summary || "");
      setAmbiguity(data.ambiguity || { is_ambiguous: false, between: [], reason: "" });
      setRecommendation(data.recommendation || "");
      setState("detected");
    } catch {
      setError("Crop evidence could not be loaded — check connection");
      setState("idle");
    }
  }, [plotId]);

  const acceptCrop = useCallback(async (cropCode: string) => {
    setState("declaring");
    setConfirmationNote("");
    try {
      const payload = buildCropLabelConfirmationPayload({
        plotId,
        cropCode,
      });
      const response = await fetch("/api/agribrain/crop-label", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.success === false) {
        throw new Error(result.error || "Crop identity confirmation failed");
      }

      const matched = candidates.find((candidate) => candidate.code === payload.cropCode);
      setDeclaredCrop({
        code: payload.cropCode,
        name: matched?.name || cropCode.replace(/_/g, " "),
        name_ar: matched?.name_ar || "",
        architecture: matched?.architecture || "unknown",
      });
      setIdentityAuthority("FARMER_CONFIRMED");
      setConfirmationNote(
        "Crop identity saved. Planting date remains unknown until you provide it explicitly.",
      );
      onCropDeclared?.();
      setState("detected");
    } catch (confirmationError) {
      setError(
        confirmationError instanceof Error
          ? confirmationError.message
          : "Failed to set crop",
      );
      setState("detected");
    }
  }, [candidates, plotId, onCropDeclared]);

  const handleManualSubmit = useCallback(() => {
    if (manualCrop.trim()) {
      acceptCrop(manualCrop.trim());
    }
  }, [manualCrop, acceptCrop]);

  const fetchSuitability = useCallback(async () => {
    if (suitability || suitabilityLoading) return; // Already fetched or fetching
    setSuitabilityLoading(true);
    try {
      const res = await fetch("/api/agribrain/crop-suitability", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plotId }),
      });
      const data = await res.json();
      if (data.success !== false) {
        setSuitability({
          rainfed: data.rainfed || [],
          irrigated: data.irrigated || [],
          total_evaluated: data.total_evaluated || 0,
          limiting_factors_summary: data.limiting_factors_summary || [],
        });
      }
    } catch {
      // Non-critical — suitability is optional
    }
    setSuitabilityLoading(false);
  }, [plotId, suitability, suitabilityLoading]);

  // The FAB remains available for both declared and undeclared plots.

  const isDetecting = state === "detecting";
  const isDetected = state === "detected" && (candidates.length > 0 || declaredCrop !== null);
  const top = isDetected ? candidates[0] : null;
  const confColor = speciesConfirmation?.available ? "#10b981" : declaredCrop ? "#818cf8" : "#f59e0b";

  // ── Modal Content (portalled to body) ─────────────────────────────
  const modalContent = (
    <div
      className="fixed inset-0 z-[9999] flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-950/80 backdrop-blur-sm"
      style={{ pointerEvents: "auto" }}
      onClick={(e) => { if (e.target === e.currentTarget) setIsOpen(false); }}
    >
      <div className="bg-[#0f172a] w-full max-w-md sm:rounded-2xl rounded-t-2xl shadow-2xl overflow-hidden border border-slate-800 flex flex-col max-h-[95vh] animate-in slide-in-from-bottom-10 sm:zoom-in-95 duration-200">

        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-indigo-500/15 rounded-lg">
              <Sparkles className="w-4 h-4 text-indigo-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Crop Intelligence</h2>
              <p className="text-xs text-slate-400 mt-0.5">Canonical crop identity and suitability evidence</p>
            </div>
          </div>
          <button onClick={() => setIsOpen(false)} className="p-2 bg-slate-800 rounded-full text-slate-400 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-4 overflow-y-auto flex-1 space-y-5">

          {/* ── DETECTING ─────────────────────── */}
          {isDetecting && (
            <div className="flex flex-col items-center justify-center py-10 gap-4">
              <div className="p-4 bg-indigo-500/10 rounded-2xl">
                <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-white">Loading canonical crop evidence…</p>
                <p className="text-xs text-slate-400 mt-1">Reading the latest published crop posterior; no live species scoring is performed.</p>
              </div>
            </div>
          )}

          {/* ── IDLE / ERROR ───────────────────── */}
          {state === "idle" && (
            <div className="flex flex-col items-center justify-center py-8 gap-4">
              <div className="p-4 bg-amber-500/10 rounded-2xl">
                <AlertTriangle className="w-8 h-8 text-amber-400" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-white">Crop evidence unavailable</p>
                <p className="text-xs text-slate-400 mt-1 max-w-[280px]">
                  {error || "No canonical crop posterior is available yet. Run plot intelligence or declare the crop manually."}
                </p>
              </div>
              <div className="flex gap-3 mt-2">
                <button
                  onClick={runDetection}
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold rounded-xl flex items-center gap-2 shadow-lg shadow-indigo-500/20 transition-all"
                >
                  <Search className="w-4 h-4" />
                  Refresh Crop Evidence
                </button>
                <button
                  onClick={() => setShowManual(true)}
                  className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-bold rounded-xl flex items-center gap-2 border border-slate-700 transition-all"
                >
                  <PenLine className="w-4 h-4" />
                  Declare Manually
                </button>
              </div>
            </div>
          )}

          {/* Declaration, EO support and species confirmation are distinct
              authority claims.  Do not collapse them into one crop score. */}
          {state === "detected" && (declaredCrop || groupSupport || conditionedGroupRanking || speciesConfirmation) && (
            <div className="space-y-2.5">
              <div className="p-3 rounded-xl border border-indigo-500/20 bg-indigo-500/5">
                <p className="text-[10px] font-bold uppercase tracking-wider text-indigo-300">
                  Registry / confirmation authority
                </p>
                {declaredCrop ? (
                  <>
                    <p className="text-sm font-bold text-white mt-1">
                      {declaredCrop.name}
                      {declaredCrop.name_ar ? (
                        <span className="text-slate-400 font-normal"> · {declaredCrop.name_ar}</span>
                      ) : null}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-1">
                      {humanizeCropAuthority(identityAuthority)}. This is not an independent satellite species detection.
                    </p>
                  </>
                ) : (
                  <p className="text-xs text-slate-400 mt-1">No crop species is declared for this plot.</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-3 rounded-xl border border-amber-500/20 bg-amber-500/5">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-amber-300">EO group support</p>
                  <p className="text-xs font-semibold text-white mt-1">
                    {groupSupport?.available && groupSupport.label ? groupSupport.label : "Unavailable"}
                  </p>
                  <p className="text-[9px] text-slate-500 mt-1">
                    {groupSupport?.available && groupSupport.ranking_share != null
                      ? `${(groupSupport.ranking_share * 100).toFixed(1)}% EO-informed model share · ${groupSupport.admitted_physical_acquisition_count || 0} physical acquisitions`
                      : "No independent group support from admitted physical observations"}
                  </p>
                </div>
                <div className="p-3 rounded-xl border border-slate-600/30 bg-slate-800/30">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-300">Species confirmation</p>
                  <p className={`text-xs font-semibold mt-1 ${speciesConfirmation?.available ? "text-emerald-400" : "text-amber-400"}`}>
                    {speciesConfirmation?.available && speciesConfirmation.code
                      ? speciesConfirmation.code.replaceAll("_", " ")
                      : "Not available"}
                  </p>
                  <p className="text-[9px] text-slate-500 mt-1">
                    {speciesConfirmation?.reason || "No validated species posterior is published."}
                  </p>
                </div>
              </div>

              {conditionedGroupRanking?.available && (
                <div className="p-3 rounded-xl border border-slate-600/30 bg-slate-800/20">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Context-conditioned pipeline ranking
                  </p>
                  <p className="text-xs font-semibold text-slate-200 mt-1">
                    {conditionedGroupRanking.label || "Unresolved"}
                    {conditionedGroupRanking.ranking_share != null
                      ? ` · ${(conditionedGroupRanking.ranking_share * 100).toFixed(1)}%`
                      : ""}
                  </p>
                  <p className="text-[9px] text-slate-500 mt-1">
                    Used for ASMAE conditioning; not independent EO evidence.
                    {conditionedGroupRanking.includes_registry_declaration ? " Includes the crop declaration prior." : ""}
                    {conditionedGroupRanking.includes_temporal_prior ? " Includes a previous-cycle-bounded belief prior." : ""}
                  </p>
                </div>
              )}

              {identitySummary && (
                <p className="text-[11px] leading-relaxed text-slate-300 px-1">{identitySummary}</p>
              )}
              {confirmationNote && (
                <div className="p-2.5 rounded-lg border border-emerald-500/20 bg-emerald-500/8 text-[10px] text-emerald-300">
                  {confirmationNote}
                </div>
              )}
            </div>
          )}

          {/* ── DETECTED ──────────────────────── */}
          {isDetected && top && (() => {
            const ArchIcon = ARCH_ICONS[top.architecture] || Sprout;
            const archColor = ARCH_COLORS[top.architecture] || "#818cf8";

            return (
              <>
                {/* Published-evidence badge */}
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-[10px] font-bold px-2.5 py-1 rounded-lg border text-slate-300 border-slate-600/30 bg-slate-700/30">
                    Canonical posterior
                  </span>
                  <span className="text-[10px] text-slate-500">
                    EO evidence: <span className={`font-bold ${
                      evidenceStrength === "HIGH" ? "text-emerald-400" 
                      : evidenceStrength === "MEDIUM" ? "text-amber-400" 
                      : "text-red-400"
                    }`}>
                      {evidenceStrength}{evidenceQualityScore != null ? ` (${evidenceQualityScore.toFixed(2)})` : ""}
                    </span>
                  </span>
                </div>

                {/* Recommendation */}
                {recommendation && (
                  <p className="text-xs text-slate-300 mb-3 leading-relaxed px-0.5 italic">
                    {recommendation}
                  </p>
                )}

                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 px-1">
                  Heuristic species ranking — not an independent confirmation
                </p>

                {/* Top ranking diagnostic */}
                <div className="p-4 rounded-xl border border-slate-700/50 bg-slate-800/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div
                      className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ border: `1px solid ${archColor}33`, background: `${archColor}15` }}
                    >
                      <ArchIcon className="w-5 h-5" style={{ color: archColor }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-base font-bold" style={{ color: archColor }}>{top.name}</span>
                        {/* Show candidate share when available, ranking score as fallback */}
                        {(() => {
                          const share = getCropCandidateRankingShare(top);
                          return share != null ? (
                            <span
                              className="text-[10px] font-bold px-2 py-0.5 rounded-md border uppercase tracking-wider"
                              style={{ color: confColor, borderColor: `${confColor}44`, background: `${confColor}10` }}
                            >
                              Ranking share: {(share * 100).toFixed(0)}%
                            </span>
                          ) : (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-md border text-slate-400 border-slate-600/30 bg-slate-700/30 uppercase tracking-wider">
                              Uncalibrated ranking
                            </span>
                          );
                        })()}
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {top.name_ar}
                        {top.crop_group && top.crop_group !== "unknown" && (
                          <> • <span className="text-indigo-400">{top.crop_group.replace(/_/g, ' ')}</span> group</>
                        )}
                        {' '} • not a calibrated species probability
                      </p>
                      {/* Ranking score as secondary detail */}
                      <p className="text-[10px] text-slate-500 mt-0.5">
                        Ranking score: {top.score.toFixed(4)}
                        {top.data_quality_tier && (
                          <> • Data: <span className={top.data_quality_tier === "curated" ? "text-emerald-500" : "text-slate-500"}>{top.data_quality_tier}</span></>
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Ambiguity Warning */}
                  {ambiguity.is_ambiguous && (
                    <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/8 border border-amber-500/20 mb-3">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-[11px] font-bold text-amber-400">
                          Ambiguous between: {ambiguity.between.join(', ')}
                        </p>
                        <p className="text-[10px] text-amber-300/60 mt-0.5">{ambiguity.reason}</p>
                      </div>
                    </div>
                  )}

                  {/* Score breakdown */}
                  {top.breakdown && (
                    <>
                      <button
                        onClick={() => setShowBreakdown(!showBreakdown)}
                        className="flex items-center gap-1.5 text-[10px] font-bold text-slate-500 uppercase tracking-wider hover:text-slate-300 transition-colors mb-2"
                      >
                        <ChevronRight className={`w-3 h-3 transition-transform ${showBreakdown ? "rotate-90" : ""}`} />
                        Score Breakdown
                      </button>
                      <AnimatePresence>
                        {showBreakdown && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="space-y-2 pt-1 pb-1">
                              {BREAKDOWN_METRICS.map((m) => {
                                const val = (top.breakdown as Record<string, number>)?.[m.key] ?? 0;
                                return (
                                  <div key={m.key} className="flex items-center gap-2">
                                    <span className="text-xs w-4 text-center">{m.icon}</span>
                                    <span className="text-[11px] text-slate-400 w-16">{m.label}</span>
                                    <div className="flex-1 h-1.5 bg-slate-700/60 rounded-full overflow-hidden">
                                      <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-indigo-400" style={{ width: `${val * 100}%` }} />
                                    </div>
                                    <span className="text-[10px] font-mono font-bold text-slate-400 w-8 text-right">
                                      {(val * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </>
                  )}
                </div>

                {/* All Candidates */}
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 block">
                    Heuristic species ranking (not calibrated)
                  </label>
                  <div className="space-y-1.5">
                    {candidates.map((c, i) => {
                      const CIcon = ARCH_ICONS[c.architecture] || Sprout;
                      const cColor = ARCH_COLORS[c.architecture] || "#64748b";
                      return (
                        <div
                          key={c.code}
                          className="flex items-center gap-2.5 p-2.5 rounded-xl bg-slate-800/40 border border-slate-700/30 hover:bg-slate-800/60 transition-colors group"
                        >
                          <span className="text-[10px] font-mono font-bold text-slate-500 w-5">#{i + 1}</span>
                          <CIcon className="w-4 h-4 flex-shrink-0" style={{ color: cColor }} />
                          <div className="flex-1 min-w-0">
                            <span className="text-sm font-medium text-white truncate block">{c.name}</span>
                            <span className="text-[9px] text-slate-500">{c.crop_group?.replace(/_/g, ' ') || ''}</span>
                          </div>
                          {/* Show candidate share bar or ranking score bar */}
                          {(() => {
                            const share = getCropCandidateRankingShare(c);
                            const displayVal = share != null ? share : c.score;
                            const maxVal = share != null ? 1.0 : (candidates[0]?.score || 1);
                            const barPct = (displayVal / maxVal) * 100;
                            return (
                              <>
                                <div className="w-14 h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
                                  <div className="h-full rounded-full" style={{ width: `${Math.min(100, barPct)}%`, background: cColor }} />
                                </div>
                                <span className="text-[11px] font-mono font-bold text-slate-400 w-11 text-right">
                                  {share != null ? `${(share * 100).toFixed(0)}%` : `${c.score.toFixed(2)}`}
                                </span>
                              </>
                            );
                          })()}
                          <button
                            onClick={() => acceptCrop(c.code)}
                            className="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-slate-700/50 border border-slate-600/30 text-slate-400 hover:bg-emerald-500/15 hover:border-emerald-500/30 hover:text-emerald-400 transition-all opacity-0 group-hover:opacity-100"
                          >
                            Declare
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* ── BEST SUITED CROPS (Suitability Engine) ────── */}
                <div className="mt-1">
                  <button
                    onClick={() => {
                      setShowSuitability(!showSuitability);
                      if (!suitability && !suitabilityLoading) fetchSuitability();
                    }}
                    className="flex items-center gap-2 w-full text-left py-2.5 px-3 rounded-xl bg-slate-800/30 border border-slate-700/30 hover:bg-slate-800/50 transition-colors"
                  >
                    <Mountain className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-bold text-slate-300 flex-1">Best Suited Crops</span>
                    <span className="text-[10px] text-slate-500">Biophysical suitability</span>
                    <ChevronDown className={`w-3.5 h-3.5 text-slate-500 transition-transform ${showSuitability ? "rotate-180" : ""}`} />
                  </button>

                  <AnimatePresence>
                    {showSuitability && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="pt-3 space-y-3">
                          {/* Loading */}
                          {suitabilityLoading && (
                            <div className="flex items-center justify-center py-6 gap-2">
                              <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
                              <span className="text-xs text-slate-400">Evaluating suitability...</span>
                            </div>
                          )}

                          {/* Results */}
                          {suitability && (
                            <>
                              {/* Site-level warnings */}
                              {suitability.limiting_factors_summary.length > 0 && (
                                <div className="flex flex-wrap gap-1.5">
                                  {suitability.limiting_factors_summary.map((f, i) => (
                                    <span key={i} className="text-[9px] font-bold px-2 py-1 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-400">
                                      {f}
                                    </span>
                                  ))}
                                </div>
                              )}

                              {/* Rainfed / Irrigated tabs */}
                              <div className="flex gap-1 p-0.5 bg-slate-800/50 rounded-lg">
                                <button
                                  onClick={() => setSuitabilityTab("rainfed")}
                                  className={`flex-1 py-1.5 rounded-md text-[11px] font-bold flex items-center justify-center gap-1.5 transition-all ${
                                    suitabilityTab === "rainfed"
                                      ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                                      : "text-slate-500 hover:text-slate-300 border border-transparent"
                                  }`}
                                >
                                  <Sun className="w-3 h-3" /> Rainfed
                                </button>
                                <button
                                  onClick={() => setSuitabilityTab("irrigated")}
                                  className={`flex-1 py-1.5 rounded-md text-[11px] font-bold flex items-center justify-center gap-1.5 transition-all ${
                                    suitabilityTab === "irrigated"
                                      ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
                                      : "text-slate-500 hover:text-slate-300 border border-transparent"
                                  }`}
                                >
                                  <Droplets className="w-3 h-3" /> Irrigated
                                </button>
                              </div>

                              {/* Suitability list */}
                              <div className="space-y-1.5">
                                {(suitabilityTab === "rainfed" ? suitability.rainfed : suitability.irrigated)
                                  .slice(0, 8)
                                  .map((s, i) => {
                                    const classColor =
                                      s.suitability_class === "S1" ? "#10b981" :
                                      s.suitability_class === "S2" ? "#f59e0b" :
                                      s.suitability_class === "S3" ? "#f97316" : "#ef4444";
                                    return (
                                      <div
                                        key={s.code}
                                        className="flex items-center gap-2 p-2 rounded-lg bg-slate-800/30 border border-slate-700/20"
                                      >
                                        <span className="text-[10px] font-mono font-bold text-slate-500 w-4">
                                          {i + 1}
                                        </span>
                                        <span
                                          className="text-[10px] font-black px-1.5 py-0.5 rounded"
                                          style={{ color: classColor, background: `${classColor}15`, border: `1px solid ${classColor}30` }}
                                        >
                                          {s.suitability_class}
                                        </span>
                                        <div className="flex-1 min-w-0">
                                          <span className="text-[12px] font-medium text-white truncate block">{s.name}</span>
                                          {s.limiting_factors.length > 0 && (
                                            <span className="text-[9px] text-amber-400/70 truncate block">
                                              {s.limiting_factors.map(l => l.message).join(' | ')}
                                            </span>
                                          )}
                                        </div>
                                        <span className="text-[10px] font-mono font-bold text-slate-500">
                                          {s.score}
                                        </span>
                                      </div>
                                    );
                                  })}
                              </div>

                              <p className="text-[10px] text-slate-600 text-center">
                                {suitability.total_evaluated} crops evaluated • FAO GAEZ methodology
                              </p>
                            </>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Action buttons: refresh canonical evidence + manual declaration */}
                <div className="flex gap-3 pt-1">
                  <button
                    onClick={runDetection}
                    className="flex-1 py-2.5 rounded-xl text-sm font-bold flex items-center justify-center gap-2 bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white transition-all"
                  >
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                  </button>
                  <button
                    onClick={() => setShowManual(!showManual)}
                    className="flex-1 py-2.5 rounded-xl text-sm font-bold flex items-center justify-center gap-2 bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white transition-all"
                  >
                    <PenLine className="w-4 h-4" />
                    Declare Manually
                  </button>
                </div>
              </>
            );
          })()}

          {/* ── Manual Declaration Input ────────── */}
          <AnimatePresence>
            {showManual && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="p-4 rounded-xl border border-slate-700/50 bg-slate-800/30">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 block">
                    Enter Crop Name
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={manualCrop}
                      onChange={(e) => setManualCrop(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") handleManualSubmit(); }}
                      placeholder="e.g. Wheat, Tomato, Olive..."
                      className="flex-1 bg-slate-900 border border-slate-700 focus:border-indigo-500 rounded-xl px-3 py-2.5 text-sm text-white placeholder-slate-600 outline-none"
                      autoFocus
                    />
                    <button
                      onClick={handleManualSubmit}
                      disabled={!manualCrop.trim() || state === "declaring"}
                      className={`px-4 py-2.5 rounded-xl font-bold text-sm flex items-center gap-2 transition-all ${
                        !manualCrop.trim()
                          ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                          : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20"
                      }`}
                    >
                      {state === "declaring" ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4" />
                      )}
                      Set
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer */}
        {(state === "detected" || state === "declaring") && top && !declaredCrop && (
          <div className="p-4 border-t border-slate-800 bg-slate-900/50 space-y-2">
            <button
              disabled={state === "declaring"}
              onClick={() => acceptCrop(top.code)}
              className={`w-full py-3.5 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${
                state === "declaring"
                  ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                  : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20"
              }`}
            >
              {state === "declaring" ? (
                <><Loader2 className="w-5 h-5 animate-spin" /> Setting crop…</>
              ) : (
                <><CheckCircle2 className="w-5 h-5" /> Declare {top.name}</>
              )}
            </button>
            <p className="text-[10px] text-slate-500 text-center">
              This records crop identity only. Planting date remains unknown unless you provide it separately.
            </p>
            <div className="flex gap-2">
              <button
                disabled={state === "declaring"}
                onClick={() => acceptCrop("fallow")}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 bg-slate-850 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-all disabled:opacity-50"
              >
                <Mountain className="w-3.5 h-3.5 text-emerald-400" />
                Mark Fallow
              </button>
              <button
                disabled={state === "declaring"}
                onClick={() => acceptCrop("mixed_unknown")}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 bg-slate-850 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-all disabled:opacity-50"
              >
                <HelpCircle className="w-3.5 h-3.5 text-amber-400" />
                Mark Unknown
              </button>
            </div>
          </div>
        )}

        {state === "idle" && !showManual && (
          <div className="p-4 border-t border-slate-800 bg-slate-900/50">
            <button
              onClick={() => setIsOpen(false)}
              className="w-full py-3 rounded-xl font-bold text-slate-400 bg-slate-800 hover:bg-slate-700 transition-all"
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* ── FAB Button (same style as Evidence button) ─── */}
      <button
        onClick={() => setIsOpen(true)}
        id="crop-detect-toggle"
        style={{
          width: "56px",
          height: "56px",
          borderRadius: "10px",
          border: isOpen ? "1px solid rgba(148,163,184,0.4)" : "1px solid rgba(71,85,105,0.25)",
          background: isOpen ? "rgba(148,163,184,0.1)" : "rgba(8,12,25,0.92)",
          backdropFilter: "blur(24px)",
          color: isOpen ? "#f8fafc" : "#cbd5e1",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 -2px 20px rgba(0,0,0,0.35), 0 0 0 1px rgba(71,85,105,0.06) inset",
          transition: "all 0.15s ease",
          position: "relative",
        }}
        title="Crop Intelligence"
      >
        {isDetecting ? (
          <Loader2 size={22} className="animate-spin" style={{ color: "#818cf8" }} />
        ) : (
          <Sprout size={22} style={{ color: isOpen ? "#e2e8f0" : "#cbd5e1", opacity: isOpen ? 1 : 0.9 }} />
        )}

        {/* Status indicator dot */}
        {isDetected && (
          <span style={{
            position: "absolute", top: 7, right: 7,
            width: 7, height: 7, borderRadius: "50%",
            background: confColor,
            boxShadow: `0 0 5px ${confColor}`,
          }} />
        )}
        {!isDetected && !isDetecting && (
          <span style={{
            position: "absolute", top: 7, right: 7,
            width: 7, height: 7, borderRadius: "50%",
            background: "#f59e0b",
            boxShadow: "0 0 5px #f59e0b",
          }} />
        )}
      </button>

      {/* ── Modal (portalled to body) ─── */}
      {mounted && isOpen && createPortal(modalContent, document.body)}
    </>
  );
}
