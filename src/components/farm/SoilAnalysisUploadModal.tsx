"use client";

import { useState } from "react";
import { addSoilAnalysis } from "@/lib/actions";
import { Loader2, Upload, X, Beaker, Calendar, MapPin, Ruler } from "lucide-react";

interface SoilAnalysisUploadModalProps {
  plotId: string;
  onClose: () => void;
  onSuccess: () => void;
}

const LOCATION_PRESETS = ["Whole Plot", "Zone A", "Zone B", "Zone C", "Center", "Edge/Border", "Custom"];

export default function SoilAnalysisUploadModal({ plotId, onClose, onSuccess }: SoilAnalysisUploadModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Form State
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [depthFrom, setDepthFrom] = useState("0");
  const [depthTo, setDepthTo] = useState("30");
  const [samplingLocation, setSamplingLocation] = useState("");
  const [customLocation, setCustomLocation] = useState("");
  const [ph, setPh] = useState("");
  const [ec, setEc] = useState("");
  const [organicMatter, setOrganicMatter] = useState("");
  const [nitrogen, setNitrogen] = useState("");
  const [phosphorus, setPhosphorus] = useState("");
  const [potassium, setPotassium] = useState("");
  const [texture, setTexture] = useState("");
  const [notes, setNotes] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const locationValue = samplingLocation === "Custom" ? customLocation : samplingLocation;

    const data = {
      date: new Date(date),
      depthFrom: depthFrom ? parseInt(depthFrom) : null,
      depthTo: depthTo ? parseInt(depthTo) : null,
      samplingLocation: locationValue || null,
      notes: notes || null,
      ph: ph ? parseFloat(ph) : null,
      ec: ec ? parseFloat(ec) : null,
      organicMatter: organicMatter ? parseFloat(organicMatter) : null,
      nitrogen: nitrogen ? parseFloat(nitrogen) : null,
      phosphorus: phosphorus ? parseFloat(phosphorus) : null,
      potassium: potassium ? parseFloat(potassium) : null,
      texture: texture || null,
    };

    const res = await addSoilAnalysis(plotId, data);

    if (res.success) {
      onSuccess();
      onClose();
    } else {
      setError(res.error || "Failed to add soil analysis.");
    }
    setLoading(false);
  };

  const inputClass = "w-full px-3 py-2 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-amber-500 focus:border-transparent text-sm";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl max-w-2xl w-full border border-slate-200 dark:border-slate-800 overflow-hidden scale-in-center max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-950 sticky top-0 z-10">
          <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
            <Beaker size={18} className="text-amber-600" />
            Log Soil Analysis
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">

          <div className="bg-amber-50 dark:bg-amber-900/10 p-4 rounded-lg border border-amber-100 dark:border-amber-800/50 flex gap-3 text-sm text-amber-800 dark:text-amber-200">
            <Upload size={20} className="shrink-0" />
            <div>
              <p className="font-medium">Have a PDF report?</p>
              <p className="opacity-80 mt-1">OCR Upload is coming soon. For now, please transcribe the key values below.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

            {/* Sampling Context */}
            <div className="space-y-4">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Sampling Context</h4>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  <Calendar size={14} className="inline mr-1" />
                  Date of Sampling
                </label>
                <input
                  type="date"
                  required
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className={inputClass}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  <Ruler size={14} className="inline mr-1" />
                  Sampling Depth (cm)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="0"
                    value={depthFrom}
                    onChange={(e) => setDepthFrom(e.target.value)}
                    placeholder="0"
                    className={inputClass}
                  />
                  <span className="text-slate-400 text-sm">to</span>
                  <input
                    type="number"
                    min="0"
                    value={depthTo}
                    onChange={(e) => setDepthTo(e.target.value)}
                    placeholder="30"
                    className={inputClass}
                  />
                </div>
                <p className="text-[10px] text-slate-400 mt-1">Common depths: 0–30, 0–60, 30–60, 60–90 cm</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  <MapPin size={14} className="inline mr-1" />
                  Sampling Location
                </label>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {LOCATION_PRESETS.map((loc) => (
                    <button
                      key={loc}
                      type="button"
                      onClick={() => setSamplingLocation(loc)}
                      className={`text-[11px] px-2.5 py-1 rounded-full border transition-all ${
                        samplingLocation === loc
                          ? "bg-amber-100 dark:bg-amber-900/30 border-amber-400 text-amber-700 dark:text-amber-400"
                          : "border-slate-200 dark:border-slate-700 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800"
                      }`}
                    >
                      {loc}
                    </button>
                  ))}
                </div>
                {samplingLocation === "Custom" && (
                  <input
                    type="text"
                    value={customLocation}
                    onChange={(e) => setCustomLocation(e.target.value)}
                    placeholder="e.g. GPS: 36.75, 3.04 or 'Near well'"
                    className={inputClass}
                  />
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Texture Class</label>
                <select
                  value={texture}
                  onChange={(e) => setTexture(e.target.value)}
                  className={inputClass}
                >
                  <option value="">Select Texture...</option>
                  <option value="Clay">Clay</option>
                  <option value="Sandy">Sandy</option>
                  <option value="Loam">Loam</option>
                  <option value="Silt">Silt</option>
                  <option value="Peat">Peat</option>
                  <option value="Chalky">Chalky</option>
                  <option value="Sandy Loam">Sandy Loam</option>
                  <option value="Clay Loam">Clay Loam</option>
                  <option value="Silty Loam">Silty Loam</option>
                  <option value="Silty Clay">Silty Clay</option>
                </select>
              </div>
            </div>

            {/* Chemical Properties */}
            <div className="space-y-4">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Chemical Properties</h4>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">pH Level</label>
                  <input
                    type="number" step="0.1"
                    value={ph}
                    onChange={(e) => setPh(e.target.value)}
                    placeholder="e.g. 6.5"
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">EC (dS/m)</label>
                  <input
                    type="number" step="0.01"
                    value={ec}
                    onChange={(e) => setEc(e.target.value)}
                    placeholder="e.g. 1.2"
                    className={inputClass}
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Organic Matter (%)</label>
                <input
                  type="number" step="0.1"
                  value={organicMatter}
                  onChange={(e) => setOrganicMatter(e.target.value)}
                  placeholder="e.g. 2.5"
                  className={inputClass}
                />
              </div>

              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider pt-2">Nutrients (mg/kg)</h4>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">N</label>
                  <input
                    type="number" step="0.1"
                    value={nitrogen}
                    onChange={(e) => setNitrogen(e.target.value)}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">P</label>
                  <input
                    type="number" step="0.1"
                    value={phosphorus}
                    onChange={(e) => setPhosphorus(e.target.value)}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">K</label>
                  <input
                    type="number" step="0.1"
                    value={potassium}
                    onChange={(e) => setPotassium(e.target.value)}
                    className={inputClass}
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Notes</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Lab name, conditions, observations..."
                  rows={3}
                  className={inputClass + " resize-none"}
                />
              </div>
            </div>
          </div>

          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg">
              {error}
            </div>
          )}

          <div className="pt-2 flex justify-end gap-3 sticky bottom-0 bg-white dark:bg-slate-900 py-4 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2 text-sm font-medium bg-amber-600 hover:bg-amber-700 text-white rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:shadow-none flex items-center gap-2"
            >
              {loading && <Loader2 className="animate-spin" size={16} />}
              Save Report
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
