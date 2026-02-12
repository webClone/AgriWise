"use client";

import { useState } from "react";
import { addIPCamera } from "@/lib/actions";
import { Loader2, Video, X, Globe } from "lucide-react";

interface IPCameraAddModalProps {
  plotId: string;
  onClose: () => void;
  onSuccess: () => void;
}

const CAMERA_TYPES = [
  { value: "FIXED", label: "Fixed Camera" },
  { value: "PTZ", label: "PTZ (Pan-Tilt-Zoom)" },
  { value: "DRONE_FEED", label: "Drone Feed" }
];

export default function IPCameraAddModal({ plotId, onClose, onSuccess }: IPCameraAddModalProps) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [type, setType] = useState("FIXED");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !url) {
        setError("Please fill in all fields.");
        return;
    }

    setLoading(true);
    setError("");

    const res = await addIPCamera(plotId, {
      name,
      url,
      type: type as any
    });

    if (res.success) {
      onSuccess();
      onClose();
    } else {
      setError(res.error || "Failed to add camera.");
    }
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl max-w-md w-full border border-slate-200 dark:border-slate-800 overflow-hidden scale-in-center">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-950">
          <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
            <Video size={18} className="text-purple-500" />
            Connect Camera Stream
          </h3>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Camera Name</label>
            <input 
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. North Sector PTZ"
              className="w-full px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Stream URL (RTSP/HLS)</label>
            <div className="relative">
                <input 
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="rtsp://192.168.1.10:554/stream"
                  className="w-full pl-10 pr-4 py-2 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-purple-500 focus:border-transparent font-mono text-xs"
                />
                <Globe size={16} className="absolute left-3 top-2.5 text-slate-400" />
            </div>
          </div>

          <div>
             <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Camera Type</label>
             <div className="grid grid-cols-3 gap-2">
                {CAMERA_TYPES.map(t => (
                    <button
                        key={t.value}
                        type="button"
                        onClick={() => setType(t.value)}
                        className={`text-xs p-2 rounded-md border transition-all ${
                            type === t.value 
                            ? "bg-purple-50 dark:bg-purple-900/20 border-purple-500 text-purple-700 dark:text-purple-400 font-medium" 
                            : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800"
                        }`}
                    >
                        {t.label}
                    </button>
                ))}
             </div>
          </div>

          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg">
                {error}
            </div>
          )}

          <div className="pt-2 flex justify-end gap-3">
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
                className="px-6 py-2 text-sm font-medium bg-purple-600 hover:bg-purple-700 text-white rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:shadow-none flex items-center gap-2"
             >
                {loading && <Loader2 className="animate-spin" size={16} />}
                Connect
             </button>
          </div>

        </form>
      </div>
    </div>
  );
}
