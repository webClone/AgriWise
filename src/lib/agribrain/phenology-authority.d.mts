export interface PhenologyPublicationContext {
  resolved_crop_stage?: string;
  phenology_evidence_class?: string;
  phenology_authority?: string;
  phenology_source?: string;
  required_phenology_source?: string;
  phenology_confidence?: number;
  phenology_posterior_hash?: string;
  phenology_receipt_valid?: boolean;
  phenology_evidence_needed_reason?: string;
  stage_available?: boolean;
  contract_version?: string;
  [key: string]: unknown;
}

export function normalizeCanonicalPhenologyPublication(input?: {
  resolvedCropStage?: string | null;
  phenologyContext?: PhenologyPublicationContext | null;
}): {
  resolvedCropStage: string;
  phenologyContext: PhenologyPublicationContext;
};

export function phenologyEvidenceReasonLabel(reason?: string | null): string;
