# Akaloris P06.05 — Interactive Geometry Authoring & Controlled Lifecycle, Candidate 01

**Branch:** `feat/plot-workspace-p06-geometry-authoring`  
**Base:** Accepted P06.04 (`981b3f617a80c36f2396649b520edf8a2f1ccd01`)  
**Canonical Draft PR #30:** Preserved untouched at `599c4f6`.  
**Safety Gate:** Physical actuation fail-closed (`AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`).

---

## 1. Architectural Separation & Lifecycle Model

P06.05 delivers an interactive editing and controlled lifecycle system for plot-scoped spatial geometries, while strictly preserving scientific authority boundaries.

### Core Architectural Separation
```
User-drawn geometry (Field Canvas Drawing Mode)
  └── Owner-declared registration (POST: PLANNED / ESTIMATED, Rev 1, SHA-256)
        └── Controlled versioned lifecycle (PATCH: Optimistic Concurrency + Append-Only Revision History)
              └── Soft-revocation (DELETE: status REVOKED, instantaneous map exclusion, history retained)
                    └── Independently qualified evidence (Admitted ONLY via governed sensor pipelines)
```

### Invariants:
1. **Never conflated with ground truth:** User-drawn lines and polygons remain `OWNER_DECLARED`. A drone corridor is `PLANNED`; a scouting zone is `ESTIMATED`. They do not claim live telemetry, optical calibration, or scientific publication authority.
2. **Append-only historical retention:** A `PATCH` never destroys previous geometry coordinates or hashes. Every modification appends an immutable `WorkspaceGeometryRevision` record with previous geometry, digest, editor, operation, and timestamp.
3. **Optimistic concurrency control:** `PATCH` and `DELETE` require `expected_revision`. Mismatched revisions return `409 Conflict`.
4. **Source-linking requirement preserved:** `FIELD_OBSERVATION` registrations require an existing, authorized `CropObservation` record in the plot's active crop cycle. The authoring flow allows selecting an existing observation or creating an authorized observation record first.
5. **Mode isolation:** When spatial authoring is active, map click-events place vertices rather than triggering device inspection, entity picking, or tool launching.

---

## 2. API Contract Specification

### 2.1 Collection: `POST /api/plots/[id]/workspace/geometries`
Registers a new owner-declared geometry.
- **Request Body:**
  ```json
  {
    "entity_kind": "DRONE_MISSION" | "FIELD_OBSERVATION" | "CAMERA",
    "source_kind": "OWNER_PLAN" | "CROP_OBSERVATION" | "IP_CAMERA",
    "source_id": string | null,
    "label": string,
    "notes"?: string | null,
    "geometry": GeoJSON LineString | Polygon
  }
  ```
- **Response (201 Created):**
  Creates `WorkspaceGeometryRegistration` (rev 1) and initial `WorkspaceGeometryRevision` (operation: `"CREATE"`). Returns projected `WorkspaceFeatureEnvelope` with `source_version: "registered-v1:<id>"`, `properties.revision: 1`.

### 2.2 Resource: `PATCH /api/plots/[id]/workspace/geometries/[regId]`
Revises an existing owner-declared geometry under optimistic concurrency.
- **Request Body:**
  ```json
  {
    "expected_revision": number,
    "label"?: string,
    "notes"?: string | null,
    "geometry"?: GeoJSON LineString | Polygon
  }
  ```
- **Responses:**
  - `409 Conflict`: If `expected_revision !== record.revision`.
  - `400 Bad Request`: If geometry is invalid or record is already `REVOKED`.
  - `200 OK`: Atomically appends `WorkspaceGeometryRevision` (operation: `"UPDATE"`, rev: $N+1$) and updates `WorkspaceGeometryRegistration` (revision: $N+1$). Returns updated feature envelope with `source_version: "registered-v<N+1>:<id>"`.

### 2.3 Resource: `DELETE /api/plots/[id]/workspace/geometries/[regId]`
Soft-revokes an owner-declared geometry under optimistic concurrency.
- **Request Body / Query:**
  ```json
  {
    "expected_revision"?: number,
    "reason"?: string
  }
  ```
- **Responses:**
  - `409 Conflict`: If `expected_revision` does not match current revision, or already revoked.
  - `200 OK`: Atomically appends `WorkspaceGeometryRevision` (operation: `"REVOKE"`, rev: $N+1$) and updates `WorkspaceGeometryRegistration` (`status: "REVOKED"`).
  - The feature is immediately omitted on subsequent `GET /workspace/entities` and `GET /workspace/geometries`.

### 2.4 History: `GET /api/plots/[id]/workspace/geometries/[regId]/revisions`
Retrieves the complete immutable audit trail of the geometry.
- **Response (200 OK):**
  ```json
  {
    "success": true,
    "registration_id": "<id>",
    "revisions": [
      {
        "revision": 1,
        "operation": "CREATE",
        "geometry": { ... },
        "geometryDigest": "...",
        "name": "...",
        "editorId": "...",
        "createdAt": "..."
      },
      {
        "revision": 2,
        "operation": "UPDATE",
        ...
      }
    ]
  }
  ```

---

## 3. Frontend Interactive Authoring & Lifecycle Architecture

1. **Drawing HUD & State Machine:**
   - Authoring mode state: `activeTool: "line" | "polygon" | null`, `vertices: [number, number][]`.
   - While authoring is active:
     - Map click events are captured by authoring controller.
     - Entity selection and investigation launching are disabled.
     - Live DeckGL rubberband layer visualizes placed vertices and path/fill preview.
     - HUD displays: coordinate readouts, vertex count, `[Undo Last Vertex]`, `[Clear]`, `[Cancel]`, `[Finish & Save]`.
2. **Metadata & Source-Link Dialog:**
   - When user clicks "Finish & Save":
     - Prompts for Name / Label and Notes.
     - If `FIELD_OBSERVATION`: presents selector of existing crop observations on the plot, or allows creating a new observation record in the active crop cycle.
     - Submits `POST /api/plots/[id]/workspace/geometries`.
     - Automatically refreshes workspace entities and selects the new shape.
3. **Inspector Lifecycle Actions:**
   - Inspector displays `Revision: N · OWNER_DECLARED`.
   - "Revise Geometry": opens revision drawer to modify title, notes, or redraw coordinates via `PATCH`.
   - "Revoke Geometry": opens confirmation dialog and dispatches `DELETE`, immediately removing the entity from map and directory.
   - "View Revision History": displays timeline of all past revisions and SHA-256 digests from `GET .../revisions`.

---

## 4. Focused Acceptance Criteria

1. **Draw, Undo, Finish & Save:** Interactive drawing of LineString and Polygon, vertex undo, and persistence via authenticated API.
2. **Reload & Projection:** Reloading the page fetches the persisted geometry directly from MongoDB with matching SHA-256 digest.
3. **Revision & Concurrency:** Updating geometry via `PATCH` advances to revision 2, updates digest, and rejects mismatched `expected_revision` with 409.
4. **Historical Auditability:** `GET .../revisions` returns complete revision history (rev 1 and rev 2 preserved).
5. **Soft-Revocation:** `DELETE` marks registration `REVOKED`; subsequent entity reads immediately exclude it from the map while preserving revision history.
6. **Safety & Boundaries:** Actuator remains fail-closed; no scientific authority is inferred; canonical Draft PR #30 remains untouched at `599c4f6`.
