import { useEffect, useState } from "react";
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

interface MapDrawerProps {
  center: [number, number];
  onDrawCreated: (geoJson: any, area: number) => void;
}

function ChangeView({ center }: { center: [number, number] }) {
  const map = useMap();
  map.setView(center, 15);
  return null;
}

function DrawControl({ onCreated }: { onCreated: (geoJson: any, area: number) => void }) {
  const map = useMap();

  useEffect(() => {
    // Initialize FeatureGroup to store drawn items
    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);

    // Initialize Draw Control
    const drawControl = new L.Control.Draw({
      edit: {
        featureGroup: drawnItems,
        remove: true,
        edit: false // Disable editing for simplicity or enable if needed
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

    // Event Handler
    const handleCreated = (e: any) => {
      const layer = e.layer;
      drawnItems.addLayer(layer);

      const geoJson = layer.toGeoJSON();

      // Calculate area
      const latlngs = layer.getLatLngs()[0];
      let area = 0;
      if (latlngs) {
         area = L.GeometryUtil.geodesicArea(latlngs) / 10000; // Convert sq meters to hectares
      }

      onCreated(geoJson, parseFloat(area.toFixed(2)));
    };

    map.on(L.Draw.Event.CREATED, handleCreated);

    return () => {
      map.removeControl(drawControl);
      map.off(L.Draw.Event.CREATED, handleCreated);
      map.removeLayer(drawnItems);
    };
  }, [map, onCreated]);

  return null;
}

export default function MapDrawer({ center, onDrawCreated }: MapDrawerProps) {
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    setMapReady(true);
  }, []);

  if (!mapReady) return <div className="h-[300px] w-full bg-gray-100 flex items-center justify-center">Loading Drawing Tools...</div>;

  return (
    <div style={{ height: "300px", width: "100%", borderRadius: "0.5rem", overflow: "hidden", border: "1px solid #ccc" }}>
      <MapContainer 
        center={center} 
        zoom={15} 
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={false}
      >
        <ChangeView center={center} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <DrawControl onCreated={onDrawCreated} />
      </MapContainer>
    </div>
  );
}
