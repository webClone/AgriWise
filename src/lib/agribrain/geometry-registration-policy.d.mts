import type {WorkspaceGeometry} from "./workspace-geometry.mjs";
export const GEOMETRY_REGISTRATION_VERSION:string;
export const REGISTRATION_SOURCES:Readonly<Record<string,string>>;
export type GeometryRegistrationInput={
 entity_kind:"DRONE_MISSION"|"CAMERA"|"FIELD_OBSERVATION";
 source_kind:"OWNER_PLAN"|"IP_CAMERA"|"CROP_OBSERVATION";
 source_id?:string|null;
 new_observation?:{
  title:string;
  type?:string;
  severity?:string;
  description?:string|null;
 }|null;
 geometry:WorkspaceGeometry;
 label:string;
 notes?:string|null;
};
export type SafeGeometryRegistration=GeometryRegistrationInput&{
 source_id:string|null;epistemic_class:"PLANNED"|"ESTIMATED";
 location_source:"USER_DECLARED";status:"OWNER_DECLARED";
};
export type GeometryRevisionInput={
 expected_revision:number;
 geometry?:WorkspaceGeometry|null;
 label?:string|null;
 notes?:string|null;
};
export function validateGeometryRegistrationInput(input:unknown):
 {ok:true;value:SafeGeometryRegistration}|{ok:false;error:string};
export function validateGeometryRevisionInput(input:unknown,entityKind?:string):
 {ok:true;value:GeometryRevisionInput}|{ok:false;error:string};
export function isRegistrationRecordInScope(record:unknown,scope:{tenantId:string;farmId:string;plotId:string}):boolean;
export const VALID_OBSERVATION_TYPES:Readonly<Set<string>>;
export function validateParcelContainment(
  geometry:unknown,
  plotGeoJson:unknown,
  options?:{entityKind?:string;tolerance?:number;buffer?:number}
):{ok:true}|{ok:false;error:string};
