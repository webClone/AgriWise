"use client";

import { useState } from "react";
import { Plus, Video, Play, Power, Trash2 } from "lucide-react";
import IPCameraAddModal from "./IPCameraAddModal";
import { deleteIPCamera, toggleIPCameraStatus } from "@/lib/actions";

interface IPCameraManagerProps {
  plotId: string;
  cameras: any[];
}

export default function IPCameraManager({ plotId, cameras: initialCameras }: IPCameraManagerProps) {
  const [cameras, setCameras] = useState(initialCameras);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleDelete = async (cameraId: string) => {
    if (!confirm("Are you sure you want to delete this camera?")) return;
    
    const res = await deleteIPCamera(plotId, cameraId);
    if (res.success) {
        setCameras(prev => prev.filter(c => c.id !== cameraId));
    } else {
        alert("Failed to delete camera");
    }
  };

  const handleToggleStatus = async (cameraId: string, currentStatus: string) => {
    // Optimistic update
    setCameras(prev => prev.map(c => 
        c.id === cameraId ? { ...c, status: c.status === 'ACTIVE' ? 'OFFLINE' : 'ACTIVE' } : c
    ));
    
    const res = await toggleIPCameraStatus(plotId, cameraId, currentStatus);
    if (!res.success) {
        // Revert on failure
        setCameras(prev => prev.map(c => 
            c.id === cameraId ? { ...c, status: currentStatus } : c
        ));
        alert("Failed to toggle camera status");
    }
  };

  const handleSuccess = () => {
    window.location.reload(); 
  };

  return (
    <div className="space-y-4">
      
      {/* Header Action */}
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
            <Video className="text-purple-500" size={18} />
            IP Cameras & Drone Feeds
        </h3>
        <button 
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 text-xs font-medium bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 px-3 py-1.5 rounded-full border border-purple-100 dark:border-purple-800 hover:bg-purple-100 dark:hover:bg-purple-900/40 transition-colors"
        >
            <Plus size={14} />
            Connect Camera
        </button>
      </div>

      {/* Grid */}
      {cameras.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cameras.map((camera) => (
                <div key={camera.id} className="relative rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 shadow-sm group">
                    {/* Video Player / Placeholder */}
                    <div className="aspect-video bg-black flex items-center justify-center relative overflow-hidden">
                        {/* Status Dot */}
                        <div className={`absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-full bg-black/50 backdrop-blur-md border border-white/10 z-10 
                            ${camera.status === 'ACTIVE' ? 'opacity-100' : 'opacity-70'}`}>
                             <div className={`w-2 h-2 rounded-full ${camera.status === 'ACTIVE' ? 'bg-red-500 animate-pulse' : 'bg-slate-500'}`} />
                             <span className="text-[10px] font-mono text-white/90 uppercase">{camera.status === 'ACTIVE' ? 'LIVE' : 'OFFLINE'}</span>
                        </div>
                        
                        {camera.status === 'ACTIVE' ? (
                             // Try to render content if active
                             <div className="w-full h-full relative">
                                {camera.url.match(/\.(jpeg|jpg|gif|png)$/i) ? (
                                    <img src={camera.url} alt={camera.name} className="w-full h-full object-cover" />
                                ) : (
                                    <video 
                                        src={camera.url} 
                                        className="w-full h-full object-cover" 
                                        autoPlay 
                                        muted 
                                        loop 
                                        playsInline
                                        onError={(e) => {
                                            // Fallback to placeholder if video fails (e.g. RTSP directly in browser)
                                            e.currentTarget.style.display = 'none';
                                            e.currentTarget.nextElementSibling?.classList.remove('hidden');
                                        }} 
                                    />
                                )}
                                {/* Fallback/Loading Overlay */}
                                <div className="hidden absolute inset-0 flex flex-col items-center justify-center bg-slate-900 text-slate-400">
                                     <Video size={48} className="mb-2 opacity-50" />
                                     <p className="text-xs">Stream Format Not Supported</p>
                                     <p className="text-[10px] opacity-60 mt-1">Check URL or use MJPEG/HLS</p>
                                </div>
                             </div>
                        ) : (
                            // Offline State
                            <div className="text-white/20 flex flex-col items-center">
                                <Video size={48} strokeWidth={1} />
                                <span className="text-xs mt-2 font-mono opacity-50">SIGNAL LOST</span>
                            </div>
                        )}
                        
                        {/* Play Overlay (Only show if offline or hovered) */}
                        <div className={`absolute inset-0 flex items-center justify-center bg-black/20 transition-opacity cursor-pointer ${camera.status === 'ACTIVE' ? 'opacity-0 hover:opacity-100' : 'opacity-100'}`}>
                            {camera.status !== 'ACTIVE' && (
                                <div onClick={() => handleToggleStatus(camera.id, camera.status || 'OFFLINE')} className="p-3 rounded-full bg-white/10 backdrop-blur hover:bg-white/20 transition-all border border-white/20">
                                    <Power size={24} className="text-white ml-0.5" />
                                </div>
                            )}
                        </div>
                    </div>
                    
                    {/* Info */}
                    <div className="p-3 flex justify-between items-start bg-white dark:bg-slate-900">
                        <div>
                             <h4 className="font-medium text-sm text-slate-800 dark:text-slate-200">{camera.name}</h4>
                             <p className="text-xs text-slate-500 dark:text-slate-400 font-mono truncate max-w-[180px]">{camera.url}</p>
                        </div>
                        <div className="flex gap-1">
                             <button 
                                onClick={() => handleToggleStatus(camera.id, camera.status || 'OFFLINE')}
                                className={`p-1.5 rounded-md transition-colors ${
                                    camera.status === 'ACTIVE' 
                                        ? 'text-green-600 bg-green-50 hover:bg-green-100 dark:bg-green-900/20 dark:text-green-400' 
                                        : 'text-slate-400 hover:text-green-600 hover:bg-slate-100 dark:hover:bg-slate-800'
                                }`}
                             >
                                <Power size={14} />
                             </button>
                             <button 
                                onClick={() => handleDelete(camera.id)}
                                className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
                             >
                                <Trash2 size={14} />
                             </button>
                        </div>
                    </div>
                </div>
            ))}
        </div>
      ) : (
        <div className="text-center py-8 bg-slate-50 dark:bg-slate-950/50 rounded-xl border border-dashed border-slate-300 dark:border-slate-800">
            <div className="inline-flex p-3 rounded-full bg-slate-100 dark:bg-slate-900 text-slate-400 mb-3">
                <Video size={24} />
            </div>
            <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">No cameras connected</p>
            <p className="text-slate-400 dark:text-slate-500 text-xs mt-1">Connect RTSP streams or drone feeds for real-time monitoring.</p>
        </div>
      )}

      {isModalOpen && (
        <IPCameraAddModal 
            plotId={plotId} 
            onClose={() => setIsModalOpen(false)} 
            onSuccess={handleSuccess}
        />
      )}

    </div>
  );
}
