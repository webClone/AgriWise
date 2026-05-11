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

interface MapDrawerProps {
  center: [number, number];
  onDrawCreated: (geoJson: any, area: number) => void;
  initialGeoJson?: any;
}

function ChangeView({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, 16);
  }, [center, map]);
  return null;
}

function DrawControl({ onCreated }: { onCreated: (geoJson: any, area: number) => void }) {
  const map = useMap();
  const drawnItemsRef = useRef<L.FeatureGroup | null>(null);

  useEffect(() => {
    const drawnItems = new L.FeatureGroup();
    drawnItemsRef.current = drawnItems;
    map.addLayer(drawnItems);

    const drawControl = new L.Control.Draw({
      position: "topleft",
      edit: {
        featureGroup: drawnItems,
        remove: true,
        edit: {},
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
          drawError: {
            color: "#ef4444",
            message: "لا يمكن للخطوط أن تتقاطع!",
          },
          shapeOptions: {
            color: "#22c55e",
            weight: 2,
            fillColor: "#22c55e",
            fillOpacity: 0.15,
          },
        },
      },
    });

    map.addControl(drawControl);

    const handleCreated = (e: any) => {
      // Clear any existing drawn layers first (single polygon mode)
      drawnItems.clearLayers();
      const layer = e.layer;
      drawnItems.addLayer(layer);

      const geoJson = layer.toGeoJSON();
      const latlngs = layer.getLatLngs()[0];
      let area = 0;
      if (latlngs) {
        area = L.GeometryUtil.geodesicArea(latlngs) / 10000;
      }
      onCreated(geoJson, parseFloat(area.toFixed(2)));
    };

    const handleEdited = (e: any) => {
      const layers = e.layers;
      layers.eachLayer((layer: any) => {
        const geoJson = layer.toGeoJSON();
        const latlngs = layer.getLatLngs()[0];
        let area = 0;
        if (latlngs) {
          area = L.GeometryUtil.geodesicArea(latlngs) / 10000;
        }
        onCreated(geoJson, parseFloat(area.toFixed(2)));
      });
    };

    const handleDeleted = () => {
      onCreated(null, 0);
    };

    map.on(L.Draw.Event.CREATED, handleCreated);
    map.on(L.Draw.Event.EDITED, handleEdited);
    map.on(L.Draw.Event.DELETED, handleDeleted);

    return () => {
      map.removeControl(drawControl);
      map.off(L.Draw.Event.CREATED, handleCreated);
      map.off(L.Draw.Event.EDITED, handleEdited);
      map.off(L.Draw.Event.DELETED, handleDeleted);
      map.removeLayer(drawnItems);
    };
  }, [map, onCreated]);

  return null;
}

export default function MapDrawer({ center, onDrawCreated, initialGeoJson }: MapDrawerProps) {
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    setMapReady(true);
  }, []);

  if (!mapReady) {
    return (
      <div style={{
        height: "100%", width: "100%",
        background: "linear-gradient(135deg, #0c1224, #131b36)",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "#64748b",
      }}>
        جاري تحميل أدوات الرسم...
      </div>
    );
  }

  return (
    <div style={{ height: "100%", width: "100%", position: "relative" }}>
      <MapContainer 
        center={center} 
        zoom={16} 
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={true}
        zoomControl={false}
      >
        <ChangeView center={center} />
        
        {/* Satellite imagery as base layer */}
        <TileLayer
          attribution='Tiles &copy; Esri'
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        />
        
        {/* Transparent labels overlay on top of satellite */}
        <TileLayer
          attribution='Labels &copy; Esri'
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
          opacity={0.7}
        />

        {/* Zoom control in bottom-left */}
        <div style={{ position: "absolute", bottom: "12px", left: "12px", zIndex: 1000 }}>
          {/* Handled by leaflet */}
        </div>

        <DrawControl onCreated={onDrawCreated} />
      </MapContainer>

      {/* Crosshair center indicator */}
      <div style={{
        position: "absolute", top: "50%", left: "50%",
        transform: "translate(-50%, -50%)",
        pointerEvents: "none", zIndex: 500, opacity: 0.3,
      }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1">
          <line x1="12" y1="4" x2="12" y2="20" />
          <line x1="4" y1="12" x2="20" y2="12" />
        </svg>
      </div>
    </div>
  );
}
