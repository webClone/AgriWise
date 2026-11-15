/** Geometry guard shared by the server envelope and client scene runtime. */
const MAX_VERTICES=10000;
const position=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)&&Math.abs(p[0])<=180&&Math.abs(p[1])<=90;
const same=(a,b)=>a[0]===b[0]&&a[1]===b[1];
function validateLine(points,closed=false){
 if(!Array.isArray(points)||points.length<(closed?4:2)||points.length>MAX_VERTICES)return false;
 if(!points.every(position))return false;
 if(closed){
  if(!same(points[0],points[points.length-1]))return false;
  const vertices=points.slice(0,-1);
  if(new Set(vertices.map(p=>p.join(","))).size<3)return false;
  let area=0;
  for(let i=0;i<vertices.length;i++){const a=vertices[i],b=vertices[(i+1)%vertices.length];area+=a[0]*b[1]-b[0]*a[1];}
  return Math.abs(area)>1e-12;
 }
 return points.some(p=>!same(p,points[0]));
}
export function isSupportedWorkspaceGeometry(geometry){
 if(!geometry||typeof geometry!=="object")return false;
 const c=geometry.coordinates;
 if(geometry.type==="Point")return position(c);
 if(geometry.type==="LineString")return validateLine(c);
 if(geometry.type==="Polygon")return Array.isArray(c)&&c.length>0&&c.length<=100&&c.every(r=>validateLine(r,true));
 if(geometry.type==="MultiPolygon")return Array.isArray(c)&&c.length>0&&c.length<=100&&c.every(poly=>Array.isArray(poly)&&poly.length>0&&poly.length<=100&&poly.every(r=>validateLine(r,true)));
 return false;
}
export function normalizeWorkspaceGeometry(geometry){
 if(!isSupportedWorkspaceGeometry(geometry))throw new TypeError("Invalid WGS84 workspace geometry");
 // Deep detach: no caller can mutate the original evidence coordinates after signing the envelope.
 const positions=JSON.parse(JSON.stringify(geometry.coordinates));
 const freeze=a=>{if(Array.isArray(a)){a.forEach(freeze);Object.freeze(a);}};
 freeze(positions);
 return Object.freeze({type:geometry.type,coordinates:positions});
}
export function geometryBounds(geometry){
 if(!isSupportedWorkspaceGeometry(geometry))return null;
 const xy=[];
 const collect=n=>{if(position(n))xy.push(n);else if(Array.isArray(n))n.forEach(collect);};
 collect(geometry.coordinates);
 const xs=xy.map(p=>p[0]),ys=xy.map(p=>p[1]);
 return [Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];
}
export function isRenderableWorkspaceEntity(e){
 return Boolean(e?.geometry&&isSupportedWorkspaceGeometry(e.geometry)&&
   e.spatial_support?.has_location===true&&
   ["REGISTERED_HARDWARE","OBSERVED_GPS","SURVEYED"].includes(e.spatial_support?.location_source)&&
   (e.geometry.type==="Point"?e.display_eligibility?.eligible_for_map_pin===true:
    e.display_eligibility?.eligible_for_map_geometry===true));
}
