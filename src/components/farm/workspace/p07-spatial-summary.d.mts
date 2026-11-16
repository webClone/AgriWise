import type {WorkspaceGeometry} from "../../../lib/agribrain/workspace-geometry.mjs";
export interface WorkspaceGeometrySummary{
 kind:"Point"|"LineString"|"Polygon"|"MultiPolygon";
 vertexCount:number;
 areaM2:number|null;
 perimeterM:number|null;
 lengthM:number|null;
}
export function summarizeWorkspaceGeometry(geometry:WorkspaceGeometry|null|undefined):WorkspaceGeometrySummary|null;
