/** P06 presentation-only scene model. Never authorizes scientific evidence. */
export const SCENE_LAYER_DEFS=Object.freeze([
{id:"raster",category:"raster",label:"Scientific surfaces",epistemicClass:"SOURCE_POLICY_GATED",zIndex:10},
{id:"zones",category:"zone",label:"Management zones",epistemicClass:"DERIVED",zIndex:20},
{id:"sensors",category:"sensor",label:"Sensors",epistemicClass:"MIXED",zIndex:30},
{id:"cameras",category:"camera",label:"Cameras",epistemicClass:"MIXED",zIndex:40},
{id:"drones",category:"drone",label:"Drone missions",epistemicClass:"MIXED",zIndex:50},
{id:"observations",category:"observation",label:"Field observations",epistemicClass:"MIXED",zIndex:60}
]);
export const SCENE_LAYER_IDS=Object.freeze(SCENE_LAYER_DEFS.map(d=>d.id));
export const isSceneLayerId=id=>typeof id==="string"&&SCENE_LAYER_IDS.includes(id);
export const sceneLayerForEntityKind=kind=>({SENSOR:"sensors",CAMERA:"cameras",DRONE_MISSION:"drones",FIELD_OBSERVATION:"observations",FIELD_EVENT:"observations"})[kind]??null;
export function filterCurrentSceneEntities(entities,scope){
 if(!scope?.tenantId||!scope?.farmId||!scope?.plotId||!Array.isArray(entities))return [];
 return entities.filter(e=>e&&e.owner_scope?.tenant_id===scope.tenantId&&e.owner_scope?.farm_id===scope.farmId&&e.owner_scope?.plot_id===scope.plotId&&sceneLayerForEntityKind(e.entity_kind)!==null&&e.display_eligibility?.eligible_for_catalog===true);
}
export function buildSceneManifest({scope,entities,zones,rasterAvailable,visibleVectors={},sceneOpacity={}}){
 const counts={raster:rasterAvailable?1:0,zones:Array.isArray(zones)?zones.filter(z=>!!z?.zone_id).length:0,sensors:0,cameras:0,drones:0,observations:0};
 for(const e of filterCurrentSceneEntities(entities,scope)){const k=sceneLayerForEntityKind(e.entity_kind);if(k)counts[k]++;}
 return SCENE_LAYER_DEFS.map(d=>({...d,count:counts[d.id],visible:visibleVectors[d.id]!==false,opacity:Number.isFinite(sceneOpacity[d.id])?Math.max(0,Math.min(1,sceneOpacity[d.id])):1}));
}
export function visibleSceneEntities(entities,scope,visibleVectors={}){
 return filterCurrentSceneEntities(entities,scope).filter(e=>{
  const k=sceneLayerForEntityKind(e.entity_kind);
  return !!k&&visibleVectors[k]!==false&&(e.display_eligibility?.eligible_for_map_pin===true||e.display_eligibility?.eligible_for_map_geometry===true)&&!!e.geometry;
 });
}
export function coincidentSceneEntities(entities,selected,project,radiusPx=13){
 if(selected?.geometry?.type!=="Point"||!Array.isArray(entities))return selected?[selected]:[];
 const projectFn=typeof project==="function"?project:null;
 const source=projectFn?projectFn(selected.geometry.coordinates):selected.geometry.coordinates;
 if(!Array.isArray(source)||!source.every(Number.isFinite))return [selected];
 const hits=entities.filter(e=>{
  if(e?.display_eligibility?.eligible_for_map_pin!==true||e.geometry?.type!=="Point")return false;
  const p=projectFn?projectFn(e.geometry.coordinates):e.geometry.coordinates;
  if(!Array.isArray(p)||!p.every(Number.isFinite))return false;
  return projectFn?Math.hypot(p[0]-source[0],p[1]-source[1])<=radiusPx:p[0]===source[0]&&p[1]===source[1];
 });
 if(!hits.some(e=>e.envelope_id===selected.envelope_id))hits.unshift(selected);
 return [selected,...hits.filter(e=>e.envelope_id!==selected.envelope_id).sort((a,b)=>String(a.envelope_id).localeCompare(String(b.envelope_id)))];
}
