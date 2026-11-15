import {isSupportedWorkspaceGeometry,normalizeWorkspaceGeometry} from "./workspace-geometry.mjs";

export const GEOMETRY_REGISTRATION_VERSION="2026.11-p06.5";
export const REGISTRATION_SOURCES=Object.freeze({
  DRONE_MISSION:"OWNER_PLAN",
  CAMERA:"IP_CAMERA",
  FIELD_OBSERVATION:"CROP_OBSERVATION",
});
const OBJECT_ID=/^[a-f\d]{24}$/i;
const permittedGeometry=Object.freeze({
  DRONE_MISSION:["LineString","Polygon","MultiPolygon"],
  CAMERA:["Polygon","MultiPolygon"],
  FIELD_OBSERVATION:["Polygon","MultiPolygon"],
});
export function validateGeometryRegistrationInput(raw){
 if(!raw||typeof raw!=="object"||Array.isArray(raw))return {ok:false,error:"Invalid registration body"};
 const kind=raw.entity_kind, source=REGISTRATION_SOURCES[kind];
 if(!source)return {ok:false,error:"Unsupported registration entity_kind"};
 if(raw.source_kind!==source)return {ok:false,error:"Source kind does not match entity kind"};
 if(source==="OWNER_PLAN"){
   if(raw.source_id!==undefined&&raw.source_id!==null)return {ok:false,error:"Owner plan must not claim an external source ID"};
   if(raw.new_observation!==undefined)return {ok:false,error:"Owner plan cannot attach crop observation"};
 }else if(source==="CROP_OBSERVATION"&&raw.new_observation){
   if(typeof raw.new_observation!=="object"||!raw.new_observation.title?.trim()){
     return {ok:false,error:"New crop observation requires a title"};
   }
   if(raw.source_id!==undefined&&raw.source_id!==null)return {ok:false,error:"Cannot supply both source_id and new_observation"};
 }else if(typeof raw.source_id!=="string"||!OBJECT_ID.test(raw.source_id)){
   return {ok:false,error:"Source record ID must be a Mongo ObjectId"};
 }
 let serializedGeometry;
 try{serializedGeometry=JSON.stringify(raw.geometry);}catch{return {ok:false,error:"Invalid geometry serialization"};}
 if(!serializedGeometry)return {ok:false,error:"Missing geometry"};
 if(serializedGeometry.length>131072)return {ok:false,error:"Geometry exceeds 128KiB"};
 if(!permittedGeometry[kind].includes(raw.geometry?.type)||!isSupportedWorkspaceGeometry(raw.geometry))
   return {ok:false,error:"Invalid or unsupported WGS84 geometry"};
 if(typeof raw.label!=="string"||!raw.label.trim()||raw.label.length>160)
   return {ok:false,error:"Label is required (maximum 160 characters)"};
 if(raw.notes!==undefined&&raw.notes!==null&&(typeof raw.notes!=="string"||raw.notes.length>2000))
   return {ok:false,error:"Notes exceed 2000 characters"};
 // Never accept client claims about scientific admission, executed status,
 // owner scope, source verification, publication, timestamps or hardware signatures.
 const allowed=new Set(["entity_kind","source_kind","source_id","new_observation","geometry","label","notes"]);
 for(const name of Object.keys(raw))if(!allowed.has(name))
   return {ok:false,error:`Unsupported or authority-bearing client field: ${name}`};
 return {ok:true,value:{
   entity_kind:kind,source_kind:source,source_id:source==="OWNER_PLAN"?null:(raw.source_id||null),
   new_observation:raw.new_observation?{
     title:raw.new_observation.title.trim(),
     type:raw.new_observation.type?.trim()||"pest",
     severity:raw.new_observation.severity?.trim()||"warning",
     description:raw.new_observation.description?.trim()||null,
   }:null,
   geometry:normalizeWorkspaceGeometry(raw.geometry),label:raw.label.trim(),notes:raw.notes?.trim()||null,
   epistemic_class:kind==="DRONE_MISSION"?"PLANNED":"ESTIMATED",
   location_source:"USER_DECLARED",status:"OWNER_DECLARED",
 }};
}

export function validateGeometryRevisionInput(raw,entityKind){
 if(!raw||typeof raw!=="object"||Array.isArray(raw))return {ok:false,error:"Invalid revision body"};
 if(!Number.isInteger(raw.expected_revision)||raw.expected_revision<1){
   return {ok:false,error:"expected_revision must be a positive integer"};
 }
 const allowed=new Set(["expected_revision","geometry","label","notes"]);
 for(const name of Object.keys(raw))if(!allowed.has(name))
   return {ok:false,error:`Unsupported or authority-bearing client field: ${name}`};
 let normalizedGeometry=null;
 if(raw.geometry!==undefined&&raw.geometry!==null){
   let serializedGeometry;
   try{serializedGeometry=JSON.stringify(raw.geometry);}catch{return {ok:false,error:"Invalid geometry serialization"};}
   if(serializedGeometry.length>131072)return {ok:false,error:"Geometry exceeds 128KiB"};
   if(!permittedGeometry[entityKind]?.includes(raw.geometry?.type)||!isSupportedWorkspaceGeometry(raw.geometry))
     return {ok:false,error:"Invalid or unsupported WGS84 geometry for this entity kind"};
   normalizedGeometry=normalizeWorkspaceGeometry(raw.geometry);
 }
 let label=null;
 if(raw.label!==undefined){
   if(typeof raw.label!=="string"||!raw.label.trim()||raw.label.length>160)
     return {ok:false,error:"Label must be a non-empty string up to 160 characters"};
   label=raw.label.trim();
 }
 let notes=undefined;
 if(raw.notes!==undefined){
   if(raw.notes!==null&&(typeof raw.notes!=="string"||raw.notes.length>2000))
     return {ok:false,error:"Notes exceed 2000 characters"};
   notes=raw.notes?raw.notes.trim():null;
 }
 return {ok:true,value:{
   expected_revision:raw.expected_revision,
   geometry:normalizedGeometry,
   label,
   notes,
 }};
}

export function isRegistrationRecordInScope(record,scope){
 return Boolean(record?.tenantId===scope?.tenantId && record?.farmId===scope?.farmId &&
  record?.plotId===scope?.plotId && record?.status==="OWNER_DECLARED");
}
