export type WorkspaceGeometry =
 | {type:"Point";coordinates:[number,number]}
 | {type:"LineString";coordinates:[number,number][]}
 | {type:"Polygon";coordinates:[number,number][][]}
 | {type:"MultiPolygon";coordinates:[number,number][][][]};
export function isSupportedWorkspaceGeometry(value:unknown):value is WorkspaceGeometry;
export function normalizeWorkspaceGeometry(value:unknown):Readonly<WorkspaceGeometry>;
export function geometryBounds(value:unknown):[number,number,number,number]|null;
export function isRenderableWorkspaceEntity(entity:unknown):boolean;
