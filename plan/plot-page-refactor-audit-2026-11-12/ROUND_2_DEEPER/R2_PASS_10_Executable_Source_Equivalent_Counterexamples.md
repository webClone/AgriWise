# Akaloris Plot — Round 2 / Pass 10: executable adversarial counterexamples

**Pinned GitHub commit:** [`1ee2c20119af29dd1f0a0b46c85217d91206b744`](https://github.com/webClone/AgriWise/commit/1ee2c20119af29dd1f0a0b46c85217d91206b744)  
**Execution:** Node.js v22, self-contained **source-equivalent** reproductions, executed on 2026-11-12.  
**Precise limitation:** the browser, MapLibre/DeckGL, Prisma, FastAPI, Python scientific engine, and the real checked-out repository **were not run**. The probe faithfully reproduces the inspected predicates and raster-mask algorithm in a standalone file. Its results show specific algorithmic counterexamples, not live production exploitability.

## Reproduction results

| Repro ID | Source logic exercised | Correct behavior | Observed with source-equivalent code | Finding |
|---|---|---|---|---|
| P10-A | `buildPolygonMask` first exterior ring | Pixel center inside polygon hole must be transparent (`0`) | Hole pixel `1`; all 16 cells filled | R2-10, P1 |
| P10-B | `buildPolygonMask` MultiPolygon selection | Second island `(3.5,3.5)` included (`1`) | Pixel `0`; only first island admitted | R2-10, P1 |
| P10-C | `buildPolygonMask` cache key | Geometry edit with same bounds/grid invalidates cached pixels | Exact same mask object reused | R2-11, P1 |
| P10-D | `getAuthorizedPlotRouteContext` owner predicate | Logged-in Alice's dev query for Bob's identifiers remains scoped to Alice | `where` contains only `id` and `farmId`; owner filter omitted | R2-01, P1 |
| P10-E | `sanitizeRecommendedAction` with `prescription_blocked` | Display suppression of dose-bearing text without signed action authority | `actionLevel=act_blocked`, `text="Apply 25mm irrigation"`, `suppressed=false` | R2-15, P1 |
| P10-F | `PlotLoadingSequence` request error classifier | Head-await timeout remains `PENDING/WAITING`, not terminal failure | Regex maps timeout message to `FAILED` | R2-04, P1 |

**Result:** 6/6 intended negative counterexamples reproduced in the standalone model. **This is not 6/6 production regression passes.**

## Source anchors

1. [`buildPolygonMask.ts#L16-L120`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/map/utils/buildPolygonMask.ts#L16-L120): `geometry.coordinates[0][0]` / `coordinates[0]` and `cacheKey` excluding geometry.
2. [`farm-services.ts#L58-L88`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/farm-services.ts#L58-L88): dev-mode omission of `ownerScope(ownerId)`.
3. [`plot-map-evidence-state.ts#L627-L666`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/plot-map-evidence-state.ts#L627-L666): blocked action retains original text.
4. [`PlotLoadingSequence.tsx#L250-L285`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/PlotLoadingSequence.tsx#L250-L285): timeout string does not match pending regex, resulting in `FAILED`.

## Exact executed files

- [Source-equivalent Node probe](probes/source_equivalent_adversarial_probes.mjs)
- [Machine-readable execution result](probes/adversarial_probe_output.json)

## Required next tests against real repository

- Mount the actual `buildPolygonMask.ts` with its runtime dependencies, not just a transcription; test Polygon hole, MultiPolygon and A→B→A geometry change.
- Execute actual server route with two persisted owners, a real dev signed session and foreign plot identifiers.
- Render the actual sanitized action in every consumer, including zone detail, zone inspector, farmer/expert sidebars and chat prompts.
- Execute delayed canonical publication with durable job `RUNNING` after 25 seconds; verify status is not `FAILED`, no replacement `forceRefresh` is offered, and exactly one existing job is retained.
- Preserve zero physical actuator commands as an independently verified interlock invariant.

**Release result: HOLD** for real-world operational use until actual-code negatives pass; this probe is supporting evidence only.