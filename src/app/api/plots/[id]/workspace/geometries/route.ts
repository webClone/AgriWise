import {NextRequest,NextResponse} from "next/server";
import {randomUUID} from "node:crypto";
import {prisma} from "@/lib/prisma";
import {authenticatedUserId} from "@/lib/tenant-authorization";
import {validateGeometryRegistrationInput} from "@/lib/agribrain/geometry-registration-policy.mjs";
import {geometryIntegrityDigest,projectWorkspaceGeometryRegistration} from "@/lib/agribrain/geometry-registration-projection.mjs";
import {readScopedWorkspaceGeometry} from "@/lib/agribrain/read-scoped-workspace-geometry";

/**
 * P06.04 — strictly owner-scoped geometry registration.
 * These records are USER_DECLARED and must not be mistaken for scientific admission,
 * signed field measurements, executed missions or hardware calibration.
 */
async function authorizedScope(rawId:string,userId:string){
 const plot=await prisma.plot.findFirst({
   where:{id:rawId,farm:{userId}},
   select:{id:true,farm:{select:{id:true,userId:true}}},
 });
 return plot?{tenantId:plot.farm.userId,farmId:plot.farm.id,plotId:plot.id}:null;
}
const objectId=/^[a-f\d]{24}$/i;
const paramsId=async(params:Promise<{id:string}>)=>(await params).id;

export async function GET(
 _request:NextRequest,{params}:{params:Promise<{id:string}>}
){
 try{
  const userId=await authenticatedUserId();
  if(!userId)return NextResponse.json({error:"Authentication required"},{status:401});
  const plotId=await paramsId(params);
  if(!objectId.test(plotId))return NextResponse.json({error:"Plot not found"},{status:404});
  const scope=await authorizedScope(plotId,userId);
  if(!scope)return NextResponse.json({error:"Plot not found"},{status:404});
  const entities=await readScopedWorkspaceGeometry(scope);
  return NextResponse.json({success:true,plot_id:scope.plotId,entities,total:entities.length,
    authority:"OWNER_DECLARED_NOT_SCIENTIFICALLY_ADMITTED"},{headers:{"Cache-Control":"private, no-store"}});
 }catch(error){console.error("[workspace/geometries:GET]",error);
  return NextResponse.json({error:"Unable to fetch geometry registrations"},{status:500});
 }
}
export async function POST(
 request:NextRequest,{params}:{params:Promise<{id:string}>}
){
 try{
  const userId=await authenticatedUserId();
  if(!userId)return NextResponse.json({error:"Authentication required"},{status:401});
  const plotId=await paramsId(params);
  if(!objectId.test(plotId))return NextResponse.json({error:"Plot not found"},{status:404});
  const scope=await authorizedScope(plotId,userId);
  if(!scope)return NextResponse.json({error:"Plot not found"},{status:404});
  if(request.headers.get("content-type")?.split(";")[0].toLowerCase()!=="application/json")
   return NextResponse.json({error:"Expected application/json"},{status:415});
  if(Number(request.headers.get("content-length")||0)>160000)
   return NextResponse.json({error:"Registration too large"},{status:413});
  const rawBody=await request.text();
  if(rawBody.length>160000)return NextResponse.json({error:"Registration too large"},{status:413});
  let raw:unknown;
  try{raw=JSON.parse(rawBody);}catch{return NextResponse.json({error:"Invalid JSON"},{status:400});}
  const validation=validateGeometryRegistrationInput(raw);
  if(!validation.ok)return NextResponse.json({error:validation.error},{status:400});
  const input=validation.value;
  // Source identity is validated independently of the untrusted geometry body.
  if(input.source_kind==="IP_CAMERA"){
    const camera=await prisma.iPCamera.findFirst({
      where:{id:input.source_id!,plotId:scope.plotId},select:{id:true},
    });
    if(!camera)return NextResponse.json({error:"Source record not found"},{status:404});
  }else if(input.source_kind==="CROP_OBSERVATION"){
    if(input.new_observation){
      let cycle=await prisma.cropCycle.findFirst({
        where:{plotId:scope.plotId},orderBy:{createdAt:"desc"},select:{id:true}
      });
      if(!cycle){
        cycle=await prisma.cropCycle.create({
          data:{cropCode:"unspecified_plot_crop",status:"PLANNED",plotId:scope.plotId},
          select:{id:true}
        });
      }
      const obs=await prisma.cropObservation.create({
        data:{
          cropCycleId:cycle.id,
          title:input.new_observation.title,
          type:input.new_observation.type||"pest",
          severity:input.new_observation.severity||"warning",
          description:input.new_observation.description||null,
          photos:[],
        },
        select:{id:true}
      });
      input.source_id=obs.id;
    }else{
      const observation=await prisma.cropObservation.findFirst({
        where:{id:input.source_id!,cropCycle:{plotId:scope.plotId}},select:{id:true},
      });
      if(!observation)return NextResponse.json({error:"Source record not found"},{status:404});
    }
  }
  const isPlan=input.source_kind==="OWNER_PLAN";
  const key=isPlan?`OWNER_PLAN:${randomUUID()}`:`${input.source_kind}:${input.source_id}`;
  if(!isPlan){
    const prior=await prisma.workspaceGeometryRegistration.findFirst({
      where:{plotId:scope.plotId,registrationKey:key},select:{id:true},
    });
    if(prior)return NextResponse.json({error:"Geometry for source already registered; revision API required"},{status:409});
  }
  const record=await prisma.workspaceGeometryRegistration.create({
    data:{
      registrationKey:key,tenantId:scope.tenantId,farmId:scope.farmId,plotId:scope.plotId,
      registeredBy:userId,entityKind:input.entity_kind,
      entityId:isPlan?key:input.source_id!,
      sourceKind:input.source_kind,sourceId:input.source_id,
      geometry:input.geometry as any,geometryDigest:geometryIntegrityDigest(input.geometry),
      name:input.label,notes:input.notes,status:"OWNER_DECLARED",
      epistemicClass:input.epistemic_class,locationSource:"USER_DECLARED",revision:1,
    },
  });
  await prisma.workspaceGeometryRevision.create({
    data:{
      registrationId:record.id,
      plotId:scope.plotId,
      revision:1,
      operation:"CREATE",
      geometry:record.geometry as any,
      geometryDigest:record.geometryDigest,
      name:record.name,
      notes:record.notes,
      editorId:userId,
    }
  });
  const entity=projectWorkspaceGeometryRegistration(record as any,scope);
  if(!entity)throw new Error("Stored registration failed canonical projection");
  return NextResponse.json({success:true,entity,authority:"OWNER_DECLARED_NOT_SCIENTIFICALLY_ADMITTED"},
    {status:201,headers:{"Cache-Control":"private, no-store"}});
 }catch(error){
  if(typeof error==="object" && error!==null && "code" in error && error.code==="P2002")
    return NextResponse.json({error:"Registration already exists"},{status:409});
  console.error("[workspace/geometries:POST]",error);
  return NextResponse.json({error:"Unable to register geometry"},{status:500});
 }
}
