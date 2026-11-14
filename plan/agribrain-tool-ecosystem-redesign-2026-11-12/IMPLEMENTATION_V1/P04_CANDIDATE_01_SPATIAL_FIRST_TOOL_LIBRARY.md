# P04 Candidate 01 — A new tool experience, not a legacy dashboard migration

Baseline: `8220621759290652f4021560307026ceb956718a`; branch `feat/plot-workspace-p04-tool-registry`.

## Locked product decision
The new Akaloris page is a **spatial-first, interactive work environment**, not an adaptation of the old PlotDashboard layout. P04 makes tool discovery and the future tool runtime possible, but must never dictate the eventual map canvas, visualization model, tool UI, or exact panel layout. P02/P03 shell and legacy integrations are transitional.

## Evidence and identity
The Pass 08 source contains **94 intended product tool entries** in six groups: 17 acquisition, 12 ASMAE, 13 drones, 15 MESIA, 19 agronomy, 18 operations. The existing P02 preview also contains **94 separately phrased concepts** across different groups. These lists are **not identical**. Preserve the P02 preview while the reviewed canonical-ID/alias crosswalk is developed; never silently hide or treat an unmatched entry as implemented.

## P04 candidate scope and limitations
- Source-grounded canonical 94 draft manifest, stable IDs, family and source references.
- Read-only discovery mode (every tool can be described; no tool is marked executable, scientifically certified, connected to equipment, or permission-granted by a local manifest).
- Search/discovery helpers and regression tests.
- **Not yet shipped:** localized Arabic/French titles, production capability qualification, full interactive library, pinned dock, context host, component mounting and browser proof. Do not declare P04 complete.

## Interaction design for P04.03–P04.07
1. The live map and selected geometry remain visible when the user opens tools. A selected zone, sensor or pixel is context, not a new page.
2. User invokes a semantic command (Explore, Compare, Simulate, Plan), then the compatible tool host enters context-panel, split, or full-workbench mode. Never suggest physical dispatch without server authorization.
3. A tool preview explains what is needed when a capability is unqualified. It must not display invented sensor values or simulated outputs as observations.
4. The library is a searchable instrument palette, not 94 permanent buttons. Favorites are 5–8 user-local pinned instruments with tenant-safe scope.
5. A closed tool returns focus to the map or launching control. Mobile uses a contextual drawer, desktop uses adaptive split/full canvas; RTL and keyboard access are first-class.
6. Subsequent passes must **remove** legacy PlotDashboard dependencies once their real map interactions are replaced, instead of accumulating wrapper panels.

## Next completion criteria
- P04-G01: 94 Pass 08 concepts with reviewed aliases/crosswalk for all 94 P02 preview labels.
- P04-G02/03: Future/hardware capabilities disclose prerequisites and remain non-executable without authoritative server capability; no fake readiness.
- P04-G04/05/06: Tool host preserves workspace plot, crop, geometry, selected entity and time; restoring focus; V2-off fallback.
- Native frontend tests, TS/build and mounted-browser LTR/RTL/mobile receipts at exact commit SHA.
