import test from "node:test";
import assert from "node:assert/strict";
import { P02_PREVIEW_CROSSWALK, getUnresolvedPreviewLabels } from "../../src/components/farm/workspace/p04-preview-crosswalk.mjs";
import { TOOL_MANIFEST } from "../../src/components/farm/workspace/tool-registry-p04.mjs";

test("P04-C02 preview catalog parity is explicit and does not invent equivalence", () => {
  assert.equal(P02_PREVIEW_CROSSWALK.length,94);
  assert.equal(new Set(P02_PREVIEW_CROSSWALK.map(e=>e.legacyId)).size,94);
  assert.equal(getUnresolvedPreviewLabels().length,94);
  assert.ok(P02_PREVIEW_CROSSWALK.every(e=>e.reviewStatus==="pending_human_review"&&e.approvedCanonicalId===null));
  const ids = new Set(TOOL_MANIFEST.map(e=>e.id));
  for(const item of P02_PREVIEW_CROSSWALK) for (const x of item.proposedCandidates) assert.ok(ids.has(x.id));
});
