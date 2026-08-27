export type TerminalCropCycleStatus = "HARVESTED" | "FAILED";
export type ActiveCropCycleStatus =
  | "PLANNED"
  | "PLANTED"
  | "GROWING"
  | "FLOWERING"
  | "FRUITING"
  | "READY_TO_HARVEST";

export const TERMINAL_CROP_CYCLE_STATUSES: readonly TerminalCropCycleStatus[];
export const ACTIVE_CROP_CYCLE_STATUSES: readonly ActiveCropCycleStatus[];

export function activeCropCyclePrismaFilter(): {
  in: ActiveCropCycleStatus[];
};

export function isActiveCropCycleStatus(status: unknown): boolean;
