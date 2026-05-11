"use client";

import { 
  Settings2, 
  Activity,
  Droplets, 
  Info,
  ChevronRight,
  Plus,
  Check,
  Loader2
} from "lucide-react";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";

interface DecisionConfigurationProps {
  initialIrrigation: string | null;
  initialSoilType: string | null;
}

const IRRIGATION_OPTIONS = ["Rainfed", "Drip", "Sprinkler", "Furrow", "Pivot", "Flood"];
const SOIL_OPTIONS = ["Sandy", "Sandy Loam", "Loam", "Silt Loam", "Clay Loam", "Clay"];

export default function DecisionConfiguration({ 
  initialIrrigation,
  initialSoilType 
}: DecisionConfigurationProps) {
  const params = useParams();
  const plotId = params?.plotId as string;

  const [irrigation, setIrrigation] = useState(initialIrrigation || "");
  const [soilType, setSoilType] = useState(initialSoilType || "");
  const [editingField, setEditingField] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showRecalibrating, setShowRecalibrating] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShowRecalibrating(true), 2000);
    const timer2 = setTimeout(() => setShowRecalibrating(false), 5000);
    return () => { clearTimeout(timer); clearTimeout(timer2); };
  }, []);

  const handleSave = async (field: string, value: string) => {
    setSaving(true);
    try {
      const updateData: Record<string, string> = {};
      if (field === "irrigation") updateData.irrigation = value;
      if (field === "soilType") updateData.soilType = value;

      const res = await fetch(`/api/plots/${plotId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updateData),
      });

      if (res.ok) {
        if (field === "irrigation") setIrrigation(value);
        if (field === "soilType") setSoilType(value);
        setEditingField(null);
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      } else {
        console.error("Save failed");
      }
    } catch (err) {
      console.error("Save error:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.06] overflow-hidden relative" style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.04) 0%, rgba(11,16,21,0.9) 40%)" }}>
      <div className="absolute top-0 right-0 p-3 opacity-[0.03] text-white">
        <Settings2 size={80} />
      </div>
      <div className="px-6 py-4 border-b border-white/[0.04] relative z-10">
        <h3 className="font-semibold text-white flex items-center gap-2 text-sm">
          <Settings2 className="text-indigo-400" size={18} />
          Decision Configuration
        </h3>
        <div className="flex items-center justify-between mt-1">
          <p className="text-[10px] text-slate-600 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse" />
            Used in irrigation, nutrient & yield models
          </p>
          {(showRecalibrating || saved) && (
            <span className={`text-[9px] font-bold flex items-center gap-1 animate-pulse px-2 py-0.5 rounded-full border ${
              saved ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" : "text-indigo-400 bg-indigo-500/10 border-indigo-500/20"
            }`}>
              {saved ? <><Check size={10} /> Saved & Synced</> : <><Activity size={10} /> Model Recalibrated</>}
            </span>
          )}
        </div>
      </div>
      <div className="p-5 space-y-3">
        {/* Irrigation */}
        <div className="p-2 rounded-xl hover:bg-white/[0.02] transition-colors">
          <div className="flex items-center justify-between cursor-pointer" onClick={() => setEditingField(editingField === "irrigation" ? null : "irrigation")}>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg border border-indigo-500/15">
                <Droplets size={16} />
              </div>
              <div>
                <p className="text-[9px] text-slate-600 uppercase font-bold tracking-widest mb-0.5">Irrigation</p>
                <p className="text-sm font-semibold text-white">{irrigation || "Not Set"}</p>
              </div>
            </div>
            {saving ? <Loader2 size={16} className="text-indigo-400 animate-spin" /> : <ChevronRight size={16} className={`transition-transform ${editingField === "irrigation" ? "rotate-90 text-indigo-400" : "text-slate-700"}`} />}
          </div>
          {editingField === "irrigation" && (
            <div className="mt-3 grid grid-cols-3 gap-1.5 animate-in fade-in slide-in-from-top-2 duration-200">
              {IRRIGATION_OPTIONS.map(opt => (
                <button key={opt} onClick={() => handleSave("irrigation", opt)}
                  className={`px-2 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider border transition-all ${
                    irrigation === opt ? "bg-indigo-500/15 text-indigo-400 border-indigo-500/20" : "text-slate-500 border-white/[0.04] hover:border-indigo-500/20 hover:text-indigo-300"
                  }`}>{opt}</button>
              ))}
            </div>
          )}
        </div>

        {/* Soil Type */}
        <div className="p-2 rounded-xl hover:bg-white/[0.02] transition-colors">
          <div className="flex items-center justify-between cursor-pointer" onClick={() => setEditingField(editingField === "soilType" ? null : "soilType")}>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500/10 text-amber-400 rounded-lg border border-amber-500/15">
                <Info size={16} />
              </div>
              <div>
                <p className="text-[9px] text-slate-600 uppercase font-bold tracking-widest mb-0.5">Soil Type</p>
                <p className="text-sm font-semibold text-white">{soilType || "Undetermined"}</p>
              </div>
            </div>
            {saving ? <Loader2 size={16} className="text-amber-400 animate-spin" /> : <ChevronRight size={16} className={`transition-transform ${editingField === "soilType" ? "rotate-90 text-amber-400" : "text-slate-700"}`} />}
          </div>
          {editingField === "soilType" && (
            <div className="mt-3 grid grid-cols-3 gap-1.5 animate-in fade-in slide-in-from-top-2 duration-200">
              {SOIL_OPTIONS.map(opt => (
                <button key={opt} onClick={() => handleSave("soilType", opt)}
                  className={`px-2 py-2 rounded-lg text-[10px] font-bold uppercase tracking-wider border transition-all ${
                    soilType === opt ? "bg-amber-500/15 text-amber-400 border-amber-500/20" : "text-slate-500 border-white/[0.04] hover:border-amber-500/20 hover:text-amber-300"
                  }`}>{opt}</button>
              ))}
            </div>
          )}
        </div>

        {/* Static management params (future: make editable) */}
        <div className="grid grid-cols-2 gap-2 pt-3 border-t border-white/[0.04]">
          {[
            { label: "Fertigation", value: irrigation ? (irrigation === "Drip" ? "Possible" : "Manual") : "—" },
            { label: "Drainage", value: "Natural" },
          ].map(item => (
            <div key={item.label} className="p-2.5 bg-white/[0.02] rounded-xl border border-white/[0.04]">
              <p className="text-[8px] text-slate-600 uppercase font-bold tracking-widest mb-1">{item.label}</p>
              <p className="text-xs font-medium text-slate-300">{item.value}</p>
            </div>
          ))}
        </div>

        <button className="w-full mt-1 py-2.5 text-xs font-bold text-slate-600 hover:text-indigo-400 transition-colors border border-dashed border-white/[0.06] rounded-xl flex items-center justify-center gap-1 hover:border-indigo-500/20 hover:bg-indigo-500/5">
          <Plus size={14} /> Add Management Parameter
        </button>
      </div>
    </div>
  );
}
