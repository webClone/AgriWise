import * as turf from "@turf/turf";
import {isSupportedWorkspaceGeometry,normalizeWorkspaceGeometry,geometryBounds} from "./workspace-geometry.mjs";

export const GEOMETRY_REGISTRATION_VERSION="2026.11-p06.5";
export const REGISTRATION_SOURCES=Object.freeze({
  DRONE_MISSION:"OWNER_PLAN",
  CAMERA:"IP_CAMERA",
  FIELD_OBSERVATION:"CROP_OBSERVATION",
});
export const VALID_OBSERVATION_TYPES = Object.freeze(new Set([
  "pest",
  "disease",
  "growth",
  "health",
  "weather_impact"
]));
export const VALID_SEVERITIES = Object.freeze(new Set([
  "info",
  "warning",
  "critical"
]));
const OBJECT_ID=/^[a-f\d]{24}$/i;
const permittedGeometry=Object.freeze({
  DRONE_MISSION:["LineString","Polygon","MultiPolygon"],
  CAMERA:["Polygon","MultiPolygon"],
  FIELD_OBSERVATION:["Polygon","MultiPolygon"],
});
export function validateGeometryRegistrationInput(raw){
 if(!raw||typeof raw!=="object"||Array.isArray(raw))return {ok:false,error:"Invalid registration body"};
 const kind=raw.entity_kind, source=REGISTRATION_SOURCES[kind];
 if(!source)return {ok:false,error:"Unsupported registration entity_kind"};
 if(raw.source_kind!==source)return {ok:false,error:"Source kind does not match entity kind"};
 if(source==="OWNER_PLAN"){
   if(raw.source_id!==undefined&&raw.source_id!==null)return {ok:false,error:"Owner plan must not claim an external source ID"};
   if(raw.new_observation!==undefined)return {ok:false,error:"Owner plan cannot attach crop observation"};
 }else if(source==="CROP_OBSERVATION"&&raw.new_observation!==undefined){
   if(typeof raw.new_observation!=="object"||raw.new_observation===null||Array.isArray(raw.new_observation)){
     return {ok:false,error:"New crop observation must be an object"};
   }
   if(raw.source_id!==undefined&&raw.source_id!==null)return {ok:false,error:"Cannot supply both source_id and new_observation"};
   if(typeof raw.new_observation.title!=="string"||!raw.new_observation.title.trim()){
     return {ok:false,error:"New crop observation requires a string title"};
   }
   if(raw.new_observation.title.trim().length>160){
     return {ok:false,error:"Observation title exceeds 160 characters"};
   }
   if(raw.new_observation.type!==undefined&&raw.new_observation.type!==null){
     if(typeof raw.new_observation.type!=="string"){
       return {ok:false,error:"Observation category must be a string"};
     }
   }
   const obsType = (raw.new_observation.type ? raw.new_observation.type.trim().toLowerCase() : "pest");
   if(!VALID_OBSERVATION_TYPES.has(obsType)) {
     return {ok:false,error:`Invalid observation category: ${String(raw.new_observation.type)}. Allowed: pest, disease, growth, health, weather_impact`};
   }
   if(raw.new_observation.severity!==undefined&&raw.new_observation.severity!==null){
     if(typeof raw.new_observation.severity!=="string"){
       return {ok:false,error:"Observation severity must be a string"};
     }
     const sev = raw.new_observation.severity.trim().toLowerCase();
     if(!VALID_SEVERITIES.has(sev)){
       return {ok:false,error:`Invalid observation severity: ${String(raw.new_observation.severity)}. Allowed: info, warning, critical`};
     }
   }
   if(raw.new_observation.description!==undefined&&raw.new_observation.description!==null){
     if(typeof raw.new_observation.description!=="string"){
       return {ok:false,error:"Observation description must be a string"};
     }
     if(raw.new_observation.description.trim().length>2000){
       return {ok:false,error:"Observation description exceeds 2000 characters"};
     }
   }
 }else if(typeof raw.source_id!=="string"||!OBJECT_ID.test(raw.source_id)){
   return {ok:false,error:"Source record ID must be a Mongo ObjectId"};
 }
 let serializedGeometry;
 try{serializedGeometry=JSON.stringify(raw.geometry);}catch{return {ok:false,error:"Invalid geometry serialization"};}
 if(!serializedGeometry)return {ok:false,error:"Missing geometry"};
 if(serializedGeometry.length>131072)return {ok:false,error:"Geometry exceeds 128KiB"};
 if(!permittedGeometry[kind].includes(raw.geometry?.type)||!isSupportedWorkspaceGeometry(raw.geometry))
   return {ok:false,error:"Invalid or unsupported WGS84 geometry"};
 if(typeof raw.label!=="string"||!raw.label.trim()||raw.label.length>160)
   return {ok:false,error:"Label is required (maximum 160 characters)"};
 if(raw.notes!==undefined&&raw.notes!==null&&(typeof raw.notes!=="string"||raw.notes.length>2000))
   return {ok:false,error:"Notes exceed 2000 characters"};
 // Never accept client claims about scientific admission, executed status,
 // owner scope, source verification, publication, timestamps or hardware signatures.
 const allowed=new Set(["entity_kind","source_kind","source_id","new_observation","geometry","label","notes"]);
 for(const name of Object.keys(raw))if(!allowed.has(name))
   return {ok:false,error:`Unsupported or authority-bearing client field: ${name}`};
 return {ok:true,value:{
   entity_kind:kind,source_kind:source,source_id:source==="OWNER_PLAN"?null:(raw.source_id||null),
   new_observation:raw.new_observation?{
     title:raw.new_observation.title.trim(),
     type:(raw.new_observation.type?raw.new_observation.type.trim().toLowerCase():"pest"),
     severity:(raw.new_observation.severity?raw.new_observation.severity.trim().toLowerCase():"warning"),
     description:raw.new_observation.description?raw.new_observation.description.trim():null,
   }:null,
   geometry:normalizeWorkspaceGeometry(raw.geometry),label:raw.label.trim(),notes:raw.notes?.trim()||null,
   epistemic_class:kind==="DRONE_MISSION"?"PLANNED":"ESTIMATED",
   location_source:"USER_DECLARED",status:"OWNER_DECLARED",
 }};
}

