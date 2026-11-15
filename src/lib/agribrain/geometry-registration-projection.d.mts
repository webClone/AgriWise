import type {WorkspaceFeatureEnvelope} from "./workspace-feature-envelope.mjs";
import type {WorkspaceGeometry} from "./workspace-geometry.mjs";
export interface PersistedGeometryRegistration{
 id:string;tenantId:string;farmId:string;plotId:string;registeredBy:string;
 registrationKey:string;entityKind:string;entityId:string;sourceKind:string;sourceId:string|null;
 geometry:WorkspaceGeometry;geometryDigest:string;name:string;notes:string|null;
 status:string;epistemicClass:string;locationSource:string;revision:number;
 createdAt:Date|string;updatedAt:Date|string;
}
export function geometryIntegrityDigest(geometry:WorkspaceGeometry):string;
export function projectWorkspaceGeometryRegistration(record:PersistedGeometryRegistration,scope:{tenantId:string;farmId:string;plotId:string}):WorkspaceFeatureEnvelope|null;
