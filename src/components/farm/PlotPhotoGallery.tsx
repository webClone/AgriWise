"use client";

import { useState } from "react";
import { Plus, Image as ImageIcon, Calendar, Trash2, Loader2 } from "lucide-react";
import { deletePlotPhoto } from "@/lib/actions";
import PlotPhotoUploadModal from "./PlotPhotoUploadModal";

interface PlotPhotoGalleryProps {
  plotId: string;
  photos: any[];
}

export default function PlotPhotoGallery({ plotId, photos: initialPhotos }: PlotPhotoGalleryProps) {
  const [photos, setPhotos] = useState(initialPhotos);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleSuccess = () => {
    window.location.reload(); 
  };

  const handleDelete = async (photoId: string) => {
    if (!confirm("Delete this photo? This cannot be undone.")) return;

    setDeletingId(photoId);
    const res = await deletePlotPhoto(photoId);
    
    if (res.success) {
      setPhotos(prev => prev.filter(p => p.id !== photoId));
    } else {
      alert(`Failed to delete: ${res.error || "Unknown error"}`);
    }
    setDeletingId(null);
  };

  return (
    <div className="space-y-4">
      
      {/* Header Action */}
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
            <ImageIcon className="text-blue-500" size={18} />
            Plot Photos
        </h3>
        <button 
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 text-xs font-medium bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 px-3 py-1.5 rounded-full border border-blue-100 dark:border-blue-800 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
        >
            <Plus size={14} />
            Add Photo
        </button>
      </div>

      {/* Grid */}
      {photos.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {photos.map((photo) => (
                <div key={photo.id} className="group relative aspect-square rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900">
                    <img 
                        src={photo.url} 
                        alt={photo.notes || "Plot Photo"} 
                        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                    />
                    
                    {/* Delete Button */}
                    <button
                      onClick={() => handleDelete(photo.id)}
                      disabled={deletingId === photo.id}
                      className="absolute top-2 right-2 p-1.5 rounded-full bg-red-500/90 text-white opacity-0 group-hover:opacity-100 hover:bg-red-600 transition-all shadow-lg disabled:opacity-50 z-10"
                      title="Delete photo"
                    >
                      {deletingId === photo.id ? (
                        <Loader2 className="animate-spin" size={14} />
                      ) : (
                        <Trash2 size={14} />
                      )}
                    </button>

                    {/* Overlay */}
                    <div className="absolute inset-0 bg-linear-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity p-3 flex flex-col justify-end">
                        <span className={`text-white text-xs font-medium px-2 py-0.5 rounded-md self-start mb-1 ${
                            (photo.type === 'SATELLITE' || photo.source === 'satellite') ? 'bg-indigo-600/80' : 'bg-blue-600/80'
                        }`}>
                            {(photo.type === 'SATELLITE' || photo.source === 'satellite') ? '🛰️ Satellite' : photo.type}
                        </span>
                        {photo.notes && (
                            <p className="text-white/90 text-xs line-clamp-2 mb-1">{photo.notes}</p>
                        )}
                        <span className="text-white/60 text-[10px] flex items-center gap-1">
                            <Calendar size={10} />
                            {new Date(photo.date).toLocaleDateString()}
                        </span>
                    </div>
                </div>
            ))}
        </div>
      ) : (
        <div className="text-center py-10 bg-slate-50 dark:bg-slate-950/50 rounded-xl border border-dashed border-slate-300 dark:border-slate-800">
            <div className="inline-flex p-3 rounded-full bg-slate-100 dark:bg-slate-900 text-slate-400 mb-3">
                <ImageIcon size={24} />
            </div>
            <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">No photos added yet</p>
            <p className="text-slate-400 dark:text-slate-500 text-xs mt-1">Upload ground truth imagery to track changes.</p>
            <button 
                onClick={() => setIsModalOpen(true)}
                className="mt-4 text-xs text-blue-600 hover:text-blue-700 font-medium underline underline-offset-2"
            >
                Add first photo
            </button>
        </div>
      )}

      {isModalOpen && (
        <PlotPhotoUploadModal 
            plotId={plotId} 
            onClose={() => setIsModalOpen(false)} 
            onSuccess={handleSuccess}
        />
      )}

    </div>
  );
}
