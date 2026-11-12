# P04 — Complete 94-concept Tool Registry, Dock, permissions and tool hosting
**Status:** NOT STARTED · **Prerequisite:** P03 · **Primary:** A2+A1+A6 · **Independent:** A7+A6/A4 as appropriate  
**Future branch:** `feat/plot-workspace-p04-tool-registry` (not created). 

## Goal, scientifically valid scope
Every intended tool must be visible, searchable, configurable and openable at its actual maturity level, without hardcoding 94 interactive windows into PlotDashboard. Capability state controls actions, not discovery. Preserve existing tools while new host provides contextual side panel and optionally full workbench.
## Target source files and new proposed modules
- `plan/agribrain-tool-ecosystem-redesign-2026-11-12/PASS_08_Complete_Tool_Registry.md`
- `src/components/farm/PlotDashboard.tsx`
- `src/components/farm/drone/DroneMissionPanel.tsx`
- `src/components/farm/intelligence/SensorNetworkWorkspace.tsx`
- `src/components/farm/intelligence/MesiaObservatoryWorkspace.tsx`
- `src/components/farm/intelligence/AgriBrainWorkspace.tsx`
- `src/components/farm/workspace/ToolRegistry.ts (proposed)`
- `src/components/farm/workspace/ToolDock.tsx (proposed)`
- `src/components/farm/workspace/ToolHost.tsx (proposed)`
## Implementation packages — in exact order
### P04.01 — Normalize catalog and aliases
Treat 94 audit items as source concepts; assign stable canonical IDs and aliases for overlapping ideas. Required fields: ID, title (Arabic/English/French), group, source module, inputs, map entity kinds, supported modes, maturity, action eligibility, permission, required evidence, and reason unavailable.

### P04.02 — Define two-axis capability state
Maturity = built UI / backend / prototype / hardware / future; runtime capability = ready/read-only/simulation-only/missing data/missing equipment/permission blocked/service down/safety locked. Permission is server authoritative; tool registry metadata is not a security gate.

### P04.03 — Build searchable Tool Library
Show all 94 concepts in All view even if future; support category filtering, fuzzy search, synonyms and semantic labels. Every entry opens actual tool, design preview or setup/protocol panel; never fake output/results to fill an empty state.

### P04.04 — Implement pinned Tool Dock
User pins/reorders 5–8 favorites; include Map, 13 ASMAE, Sensors, Drones, MESIA, Experiments initially. Local preference persists per user, not across tenants by accident. Support keyboard navigation, tooltip, aria-label, RTL order and mobile drawer.

### P04.05 — Unify tool host modes
Create `context`, `split`, `full_workbench` hosts where selected plot/zone/time stays visible. Legacy Drone/Sensor/MESIA components can mount temporarily via adapter; host preserves control flow and close/back behavior.

### P04.06 — Context launch from map feature
Map selected kind determines compatible-tool actions via declared `accepts` and permissions, e.g. zone -> ASMAE, drone mission, sampling, experiment; sensor -> device, calibration and state comparison. Do not advertise an unavailable physical action.

### P04.07 — Make action and provenance semantics consistent
Every action explicitly says View/Analyze/Preview/Simulate/Plan/Propose/Authorize/Dispatch; no UI labels that collapse planned vs actual. Record opened tool and selected context for debuggability, avoiding sensitive payload logging.

### P04.08 — Tool catalog parity gate
Cross-reference 94 audited source concepts against new IDs/aliases and existing page controls. Confirm no module lost; flag undocumented/duplicate tools for review rather than silently dropping.
## Release / adversarial gates
- **P04-G01** Every one of 94 intended concepts resolves to a visible searchable catalog entry or explicit reviewed alias.
- **P04-G02** A future MESIA tool launches setup/description but cannot invent physical result.
- **P04-G03** User without hardware permission can view plan but cannot obtain dispatch authority via client toggle.
- **P04-G04** Tool selection preserves plot ID, geometry epoch, selected zone and historical time.
- **P04-G05** Closing a tool restores map focus and keyboard focus.
- **P04-G06** Old Drone/Sensors/MESIA/Experiment controls remain accessible under V2 and V2-off.
## Required pass artifacts
- Complete versioned ToolManifest JSON/TS type, semantic aliases and maturity/permission matrix.
- Screenshots Library/Dock/empty state Arabic+English and evidence of all concepts.
- Host interoperability smoke suite + exact tool parity register.
- Migration decision on overlap/renaming; V2 fallback functional.
**HOLD:** missing tools, simulated action displayed as live, or tool manifest used as authority.
## Multi-agent handoff
R0 pinned source baseline/negative fixtures → R1 author vs independently prepared design critique → R2 A4 scientific + A6 security and A3 geometry where applicable → R3 A7 adversarial fail-old/pass-new tests → R4 A2/A8 integrated actual-browser check for UI → R5 A0 SHA/test receipts/GO-HOLD and rollback.
