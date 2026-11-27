export interface WorldModelV1SummaryView {
  cropVerified: boolean;
  tenantVerified: boolean;
  syntheticRejected: boolean;
  cropBadgeLabel: string | null;
  cropDeclarationAuthority: string | null;
  tenantLabel: string | null;
  tenantOwnershipSource: string | null;
  asOfCropLabel: string | null;
  physicalRegime: string | null;
  preKnownCycleUnknown: boolean;
  unknownMassPct: number | null;
  latestEoGroup: string | null;
  withheldReprocessedAfterK: number;
  cropChronologyHash: string | null;
  weatherLineageHash: string | null;
  crossLayerPriorVersion: string | null;
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
