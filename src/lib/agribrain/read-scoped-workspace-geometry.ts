import {prisma} from "@/lib/prisma";
import {projectWorkspaceGeometryRegistration} from "@/lib/agribrain/geometry-registration-projection.mjs";

/**
 * P06.04: Revalidates source ownership on EVERY read.
 * Moving or deleting a camera/scouting source invalidates its old geometry projection.
 */
export async function readScopedWorkspaceGeometry(scope:{tenantId:string;farmId:string;plotId:string}){
 const records=await prisma.workspaceGeometryRegistration.findMany({
   where:{tenantId:scope.tenantId,farmId:scope.farmId,plotId:scope.plotId,status:"OWNER_DECLARED"},
   orderBy:{createdAt:"desc"},take:200,
 });
 const validId=(value:string|null)=>typeof value==="string"&&/^[a-f\d]{24}$/i.test(value);
 const cameraIds=records.filter(r=>r.sourceKind==="IP_CAMERA"&&validId(r.sourceId)).map(r=>r.sourceId!);
 const scoutingIds=records.filter(r=>r.sourceKind==="CROP_OBSERVATION"&&validId(r.sourceId)).map(r=>r.sourceId!);
 const [cameras,scouts]=await Promise.all([
  cameraIds.length?prisma.iPCamera.findMany({where:{id:{in:cameraIds},plotId:scope.plotId},select:{id:true}}):Promise.resolve([]),
  scoutingIds.length?prisma.cropObservation.findMany({
    where:{id:{in:scoutingIds},cropCycle:{plotId:scope.plotId}},select:{id:true},
  }):Promise.resolve([]),
 ]);
 const cameraSet=new Set(cameras.map(x=>x.id)),scoutSet=new Set(scouts.map(x=>x.id));
 return records.flatMap(record=>{
  if(record.sourceKind==="IP_CAMERA" && !cameraSet.has(record.sourceId||""))return [];
  if(record.sourceKind==="CROP_OBSERVATION" && !scoutSet.has(record.sourceId||""))return [];
  const entity=projectWorkspaceGeometryRegistration(record as any,scope);
  return entity?[entity]:[];
 });
}