export function validateGeometryRevisionInput(raw,entityKind){
 if(!raw||typeof raw!=="object"||Array.isArray(raw))return {ok:false,error:"Invalid revision body"};
 if(!Number.isInteger(raw.expected_revision)||raw.expected_revision<1){
   return {ok:false,error:"expected_revision must be a positive integer"};
 }
 const allowed=new Set(["expected_revision","geometry","label","notes"]);
 for(const name of Object.keys(raw))if(!allowed.has(name))
   return {ok:false,error:`Unsupported or authority-bearing client field: ${name}`};
 let normalizedGeometry=null;
 if(raw.geometry!==undefined&&raw.geometry!==null){
   let serializedGeometry;
   try{serializedGeometry=JSON.stringify(raw.geometry);}catch{return {ok:false,error:"Invalid geometry serialization"};}
   if(serializedGeometry.length>131072)return {ok:false,error:"Geometry exceeds 128KiB"};
   if(!permittedGeometry[entityKind]?.includes(raw.geometry?.type)||!isSupportedWorkspaceGeometry(raw.geometry))
     return {ok:false,error:"Invalid or unsupported WGS84 geometry for this entity kind"};
   normalizedGeometry=normalizeWorkspaceGeometry(raw.geometry);
 }
 let label=null;
 if(raw.label!==undefined){
   if(typeof raw.label!=="string"||!raw.label.trim()||raw.label.length>160)
     return {ok:false,error:"Label must be a non-empty string up to 160 characters"};
   label=raw.label.trim();
 }
 let notes=undefined;
 if(raw.notes!==undefined){
   if(raw.notes!==null&&(typeof raw.notes!=="string"||raw.notes.length>2000))
     return {ok:false,error:"Notes exceed 2000 characters"};
   notes=raw.notes?raw.notes.trim():null;
 }
 return {ok:true,value:{
   expected_revision:raw.expected_revision,
   geometry:normalizedGeometry,
   label,
   notes,
 }};
}

