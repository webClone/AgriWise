export interface WorldModelV1SummaryView {
  cropVerified: boolean;
  tenantVerified: boolean;
  syntheticRejected: boolean;
  cropBadgeLabel: string | null;
  tenantLabel: string | null;
  asOfCropLabel: string | null;
  physicalRegime: string | null;
  unknownMassPct: number | null;
  latestEoGroup: string | null;
  exploratory36_90d: {
    n: number;
    skillVsPersistence: number | null;
    rmse: number | null;
    exploratoryOnly: boolean;
  } | null;
  primaryFailureCause: string | null;
  primaryFailureAction: string | null;
}

export function summarizeWorldModelV1View(payload: any): WorldModelV1SummaryView;
