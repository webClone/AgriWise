"use client";

import { useEffect, useState, useRef } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
import L from "leaflet";
import "leaflet-draw";

// Fix for default markers
const icon = L.icon({
  iconUrl: "/images/marker-icon.png",
  shadowUrl: "/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = icon;

interface PlotMapEditorProps {
  center: [number, number];
  initialGeoJson?: any;
  readOnly?: boolean;
  onSave: (geoJson: any, area: number) => void;
}

function ChangeView({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, 16);
  }, [center, map]);
  return null;
}

function DrawControl({ initialGeoJson, readOnly, onCreated }: { initialGeoJson?: any, readOnly?: boolean, onCreated: (geoJson: any, area: number) => void }) {
  const map = useMap();
  const drawnItemsRef = useRef<L.FeatureGroup | null>(null);

  useEffect(() => {
    // Initialize FeatureGroup to store drawn items
    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    drawnItemsRef.current = drawnItems;

    // Load initial GeoJSON if available
    if (initialGeoJson) {
        try {
            const layer = L.geoJSON(initialGeoJson, {
                style: {
                    color: "#97009c",
                    weight: 3
                }
            });
            layer.eachLayer((l: any) => {
                drawnItems.addLayer(l);
                // Center map on existing plot
                if (l.getBounds) {
                    map.fitBounds(l.getBounds(), { padding: [50, 50] });
                }
            });
        } catch (e) {
            console.error("Invalid GeoJSON", e);
        }
    }

    if (!readOnly) {
      // Initialize Draw Control with Edit enabled
      const drawControl = new L.Control.Draw({
        edit: {
          featureGroup: drawnItems,
          remove: true,
        },
        draw: {
          rectangle: false,
          circle: false,
          circlemarker: false,
          marker: false,
          polyline: false,
          polygon: {
            allowIntersection: false,
            showArea: true,
            shapeOptions: {
              color: "#97009c"
            }
          }
        }
      });

      map.addControl(drawControl);

      // Event Handlers
      const handleCreated = (e: any) => {
        drawnItems.clearLayers(); 
        const layer = e.layer;
        drawnItems.addLayer(layer);
        updateParent(layer);
      };

      const handleEdited = (e: any) => {
          const layers = e.layers;
          layers.eachLayer((layer: any) => {
              updateParent(layer);
          });
      };

      const updateParent = (layer: any) => {
          const geoJson = layer.toGeoJSON();
          const latlngs = layer.getLatLngs()[0];
          let area = 0;
          if (latlngs) {
             area = L.GeometryUtil.geodesicArea(latlngs) / 10000; 
          }
          onCreated(geoJson, parseFloat(area.toFixed(4)));
      };

      map.on(L.Draw.Event.CREATED, handleCreated);
      map.on(L.Draw.Event.EDITED, handleEdited);

      return () => {
        map.removeControl(drawControl);
        map.off(L.Draw.Event.CREATED, handleCreated);
        map.off(L.Draw.Event.EDITED, handleEdited);
        map.removeLayer(drawnItems);
      };
    } else {
       return () => {
         map.removeLayer(drawnItems);
       };
    }
  }, [map, initialGeoJson, readOnly, onCreated]);

  return null;
}

export default function PlotMapEditor({ center, initialGeoJson, readOnly, onSave }: PlotMapEditorProps) {
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    setMapReady(true);
  }, []);

  if (!mapReady) return <div className="h-[400px] w-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center animate-pulse rounded-lg">Loading Editor...</div>;

  return (
    <div style={{ height: "400px", width: "100%", borderRadius: "0.5rem", overflow: "hidden", border: "1px solid #e2e8f0" }}>
      <MapContainer 
        center={center} 
        zoom={16} 
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={false}
      >
        <ChangeView center={center} />
        <TileLayer
          attribution='&copy; Start with Esri'
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        />
         <TileLayer
          attribution='Overlay'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          opacity={0.4}
        />
        <DrawControl initialGeoJson={initialGeoJson} onCreated={onSave} />
      </MapContainer>
    </div>
  );
}
