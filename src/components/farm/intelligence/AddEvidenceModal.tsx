"use client";

import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Camera, Image as ImageIcon, Map as MapIcon, AlertTriangle, Pin, Leaf, X, CheckCircle, Loader2, Sparkles } from "lucide-react";

interface AddEvidenceModalProps {
  plotId: string;
  zoneId?: string;
  plotName?: string;
  onClose: () => void;
  onSuccess: () => void;
}

const EVIDENCE_TYPES = [
  { id: "CROP", label: "Crop Photo", icon: <Leaf className="w-5 h-5 text-emerald-400" /> },
  { id: "SOIL", label: "Soil Photo", icon: <MapIcon className="w-5 h-5 text-amber-600" /> },
  { id: "OVERVIEW", label: "Field Overview", icon: <ImageIcon className="w-5 h-5 text-blue-400" /> },
  { id: "DAMAGE", label: "Damage / Symptom", icon: <AlertTriangle className="w-5 h-5 text-rose-500" /> },
  { id: "OTHER", label: "Other", icon: <Pin className="w-5 h-5 text-slate-400" /> },
];

export default function AddEvidenceModal({
  plotId,
  zoneId,
  plotName = "Field",
  onClose,
  onSuccess
}: AddEvidenceModalProps) {
  const [selectedType, setSelectedType] = useState<string>("CROP");
  const [photoBase64, setPhotoBase64] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  
  const [aiTags, setAiTags] = useState<string[]>([]);
  const [aiInterpretation, setAiInterpretation] = useState<string | null>(null);
  const [isTagging, setIsTagging] = useState(false);
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
      const base64 = event.target?.result as string;
      setPhotoBase64(base64);
      
      // Trigger AI Tagging immediately
      setIsTagging(true);
      try {
        const res = await fetch("/api/vision/quick-tags", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ imageBase64: base64 })
        });
        const data = await res.json();
        if (data.tags) setAiTags(data.tags);
        if (data.interpretation) setAiInterpretation(data.interpretation);
      } catch (err) {
        console.error("AI Tagging failed", err);
      } finally {
        setIsTagging(false);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleSubmit = async () => {
    if (!photoBase64) return;
    
    setIsSubmitting(true);
    try {
      const res = await fetch("/api/evidence/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plotId,
          zoneId,
          type: selectedType,
          base64Image: photoBase64,
          notes,
          date,
          aiTags,
          source: "farmer"
        })
      });
      
      if (res.ok) {
        setSubmitted(true);
        setTimeout(() => {
          onSuccess();
        }, 1500);
      }
    } catch (err) {
      console.error("Failed to submit evidence", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const modalContent = (
    <div className="fixed inset-0 z-[9999] flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-950/80 backdrop-blur-sm" style={{ pointerEvents: "auto" }}>
      <div className="bg-[#0f172a] w-full max-w-md sm:rounded-2xl rounded-t-2xl shadow-2xl overflow-hidden border border-slate-800 flex flex-col max-h-[95vh] animate-in slide-in-from-bottom-10 sm:zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-900/50">
          <div>
            <h2 className="text-lg font-bold text-white">Add Evidence to {plotName}</h2>
            <p className="text-xs text-slate-400 mt-0.5">Help the AI understand your field better</p>
          </div>
          <button onClick={onClose} className="p-2 bg-slate-800 rounded-full text-slate-400 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-4 overflow-y-auto flex-1 space-y-6">
          
          {/* Evidence Type */}
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 block">Evidence Type</label>
            <div className="grid grid-cols-3 gap-2 pb-2">
              {EVIDENCE_TYPES.map(type => (
                <button
                  key={type.id}
                  onClick={() => setSelectedType(type.id)}
                  className={`flex flex-col items-center justify-center p-3 rounded-xl border transition-all ${
                    selectedType === type.id 
                      ? "bg-slate-800 border-indigo-500 ring-1 ring-indigo-500/50" 
                      : "bg-slate-900/50 border-slate-800 hover:border-slate-700 opacity-70 hover:opacity-100"
                  }`}
                >
                  <div className="mb-2">{type.icon}</div>
                  <span className={`text-[10px] font-medium text-center ${selectedType === type.id ? "text-white" : "text-slate-400"}`}>
                    {type.label}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Photo Area */}
          <div>
            <input 
              type="file" 
              accept="image/*" 
              capture="environment"
              className="hidden" 
              ref={fileInputRef}
              onChange={handlePhotoSelect}
            />
            
            {!photoBase64 ? (
              <button 
                onClick={() => fileInputRef.current?.click()}
                className="w-full aspect-video bg-slate-900 border-2 border-dashed border-slate-700 hover:border-indigo-500 rounded-2xl flex flex-col items-center justify-center gap-3 transition-colors group"
              >
                <div className="p-4 bg-slate-800 group-hover:bg-indigo-500/20 rounded-full transition-colors">
                  <Camera className="w-8 h-8 text-indigo-400" />
                </div>
                <span className="text-sm font-medium text-slate-300">Take Photo or Choose from Gallery</span>
              </button>
            ) : (
              <div className="relative w-full aspect-video rounded-2xl overflow-hidden bg-slate-900 border border-slate-700 group">
                <img src={photoBase64} alt="Evidence" className="w-full h-full object-cover" />
                <button 
                  onClick={() => setPhotoBase64(null)}
                  className="absolute top-2 right-2 p-1.5 bg-black/50 hover:bg-rose-500 text-white rounded-full transition-colors opacity-0 group-hover:opacity-100"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
            
            {/* AI Tags Section */}
            {photoBase64 && (
              <div className="mt-3 p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl">
                <div className="flex items-center gap-1.5 mb-2">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                  <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">AI Quick Analysis</span>
                </div>
                
                {isTagging ? (
                  <div className="flex items-center gap-2 text-sm text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin" /> Processing image...
                  </div>
                ) : (
                  <>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {aiTags.map(tag => (
                        <span key={tag} className="px-2 py-0.5 bg-indigo-500/20 text-indigo-300 text-[10px] font-bold uppercase tracking-wider rounded-md border border-indigo-500/30">
                          {tag}
                        </span>
                      ))}
                    </div>
                    {aiInterpretation && (
                      <p className="text-xs text-slate-300 leading-relaxed">{aiInterpretation}</p>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          {/* Form Fields */}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">Short Notes</label>
              <textarea 
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="E.g., Leaves turning yellow in the south corner..."
                className="w-full bg-slate-900 border border-slate-700 focus:border-indigo-500 rounded-xl p-3 text-sm text-white placeholder-slate-600 outline-none resize-none h-20"
              />
            </div>
            
            <div className="col-span-2">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">Observation Date</label>
              <input 
                type="date" 
                value={date}
                onChange={e => setDate(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 focus:border-indigo-500 rounded-xl p-3 text-sm text-white outline-none"
              />
            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/50">
          <button 
            disabled={!photoBase64 || isSubmitting || submitted}
            onClick={handleSubmit}
            className={`w-full py-3.5 rounded-xl font-bold flex items-center justify-center gap-2 transition-all ${
              submitted ? 'bg-emerald-500 text-white' :
              !photoBase64 ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 
              'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20'
            }`}
          >
            {submitted ? (
              <><CheckCircle className="w-5 h-5" /> Evidence Added</>
            ) : isSubmitting ? (
              <><Loader2 className="w-5 h-5 animate-spin" /> Uploading...</>
            ) : (
              'Submit Evidence'
            )}
          </button>
        </div>

      </div>
    </div>
  );

  if (!mounted) return null;
  return createPortal(modalContent, document.body);
}
