/**
 * Akaloris P06.05: Interactive Geometry Authoring & Lifecycle Client Services.
 * Enforces optimistic concurrency and owner-declared epistemic boundaries.
 */

export interface GeometryDraft {
  entityKind: "DRONE_MISSION" | "FIELD_OBSERVATION";
  type: "LineString" | "Polygon";
  coordinates: [number, number][]; // [lon, lat]
}

export interface NewCropObservationPayload {
  title: string;
  type?: string;
  severity?: string;
  description?: string | null;
}

export interface RegisterGeometryPayload {
  entity_kind: "DRONE_MISSION" | "FIELD_OBSERVATION" | "CAMERA";
  source_kind: "OWNER_PLAN" | "CROP_OBSERVATION" | "IP_CAMERA";
  source_id?: string | null;
  new_observation?: NewCropObservationPayload | null;
  label: string;
  notes?: string | null;
  geometry: {
    type: "LineString" | "Polygon" | "MultiPolygon";
    coordinates: any;
  };
}

export interface ReviseGeometryPayload {
  expected_revision: number;
  label?: string;
  notes?: string | null;
  geometry?: {
    type: "LineString" | "Polygon" | "MultiPolygon";
    coordinates: any;
  };
}

export interface GeometryRevisionRecord {
  id: string;
  revision: number;
  operation: "CREATE" | "UPDATE" | "REVOKE";
  geometry: any;
  geometryDigest: string;
  name: string;
  notes: string | null;
  editorId: string;
  createdAt: string;
}

export async function createGeometryRegistration(
  plotId: string,
  payload: RegisterGeometryPayload
) {
  const res = await fetch(`/api/plots/${encodeURIComponent(plotId)}/workspace/geometries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `Registration failed with status ${res.status}`);
  }
  return data;
}

export async function reviseGeometryRegistration(
  plotId: string,
  regId: string,
  payload: ReviseGeometryPayload
) {
  const res = await fetch(
    `/api/plots/${encodeURIComponent(plotId)}/workspace/geometries/${encodeURIComponent(regId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.error || `Revision failed with status ${res.status}`);
    (err as any).status = res.status;
    (err as any).currentRevision = data.current_revision;
    throw err;
  }
  return data;
}

export async function revokeGeometryRegistration(
  plotId: string,
  regId: string,
  expectedRevision: number,
  reason?: string
) {
  const res = await fetch(
    `/api/plots/${encodeURIComponent(plotId)}/workspace/geometries/${encodeURIComponent(regId)}`,
    {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_revision: expectedRevision, reason }),
    }
  );
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.error || `Revocation failed with status ${res.status}`);
    (err as any).status = res.status;
    throw err;
  }
  return data;
}

export async function getGeometryRevisions(plotId: string, regId: string) {
  const res = await fetch(
    `/api/plots/${encodeURIComponent(plotId)}/workspace/geometries/${encodeURIComponent(regId)}/revisions`
  );
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `Failed to fetch revision history: ${res.status}`);
  }
  return data as {
    success: boolean;
    registration_id: string;
    current_revision: number;
    current_status: string;
    revisions: GeometryRevisionRecord[];
  };
}

/**
 * Validates whether draft coordinates form a closed polygon or valid linestring
 */
export function formatDraftGeometry(draft: GeometryDraft) {
  if (draft.type === "LineString") {
    if (draft.coordinates.length < 2) return null;
    return {
      type: "LineString" as const,
      coordinates: draft.coordinates,
    };
  }

  if (draft.type === "Polygon") {
    if (draft.coordinates.length < 3) return null;
    const ring = [...draft.coordinates];
    const first = ring[0];
    const last = ring[ring.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) {
      ring.push([first[0], first[1]]);
    }
    return {
      type: "Polygon" as const,
      coordinates: [ring],
    };
  }

  return null;
}
