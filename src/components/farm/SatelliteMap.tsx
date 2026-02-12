"use client";

import { useEffect, useMemo } from "react";
import { 
    MapContainer, 
    TileLayer, 
    GeoJSON, 
    Rectangle, 
    useMap, 
    WMSTileLayer,
    ImageOverlay
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { generateRasterGrid, RasterPixel } from "@/lib/satellite-providers/satellite-utils";
import L from "leaflet";

// Fix for default marker icons in Leaflet + Next.js
if (typeof window !== "undefined") {
  // @ts-expect-error - Leaflet icon property redefinition
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
    iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
    shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  });
}

interface SatelliteMapProps {
    lat: number;
    lng: number;
    geoJson?: any;
    metric?: string;
    imageUrl?: string;
    imageBounds?: [[number, number], [number, number]];
    interactive?: boolean;
    provider?: string;
    avgValue?: number;
    date?: string;
}

function MapController({ lat, lng, geoJson }: { lat: number; lng: number, geoJson?: any }) {
    const map = useMap();
    
    useEffect(() => {
        if (geoJson) {
            try {
                const layer = L.geoJSON(geoJson);
                map.fitBounds(layer.getBounds(), { padding: [50, 50] });
            } catch {
                map.setView([lat, lng], 16);
            }
        } else {
            map.setView([lat, lng], 16);
        }
    }, [lat, lng, geoJson, map]);

    return null;
}

export default function SatelliteMap({ 
    lat, 
    lng, 
    geoJson, 
    metric = 'none', 
    avgValue, 
    imageUrl,
    imageBounds,
    interactive = true,
    provider = 'openweather',
    date
}: SatelliteMapProps) {
    const rasterPixels = useMemo<RasterPixel[]>(() => {
        if (metric === 'none' || !geoJson || provider === 'sentinel') return []; 
        return generateRasterGrid(geoJson, metric, avgValue);
    }, [geoJson, metric, avgValue, provider]);

    const wmsLayerId = useMemo(() => {
        switch(metric) {
            case 'none': return 'TRUE-COLOR';
            case 'false-color': return 'FALSE-COLOR';
            case 'ndvi': return 'NDVI';
            case 'evi': return 'EVI';
            case 'savi': return 'SAVI';
            case 'moisture-index': return 'NDMI';
            case 'moisture-stress': return 'NDMI';
            case 'ndwi': return 'NDWI';
            case 'agriculture': return 'AGRICULTURE';
            case 'barren-soil': return 'BARREN-SOIL';
            default: return 'TRUE-COLOR';
        }
    }, [metric]);

    return (
        <div className="relative w-full h-full bg-slate-900 border-2 border-slate-800 rounded-lg overflow-hidden shadow-2xl">
            <style jsx global>{`
                .raster-pixel {
                    stroke: none;
                    shape-rendering: crispEdges; 
                    transition: fill 0.3s ease;
                }
                .raster-pixel:hover {
                    fill-opacity: 1 !important;
                    filter: brightness(1.2);
                }
            `}</style>

            <MapContainer 
                center={[lat, lng]} 
                zoom={16} 
                style={{ height: "100%", width: "100%", background: "transparent" }}
                zoomControl={false} 
                dragging={interactive}
                scrollWheelZoom={interactive}
                doubleClickZoom={interactive}
                attributionControl={false}
            >
                <TileLayer
                    url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                    attribution="Tiles &copy; Esri"
                />

                {provider === 'sentinel' && (
                    <WMSTileLayer
                        {...({
                            url: "/api/satellite/sentinel/wms",
                            layers: wmsLayerId,
                            format: "image/png",
                            transparent: true,
                            attribution: "&copy; Copernicus Data Space",
                            version: "1.3.0",
                            uppercase: true,
                            time: date ? `${date}/${date}` : undefined
                        } as any)}
                    />
                )}

                {imageUrl && imageBounds && (
                    <ImageOverlay
                        url={imageUrl}
                        bounds={imageBounds}
                        opacity={metric === 'none' ? 1 : 0.4}
                        zIndex={10}
                    />
                )}

                {rasterPixels.length > 0 && (
                    <>
                       {rasterPixels.map((p, i) => (
                           <Rectangle 
                               key={i}
                               bounds={p.bounds as any}
                               pathOptions={{
                                   fillColor: p.color,
                                   fillOpacity: 0.85,
                                   stroke: false,
                               }}
                               className="raster-pixel"
                           />
                       ))}
                    </>
                )}

                {geoJson && (
                    <GeoJSON 
                        data={geoJson} 
                        style={{
                            color: "#fff",
                            weight: 2,
                            fillColor: "rgba(255,255,255,0.05)",
                            fillOpacity: 0.1,
                            dashArray: "4, 1"
                        }}
                    />
                )}
                <MapController lat={lat} lng={lng} geoJson={geoJson} />
            </MapContainer>

            <div className="absolute bottom-4 right-4 z-1000 bg-slate-900/80 backdrop-blur-md p-2 rounded border border-slate-700 pointer-events-none flex items-center gap-2">
                <div className="text-[10px] font-bold text-slate-400">LOW</div>
                <div className="flex h-1.5 w-24 rounded-full overflow-hidden bg-gradient-to-r from-red-800 via-yellow-500 to-emerald-800" />
                <div className="text-[10px] font-bold text-emerald-400">HIGH</div>
            </div>
        </div>
    );
}
