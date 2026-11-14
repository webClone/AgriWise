export const WORKSPACE_FEATURE_CONTRACT_VERSION: "2026.11-p05.1";

export type EntityKind =
  | "SENSOR"
  | "CAMERA"
  | "DRONE_MISSION"
  | "FIELD_OBSERVATION"
  | "FIELD_EVENT"
  | "ZONE";

export type LocationSource =
  | "REGISTERED_HARDWARE"
  | "OBSERVED_GPS"
  | "SURVEYED"
  | "UNSPECIFIED";

export type EpistemicClass =
  | "REGISTERED_GROUND_TRUTH"
  | "OBSERVED_TELEMETRY"
  | "ESTIMATED"
  | "SIMULATED"
  | "PLANNED";

export interface OwnerScopeEnvelope {
  tenant_id: string;
  farm_id: string;
  plot_id: string;
}

export interface PointGeometry {
  type: "Point";
  coordinates: [number, number]; // [lng, lat]
}

export interface SpatialSupportEnvelope {
  has_location: boolean;
  location_source: LocationSource;
  support_radius_m: number | null;
  depth_cm: number | null;
  altitude_m: number | null;
  zone_id: string | null;
}

export interface TemporalExtentEnvelope {
  observed_at: string | null;
  first_available_at: string | null;
  valid_from: string | null;
  valid_to: string | null;
  published_at: string | null;
}

export interface DisplayEligibilityEnvelope {
  eligible_for_map_pin: boolean;
  eligible_for_catalog: boolean;
  ineligibility_reason: string | null;
}

export interface ProvenanceEnvelope {
  record_digest: string;
  verified_identity: boolean;
  [key: string]: unknown;
}

export interface WorkspaceFeatureEnvelope {
  contract_version: string;
  envelope_id: string;
  entity_kind: EntityKind;
  entity_id: string;
  source_version: string;
  owner_scope: OwnerScopeEnvelope;
  geometry: PointGeometry | null;
  spatial_support: SpatialSupportEnvelope;
  temporal_extent: TemporalExtentEnvelope;
  epistemic_class: EpistemicClass;
  properties: Record<string, unknown>;
  provenance: ProvenanceEnvelope;
  display_eligibility: DisplayEligibilityEnvelope;
}

export interface CreateFeatureEnvelopeParams {
  entity_kind: EntityKind;
  entity_id: string;
  source_version?: string;
  owner_scope: {
    tenant_id?: string;
    tenantId?: string;
    farm_id?: string;
    farmId?: string;
    plot_id?: string;
    plotId?: string;
  };
  latitude?: number | null;
  longitude?: number | null;
  altitude_m?: number | null;
  depth_cm?: number | null;
  support_radius_m?: number | null;
  zone_id?: string | null;
  location_source?: LocationSource;
  epistemic_class?: EpistemicClass;
  temporal_extent?: Partial<TemporalExtentEnvelope>;
  properties?: Record<string, unknown>;
  provenance?: Record<string, unknown>;
  is_centroid_substitute?: boolean;
}

export function createWorkspaceFeatureEnvelope(params: CreateFeatureEnvelopeParams): WorkspaceFeatureEnvelope;

export function validateWorkspaceFeatureEnvelope(
  envelope: unknown,
  expectedScope?: { tenant_id?: string; tenantId?: string; plot_id?: string; plotId?: string }
): { valid: boolean; errors: string[] };
