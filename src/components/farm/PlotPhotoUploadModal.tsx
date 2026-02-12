"use client";

import { useState, useRef } from "react";
import { addPlotPhoto } from "@/lib/actions";
import { 
  Loader2, 
  Upload, 
  Camera, 
  X, 
  ImageIcon, 
  Trash2,
  FileImage
} from "lucide-react";

interface PlotPhotoUploadModalProps {
  plotId: string;
  onClose: () => void;
  onSuccess: () => void;
}

const PHOTO_TYPES = [
  { value: "OVERVIEW", label: "Overview" },
  { value: "CROP", label: "Crop Close-up" },
  { value: "SOIL", label: "Soil Detail" },
  { value: "DAMAGE", label: "Pest/Damage" },
  { value: "OTHER", label: "Other" }
];

export default function PlotPhotoUploadModal({ plotId, onClose, onSuccess }: PlotPhotoUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [type, setType] = useState("OVERVIEW");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (!selected.type.startsWith("image/")) {
      setError("Please select an image file.");
      return;
    }
    if (selected.size > 10 * 1024 * 1024) {
      setError("File too large. Maximum size is 10MB.");
      return;
    }

    setFile(selected);
    setError("");

    // Create preview
    const reader = new FileReader();
    reader.onload = (ev) => setPreview(ev.target?.result as string);
    reader.readAsDataURL(selected);
  };

  const clearFile = () => {
    setFile(null);
    setPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (cameraInputRef.current) cameraInputRef.current.value = "";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please select or capture an image.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      // Step 1: Upload the file
      const formData = new FormData();
      formData.append("file", file);

      const uploadRes = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      const uploadData = await uploadRes.json();

      if (!uploadRes.ok || !uploadData.url) {
        setError(uploadData.error || "Upload failed.");
        setLoading(false);
        return;
      }

      // Step 2: Save the photo record to DB
      const res = await addPlotPhoto(plotId, {
        url: uploadData.url,
        type: type as "CROP" | "SOIL" | "OVERVIEW" | "DAMAGE" | "OTHER",
        notes,
        date: new Date(),
      });

      if (res.success) {
        onSuccess();
        onClose();
      } else {
        setError(res.error || "Failed to save photo record.");
      }
    } catch {
      setError("Network error. Please try again.");
    }

    setLoading(false);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl max-w-md w-full border border-slate-200 dark:border-slate-800 overflow-hidden">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-950">
          <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
            <Upload size={18} className="text-emerald-500" />
            Add Plot Photo
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
          
          {/* Hidden file inputs */}
          <input 
            ref={fileInputRef}
            type="file" 
            accept="image/*"
            onChange={handleFileSelect}
            className="hidden"
          />
          <input 
            ref={cameraInputRef}
            type="file" 
            accept="image/*"
            capture="environment"
            onChange={handleFileSelect}
            className="hidden"
          />

          {/* Image Selection Area */}
          {!preview ? (
            <div className="space-y-3">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Choose Source
              </label>
              <div className="grid grid-cols-2 gap-3">
                {/* Take Photo Button */}
                <button
                  type="button"
                  onClick={() => cameraInputRef.current?.click()}
                  className="flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed border-emerald-300 dark:border-emerald-700 bg-emerald-50/50 dark:bg-emerald-950/20 hover:bg-emerald-100 dark:hover:bg-emerald-900/30 hover:border-emerald-400 transition-all group cursor-pointer"
                >
                  <div className="p-3 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400 group-hover:scale-110 transition-transform">
                    <Camera size={24} />
                  </div>
                  <span className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
                    Take Photo
                  </span>
                  <span className="text-[10px] text-slate-500 dark:text-slate-500">
                    Use camera
                  </span>
                </button>

                {/* Upload File Button */}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed border-blue-300 dark:border-blue-700 bg-blue-50/50 dark:bg-blue-950/20 hover:bg-blue-100 dark:hover:bg-blue-900/30 hover:border-blue-400 transition-all group cursor-pointer"
                >
                  <div className="p-3 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 group-hover:scale-110 transition-transform">
                    <ImageIcon size={24} />
                  </div>
                  <span className="text-sm font-medium text-blue-700 dark:text-blue-400">
                    Upload Photo
                  </span>
                  <span className="text-[10px] text-slate-500 dark:text-slate-500">
                    From device
                  </span>
                </button>
              </div>
            </div>
          ) : (
            /* Image Preview */
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Selected Image
              </label>
              <div className="relative group rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700">
                <img 
                  src={preview} 
                  alt="Preview" 
                  className="w-full h-48 object-cover"
                />
                <button
                  type="button"
                  onClick={clearFile}
                  className="absolute top-2 right-2 p-1.5 rounded-full bg-red-500/90 text-white hover:bg-red-600 transition-colors shadow-lg"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              {file && (
                <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <FileImage size={12} />
                  <span className="truncate">{file.name}</span>
                  <span className="text-slate-400">•</span>
                  <span>{formatFileSize(file.size)}</span>
                </div>
              )}
            </div>
          )}

          {/* Photo Type */}
          <div>
             <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Photo Type</label>
             <div className="grid grid-cols-3 gap-2">
                {PHOTO_TYPES.map(t => (
                    <button
                        key={t.value}
                        type="button"
                        onClick={() => setType(t.value)}
                        className={`text-xs p-2 rounded-md border transition-all ${
                            type === t.value 
                            ? "bg-emerald-50 dark:bg-emerald-900/20 border-emerald-500 text-emerald-700 dark:text-emerald-400 font-medium" 
                            : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800"
                        }`}
                    >
                        {t.label}
                    </button>
                ))}
             </div>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Notes (Optional)</label>
            <textarea 
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Showing signs of early blight..."
              className="w-full p-3 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500 focus:border-transparent h-20 resize-none text-sm"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg">
                {error}
            </div>
          )}

          {/* Actions */}
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
                disabled={loading || !file}
                className="px-6 py-2 text-sm font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:shadow-none flex items-center gap-2"
             >
                {loading && <Loader2 className="animate-spin" size={16} />}
                {loading ? "Uploading..." : "Add Photo"}
             </button>
          </div>

        </form>
      </div>
    </div>
  );
}
