"use client";

import { useState } from "react";
import Link from "next/link";
import AddPlotForm from "./AddPlotForm";


interface Plot {
  id: string;
  name: string;
  nameAr?: string;
  area: number;
  soilType?: string;
  irrigation?: string;
}

interface CropCycle {
  id: string;
  cropCode: string;
  cropNameAr?: string;
  variety?: string;
  status: string;
  plotId: string;
}

interface PlotsSectionProps {
  farmId: string;
  plots: Plot[];
  cropCycles: CropCycle[];
  farmCoordinates?: { lat: number; lng: number };
}

export default function PlotsSection({ farmId, plots, cropCycles, farmCoordinates }: PlotsSectionProps) {
  const [showAddForm, setShowAddForm] = useState(false);

  return (
    <>
      <div className="card fade-in" style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, fontWeight: 600 }}>🌱 قطع الأرض ({plots.length})</h3>
          <button 
            className="btn btn-secondary" 
            style={{ padding: "0.35rem 0.75rem", fontSize: "0.75rem" }}
            onClick={() => setShowAddForm(true)}
          >
            + إضافة
          </button>
        </div>
        
        {plots.length === 0 ? (
          <div style={{ textAlign: "center", padding: "2rem", border: "2px dashed var(--background-tertiary)", borderRadius: "12px" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>🚜</div>
            <p className="page-subtitle">لم يتم تحديد قطع أرض بعد</p>
            <button 
              className="btn btn-primary" 
              style={{ marginTop: "0.75rem" }}
              onClick={() => setShowAddForm(true)}
            >
              تحديد القطع
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {plots.map((plot) => {
              const plotCrops = cropCycles.filter(c => c.plotId === plot.id);
              return (
                <Link 
                  href={`/farm/${farmId}/plot/${plot.id}`}
                  key={plot.id} 
                  style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
                >
                  <div style={{ 
                    padding: "1rem", 
                    background: "var(--background-secondary)", 
                    borderRadius: "12px",
                    border: "1px solid var(--background-tertiary)",
                    transition: "transform 0.2s, box-shadow 0.2s",
                    cursor: "pointer"
                  }}
                  className="hover:shadow-md hover:scale-[1.01]"
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
                      <div>
                        <h4 style={{ margin: 0, fontWeight: 600 }}>{plot.name}</h4>
                        <p className="page-subtitle" style={{ margin: "0.25rem 0 0 0", fontSize: "0.8rem" }}>
                          {plot.area} هكتار • {plot.soilType || 'تربة غير محددة'}
                        </p>
                      </div>
                      <span style={{ 
                        fontSize: "0.7rem", 
                        background: "var(--background-tertiary)", 
                        padding: "0.25rem 0.5rem", 
                        borderRadius: "4px" 
                      }}>
                        {plot.irrigation || 'بعلي'}
                      </span>
                    </div>
                    {plotCrops.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem" }}>
                        {plotCrops.map((crop) => (
                          <span 
                            key={crop.id} 
                            style={{ 
                              fontSize: "0.75rem", 
                              padding: "0.25rem 0.5rem", 
                              borderRadius: "9999px",
                              background: crop.status === 'GROWING' ? 'rgba(34, 197, 94, 0.15)' :
                                          crop.status === 'FLOWERING' ? 'rgba(236, 72, 153, 0.15)' :
                                          crop.status === 'PLANTED' ? 'rgba(59, 130, 246, 0.15)' :
                                          'rgba(234, 179, 8, 0.15)',
                              color: crop.status === 'GROWING' ? 'var(--color-primary-600)' :
                                     crop.status === 'FLOWERING' ? '#db2777' :
                                     crop.status === 'PLANTED' ? '#2563eb' :
                                     '#ca8a04'
                            }}
                          >
                            {crop.cropNameAr || crop.cropCode} - {crop.variety}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {showAddForm && (
        <AddPlotForm 
          farmId={farmId} 
          farmCoordinates={farmCoordinates}
          onClose={() => setShowAddForm(false)} 
        />
      )}
    </>
  );
}