export function isRegistrationRecordInScope(record,scope){
 return Boolean(record?.tenantId===scope?.tenantId && record?.farmId===scope?.farmId &&
  record?.plotId===scope?.plotId && record?.status==="OWNER_DECLARED");
}

function extractGeometry(geoJson) {
  if (!geoJson) return null;
  if (geoJson.type === "Feature" && geoJson.geometry) return geoJson.geometry;
  if (geoJson.type === "Polygon" || geoJson.type === "MultiPolygon") return geoJson;
  return null;
}

function pointInRing(pt, ring) {
  const x = pt[0], y = pt[1];
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    const intersect = ((yi > y) !== (yj > y)) &&
      (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function minDistanceToRing(pt, ring) {
  let minD = Infinity;
  for (let i = 0; i < ring.length - 1; i++) {
    const a = ring[i];
    const b = ring[i + 1];
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const l2 = dx * dx + dy * dy;
    let d;
    if (l2 === 0) {
      d = Math.hypot(pt[0] - a[0], pt[1] - a[1]);
    } else {
      let t = ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / l2;
      t = Math.max(0, Math.min(1, t));
      const px = a[0] + t * dx;
      const py = a[1] + t * dy;
      d = Math.hypot(pt[0] - px, pt[1] - py);
    }
    if (d < minD) minD = d;
  }
  return minD;
}

function pointInPolygonWithTolerance(pt, polyCoords, tolerance = 0.0001) {
  const outerRing = polyCoords[0];
  if (!outerRing || outerRing.length < 4) return false;
  const inOuter = pointInRing(pt, outerRing);
  if (!inOuter) {
    const dist = minDistanceToRing(pt, outerRing);
    return dist <= tolerance;
  }
  for (let h = 1; h < polyCoords.length; h++) {
    const hole = polyCoords[h];
    if (pointInRing(pt, hole)) {
      const distHole = minDistanceToRing(pt, hole);
      if (distHole > tolerance) return false;
    }
  }
  return true;
}

function extractPolygons(geom) {
  if (!geom) return [];
  if (geom.type === "Polygon") return [geom.coordinates];
  if (geom.type === "MultiPolygon") return geom.coordinates;
  return [];
}

function collectVertices(coords) {
  const pts = [];
  const recurse = (c) => {
    if (Array.isArray(c) && c.length === 2 && typeof c[0] === "number" && typeof c[1] === "number") {
      pts.push(c);
    } else if (Array.isArray(c)) {
      c.forEach(recurse);
    }
  };
  recurse(coords);
  return pts;
}

export function validateParcelContainment(geometry, plotGeoJson, options = {}) {
  // Fail closed if authoritative parcel boundary is unavailable
  if (!plotGeoJson) {
    return {
      ok: false,
      error: "Authoritative plot parcel boundary is missing or unavailable; spatial containment cannot be validated",
    };
  }
  const plotGeom = extractGeometry(plotGeoJson);
  if (!plotGeom || (plotGeom.type !== "Polygon" && plotGeom.type !== "MultiPolygon")) {
    return {
      ok: false,
      error: "Authoritative plot parcel has no valid Polygon or MultiPolygon geometry; spatial containment cannot be validated",
    };
  }

  const entityKind = options.entityKind || "FIELD_OBSERVATION";
  const tolerance = typeof options.tolerance === "number" ? options.tolerance : 0.0001; // ~10m tolerance at mid-latitudes

  // 1. Strict polygon containment for field observations / scouting areas
  if (entityKind === "FIELD_OBSERVATION" || entityKind === "CROP_OBSERVATION") {
    const parcelPolygons = extractPolygons(plotGeom);
    if (parcelPolygons.length === 0) {
      return {
        ok: false,
        error: "Authoritative parcel contains no valid polygon boundaries; failing closed",
      };
    }

    if (!geometry || (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon")) {
      return { ok: false, error: "Field observation requires Polygon or MultiPolygon geometry" };
    }

    const vertices = collectVertices(geometry?.coordinates);
    if (vertices.length === 0) {
      return { ok: false, error: "Geometry contains no valid coordinates to validate" };
    }

    // Fast vertex point-in-polygon check with tolerance margin
    for (const pt of vertices) {
      const isContained = parcelPolygons.some((poly) => pointInPolygonWithTolerance(pt, poly, tolerance));
      if (!isContained) {
        return {
          ok: false,
          error: `Field observation vertex [${pt[0].toFixed(5)}, ${pt[1].toFixed(5)}] is outside authoritative parcel boundary (exceeds ${Math.round(tolerance * 100000)}m tolerance)`,
        };
      }
    }

    // Full polygon topology & coverage check (concave boundaries, gaps, holes, and edge crossings)
    try {
      const scoutingFeature = geometry.type === "Feature" ? geometry : { type: "Feature", properties: {}, geometry };
      const parcelFeature = plotGeom.type === "Feature" ? plotGeom : { type: "Feature", properties: {}, geometry: plotGeom };

      // Reject self-intersecting geometries
      const kinks = turf.kinks(scoutingFeature);
      if (kinks?.features?.length > 0) {
        return {
          ok: false,
          error: "Field observation polygon has self-intersecting boundaries (kinks detected)",
        };
      }

      const toleranceMeters = Math.max(1, Math.round(tolerance * 100000)); // ~10m tolerance
      const bufferedParcel = turf.buffer(parcelFeature, toleranceMeters, { units: "meters" });
      if (!bufferedParcel) {
        return {
          ok: false,
          error: "Failed to compute spatial buffer for authoritative parcel boundary",
        };
      }

      const diff = turf.difference(turf.featureCollection([scoutingFeature, bufferedParcel]));
      if (diff) {
        const outsideArea = turf.area(diff);
        if (outsideArea > 1.0) { // Ignore floating-point micro-slivers <= 1 m²
          return {
            ok: false,
            error: `Field observation geometry is outside authoritative parcel boundary (edges or coverage outside parcel by ${outsideArea.toFixed(1)} m² exceeds ${toleranceMeters}m tolerance)`,
          };
        }
      }
    } catch (err) {
      return {
        ok: false,
        error: `Spatial topology validation failed: ${err instanceof Error ? err.message : String(err)}`,
      };
    }

    return { ok: true };
  }

  // 2. Operational envelope containment with buffer for drone missions / flight corridors
  const pBounds = geometryBounds(plotGeom);
  const gBounds = geometryBounds(geometry);
  if (!pBounds || !gBounds) {
    return { ok: false, error: "Unable to calculate bounding coordinates for geometry" };
  }

  const buffer = typeof options.buffer === "number" ? options.buffer : 0.02; // ~2.2 km operational envelope margin
  const [pMinX, pMinY, pMaxX, pMaxY] = pBounds;
  const [gMinX, gMinY, gMaxX, gMaxY] = gBounds;

  if (
    gMinX < pMinX - buffer ||
    gMaxX > pMaxX + buffer ||
    gMinY < pMinY - buffer ||
    gMaxY > pMaxY + buffer
  ) {
    return {
      ok: false,
      error: `Flight corridor bounds [${gMinX.toFixed(4)}, ${gMinY.toFixed(4)}, ${gMaxX.toFixed(4)}, ${gMaxY.toFixed(4)}] exceed authorized operational margin [${(pMinX - buffer).toFixed(4)}, ${(pMinY - buffer).toFixed(4)}] to [${(pMaxX + buffer).toFixed(4)}, ${(pMaxY + buffer).toFixed(4)}]`,
    };
  }

  return { ok: true };
}
