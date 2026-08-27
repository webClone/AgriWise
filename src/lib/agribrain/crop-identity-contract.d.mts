export interface CropLabelConfirmationInput {
  plotId: string;
  cropCode: string;
}

export interface CropLabelConfirmationPayload {
  plotId: string;
  cropCode: string;
  synthetic: false;
}

export function getCropCandidateRankingShare(
  candidate?: { ranking_share?: number | null } | null,
): number | null;

export function buildCropLabelConfirmationPayload(
  input: CropLabelConfirmationInput,
): CropLabelConfirmationPayload;

export function humanizeCropAuthority(authority?: string | null): string;
