import { PathLayer, GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import type {WorkspaceFeatureEnvelope} from "@/lib/agribrain/workspace-feature-envelope";
import {isRenderableWorkspaceEntity} from "@/lib/agribrain/workspace-geometry.mjs";

export interface WorkspaceDraftGeometryProps {
  type: "LineString" | "Polygon";
  coordinates: [number, number][];
}

export function getWorkspaceDraftGeometryLayers(draft: WorkspaceDraftGeometryProps | null) {
  if (!draft || draft.coordinates.length === 0) return [];
  const layers = [];
  layers.push(
    new ScatterplotLayer({
      id: "workspace-draft-vertices",
      data: draft.coordinates.map((c, i) => ({ position: c, index: i })),
      pickable: false,
      getPosition: (d: any) => d.position,
      getFillColor: [250, 204, 21, 255],
      getLineColor: [0, 0, 0, 200],
      stroked: true,
      lineWidthMinPixels: 2,
      radiusMinPixels: 5,
      radiusMaxPixels: 8,
    })
  );
  if (draft.type === "LineString" && draft.coordinates.length >= 2) {
    layers.push(
      new PathLayer({
        id: "workspace-draft-path",
        data: [{ path: draft.coordinates }],
        pickable: false,
        getPath: (d: any) => d.path,
        getColor: [251, 146, 60, 255],
        widthMinPixels: 4,
      })
    );
  } else if (draft.type === "Polygon" && draft.coordinates.length >= 3) {
    const closed = [...draft.coordinates];
    if (closed[0][0] !== closed[closed.length - 1][0] || closed[0][1] !== closed[closed.length - 1][1]) {
      closed.push(closed[0]);
    }
    layers.push(
      new GeoJsonLayer({
        id: "workspace-draft-area",
        data: {
          type: "Feature",
          geometry: { type: "Polygon", coordinates: [closed] },
          properties: {},
        } as any,
        pickable: false,
        filled: true,
        stroked: true,
        getFillColor: [244, 63, 94, 60],
        getLineColor: [244, 63, 94, 255],
        lineWidthMinPixels: 2.5,
      })
    );
  }
  return layers;
}

export interface WorkspaceGeometryLayerProps {
  entities:WorkspaceFeatureEnvelope[];
  selectedEntityId?:string|null;
  onEntityClick?:(entity:WorkspaceFeatureEnvelope,info?:any)=>void;
  sceneOpacity?:Record<string,number>;
}
const family=(e:WorkspaceFeatureEnvelope)=>({
 SENSOR:"sensors",CAMERA:"cameras",DRONE_MISSION:"drones",
 FIELD_OBSERVATION:"observations",FIELD_EVENT:"observations",ZONE:"zones"
} as Record<string,string>)[e.entity_kind]||"observations";
const tint=(e:WorkspaceFeatureEnvelope,alpha:number,opacity:Record<string,number>):[number,number,number,number]=>{
 const demo=e.epistemic_class==="SIMULATED"||e.properties?.is_benchmark_fixture===true || e.spatial_support?.location_source==="USER_DECLARED";
 const rgb=demo?[234,179,8]:e.entity_kind==="CAMERA"?[168,85,247]:
   e.entity_kind==="DRONE_MISSION"?[249,115,22]:
   e.entity_kind==="ZONE"?[34,197,94]:[244,63,94];
 const factor=Math.min(1,Math.max(0,opacity[family(e)]??1));
 return [rgb[0],rgb[1],rgb[2],Math.round(alpha*factor)];
};
const chosen=(e:WorkspaceFeatureEnvelope,id:string|null|undefined)=>
 e.entity_id===id||e.envelope_id===id;

/** Geometry exists only where a typed, eligible source geometry has been supplied. */
export function getWorkspaceEntityGeometryLayers({entities,selectedEntityId,onEntityClick,sceneOpacity={}}:WorkspaceGeometryLayerProps){
 const valid=entities.filter(e=>e.geometry?.type!=="Point"&&isRenderableWorkspaceEntity(e));
 const lines=valid.filter(e=>e.geometry?.type==="LineString");
 const areas=valid.filter(e=>e.geometry?.type==="Polygon"||e.geometry?.type==="MultiPolygon");
 const layers=[];
 if(areas.length){
  const features=areas.map(e=>({
   type:"Feature" as const,
   id:e.envelope_id,
   geometry:e.geometry!,
   properties:{envelope_id:e.envelope_id},
  }));
  layers.push(new GeoJsonLayer({
   id:"workspace-entity-areas",
   data:{type:"FeatureCollection",features} as any,
   pickable:true,filled:true,stroked:true,wireframe:false,
   lineWidthUnits:"pixels",lineWidthMinPixels:1.5,
   getFillColor:(f:any):[number,number,number,number]=>{
     const e=areas.find(x=>x.envelope_id===f.properties?.envelope_id);
     return e?tint(e,chosen(e,selectedEntityId)?110:50,sceneOpacity):[0,0,0,0];
   },
   getLineColor:(f:any):[number,number,number,number]=>{
     const e=areas.find(x=>x.envelope_id===f.properties?.envelope_id);
     return !e?[0,0,0,0]:chosen(e,selectedEntityId)?[34,211,238,255]:tint(e,225,sceneOpacity);
   },
   getLineWidth:(f:any)=>{
     const e=areas.find(x=>x.envelope_id===f.properties?.envelope_id);
     return e&&chosen(e,selectedEntityId)?4:2;
   },
   onClick:info=>{
     const e=areas.find(x=>x.envelope_id===(info.object as any)?.properties?.envelope_id);
     if(e)onEntityClick?.(e,info);
   },
   updateTriggers:{getFillColor:[selectedEntityId,sceneOpacity],getLineColor:[selectedEntityId,sceneOpacity],getLineWidth:[selectedEntityId]},
  }));
 }
 if(lines.length){
  layers.push(new PathLayer<WorkspaceFeatureEnvelope>({
   id:"workspace-entity-paths",data:lines,pickable:true,
   widthUnits:"pixels",widthMinPixels:3,
   getPath:e=>(e.geometry?.type==="LineString"?e.geometry.coordinates:[]),
   getColor:(e):[number,number,number,number]=>chosen(e,selectedEntityId)?[34,211,238,255]:tint(e,255,sceneOpacity),
   getWidth:e=>chosen(e,selectedEntityId)?7:4,
   onClick:info=>{if(info.object)onEntityClick?.(info.object,info);},
   updateTriggers:{getColor:[selectedEntityId,sceneOpacity],getWidth:[selectedEntityId]},
  }));
 }
 return layers;
}
