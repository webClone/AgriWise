"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { 
  Loader2, 
  Map as MapIcon, 
  Save, 
  Pencil, 
  Ruler, 
  Scaling, 
  User, 
  Droplet, 
  AlertTriangle 
} from "lucide-react";

const PlotMapEditor = dynamic(() => import("./PlotMapEditor"), {
  ssr: false,
  loading: () => <div className="h-[400px] w-full bg-slate-100 dark:bg-slate-800 animate-pulse rounded-lg flex items-center justify-center">Loading Map Editor...</div>
});

interface PlotIdentityFormProps {
  plot: any;
  lat: number;
  lng: number;
}

const CONSTRIANTS_OPTIONS = [
  "Slope present",
  "Salinity issues",
  "Drainage problems",
  "Compaction zones",
  "Rocky soil",
  "Flood risk"
];

export default function PlotIdentityForm({ plot, lat, lng }: PlotIdentityFormProps) {
  const [formData, setFormData] = useState({
    name: plot.name || "",
    perimeter: plot.perimeter || 0,
    ownership: plot.ownership || "",
    irrigationDistrict: plot.irrigationDistrict || "",
    physicalConstraints: plot.physicalConstraints || [],
    geoJson: plot.geoJson
  });

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [isEditingDetails, setIsEditingDetails] = useState(false);
  const [isEditingMap, setIsEditingMap] = useState(false);
  const [area, setArea] = useState(plot.area);

  // Sync local state when plot data updates from server (e.g. after revalidation)
  useEffect(() => {
    setFormData({
      name: plot.name || "",
      perimeter: plot.perimeter || 0,
      ownership: plot.ownership || "",
      irrigationDistrict: plot.irrigationDistrict || "",
      physicalConstraints: plot.physicalConstraints || [],
      geoJson: plot.geoJson
    });
    setArea(plot.area);
  }, [plot]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleConstraintToggle = (constraint: string) => {
    setFormData(prev => {
      const current = prev.physicalConstraints as string[];
      if (current.includes(constraint)) {
        return { ...prev, physicalConstraints: current.filter(c => c !== constraint) };
      } else {
        return { ...prev, physicalConstraints: [...current, constraint] };
      }
    });
  };

  const handleSave = async () => {
    setLoading(true);
    setSuccess(false);
    
    // Safely parse numbers
    const perimeterValue = formData.perimeter === "" ? null : parseFloat(String(formData.perimeter));

    // Use the existing working API route instead of the server action
    try {
      const res = await fetch(`/api/plots/${plot.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name,
          perimeter: isNaN(perimeterValue!) ? undefined : perimeterValue,
          ownership: formData.ownership,
          irrigationDistrict: formData.irrigationDistrict,
          physicalConstraints: formData.physicalConstraints,
          geoJson: formData.geoJson,
          area: area
        }),
      });

      const data = await res.json();
      
      if (res.ok && data.success) {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        setIsEditingDetails(false);
        // Force page data refresh
        window.location.reload();
      } else {
        alert(`Failed to save: ${data.error || 'Unknown error'}`);
        console.error("Save failed:", data);
      }
    } catch (err) {
      alert(`Failed to save: Network error`);
      console.error("Save network error:", err);
    }
    setLoading(false);
  };
  
  const handleMapSave = async (newGeoJson: any, newArea: number) => {
      // Update local state immediately
      setFormData(prev => ({ ...prev, geoJson: newGeoJson }));
      setArea(newArea);
      setIsEditingMap(false);
      setLoading(true);
      
      try {
        const res = await fetch(`/api/plots/${plot.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            geoJson: newGeoJson,
            area: newArea,
          }),
        });

        const data = await res.json();
        
        if (res.ok && data.success) {
          setSuccess(true);
          setTimeout(() => setSuccess(false), 3000);
        } else {
          alert(`Failed to save geometry: ${data.error || 'Unknown error'}`);
          console.error("Geometry save failed:", data);
        }
      } catch (err) {
        alert(`Failed to save geometry: Network error`);
        console.error("Geometry save network error:", err);
      }
      setLoading(false);
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      
      {/* Header */}
      <div className="bg-slate-50 dark:bg-slate-950 px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
        <div className="flex items-center gap-3">
            <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <MapIcon className="text-emerald-500" size={18} />
                Plot Basics
            </h3>
            <p className="text-[10px] text-slate-500 mt-1">
                Establishes spatial context for satellite integration.
            </p>
            {!isEditingDetails && (
                <span className="text-xs text-slate-400 font-mono bg-slate-100 dark:bg-slate-900 px-2 py-1 rounded border border-slate-200 dark:border-slate-800">
                    {plot.id.substring(0, 8)}
                </span>
            )}
        </div>
        
        {!isEditingDetails && (
            <button 
                onClick={() => setIsEditingDetails(true)}
                className="flex items-center gap-2 text-xs font-medium text-slate-600 hover:text-emerald-600 dark:text-slate-400 dark:hover:text-emerald-400 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
            >
                <Pencil size={14} />
                Edit Details
            </button>
        )}
      </div>

      <div className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Left Col: Details */}
        <div className="space-y-4">
             {isEditingDetails ? (
                /* EDIT FORM */
                <div className="space-y-5 fade-in">
                    <div className="flex justify-between items-center pb-2 border-b border-slate-100 dark:border-slate-800">
                         <h4 className="text-sm font-medium text-slate-900 dark:text-slate-100">Edit Plot Information</h4>
                         <button 
                            onClick={() => setIsEditingDetails(false)}
                            className="text-xs text-slate-500 hover:text-slate-700"
                         >
                            Cancel
                         </button>
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5 uppercase tracking-wide">Plot Name</label>
                        <input 
                            name="name"
                            value={formData.name}
                            onChange={handleChange}
                            className="w-full p-2.5 border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5 uppercase tracking-wide">Area (ha)</label>
                            <div className="w-full p-2.5 bg-slate-100 dark:bg-slate-800 rounded-lg text-slate-500 border border-transparent">
                                {area}
                            </div>
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5 uppercase tracking-wide">Perimeter (m)</label>
                            <input 
                                type="number"
                                name="perimeter"
                                value={formData.perimeter}
                                onChange={handleChange}
                                className="w-full p-2.5 border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5 uppercase tracking-wide">Ownership</label>
                        <input 
                            name="ownership"
                            value={formData.ownership}
                            onChange={handleChange}
                            placeholder="e.g. John Doe / Coop A"
                            className="w-full p-2.5 border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
                        />
                    </div>
                    
                    <div>
                        <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5 uppercase tracking-wide">Irrigation District</label>
                        <input 
                            name="irrigationDistrict"
                            value={formData.irrigationDistrict}
                            onChange={handleChange}
                            placeholder="e.g. Sector 4 - Canal B"
                            className="w-full p-2.5 border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-3 uppercase tracking-wide">Physical Constraints</label>
                        <div className="grid grid-cols-2 gap-3">
                            {CONSTRIANTS_OPTIONS.map(opt => (
                                <label key={opt} className="flex items-center gap-3 p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-950 hover:border-emerald-200 dark:hover:border-emerald-900/50 cursor-pointer transition-colors group">
                                    <div className="relative flex items-center">
                                         <input 
                                            type="checkbox"
                                            checked={(formData.physicalConstraints as string[]).includes(opt)}
                                            onChange={() => handleConstraintToggle(opt)}
                                            className="peer h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                                        />
                                    </div>
                                    <span className="text-sm text-slate-600 dark:text-slate-400 group-hover:text-slate-900 dark:group-hover:text-slate-200 transition-colors">{opt}</span>
                                </label>
                            ))}
                        </div>
                    </div>
                    
                    <div className="pt-4 flex items-center gap-4">
                        <button 
                            onClick={handleSave}
                            disabled={loading}
                            className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm hover:shadow transition-all disabled:opacity-50 font-medium text-sm"
                        >
                            {loading ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                            Save Changes
                        </button>
                        {success && <span className="text-emerald-600 text-sm font-medium fade-in flex items-center gap-1"><span className="text-lg">✓</span> Saved successfully</span>}
                    </div>
                </div>
             ) : (
                /* READ ONLY VIEW */
                <div className="space-y-6 fade-in h-full flex flex-col">
                    {/* Plot Name Card */}
                    <div className="bg-slate-50/50 dark:bg-slate-800/20 p-4 rounded-xl border border-slate-100 dark:border-slate-800">
                         <h4 className="text-xs uppercase tracking-wider text-slate-400 mb-1 flex items-center gap-2">
                            Plot Name
                         </h4>
                         <p className="text-2xl font-bold text-slate-800 dark:text-slate-100 tracking-tight">
                            {formData.name || <span className="text-slate-300 italic">Unnamed Plot</span>}
                         </p>
                    </div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="p-4 rounded-xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col justify-between">
                             <div className="flex items-center gap-2 mb-2">
                                <span className="p-1.5 rounded-md bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400">
                                    <Scaling size={16} />
                                </span>
                                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Area</h4>
                             </div>
                             <p className="text-xl font-bold text-slate-800 dark:text-slate-200">
                                {area} <span className="text-sm font-normal text-slate-400">ha</span>
                             </p>
                        </div>
                        <div className="p-4 rounded-xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col justify-between">
                             <div className="flex items-center gap-2 mb-2">
                                <span className="p-1.5 rounded-md bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400">
                                    <Ruler size={16} />
                                </span>
                                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Perimeter</h4>
                             </div>
                             <p className="text-xl font-bold text-slate-800 dark:text-slate-200">
                                {formData.perimeter ? formData.perimeter : "-"} <span className="text-sm font-normal text-slate-400">m</span>
                             </p>
                        </div>
                    </div>

                    {/* Info Grid */}
                    <div className="grid grid-cols-1 gap-4">
                        <div className="flex items-start gap-3 p-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                            <span className="mt-0.5 text-slate-400"><User size={18} /></span>
                            <div>
                                <h4 className="text-xs font-medium text-slate-500 uppercase mb-0.5">Ownership / Manager</h4>
                                <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                                    {formData.ownership || <span className="text-slate-400 italic">Not specified</span>}
                                </p>
                            </div>
                        </div>
                        
                        <div className="flex items-start gap-3 p-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                            <span className="mt-0.5 text-slate-400"><Droplet size={18} /></span>
                            <div>
                                <h4 className="text-xs font-medium text-slate-500 uppercase mb-0.5">Irrigation District</h4>
                                <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                                    {formData.irrigationDistrict || <span className="text-slate-400 italic">Not specified</span>}
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Constraints Chips */}
                    <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                        <h4 className="text-xs uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-2">
                            <AlertTriangle size={12} className="text-amber-500" />
                            Physical Constraints
                        </h4>
                        <div className="flex flex-wrap gap-2">
                            {(formData.physicalConstraints as string[]).length > 0 ? (
                                (formData.physicalConstraints as string[]).map(c => (
                                    <span key={c} className="px-3 py-1 bg-amber-50 dark:bg-amber-900/10 text-amber-700 dark:text-amber-400 text-xs font-medium rounded-full border border-amber-100 dark:border-amber-800">
                                        {c}
                                    </span>
                                ))
                            ) : (
                                <span className="text-slate-400 text-sm italic py-1">No physical constraints recorded.</span>
                            )}
                        </div>
                    </div>
                </div>
             )}
        </div>

        {/* Right Col: Geometry Editor */}
        <div className="flex flex-col h-full">
            <div className="flex justify-between items-center mb-3">
                 <label className="text-sm font-medium text-slate-700 dark:text-slate-300 flex items-center gap-2">
                    Plot Geometry
                    <span className="text-xs font-normal text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">Leaflet Satellite</span>
                 </label>
                 {isEditingDetails && (
                    <button 
                        onClick={() => setIsEditingMap(!isEditingMap)}
                        className={`text-xs flex items-center gap-1 font-medium px-3 py-1.5 rounded-md border transition-all ${isEditingMap ? 'bg-blue-50 text-blue-700 border-blue-200' : 'text-slate-600 hover:text-blue-600 border-transparent hover:bg-blue-50'}`}
                    >
                        <MapIcon size={14} />
                        {isEditingMap ? "Finish Editing" : "Edit Boundary"}
                    </button>
                 )}
            </div>
            
            <div className="flex-1 rounded-xl overflow-hidden shadow-sm border border-slate-200 dark:border-slate-800 relative group">
                    <div className="absolute inset-0 z-0">
                         <PlotMapEditor 
                            center={[lat, lng]} 
                            initialGeoJson={formData.geoJson}
                            readOnly={!isEditingMap}
                            onSave={handleMapSave}
                        />
                    </div>
                   
                    {/* Overlay Tip for Edit Mode */}
                    {isEditingMap && (
                        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] bg-white/90 dark:bg-slate-900/90 backdrop-blur text-slate-800 dark:text-slate-200 text-xs px-4 py-2 rounded-full shadow-lg border border-slate-200 dark:border-slate-700 pointer-events-none">
                            Drafting Mode Active
                        </div>
                    )}
            </div>
            
            {/* Boundary Source Metadata */}
            <div className="mt-2 flex items-center gap-1.5 text-[10px] text-slate-400 dark:text-slate-500 font-medium">
                <span className="uppercase tracking-wider opacity-70">Boundary source:</span>
                <span className="text-slate-600 dark:text-slate-400">User-drawn</span>
                <span className="mx-0.5 opacity-30">·</span>
                <span>Updated Feb 10, 2026</span>
            </div>

            {isEditingMap && (
                 <div className="text-xs text-slate-500 mt-2 text-center">
                    Use the sidebar tools to draw. Click the square to save.
                </div>
            )}
        </div>

      </div>
    </div>
  );
}
