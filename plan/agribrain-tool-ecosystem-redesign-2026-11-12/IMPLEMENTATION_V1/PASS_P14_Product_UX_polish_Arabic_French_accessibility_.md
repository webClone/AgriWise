# P14 — Product UX polish Arabic French accessibility responsive map performance
**Status:** NOT STARTED · **Dependency:** P02–P13 stable contracts · **Primary agents:** A1+A8+A3 · **Independent reviews:** A4 science, A6 security/safety, A7 adversarial QA, A8 UX release as applicable  
**Proposed code branch:** `feat/plot-workspace-p14-accessibility-performance` (not created).
## Goal and critical boundaries
Deliver premium usable production-grade interactive Plot Workspace without sacrificing scientific legibility. Validate against a real rendering environment and complex scenes, not merely screenshots of static cards.
## Code paths and anticipated integrations
- `src/components/farm/workspace/ (proposed)`
- `src/components/farm/map/PlotMapShell.tsx`
- `src/components/farm/map/buildLayerStack.ts`
- `src/components/farm/map/plot-scientific-legend.css`
- `src/components/farm/intelligence/TimelineStrip.tsx`
- `src/components/farm/PlotDashboard.tsx`
- `src/app/farm/[id]/plot/[plotId]/PlotLayoutClient.tsx`
- `tests/frontend/ (extended)`
- `Playwright/browser test harness (proposed; inspect dependency policy before adding)`
## Detailed implementation tasks
### P14.01 — Create visual-language audit
Reconcile 13-state lab, Tool Library, map vector legend, timeline, MESIA, drone, sensor and experiment workbenches. Use consistent typography, spacing, statuses, iconography, controlled colors, numeric precision, dark/light readability; never imply verification via aesthetics.

### P14.02 — RTL/LTR and bilingual layout
Arabic RTL mirrored navigation and inspector, preserved WGS84/map coordinate semantics (map gestures unchanged), mixed Latin device IDs/numbers readable; French/English LTR. Localize dates/units and status vocabulary without changing payload keys.

### P14.03 — Responsive shell scenarios
Test 1600×900, 1366×768, 1024, 768, 430, 360 viewport with inspector/dock/time rail open and map interaction. Avoid absolute-position cards covering map or navigation. Mobile bottom sheet, non-overlapping time rail.

### P14.04 — Keyboard and assistive access
Tab/arrow/escape focus cycle, skip-to-map, spatial-entity list alternative, tool launcher search, ARIA labeling/status, color-independent simulated/observed styles, 200% zoom and reduced motion; contrast review.

### P14.05 — Heavy map scene benchmark
Test large realistic mix: 500+ registered sensors, 1000+ event features, zones, 2 raster renders, 10 drone paths, MESIA receivers, imagery layer. Measure CPU/GPU/frame time, memory peak/steady, JS heap, tiles, GET rate, map-zoom responsiveness.

### P14.06 — Optimize layer loading
Zoom/viewport bbox filtering, server aggregation/clustering, stable DeckGL layer IDs/memo keys, virtualized long lists, lazy loaded full workbenches, cancellation on scope switch, remove leaked listeners/timers and GPU buffers.

### P14.07 — Optimize science UX without bypass
Show last valid snapshot visibly labeled historic while a job waits; activity center distinguishes unavailable/broken/in-progress and validated. Never fake raster pixels or fallback to ungrounded dense map because it looks nicer.

### P14.08 — User journey usability rehearsal
Farmer scenario (open field, inspect warning, schedule sample), expert scenario (ASMAE covariance evidence), drone planner, MESIA bench setup, sensor calibration/alerts and 94-concept search. Record step count, lost context and confusion.

### P14.09 — No-data/offline/error states
Test service unavailable, no device, no raster, invalid geometry, no geolocation, denied permission, canceled experiment, mock drone, stale publication, inability to fetch map tiles, high zoom and reconnect.

### P14.10 — Performance regression budgets
Take P00 baseline and set measured release budgets before optimizing; track p50/p95 time to authorized raster, selection latency, memory 10-minute use, number of subscriptions and frame rate by device class. No invented threshold claims.
## Pass acceptance / adversarial cases
- **P14-G01** Full tool experience usable at 360 and 200% zoom without losing map selection.
- **P14-G02** RTL layout has logical focus order and no clipped mixed text or legends.
- **P14-G03** All actions keyboard accessible through an entity list even if canvas inaccessible.
- **P14-G04** Accessibility status and source class not conveyed only by color.
- **P14-G05** User can pin/search all 94 concepts on touch device.
- **P14-G06** No unbounded subscription count or memory leak on 50 tool/plot transitions.
- **P14-G07** Renderer under representative dense fixture meets thresholds fixed after baseline.
- **P14-G08** Privacy/authority/actuation badges remain readable under any theme.
## Evidence needed to close
- Visual specification, annotated screenshots/video, keyboard/RTL/accessibility review.
- Measured performance baselines, optimizations and p95/heap/GPU telemetry.
- Usability notes from farmer/expert workflows and tracked changes.
- A1+A8+A3+A7 signed browser/interaction parity evidence.
**HOLD:** essential tools inaccessible, false authority conveyed by color, major scene instability or no measurable performance proof.
## Multi-agent R0–R5 protocol
R0 pin exact source & immutable fixture; R1 owner writes proposal and independent reviewer separately critiques; R2 A4+A6/A3 challenge math, source identity, device safety, security and geometry; R3 A7 executes negative tests; R4 A2+A8 perform integrated real-browser and performance review where UI changes; R5 A0 issues signed GO/HOLD with exact commit, logs, rollback and remaining risks. None of these reviews should be marked complete until actually executed.
