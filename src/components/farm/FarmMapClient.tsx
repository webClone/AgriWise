"use client";

import dynamic from "next/dynamic";

// Dynamically import Map (Client side only)
const FarmMap = dynamic(() => import("@/components/farm/FarmMap"), { 
  ssr: false,
  loading: () => (
    <div className="h-[400px] w-full bg-gray-100 rounded-xl animate-pulse flex items-center justify-center text-gray-400">
      Loading Map...
    </div>
  )
});

// Re-export with proper typing
interface Farm {
  id: string;
  name: string;
  latitude?: number | null;
  longitude?: number | null;
  wilaya: string;
  commune?: string | null;
  totalArea: number;
}
import { useRouter } from "next/navigation";
import { FarmData, PlotData } from "@/components/farm/FarmMap";

interface FarmMapClientProps {
  farms: Farm[];
  plots?: PlotData[];
  cropName?: string;
}

export default function FarmMapClient({ farms, plots, cropName }: FarmMapClientProps) {
  const router = useRouter();

  const handleSelectPlot = (plotId: string) => {
    // Assuming we are on a farm detail page and the first farm is the current one
    if (farms.length > 0) {
      router.push(`/farm/${farms[0].id}/plot/${plotId}`);
    }
  };

  return <FarmMap farms={farms as unknown as FarmData[]} plots={plots} onSelectPlot={handleSelectPlot} cropName={cropName} />;
}
