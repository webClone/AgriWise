"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface StartCycleModalProps {
  plotId: string;
  onClose: () => void;
  onSuccess?: () => void;
}

interface CropOption {
  code: string;
  nameAr: string;
  icon: string;
}

export default function StartCycleModal({ plotId, onClose, onSuccess }: StartCycleModalProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [loadingCrops, setLoadingCrops] = useState(true);
  const [error, setError] = useState("");
  
  const [crops, setCrops] = useState<CropOption[]>([]);
  const [filteredCrops, setFilteredCrops] = useState<CropOption[]>([]);
  const [inputCrop, setInputCrop] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Form State
  const [formData, setFormData] = useState({
    cropName: "",
    variety: "",
    startDate: new Date().toISOString().split('T')[0],
  });

  useEffect(() => {
    fetch("/api/crops")
      .then(res => res.json())
      .then(data => {
        if (data.success) {
            setCrops(data.crops);
            setFilteredCrops(data.crops);
        }
      })
      .finally(() => setLoadingCrops(false));
  }, []);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputCrop(val);
    setFormData(prev => ({ ...prev, cropName: val }));
    setShowSuggestions(true);

    const filtered = crops.filter(c => 
        c.nameAr.toLowerCase().includes(val.toLowerCase()) || 
        c.code.toLowerCase().includes(val.toLowerCase())
    );
    setFilteredCrops(filtered);
  };

  const selectCrop = (crop: CropOption) => {
    setInputCrop(crop.nameAr); // Display name
    setFormData(prev => ({ ...prev, cropName: crop.nameAr.split('(')[0].trim() })); // Use clean name for AI
    setShowSuggestions(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`/api/plots/${plotId}/cycle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      const data = await res.json();

      if (data.success) {
        router.refresh();
        onSuccess?.();
        onClose();
      } else {
        setError(data.error || "حدث خطأ أثناء بدء الدورة");
      }
    } catch (err) {
      console.error(err);
      setError("حدث خطأ. حاول مرة أخرى.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1000] p-4 backdrop-blur-sm fade-in">
      <div className="card w-full max-w-[500px] max-h-[90vh] overflow-y-auto relative bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl rounded-xl">
        <div className="flex justify-between items-center mb-4 p-6 border-b border-slate-100 dark:border-slate-800">
          <h3 className="m-0 font-semibold text-xl text-slate-800 dark:text-slate-100">🌱 بدء دورة زراعية جديدة</h3>
          <button onClick={onClose} className="bg-transparent border-none text-2xl cursor-pointer text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors">✕</button>
        </div>

        <div className="p-6 pt-2">
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg mb-4 text-sm border border-red-100 dark:border-red-900/30">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Crop Autocomplete */}
            <div className="relative">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">نوع المحصول *</label>
              <input
                type="text"
                required
                className="w-full p-3 bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 outline-none transition-all text-slate-800 dark:text-slate-200"
                placeholder="ابحث أو اكتب اسم محصول..."
                value={inputCrop}
                onChange={handleSearch}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 200)} // Delay to allow click
              />
              
              {showSuggestions && (
                  <div className="absolute top-full left-0 right-0 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-b-lg max-h-[200px] overflow-y-auto z-10 shadow-lg mt-1">
                      {loadingCrops ? (
                          <div className="p-3 text-slate-400 text-sm">جاري التحميل...</div>
                      ) : filteredCrops.length > 0 ? (
                          filteredCrops.map(crop => (
                              <div 
                                  key={crop.code}
                                  onClick={() => selectCrop(crop)}
                                  className="p-3 cursor-pointer flex gap-2 items-center border-b border-slate-100 dark:border-slate-700/50 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-slate-700 dark:text-slate-200"
                              >
                                  <span>{crop.icon}</span>
                                  <span>{crop.nameAr}</span>
                              </div>
                          ))
                      ) : (
                           <div className="p-3 text-slate-500 dark:text-slate-400 text-sm">
                              ازرع &quot;{inputCrop}&quot; (سيقوم الذكاء الاصطناعي بإنشاء الخطة)
                           </div>
                      )}
                  </div>
              )}
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  يمكنك كتابة أي اسم محصول (مثلاً: "كينوا"، "فاكهة التنين")، وسيقوم AgriBrain بإنشاء خطة زراعية مخصصة له.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">الصنف / النوع</label>
              <input
                type="text"
                className="w-full p-3 bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 outline-none transition-all text-slate-800 dark:text-slate-200"
                placeholder="مثال: سيميتو، سبونتا (اختياري)"
                value={formData.variety}
                onChange={(e) => setFormData(prev => ({ ...prev, variety: e.target.value }))}
              />
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">تاريخ الزراعة *</label>
              <input
                type="date"
                required
                className="w-full p-3 bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 outline-none transition-all text-slate-800 dark:text-slate-200 scheme-light dark:scheme-dark"
                value={formData.startDate}
                onChange={(e) => setFormData(prev => ({ ...prev, startDate: e.target.value }))}
              />
            </div>

            <div className="flex gap-3 pt-2">
              <button type="button" onClick={onClose} className="flex-1 px-4 py-3 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 font-medium hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">إلغاء</button>
              <button type="submit" disabled={loading} className="flex-1 px-4 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-70 disabled:cursor-not-allowed">
                {loading ? "جاري الإنشاء..." : "🚀 بدء الدورة"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
