# Akaloris Plot Page — Pass 01: Route, Authentication, Ownership, and Page Lifecycle

> **Audit evidence scope:** Static GitHub source inspection pinned to commit `1ee2c20119af29dd1f0a0b46c85217d91206b744` and the provided 1600×900 browser screenshot. Files were retrieved from the repository and inspected structurally; selected control-flow paths were deep-traced. No local Next.js/FastAPI runtime, tests, browser automation, or production hardware was executed. Findings distinguish observed screenshot behavior, confirmed source behavior, and test-required hypotheses.


## Pass coverage

- Source files inventoried and inspected: **14/14 (100% of this pass’s selected static inventory)**.
- Detailed data-flow traced: **7/14**
- Browser/runtime verification: **0 executed sessions** (source-and-screenshot audit only).

### Sources inspected

- [`src/app/farm/[id]/plot/[plotId]/layout.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/layout.tsx) — **detailed trace**
- [`src/app/farm/[id]/plot/[plotId]/page.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/page.tsx) — **detailed trace**
- [`src/app/farm/[id]/plot/[plotId]/PlotLayoutClient.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/PlotLayoutClient.tsx) — structural scan
- [`src/app/farm/[id]/plot/[plotId]/analysis/page.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/analysis/page.tsx) — structural scan
- [`src/app/farm/[id]/plot/[plotId]/raw-data/page.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/raw-data/page.tsx) — structural scan
- [`src/app/farm/[id]/plot/[plotId]/user-inputs/page.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/user-inputs/page.tsx) — structural scan
- [`src/app/farm/[id]/plot/[plotId]/live-assistance/page.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/live-assistance/page.tsx) — structural scan
- [`src/app/farm/[id]/plot/[plotId]/irrigation/page.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/irrigation/page.tsx) — structural scan
- [`src/lib/farm-services.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/farm-services.ts) — **detailed trace**
- [`src/lib/session.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/session.ts) — **detailed trace**
- [`src/components/auth/DevelopmentSessionBootstrap.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/auth/DevelopmentSessionBootstrap.tsx) — **detailed trace**
- [`src/app/api/auth/dev-session/route.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/api/auth/dev-session/route.ts) — **detailed trace**
- [`src/app/farm/error.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/error.tsx) — **detailed trace**
- [`src/components/farm/FarmThemeWrapper.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/FarmThemeWrapper.tsx) — structural scan

## Visible symptoms and layout ownership

The screenshot shows a valid map basemap and white plot boundary with a centered failed-publication panel, a right-side evidence legend reporting **“No scientific surface,”** the stage label **“Stage unknown,”** and a bottom-left **“🔬 NDVI”** control. These are independently observable UI facts, not proof that ASMAE has failed. The page must express both *map context is available* and *scientific publication has not been committed*.

### Findings

| ID | Priority | Evidence | Assessment / required change |
|---|---|---|---|
| RTE-01 | P1 | [`src/app/farm/[id]/plot/[plotId]/layout.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/layout.tsx#L19-L57) / [`src/lib/farm-services.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/farm-services.ts#L39-L97) | **Session scope can be incomplete in development.** `getAuthorizedPlotRouteContext` allows ownerless developer lookup; `mapFarm()` excludes owner IDs; layout passes `session?.userId || farm.userId || farm.ownerId || ''` as `tenantId` to `PlotTelemetryProvider`. Earlier observed `telemetry_scope_incomplete` is explained by this path. Latest screenshot shows the layout now mounts, but the pinned GitHub source still has this defect. Use an authenticated development bootstrap before mounting providers; never fabricate `tenantId`. |
| RTE-02 | P2 | [`src/app/farm/[id]/plot/[plotId]/page.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/page.tsx#L1-L38), [`src/app/farm/[id]/plot/[plotId]/layout.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/layout.tsx#L20-L38) | **Layout and page repeat authenticated context resolution**, though `react.cache` in farm-services mitigates redundant DB work. Consolidate the route context and consistent absence/error states; preserve ownership checks on every action. |
| RTE-03 | P2 | [`src/app/farm/error.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/error.tsx#L1-L70) | **Generic Arabic error is factually misleading for a publisher fault**: “check Internet connection” does not distinguish authentication, backend, publication, or scientific contract failure. Introduce structured localized error explanations and request trace ID; no fake backend diagnoses. |
| RTE-04 | P2 | [`src/app/farm/[id]/plot/[plotId]/PlotLayoutClient.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/PlotLayoutClient.tsx), [`src/components/farm/PlotContextBand.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotContextBand.tsx), [`src/components/farm/plot-context-akaloris.css`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/plot-context-akaloris.css) | Context bar takes substantial screen height, tiny ~10–11px metadata and horizontal scrolling. In screenshot the top band visually dominates science status; shift to a compact adaptive header with farmer/expert switch and status/accessibility controls. |
| RTE-05 | P2 | [`src/app/farm/[id]/plot/[plotId]/irrigation/page.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/irrigation/page.tsx) and [`src/components/irrigation/IrrigationDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/irrigation/IrrigationDashboard.tsx) | Dedicated irrigation route is nested under this plot context. For **observation-only pilot**, route/UI state must not imply physical actuation capability. See P05 for confirmed simulator implementation. |
| RTE-06 | P3 | [`src/app/farm/[id]/plot/[plotId]/live-assistance/page.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/app/farm/[id]/plot/[plotId]/live-assistance/page.tsx) | Live Assistance route is a short placeholder rather than a full connected workflow; refactor navigation should label unavailable features honestly. |

### Recommended route composition

```text
Server PlotRouteLayout
  ├─ session/owner authorization (single resolver)
  ├─ geometry/crop-cycle freshness and namespace
  ├─ read-only PlotRouteContext {tenantId, farmId, plotId, geometryHash, cycleId}
  └─ ClientPlotShell
       ├─ ContextHeader (one compact line + tabs)
       ├─ CanonicalPublicationProvider
       ├─ OperationalTelemetryProvider (only with complete namespace)
       └─ active page view (Overview / Raw Data / User Inputs / AgriBrain)
```

**Non-negotiables:** no dev bypass in production; owner identity derived from DB plus actual session; transient session absence must not instantiate scientific or telemetry streams; plot/farm mismatch returns 404; a development bootstrap must be localhost + dev-only, not fake auth for production.

### Acceptance tests

1. Valid owner opens a plot; all downstream scope keys equal DB-owned `(tenant,farm,plot)`.
2. Local dev without cookie sees Bootstrap, establishes real owner-scoped development session, then dashboard loads. No incomplete-scope exception.
3. Foreign-tenant plot denied even if plot ID appears valid; no telemetry/API fetch is sent.
4. Farm deletion/plot reparent/geometry update invalidates display, not silently adopting stale science.
5. 375px, 768px and 1600px viewport header/tab navigation with keyboard focus and no hidden active label.

**Remaining unverified:** actual session/cookie flow, DB queries and browser navigation were not executed in this audit.