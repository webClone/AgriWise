# P12 — Agronomic Layers 2 through 9 water nutrients biology planning operations and reports
**Status:** NOT STARTED · **Dependency:** P04,P07,P11 · **Primary agents:** A4+A5+A6 · **Independent reviews:** A4 science, A6 security/safety, A7 adversarial QA, A8 UX release as applicable  
**Proposed code branch:** `feat/plot-workspace-p12-agronomy-tools` (not created).
## Goal and critical boundaries
Expose the existing crop, phenology, water, soil, nutrient, biological, operations, planning, yield, suitability, risk, prescriptions and reports as first-class tools, integrated with the same ASMAE evidence, map and zone. Product breadth is not permission to market an unverified proxy or invent recommendations. World Model/Omega planned concepts remain discoverable.
## Code paths and anticipated integrations
- `services/agribrain/layer2_veg_int/phenology_engine.py`
- `services/agribrain/layer3_water/irrigation_optimizer.py`
- `services/agribrain/layer4_nutrients/vra/engine.py`
- `services/agribrain/layer5_bio/runner.py`
- `services/agribrain/layer6_exec/runner.py`
- `services/agribrain/layer7_planning/runner.py`
- `services/agribrain/layer8_prescriptive/runner.py`
- `services/agribrain/layer9_interface/engines/what_if_sandbox.py`
- `services/agribrain/world_model/contracts.py`
- `src/components/farm/intelligence/AgriBrainWorkspace.tsx`
- `src/components/farm/intelligence/ZoneDetailStrip.tsx`
- `src/components/irrigation/IrrigationDashboard.tsx`
## Detailed implementation tasks
### P12.01 — Build agronomy-to-tool matrix
L2: crop identity/phenology; L3: hydrological diagnostics; L4: nutrient stress/needs/VRA preview; L5: weather/biotic pressure; L6: field task feasibility/interventions; L7: planting/suitability/rotation/yield/economics; L8: proposed prescription/constraints; L9: AI explanation, reports, scenarios. Each maps to Tool Registry entry with required evidence, available geometry and maturity.

### P12.02 — Crop phenology and calendar
Use actual stage authority/source and observed/hypothesized progression, not administrative crop-cycle status as calibrated crop stage. Timeline supports stage confidence and event annotations; panel highlights plot stage and associated stress signals.

### P12.03 — Water and soil diagnostic workbench
Show ASMAE root-zone and canopy water, water stress probability, soil proxy depth, weather and irrigation events with sigma/source scope; compare sensor evidence without assuming physical depth equivalence. Deprecated `IrrigationOptimizer` never silently becomes new production prescription.

### P12.04 — Nutrient and salinity suite
Show nutrient source surfaces, soil analyses, salinity exposure and VRA zone *preview*. Units, crop species, soil lab calibration and permissions required before an application dosage; default only evidence and scouting recommendation.

### P12.05 — Biotic and disease investigation
Show pathogen pressure hypotheses, stress confounders, weather pressure and sample/photos in selected zone; avoid auto-confirming a disease species or chemical use. Explain model limits and require physical confirmation when relevant.

### P12.06 — Field operations and action lifecycle
Task/scouting/inspection can be created with real owner-scoped geometry, assignment and status history. Separate suggestion, proposal, authorization, schedule, dispatch and confirmed execution. Hardware action disabled by policy.

### P12.07 — Planning/suitability/economics
Present crop rotation, planting windows, yield distributions, water feasibility and economics as forecast/model outputs with uncertainty and horizon. Put scalar planning results in charts, spatial outputs only with qualified support.

### P12.08 — Expert/farmer differentiation
Farmer mode summarizes actionable observation and confidence. Expert mode exposes drivers, priors, exact source, alternative explanation, model version, thresholds and publication. Same underlying scientific truth.

### P12.09 — World Model and Omega placeholders
Show intended user journeys (multi-depth hydrology, scenario actions, learned transitions) from contracts/monograph as concept workbenches only. Clearly mark research or not yet implemented; do not fabricate model rollout.

### P12.10 — Cross-tool assistance and export
Open AI advisor/report on chosen sensor/zone/state and source evidence manifest; AI output distinguishes observed vs inferred vs hypothetical and links evidence. No treating free-text advice as signed prescriptive authority.
## Pass acceptance / adversarial cases
- **P12-G01** Unverified phenology administrative status never masquerades as calibrated stage.
- **P12-G02** VRA preview cannot auto-issue fertilizer prescription/actuator command.
- **P12-G03** Disease probability is not a confirmed lab diagnosis and has confounder link.
- **P12-G04** Every map overlay displays valid source, time, unit and uncertainty or explicitly unavailable.
- **P12-G05** Task status transitions do not claim field completion without evidence.
- **P12-G06** World Model/Omega entries visible without fictional runtime outputs.
- **P12-G07** Selected sensor/zone/ASMAE state remains in scope across agronomic tools.
- **P12-G08** Irrigation safety flag false yields zero real actuator dispatches.
## Evidence needed to close
- Tool availability+source table for Layers2–9 and World Model/Omega.
- Cross-tool agronomy panels and contextual map link screenshots.
- Source/uncertainty/authority language review, permissions matrix.
- Sandbox/field task negative tests, farmer-expert UX comparison.
**HOLD:** unsupported fertilizer/chemical/irrigation command, false diagnosis or planned World Model results presented as real.
## Multi-agent R0–R5 protocol
R0 pin exact source & immutable fixture; R1 owner writes proposal and independent reviewer separately critiques; R2 A4+A6/A3 challenge math, source identity, device safety, security and geometry; R3 A7 executes negative tests; R4 A2+A8 perform integrated real-browser and performance review where UI changes; R5 A0 issues signed GO/HOLD with exact commit, logs, rollback and remaining risks. None of these reviews should be marked complete until actually executed.
