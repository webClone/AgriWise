import {isSupportedWorkspaceGeometry,normalizeWorkspaceGeometry} from "./workspace-geometry.mjs";

export const GEOMETRY_REGISTRATION_VERSION="2026.11-p06.4";
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
 }else if(typeof raw.source_id!=="string"||!OBJECT_ID.test(raw.source_id)){
   return {ok:false,error:"Source record ID must be a Mongo ObjectId"};
 }
 if(!permittedGeometry[kind].includes(raw.geometry?.type)||!isSupportedWorkspaceGeometry(raw.geometry))
   return {ok:false,error:"Invalid or unsupported WGS84 geometry"};
 if(JSON.stringify(raw.geometry).length>131072)return {ok:false,error:"Geometry exceeds 128KiB"};
 if(typeof raw.label!=="string"||!raw.label.trim()||raw.label.length>160)
   return {ok:false,error:"Label is required (maximum 160 characters)"};
 if(raw.notes!==undefined&&raw.notes!==null&&(typeof raw.notes!=="string"||raw.notes.length>2000))
   return {ok:false,error:"Notes exceed 2000 characters"};
 // Never accept client claims about scientific admission, executed status,
 // owner scope, source verification, publication, timestamps or hardware signatures.
 const forbidden=["tenant_id","farm_id","plot_id","epistemic_class","location_source","verified_identity","is_benchmark_fixture","observed_at","published_at","first_available_at","publication_id","is_executed","attestation","source_version","revision"];
 for(const name of forbidden)if(Object.hasOwn(raw,name))return {ok:false,error:`Client authority field forbidden: ${name}`};
 return {ok:true,value:{
   entity_kind:kind,source_kind:source,source_id:source==="OWNER_PLAN"?null:raw.source_id,
   geometry:normalizeWorkspaceGeometry(raw.geometry),label:raw.label.trim(),notes:raw.notes?.trim()||null,
   epistemic_class:kind==="DRONE_MISSION"?"PLANNED":"ESTIMATED",
   location_source:"USER_DECLARED",status:"OWNER_DECLARED",
 }};
}

export function isRegistrationRecordInScope(record,scope){
 return Boolean(record?.tenantId===scope?.tenantId && record?.farmId===scope?.farmId &&
  record?.plotId===scope?.plotId && record?.status==="OWNER_DECLARED");
}
