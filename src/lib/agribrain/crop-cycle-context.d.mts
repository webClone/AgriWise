export interface CropCycleNamespaceV2 {
  tenant_id: string;
  farm_id: string;
  plot_id: string;
}

export interface CanonicalCropCycleContextV2 {
  contract_version: "canonical_crop_cycle_context_v2";
  plot_namespace: CropCycleNamespaceV2;
  crop_cycle_id: string;
  geometry_version: string;
  effective_at: string;
  declared_crop_code: string;
  declared_crop_authority:
    | "UNKNOWN"
    | "REGISTRY_DECLARED"
    | "USER_CONFIRMED"
    | "FARMER_CONFIRMED"
    | "OFFICIAL_PARCEL_LABEL"
    | "AGRONOMIST_CONFIRMED";
  declared_crop_at: string | null;
  declared_crop_source: string;
  variety: string | null;
  irrigation_type: string;
  plant_date: string | null;
  planting_date: string | null;
  plant_date_status: "confirmed" | "estimated" | "interval" | "unknown";
  plant_date_source: string;
  plant_date_confidence: number | null;
  plant_date_min: string | null;
  plant_date_max: string | null;
  harvest_dates: {
    expected: string | null;
    actual: string | null;
  };
  administrative_status: string;
  administrative_status_role: "workflow_only_not_phenology_evidence";
  management_event_refs: readonly string[];
  phenology_from_administrative_status_allowed: false;
  content_hash: string;
}

export const CROP_CYCLE_CONTEXT_CONTRACT_VERSION:
  "canonical_crop_cycle_context_v2";
export function canonicalScientificHash(value: unknown): string;
export function buildCanonicalCropCycleContextV2(
  input: Record<string, any>,
): CanonicalCropCycleContextV2;
