import { useEffect, useState, useRef, useCallback } from "react";
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

// Global reference for programmatic control
let currentDrawHandler: any = null;
let currentEditHandler: any = null;

function AdvancedDrawControl({
  onCreated,
  onModeChange,
}: {
  onCreated: (geoJson: any, area: number, layer: L.Layer | null) => void;
  onModeChange: (mode: "idle" | "drawing" | "editing") => void;
}) {
  const map = useMap();
  const drawnItemsRef = useRef<L.FeatureGroup | null>(null);

  // We expose standard drawing functions on the map instance for the UI to call
  useEffect(() => {
    const drawnItems = new L.FeatureGroup();
    drawnItemsRef.current = drawnItems;
    map.addLayer(drawnItems);

    const emitUpdate = () => {
      const layers = drawnItems.getLayers();
      if (layers.length === 0) {
        onCreated(null, 0, null);
        return;
      }
      const layer = layers[0] as L.Polygon;
      const geoJson = layer.toGeoJSON();
      const latlngs = layer.getLatLngs()[0];
      let area = 0;
      if (latlngs && Array.isArray(latlngs)) {
        area = L.GeometryUtil.geodesicArea(latlngs as L.LatLng[]) / 10000;
      }
      onCreated(geoJson, parseFloat(area.toFixed(2)), layer);
    };

    // Listeners for drawing events
    const handleCreated = (e: any) => {
      drawnItems.clearLayers();
      drawnItems.addLayer(e.layer);
      emitUpdate();
      onModeChange("idle");
    };

    const handleEdited = () => {
      emitUpdate();
      onModeChange("idle");
    };

    const handleDeleted = () => {
      drawnItems.clearLayers();
      emitUpdate();
      onModeChange("idle");
    };

    map.on(L.Draw.Event.CREATED, handleCreated);
    map.on(L.Draw.Event.EDITED, handleEdited);
    map.on(L.Draw.Event.DELETED, handleDeleted);

    // Attach programmatic controllers to map for the React UI to consume
    (map as any).startDrawing = () => {
      if (currentDrawHandler) currentDrawHandler.disable();
      if (currentEditHandler) currentEditHandler.disable();
      
      drawnItems.clearLayers();
      emitUpdate();
      
      const polygonDrawer = new L.Draw.Polygon(map as any, {
        allowIntersection: false,
        showArea: true,
        drawError: { color: "#ef4444", message: "لا يمكن للخطوط أن تتقاطع!" },
        shapeOptions: {
          color: "#22c55e",
          weight: 4,
          opacity: 0.9,
          fillColor: "#22c55e",
          fillOpacity: 0.3,
          dashArray: "8 8",
        },
      });
      
      currentDrawHandler = polygonDrawer;
      polygonDrawer.enable();
      onModeChange("drawing");
    };

    (map as any).startEditing = () => {
      if (currentDrawHandler) currentDrawHandler.disable();
      if (currentEditHandler) currentEditHandler.disable();
      
      if (drawnItems.getLayers().length > 0) {
        const editHandler = new L.EditToolbar.Edit(map as any, {
          featureGroup: drawnItems,
          selectedPathOptions: {
            maintainColor: true,
            opacity: 0.9,
            dashArray: "",
            weight: 5,
          } as any,
        });
        currentEditHandler = editHandler;
        editHandler.enable();
        onModeChange("editing");
      }
    };

    (map as any).saveEditing = () => {
      if (currentEditHandler) {
        currentEditHandler.save();
        currentEditHandler.disable();
        currentEditHandler = null;
        emitUpdate();
        onModeChange("idle");
      }
    };

    (map as any).clearAll = () => {
      if (currentDrawHandler) currentDrawHandler.disable();
      if (currentEditHandler) currentEditHandler.disable();
      drawnItems.clearLayers();
      emitUpdate();
      onModeChange("idle");
    };

    return () => {
      map.off(L.Draw.Event.CREATED, handleCreated);
      map.off(L.Draw.Event.EDITED, handleEdited);
      map.off(L.Draw.Event.DELETED, handleDeleted);
      map.removeLayer(drawnItems);
    };
  }, [map, onCreated, onModeChange]);

  return null;
}

