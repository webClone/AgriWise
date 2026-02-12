"use client";

import { useState } from "react";
import { Plus, Beaker, FileText, MapPin, Ruler, Trash2, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import SoilAnalysisUploadModal from "./SoilAnalysisUploadModal";

interface SoilAnalysisHistoryProps {
  plotId: string;
  analyses: any[];
}

function getAgeBadge(dateStr: string): { label: string; color: string; dot: string } {
  const ageMs = Date.now() - new Date(dateStr).getTime();
  const years = ageMs / (1000 * 60 * 60 * 24 * 365);

  if (years < 1) return { label: "Current", color: "bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-800", dot: "bg-green-500" };
  if (years < 3) return { label: "Aging", color: "bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800", dot: "bg-amber-500" };
  return { label: "Outdated", color: "bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800", dot: "bg-red-500" };
}

function getAgeTooltip(dateStr: string): string {
  const ageMs = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(ageMs / (1000 * 60 * 60 * 24));
  if (days < 30) return `${days} days old`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} month${months > 1 ? "s" : ""} old`;
  const years = (days / 365).toFixed(1);
  return `${years} years old`;
}

export default function SoilAnalysisHistory({ plotId, analyses: initialAnalyses }: SoilAnalysisHistoryProps) {
  const [analyses, setAnalyses] = useState(initialAnalyses);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(analyses[0]?.id || null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleSuccess = () => {
    window.location.reload();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this soil analysis record?")) return;
    setDeletingId(id);
    try {
      const res = await fetch(`/api/soil-analysis/${id}`, { method: "DELETE" });
      if (res.ok) {
        setAnalyses((prev) => prev.filter((a) => a.id !== id));
      } else {
        alert("Failed to delete.");
      }
    } catch {
      alert("Network error.");
    }
    setDeletingId(null);
  };

  return (
    <div className="space-y-5">

      {/* Header */}
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <Beaker className="text-amber-600" size={18} />
          Soil Analysis History
          {analyses.length > 0 && (
            <span className="text-xs font-normal text-slate-400 ml-1">
              ({analyses.length} record{analyses.length !== 1 ? "s" : ""})
            </span>
          )}
        </h3>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-1.5 text-xs font-medium bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 px-3 py-1.5 rounded-full border border-amber-100 dark:border-amber-800 hover:bg-amber-100 dark:hover:bg-amber-900/40 transition-colors"
        >
          <Plus size={14} />
          Log Report
        </button>
      </div>

      {/* Records */}
      {analyses.length > 0 ? (
        <div className="space-y-3">
          {analyses.map((item, idx) => {
            const badge = getAgeBadge(item.date);
            const isExpanded = expandedId === item.id;
            const isLatest = idx === 0;

            return (
              <div
                key={item.id}
                className={`rounded-xl border overflow-hidden transition-all ${
                  isLatest
                    ? "border-amber-200 dark:border-amber-800/50 shadow-sm"
                    : "border-slate-200 dark:border-slate-800"
                }`}
              >
                {/* Header Row */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : item.id)}
                  className={`w-full flex items-center justify-between p-4 text-left transition-colors ${
                    isLatest
                      ? "bg-amber-50/50 dark:bg-amber-900/5 hover:bg-amber-50 dark:hover:bg-amber-900/10"
                      : "bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                      isLatest ? "bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400" : "bg-slate-100 dark:bg-slate-800 text-slate-400"
                    }`}>
                      <Beaker size={18} />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
                          {new Date(item.date).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}
                        </span>
                        {isLatest && (
                          <span className="text-[10px] font-medium px-1.5 py-0.5 bg-amber-500 text-white rounded">LATEST</span>
                        )}
                        {/* Age Badge */}
                        <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border ${badge.color}`} title={getAgeTooltip(item.date)}>
                          <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} />
                          {badge.label}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 mt-1 text-xs text-slate-500 dark:text-slate-400 flex-wrap">
                        {/* Depth */}
                        {(item.depthFrom != null || item.depthTo != null) && (
                          <span className="flex items-center gap-1">
                            <Ruler size={11} />
                            {item.depthFrom ?? 0}–{item.depthTo ?? "?"} cm
                          </span>
                        )}
                        {/* Location */}
                        {item.samplingLocation && (
                          <span className="flex items-center gap-1">
                            <MapPin size={11} />
                            {item.samplingLocation}
                          </span>
                        )}
                        {/* Quick values */}
                        <span>pH: {item.ph ?? "–"}</span>
                        <span>EC: {item.ec ?? "–"}</span>
                        {item.texture && <span>{item.texture}</span>}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 ml-3 shrink-0">
                    {item.fileUrl && (
                      <a
                        href={item.fileUrl}
                        target="_blank"
                        onClick={(e) => e.stopPropagation()}
                        className="text-xs flex items-center gap-1 text-amber-600 hover:underline"
                      >
                        <FileText size={12} /> PDF
                      </a>
                    )}
                    {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                  </div>
                </button>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="px-4 pb-4 pt-2 border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">
                    
                    {/* Sampling Context */}
                    {(item.depthFrom != null || item.samplingLocation || item.notes) && (
                      <div className="mb-4 p-3 bg-slate-50 dark:bg-slate-950 rounded-lg text-xs space-y-1">
                        {(item.depthFrom != null || item.depthTo != null) && (
                          <p className="text-slate-600 dark:text-slate-400 flex items-center gap-2">
                            <Ruler size={12} className="text-slate-400 shrink-0" />
                            <span><strong>Sampling Depth:</strong> {item.depthFrom ?? 0}–{item.depthTo ?? "?"} cm</span>
                          </p>
                        )}
                        {item.samplingLocation && (
                          <p className="text-slate-600 dark:text-slate-400 flex items-center gap-2">
                            <MapPin size={12} className="text-slate-400 shrink-0" />
                            <span><strong>Location:</strong> {item.samplingLocation}</span>
                          </p>
                        )}
                        {item.notes && (
                          <p className="text-slate-500 dark:text-slate-500 mt-1 italic">{item.notes}</p>
                        )}
                      </div>
                    )}

                    {/* Value Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <ValueCard label="pH" value={item.ph} />
                      <ValueCard label="EC" value={item.ec} unit="dS/m" />
                      <ValueCard label="OM" value={item.organicMatter} unit="%" />
                      <div className="bg-slate-50 dark:bg-slate-950 p-3 rounded-lg border border-slate-100 dark:border-slate-800">
                        <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">NPK</span>
                        <div className="flex items-baseline gap-1 text-sm font-medium text-slate-600 dark:text-slate-300">
                          <span>{item.nitrogen ?? "–"}</span>
                          <span className="text-slate-300 dark:text-slate-600">/</span>
                          <span>{item.phosphorus ?? "–"}</span>
                          <span className="text-slate-300 dark:text-slate-600">/</span>
                          <span>{item.potassium ?? "–"}</span>
                        </div>
                        <span className="text-[9px] text-slate-400">mg/kg</span>
                      </div>
                    </div>

                    {/* Texture */}
                    {item.texture && (
                      <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                        <strong>Texture:</strong> {item.texture}
                      </div>
                    )}

                    {/* Delete */}
                    <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 flex justify-end">
                      <button
                        onClick={() => handleDelete(item.id)}
                        disabled={deletingId === item.id}
                        className="text-xs text-red-500 hover:text-red-600 flex items-center gap-1 disabled:opacity-50"
                      >
                        {deletingId === item.id ? <Loader2 className="animate-spin" size={12} /> : <Trash2 size={12} />}
                        Delete Record
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-10 rounded-xl border border-dashed border-slate-300 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="inline-flex p-3 rounded-full bg-slate-100 dark:bg-slate-900 text-slate-400 mb-3">
            <Beaker size={24} />
          </div>
          <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">No soil analysis records</p>
          <p className="text-slate-400 dark:text-slate-500 text-xs mt-1">Log a lab report to track soil health over time.</p>
          <button
            onClick={() => setIsModalOpen(true)}
            className="mt-4 text-xs text-amber-600 hover:text-amber-700 font-medium underline underline-offset-2"
          >
            Log your first report
          </button>
        </div>
      )}

      {isModalOpen && (
        <SoilAnalysisUploadModal
          plotId={plotId}
          onClose={() => setIsModalOpen(false)}
          onSuccess={handleSuccess}
        />
      )}
    </div>
  );
}

function ValueCard({ label, value, unit }: { label: string; value: number | null; unit?: string }) {
  return (
    <div className="bg-slate-50 dark:bg-slate-950 p-3 rounded-lg border border-slate-100 dark:border-slate-800">
      <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1">{label}</span>
      <span className="text-lg font-bold text-slate-700 dark:text-slate-200">
        {value != null ? value : "–"}
        {unit && value != null && <span className="text-xs font-normal text-slate-400 ml-1">{unit}</span>}
      </span>
    </div>
  );
}
