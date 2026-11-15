import {createHash} from "node:crypto";
import {createWorkspaceFeatureEnvelope,validateWorkspaceFeatureEnvelope} from "./workspace-feature-envelope.mjs";
import {isSupportedWorkspaceGeometry} from "./workspace-geometry.mjs";
import {isRegistrationRecordInScope,REGISTRATION_SOURCES} from "./geometry-registration-policy.mjs";

export const geometryIntegrityDigest=geometry=>createHash("sha256").update(JSON.stringify({type:geometry.type,coordinates:geometry.coordinates})).digest("hex");

/** Projection is intentionally weaker than scientific admission.
 * A source-linked record is still owner-declared until independently qualified.
 */
export function projectWorkspaceGeometryRegistration(record,scope){
 if(!isRegistrationRecordInScope(record,scope))return null;
 if(REGISTRATION_SOURCES[record.entityKind]!==record.sourceKind ||
   (record.sourceKind==="OWNER_PLAN" ? record.sourceId!=null : !/^[a-f\\d]{24}$/i.test(record.sourceId||"")))return null;
 if(record.epistemicClass!==(record.entityKind==="DRONE_MISSION"?"PLANNED":"ESTIMATED") ||
   record.locationSource!=="USER_DECLARED" || record.revision!==1)return null;
 if(!isSupportedWorkspaceGeometry(record.geometry) ||
   geometryIntegrityDigest(record.geometry)!==record.geometryDigest)return null;
 const envelope=createWorkspaceFeatureEnvelope({
   entity_kind:record.entityKind,
   entity_id:record.entityId,
   source_version:`registered-v1:${record.id}`,
   owner_scope:{tenant_id:scope.tenantId,farm_id:scope.farmId,plot_id:scope.plotId},
   geometry:record.geometry,
   location_source:"USER_DECLARED",
   epistemic_class:record.epistemicClass,
   temporal_extent:{observed_at:null,first_available_at:null,published_at:null},
   properties:{
     name:record.name,
     notes:record.notes||null,
     geometry_source:"OWNER_DECLARED",
     registration_status:"OWNER_DECLARED",
     registered_at:record.createdAt instanceof Date?record.createdAt.toISOString():String(record.createdAt),
     source_kind:record.sourceKind,
     source_record_id:record.sourceId,
     is_benchmark_fixture:false,
     is_executed:false,
   },
   provenance:{
     registry_source:"prisma:workspaceGeometryRegistration",
     registration_id:record.id,
     geometry_digest:record.geometryDigest,
     verified_identity:false,
     source_evidence_admitted:false,
   },
 });
 const result=validateWorkspaceFeatureEnvelope(envelope,{
  tenant_id:scope.tenantId,farm_id:scope.farmId,plot_id:scope.plotId,
 });
 return result.valid?envelope:null;
}
