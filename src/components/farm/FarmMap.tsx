"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, Polygon, Marker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

// Fix for default markers in Leaflet with Next.js
const icon = L.icon({
  iconUrl: "/images/marker-icon.png",
  shadowUrl: "/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

export interface FarmData {
  id: string;
  latitude?: number | null;
  longitude?: number | null;
  geoJson?: string;
}

export interface PlotData {
  id: string;
  name?: string;
  area?: number | string;
  soilType?: string;
  geoJson?: {
    geometry: {
      type: string;
      coordinates: number[][] | number[][][] | number[][][][]; // Using union for polygon/multipolygon
    }
  };
}

interface FarmMapProps {
  farms: FarmData[];
  plots?: PlotData[];
  onSelectFarm?: (farmId: string) => void;
  onSelectPlot?: (plotId: string) => void;
}

function ChangeView({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  map.setView(center, zoom);
  return null;
}

export default function FarmMap({ farms, plots = [], onSelectPlot, cropName }: FarmMapProps & { cropName?: string }) {
  const [center] = useState<[number, number]>([36.75, 3.05]); // Default: Algiers
  const [zoom] = useState(13);

  // Auto-fit bounds component
  function AutoFitBoundaries({ plots }: { plots: PlotData[] }) {
    const map = useMap();

    useEffect(() => {
      if (plots && plots.length > 0 && plots[0].geoJson) {
        try {
          const geoJson = plots[0].geoJson;
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          let coords: any = [];
          
          if (geoJson.geometry.type === 'Polygon') {
            coords = geoJson.geometry.coordinates[0];
          } else if (geoJson.geometry.type === 'MultiPolygon') {
             // eslint-disable-next-line @typescript-eslint/no-explicit-any
             coords = (geoJson.geometry.coordinates[0] as any)[0];
          }

          if (coords.length > 0) {
             // eslint-disable-next-line @typescript-eslint/no-explicit-any
             const bounds = L.latLngBounds((coords as any[]).map((c: any) => [c[1], c[0]]));
             map.fitBounds(bounds, { padding: [50, 50], animate: true, duration: 1 });
          }
        } catch (e) {
          console.error("Error fitting bounds", e);
        }
      } else if (farms.length > 0 && farms[0].latitude && farms[0].longitude) {
         map.setView([farms[0].latitude, farms[0].longitude], 15);
      }
    }, [plots, map]);

    return null;
  }

  return (
    <div style={{ height: "100%", width: "100%", borderRadius: "1rem", overflow: "hidden", position: "relative" }}>
      <MapContainer 
        center={center} 
        zoom={zoom} 
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={false}
        zoomControl={false}
      >
        <AutoFitBoundaries plots={plots} />
        
        <TileLayer
          attribution='Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        />
        
        {/* Attribution Overlay */}
        <div className="leaflet-bottom leaflet-right" style={{ pointerEvents: 'none', zIndex: 1000 }}>
             <div className="leaflet-control" style={{ 
                 background: 'rgba(0,0,0,0.5)', 
                 color: 'white', 
                 padding: '2px 5px', 
                 fontSize: '10px', 
                 borderRadius: '3px',
                 margin: '0 5px 5px 0'
             }}>
                 Satellite: Esri
             </div>
        </div>
        
        {farms.map((farm) => (
          <div key={farm.id}>
             {/* Farm Boundary if available */}
            {farm.geoJson && (
              <Polygon 
                positions={JSON.parse(farm.geoJson as string)}
                pathOptions={{ color: 'white', weight: 1, fill: false, dashArray: '5, 5' }} 
              />
            )}
          </div>
        ))}

        {/* Render Plots */}
        {plots && plots.map((plot) => (
            plot.geoJson && (
              <Polygon 
                key={plot.id}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                positions={plot.geoJson.geometry.coordinates?.map((ring: any) => ring.map((coord: any) => [coord[1], coord[0]])) || []}
                pathOptions={{ 
                    color: '#facc15', // Yellow 400
                    weight: 3,
                    fillColor: '#facc15', 
                    fillOpacity: 0.1 
                }} 
                eventHandlers={{
                  click: () => onSelectPlot?.(plot.id),
                  mouseover: (e) => { e.target.setStyle({ fillOpacity: 0.3, weight: 4 }); },
                  mouseout: (e) => { e.target.setStyle({ fillOpacity: 0.1, weight: 3 }); }
                }}
              >
                 <Popup className="custom-popup">
                  <div style={{ textAlign: "right", fontFamily: "inherit" }}>
                      <b style={{ fontSize: "1.1rem" }}>{plot.name}</b>
                      <div style={{ margin: "5px 0", height: "1px", background: "#eee" }}/>
                      {cropName && (
                          <div style={{ marginBottom: "0.25rem" }}>
                              🌱 <b>المحصول:</b> {cropName}
                          </div>
                      )}
                      <div>📏 <b>المساحة:</b> {plot.area} هكتار</div>
                      <div>🧱 <b>التربة:</b> {plot.soilType}</div>
                  </div>
                </Popup>
              </Polygon>
            )
        ))}
      </MapContainer>
    </div>
  );
}
