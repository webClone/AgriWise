import test from "node:test";
import assert from "node:assert/strict";
import { TOOL_FAMILIES, TOOL_MANIFEST, TOOL_MANIFEST_COUNT, getToolConcept, searchToolConcepts, describeToolAvailability } from "../../src/components/farm/workspace/tool-registry-p04.mjs";

test("P04.01 94 canonical Pass 08 concepts survive without duplicate IDs", () => {
  assert.equal(TOOL_MANIFEST_COUNT, 94);
  assert.equal(new Set(TOOL_MANIFEST.map(t => t.id)).size, 94);
  assert.deepEqual(TOOL_FAMILIES.map(f => f.count), [17,12,13,15,19,18]);
  for (const group of TOOL_FAMILIES) assert.equal(TOOL_MANIFEST.filter(t => t.family === group.id).length, group.count);
});

test("P04.01 all catalog items searchable and referentially stable", () => {
  for (const entry of TOOL_MANIFEST) {
    assert.equal(getToolConcept(entry.id), entry);
    assert.ok(searchToolConcepts(entry.title.en, entry.family).some(t => t.id === entry.id), entry.title.en);
    assert.ok(entry.title.en.length > 3);
  }
  assert.equal(searchToolConcepts("", "all").length, 94);
  assert.equal(searchToolConcepts("no-such-tool-protocol").length, 0);
  assert.equal(getToolConcept("__proto__"), null);
});

test("P04.02 discovery never grants scientific or physical execution authority", () => {
  for (const entry of TOOL_MANIFEST) {
    const capability = describeToolAvailability(entry.id);
    assert.equal(capability.discoverable, true);
    assert.equal(capability.canOpen, true);
    assert.equal(capability.canExecute, false);
    assert.equal(capability.canDispatch, false);
    assert.equal(entry.maturity, "unreviewed");
    assert.equal(entry.capability, "read_only");
    assert.equal(entry.surface, "concept_preview");
  }
  assert.equal(describeToolAvailability("unknown").canExecute, false);
});
