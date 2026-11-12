# Akaloris Plot — Round 2 / Pass 01: owner-scoped route, telemetry and navigation

**Audit target:** `integrate/layer0-layer1-observation-pilot@1ee2c20119af29dd1f0a0b46c85217d91206b744` (pinned). **Method:** static source/control-flow; no authenticated browser or database calls executed.

### R2-01 — P1, development owner bypass (confirmed in source, production impact not established)

[`src/lib/farm-services.ts#L58-L88`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/farm-services.ts#L58-L88) builds Prisma `where` as `{id:plotId,farmId,...(ownerId && !isDev ? ownerScope(ownerId) : {})}`. Thus when `NODE_ENV=development`, the owner predicate is absent **even for a valid signed-in user**. Layout permits missing user session in development ([`layout.tsx#L22-L38`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/%5Bid%5D/plot/%5BplotId%5D/layout.tsx#L22-L38)). If a shared dev environment is accessible, knowing a plot+farm ID could expose owner-specific plot, photos and sensor metadata. This is not an observed production bypass.

**Remediation:** use owner predicate in all environments; a dev-only bootstrap should issue a real scoped session and then use the same authorization function. Deny other-owner plots even in development. **Negative test:** logged-in Alice in dev requests Bob's valid plot IDs; should return 404 without loading nested records.

### R2-02 — P1, incomplete telemetry tenant

[`mapFarm()`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/farm-services.ts#L23-L35) omits `farm.userId`, but [`layout.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/%5Bid%5D/plot/%5BplotId%5D/layout.tsx#L48-L70) passes `session?.userId || farm.userId || farm.ownerId || ''` to `PlotTelemetryProvider`. The initialization in [`usePlotTelemetry.ts#L34-L40`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/usePlotTelemetry.ts#L34-L40) requires all three scope keys. This explains the previously reported `telemetry_scope_incomplete` when no usable session exists. The latest screenshot rendered, so current reproduction is not proven.

**Remediation:** server-resolved typed `PlotOwnerScope`, no empty string fallback, never mount telemetry without verified `(tenant,farm,plot)`.

### R2-03 — P2, wrong layout for irrigation and misplaced readiness

[`PlotLayoutClient.tsx#L16-L35`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/%5Bid%5D/plot/%5BplotId%5D/PlotLayoutClient.tsx#L16-L35) marks every route except `user-inputs`, `analysis`, `raw-data` and `live-assistance` as map view: **`irrigation` is mistakenly included** and inherits `h-screen`, `overflow-hidden`. The prop `topBarFull` is never used. User inputs also treats `plot.area>0` as adequate geometry; crop+soil+that check labels irrigation unlocked, not an actuation safety proof ([`user-inputs/page.tsx#L26-L65`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/%5Bid%5D/plot/%5BplotId%5D/user-inputs/page.tsx#L26-L65)).

**Remediation:** explicit route layouts (`fullScreenMap`, `scrollablePage`, `simulatorOnly`) and distinct labels `configuration readiness` vs `scientific admissibility` vs `hardware readiness`. **Acceptance:** test 375px/768px/1600px, keyboard navigation, unknown route, missing geometry and active crop-cycle changes.

**Result:** 2 confirmed source-level contract defects and one layout/readiness issue; runtime effects are held for E2E testing.