import * as turf from "@turf/turf";

/**
 * Geographic dimensions of the submitted geometry only.
 * Never a measurement attestation, verified survey or scientific raster metric.
 */
export function summarizeWorkspaceGeometry(geometry) {
 if(!geometry || typeof geometry!=="object")return null;
 try{
  if(geometry.type==="Point")return {kind:"Point",vertexCount:1,areaM2:null,perimeterM:null,lengthM:null};
  if(geometry.type==="LineString"){
    const vertexCount=geometry.coordinates?.length||0;
    if(vertexCount<2)return null;
    const lengthM=turf.length(turf.lineString(geometry.coordinates),{units:"kilometers"})*1000;
    return Number.isFinite(lengthM)?{kind:"LineString",vertexCount,areaM2:null,perimeterM:null,lengthM}:null;
  }
  if(geometry.type!=="Polygon"&&geometry.type!=="MultiPolygon")return null;
  const polygons=geometry.type==="Polygon"?[geometry.coordinates]:geometry.coordinates;
  const feature=geometry.type==="Polygon"?turf.polygon(geometry.coordinates):turf.multiPolygon(geometry.coordinates);
  const areaM2=turf.area(feature);
  const rings=polygons.flat();
  let perimeterM=0,vertexCount=0;
  for(const ring of rings){
    if(!Array.isArray(ring)||ring.length<4)return null;
    perimeterM+=turf.length(turf.lineString(ring),{units:"kilometers"})*1000;
    vertexCount+=ring.length-1;
  }
  if(!Number.isFinite(areaM2)||!Number.isFinite(perimeterM))return null;
  return {kind:geometry.type,vertexCount,areaM2,perimeterM,lengthM:null};
 }catch{return null}
}
