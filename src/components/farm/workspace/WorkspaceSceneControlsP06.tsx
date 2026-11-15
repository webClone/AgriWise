"use client";
import {useState} from "react";
import {Layers3, ListFilter, X} from "lucide-react";
import type {WorkspaceFeatureEnvelope} from "@/lib/agribrain/workspace-feature-envelope";
import type {SceneLayerEntry} from "./p06-scene-registry.mjs";
import {sceneLayerForEntityKind} from "./p06-scene-registry.mjs";

export default function WorkspaceSceneControlsP06({
 manifest, entities, zones, selectedId, onToggle, onOpacity, onAll, onSelectEntity, onSelectZone,
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
}) {
 const [open,setOpen]=useState(false);
 const [directory,setDirectory]=useState(false);
 const visibleCount=manifest.filter(layer=>layer.visible).length;
 return (
  <div className="pw-scene-controls" data-testid="p06-scene-controls">
   <div className="pw-scene-header">
    <button type="button" aria-expanded={open} aria-controls="pw-scene-layer-panel" onClick={()=>setOpen(!open)}>
     <Layers3 size={16} aria-hidden="true"/> Layers <span>{visibleCount}/{manifest.length}</span>
    </button>
    <button type="button" aria-expanded={directory} aria-controls="pw-scene-directory" onClick={()=>setDirectory(!directory)}>
     <ListFilter size={16} aria-hidden="true"/> Entities <span>{entities.length + zones.length}</span>
    </button>
   </div>
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
          <button type="button" aria-current={selectedId===zone.zone_id?"true":undefined} onClick={()=>onSelectZone(zone.zone_id)}>
           <span>Zone · {zone.label||zone.zone_id}</span><small>Scientific zone</small>
          </button>
        </li>
       ))}
       {entities.map(entity=>{
         const label=String(entity.properties?.name||entity.properties?.deviceId||entity.entity_id);
         const located=entity.display_eligibility?.eligible_for_map_pin===true && !!entity.geometry;
         const layerId=sceneLayerForEntityKind(entity.entity_kind);
         const hidden=manifest.find(l=>l.id===layerId)?.visible===false;
         const demo=entity.properties?.is_benchmark_fixture===true||entity.epistemic_class==="SIMULATED";
         return <li key={entity.envelope_id}>
          <button type="button" aria-current={selectedId===entity.entity_id||selectedId===entity.envelope_id?"true":undefined}
            onClick={()=>onSelectEntity(entity)}>
            <span>{entity.entity_kind.replaceAll("_"," ")} · {label}</span>
            <small>{demo?"DEMO · ":""}{located?hidden?"Layer hidden":"Mapped":"Location not registered (list only)"}</small>
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
