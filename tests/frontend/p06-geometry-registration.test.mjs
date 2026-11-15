import test from "node:test";
import assert from "node:assert/strict";
import {validateGeometryRegistrationInput,isRegistrationRecordInScope} from "../../src/lib/agribrain/geometry-registration-policy.mjs";
import {geometryIntegrityDigest,projectWorkspaceGeometryRegistration} from "../../src/lib/agribrain/geometry-registration-projection.mjs";
import {validateWorkspaceFeatureEnvelope} from "../../src/lib/agribrain/workspace-feature-envelope.mjs";
import {isRenderableWorkspaceEntity} from "../../src/lib/agribrain/workspace-geometry.mjs";

const plot={tenantId:"tenant-1",farmId:"farm-1",plotId:"plot-1"};
const cameraSource="507f1f77bcf86cd799439011";
const line={type:"LineString",coordinates:[[2.659,36.508],[2.66,36.509]]};
const polygon={type:"Polygon",coordinates:[[[2.65,36.50],[2.66,36.50],[2.66,36.51],[2.65,36.51],[2.65,36.50]]]};
const raw=(kind,geometry,source_kind,source_id)=>({entity_kind:kind,geometry,source_kind,source_id,label:"Registered test"});
const record=(kind="DRONE_MISSION",geo=line)=>({
 id:"507f1f77bcf86cd799439012",registrationKey:"OWNER_PLAN:test",
 tenantId:plot.tenantId,farmId:plot.farmId,plotId:plot.plotId,
 registeredBy:plot.tenantId,
 entityKind:kind,entityId:"owner-plan-001",
 sourceKind:kind==="DRONE_MISSION"?"OWNER_PLAN":"IP_CAMERA",
 sourceId:kind==="DRONE_MISSION"?null:cameraSource,
 geometry:geo,geometryDigest:geometryIntegrityDigest(geo),
 name:"Sample registered geometry",notes:null,status:"OWNER_DECLARED",
 epistemicClass:kind==="DRONE_MISSION"?"PLANNED":"ESTIMATED",
 locationSource:"USER_DECLARED",revision:1,createdAt:new Date("2026-11-15T16:00:00Z"),
});
test("P06.04: planned mission registration stays planned, not executed or observed",()=>{
 const p=validateGeometryRegistrationInput(raw("DRONE_MISSION",line,"OWNER_PLAN"));
 assert.equal(p.ok,true);
 assert.equal(p.value.epistemic_class,"PLANNED");
 assert.equal(p.value.location_source,"USER_DECLARED");
 const entity=projectWorkspaceGeometryRegistration(record(),plot);
 assert.ok(entity);
 assert.equal(entity.geometry.type,"LineString");
 assert.equal(entity.epistemic_class,"PLANNED");
 assert.equal(entity.display_eligibility.eligible_for_map_pin,false);
 assert.equal(entity.display_eligibility.eligible_for_map_geometry,true);
 assert.equal(entity.provenance.verified_identity,false);
 assert.equal(entity.provenance.source_evidence_admitted,false);
 assert.equal(entity.properties.is_executed,false);
 assert.equal(entity.temporal_extent.observed_at,null);
 assert.equal(entity.temporal_extent.published_at,null);
 assert.equal(validateWorkspaceFeatureEnvelope(entity,{tenant_id:plot.tenantId,farm_id:plot.farmId,plot_id:plot.plotId}).valid,true);
 assert.equal(isRenderableWorkspaceEntity(entity),true);
});
test("P06.04: camera FOV is an estimated owner-declared polygon and must have DB source ID",()=>{
 assert.equal(validateGeometryRegistrationInput(raw("CAMERA",polygon,"IP_CAMERA",cameraSource)).ok,true);
 const c=record("CAMERA",polygon);
 const e=projectWorkspaceGeometryRegistration(c,plot);
 assert.equal(e.epistemic_class,"ESTIMATED");
 assert.equal(e.spatial_support.location_source,"USER_DECLARED");
 assert.equal(e.display_eligibility.eligible_for_map_geometry,true);
});
test("P06.04: source kind and 24-character source identity are required",()=>{
 assert.equal(validateGeometryRegistrationInput(raw("CAMERA",polygon,"IP_CAMERA","other")).ok,false);
 assert.equal(validateGeometryRegistrationInput(raw("CAMERA",polygon,"OWNER_PLAN")).ok,false);
 assert.equal(validateGeometryRegistrationInput(raw("DRONE_MISSION",line,"OWNER_PLAN",cameraSource)).ok,false);
 assert.equal(validateGeometryRegistrationInput(raw("SENSOR",polygon,"OWNER_PLAN")).ok,false);
 assert.equal(validateGeometryRegistrationInput(raw("FIELD_OBSERVATION",polygon,"CROP_OBSERVATION",cameraSource)).ok,true);
});
test("P06.04: client cannot claim admitted science, ownership, executed mission or survey status",()=>{
 const extra={tenant_id:"other",epistemic_class:"OBSERVED_TELEMETRY",verified_identity:true,observed_at:"2026-11-15T00:00:00Z",is_executed:true,location_source:"REGISTERED_HARDWARE"};
 for(const [k,v] of Object.entries(extra)){
  assert.equal(validateGeometryRegistrationInput({...raw("DRONE_MISSION",line,"OWNER_PLAN"),[k]:v}).ok,false,k);
 }
});
test("P06.04: invalid or overlarge geometry cannot be persisted",()=>{
 const invalid={type:"Polygon",coordinates:[[[2,36],[3,36],[2,36]]]};
 assert.equal(validateGeometryRegistrationInput(raw("CAMERA",invalid,"IP_CAMERA",cameraSource)).ok,false);
 assert.equal(validateGeometryRegistrationInput(raw("DRONE_MISSION",polygon,"OWNER_PLAN")).ok,true);
 const oversized={type:"LineString",coordinates:Array.from({length:9800},(_,i)=>[2+i/100000,36+i/100000])};
 assert.equal(validateGeometryRegistrationInput(raw("DRONE_MISSION",oversized,"OWNER_PLAN")).ok,false);
});
test("P06.04: record projection is strictly tenant/farm/plot scoped",()=>{
 const r=record();
 assert.equal(isRegistrationRecordInScope(r,plot),true);
 assert.equal(projectWorkspaceGeometryRegistration(r,{...plot,tenantId:"foreign"}),null);
 assert.equal(projectWorkspaceGeometryRegistration(r,{...plot,farmId:"foreign"}),null);
 assert.equal(projectWorkspaceGeometryRegistration(r,{...plot,plotId:"foreign"}),null);
 assert.equal(projectWorkspaceGeometryRegistration({...r,status:"REVOKED"},plot),null);
});
test("P06.04: copied stored geometry with mutated coordinates is rejected by SHA-256",()=>{
 const r=record(),t=JSON.parse(JSON.stringify(r));
 t.geometry.coordinates[1][0]=2.7;
 assert.equal(projectWorkspaceGeometryRegistration(t,plot),null);
 assert.match(geometryIntegrityDigest(r.geometry),/^[0-9a-f]{64}$/);
 assert.notEqual(geometryIntegrityDigest(t.geometry),r.geometryDigest);
});
test("P06.04: a forged verified identity or observed class fails projection",()=>{
 const r=record();
 assert.equal(projectWorkspaceGeometryRegistration({...r,epistemicClass:"OBSERVED_TELEMETRY"},plot),null);
 assert.equal(projectWorkspaceGeometryRegistration({...r,locationSource:"REGISTERED_HARDWARE"},plot),null);
 const e=projectWorkspaceGeometryRegistration(r,plot);
 const tampered=JSON.parse(JSON.stringify(e));
 tampered.provenance.verified_identity=true;
 assert.equal(validateWorkspaceFeatureEnvelope(tampered,{tenant_id:plot.tenantId}).valid,false);
});
test("P06.04: registration must not overwrite or backdate verified publication metadata",()=>{
 const entity=projectWorkspaceGeometryRegistration(record(),plot);
 assert.equal(entity.temporal_extent.published_at,null);
 assert.equal(entity.temporal_extent.first_available_at,null);
 assert.equal(entity.provenance.registry_source,"prisma:workspaceGeometryRegistration");
 assert.equal(entity.provenance.source_evidence_admitted,false);
});
