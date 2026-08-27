/** Crop-cycle workflow statuses that cannot be selected as the active cycle. */
export const TERMINAL_CROP_CYCLE_STATUSES = Object.freeze([
  "HARVESTED",
  "FAILED",
]);

export const ACTIVE_CROP_CYCLE_STATUSES = Object.freeze([
  "PLANNED",
  "PLANTED",
  "GROWING",
  "FLOWERING",
  "FRUITING",
  "READY_TO_HARVEST",
]);

/** Prisma-compatible filter for the current scientific/operational cycle. */
export function activeCropCyclePrismaFilter() {
  return { in: [...ACTIVE_CROP_CYCLE_STATUSES] };
}

/** Shared UI guard for arrays that may still contain historical cycles. */
export function isActiveCropCycleStatus(status) {
  const normalized = String(status || "").trim().toUpperCase();
  return ACTIVE_CROP_CYCLE_STATUSES.includes(normalized);
}
