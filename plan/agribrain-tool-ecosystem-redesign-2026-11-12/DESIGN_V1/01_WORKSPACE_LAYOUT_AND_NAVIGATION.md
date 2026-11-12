# Design Pass 01 — Workspace Layout, Tool Dock and Information Architecture
## Product rule
The map is the permanent shared work surface. An instrument panel can narrow the map but never replaces it by default. The user can promote complex tools to full workbench while retaining a map mini-context, selected object, time and publication identity. A 'return to map' action is always visible.
## Desktop wireframe (structural; not a screenshot)
```
┌───────────────────────────────────────────────────────────────────────────────┐
│ AKALORIS / Farm / Plot / Crop Cycle     Publication + Time   Evidence Status  │
├──────┬────────────────────────────────────────────┬───────────────────────────┤
│ TOOL │  MAP: basemap + scientific surface         │ CONTEXT INSPECTOR / TOOL │
│ DOCK │  ┌ Layers: SIRE, Sensor, Camera, Mission ┐ │ Selected entity & links  │
│      │  │ plot polygon + zone polygons + pins │   │ Evidence, history, risk  │
│ Map  │  │ drone plan/actual track + RF coverage│  │ Tool-specific controls   │
│ ASMAE│  │ tap/click any object to inspect      │   │ Open full workbench     │
│ Drone│  └────────────────────────────────────────┘│                           │
│ Sensor                                               │                       │
│ MESIA│                MAP CANVAS                  │                           │
│ Labs │                                            │                           │
│ All  │                                            │                           │
├──────┴────────────────────────────────────────────┴───────────────────────────┤
│ TIME: observations | scientific snapshots | events | drones | forecasts      │
└───────────────────────────────────────────────────────────────────────────────┘
```
### Layout behavior
- Header: breadcrumb, active crop cycle, publication ID with as-of time and state (VALID, STALE, PENDING, UNAVAILABLE, INVALID). Snapshot menu enables selecting valid historical publication but never mutates canonical now.
- Tool Dock: 5–8 pinned entries, reorderable, tool search, complete 'All Tools' catalog (all 94 concepts discoverable; canonical IDs can combine overlapping concepts). Count means product concepts, not 94 validated applications.
- Side panel: inspector defaults to selected object; a tool can replace inspector content but contextual identity stays in a sticky strip. If multiple objects overlap at cursor, present a disambiguation list.
- Bottom Time Rail: multi-track rows for acquisition, sensor, drone mission, MESIA receiver observations, field events, scientific snapshots, interventions/tasks and experiment runs; UTC in data, localized readable display.
- Optional split-view: map comparison side-by-side or swipe for two compatible authorized rasters, enforcing same plot and aligned spatial/temporal identity.
- Alerts/Jobs: nonmodal Activity Center for acquisition, worker and publication jobs. Current older verified snapshot may remain visible while a new one is pending, conspicuously marked as historical.
## Map / panel / tool transitions
| Initiator | Selection update | Map result | Inspector | Other tools |
|---|---|---|---|---|
| Click sensor point | sensor ID | focus/highlight pin | device + depth/status | sensor series, evidence links |
| Click SIRE zone | zone ID + publication | highlight polygon | zone support/uncertainty | drone mission proposal, samples |
| Select ASMAE state | state key + publication | authorized raster if qualified | posterior/sigma/status | evidence & temporal history |
| Select drone mission | mission ID | planned dashed line, flown solid only with actual telemetry | mission steps/receipt | imagery, event timeline |
| Select experiment | experiment/run ID | geometry only if declared, simulation watermark | assumptions/results | compare, export |
| Scrub timeline | time mode + cursor | load time-valid entities | source-scope status | retain selection if valid |
## Adaptive layouts
At ~1600px: 64–80px dock; map remainder; 320–420px right panel; 120–180px timeline. At ~1024px: collapsible inspector/dock with minimum map utility. At ~768px: top search and bottom tool drawer, map occupies majority. At ~360px: full viewport map with bottom sheets for selected items and timeline; no off-screen scientific legend.
## Visual language
Use existing Akaloris branding; status and semantic authority are distinguishable via icon+text+pattern, not color alone. Planned route dashed, flown route solid, simulated data watermark/checker. Keep label typography legible at 200% zoom and RTL Arabic. No persistent unrelated floating cards.
## Accessibility & performance
Keyboard through map layer list and entity list; ESC closes tool without clearing plot unless user deliberately clears; focus returns to prior trigger. Dynamic layer group list with aria roles; map alternatives in spatial-entity list. Clustering, spatial extent queries and pointer-event priority avoid dense overlapping map objects. Do not render all 94 tool interfaces simultaneously.
## UX decision
The user retains existing Drone, Sensor, MESIA, ASMAE and Experimental controls. The tool launcher moves their entry points into a unified dock; legacy full-screen components will migrate one by one, not be deleted.
