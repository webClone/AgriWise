import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";
export type SceneLayerId="raster"|"zones"|"sensors"|"cameras"|"drones"|"observations";
export interface SceneLayerEntry {id:SceneLayerId;category:string;label:string;epistemicClass:string;count:number;visible:boolean;opacity:number;zIndex:number}
export const SCENE_LAYER_DEFS:readonly Omit<SceneLayerEntry,"count"|"visible"|"opacity">[];
export const SCENE_LAYER_IDS:readonly SceneLayerId[];
export function isSceneLayerId(id:unknown):id is SceneLayerId;
export function sceneLayerForEntityKind(kind:string):SceneLayerId|null;
export function filterCurrentSceneEntities(entities:WorkspaceFeatureEnvelope[],scope:{tenantId:string;farmId:string;plotId:string}):WorkspaceFeatureEnvelope[];
export function buildSceneManifest(args:{scope:{tenantId:string;farmId:string;plotId:string};entities:WorkspaceFeatureEnvelope[];zones:{zone_id:string}[]|null|undefined;rasterAvailable:boolean;visibleVectors?:Record<string,boolean>;sceneOpacity?:Record<string,number>}):SceneLayerEntry[];
export function visibleSceneEntities(entities:WorkspaceFeatureEnvelope[],scope:{tenantId:string;farmId:string;plotId:string},visibleVectors:Record<string,boolean>):WorkspaceFeatureEnvelope[];
export function coincidentSceneEntities(entities:WorkspaceFeatureEnvelope[],selected:WorkspaceFeatureEnvelope,project?:((point:[number,number])=>[number,number])|null,radiusPx?:number):WorkspaceFeatureEnvelope[];
