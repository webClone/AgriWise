import assert from "node:assert/strict";
import test from "node:test";

import {
  activeCropCyclePrismaFilter,
  isActiveCropCycleStatus,
  TERMINAL_CROP_CYCLE_STATUSES,
} from "../../src/lib/agribrain/crop-cycle-status.mjs";

test("terminal failed and harvested cycles are never active", () => {
  assert.deepEqual(
    [...TERMINAL_CROP_CYCLE_STATUSES].sort(),
    ["FAILED", "HARVESTED"],
  );
  assert.equal(isActiveCropCycleStatus("FAILED"), false);
  assert.equal(isActiveCropCycleStatus("harvested"), false);
  assert.equal(isActiveCropCycleStatus("GROWING"), true);
  assert.equal(isActiveCropCycleStatus("PLANNED"), true);
  assert.equal(isActiveCropCycleStatus("CANCELLED"), false);
  assert.equal(isActiveCropCycleStatus(""), false);
});

test("Prisma scientific-cycle queries use the same terminal exclusion", () => {
  assert.deepEqual(activeCropCyclePrismaFilter(), {
    in: [
      "PLANNED",
      "PLANTED",
      "GROWING",
      "FLOWERING",
      "FRUITING",
      "READY_TO_HARVEST",
    ],
  });
});
