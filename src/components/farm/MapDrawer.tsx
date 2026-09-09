"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { MapContainer, TileLayer, useMap, useMapEvents, CircleMarker } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
import L from "leaflet";
import "leaflet-draw";
import {
  detectFieldAtPoint,
  scanViewportPlots,
  type DetectedPlot,
} from "@/lib/map/plotBoundaryDetector";

// Fix for default markers in Leaflet
const icon = L.icon({
  iconUrl: "/images/marker-icon.png",
  shadowUrl: "/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = icon;

export interface MapDrawerProps {
  center: [number, number];
  onDrawCreated: (geoJson: any, area: number) => void;
  initialGeoJson?: any;
  lang?: "en" | "ar";
}

const I18N = {
  en: {
    loadingMap: "Loading map & satellite imagery...",
    startDrawGuide: "👋 Choose Magic Wand 🪄, Auto-Scan ⚡, or draw manually ✏️",
    drawingGuide: "📍 Click on map to place points. Click the first point to finish",
    editingGuide: "✂️ Drag points to adjust boundary, then click Save",
    wandGuide: "🪄 Click inside any field to snap its boundary automatically",
    scanningGuide: "🛰️ AI analyzing satellite imagery for field boundaries...",
    candidatesGuide: (count: number) =>
      `🎯 Found ${count} field candidate${count > 1 ? "s" : ""} — click any field to select`,
    drawBtn: "Manual Draw",
    redrawBtn: "Redraw",
    editBtn: "Edit",
    deleteBtn: "Delete",
    saveEditBtn: "Save Edits",
    cancelDrawBtn: "Cancel",
    magicWandBtn: "Magic Wand",
    autoScanBtn: "Auto-Detect Plots",
    clearCandidatesBtn: "Clear Suggestions",
    wandDetecting: "🛰️ AI analyzing satellite tiles...",
    wandSuccess: (area: number) => `✨ Field detected: ${area} ha`,
    wandFail:
      "Could not detect clear boundary. Try clicking in the center of a visible field, or zoom in closer.",
    noCrossLines: "Lines cannot self-intersect!",
    fieldDetected: "Field Selected",
    clickToSelect: "Click to select",
  },
  ar: {
    loadingMap: "جاري تحميل أدوات الخريطة وصور الأقمار الصناعية...",
    startDrawGuide: "👋 اختر المحدد الذكي 🪄، المسح التلقائي ⚡، أو ارسم يدوياً ✏️",
    drawingGuide: "📍 انقر على الخريطة لوضع النقاط، وانقر على أول نقطة للإنهاء",
    editingGuide: "✂️ اسحب النقاط لتعديل الشكل، ثم اضغط حفظ التعديلات",
    wandGuide: "🪄 انقر داخل أي حقل على الخريطة لكشف حدوده تلقائياً",
    scanningGuide: "🛰️ الذكاء الاصطناعي يحلل صور الأقمار الصناعية لكشف حدود الحقول...",
    candidatesGuide: (count: number) =>
      `🎯 تم اكتشاف ${count} حقل — انقر على أي حقل لاختياره`,
    drawBtn: "رسم يدوي",
    redrawBtn: "إعادة الرسم",
    editBtn: "تعديل",
    deleteBtn: "حذف",
    saveEditBtn: "حفظ التعديلات",
    cancelDrawBtn: "إلغاء الرسم",
    magicWandBtn: "المحدد الذكي",
    autoScanBtn: "كشف القطع تلقائياً",
    clearCandidatesBtn: "مسح المقترحات",
    wandDetecting: "🛰️ الذكاء الاصطناعي يحلل صور الأقمار الصناعية...",
    wandSuccess: (area: number) => `✨ تم كشف الحقل: ${area} هكتار`,
    wandFail: "تعذر كشف حدود واضحة. حاول النقر في وسط حقل مرئي، أو قم بتكبير الصورة.",
    noCrossLines: "لا يمكن للخطوط أن تتقاطع!",
    fieldDetected: "تم تحديد الحقل",
    clickToSelect: "انقر للاختيار",
  },
};

function ChangeView({ center }: { center: [number, number] }) {
  const map = useMap();
  const initialCenterRef = useRef<string | null>(null);

  useEffect(() => {
    const key = `${center[0].toFixed(5)},${center[1].toFixed(5)}`;
    if (initialCenterRef.current === null) {
      initialCenterRef.current = key;
      return; // Initial positioning is handled by MapContainer center prop
    }
    // Only reposition if the farm center actually changes to a different coordinate
    if (initialCenterRef.current !== key) {
      initialCenterRef.current = key;
      map.setView(center, map.getZoom() || 16);
    }
  }, [center[0], center[1], map]);

  return null;
}

// Global references for programmatic draw controllers
let currentDrawHandler: any = null;
let currentEditHandler: any = null;

function AdvancedDrawControl({
  onCreated,
  onModeChange,
  initialGeoJson,
  lang = "en",
}: {
  onCreated: (geoJson: any, area: number, layer: L.Layer | null) => void;
  onModeChange: (mode: "idle" | "drawing" | "editing" | "wand") => void;
  initialGeoJson?: any;
  lang?: "en" | "ar";
}) {
  const map = useMap();
  const drawnItemsRef = useRef<L.FeatureGroup | null>(null);
  const onCreatedRef = useRef(onCreated);
  onCreatedRef.current = onCreated;
  const onModeChangeRef = useRef(onModeChange);
  onModeChangeRef.current = onModeChange;
  const langRef = useRef(lang);
  langRef.current = lang;
  const initialLoadedRef = useRef(false);

  useEffect(() => {
    const drawnItems = new L.FeatureGroup();
    drawnItemsRef.current = drawnItems;
    map.addLayer(drawnItems);

    const emitUpdate = () => {
      const layers = drawnItems.getLayers();
      if (layers.length === 0) {
        onCreatedRef.current(null, 0, null);
        return;
      }
      const layer = layers[0] as L.Polygon;
      const geoJson = layer.toGeoJSON();
      const latlngs = layer.getLatLngs()[0];
      let area = 0;
      if (latlngs && Array.isArray(latlngs)) {
        area = L.GeometryUtil.geodesicArea(latlngs as L.LatLng[]) / 10000;
      }
      onCreatedRef.current(geoJson, parseFloat(area.toFixed(2)), layer);
    };

    // Load initialGeoJson ONCE if provided on mount
    if (!initialLoadedRef.current && initialGeoJson?.geometry?.coordinates?.[0]) {
      initialLoadedRef.current = true;
      const rawCoords = initialGeoJson.geometry.coordinates[0];
      const latlngs: L.LatLngTuple[] = rawCoords.map((c: any) => [c[1], c[0]] as L.LatLngTuple);
      const initialPoly = L.polygon(latlngs, {
        color: "#22c55e",
        weight: 4,
        opacity: 0.9,
        fillColor: "#22c55e",
        fillOpacity: 0.35,
      });
      drawnItems.addLayer(initialPoly);
      // NOTE: Do not emitUpdate() here; parent already provided initialGeoJson.
    }

    const handleCreated = (e: any) => {
      drawnItems.clearLayers();
      drawnItems.addLayer(e.layer);
      emitUpdate();
      onModeChangeRef.current("idle");
    };

    const handleEdited = () => {
      emitUpdate();
      onModeChangeRef.current("idle");
    };

    const handleDeleted = () => {
      drawnItems.clearLayers();
      emitUpdate();
      onModeChangeRef.current("idle");
    };

    map.on(L.Draw.Event.CREATED, handleCreated);
    map.on(L.Draw.Event.EDITED, handleEdited);
    map.on(L.Draw.Event.DELETED, handleDeleted);

    // Attach programmatic controllers to map instance
    (map as any).setPolygonGeoJson = (geoJson: any) => {
      if (currentDrawHandler) currentDrawHandler.disable();
      if (currentEditHandler) currentEditHandler.disable();

      drawnItems.clearLayers();

      const coords = geoJson?.geometry
        ? geoJson.geometry.coordinates[0]
        : geoJson?.coordinates?.[0];

      if (coords && Array.isArray(coords)) {
        const latlngs: L.LatLngTuple[] = coords.map((c: any) => [c[1], c[0]] as L.LatLngTuple);
        const poly = L.polygon(latlngs, {
          color: "#22c55e",
          weight: 4,
          opacity: 0.95,
          fillColor: "#22c55e",
          fillOpacity: 0.35,
        });
        drawnItems.addLayer(poly);
        emitUpdate();
        onModeChangeRef.current("idle");

        // Only adjust view if the newly detected polygon is outside the current viewport
        try {
          const bounds = poly.getBounds();
          if (bounds && bounds.isValid()) {
            map.invalidateSize();
            const currentBounds = map.getBounds();
            if (!currentBounds.contains(bounds)) {
              map.fitBounds(bounds, { padding: [40, 40], maxZoom: 18, animate: true });
            }
          }
        } catch (fitErr) {
          console.warn("[MapDrawer] fitBounds safely handled:", fitErr);
        }
      }
    };

    (map as any).startDrawing = () => {
      if (currentDrawHandler) currentDrawHandler.disable();
      if (currentEditHandler) currentEditHandler.disable();

      drawnItems.clearLayers();
      emitUpdate();

      const t = I18N[langRef.current];
      const polygonDrawer = new L.Draw.Polygon(map as any, {
        allowIntersection: false,
        showArea: true,
        drawError: { color: "#ef4444", message: t.noCrossLines },
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
      onModeChangeRef.current("drawing");
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
        onModeChangeRef.current("editing");
      }
    };

    (map as any).saveEditing = () => {
      if (currentEditHandler) {
        currentEditHandler.save();
        currentEditHandler.disable();
        currentEditHandler = null;
        emitUpdate();
        onModeChangeRef.current("idle");
      }
    };

    (map as any).clearAll = () => {
      if (currentDrawHandler) currentDrawHandler.disable();
      if (currentEditHandler) currentEditHandler.disable();
      drawnItems.clearLayers();
      emitUpdate();
      onModeChangeRef.current("idle");
    };

    return () => {
      map.off(L.Draw.Event.CREATED, handleCreated);
      map.off(L.Draw.Event.EDITED, handleEdited);
      map.off(L.Draw.Event.DELETED, handleDeleted);
      map.removeLayer(drawnItems);
    };
  }, [map]);

  return null;
}

/**
 * Handles Magic Wand clicks on the map:
 * Intercepts clicks when mode === "wand" and runs computer vision detection.
 */
function MagicWandHandler({
  active,
  onDetectStart,
  onDetectEnd,
  onDetected,
  onError,
  lang = "en",
}: {
  active: boolean;
  onDetectStart: () => void;
  onDetectEnd: () => void;
  onDetected: (plot: DetectedPlot) => void;
  onError: (msg: string) => void;
  lang?: "en" | "ar";
}) {
  const map = useMap();
  const [clickedLatLng, setClickedLatLng] = useState<L.LatLng | null>(null);

  useMapEvents({
    click: async (e) => {
      if (!active) return;
      setClickedLatLng(e.latlng);
      onDetectStart();

      try {
        console.log(`[Magic Wand] Clicked at [${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}]`);
        const detected = await detectFieldAtPoint(map, e.latlng);
        if (detected) {
          console.log(`[Magic Wand] Detected: ${detected.name}, ${detected.areaHa}ha, source=${detected.source}`);
          (map as any).setPolygonGeoJson(detected.geoJson);
          onDetected(detected);
        } else {
          console.warn("[Magic Wand] No boundary detected");
          onError(I18N[lang].wandFail);
        }
      } catch (err) {
        console.error("[Magic Wand] Detection error:", err);
        onError(I18N[lang].wandFail);
      } finally {
        setClickedLatLng(null);
        onDetectEnd();
      }
    },
  });

  if (!clickedLatLng) return null;

  return (
    <CircleMarker
      center={clickedLatLng}
      radius={12}
      pathOptions={{
        color: "#22c55e",
        fillColor: "#4ade80",
        fillOpacity: 0.75,
        weight: 3,
        className: "pulsing-wand-marker",
      }}
    />
  );
}

/**
 * Renders candidate field polygons discovered by Viewport Scanning.
 */
function CandidatesLayer({
  candidates,
  onSelect,
  lang = "en",
}: {
  candidates: DetectedPlot[];
  onSelect: (plot: DetectedPlot) => void;
  lang?: "en" | "ar";
}) {
  const map = useMap();
  const layerGroupRef = useRef<L.FeatureGroup | null>(null);

  useEffect(() => {
    if (!layerGroupRef.current) {
      layerGroupRef.current = new L.FeatureGroup();
      map.addLayer(layerGroupRef.current);
    }
    const group = layerGroupRef.current;
    group.clearLayers();

    if (candidates.length === 0) return;

    candidates.forEach((cand, idx) => {
      const coords = cand.geoJson.geometry.coordinates[0];
      const latlngs: L.LatLngTuple[] = coords.map((c) => [c[1], c[0]] as L.LatLngTuple);

      const poly = L.polygon(latlngs, {
        color: "#38bdf8", // Sky blue for candidate suggestions
        weight: 2.5,
        opacity: 0.9,
        dashArray: "6 6",
        fillColor: "#0284c7",
        fillOpacity: 0.22,
      });

      const label = cand.name || `Field #${idx + 1}`;
      poly.bindTooltip(
        `<div>
          <strong style="color: #38bdf8;">${label}</strong><br/>
          <span>${cand.areaHa} ha</span> • <em>${I18N[lang].clickToSelect}</em>
        </div>`,
        { sticky: true, className: "agri-plot-candidate-tooltip" }
      );

      poly.on("mouseover", () => {
        poly.setStyle({
          color: "#4ade80",
          weight: 4,
          dashArray: "",
          fillColor: "#22c55e",
          fillOpacity: 0.45,
        });
      });

      poly.on("mouseout", () => {
        poly.setStyle({
          color: "#38bdf8",
          weight: 2.5,
          dashArray: "6 6",
          fillColor: "#0284c7",
          fillOpacity: 0.22,
        });
      });

      poly.on("click", (e) => {
        L.DomEvent.stopPropagation(e);
        onSelect(cand);
      });

      group.addLayer(poly);
    });

    return () => {
      group.clearLayers();
    };
  }, [map, candidates, onSelect, lang]);

  return null;
}

export default function MapDrawer({
  center,
  onDrawCreated,
  initialGeoJson,
  lang = "en",
}: MapDrawerProps) {
  const [mapReady, setMapReady] = useState(false);
  const [mode, setMode] = useState<"idle" | "drawing" | "editing" | "wand">("idle");
  const [hasPolygon, setHasPolygon] = useState(!!initialGeoJson);
  const [scanning, setScanning] = useState(false);
  const [detectingWand, setDetectingWand] = useState(false);
  const [candidates, setCandidates] = useState<DetectedPlot[]>([]);
  const [notification, setNotification] = useState<string | null>(null);
  const mapRef = useRef<L.Map | null>(null);

  const t = I18N[lang];

  useEffect(() => {
    setMapReady(true);
  }, []);

  const handleCreatedWrapper = useCallback(
    (geoJson: any, area: number, layer: L.Layer | null) => {
      setHasPolygon((prev) => {
        const next = !!geoJson;
        return prev !== next ? next : prev;
      });
      onDrawCreated(geoJson, area);
    },
    [onDrawCreated]
  );

  const handleAutoScan = async () => {
    if (!mapRef.current) return;
    setScanning(true);
    setCandidates([]);
    setNotification(t.scanningGuide);

    try {
      const plots = await scanViewportPlots(mapRef.current);
      setCandidates(plots);

      if (plots.length > 0) {
        setNotification(t.candidatesGuide(plots.length));
      } else {
        setNotification(t.wandFail);
        setTimeout(() => setNotification(null), 6000);
      }
    } catch (err) {
      console.error("Auto scan failed:", err);
      setNotification(t.wandFail);
      setTimeout(() => setNotification(null), 6000);
    } finally {
      setScanning(false);
    }
  };

  const handleSelectCandidate = (plot: DetectedPlot) => {
    if (!mapRef.current) return;
    (mapRef.current as any).setPolygonGeoJson(plot.geoJson);
    setCandidates([]);
    setNotification(t.wandSuccess(plot.areaHa));
    setTimeout(() => setNotification(null), 4000);
  };

  const handleWandDetected = (plot: DetectedPlot) => {
    setMode("idle");
    setNotification(t.wandSuccess(plot.areaHa));
    setTimeout(() => setNotification(null), 4000);
  };

  if (!mapReady) {
    return (
      <div
        style={{
          height: "100%",
          width: "100%",
          background: "linear-gradient(135deg, #0c1224, #131b36)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#64748b",
        }}
      >
        {t.loadingMap}
      </div>
    );
  }

  const cursorStyle =
    mode === "drawing"
      ? "crosshair"
      : mode === "wand"
      ? "cell"
      : "grab";

  return (
    <div style={{ height: "100%", width: "100%", position: "relative" }}>
      <MapContainer
        center={center}
        zoom={16}
        style={{ height: "100%", width: "100%", cursor: cursorStyle }}
        scrollWheelZoom={true}
        zoomControl={false}
        ref={mapRef}
      >
        <ChangeView center={center} />

        <TileLayer
          attribution="Tiles &copy; Esri"
          url="/api/map/tiles/esri/{z}/{y}/{x}"
        />

        <TileLayer
          attribution="Labels &copy; Esri"
          url="/api/map/tiles/esri-labels/{z}/{y}/{x}"
          opacity={0.7}
        />

        <AdvancedDrawControl
          onCreated={handleCreatedWrapper}
          onModeChange={setMode}
          initialGeoJson={initialGeoJson}
          lang={lang}
        />

        <MagicWandHandler
          active={mode === "wand"}
          onDetectStart={() => setDetectingWand(true)}
          onDetectEnd={() => setDetectingWand(false)}
          onDetected={handleWandDetected}
          onError={(msg) => {
            setNotification(msg);
            setTimeout(() => setNotification(null), 6000);
          }}
          lang={lang}
        />

        <CandidatesLayer
          candidates={candidates}
          onSelect={handleSelectCandidate}
          lang={lang}
        />
      </MapContainer>

      {/* ─── Top Floating Guidance Banner ─────────────────────────────── */}
      <div
        style={{
          position: "absolute",
          top: "16px",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 1000,
          pointerEvents: "none",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "8px",
          maxWidth: "90%",
          transition: "all 0.3s ease",
        }}
      >
        {/* Active Notification Badge */}
        {notification && (
          <div
            style={{
              background: "rgba(15, 23, 42, 0.92)",
              backdropFilter: "blur(14px)",
              padding: "8px 18px",
              borderRadius: "20px",
              border: "1px solid rgba(56, 189, 248, 0.4)",
              color: "#38bdf8",
              fontSize: "0.85rem",
              fontWeight: 600,
              boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
              animation: "fadeIn 0.2s ease-out",
            }}
          >
            {notification}
          </div>
        )}

        {/* Dynamic Mode Instructions */}
        {!notification && (
          <>
            {mode === "idle" && !hasPolygon && candidates.length === 0 && (
              <div
                style={{
                  background: "rgba(15, 23, 42, 0.88)",
                  backdropFilter: "blur(12px)",
                  padding: "8px 18px",
                  borderRadius: "20px",
                  border: "1px solid rgba(59, 130, 246, 0.3)",
                  color: "#93c5fd",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
                }}
              >
                {t.startDrawGuide}
              </div>
            )}

            {mode === "wand" && (
              <div
                style={{
                  background: "linear-gradient(135deg, #7c3aed, #6366f1)",
                  padding: "8px 18px",
                  borderRadius: "20px",
                  border: "1px solid rgba(167, 139, 250, 0.5)",
                  color: "#fff",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  boxShadow: "0 8px 32px rgba(124, 58, 237, 0.4)",
                  animation: detectingWand ? "pulse 1.2s infinite" : "none",
                }}
              >
                {detectingWand ? t.wandDetecting : t.wandGuide}
              </div>
            )}

            {mode === "drawing" && (
              <div
                style={{
                  background: "rgba(22, 163, 74, 0.9)",
                  backdropFilter: "blur(12px)",
                  padding: "8px 18px",
                  borderRadius: "20px",
                  border: "1px solid rgba(34, 197, 94, 0.5)",
                  color: "#fff",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  boxShadow: "0 8px 32px rgba(34, 197, 94, 0.3)",
                }}
              >
                {t.drawingGuide}
              </div>
            )}

            {mode === "editing" && (
              <div
                style={{
                  background: "rgba(234, 179, 8, 0.92)",
                  backdropFilter: "blur(12px)",
                  padding: "8px 18px",
                  borderRadius: "20px",
                  border: "1px solid rgba(250, 204, 21, 0.5)",
                  color: "#000",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  boxShadow: "0 8px 32px rgba(234, 179, 8, 0.3)",
                }}
              >
                {t.editingGuide}
              </div>
            )}
          </>
        )}
      </div>

      {/* ─── Bottom Floating Action Bar ─────────────────────────────── */}
      <div
        style={{
          position: "absolute",
          bottom: "20px",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 1000,
          display: "flex",
          alignItems: "center",
          gap: "10px",
          background: "rgba(15, 23, 42, 0.9)",
          backdropFilter: "blur(16px)",
          padding: "8px 12px",
          borderRadius: "16px",
          border: "1px solid rgba(71, 85, 105, 0.3)",
          boxShadow: "0 14px 44px rgba(0,0,0,0.6)",
          maxWidth: "95%",
          overflowX: "auto",
        }}
      >
        {/* Mode: IDLE or WAND */}
        {(mode === "idle" || mode === "wand") && (
          <>
            {/* 1. Magic Wand Auto-Detect Tool */}
            <button
              type="button"
              onClick={() => {
                if (mode === "wand") {
                  setMode("idle");
                } else {
                  setMode("wand");
                }
              }}
              style={{
                background:
                  mode === "wand"
                    ? "linear-gradient(135deg, #8b5cf6, #7c3aed)"
                    : "rgba(124, 58, 237, 0.18)",
                color: mode === "wand" ? "#fff" : "#c4b5fd",
                border:
                  mode === "wand"
                    ? "1px solid #a78bfa"
                    : "1px solid rgba(139, 92, 246, 0.35)",
                padding: "8px 16px",
                borderRadius: "10px",
                fontWeight: 600,
                fontSize: "0.85rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                transition: "all 0.2s ease",
                boxShadow:
                  mode === "wand"
                    ? "0 4px 16px rgba(124, 58, 237, 0.4)"
                    : "none",
              }}
            >
              <span>🪄</span>
              <span>{t.magicWandBtn}</span>
            </button>

            {/* 2. Auto-Detect / Scan Viewport Tool */}
            <button
              type="button"
              onClick={handleAutoScan}
              disabled={scanning}
              style={{
                background: scanning
                  ? "rgba(14, 165, 233, 0.3)"
                  : "rgba(14, 165, 233, 0.18)",
                color: "#7dd3fc",
                border: "1px solid rgba(56, 189, 248, 0.35)",
                padding: "8px 16px",
                borderRadius: "10px",
                fontWeight: 600,
                fontSize: "0.85rem",
                cursor: scanning ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                transition: "all 0.2s ease",
              }}
            >
              <span style={{ animation: scanning ? "spin 1s linear infinite" : "none" }}>
                {scanning ? "🔄" : "⚡"}
              </span>
              <span>{scanning ? t.wandDetecting : t.autoScanBtn}</span>
            </button>

            {/* Clear suggestions if any exist */}
            {candidates.length > 0 && (
              <button
                type="button"
                onClick={() => setCandidates([])}
                style={{
                  background: "rgba(51, 65, 85, 0.4)",
                  color: "#94a3b8",
                  border: "1px solid rgba(71, 85, 105, 0.3)",
                  padding: "8px 12px",
                  borderRadius: "10px",
                  fontSize: "0.8rem",
                  cursor: "pointer",
                }}
              >
                ✕ {t.clearCandidatesBtn}
              </button>
            )}

            <div
              style={{
                width: "1px",
                height: "24px",
                background: "rgba(71, 85, 105, 0.3)",
                margin: "0 2px",
              }}
            />

            {/* 3. Manual Draw Tool */}
            <button
              type="button"
              onClick={() => (mapRef.current as any)?.startDrawing()}
              style={{
                background: "linear-gradient(135deg, #22c55e, #16a34a)",
                color: "#fff",
                border: "none",
                padding: "8px 18px",
                borderRadius: "10px",
                fontWeight: 600,
                fontSize: "0.85rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                boxShadow: "0 4px 12px rgba(34, 197, 94, 0.3)",
                transition: "all 0.2s ease",
              }}
              onMouseOver={(e) => (e.currentTarget.style.filter = "brightness(1.1)")}
              onMouseOut={(e) => (e.currentTarget.style.filter = "brightness(1)")}
            >
              <span>✏️</span>
              <span>{hasPolygon ? t.redrawBtn : t.drawBtn}</span>
            </button>

            {/* Editing & Deletion options when a polygon exists */}
            {hasPolygon && (
              <>
                <button
                  type="button"
                  onClick={() => (mapRef.current as any)?.startEditing()}
                  style={{
                    background: "rgba(51, 65, 85, 0.5)",
                    color: "#e2e8f0",
                    border: "1px solid rgba(71, 85, 105, 0.4)",
                    padding: "8px 14px",
                    borderRadius: "10px",
                    fontWeight: 600,
                    fontSize: "0.85rem",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                  onMouseOver={(e) =>
                    (e.currentTarget.style.background = "rgba(71, 85, 105, 0.7)")
                  }
                  onMouseOut={(e) =>
                    (e.currentTarget.style.background = "rgba(51, 65, 85, 0.5)")
                  }
                >
                  <span>✂️</span>
                  <span>{t.editBtn}</span>
                </button>

                <button
                  type="button"
                  onClick={() => (mapRef.current as any)?.clearAll()}
                  style={{
                    background: "rgba(239, 68, 68, 0.15)",
                    color: "#f87171",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                    padding: "8px 14px",
                    borderRadius: "10px",
                    fontWeight: 600,
                    fontSize: "0.85rem",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                  onMouseOver={(e) =>
                    (e.currentTarget.style.background = "rgba(239, 68, 68, 0.25)")
                  }
                  onMouseOut={(e) =>
                    (e.currentTarget.style.background = "rgba(239, 68, 68, 0.15)")
                  }
                >
                  <span>🗑️</span>
                  <span>{t.deleteBtn}</span>
                </button>
              </>
            )}
          </>
        )}

        {/* Mode: EDITING */}
        {mode === "editing" && (
          <button
            type="button"
            onClick={() => (mapRef.current as any)?.saveEditing()}
            style={{
              background: "linear-gradient(135deg, #eab308, #ca8a04)",
              color: "#fff",
              border: "none",
              padding: "10px 24px",
              borderRadius: "10px",
              fontWeight: 600,
              fontSize: "0.9rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              boxShadow: "0 4px 12px rgba(234, 179, 8, 0.3)",
            }}
          >
            <span>💾</span>
            <span>{t.saveEditBtn}</span>
          </button>
        )}

        {/* Mode: DRAWING */}
        {mode === "drawing" && (
          <button
            type="button"
            onClick={() => (mapRef.current as any)?.clearAll()}
            style={{
              background: "rgba(51, 65, 85, 0.5)",
              color: "#e2e8f0",
              border: "1px solid rgba(71, 85, 105, 0.4)",
              padding: "10px 24px",
              borderRadius: "10px",
              fontWeight: 600,
              fontSize: "0.9rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <span>✖️</span>
            <span>{t.cancelDrawBtn}</span>
          </button>
        )}
      </div>

      {/* Global & Leaflet Tooltip Styles */}
      <style>{`
        .leaflet-draw-toolbar { display: none !important; }
        .leaflet-editing-icon {
          width: 14px !important;
          height: 14px !important;
          border-radius: 50% !important;
          background: #fff !important;
          border: 3px solid #22c55e !important;
          margin-left: -7px !important;
          margin-top: -7px !important;
          box-shadow: 0 2px 6px rgba(0,0,0,0.4) !important;
        }
        .agri-plot-candidate-tooltip {
          background: rgba(15, 23, 42, 0.95) !important;
          border: 1px solid #38bdf8 !important;
          color: #f8fafc !important;
          border-radius: 8px !important;
          padding: 6px 10px !important;
          font-size: 0.8rem !important;
          box-shadow: 0 4px 16px rgba(0,0,0,0.5) !important;
        }
        .agri-plot-candidate-tooltip:before {
          border-top-color: #38bdf8 !important;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes wandMarkerPulse {
          0% { stroke-width: 3; stroke-opacity: 1; fill-opacity: 0.8; }
          50% { stroke-width: 8; stroke-opacity: 0.4; fill-opacity: 0.3; }
          100% { stroke-width: 3; stroke-opacity: 1; fill-opacity: 0.8; }
        }
        .pulsing-wand-marker {
          animation: wandMarkerPulse 1.2s infinite ease-in-out;
        }
      `}</style>
    </div>
  );
}
