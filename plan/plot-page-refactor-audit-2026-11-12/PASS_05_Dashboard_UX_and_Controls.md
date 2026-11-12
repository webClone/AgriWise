# Akaloris Plot Page — Pass 05: Dashboard Experience, Navigation, Forms, and Irrigation Controls

> **Audit evidence scope:** Static GitHub source inspection pinned to commit `1ee2c20119af29dd1f0a0b46c85217d91206b744` and the provided 1600×900 browser screenshot. Files were retrieved from the repository and inspected structurally; selected control-flow paths were deep-traced. No local Next.js/FastAPI runtime, tests, browser automation, or production hardware was executed. Findings distinguish observed screenshot behavior, confirmed source behavior, and test-required hypotheses.


## Pass coverage

- Source files inventoried and inspected: **12/12 (100% of this pass’s selected static inventory)**.
- Detailed data-flow traced: **6/12**
- Browser/runtime verification: **0 executed sessions** (source-and-screenshot audit only).

### Sources inspected

- [`src/components/farm/PlotDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx) — **detailed trace**
- [`src/components/farm/PlotContextBand.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotContextBand.tsx) — **detailed trace**
- [`src/components/farm/PlotControls.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotControls.tsx) — structural scan
- [`src/components/farm/plot-context-akaloris.css`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/plot-context-akaloris.css) — **detailed trace**
- [`src/components/farm/PlotPageClient.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotPageClient.tsx) — structural scan
- [`src/components/farm/RawTelemetryHub.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/RawTelemetryHub.tsx) — structural scan
- [`src/components/farm/RawSatelliteViewer.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/RawSatelliteViewer.tsx) — structural scan
- [`src/components/farm/PlotIdentityForm.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotIdentityForm.tsx) — structural scan
- [`src/components/farm/PlotVisualGroundTruth.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotVisualGroundTruth.tsx) — structural scan
- [`src/components/farm/DecisionConfiguration.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/DecisionConfiguration.tsx) — **detailed trace**
- [`src/components/irrigation/IrrigationDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/irrigation/IrrigationDashboard.tsx) — **detailed trace**
- [`src/hooks/useIrrigationState.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useIrrigationState.ts) — **detailed trace**

## Visual review against the supplied screenshot

The **basemap fills almost all available height**, but a prominent centered error panel competes with scientific content. The right evidence card and Color Lens occupy map real estate; bottom-left NDVI debug remains visible without a scientific surface. The top context bar is attractive but extremely compact and hard to scan. Controls are scattered rather than organized into a clear observing workflow.

### Findings

| ID | Priority | Source | Assessment / refactor |
|---|---|---|---|
| UX-01 | P1 | [`src/components/farm/PlotDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx#L752-L775) | Full-center error overlay is driven by provider error even if basemap is healthy. Prefer persistent nonmodal job status / right-side status drawer. Distinguish `RUNNING`, `waiting`, `failed`, `no_science`, `stale`, `invalid` and don't offer retry on a nonterminal wait. |
| UX-02 | P1 (integrity of user-facing status) | [`src/hooks/useIrrigationState.ts`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useIrrigationState.ts#L293-L411), [`src/components/irrigation/IrrigationDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/irrigation/IrrigationDashboard.tsx#L249-L392) | **Irrigation control is a local simulator presented with operational vocabulary.** Fleet/events/budget use `generateMock*`, `dispatchCommand()` logs a request and returns `success:true`, `emergencyStopAll()` logs and returns true. This source DOES NOT demonstrate real hardware actuation, but a user may believe an E-STOP or command succeeded. During observation-only pilot, hide live actuation UI or label entire workspace `SIMULATION ONLY — no connected actuator`; never represent a simulated E-STOP as hardware safety. Server/hardware interlock remains separate. |
| UX-03 | P2 | [`src/components/farm/PlotDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx#L360-L680) | Many absolute/fixed-position floating buttons use `calc(50% + 440px)` and hardcoded top/bottom offsets; sidebar uses rigid `width:320px` and `bottom:170px` [`src/components/farm/intelligence/RawDataSidebar.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/RawDataSidebar.tsx#L169-L205). Layout collision on smaller screens and accessibility zoom is likely; test, do not assert precise breakpoints without browser. |
| UX-04 | P2 | [`src/components/farm/DecisionConfiguration.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/DecisionConfiguration.tsx#L38-L41) / [`src/components/farm/DecisionConfiguration.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/DecisionConfiguration.tsx#L80-L96) | “Model Recalibrated” badge is driven by a timer, not a confirmed model recalibration receipt. Replace with `Saved` / `Recalibration queued` / `Recalibrated: receipt ID`, only when backend confirms. |
| UX-05 | P2 | [`src/components/farm/PlotContextBand.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotContextBand.tsx) / [`src/components/farm/plot-context-akaloris.css`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/plot-context-akaloris.css) | Header/legend cramped; user cannot immediately distinguish “Stage unknown” from “pipeline failed.” Replace with 3-line information hierarchy: plot identity, actual science status+as-of, current view/actions. |
| UX-06 | P2 | [`src/components/farm/RawSatelliteViewer.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/RawSatelliteViewer.tsx) / [`src/components/farm/RawTelemetryHub.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/RawTelemetryHub.tsx) | Raw tab uses separate satellite/intelligence views with sources labeled “Live”. Raw data needs explicit `observed_at`, `ingested_at`, supplier, trustedness and spatial support; don't label caches/live gateway views as validated science. |
| UX-07 | P2 | [`src/components/farm/PlotControls.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotControls.tsx) / [`src/components/farm/PlotIdentityForm.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotIdentityForm.tsx) | Mutating controls (delete, geometry edit, crop metadata) coexist with scientific view. Require confirmation and plot-scope reset, complete geometry epoch propagation, and no silent reuse of stale posterior. |
| UX-08 | P2 | [`src/components/farm/PlotDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/PlotDashboard.tsx) | Single component owns map, error state, retry, satellite vision refresh, modal workflows, buttons, multiple panel toggles, display policies. Break into task-focused bounded components and shared design primitives. |

### Proposed new information architecture

**Top context:** plot name, crop & confirmed phenology (or “not determined”), authoritative snapshot timestamp/status, baseline condition.

**Primary view:** full map with minimal controls; narrow contextual science status panel; configurable legend but never hidden evidence. **Actions sidebar:** `Observe`, `Inspect`, `Compare dates`, `Explain`, `Export provenance`. Keep “Irrigation” in a separately marked advisory-only area while actuation is disabled.

**Interaction states:** Load (skeleton) → Basemap only (no science) → Scientific preparation (progress, jobId) → Science committed (surface+legend) → Degraded/last-known-good → Scientific failure. No hard timeout masquerading as failed run.

### Acceptance criteria

- 320px/375px/768px/1024px/1600px screenshots, landscape tablet, zoom 200%, screenreader order, clear keyboard focus, no panel overlap.
- Map remains usable through delayed science computation; no blocker overlay except consent/security-critical modal.
- No fabricated scientific, telemetry, hardware, recalibration or E-STOP successes.
- Palette/legend and evidence status work when there is no raster.
- Plot identity/source status/active crop are independently labeled; stage unknown is allowed only when actually missing.