# EXECUTION INDEX — Akaloris Plot Workspace implementation
**16 passes; all NOT STARTED (planning complete only).**  
**Source freeze:** 2026-11-12; code baseline `1ee2c20` and planning start `9273098`. Re-pin at implementation start and compare every source change.  
**Repository:** `webClone/AgriWise` · **Target:** integrate/layer0-layer1-observation-pilot, with implementation via separate bounded code branches and PRs.  
**Safety:** irrigation actuation OFF; science monograph unchanged; Draft PR #28 and protected main untouched unless explicitly separately authorized.
## Start here, in order
1. [Master Program](00_MASTER_IMPLEMENTATION_PROGRAM.md) — architecture, scope and release semantics.
2. [Agent Orchestration and Signoff](01_AGENT_ORCHESTRATION_AND_SIGNOFF.md) — nine roles and six rounds R0–R5.
3. [Dependencies and PR Graph](02_DEPENDENCIES_PR_GRAPH_AND_EFFORT.md) — sequencing and concurrency boundaries.
4. [Traceability and Risk Register](03_REQUIREMENTS_TRACEABILITY_AND_RISK_REGISTER.md) — 22 top-level requirements and 18 initial risks.
5. [Adversarial Acceptance Catalog](04_ACCEPTANCE_TEST_CATALOG.md) — ten end-to-end journeys, safety and test commands.
6. [Receipt Template](05_PASS_RECEIPT_AND_PROGRESS_TEMPLATE.md) — no unsupported completion claims.
## All implementation passes
| Pass | Deliverable | Primary agents | Depends on | Status |
|---|---|---|---|---|
| [P00](PASS_P00_Reproducible_baseline_complete_behavior_invent.md) | Freeze and audit baseline | A0+A4+A7 | — | NOT STARTED |
| [P01](PASS_P01_P0_P1_safety_authorization_geometry_and_scient.md) | Resolve authorization/science/geometry/simulation blockers | A6+A3+A2 | P00 | NOT STARTED |
| [P02](PASS_P02_Design_system_responsive_Plot_Workspace_shell_.md) | Design system and responsive shell | A1+A2+A8 | P00–01 | NOT STARTED |
| [P03](PASS_P03_Scoped_Workspace_Store_selection_reducer_tempo.md) | Shared selection/time/scope controller | A2+A6+A4 | P01–02 | NOT STARTED |
| [P04](PASS_P04_Complete_94_concept_Tool_Registry_Dock_permiss.md) | 94-concept Tool Library and Tool Host | A2+A1+A6 | P03 | NOT STARTED |
| [P05](PASS_P05_Tenant_scoped_feature_projection_APIs_geometry.md) | Owner-scoped spatial API and source evidence adapters | A5+A6+A4 | P01,P03 | NOT STARTED |
| [P06](PASS_P06_Unified_Map_Scene_Registry_multilayer_renderin.md) | Unified map scene and independent vector overlays | A3+A2+A4 | P03,P05 | NOT STARTED |
| [P07](PASS_P07_13_ASMAE_State_Laboratory_SIRE_map_integrity_a.md) | 13-state ASMAE and SIRE trustworthy pixel rendering | A4+A3+A7 | P01,P03,P06 | NOT STARTED |
| [P08](PASS_P08_Sensors_Cameras_Ground_Truth_live_telemetry_an.md) | Sensor/camera/photo/ground-truth tools | A5+A3+A6 | P04–06 | NOT STARTED |
| [P09](PASS_P09_Drone_planning_control_live_track_distinction_.md) | Drone mission, flight, imagery distinction | A5+A3+A6 | P04–06 | NOT STARTED |
| [P10](PASS_P10_MESIA_Observatory_receiver_network_coverage_sc.md) | MESIA full observatory and RF experiment tools | A4+A5+A6 | P04–06 | NOT STARTED |
| [P11](PASS_P11_Experiment_Studio_what_if_lab_calibration_and_.md) | Scientific what-if and isolated Experiment Studio | A4+A2+A7 | P03,P04,P07 | NOT STARTED |
| [P12](PASS_P12_Agronomic_Layers_2_through_9_water_nutrients_b.md) | Agronomic Layers2–9, Operations, World Model concepts | A4+A5+A6 | P04,P07,P11 | NOT STARTED |
| [P13](PASS_P13_Unified_event_timeline_historical_time_peel_co.md) | Event chronology, time-peel, cross-source correlation | A2+A4+A7 | P05,P07–12 | NOT STARTED |
| [P14](PASS_P14_Product_UX_polish_Arabic_French_accessibility_.md) | UX/Arabic RTL/French/a11y/browser performance | A1+A8+A3 | P02–13 | NOT STARTED |
| [P15](PASS_P15_Full_staging_end_to_end_publisher_API_browser_.md) | Controlled production-path staging, release, rollback | A0+A7+A6+A8 | all | NOT STARTED |
## Operations checklist (do not tick prematurely)
- [ ] Assign real reviewers, note A0 through A8 actual identity or clearly call it role-based review.
- [ ] Re-pin repository branch SHA and compare against audited code baseline; reconcile drift and previous audit reports.
- [ ] Execute P00 baseline; save logs, browser traces and source version manifest.
- [ ] Resolve P01 P0/P1 findings with independent fail-old/pass-new tests.
- [ ] Implement P02/P03/P04 before porting tools; preserve fallback.
- [ ] Implement owner-scoped feature adapters and shared map before spatializing all tools.
- [ ] Qualify 13-state SIRE independently and never promote proximity or simulation to state evidence.
- [ ] Integrate device/drone/MESIA/experiment/agronomy tools in independent bounded passes.
- [ ] Qualify multi-lane timeline and historical knowledge cutoff.
- [ ] Run responsive/RTL/a11y/performance/browser/hardware-negative gates.
- [ ] Run controlled staging Publisher→FastAPI→Next→Browser exact identity proof.
- [ ] Verify rollback feature flag, 0 physical actuator commands, preserved releases/main/PR #28.
## What is not accepted by this plan
This folder does **not** establish that source code was changed, any tests passed, browser interaction worked, 94 tools are functional, real sensor/flight/RF devices connected, or physical field validation occurred. All status cells remain NOT STARTED until independently verified evidence is attached.
## Release semantics
Catalog completeness, UI parity, scientific visualization and physical hardware qualification are **separate** scorecards. Physical field trial and physical actuation remain separate projects with their own authority and test evidence. 
