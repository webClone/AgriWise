# Akaloris Plot Page — Pass 06: Scientific Intelligence Panels, Evidence Wording, and Advice Safety

> **Audit evidence scope:** Static GitHub source inspection pinned to commit `1ee2c20119af29dd1f0a0b46c85217d91206b744` and the provided 1600×900 browser screenshot. Files were retrieved from the repository and inspected structurally; selected control-flow paths were deep-traced. No local Next.js/FastAPI runtime, tests, browser automation, or production hardware was executed. Findings distinguish observed screenshot behavior, confirmed source behavior, and test-required hypotheses.


## Pass coverage

- Source files inventoried and inspected: **27/27 (100% of this pass’s selected static inventory)**.
- Detailed data-flow traced: **6/27**
- Browser/runtime verification: **0 executed sessions** (source-and-screenshot audit only).

### Sources inspected

- [`src/components/farm/intelligence/PlotLoadingSequence.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/PlotLoadingSequence.tsx) — **detailed trace**
- [`src/components/farm/intelligence/EnginePipelinePanel.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/EnginePipelinePanel.tsx) — **detailed trace**
- [`src/components/farm/intelligence/RawDataSidebar.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/RawDataSidebar.tsx) — **detailed trace**
- [`src/components/farm/intelligence/FieldInsightBar.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/FieldInsightBar.tsx) — structural scan
- [`src/components/farm/intelligence/FieldSnapshotHUD.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/FieldSnapshotHUD.tsx) — structural scan
- [`src/components/farm/intelligence/TimelineStrip.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/TimelineStrip.tsx) — structural scan
- [`src/components/farm/intelligence/ResolutionCoverageHUD.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ResolutionCoverageHUD.tsx) — structural scan
- [`src/components/farm/intelligence/MapLayerDock.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/MapLayerDock.tsx) — structural scan
- [`src/components/farm/intelligence/MapModeSwitcher.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/MapModeSwitcher.tsx) — structural scan
- [`src/components/farm/intelligence/CropIdentityBanner.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/CropIdentityBanner.tsx) — structural scan
- [`src/components/farm/intelligence/AgriBrainWorkspace.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/AgriBrainWorkspace.tsx) — structural scan
- [`src/components/farm/intelligence/AgriBrainCommandCenterClient.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/AgriBrainCommandCenterClient.tsx) — structural scan
- [`src/components/farm/intelligence/ZoneInspector.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ZoneInspector.tsx) — structural scan
- [`src/components/farm/intelligence/ZoneDetailStrip.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ZoneDetailStrip.tsx) — **detailed trace**
- [`src/components/farm/intelligence/MethodologyDrawer.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/MethodologyDrawer.tsx) — structural scan
- [`src/components/farm/intelligence/HistogramDrawer.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/HistogramDrawer.tsx) — structural scan
- [`src/components/farm/intelligence/QuicklookStrip.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/QuicklookStrip.tsx) — structural scan
- [`src/components/farm/intelligence/TruthEnvelopeRenderer.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/TruthEnvelopeRenderer.tsx) — structural scan
- [`src/components/farm/intelligence/EngineFarmerView.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/EngineFarmerView.tsx) — structural scan
- [`src/components/farm/intelligence/EngineExpertView.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/EngineExpertView.tsx) — structural scan
- [`src/components/farm/intelligence/SidebarFarmerView.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/SidebarFarmerView.tsx) — **detailed trace**
- [`src/components/farm/intelligence/SidebarExpertView.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/SidebarExpertView.tsx) — structural scan
- [`src/components/farm/intelligence/SubsystemLayerDashboard.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/SubsystemLayerDashboard.tsx) — structural scan
- [`src/components/farm/intelligence/SensorNetworkWorkspace.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/SensorNetworkWorkspace.tsx) — structural scan
- [`src/components/farm/intelligence/MesiaObservatoryWorkspace.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/MesiaObservatoryWorkspace.tsx) — **detailed trace**
- [`src/components/farm/intelligence/WorkspaceIntelPanel.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/WorkspaceIntelPanel.tsx) — structural scan
- [`src/components/farm/intelligence/ModeLens.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ModeLens.tsx) — structural scan

## Scientific UI is an evidence interpreter, not a second estimation engine

The page composes `EnginePipelinePanel`, `RawDataSidebar`, `FieldInsightBar`, `TimelineStrip`, zone cards, diagnostic overlays and MESIA/ASMAE workspaces. Main producers and provenance should remain authoritative; panels must consume an immutable snapshot-scoped view-model, never derive higher scientific authority from appearance or default values.

### Findings

| ID | Priority | Code evidence | Assessment / change |
|---|---|---|---|
| SCI-01 | P1/P2 | [`src/components/farm/intelligence/ZoneDetailStrip.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ZoneDetailStrip.tsx#L18-L115) | **Static treatment-oriented explanations** include irrigation/fertilization/disease-control recommendations keyed to zone category. These are UI copy templates, not verified site-specific agronomy. In observation-only pilot, restrict to scouting and verification suggestions unless source, unit, crop applicability and claim evidence are independently qualified. |
| SCI-02 | P2 | [`src/components/farm/intelligence/SidebarFarmerView.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/SidebarFarmerView.tsx#L208-L238) | VPD alert wording can suggest irrigation frequency or shade nets from a single atmospheric indicator. Explanations need uncertainty, crop/soil compatibility and a `diagnostic_only` label; do not conflate advice with actuator approval. |
| SCI-03 | P2 | [`src/components/farm/intelligence/MesiaObservatoryWorkspace.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/MesiaObservatoryWorkspace.tsx#L75-L79) | Satellite counter defaults to `?? 8` satellites when not available, giving users a fabricated precise-looking number. Use `Not reported` and classify source/provenance. |
| SCI-04 | P2 | [`src/components/farm/intelligence/EngineFarmerView.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/EngineFarmerView.tsx#L271-L283) | Soil/biological summary helpers include fallback words like “Loam” and “Low” when raw inputs are absent. The system must not infer physical conditions from missing data. Prefer explicit `Unknown — field measurement needed`. |
| SCI-05 | P2 | [`src/components/farm/intelligence/EnginePipelinePanel.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/EnginePipelinePanel.tsx#L270-L283), [`src/components/farm/intelligence/RawDataSidebar.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/RawDataSidebar.tsx#L169-L205) | Several scientific/status labels use 7–10px type, weak contrast and tight badges; high cognitive load for farmers. Prioritize 12–14px essential labels, distinct evidence chips, expandable technical detail. |
| SCI-06 | P2 | [`src/components/farm/intelligence/EnginePipelinePanel.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/EnginePipelinePanel.tsx#L333-L362) | Panel computes `plotId` from `window.location.pathname.split('/plot/')` as fallback. Route namespace should flow through an explicit provider, not parse browser URL or use `default`. |
| SCI-07 | P2 | [`src/components/farm/intelligence/AgriBrainCommandCenterClient.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/AgriBrainCommandCenterClient.tsx#L22-L38) | Some empty states use generic “System Ready” or live-model vocabulary. When no published snapshot exists, show `No certified assessment yet`, not affirmative status. |
| SCI-08 | P2 | [`src/components/farm/intelligence/PlotLoadingSequence.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/PlotLoadingSequence.tsx#L260-L352), [`src/components/farm/intelligence/RawDataSidebar.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/RawDataSidebar.tsx) | Missing canonical map is conflated visually with ASMAE worker progress; panels should display clear `Not published`, `Working`, `Pending validation`, `Invalid`, `Unavailable`, and `Historical only` statuses. |
| SCI-09 | P2 | [`src/components/farm/intelligence/WorkspaceIntelPanel.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/WorkspaceIntelPanel.tsx#L100-L115) | This panel appropriately requires render authorization and inspector authorization. Preserve it; use **same** authorizations in map, legend, hover, histogram, downstream advice. |
| SCI-10 | P2 | [`src/components/farm/intelligence/MethodologyDrawer.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/MethodologyDrawer.tsx) / [`src/components/farm/intelligence/TruthEnvelopeRenderer.tsx`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/TruthEnvelopeRenderer.tsx) | Methodology and source-class proof views exist but are detached deep subpanels. Elevate source/date/units/uncertainty/interpretation status into primary evidence inspector. |

### Refactor principles

- One `ScientificDisplayDTO` with `snapshotId`, `publishedAt`, `sourceClass`, `groundingClass`, `spatialSupport`, `uncertainty`, `mode`, `renderAuthorization`, `claimStatus` and `actionability`.
- Explicit **three levels of visibility**: `basemap-only`, `scientific diagnostic raster`, `scientifically qualified intervention`. Observation-only users never see level 3 as available.
- Farmer view: plain labels and “what has been measured, when, by whom” first. Expert view: numerical/covariance/model provenance, exact validation flags and receipt links.
- No default positive assertions for missing evidence; no hardcoded therapy or water volume claims from zone name alone; no speculative crop health status.
- Keep raw telemetry (uncertified), weather forecast, satellite observed pixels, and ASMAE model posterior as separate visibly labeled categories.

### Acceptance gate

For every panel, use an absence matrix: `no data`, `provider observed`, `model-estimated`, `diagnostic only`, `late/unadmitted`, `stale`, `invalid`, `revoked`. Assert the title, warning, controls and advice remain correctly bounded. Verify both farmer and expert modes and specific cases of evidence contradictory across providers.

**Not tested:** actual output from MESIA provider, field VPD agronomy or user comprehension studies. These are source-content and contract audits.