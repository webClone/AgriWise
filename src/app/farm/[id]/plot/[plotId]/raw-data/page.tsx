import { prisma } from "@/lib/prisma";
import { getPlot, getFarm, getCropCycles, getPlotCenter } from "@/lib/farm-services";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";

import PlotPageClient from "@/components/farm/PlotPageClient";
import SatelliteMissionControl from "@/components/farm/SatelliteMissionControl";
import PlotWeatherWidget from "@/components/farm/PlotWeatherWidget";
import PlotSoilPanel from "@/components/farm/PlotSoilPanel";
import PlotPhenologyCard from "@/components/farm/PlotPhenologyCard";
import PlotEnvironmentPanel from "@/components/farm/PlotEnvironmentPanel";
import PlotSARPanel from "@/components/farm/PlotSARPanel";
import PlotRainfallHistoryPanel from "@/components/farm/PlotRainfallHistoryPanel";
import PlotWaterStressPanel from "@/components/farm/PlotWaterStressPanel";
import PlotLandCoverPanel from "@/components/farm/PlotLandCoverPanel";
import MasonryGrid from "@/components/ui/MasonryGrid";

export default async function RawDataPage({ params }: { params: Promise<{ id: string; plotId: string }> }) {
  const { id: farmId, plotId } = await params;
  
  // Use Shared Services
  const plot = await getPlot(plotId);
  const farm = await getFarm(farmId);
  const cropCycles = await getCropCycles(plotId);
  const currentCrop = cropCycles.find(c => c.status !== 'HARVESTED');
  
  // Fetch tasks for the current crop if exists
  let currentTasks: any[] = [];
  if (currentCrop) {
      currentTasks = await prisma.cropTask.findMany({
          where: { cropCycleId: currentCrop.id },
          orderBy: { dueDate: 'asc' }
      });
  }

  if (!plot) return <div>Plot not found</div>;

  // Calculate coordinates using shared helper
  const { lat, lng } = getPlotCenter(plot, farm);

  return (
    <div className="w-full pb-32 px-4 md:px-8">
      {/* DASHBOARD GRID */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        
        {/* ROW 1: SATELLITE INTELLIGENCE (Full Width) */}
        <div className="card fade-in" style={{ padding: "1.5rem", overflow: "hidden" }}>
             <SatelliteMissionControl 
                lat={lat}
                lng={lng}
                cropCode={currentCrop?.cropCode || "Generic"}
                geoJson={plot?.geoJson as any}
            />
        </div>

        {/* ROW 2: RAINFALL (2/3) & OPERATIONS (1/3) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 card fade-in h-full">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                    <h3 style={{ margin: 0, fontWeight: 600 }}>🌧️ التحليل المناخي (30 سنة)</h3>
                </div>
                <PlotRainfallHistoryPanel lat={lat} lng={lng} />
            </div>
            <div className="card fade-in" style={{ padding: 0, overflow: "hidden" }}>
                <PlotPageClient 
                    plotId={plotId} 
                    activeCycle={currentCrop || null} 
                    tasks={currentTasks} 
                />
            </div>
        </div>

        {/* ROW 3: MASONRY GRID (Automatic Packing for Remaining Widgets) */}
        <MasonryGrid>

            {/* 1. Land Cover (Priority: High, Visual) */}
            <div className="h-full">
                <PlotLandCoverPanel lat={lat} lng={lng} />
            </div>
            
            {/* 2. Weather Forecast (Priority: High, Height: Medium) */}
            <div className="h-full">
                <PlotWeatherWidget lat={lat} lng={lng} />
            </div>

            {/* 3. Water Stress Analysis (Priority: High) */}
             <div className="h-full">
                <PlotWaterStressPanel lat={lat} lng={lng} />
            </div>

            {/* 2. Phenology (Priority: High, Height: Short) */}
            <div className="h-full">
                <PlotPhenologyCard 
                    lat={lat}
                    lng={lng}
                    crop={currentCrop?.cropCode || "wheat"}
                />
            </div>

            {/* 4. Soil Properties (Priority: Med, Height: Medium) */}
            <div className="h-full">
                <PlotSoilPanel lat={lat} lng={lng} />
            </div>

            {/* 6. SAR Radar (Priority: Med, Height: Medium) */}
            <div className="h-full">
                <PlotSARPanel lat={lat} lng={lng} />
            </div>

            {/* 7. Environmental Risks (Priority: Low, Height: Short) */}
            <div className="h-full">
                <PlotEnvironmentPanel lat={lat} lng={lng} />
            </div>

            {/* 8. Crop History (Priority: Low, Height: Variable) */}
            <div className="card fade-in h-full">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                    <h3 style={{ margin: 0, fontWeight: 600 }}>📜 سجل المحاصيل</h3>
                </div>
                
                {cropCycles.filter(c => c.status === 'HARVESTED').length === 0 ? (
                    <div style={{ textAlign: "center", padding: "1rem", color: "var(--foreground-muted)", fontSize: "0.875rem" }}>
                        لا توجد دورات زراعية سابقة
                    </div>
                ) : (
                    <div className="custom-scrollbar" style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxHeight: "400px", overflowY: "auto" }}>
                        {cropCycles.filter(c => c.status === 'HARVESTED').map(crop => (
                            <div key={crop.id} style={{ 
                                padding: "0.75rem", 
                                border: "1px solid var(--background-tertiary)", 
                                borderRadius: "0.5rem",
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center"
                            }}>
                                <div>
                                    <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{crop.cropNameAr || crop.cropCode}</div>
                                    <div style={{ fontSize: "0.75rem", color: "var(--foreground-muted)" }}>
                                        {crop.startDate ? crop.startDate.toLocaleDateString('ar-DZ') : 'تاريخ غير محدد'}
                                    </div>
                                </div>
                                <span style={{
                                    padding: "0.15rem 0.5rem",
                                    borderRadius: "99px",
                                    fontSize: "0.65rem",
                                    background: 'var(--background-tertiary)',
                                    color: 'var(--foreground-muted)'
                                }}>
                                    مكتمل
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

        </MasonryGrid>

      </div>
    </div>
  );
}