export default function MapDrawer({ center, onDrawCreated, initialGeoJson }: MapDrawerProps) {
  const [mapReady, setMapReady] = useState(false);
  const [mode, setMode] = useState<"idle" | "drawing" | "editing">("idle");
  const [hasPolygon, setHasPolygon] = useState(false);
  const mapRef = useRef<L.Map | null>(null);

  useEffect(() => {
    setMapReady(true);
  }, []);

  const handleCreatedWrapper = useCallback((geoJson: any, area: number, layer: L.Layer | null) => {
    setHasPolygon(!!geoJson);
    onDrawCreated(geoJson, area);
  }, [onDrawCreated]);

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
        style={{ height: "100%", width: "100%", cursor: mode === "drawing" ? "crosshair" : "grab" }}
        scrollWheelZoom={true}
        zoomControl={false}
        ref={mapRef}
      >
        <ChangeView center={center} />
        
        <TileLayer
          attribution='Tiles &copy; Esri'
          url="/api/map/tiles/esri/{z}/{y}/{x}"
        />
        
        <TileLayer
          attribution='Labels &copy; Esri'
          url="/api/map/tiles/esri-labels/{z}/{y}/{x}"
          opacity={0.7}
        />

        <AdvancedDrawControl onCreated={handleCreatedWrapper} onModeChange={setMode} />
      </MapContainer>

      {/* ─── Custom Floating UX Toolbar ─────────────────────────────── */}
      
      {/* Top Banner Instruction */}
      <div style={{
        position: "absolute", top: "16px", left: "50%", transform: "translateX(-50%)",
        zIndex: 1000, pointerEvents: "none",
        display: "flex", flexDirection: "column", alignItems: "center", gap: "8px",
        transition: "all 0.3s ease",
      }}>
        {mode === "idle" && !hasPolygon && (
          <div style={{
            background: "rgba(15, 23, 42, 0.85)", backdropFilter: "blur(12px)",
            padding: "8px 16px", borderRadius: "20px", border: "1px solid rgba(59, 130, 246, 0.3)",
            color: "#93c5fd", fontSize: "0.85rem", fontWeight: 600,
            boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          }}>
            👋 ابدأ برسم حدود المزرعة بدقة
          </div>
        )}
        {mode === "drawing" && (
          <div style={{
            background: "rgba(22, 163, 74, 0.9)", backdropFilter: "blur(12px)",
            padding: "8px 16px", borderRadius: "20px", border: "1px solid rgba(34, 197, 94, 0.5)",
            color: "#fff", fontSize: "0.85rem", fontWeight: 600,
            boxShadow: "0 8px 32px rgba(34, 197, 94, 0.3)",
            animation: "pulse 2s infinite",
          }}>
            📍 انقر على الخريطة لوضع النقاط، وانقر على أول نقطة للإنهاء
          </div>
        )}
        {mode === "editing" && (
          <div style={{
            background: "rgba(234, 179, 8, 0.9)", backdropFilter: "blur(12px)",
            padding: "8px 16px", borderRadius: "20px", border: "1px solid rgba(250, 204, 21, 0.5)",
            color: "#000", fontSize: "0.85rem", fontWeight: 600,
            boxShadow: "0 8px 32px rgba(234, 179, 8, 0.3)",
          }}>
            ✂️ اسحب النقاط لتعديل الشكل، ثم احفظ التعديلات
          </div>
        )}
      </div>

      {/* Bottom Floating Toolbar */}
      <div style={{
        position: "absolute", bottom: "24px", left: "50%", transform: "translateX(-50%)",
        zIndex: 1000, display: "flex", gap: "12px",
        background: "rgba(15, 23, 42, 0.85)", backdropFilter: "blur(16px)",
        padding: "8px", borderRadius: "16px", border: "1px solid rgba(71, 85, 105, 0.3)",
        boxShadow: "0 12px 40px rgba(0,0,0,0.5)",
      }}>
        {mode === "idle" && (
          <>
            <button
              onClick={() => (mapRef.current as any)?.startDrawing()}
              style={{
                background: "linear-gradient(135deg, #22c55e, #16a34a)", color: "#fff",
                border: "none", padding: "10px 20px", borderRadius: "10px",
                fontWeight: 600, fontSize: "0.9rem", cursor: "pointer",
                display: "flex", alignItems: "center", gap: "8px",
                boxShadow: "0 4px 12px rgba(34, 197, 94, 0.3)",
                transition: "transform 0.2s ease, filter 0.2s ease",
              }}
              onMouseOver={e => e.currentTarget.style.filter = "brightness(1.1)"}
              onMouseOut={e => e.currentTarget.style.filter = "brightness(1)"}
              onMouseDown={e => e.currentTarget.style.transform = "scale(0.95)"}
              onMouseUp={e => e.currentTarget.style.transform = "scale(1)"}
            >
              <span>{hasPolygon ? "إعادة الرسم" : "رسم القطعة"}</span>
              <span style={{ fontSize: "1.2rem" }}>✏️</span>
            </button>
            
            {hasPolygon && (
              <>
                <div style={{ width: "1px", background: "rgba(71, 85, 105, 0.3)", margin: "4px 0" }} />
                <button
                  onClick={() => (mapRef.current as any)?.startEditing()}
                  style={{
                    background: "rgba(51, 65, 85, 0.5)", color: "#e2e8f0",
                    border: "1px solid rgba(71, 85, 105, 0.4)", padding: "10px 16px", borderRadius: "10px",
                    fontWeight: 600, fontSize: "0.9rem", cursor: "pointer",
                    display: "flex", alignItems: "center", gap: "8px",
                    transition: "all 0.2s ease",
                  }}
                  onMouseOver={e => e.currentTarget.style.background = "rgba(71, 85, 105, 0.6)"}
                  onMouseOut={e => e.currentTarget.style.background = "rgba(51, 65, 85, 0.5)"}
                >
                  <span>تعديل</span>
                  <span>✂️</span>
                </button>
                <button
                  onClick={() => (mapRef.current as any)?.clearAll()}
                  style={{
                    background: "rgba(239, 68, 68, 0.15)", color: "#f87171",
                    border: "1px solid rgba(239, 68, 68, 0.3)", padding: "10px 16px", borderRadius: "10px",
                    fontWeight: 600, fontSize: "0.9rem", cursor: "pointer",
                    display: "flex", alignItems: "center", gap: "8px",
                    transition: "all 0.2s ease",
                  }}
                  onMouseOver={e => { e.currentTarget.style.background = "rgba(239, 68, 68, 0.25)"; }}
                  onMouseOut={e => { e.currentTarget.style.background = "rgba(239, 68, 68, 0.15)"; }}
                >
                  <span>حذف</span>
                  <span>🗑️</span>
                </button>
              </>
            )}
          </>
        )}

        {mode === "editing" && (
          <button
            onClick={() => (mapRef.current as any)?.saveEditing()}
            style={{
              background: "linear-gradient(135deg, #eab308, #ca8a04)", color: "#fff",
              border: "none", padding: "10px 24px", borderRadius: "10px",
              fontWeight: 600, fontSize: "0.9rem", cursor: "pointer",
              display: "flex", alignItems: "center", gap: "8px",
              boxShadow: "0 4px 12px rgba(234, 179, 8, 0.3)",
              transition: "transform 0.2s ease, filter 0.2s ease",
            }}
            onMouseOver={e => e.currentTarget.style.filter = "brightness(1.1)"}
            onMouseOut={e => e.currentTarget.style.filter = "brightness(1)"}
            onMouseDown={e => e.currentTarget.style.transform = "scale(0.95)"}
            onMouseUp={e => e.currentTarget.style.transform = "scale(1)"}
          >
            <span>حفظ التعديلات</span>
            <span>💾</span>
          </button>
        )}

        {mode === "drawing" && (
          <button
            onClick={() => (mapRef.current as any)?.clearAll()}
            style={{
              background: "rgba(51, 65, 85, 0.5)", color: "#e2e8f0",
              border: "1px solid rgba(71, 85, 105, 0.4)", padding: "10px 24px", borderRadius: "10px",
              fontWeight: 600, fontSize: "0.9rem", cursor: "pointer",
              display: "flex", alignItems: "center", gap: "8px",
              transition: "all 0.2s ease",
            }}
            onMouseOver={e => e.currentTarget.style.background = "rgba(71, 85, 105, 0.6)"}
            onMouseOut={e => e.currentTarget.style.background = "rgba(51, 65, 85, 0.5)"}
          >
            <span>إلغاء الرسم</span>
            <span>✖️</span>
          </button>
        )}
      </div>

      {/* Hide default Leaflet Draw controls using scoped CSS injection */}
      <style>{`
        .leaflet-draw-toolbar { display: none !important; }
        /* Make drawing vertices larger for better UX */
        .leaflet-editing-icon {
          width: 14px !important;
          height: 14px !important;
          border-radius: 50% !important;
          background: #fff !important;
          border: 3px solid #22c55e !important;
          margin-left: -7px !important;
          margin-top: -7px !important;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
        }
        .leaflet-grab { cursor: grab !important; }
        .leaflet-crosshair { cursor: crosshair !important; }
        .leaflet-interactive { cursor: pointer; }
      `}</style>
    </div>
  );
}
