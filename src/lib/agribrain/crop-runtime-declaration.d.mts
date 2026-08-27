export interface CropRuntimeDeclarationReceiptV1 {
  contract_version: "crop_runtime_declaration_v1";
  plot_namespace: {
    tenant_id: string;
    farm_id: string;
    plot_id: string;
  };
  crop_cycle_id: string;
  crop_code: string;
  authority:
    | "FARMER_CONFIRMED"
    | "AGRONOMIST_CONFIRMED"
    | "OFFICIAL_PARCEL_LABEL";
  declared_at: string;
  source: string;
  cycle_created: boolean;
  plant_date_asserted: false;
  content_hash: string;
}

export const CROP_RUNTIME_DECLARATION_VERSION: "crop_runtime_declaration_v1";

export function normalizeCropRuntimeDeclarationReceipt(
  value: unknown,
  expected?: Partial<CropRuntimeDeclarationReceiptV1["plot_namespace"]>,
): Readonly<CropRuntimeDeclarationReceiptV1>;
