"use client";
import {useState} from "react";
import {Layers3, ListFilter, PenTool, Plane, FileText, X, Eye, FlaskConical, PanelRightOpen, PanelRightClose} from "lucide-react";
import type {WorkspaceFeatureEnvelope} from "@/lib/agribrain/workspace-feature-envelope";
import type {SceneLayerEntry} from "./p06-scene-registry.mjs";
import {sceneLayerForEntityKind} from "./p06-scene-registry.mjs";
import {
  ASMAE_13_STATE_ORDER,
  ASMAE_13_STATE_CATALOG,
  type AsmaeStateKey,
  type AsmaeStateAvailabilityResult,
} from "@/lib/agribrain/asmae-13-states";

export default function WorkspaceSceneControlsP06({
 manifest,
 entities,
 zones,
 selectedId,
 onToggle,
 onOpacity,
 onAll,
 onSelectEntity,
 onSelectZone,
 onStartDrawing,
 mapVisualLens = "standard",
 onPaletteChange,
 canTransect = false,
 transectActive = false,
 transectPointsCount = 0,
 onToggleTransect,
 activeAsmaeKey = "vigor",
 onSelectAsmaeState,
 asmaeStatesSummary = [],
 isInspectorOpen = false,
 onToggleInspector,
}:{
 manifest:SceneLayerEntry[];
 entities:WorkspaceFeatureEnvelope[];
 zones:{zone_id:string;label?:string|null}[];
 selectedId:string|null;
 onToggle:(id:string,visible:boolean)=>void;
 onOpacity:(id:string,value:number)=>void;
 onAll:(visible:boolean)=>void;
 onSelectEntity:(item:WorkspaceFeatureEnvelope)=>void;
 onSelectZone:(id:string)=>void;
 onStartDrawing?:(kind:"DRONE_MISSION"|"FIELD_OBSERVATION")=>void;
 mapVisualLens?: "standard" | "thermal" | "chlorophyll" | "chroma";
 onPaletteChange?: (lens: "standard" | "thermal" | "chlorophyll" | "chroma") => void;
 canTransect?: boolean;
 transectActive?: boolean;
 transectPointsCount?: number;
 onToggleTransect?: () => void;
 activeAsmaeKey?: AsmaeStateKey | null;
 onSelectAsmaeState?: (key: AsmaeStateKey) => void;
 asmaeStatesSummary?: AsmaeStateAvailabilityResult[];
 isInspectorOpen?: boolean;
 onToggleInspector?: () => void;
}) {
 const [open,setOpen]=useState(false);
 const [directory,setDirectory]=useState(false);
 const [drawMenuOpen,setDrawMenuOpen]=useState(false);
 const [viewOpen,setViewOpen]=useState(false);
 const [asmaeOpen,setAsmaeOpen]=useState(false);
 const visibleCount=manifest.filter(layer=>layer.visible).length;
 return (
  <div className="pw-scene-controls" data-testid="p06-scene-controls">
   <div className="pw-scene-header">
    <button
      type="button"
      data-testid="p07-asmae-lab-toggle"
      aria-expanded={asmaeOpen}
      aria-controls="p07-asmae-lab-panel"
      onClick={()=>{
        setAsmaeOpen(!asmaeOpen);
        setViewOpen(false);
        setOpen(false);
        setDirectory(false);
        setDrawMenuOpen(false);
      }}
      title="ASMAE 13-State Scientific Laboratory"
      style={{
        background: activeAsmaeKey ? "rgba(16, 185, 129, 0.18)" : undefined,
        borderColor: activeAsmaeKey ? "rgba(16, 185, 129, 0.4)" : undefined,
      }}
    >
      <FlaskConical size={16} aria-hidden="true"/> ASMAE Lab <span>{activeAsmaeKey ? (ASMAE_13_STATE_CATALOG[activeAsmaeKey]?.shortName || "13 States") : "13 States"}</span>
    </button>
    <button
      type="button"
      data-testid="p07-map-view-toggle"
      aria-expanded={viewOpen}
      aria-controls="p07-map-view-panel"
      onClick={()=>{
        setViewOpen(!viewOpen);
        setOpen(false);
        setDirectory(false);
        setDrawMenuOpen(false);
      }}
      title="Map presentation lens and analysis"
    >
      <Eye size={16} aria-hidden="true"/> View
    </button>
    <button type="button" aria-expanded={open} aria-controls="pw-scene-layer-panel" onClick={()=>{setOpen(!open);setViewOpen(false);setDrawMenuOpen(false);}}>
     <Layers3 size={16} aria-hidden="true"/> Layers <span>{visibleCount}/{manifest.length}</span>
    </button>
    <button type="button" aria-expanded={directory} aria-controls="pw-scene-directory" onClick={()=>{setDirectory(!directory);setViewOpen(false);setDrawMenuOpen(false);}}>
     <ListFilter size={16} aria-hidden="true"/> Entities <span>{entities.length + zones.length}</span>
    </button>
    {onStartDrawing && (
      <button
        type="button"
        aria-expanded={drawMenuOpen}
        onClick={()=>{setDrawMenuOpen(!drawMenuOpen);setViewOpen(false);setOpen(false);setDirectory(false);}}
        data-testid="p06-draw-geometry-btn"
        title="Draw planned flight route or scouting boundary"
      >
        <PenTool size={16} aria-hidden="true"/> Draw
      </button>
    )}
    {onToggleInspector && (
      <button
        type="button"
        data-testid="p07-scene-inspector-toggle"
        className="pw-desktop-inspector-reopen"
        aria-expanded={isInspectorOpen}
        aria-controls="pw-context-inspector"
        onClick={onToggleInspector}
        title={isInspectorOpen ? "Collapse Context Inspector" : "Expand Context Inspector"}
        style={{
          background: isInspectorOpen ? "rgba(255, 255, 255, 0.18)" : undefined,
          borderColor: isInspectorOpen ? "rgba(255, 255, 255, 0.35)" : undefined,
        }}
      >
        {isInspectorOpen ? <PanelRightClose size={16} aria-hidden="true" /> : <PanelRightOpen size={16} aria-hidden="true" />}
        Inspector
      </button>
    )}
   </div>
   {viewOpen && (
    <section id="p07-map-view-panel" aria-label="Map presentation lens and analysis" className="pw-scene-panel" style={{ width: "230px" }}>
      <div className="pw-scene-panel-title">
        <strong>View &amp; Analysis</strong>
        <button type="button" aria-label="Close view tools" onClick={()=>setViewOpen(false)}>
          <X size={15}/>
        </button>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "10px", padding: "6px 0" }}>
        <div>
          <div style={{ fontSize: "10px", fontWeight: 700, letterSpacing: "0.08em", color: "#d0a278", textTransform: "uppercase", marginBottom: "6px" }}>
            Color Lens
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }}>
            {[
              { id: "standard", label: "Standard", color: "#10b981" },
              { id: "thermal", label: "Thermal", color: "#f97316" },
              { id: "chlorophyll", label: "Chlorophyll", color: "#ec4899" },
              { id: "chroma", label: "Chroma", color: "#6366f1" },
            ].map((pal) => (
              <button
                key={pal.id}
                type="button"
                onClick={() => onPaletteChange?.(pal.id as "standard" | "thermal" | "chlorophyll" | "chroma")}
                style={{
                  display: "flex", alignItems: "center", gap: "6px", padding: "6px 8px",
                  borderRadius: "6px", fontSize: "11px", fontWeight: 600, cursor: "pointer",
                  border: mapVisualLens === pal.id ? "1px solid rgba(255,255,255,0.4)" : "1px solid rgba(255,255,255,0.08)",
                  background: mapVisualLens === pal.id ? "rgba(255,255,255,0.18)" : "rgba(16,38,32,0.6)",
                  color: "#eef4ed",
                }}
              >
                <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: pal.color, flexShrink: 0 }} />
                {pal.label}
              </button>
            ))}
          </div>
          <div style={{ fontSize: "9px", color: "var(--pw-dim, #91aa9b)", fontStyle: "italic", marginTop: "5px", lineHeight: 1.3 }}>
            Color-only visualization; does not modify raw sensor bands.
          </div>
        </div>

        <div style={{ borderTop: "1px solid var(--pw-border, rgba(181, 204, 186, 0.2))", paddingTop: "8px" }}>
          <div style={{ fontSize: "10px", fontWeight: 700, letterSpacing: "0.08em", color: "#d0a278", textTransform: "uppercase", marginBottom: "6px" }}>
            Spatial Analysis
          </div>
          <button
            type="button"
            onClick={() => onToggleTransect?.()}
            disabled={!canTransect}
            style={{
              width: "100%", padding: "7px 10px", borderRadius: "6px", fontSize: "11px", fontWeight: 600,
              display: "flex", alignItems: "center", justifyContent: "center", gap: "6px",
              cursor: canTransect ? "pointer" : "not-allowed",
              opacity: canTransect ? 1 : 0.45,
              border: !canTransect ? "1px solid rgba(255,255,255,0.08)" : transectActive ? "1px solid #facc15" : "1px solid rgba(250,204,21,0.35)",
              background: !canTransect ? "rgba(16,38,32,0.4)" : transectActive ? "#facc15" : "rgba(250,204,21,0.12)",
              color: transectActive ? "#0f172a" : "#fef08a",
            }}
            title={!canTransect ? "Cross-section requires inspector-authorized observed raster data" : "Draw a transect line on the map"}
          >
            📏 {!canTransect ? "Cross-Section unavailable" : transectActive ? "Placing A ➔ B..." : (transectPointsCount > 0) ? "Reset Transect" : "Cross-Section"}
          </button>
        </div>
      </div>
      <p className="pw-scene-hint">Presentation lens changes visualization only, never scientific authority.</p>
    </section>
   )}
   {asmaeOpen && (
    <section
      id="p07-asmae-lab-panel"
      aria-label="ASMAE 13-State Scientific Laboratory"
      className="pw-scene-panel"
      style={{ width: "min(340px, calc(100vw - 80px))", maxHeight: "58vh" }}
    >
      <div className="pw-scene-panel-title">
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <FlaskConical size={15} style={{ color: "#34d399" }} />
          <strong>ASMAE 13-State Laboratory</strong>
        </div>
        <button type="button" aria-label="Close ASMAE lab" onClick={() => setAsmaeOpen(false)}>
          <X size={15} />
        </button>
      </div>
      <div style={{ fontSize: "10px", color: "var(--pw-dim, #91aa9b)", marginBottom: "8px", lineHeight: 1.3 }}>
        Canonical latent state biophysical inversions (V1.13). Never fabricates rasters for scalar-only states.
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {ASMAE_13_STATE_ORDER.map((stateKey, idx) => {
          const def = ASMAE_13_STATE_CATALOG[stateKey];
          const summary = asmaeStatesSummary?.find((s) => s.state.key === stateKey);
          const isSelected = activeAsmaeKey === stateKey;
          const status = summary?.status || "UNAVAILABLE";
          const statusColor =
            status === "QUALIFIED_RASTER"
              ? "#34d399"
              : status === "SCALAR_ONLY"
              ? "#facc15"
              : "#94a3b8";
          const statusLabel =
            status === "QUALIFIED_RASTER"
              ? "Raster Qualified"
              : status === "SCALAR_ONLY"
              ? "Scalar Estimate"
              : "Unavailable";

          return (
            <button
              key={stateKey}
              type="button"
              data-testid={`p07-asmae-state-${stateKey}`}
              onClick={() => {
                onSelectAsmaeState?.(stateKey);
                setAsmaeOpen(false);
              }}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "8px",
                padding: "8px 10px",
                background: isSelected ? "rgba(16, 185, 129, 0.2)" : "rgba(255, 255, 255, 0.04)",
                border: isSelected ? "1px solid #34d399" : "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: "8px",
                textAlign: "left",
                cursor: "pointer",
                color: "#e2e8f0",
              }}
            >
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: 800,
                  fontFamily: "monospace",
                  color: isSelected ? "#34d399" : "#a9c9b5",
                  marginTop: "2px",
                }}
              >
                {String(idx + 1).padStart(2, "0")}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "6px" }}>
                  <strong style={{ fontSize: "11px", color: isSelected ? "#ffffff" : "#f1f5f9" }}>
                    {def.shortName}
                  </strong>
                  <span
                    style={{
                      fontSize: "9px",
                      padding: "1px 5px",
                      borderRadius: "10px",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      background: `${statusColor}22`,
                      color: statusColor,
                      border: `1px solid ${statusColor}44`,
                    }}
                  >
                    {statusLabel}
                  </span>
                </div>
                <div style={{ fontSize: "10px", color: "#94a3b8", marginTop: "2px" }}>
                  {def.name}
                </div>
                {summary && summary.mean !== null ? (
                  <div style={{ fontSize: "10px", color: "#34d399", fontWeight: 600, marginTop: "3px" }}>
                    {summary.mean} {summary.sigma !== null ? `± ${summary.sigma}` : ""} {def.unit}
                  </div>
                ) : (
                  <div style={{ fontSize: "9px", color: "#64748b", fontStyle: "italic", marginTop: "2px" }}>
                    {def.authorityCeiling.replace(/_/g, " ")}
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </section>
   )}
   {drawMenuOpen && (
    <section aria-label="Spatial authoring tools" className="pw-scene-panel" style={{ width: "240px" }}>
      <div className="pw-scene-panel-title">
        <strong>Author Geometry</strong>
        <button type="button" aria-label="Close draw tools" onClick={()=>setDrawMenuOpen(false)}>
          <X size={15}/>
        </button>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "8px", padding: "6px 0" }}>
        <button
          type="button"
          data-testid="p06-draw-drone-btn"
          onClick={()=>{setDrawMenuOpen(false);onStartDrawing?.("DRONE_MISSION");}}
          style={{
            display: "flex", alignItems: "center", gap: "8px", padding: "8px 12px",
            background: "rgba(249, 115, 22, 0.15)", border: "1px solid rgba(249, 115, 22, 0.35)",
            color: "#fb923c", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: 600,
          }}
        >
          <Plane size={15}/> Plan Drone Route (Line)
        </button>
        <button
          type="button"
          data-testid="p06-draw-scout-btn"
          onClick={()=>{setDrawMenuOpen(false);onStartDrawing?.("FIELD_OBSERVATION");}}
          style={{
            display: "flex", alignItems: "center", gap: "8px", padding: "8px 12px",
            background: "rgba(244, 63, 94, 0.15)", border: "1px solid rgba(244, 63, 94, 0.35)",
            color: "#f43f5e", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: 600,
          }}
        >
          <FileText size={15}/> Map Scouting Area (Polygon)
        </button>
      </div>
      <p className="pw-scene-hint">Drawings are saved as owner-declared and do not infer scientific admission.</p>
    </section>
   )}
   {open && (
    <section id="pw-scene-layer-panel" aria-label="Map scene layer controls" className="pw-scene-panel">
      <div className="pw-scene-panel-title"><strong>Visible map layers</strong><button type="button" aria-label="Close layer controls" onClick={()=>setOpen(false)}><X size={15}/></button></div>
      <div className="pw-scene-all"><button type="button" onClick={()=>onAll(true)}>Show all</button><button type="button" onClick={()=>onAll(false)}>Hide all</button></div>
      {manifest.map(layer=>(
       <div className="pw-scene-layer" key={layer.id} data-layer-id={layer.id}>
        <label><input type="checkbox" checked={layer.visible} onChange={e=>onToggle(layer.id,e.target.checked)} aria-label={layer.label}/>
          <span>{layer.label}</span><small>{layer.count}</small>
        </label>
        <div className="pw-scene-opacity">
          <label htmlFor={`pw-opacity-${layer.id}`}>Opacity</label>
          <input id={`pw-opacity-${layer.id}`} type="range" min="0.2" max="1" step="0.1"
            value={Math.max(0.2,layer.opacity)} disabled={!layer.visible}
            onChange={e=>onOpacity(layer.id,Number(e.target.value))}/>
          <output>{Math.round(layer.opacity*100)}%</output>
        </div>
       </div>
      ))}
      <p className="pw-scene-hint">Layer visibility changes presentation only, never scientific publication authority.</p>
    </section>
   )}
   {directory && (
    <section id="pw-scene-directory" aria-label="Accessible plot entity directory" className="pw-scene-panel pw-scene-directory">
      <div className="pw-scene-panel-title"><strong>Entities in this plot</strong><button type="button" aria-label="Close entity directory" onClick={()=>setDirectory(false)}><X size={15}/></button></div>
      <ul>
       {zones.map(zone=>(
        <li key={`zone-${zone.zone_id}`}>
          <button type="button" aria-current={selectedId===zone.zone_id?"true":undefined} onClick={()=>{setDirectory(false);onSelectZone(zone.zone_id);}}>
           <span>Zone · {zone.label||zone.zone_id}</span><small>Scientific zone</small>
          </button>
        </li>
       ))}
       {entities.map(entity=>{
         const label=String(entity.properties?.name||entity.properties?.deviceId||entity.entity_id);
         const located=(entity.display_eligibility?.eligible_for_map_pin===true||entity.display_eligibility?.eligible_for_map_geometry===true) && !!entity.geometry;
         const layerId=sceneLayerForEntityKind(entity.entity_kind);
         const hidden=manifest.find(l=>l.id===layerId)?.visible===false;
         const demo=entity.properties?.is_benchmark_fixture===true||entity.epistemic_class==="SIMULATED";
         const provisional=entity.spatial_support?.location_source==="USER_DECLARED";
         return <li key={entity.envelope_id}>
          <button type="button" aria-current={selectedId===entity.entity_id||selectedId===entity.envelope_id?"true":undefined}
            onClick={()=>{setDirectory(false);onSelectEntity(entity);}}>
            <span>{entity.entity_kind.replaceAll("_"," ")} · {label}</span>
            <small>{provisional?"OWNER-DECLARED · ":demo?"DEMO · ":""}{located?hidden?"Layer hidden":`${entity.geometry?.type} mapped`:"Location not registered (list only)"}</small>
          </button>
         </li>;
       })}
      </ul>
      {entities.length===0&&zones.length===0&&<p>No entities are registered for this plot scope.</p>}
      <p className="pw-scene-hint">Keyboard-select any listed entity. Unlocated devices are never assigned synthetic map coordinates.</p>
    </section>
   )}
  </div>
 );
}
