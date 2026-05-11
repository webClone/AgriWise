import { notFound } from "next/navigation";
import { getPlot, getFarm, getPlotCenter, getCropCycles } from "@/lib/farm-services";
import PlotIdentityForm from "@/components/farm/PlotIdentityForm";
import PlotVisualGroundTruth from "@/components/farm/PlotVisualGroundTruth";
import PlotSoilData from "@/components/farm/PlotSoilData";
import CurrentCropStatus from "@/components/farm/CurrentCropStatus";
import DecisionConfiguration from "@/components/farm/DecisionConfiguration";
import ReadinessScore from "@/components/farm/ReadinessScore";

interface PageProps {
  params: Promise<{
    id: string;
    plotId: string;
  }>;
}

export default async function UserInputsPage({ params }: PageProps) {
  const { id, plotId } = await params;

  // 1. Fetch Data
  const [plot, farm, cycles] = await Promise.all([
    getPlot(plotId),
    getFarm(id),
    getCropCycles(plotId)
  ]);

  if (!plot || !farm) {
    notFound();
  }

  // 2. Calculate Weighted Readiness Score
  const checks = {
    geometry: !!plot.geoJson || plot.area > 0,
    crop: cycles && cycles.length > 0,
    // Stricter check: Soil data must have actual values (pH, OM, N, P, K) to count
    soil: plot.soilAnalyses?.some((a: any) => 
        a.ph > 0 || a.organicMatter > 0 || a.nitrogen > 0 || a.phosphorus > 0 || a.potassium > 0
    ),
    photos: plot.photos?.length > 0 || plot.cameras?.length > 0,
    sensors: plot.sensors?.length > 0,
    activeSensors: plot.sensors?.some(s => {
        // Simple check for online status (approximate based on lastSync)
        if (!s.lastSync) return false;
        // Check if sync was within last hour
        const lastSync = new Date(s.lastSync).getTime();
        const now = new Date().getTime();
        const mins = (now - lastSync) / 60000;
        return mins < 60; 
    })
  };
  
  // Weights: Geometry (30), Crop (30), Soil (20), Sensors (20)
  let score = 0;
  if (checks.geometry) score += 30;
  if (checks.crop) score += 30;
  if (checks.soil) score += 20;
  
  // Sensor score is nuanced: 10 pts for having sensors, 10 pts for having *active* sensors
  if (checks.sensors) score += 10;
  if (checks.activeSensors) score += 10;

  // 3. Unlock Status
  const unlocks = {
    irrigation: checks.crop && checks.soil && checks.geometry, // Basic irrigation needs these
    yield: checks.crop && checks.soil && checks.photos,        // Yield needs history/visuals
    alerts: checks.activeSensors                               // Alerts need live data
  };

  // 4. Calculate Center for Map
  const { lat, lng } = getPlotCenter(plot, farm);

  return (
    <div className="min-h-screen p-6 pb-24 space-y-5 max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-white flex items-center gap-3">
          🏗️ Plot Configuration
          <span className="text-[10px] font-bold text-indigo-400 bg-indigo-500/10 px-3 py-1 rounded-full border border-indigo-500/20 uppercase tracking-wider">
            Phase 1: Identity & Geometry
          </span>
        </h1>
        <p className="text-sm text-slate-500 max-w-2xl">
          Establish the Ground Truth for your field. Accurate geometry and soil profiles ensure high-fidelity satellite analysis.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content (Wide) */}
          <div className="lg:col-span-2 space-y-6">
              <CurrentCropStatus 
                cycles={cycles}
                readinessScore={score}
              />
              
              <PlotIdentityForm plot={plot} lat={lat} lng={lng} />
              
              <PlotVisualGroundTruth plot={plot} lat={lat} lng={lng} polygon={plot.geoJson || null} />
              
              <PlotSoilData 
                  plotId={plot.id} 
                  soilAnalyses={plot.soilAnalyses || []} 
                  sensors={plot.sensors || []}
              />
          </div>

          {/* Sidebar (Narrow) - Sticky */}
          <div className="space-y-6">
              <div className="sticky top-24 space-y-6">
                  <ReadinessScore score={score} checks={checks} unlocks={unlocks} />
                  
                  <DecisionConfiguration 
                    initialIrrigation={plot.irrigation}
                    initialSoilType={plot.soilType}
                  />
              </div>
          </div>
      </div>

    </div>
  );
}
