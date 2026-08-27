export interface PixelInspectorCapabilities {
  canSamplePixel: boolean;
  canInterpretForScouting: boolean;
  canInterpretDiagnostically: boolean;
  canUseForPrescription: boolean;
}

export function resolvePixelInspectorCapabilities(input?: {
  surface?: Record<string, any> | null;
  inspectorAuthorization?: Record<string, any> | null;
}): PixelInspectorCapabilities;

export function resolvePixelInspectorTitle(
  surfaceType?: string | null,
  activeMode?: string | null,
): string | null;

export function resolveCropStageLabels(
  cropName?: string | null,
  cropStage?: string | null,
): {
  cropLabel: string | null;
  growthStageLabel: string | null;
};
