# Pass 05 — Agronomic diagnostics, decisions, planning and reports
**Representative source:** `layer2_veg_int/phenology_engine.py`, `layer3_water/irrigation_optimizer.py`, `layer4_nutrients/vra/engine.py`, `layer5_bio/runner.py`, `layer6_exec/runner.py`, `layer7_planning/runner.py`, `layer8_prescriptive/runner.py`, `layer9_interface/engines/what_if_sandbox.py`, `layer10_sire/surfaces/*.py`, `layer10_sire/explainability.py`, `world_model/contracts.py`.
## Opportunities by scientific layer
- **L2 Vegetation/Crop:** crop-identity posterior, stage/phenology trajectory, growth/development explorer, spectral response, crop cycle comparison.
- **L3 Water:** water limitation, hydraulic profile, root-zone/surface comparison, irrigation requirement *analysis*, water stress and observed irrigation events. `IrrigationOptimizer` is deprecated and should not become a newly endorsed control engine.
- **L4 Nutrients:** nutrient stress/reliability, crop demand, nutrient losses, soil salinity, VRA-zone *preview* and calibration/soil sampling workflow. The VRA engine computes zone rates from spectral data but is not itself an approved fertilizer prescription.
- **L5 Biotic:** weather-driven biological pressure, evidence/confounder inspection, candidate outbreaks and temporal risk; diagnosis must not be relabeled confirmed pathogen identification.
- **L6 Operations:** task priority, feasibility, resource/constraint checks, proposed intervention graph, task status, outcome review; *execution state* must not imply physical execution without receipts.
- **L7 Planning:** crop suitability, planting windows, soil workability, water feasibility, rotations, yield distributions, season plans, economic tradeoffs.
- **L8 Intervention:** conditionally eligible recommendations, zone priority, environmental/spray drift constraints and scheduler; observe-only pilot permits non-actuating scouting and verification actions, not unsupported chemical/irrigation dosage.
- **L9 Intelligence:** What-If Sandbox, evidence explanation, role-sensitive advisor, anomaly exploration, expert/farmer reports, notification and follow-up workflows. `what_if_sandbox.py` contains estimated/default baseline logic; outputs must be sandbox-tagged and cannot replace historical observations.
- **World model:** contracts for five-soil-layer state, environmental disturbances and action vectors exist; these are *foundation/possible future tools*, not proof of deployed Omega world-model inference.
## Extracted high-value products
Phenology Calendar; Crop Identification; Soil Profile Viewer; Water Balance Studio; Root-Zone Diagnostics; Irrigation Scenario Simulator; Nutrient Supply/Demand; VRA Preview; Salinity Survey; Biotic Pressure Monitor; Scouting Planner; Crop Suitability Comparison; Planting Window Planner; Rotation Explorer; Yield Trajectory; Cost/Risk Simulator; Action Feasibility; Task Scheduler; Evidence-Based AI Advisor; Report Builder; Historical Compare; Future World Model Studio.
## Correlation examples
Select water-stress cell -> read ASMAE water + sigma, inspect local sensors and rainfall events, compare SIRE water product history, start hypothetical irrigation scenario with separate simulated overlay, create a scouting task. A task marker appears only with real task spatial identity, not an algorithmic guess.
Select disease-risk zone -> view actual weather and optical evidence, uncertainty, confounders, field photos, follow-up sample task. No chemical treatment without explicit authorized action artifact.
## Product controls
Plan, Suggest, Simulate, Recommend, Authorize, Dispatch and Confirm-Executed are **different verbs/states**. UI/notification/report/AI must use the same visibility policy for every proposed recommendation. No default treatment doses in zone UI. Keep physical irrigation interlock off.
## Evidence limitations
This pass verifies backend modules and interfaces exist and contain algorithms. It does not independently validate agronomic effectiveness, calibrated yield accuracy or production authorization of any tool.
